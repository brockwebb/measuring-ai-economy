"""arxiv fetcher.

API: http://export.arxiv.org/api/query (Atom XML)
Auth: none.
Rate limit: arxiv asks for 3+ sec between requests. We pace at 1 req per 3 sec
(0.333 req/sec).
Pagination: ?start=N&max_results=M.

Note: arxiv's API returns Atom even from the HTTP/JSON-API-style endpoint, so
this fetcher does the XML parsing inline rather than reusing RssFetcher (the
Atom is wrapped in arxiv-specific OpenSearch metadata).
"""

from __future__ import annotations

import json
from typing import Any, Iterable

import feedparser
import httpx

from harvester.fetchers.base import Fetcher
from harvester.types import RateLimit, RawPayload


_BASE_URL = "https://export.arxiv.org/api/query"
_DEFAULT_PER_PAGE = 50
_DEFAULT_MAX_PAGES = 5
_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"


class ArxivFetcher(Fetcher):
    source_id = "arxiv"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(
            requests_per_second=0.333,
            max_retries=3,
            backoff_seconds=[5, 15, 60],
        )

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        """Yield one RawPayload per arxiv entry matching the query.

        Query shape:
            {
                "categories": ["cs.AI", "stat.ML"],
                "keyword": "knowledge graph agent",
                "per_page": 50,
                "max_pages": 5,
                "sort_by": "submittedDate",
                "sort_order": "descending",
            }
        """
        seen = seen or set()
        per_page = int(query.get("per_page", _DEFAULT_PER_PAGE))
        max_pages = int(query.get("max_pages", _DEFAULT_MAX_PAGES))

        with httpx.Client(
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            for page in range(max_pages):
                self._pace()
                params = self._build_params(query, page=page, per_page=per_page)
                resp = client.get(_BASE_URL, params=params)
                resp.raise_for_status()
                xml_text = resp.text

                parsed = feedparser.parse(xml_text)
                entries = list(parsed.entries)
                if not entries:
                    break

                for entry in entries:
                    abs_url = self._canonical_url(entry)
                    if abs_url and abs_url in seen:
                        continue
                    entry_bytes = self._entry_to_bytes(entry)
                    yield self.archive.write(
                        source_id=self.source_id,
                        source_url=abs_url,
                        request_params={
                            **params,
                            "arxiv_id": getattr(entry, "id", ""),
                        },
                        content=entry_bytes,
                        content_type="application/xml",
                    )

                if len(entries) < per_page:
                    break

    @staticmethod
    def _build_params(query: dict[str, Any], *, page: int, per_page: int) -> dict[str, Any]:
        parts: list[str] = []
        if categories := query.get("categories"):
            cat_or = " OR ".join(f"cat:{c}" for c in categories)
            parts.append(f"({cat_or})")
        if keyword := query.get("keyword"):
            parts.append(f'all:"{keyword}"')
        search_query = " AND ".join(parts) if parts else "all:*"
        return {
            "search_query": search_query,
            "start": page * per_page,
            "max_results": per_page,
            "sortBy": query.get("sort_by", "submittedDate"),
            "sortOrder": query.get("sort_order", "descending"),
        }

    @staticmethod
    def _canonical_url(entry: Any) -> str:
        for link in entry.get("links", []):
            if link.get("rel") == "alternate" and link.get("href"):
                return link["href"]
        return entry.get("id", "")

    @staticmethod
    def _entry_to_bytes(entry: Any) -> bytes:
        record = {
            "id": entry.get("id"),
            "title": entry.get("title"),
            "summary": entry.get("summary"),
            "published": entry.get("published"),
            "updated": entry.get("updated"),
            "authors": [a.get("name") for a in entry.get("authors", []) if a.get("name")],
            "tags": [t.get("term") for t in entry.get("tags", []) if t.get("term")],
            "links": [{"rel": link.get("rel"), "href": link.get("href"), "type": link.get("type")}
                      for link in entry.get("links", [])],
            "arxiv_primary_category": entry.get("arxiv_primary_category", {}).get("term")
                if isinstance(entry.get("arxiv_primary_category"), dict) else None,
            "arxiv_doi": entry.get("arxiv_doi"),
            "arxiv_journal_ref": entry.get("arxiv_journal_ref"),
        }
        return json.dumps(record, sort_keys=True).encode("utf-8")
