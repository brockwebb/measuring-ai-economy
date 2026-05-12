"""Tests for Crawl4aiFetcher base (with crawl4ai mocked)."""

from unittest.mock import patch, MagicMock, AsyncMock


from harvester.fetchers.crawl4ai_base import Crawl4aiFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


class _FakeCrawl4aiFetcher(Crawl4aiFetcher):
    source_id = "fake_crawl"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=2.0)

    def urls_to_crawl(self, query):
        return ["https://example.com/a", "https://example.com/b"]

    def crawl_config(self):
        # Override default to avoid importing crawl4ai
        return None


def _mock_crawl_result(url: str, markdown: str):
    """Build a MagicMock that quacks like a CrawlResult."""
    result = MagicMock()
    result.url = url
    result.markdown = MagicMock(fit_markdown=markdown, raw_markdown=markdown)
    result.success = True
    result.html = f"<html><body>{markdown}</body></html>"
    return result


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_crawl4ai_fetcher_yields_one_per_url(mock_build_crawler, tmp_path):
    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)
    crawler.arun = AsyncMock(side_effect=lambda url, config=None: _mock_crawl_result(url, f"# Page at {url}"))
    mock_build_crawler.return_value = crawler

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeCrawl4aiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}))

    assert len(payloads) == 2
    assert all(p.content_type == "text/markdown" for p in payloads)
    urls = [p.source_url for p in payloads]
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_crawl4ai_fetcher_respects_seen(mock_build_crawler, tmp_path):
    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)
    crawler.arun = AsyncMock(side_effect=lambda url, config=None: _mock_crawl_result(url, "# x"))
    mock_build_crawler.return_value = crawler

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeCrawl4aiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}, seen={"https://example.com/a"}))

    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/b"
