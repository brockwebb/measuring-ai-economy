"""Tests for llms.txt parser."""

from pathlib import Path

from harvester.discovery.llms_txt import parse_llms_txt

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_parse_valid_llms_txt():
    text = (FIXTURE_DIR / "llms_txt_valid.txt").read_text()
    result = parse_llms_txt(text)
    assert result["title"] == "Example Corp"
    assert "widgets" in result["summary"]
    assert "Docs" in result["sections"]
    docs = result["sections"]["Docs"]
    assert any(link["url"] == "https://example.com/docs/start" for link in docs)
    assert any(link["url"] == "https://example.com/docs/api" for link in docs)
    assert "Optional" in result["sections"]


def test_parse_malformed_llms_txt_returns_minimal_dict():
    text = (FIXTURE_DIR / "llms_txt_malformed.txt").read_text()
    result = parse_llms_txt(text)
    assert result["title"] is None
    assert result["sections"] == {}


def test_parse_with_optional_section():
    text = (FIXTURE_DIR / "llms_txt_with_sections.txt").read_text()
    result = parse_llms_txt(text)
    assert result["title"] == "OpenAlex"
    assert "API" in result["sections"]
    assert "Bulk" in result["sections"]
    api_links = result["sections"]["API"]
    assert any(link["url"].endswith("openapi.json") for link in api_links)


def test_parse_empty_string():
    result = parse_llms_txt("")
    assert result["title"] is None
    assert result["sections"] == {}
