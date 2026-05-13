"""Zenodo fetcher.

API: https://developers.zenodo.org/#records
Auth: none for public records.
Rate limit: unauthenticated cap is ~60 req/min; we pace at 1 req/sec.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from harvester.fetchers.http_api import HttpApiFetcher
from harvester.types import RateLimit


class ZenodoFetcher(HttpApiFetcher):
    source_id = "zenodo"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(
            requests_per_second=1.0,
            max_retries=3,
            backoff_seconds=[2, 5, 15, 60],
        )

    def base_url(self) -> str:
        return "https://zenodo.org/api/records"

    def build_params(self, query: dict[str, Any], *, page: int) -> dict[str, Any]:
        # Zenodo's unauthenticated API caps size at 25 items per page; values
        # above that return HTTP 400. Cap aggressively here so the fetcher
        # works with the default per_page=100 the CLI passes.
        per_page = min(int(query.get("per_page", 25)), 25)
        params: dict[str, Any] = {
            "q": query.get("keyword", ""),
            "page": page,
            "size": per_page,
            "type": query.get("type", "publication"),
            "status": query.get("status", "published"),
            "sort": query.get("sort", "mostrecent"),
        }
        if "publication_date_gte" in query and "publication_date_lte" in query:
            # Zenodo supports range filters via the q string only.
            params["q"] = (
                f'{params["q"]} AND publication_date:'
                f'[{query["publication_date_gte"]} TO {query["publication_date_lte"]}]'
            ).strip()
        return params

    def extract_items(self, body: dict[str, Any]) -> Iterable[dict[str, Any]]:
        return body.get("hits", {}).get("hits", [])

    def item_to_payload_kwargs(self, item: dict[str, Any]) -> dict[str, Any]:
        zid = item.get("id")
        url = f"https://zenodo.org/records/{zid}" if zid else ""
        return {
            "source_url": url,
            "content_type": "application/json",
            "content_bytes": json.dumps(item, sort_keys=True).encode("utf-8"),
            "item_index": zid,
        }
