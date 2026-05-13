"""Tests for harvester.etl.url_drain.UrlDrainETL.

Tests cover:
- source_type detection by URL host
- title extraction from markdown (first H1)
- ParsedDoc shape with both document_metadata and url_drain_documents rows
- empty/short-content edge cases
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harvester.etl.url_drain import UrlDrainETL, detect_source_type
from harvester.types import RawPayload


_FXT = Path(__file__).parent / "fixtures" / "url_drain"

_FETCHED_AT = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


def _raw_payload_for(name: str, url: str, tmp_path: Path) -> RawPayload:
    src = _FXT / f"markdown_{name}.md"
    dst = tmp_path / src.name
    dst.write_text(src.read_text())
    return RawPayload(
        file_path=dst,
        source_id="url_drain",
        source_url=url,
        raw_hash="sha256:test",
        request_params={"url": url},
        content_type="text/markdown",
        fetched_at=_FETCHED_AT,
    )


@pytest.mark.parametrize("url,expected", [
    ("https://arxiv.org/abs/2605.10938", "arxiv_paper"),
    ("https://zenodo.org/records/19130988", "arxiv_paper"),
    ("https://ssrn.com/abstract=12345", "arxiv_paper"),
    ("https://www.youtube.com/watch?v=abc123", "youtube_transcript"),
    ("https://youtu.be/abc123", "youtube_transcript"),
    ("https://github.com/foo/bar", "github_repo"),
    ("https://example.com/foo.pdf", "pdf_document"),
    ("https://medium.com/some-article", "web_article"),
    ("https://example.com/blog/post", "web_article"),
])
def test_detect_source_type(url, expected):
    assert detect_source_type(url) == expected


def test_url_drain_etl_source_id_and_schema_version():
    etl = UrlDrainETL()
    assert etl.source_id == "url_drain"
    assert etl.expected_schema_version == 9


def test_url_drain_etl_parses_arxiv_markdown(tmp_path):
    etl = UrlDrainETL()
    raw = _raw_payload_for("arxiv", "https://arxiv.org/abs/2605.10938", tmp_path)
    parsed = etl.parse(raw)

    assert parsed.title == "ELF: Embedded Language Flows"
    assert parsed.source_url == "https://arxiv.org/abs/2605.10938"
    assert parsed.published_date is None  # url_drain doesn't extract dates

    # Two rows: document_metadata first, then url_drain_documents.
    assert len(parsed.rows) == 2
    meta_row, dense_row = parsed.rows
    assert meta_row.target_table == "harvest.document_metadata"
    assert meta_row.data["source_id"] == "url_drain"
    assert meta_row.data["title"] == "ELF: Embedded Language Flows"
    assert meta_row.data["document_type"] == "arxiv_paper"

    assert dense_row.target_table == "harvest.url_drain_documents"
    assert dense_row.data["source_url"] == "https://arxiv.org/abs/2605.10938"
    assert dense_row.data["title"] == "ELF: Embedded Language Flows"
    assert dense_row.data["source_type"] == "arxiv_paper"
    assert dense_row.data["host"] == "arxiv.org"
    assert dense_row.data["byte_size"] > 0
    assert dense_row.data["raw_hash"] == "sha256:test"
    assert dense_row.data["fetched_at"] == _FETCHED_AT


def test_url_drain_etl_parses_youtube_markdown(tmp_path):
    etl = UrlDrainETL()
    raw = _raw_payload_for(
        "youtube", "https://www.youtube.com/watch?v=abc123", tmp_path
    )
    parsed = etl.parse(raw)
    assert parsed.title.startswith("How to Train a Dog")
    dense_row = parsed.rows[1]
    assert dense_row.data["source_type"] == "youtube_transcript"
    assert dense_row.data["host"] == "www.youtube.com"


def test_url_drain_etl_falls_back_to_untitled_for_empty_markdown(tmp_path):
    """If the markdown has no H1, title falls back to 'Untitled'."""
    p = tmp_path / "no_heading.md"
    p.write_text("Just some body text. No heading.\n")
    raw = RawPayload(
        file_path=p, source_id="url_drain",
        source_url="https://example.com/no-title",
        raw_hash="sha256:test", request_params={"url": "https://example.com/no-title"},
        content_type="text/markdown", fetched_at=_FETCHED_AT,
    )
    parsed = UrlDrainETL().parse(raw)
    assert parsed.title == "Untitled"
    # Even with no title, both rows still emit.
    assert len(parsed.rows) == 2


def test_url_drain_etl_strips_common_site_suffixes(tmp_path):
    """The legacy script stripped suffixes like ' | Medium', ' - SSRN' from
    titles. The ETL preserves that hygiene to keep titles readable."""
    p = tmp_path / "suffix.md"
    p.write_text("# Why SDEs Matter | Medium\n\nBody.\n")
    raw = RawPayload(
        file_path=p, source_id="url_drain",
        source_url="https://medium.com/some-post",
        raw_hash="sha256:test", request_params={"url": "https://medium.com/some-post"},
        content_type="text/markdown", fetched_at=_FETCHED_AT,
    )
    parsed = UrlDrainETL().parse(raw)
    assert parsed.title == "Why SDEs Matter"
