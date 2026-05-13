"""URL drain fetcher.

Single-URL on-demand fetcher backed by Crawl4aiFetcher. The query dict
carries one key: `url` — the target page. urls_to_crawl returns it as a
one-element iterable so the Crawl4aiFetcher base does the rest (async
browser, markdown extraction, archive write).

Replaces the legacy ~/.wintermute/scripts/drain_url_c4a.py which did the
same job but staged markdown files directly to ~/.wintermute/staging/
rather than going through the harvester DB pipeline.
"""

from __future__ import annotations

from typing import Any, Iterable

from harvester.fetchers.crawl4ai_base import Crawl4aiFetcher
from harvester.types import RateLimit


class UrlDrainFetcher(Crawl4aiFetcher):
    source_id = "url_drain"

    def rate_limit_spec(self) -> RateLimit:
        # On-demand single-URL fetches are not high-volume. Pace at 1 req/sec
        # to match sibling fetchers and avoid any chance of looking like a bot
        # to the target site.
        return RateLimit(
            requests_per_second=1.0,
            max_retries=2,
            backoff_seconds=[5, 15],
        )

    def urls_to_crawl(self, query: dict[str, Any]) -> Iterable[str]:
        url = query.get("url")
        return [url] if url else []
