"""Tests for robots.txt parser."""

from pathlib import Path

from harvester.discovery.robots import parse_robots_txt

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_parse_simple_robots():
    text = (FIXTURE_DIR / "robots_simple.txt").read_text()
    result = parse_robots_txt(text)
    assert "*" in result["groups"]
    star_group = result["groups"]["*"]
    assert star_group["allow"] == ["/"]
    assert star_group["disallow"] == []
    assert result["sitemaps"] == []


def test_parse_robots_with_sitemap():
    text = (FIXTURE_DIR / "robots_with_sitemap.txt").read_text()
    result = parse_robots_txt(text)
    assert "*" in result["groups"]
    assert result["groups"]["*"]["disallow"] == ["/private/"]
    assert "https://example.com/sitemap.xml" in result["sitemaps"]
    assert "https://example.com/sitemap-news.xml" in result["sitemaps"]


def test_parse_robots_with_multiple_groups_and_crawl_delay():
    text = (FIXTURE_DIR / "robots_with_disallow.txt").read_text()
    result = parse_robots_txt(text)
    assert "GPTBot" in result["groups"]
    assert "CCBot" in result["groups"]
    assert "*" in result["groups"]
    assert result["groups"]["GPTBot"]["disallow"] == ["/"]
    assert "/admin/" in result["groups"]["*"]["disallow"]
    assert result["groups"]["*"]["crawl_delay"] == 10


def test_parse_empty_robots():
    result = parse_robots_txt("")
    assert result["groups"] == {}
    assert result["sitemaps"] == []
