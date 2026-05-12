"""Core data model dataclasses used across fetcher / ETL / normalizer boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RawPayload:
    """Immutable record of a fetched raw artifact written to disk."""

    raw_hash: str
    file_path: Path
    content_type: str
    fetched_at: datetime
    source_id: str
    source_url: str
    request_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Row:
    """A row destined for a postgres table; the Loader routes by target_table."""

    target_table: str
    data: dict[str, Any]


@dataclass(frozen=True)
class ParsedDoc:
    """Result of an ETL parse step — title + url + the rows to write."""

    title: str
    source_url: str
    published_date: date | None
    rows: list[Row]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RateLimit:
    """Rate limit + retry policy for a fetcher."""

    requests_per_second: float
    max_retries: int = 3
    backoff_seconds: list[int] = field(default_factory=lambda: [2, 5, 15, 60])

    @property
    def seconds_between_requests(self) -> float:
        return 1.0 / self.requests_per_second if self.requests_per_second > 0 else 0.0
