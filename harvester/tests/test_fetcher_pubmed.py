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
    assert args["max_results"] == PubMedFetcher._MAX_RESULTS_CAP


def test_pubmed_fetcher_args_for_query_caps_max_results_at_cap():
    """The CLI defaults per_page to 100. PubMed caps aggressively to keep
    cost-per-night bounded (two MCP calls per term: search + get_metadata)."""
    f = PubMedFetcher.__new__(PubMedFetcher)
    args = f.args_for_query({"keyword": "test", "per_page": 100})
    assert args["max_results"] == PubMedFetcher._MAX_RESULTS_CAP


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


def test_pubmed_fetcher_items_from_response_handles_markdown_fenced_result():
    """claude CLI may wrap the JSON in a markdown code fence inside the result string.
    Observed in production: result='```json\\n{...}\\n```'."""
    f = PubMedFetcher.__new__(PubMedFetcher)
    inner_obj = {"results": [{"pmid": "2", "title": "y", "url": "https://pubmed.ncbi.nlm.nih.gov/2/"}]}
    fenced = f"```json\n{json.dumps(inner_obj)}\n```"
    wrapped = {"type": "result", "result": fenced}
    items = list(f.items_from_response(wrapped))
    assert len(items) == 1
    assert items[0]["pmid"] == "2"


def test_pubmed_fetcher_items_from_response_handles_dict_result_field():
    """Some Claude CLI versions return result as a dict directly, not a string."""
    f = PubMedFetcher.__new__(PubMedFetcher)
    wrapped = {"type": "result", "result": {"results": [{"pmid": "3", "title": "z", "url": "https://pubmed.ncbi.nlm.nih.gov/3/"}]}}
    items = list(f.items_from_response(wrapped))
    assert len(items) == 1
    assert items[0]["pmid"] == "3"


def test_pubmed_fetcher_allowed_tools_includes_both_mcp_tools():
    """Fetcher must pre-approve both search and get_metadata to avoid permission denial."""
    f = PubMedFetcher.__new__(PubMedFetcher)
    assert "mcp__claude_ai_PubMed__search_articles" in f.allowed_tools
    assert "mcp__claude_ai_PubMed__get_article_metadata" in f.allowed_tools


def test_pubmed_fetcher_normalize_item_flattens_nested_identifiers():
    """get_article_metadata returns pmid nested under identifiers; normalize flattens it."""
    raw = {
        "identifiers": {"pmid": "42126808", "doi": "10.1007/test", "pii": "10.1007/test"},
        "title": "Test title",
        "abstract": "Test abstract",
        "authors": ["Jane Smith", "John Doe"],
        "journal": "GeroScience",
        "publication_date": "2026-05-13",
        "keywords": ["Canine cognitive dysfunction", "Dog dementia"],
        "article_types": ["Journal Article"],
    }
    result = PubMedFetcher._normalize_item(raw)
    assert result["pmid"] == "42126808"
    assert result["doi"] == "10.1007/test"
    assert result["authors"] == [{"name": "Jane Smith"}, {"name": "John Doe"}]
    assert result["mesh_terms"] == ["Canine cognitive dysfunction", "Dog dementia"]
    assert result["url"] == "https://pubmed.ncbi.nlm.nih.gov/42126808/"


def test_pubmed_fetcher_normalize_item_handles_structured_author_dicts():
    """get_article_metadata may return authors as {last_name, fore_name, ...} dicts."""
    raw = {
        "pmid": "42126808",
        "title": "Test",
        "authors": [
            {"last_name": "Taylor", "fore_name": "Tracey L", "initials": "TL",
             "affiliations": ["University of Adelaide"]},
            {"last_name": "Hazel", "fore_name": "Susan J", "initials": "SJ",
             "affiliations": ["University of Adelaide"]},
        ],
        "publication_date": {"year": "2026", "month": "05", "day": "13"},
        "keywords": ["dogs"],
    }
    result = PubMedFetcher._normalize_item(raw)
    assert result["authors"] == [{"name": "Tracey L Taylor"}, {"name": "Susan J Hazel"}]
    assert result["publication_date"] == "2026-05-13"


def test_pubmed_fetcher_normalize_item_handles_date_as_dict():
    """get_article_metadata may return publication_date as {year, month, day} dict."""
    raw = {
        "pmid": "99",
        "title": "X",
        "authors": [],
        "publication_date": {"year": "2025", "month": "3", "day": "7"},
        "keywords": [],
    }
    result = PubMedFetcher._normalize_item(raw)
    assert result["publication_date"] == "2025-03-07"


def test_pubmed_fetcher_normalize_item_handles_journal_as_dict():
    """get_article_metadata may return journal as {title, iso_abbreviation} dict."""
    raw = {
        "pmid": "42126808",
        "title": "Test",
        "authors": [],
        "journal": {"title": "GeroScience", "iso_abbreviation": "Geroscience"},
        "publication_date": "2026-05-13",
        "keywords": [],
    }
    result = PubMedFetcher._normalize_item(raw)
    assert result["journal"] == "GeroScience"


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
