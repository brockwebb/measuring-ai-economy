"""Bulk download fetcher skeleton.

For sources offering full-snapshot downloads (Common Crawl, Wikipedia dumps,
PubMed Central FTP, OpenAlex snapshots). Phase 1 defines the interface;
concrete implementation lands in a future spec.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


class BulkDownloadFetcher(Fetcher):
    """Subclasses set snapshot_url() and implement parse_snapshot()."""

    @abstractmethod
    def snapshot_url(self) -> str: ...

    @abstractmethod
    def parse_snapshot(self, path: Path) -> Iterable[dict[str, Any]]: ...

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        raise NotImplementedError(
            "bulk download fetcher implementation deferred to a future spec. "
            "Required interface: snapshot download (resumable), local cache, "
            "parse_snapshot streaming, per-record archive.write() with seen-skip."
        )
