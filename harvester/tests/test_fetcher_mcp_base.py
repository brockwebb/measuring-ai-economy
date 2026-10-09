"""Tests for McpFetcher base.

MODEL-001 (seldon AD-035): these tests used to patch `subprocess.run` inside mcp_base. The base now
requires a registry role and execs the lock's CLI through harvester.model_launch, so they run
against `seldon_models_home` (a fixture lock and a fake CLI, tests/conftest.py).
"""

import subprocess

import pytest

from harvester import model_launch
from harvester.fetchers.mcp_base import McpFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


class _FakeMcpFetcher(McpFetcher):
    source_id = "fake_mcp"
    mcp_tool = "mcp__test__search"
    # Any registry role serves here: the fixture registry is a copy of seldon's.
    model_role = "triage"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=1.0)

    def args_for_query(self, query):
        return {"q": query.get("q", "")}

    def items_from_response(self, response):
        return response.get("results", [])


def test_mcp_fetcher_yields_one_per_item(seldon_models_home, tmp_path):
    seldon_models_home.reply("", top={
        "results": [
            {"url": "https://example.com/a", "title": "A"},
            {"url": "https://example.com/b", "title": "B"},
        ]
    })
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "ai"}))

    assert len(payloads) == 2
    assert all(p.content_type == "application/json" for p in payloads)


def test_mcp_fetcher_respects_seen(seldon_models_home, tmp_path):
    seldon_models_home.reply("", top={
        "results": [
            {"url": "https://example.com/a"},
            {"url": "https://example.com/b"},
        ]
    })
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "ai"}, seen={"https://example.com/a"}))

    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/b"


def test_mcp_fetcher_raises_on_nonzero_exit(seldon_models_home, tmp_path, monkeypatch):
    def failing(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="oh no")
    monkeypatch.setattr(model_launch.subprocess, "run", failing)
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    with pytest.raises(RuntimeError, match="MCP call failed"):
        list(fetcher.iter_payloads({"q": "x"}))
