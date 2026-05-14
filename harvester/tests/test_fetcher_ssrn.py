"""Tests for harvester.fetchers.ssrn.SsrnFetcher.

SsrnFetcher overrides iter_payloads for a two-stage Crawl4ai flow:
  Stage 1: crawl the SSRN search page for a keyword
  Stage 2: regex-extract abstract_id URLs from the search markdown
  Stage 3: crawl each paper page

Tests mock crawl4ai entirely via the same _build_crawler hook used by
test_fetcher_url_drain.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from harvester.fetchers.ssrn import SsrnFetcher


_FXT = Path(__file__).parent / "fixtures" / "ssrn"


def test_ssrn_fetcher_source_id():
    f = SsrnFetcher.__new__(SsrnFetcher)
    assert f.source_id == "ssrn"


def test_ssrn_fetcher_search_url_includes_keyword():
    f = SsrnFetcher.__new__(SsrnFetcher)
    url = f._search_url({"keyword": "stochastic differential equations"})
    assert "papers.ssrn.com/sol3/results.cfm" in url
    assert "stochastic%20differential%20equations" in url or "stochastic+differential+equations" in url


def test_ssrn_fetcher_search_url_empty_keyword_returns_empty():
    f = SsrnFetcher.__new__(SsrnFetcher)
    assert f._search_url({}) == ""
    assert f._search_url({"keyword": ""}) == ""


def test_ssrn_fetcher_parse_paper_urls_extracts_abstract_ids():
    f = SsrnFetcher.__new__(SsrnFetcher)
    markdown = (_FXT / "search_page_sde.md").read_text()
    urls = f._parse_paper_urls(markdown, max_results=5)
    assert len(urls) == 3
    assert all("papers.cfm?abstract_id=" in u for u in urls)
    assert "1234567" in urls[0]


def test_ssrn_fetcher_parse_paper_urls_respects_max_results():
    f = SsrnFetcher.__new__(SsrnFetcher)
    markdown = (_FXT / "search_page_sde.md").read_text()
    urls = f._parse_paper_urls(markdown, max_results=2)
    assert len(urls) == 2


def test_ssrn_fetcher_parse_paper_urls_dedupes_repeats():
    """SSRN search pages sometimes link the same paper twice (title + 'read more')."""
    f = SsrnFetcher.__new__(SsrnFetcher)
    md = "[a](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=999)\n[b](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=999)"
    urls = f._parse_paper_urls(md, max_results=10)
    assert len(urls) == 1


def _mock_crawl_result(markdown_text: str) -> MagicMock:
    result = MagicMock()
    result.success = True
    result.markdown.fit_markdown = markdown_text
    result.markdown.raw_markdown = markdown_text
    result.metadata = {}
    result.error_message = None
    return result


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_ssrn_iter_payloads_two_stage_flow(mock_build_crawler, tmp_path):
    """End-to-end mock: search-page crawl → parse → paper crawl. Verifies
    iter_payloads yields one RawPayload per parsed paper URL."""
    from harvester.manifest import RawArchive

    search_md = (_FXT / "search_page_sde.md").read_text()
    paper_md_template = "# Paper Title {n}\n\nAbstract text here."

    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)

    async def fake_arun(url, config=None):
        if "results.cfm" in url:
            return _mock_crawl_result(search_md)
        # paper page
        return _mock_crawl_result(paper_md_template.format(n=url.rsplit("=", 1)[-1]))

    crawler.arun = AsyncMock(side_effect=fake_arun)
    mock_build_crawler.return_value = crawler

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    f = SsrnFetcher(archive=archive)
    f.crawl_config = lambda: None  # type: ignore[assignment]

    payloads = list(f.iter_payloads({"keyword": "stochastic differential equations", "per_page": 5}))
    assert len(payloads) == 3
    for p in payloads:
        assert p.source_id == "ssrn"
        assert p.content_type == "text/markdown"
        assert "papers.cfm?abstract_id=" in p.source_url


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_ssrn_iter_payloads_handles_empty_search_results(mock_build_crawler, tmp_path):
    """Search page with no abstract_id links → fetcher yields no payloads."""
    from harvester.manifest import RawArchive

    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)
    crawler.arun = AsyncMock(return_value=_mock_crawl_result("# No results"))
    mock_build_crawler.return_value = crawler

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    f = SsrnFetcher(archive=archive)
    f.crawl_config = lambda: None  # type: ignore[assignment]

    payloads = list(f.iter_payloads({"keyword": "no-results"}))
    assert payloads == []


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_ssrn_iter_payloads_empty_keyword_yields_nothing(mock_build_crawler, tmp_path):
    """No keyword → no search → no crawler invocation at all."""
    from harvester.manifest import RawArchive

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    f = SsrnFetcher(archive=archive)

    payloads = list(f.iter_payloads({}))
    assert payloads == []
    mock_build_crawler.assert_not_called()
