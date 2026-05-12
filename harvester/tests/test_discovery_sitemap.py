"""Tests for sitemap.xml parser."""

from pathlib import Path

from harvester.discovery.sitemap import parse_sitemap

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_parse_basic_sitemap_returns_urls():
    xml = (FIXTURE_DIR / "sitemap_basic.xml").read_text()
    result = parse_sitemap(xml)
    assert result["kind"] == "urlset"
    urls = [u["loc"] for u in result["entries"]]
    assert "https://example.com/page1" in urls
    assert "https://example.com/page2" in urls


def test_parse_sitemap_index_returns_subsitemaps():
    xml = (FIXTURE_DIR / "sitemap_index.xml").read_text()
    result = parse_sitemap(xml)
    assert result["kind"] == "index"
    sub_urls = [s["loc"] for s in result["entries"]]
    assert "https://example.com/sitemap-2025.xml" in sub_urls
    assert "https://example.com/sitemap-2026.xml" in sub_urls


def test_parse_sitemap_with_priorities():
    xml = (FIXTURE_DIR / "sitemap_with_priorities.xml").read_text()
    result = parse_sitemap(xml)
    assert result["kind"] == "urlset"
    by_loc = {u["loc"]: u for u in result["entries"]}
    assert by_loc["https://example.com/important"]["priority"] == "1.0"
    assert by_loc["https://example.com/important"]["changefreq"] == "daily"


def test_parse_invalid_xml_returns_empty():
    result = parse_sitemap("not xml at all")
    assert result["kind"] == "unknown"
    assert result["entries"] == []
