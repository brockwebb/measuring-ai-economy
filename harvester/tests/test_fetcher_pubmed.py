"""Tests for harvester.fetchers.pubmed.PubMedFetcher.

PubMedFetcher is an McpFetcher subclass: query in, JSON tool-response out
via `claude -p` subprocess. Tests mock subprocess.run entirely so no real
Claude calls happen at test time.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harvester.fetchers.pubmed import PubMedFetcher


_FIXTURE = Path(__file__).parent / "fixtures" / "pubmed" / "search_response_canine.json"


def test_pubmed_fetcher_source_id_is_pubmed():
    f = PubMedFetcher.__new__(PubMedFetcher)
    assert f.source_id == "pubmed"


def test_pubmed_fetcher_mcp_tool_is_search_articles():
    f = PubMedFetcher.__new__(PubMedFetcher)
    assert f.mcp_tool == "mcp__claude_ai_PubMed__search_articles"


def test_pubmed_fetcher_args_for_query_maps_keyword_to_query():
    f = PubMedFetcher.__new__(PubMedFetcher)
    args = f.args_for_query({"keyword": "canine cognition", "per_page": 5})
    assert args["query"] == "canine cognition"
    assert args["max_results"] == 5


def test_pubmed_fetcher_args_for_query_defaults_max_results():
    f = PubMedFetcher.__new__(PubMedFetcher)
    args = f.args_for_query({"keyword": "BJJ injury"})
    assert args["query"] == "BJJ injury"
    assert args["max_results"] == 10


def test_pubmed_fetcher_items_from_response_extracts_results_list():
    f = PubMedFetcher.__new__(PubMedFetcher)
    response = json.loads(_FIXTURE.read_text())
    items = list(f.items_from_response(response))
    assert len(items) == 2
    assert items[0]["pmid"] == "37001234"
    assert items[0]["url"].startswith("https://pubmed.ncbi.nlm.nih.gov/")


def test_pubmed_fetcher_items_from_response_handles_empty():
    f = PubMedFetcher.__new__(PubMedFetcher)
    items = list(f.items_from_response({"results": []}))
    assert items == []


def test_pubmed_fetcher_items_from_response_unwraps_claude_result_field(tmp_path):
    """If subprocess returns claude's --output-format json shape (with a 'result'
    field that itself contains the tool JSON as a string), unwrap before iterating."""
    f = PubMedFetcher.__new__(PubMedFetcher)
    # Claude's CLI may return: {"type": "result", "result": "<tool's json as string>", ...}
    inner = json.dumps({"results": [{"pmid": "1", "title": "x", "url": "https://pubmed.ncbi.nlm.nih.gov/1/"}]})
    wrapped = {"type": "result", "result": inner, "session_id": "abc"}
    items = list(f.items_from_response(wrapped))
    assert len(items) == 1
    assert items[0]["pmid"] == "1"


@patch("harvester.fetchers.mcp_base.subprocess.run")
def test_pubmed_iter_payloads_yields_one_payload_per_result(mock_run, tmp_path):
    """End-to-end mock: subprocess returns search response, fetcher yields
    one RawPayload per result, content_type='application/json'."""
    from harvester.manifest import RawArchive

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=_FIXTURE.read_text(),
        stderr="",
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    f = PubMedFetcher(archive=archive)
    payloads = list(f.iter_payloads({"keyword": "canine cognition"}))

    assert len(payloads) == 2
    for p in payloads:
        assert p.content_type == "application/json"
        assert p.source_id == "pubmed"
        assert p.source_url.startswith("https://pubmed.ncbi.nlm.nih.gov/")
