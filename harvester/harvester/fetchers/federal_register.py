"""Federal Register fetcher.

API: https://www.federalregister.gov/developers/documentation/api/v1
Auth: none.
Rate limit: undocumented; we pace at 1 req/sec to be polite.
Pagination: ?page=N, max 1000 per page.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

import httpx

from harvester.fetchers.base import Fetcher
from harvester.types import RateLimit, RawPayload


_BASE_URL = "https://www.federalregister.gov/api/v1/documents.json"
_DEFAULT_PER_PAGE = 100
_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"


class FederalRegisterFetcher(Fetcher):
    """Fetches documents from federalregister.gov."""

    source_id = "federal_register"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(
            requests_per_second=1.0,
            max_retries=3,
            backoff_seconds=[2, 5, 15, 60],
        )

    def iter_payloads(self, query: dict[str, Any]) -> Iterable[RawPayload]:
        """Yield one RawPayload per document matching the query.

        Query shape (matches FR API conditions):
            {
                "term": "artificial intelligence",
                "type": ["RULE", "PRORULE", "NOTICE", "PRESDOCU"],
                "publication_date_gte": "2026-03-01",
                "publication_date_lte": "2026-05-11",
                "per_page": 100,
                "max_pages": 5,
            }
        """
        per_page = int(query.get("per_page", _DEFAULT_PER_PAGE))
        max_pages = int(query.get("max_pages", 10))

        with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=30) as client:
            for page in range(1, max_pages + 1):
                self._pace()
                params = self._build_params(query, page=page, per_page=per_page)
                resp = client.get(_BASE_URL, params=params)
                resp.raise_for_status()
                body = resp.json()
                results = body.get("results", [])
                if not results:
                    break

                for result in results:
                    payload_bytes = json.dumps(result, sort_keys=True).encode("utf-8")
                    yield self.archive.write(
                        source_id=self.source_id,
                        source_url=result.get("html_url") or result.get("pdf_url") or "",
                        request_params={**params, "result_index": result.get("document_number")},
                        content=payload_bytes,
                        content_type="application/json",
                    )

                # If this page wasn't full, we've reached the end.
                if len(results) < per_page:
                    break

    @staticmethod
    def _build_params(query: dict[str, Any], *, page: int, per_page: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "per_page": per_page,
            "page": page,
            "order": query.get("order", "newest"),
        }
        if "term" in query:
            params["conditions[term]"] = query["term"]
        if "type" in query:
            params["conditions[type][]"] = query["type"]
        if "publication_date_gte" in query:
            params["conditions[publication_date][gte]"] = query["publication_date_gte"]
        if "publication_date_lte" in query:
            params["conditions[publication_date][lte]"] = query["publication_date_lte"]
        return params
