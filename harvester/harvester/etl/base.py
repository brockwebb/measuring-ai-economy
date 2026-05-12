"""ETL abstract base class.

An ETL knows how to parse a RawPayload into a ParsedDoc with the postgres
rows to insert. It is a pure function of (raw_bytes) — no side effects
beyond parsing. The Loader writes rows to postgres.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from harvester.types import ParsedDoc, RawPayload, Row


class ETL(ABC):
    source_id: str
    expected_schema_version: int

    @abstractmethod
    def parse(self, raw: RawPayload) -> ParsedDoc:
        """Return a ParsedDoc (title, url, rows) derived from the raw payload."""

    def to_rows(self, parsed: ParsedDoc) -> Iterable[Row]:
        """Default: return the rows already on the ParsedDoc. Override if needed."""
        return parsed.rows
