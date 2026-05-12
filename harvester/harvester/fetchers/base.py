"""Fetcher abstract base class.

A Fetcher knows how to paginate, authenticate, and write raw bytes for a
specific upstream source. It does NOT normalize, write to postgres, or
manage advisory locks — those are runner responsibilities.

Per the design spec §3.1, there is no discover/fetch split — fetchers
expose a single iter_payloads method and decide internally whether the
upstream is one-step (API returns full docs in search results) or two-
step (HTML index → per-page fetch).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Iterable

from harvester.manifest import RawArchive
from harvester.types import RateLimit, RawPayload


class Fetcher(ABC):
    """Abstract fetcher. Subclasses implement source-specific logic."""

    source_id: str

    def __init__(self, archive: RawArchive) -> None:
        self.archive = archive
        self._last_request_at: float = 0.0

    @abstractmethod
    def rate_limit_spec(self) -> RateLimit:
        """Return the rate limit policy for this fetcher."""

    @abstractmethod
    def iter_payloads(self, query: dict[str, Any]) -> Iterable[RawPayload]:
        """Yield RawPayload objects for items matching the query.

        Implementation contract:
          - Respect rate_limit_spec() via self._pace()
          - Write raw bytes via self.archive.write() — that returns the RawPayload
          - Do NOT check fetched_items; that's the runner's job
          - May raise on unrecoverable errors; the runner records them in run_log
        """

    def _pace(self) -> None:
        """Sleep as needed to honor the rate limit."""
        gap = self.rate_limit_spec().seconds_between_requests
        if gap <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < gap:
            time.sleep(gap - elapsed)
        self._last_request_at = time.monotonic()
