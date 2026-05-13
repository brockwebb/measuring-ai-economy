"""Semantic Scholar Graph API fetcher.

API: https://api.semanticscholar.org/graph/v1/
Auth: API key via x-api-key header. Without a key, requests share a global
      1000 req/sec pool across all anonymous clients and are throttled
      further during heavy use — expect bursts of 429s independent of your
      own rate. With a key, you get your own quota and higher limits.
      We pace ourselves at 1 req/sec regardless (see rate_limit_spec).
Pagination: ?offset=N&limit=M (limit max 100 for search).

Two modes:
- search (iter_payloads): /paper/search?query=... — used by standalone harvester runs.
- lookup (get_paper / get_references): /paper/{id} and /paper/{id}/references —
  used by CitationChain. These bypass iter_payloads and are exposed as separate
  methods on the fetcher class so CitationChain can drive them directly.

Pagination note: The SS API is offset-based (offset=0 for first page), not
1-indexed like Federal Register. build_params translates page (1-indexed, as
HttpApiFetcher passes it) to offset via: offset = (page - 1) * limit.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

import httpx

from harvester.fetchers.http_api import HttpApiFetcher
from harvester.types import RateLimit, RawPayload


_BASE_URL = "https://api.semanticscholar.org/graph/v1"
_SEARCH_URL = f"{_BASE_URL}/paper/search"
_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"

_PAPER_FIELDS = (
    "paperId,externalIds,title,abstract,authors,venue,year,publicationDate,"
    "citationCount,referenceCount,influentialCitationCount,openAccessPdf,url"
)


def _api_key() -> str | None:
    return os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None


def _headers() -> dict[str, str]:
    h = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    if key := _api_key():
        h["x-api-key"] = key
    return h


class SemanticScholarFetcher(HttpApiFetcher):
    source_id = "semantic_scholar"

    def rate_limit_spec(self) -> RateLimit:
        # Self-imposed politeness, not an API per-client cap. Anonymous traffic
        # shares a global 1000 req/sec pool that gets throttled during heavy
        # use; authenticated keys get their own quota. 1 req/sec is well below
        # either ceiling and keeps the Sunday batch from spiking.
        return RateLimit(
            requests_per_second=1.0,
            max_retries=3,
            backoff_seconds=[2, 5, 15, 60],
        )

    def base_url(self) -> str:
        return _SEARCH_URL

    def build_params(self, query: dict[str, Any], *, page: int) -> dict[str, Any]:
        limit = int(query.get("per_page", 50))
        # SS API is offset-based (offset=0 for first page). HttpApiFetcher passes
        # page as 1-indexed, so we subtract 1 to get offset=0 on the first request.
        # (spec draft had `page * limit` which would skip the first page in prod.)
        return {
            "query": query.get("keyword", ""),
            "offset": (page - 1) * limit,
            "limit": limit,
            "fields": _PAPER_FIELDS,
        }

    def extract_items(self, body: dict[str, Any]) -> Iterable[dict[str, Any]]:
        return body.get("data", [])

    def item_to_payload_kwargs(self, item: dict[str, Any]) -> dict[str, Any]:
        # Prefer the openAccessPdf URL when available, else the paper page url.
        oa_pdf = item.get("openAccessPdf")
        oa_url = oa_pdf.get("url") if isinstance(oa_pdf, dict) else None
        url = (
            oa_url
            or item.get("url")
            or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}"
        )
        return {
            "source_url": url,
            "content_type": "application/json",
            "content_bytes": json.dumps(item, sort_keys=True).encode("utf-8"),
            "item_index": item.get("paperId"),
        }

    # ---- Direct-lookup methods used by CitationChain ----

    def get_paper(self, paper_id: str) -> dict[str, Any] | None:
        """Fetch a single paper by Semantic Scholar paper ID, DOI, or arXiv ID.

        paper_id can be prefixed: 'DOI:10.x/y', 'ARXIV:2305.12345', or a bare
        Semantic Scholar Paper ID.
        """
        url = f"{_BASE_URL}/paper/{paper_id}"
        with httpx.Client(headers=_headers(), timeout=30) as client:
            self._pace()
            resp = client.get(url, params={"fields": _PAPER_FIELDS})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    def get_references(self, paper_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return the references list of a paper. Each ref has the cited paper's
        basic metadata.
        """
        url = f"{_BASE_URL}/paper/{paper_id}/references"
        with httpx.Client(headers=_headers(), timeout=30) as client:
            self._pace()
            resp = client.get(url, params={
                "fields": _PAPER_FIELDS,
                "limit": limit,
            })
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            body = resp.json()
            # Response shape: {"data": [{"citedPaper": {...}}, ...]}
            return [
                d.get("citedPaper")
                for d in body.get("data", [])
                if isinstance(d, dict) and d.get("citedPaper")
            ]
