"""Tests for harvester.fetchers.url_drain.UrlDrainFetcher.

UrlDrainFetcher is a Crawl4aiFetcher subclass: one URL in, one markdown
payload out. Tests mock crawl4ai entirely — they verify the urls_to_crawl
contract and source_id, without invoking a real browser.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from harvester.fetchers.url_drain import UrlDrainFetcher


def test_url_drain_fetcher_source_id():
    f = UrlDrainFetcher.__new__(UrlDrainFetcher)
    assert f.source_id == "url_drain"


def test_url_drain_urls_to_crawl_returns_single_url_from_query():
    f = UrlDrainFetcher.__new__(UrlDrainFetcher)
    urls = list(f.urls_to_crawl({"url": "https://example.com/post"}))
    assert urls == ["https://example.com/post"]


def test_url_drain_urls_to_crawl_empty_when_url_missing():
    f = UrlDrainFetcher.__new__(UrlDrainFetcher)
    urls = list(f.urls_to_crawl({}))
    assert urls == []


def _mock_crawl_result(markdown_text: str, title: str = "Test Title") -> MagicMock:
    """Quack like crawl4ai's CrawlResult."""
    result = MagicMock()
    result.success = True
    result.markdown.fit_markdown = markdown_text
    result.markdown.raw_markdown = markdown_text
    result.metadata = {"title": title}
    result.error_message = None
    return result


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_url_drain_iter_payloads_yields_one_markdown_payload(mock_build_crawler, tmp_path):
    """Full crawl4ai mock — verifies that a single URL flows through
    iter_payloads into exactly one RawPayload with content_type='text/markdown'."""
    from harvester.manifest import RawArchive

    # Mock crawler: arun returns one mock result, no real browser.
    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)
    crawler.arun = AsyncMock(return_value=_mock_crawl_result(
        markdown_text="# Hello\n\nWorld.\n", title="Hello World"
    ))
    mock_build_crawler.return_value = crawler

    archive_root = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.parquet"
    archive = RawArchive(root=archive_root, manifest_path=manifest_path)

    f = UrlDrainFetcher(archive=archive)
    # Override crawl_config so crawl4ai's import isn't needed during the call.
    f.crawl_config = lambda: None  # type: ignore[assignment]

    payloads = list(f.iter_payloads({"url": "https://example.com/post"}))
    assert len(payloads) == 1
    p = payloads[0]
    assert p.source_url == "https://example.com/post"
    assert p.content_type == "text/markdown"
    assert p.source_id == "url_drain"
    # Markdown bytes round-trip
    assert p.file_path.read_text() == "# Hello\n\nWorld.\n"
