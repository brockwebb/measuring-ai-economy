"""Federal Register fetcher.

API: https://www.federalregister.gov/developers/documentation/api/v1
Auth: none.
Rate limit: undocumented; we pace at 1 req/sec to be polite.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from harvester.fetchers.http_api import HttpApiFetcher
from harvester.types import RateLimit


class FederalRegisterFetcher(HttpApiFetcher):
    source_id = "federal_register"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(
            requests_per_second=1.0,
            max_retries=3,
            backoff_seconds=[2, 5, 15, 60],
        )

    def base_url(self) -> str:
        return "https://www.federalregister.gov/api/v1/documents.json"

    def build_params(self, query: dict[str, Any], *, page: int) -> dict[str, Any]:
        per_page = int(query.get("per_page", 100))
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

    def extract_items(self, body: dict[str, Any]) -> Iterable[dict[str, Any]]:
        return body.get("results", [])

    def item_to_payload_kwargs(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_url": item.get("html_url") or item.get("pdf_url") or "",
            "content_type": "application/json",
            "content_bytes": json.dumps(item, sort_keys=True).encode("utf-8"),
            "item_index": item.get("document_number"),
        }
