"""Tests for McpFetcher base (with subprocess mocked)."""

import json
from unittest.mock import patch, MagicMock

import pytest

from harvester.fetchers.mcp_base import McpFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


class _FakeMcpFetcher(McpFetcher):
    source_id = "fake_mcp"
    mcp_tool = "mcp__test__search"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=1.0)

    def args_for_query(self, query):
        return {"q": query.get("q", "")}

    def items_from_response(self, response):
        return response.get("results", [])


@patch("harvester.fetchers.mcp_base.subprocess.run")
def test_mcp_fetcher_yields_one_per_item(mock_run, tmp_path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "results": [
                {"url": "https://example.com/a", "title": "A"},
                {"url": "https://example.com/b", "title": "B"},
            ]
        }),
        stderr="",
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "ai"}))

    assert len(payloads) == 2
    assert all(p.content_type == "application/json" for p in payloads)


@patch("harvester.fetchers.mcp_base.subprocess.run")
def test_mcp_fetcher_respects_seen(mock_run, tmp_path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "results": [
                {"url": "https://example.com/a"},
                {"url": "https://example.com/b"},
            ]
        }),
        stderr="",
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "ai"}, seen={"https://example.com/a"}))

    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/b"


@patch("harvester.fetchers.mcp_base.subprocess.run")
def test_mcp_fetcher_raises_on_nonzero_exit(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="oh no")
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    with pytest.raises(RuntimeError, match="MCP call failed"):
        list(fetcher.iter_payloads({"q": "x"}))
