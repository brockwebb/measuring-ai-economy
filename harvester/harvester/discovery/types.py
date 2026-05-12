"""Discovery dataclasses for MUI scout results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DiscoveryNotes:
    """Result of probing a source's machine-readable affordances.

    Persisted as JSON into harvest.data_sources.discovery_notes.
    Empty collections/None mean "probed but not found"; probe_errors
    captures fetch failures per endpoint.
    """

    base_url: str
    probed_at: datetime
    llms_txt: dict[str, Any] | None
    robots_rules: dict[str, Any] | None
    sitemap_urls: list[str]
    openapi_spec: dict[str, Any] | None
    rss_feeds: list[str]
    schema_org_types: list[str]
    probe_errors: dict[str, str] = field(default_factory=dict)
