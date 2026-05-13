"""URL drain ETL.

Pure parse: takes a crawl4ai-fetched markdown payload and produces a
ParsedDoc with rows for harvest.document_metadata (generic) and
harvest.url_drain_documents (dense, per-source).

Source-type is detected from the URL host (preserves the legacy
drain_url_c4a.py mapping). Title is extracted from the first '# ' line;
common site-name suffixes are stripped to keep titles tidy.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


_TITLE_SUFFIXES = [
    " | Medium",
    " - Level Up Coding",
    " | Towards AI",
    " | arXiv",
    " - SSRN",
    " | Zenodo",
]

_SOURCE_TYPE_BY_HOST = [
    ("arxiv.org", "arxiv_paper"),
    ("zenodo.org", "arxiv_paper"),
    ("ssrn.com", "arxiv_paper"),
    ("youtube.com", "youtube_transcript"),
    ("youtu.be", "youtube_transcript"),
    ("github.com", "github_repo"),
]


def detect_source_type(url: str) -> str:
    """Return one of: arxiv_paper, youtube_transcript, github_repo,
    pdf_document, web_article. Host-based detection matches the legacy
    drain_url_c4a.py mapping."""
    host = (urlparse(url).hostname or "").lower()
    for needle, stype in _SOURCE_TYPE_BY_HOST:
        if needle in host:
            return stype
    if url.lower().endswith(".pdf"):
        return "pdf_document"
    return "web_article"


def _extract_title(markdown: str) -> str:
    """First '# Heading' line in the markdown, with common site suffixes
    stripped. Falls back to 'Untitled'."""
    for line in markdown.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            for suffix in _TITLE_SUFFIXES:
                title = title.replace(suffix, "")
            return title.strip() or "Untitled"
    return "Untitled"


class UrlDrainETL(ETL):
    source_id = "url_drain"
    expected_schema_version = 9

    def parse(self, raw: RawPayload) -> ParsedDoc:
        markdown = raw.file_path.read_text()
        title = _extract_title(markdown)
        source_type = detect_source_type(raw.source_url)
        host = (urlparse(raw.source_url).hostname or "")
        byte_size = len(markdown)

        dense_row = Row(
            target_table="harvest.url_drain_documents",
            data={
                "source_url": raw.source_url,
                "title": title,
                "source_type": source_type,
                "host": host,
                "byte_size": byte_size,
                "fetched_at": raw.fetched_at,
                "raw_hash": raw.raw_hash,
            },
        )

        meta_row = Row(
            target_table="harvest.document_metadata",
            data={
                "source_id": self.source_id,
                "title": title,
                "authors": json.dumps([]),
                "doi": None,
                "source_url": raw.source_url,
                "published_date": None,
                "document_type": source_type,
                "payload": json.dumps(
                    {
                        "source_type": source_type,
                        "host": host,
                        "byte_size": byte_size,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=raw.source_url,
            published_date=None,
            rows=[meta_row, dense_row],
            metadata={
                "source_type": source_type,
                "host": host,
                "byte_size": byte_size,
            },
        )
