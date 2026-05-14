"""SSRN fetcher.

Two-stage Crawl4ai flow because SSRN's search page returns a list of papers
that must be parsed before individual paper pages can be fetched:

  Stage 1: crawl https://papers.ssrn.com/sol3/results.cfm?...  for a keyword
  Stage 2: regex out /sol3/papers.cfm?abstract_id=NNNNNNN URLs from the
           rendered markdown
  Stage 3: crawl each paper page

The base Crawl4aiFetcher only supports a single static URL list (via
urls_to_crawl). We override iter_payloads entirely to drive the two-stage
flow. Conservative pacing (0.2 req/sec) because SSRN aggressively blocks
headless browsers.

Replaces the SSRN block of ~/.wintermute/scripts/search_papers.py.
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from typing import Any, Iterable

from harvester.fetchers.crawl4ai_base import Crawl4aiFetcher
from harvester.types import RateLimit, RawPayload


_SEARCH_URL_TEMPLATE = (
    "https://papers.ssrn.com/sol3/results.cfm"
    "?txtbox_Keywords={query}"
    "&subjectId=&jrnlid=&absid=&cls=&stype=1&evtid=&Network=&crit=&orderby=0"
    "&crtest=&recid=&txtbox_Title=&txtbox_Author=&pn=0"
)

_PAPER_URL_RE = re.compile(
    r"https?://papers\.ssrn\.com/sol3/papers\.cfm\?abstract_id=(\d+)"
)


class SsrnFetcher(Crawl4aiFetcher):
    source_id = "ssrn"

    def rate_limit_spec(self) -> RateLimit:
        # SSRN aggressively rate-limits and blocks headless browsers (403,
        # captcha redirects). Pace at 0.2 req/sec (1 req per 5 sec) with
        # long backoffs.
        return RateLimit(
            requests_per_second=0.2,
            max_retries=3,
            backoff_seconds=[10, 30, 120],
        )

    def crawl_config(self) -> Any:
        # Override to lengthen page_timeout — SSRN's CFM-rendered pages are
        # slow. wait_until="networkidle" ensures dynamic content has settled.
        from crawl4ai import CrawlerRunConfig
        return CrawlerRunConfig(
            excluded_tags=["nav", "header", "footer", "aside", "script", "style"],
            exclude_external_links=True,
            verbose=False,
            page_timeout=60000,  # 60 sec
        )

    def urls_to_crawl(self, query: dict[str, Any]) -> Iterable[str]:
        """Unused — we override iter_payloads. Returns [] to satisfy the
        abstract method contract."""
        return []

    def _search_url(self, query: dict[str, Any]) -> str:
        keyword = (query.get("keyword") or "").strip()
        if not keyword:
            return ""
        return _SEARCH_URL_TEMPLATE.format(query=urllib.parse.quote(keyword))

    def _parse_paper_urls(self, search_markdown: str, *, max_results: int) -> list[str]:
        """Extract canonical paper URLs from a crawled search-results
        markdown. De-duplicates by abstract_id (the same paper can appear
        as both title-link and 'read more' link). Caps at max_results."""
        seen_ids: set[str] = set()
        urls: list[str] = []
        for abstract_id in _PAPER_URL_RE.findall(search_markdown):
            if abstract_id in seen_ids:
                continue
            seen_ids.add(abstract_id)
            urls.append(
                f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={abstract_id}"
            )
            if len(urls) >= max_results:
                break
        return urls

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        seen = seen or set()
        search_url = self._search_url(query)
        if not search_url:
            return  # nothing to do without a keyword

        # Stage 1: search page
        self._pace()
        results = asyncio.run(self._crawl_all([search_url]))
        if not results:
            return
        _, search_md = results[0]

        # Stage 2: parse paper URLs
        max_results = int(query.get("per_page", 10))
        paper_urls = [u for u in self._parse_paper_urls(search_md, max_results=max_results) if u not in seen]
        if not paper_urls:
            return

        # Stage 3: crawl each paper page
        for url, markdown in asyncio.run(self._crawl_all(paper_urls)):
            self._pace()
            yield self.archive.write(
                source_id=self.source_id,
                source_url=url,
                request_params={"keyword": query.get("keyword"), "search_url": search_url},
                content=markdown.encode("utf-8"),
                content_type="text/markdown",
            )
