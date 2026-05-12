"""Tests for discovery dataclasses."""

from datetime import datetime, timezone

from harvester.discovery.types import DiscoveryNotes


def test_discovery_notes_constructor():
    notes = DiscoveryNotes(
        base_url="https://example.com",
        probed_at=datetime(2026, 5, 11, 22, 0, 0, tzinfo=timezone.utc),
        llms_txt={"intro": "Hello"},
        robots_rules={"User-agent": "*", "Disallow": "/private"},
        sitemap_urls=["https://example.com/sitemap.xml"],
        openapi_spec=None,
        rss_feeds=["https://example.com/feed.xml"],
        schema_org_types=["Article"],
        probe_errors={},
    )
    assert notes.base_url == "https://example.com"
    assert notes.llms_txt == {"intro": "Hello"}
    assert "Article" in notes.schema_org_types
    assert notes.openapi_spec is None
    assert notes.probe_errors == {}


def test_discovery_notes_is_frozen():
    notes = DiscoveryNotes(
        base_url="https://example.com",
        probed_at=datetime.now(timezone.utc),
        llms_txt=None,
        robots_rules=None,
        sitemap_urls=[],
        openapi_spec=None,
        rss_feeds=[],
        schema_org_types=[],
        probe_errors={},
    )
    try:
        notes.base_url = "https://other.com"  # type: ignore
    except Exception as e:
        assert "frozen" in str(e).lower() or "can't set attribute" in str(e).lower() or "cannot assign" in str(e).lower()
    else:
        raise AssertionError("DiscoveryNotes should be frozen")
