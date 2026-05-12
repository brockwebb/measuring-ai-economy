"""Tests for the MuiScout orchestrator."""

from pathlib import Path

from harvester.discovery.scout import MuiScout

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_scout_with_full_mui_present(httpx_mock):
    """Source publishes llms.txt, robots.txt, sitemap, openapi, and JSON-LD."""
    base = "https://example.com"
    httpx_mock.add_response(method="GET", url=f"{base}/llms.txt",
                            text=(FIXTURE_DIR / "llms_txt_valid.txt").read_text())
    httpx_mock.add_response(method="GET", url=f"{base}/robots.txt",
                            text=(FIXTURE_DIR / "robots_with_sitemap.txt").read_text())
    httpx_mock.add_response(method="GET", url=f"{base}/sitemap.xml",
                            text=(FIXTURE_DIR / "sitemap_basic.xml").read_text())
    httpx_mock.add_response(method="GET", url=f"{base}/.well-known/openapi.json",
                            json={"openapi": "3.0.3", "info": {"title": "T", "version": "1"},
                                  "paths": {"/foo": {}}, "servers": [{"url": "https://api.example.com"}]})
    httpx_mock.add_response(method="GET", url=base,
                            text=(FIXTURE_DIR / "html_with_jsonld.html").read_text())

    scout = MuiScout()
    notes = scout.probe(base)

    assert notes.base_url == base
    assert notes.llms_txt is not None
    assert notes.llms_txt["title"] == "Example Corp"
    assert notes.robots_rules is not None
    assert "*" in notes.robots_rules["groups"]
    assert "https://example.com/page1" in notes.sitemap_urls
    assert notes.openapi_spec is not None
    assert notes.openapi_spec["title"] == "T"
    assert "https://example.com/feed.xml" in notes.rss_feeds
    assert "Article" in notes.schema_org_types
    assert "Organization" in notes.schema_org_types
    assert notes.probe_errors == {}


def test_scout_with_all_404(httpx_mock):
    """Source publishes none of the MUI affordances."""
    base = "https://bare.example.com"
    for path in ["/llms.txt", "/robots.txt", "/sitemap.xml", "/.well-known/openapi.json", "/openapi.json"]:
        httpx_mock.add_response(method="GET", url=f"{base}{path}", status_code=404, is_optional=True)
    httpx_mock.add_response(method="GET", url=base, text="<html><body>nothing</body></html>", is_optional=True)

    scout = MuiScout()
    notes = scout.probe(base)

    assert notes.llms_txt is None
    assert notes.robots_rules is None
    assert notes.sitemap_urls == []
    assert notes.openapi_spec is None
    assert notes.rss_feeds == []
    assert notes.schema_org_types == []


def test_scout_with_malformed_llms_txt(httpx_mock):
    base = "https://malformed.example.com"
    httpx_mock.add_response(method="GET", url=f"{base}/llms.txt",
                            text=(FIXTURE_DIR / "llms_txt_malformed.txt").read_text())
    for path in ["/robots.txt", "/sitemap.xml", "/.well-known/openapi.json", "/openapi.json"]:
        httpx_mock.add_response(method="GET", url=f"{base}{path}", status_code=404, is_optional=True)
    httpx_mock.add_response(method="GET", url=base, text="<html></html>", is_optional=True)

    scout = MuiScout()
    notes = scout.probe(base)
    assert notes.llms_txt is not None
    assert notes.llms_txt["title"] is None
