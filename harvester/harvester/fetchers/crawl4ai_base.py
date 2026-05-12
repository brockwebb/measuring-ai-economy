"""Crawl4ai-backed fetcher base class.

For HTML/JS-heavy sources where a real browser-equivalent extractor is needed.
Lazy-imports crawl4ai so the harvester package can be installed without the
heavy chromium dep — install with `uv sync --extra html` when needed.
"""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


def _build_crawler() -> Any:
    """Construct an AsyncWebCrawler. Lazy import so missing crawl4ai
    only fails at runtime, not import time. Override in tests via mock."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig
    except ImportError as e:
        raise RuntimeError(
            "crawl4ai not installed. Install with: uv sync --extra html"
        ) from e
    return AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False))


class Crawl4aiFetcher(Fetcher):
    """Subclasses provide urls_to_crawl(); optionally override crawl_config()."""

    last_known_good_selector: str | None = None  # sentinel CSS; verified pre-extract

    @abstractmethod
    def urls_to_crawl(self, query: dict[str, Any]) -> Iterable[str]: ...

    def crawl_config(self) -> Any:
        """Default crawl config. Override for source-specific tuning.
        Lazy-imports CrawlerRunConfig so tests can override before crawl4ai
        is even installed."""
        from crawl4ai import CrawlerRunConfig
        return CrawlerRunConfig(
            excluded_tags=["nav", "header", "footer", "aside", "script", "style"],
            exclude_external_links=True,
            verbose=False,
        )

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        seen = seen or set()
        urls = [u for u in self.urls_to_crawl(query) if u not in seen]
        if not urls:
            return
        for url, markdown in asyncio.run(self._crawl_all(urls)):
            self._pace()
            yield self.archive.write(
                source_id=self.source_id,
                source_url=url,
                request_params={"url": url},
                content=markdown.encode("utf-8"),
                content_type="text/markdown",
            )

    async def _crawl_all(self, urls: list[str]) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        crawler = _build_crawler()
        async with crawler:
            config = self.crawl_config() if callable(getattr(self, "crawl_config", None)) else None
            for url in urls:
                try:
                    result = await crawler.arun(url, config=config)
                    md = (result.markdown.fit_markdown
                          if getattr(result.markdown, "fit_markdown", None)
                          else getattr(result.markdown, "raw_markdown", "") or "")
                    results.append((url, md))
                except Exception:
                    continue
        return results
