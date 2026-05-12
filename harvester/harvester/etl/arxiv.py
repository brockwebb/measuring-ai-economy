"""arxiv ETL.

Parses the JSON-shaped entry dict (produced by ArxivFetcher._entry_to_bytes)
into rows for:
  - harvest.document_metadata (thin, generic)
  - harvest.arxiv_papers (dense, source-shaped)
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/([^/?#]+)")
_VERSION_SUFFIX_RE = re.compile(r"v\d+$")


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def _extract_arxiv_ids(entry_id: str | None) -> tuple[str, str]:
    if not entry_id:
        return "", ""
    m = _ARXIV_ID_RE.search(entry_id)
    if not m:
        return "", ""
    full = m.group(1)
    short = _VERSION_SUFFIX_RE.sub("", full)
    return full, short


def _abs_url_from_links(links: list[dict[str, Any]]) -> str:
    for link in links:
        if link.get("rel") == "alternate" and link.get("href"):
            return link["href"]
    return ""


def _pdf_url_from_links(links: list[dict[str, Any]]) -> str | None:
    for link in links:
        if link.get("type") == "application/pdf" and link.get("href"):
            return link["href"]
    return None


class ArxivETL(ETL):
    source_id = "arxiv"
    expected_schema_version = 5

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())

        title = (record.get("title") or "").strip()
        title = " ".join(title.split())[:5000]

        abstract = (record.get("summary") or "").strip() or None
        if abstract:
            abstract = " ".join(abstract.split())

        authors = record.get("authors") or []
        categories = record.get("tags") or []
        primary_category = record.get("arxiv_primary_category")
        published_date = _date_or_none(record.get("published"))
        updated_date = _date_or_none(record.get("updated"))
        doi = record.get("arxiv_doi")
        journal_ref = record.get("arxiv_journal_ref")
        links = record.get("links") or []
        arxiv_url = _abs_url_from_links(links)
        pdf_url = _pdf_url_from_links(links)

        arxiv_id_full, arxiv_id_short = _extract_arxiv_ids(record.get("id"))

        arxiv_row = Row(
            target_table="harvest.arxiv_papers",
            data={
                "arxiv_id": arxiv_id_full,
                "arxiv_id_short": arxiv_id_short,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "primary_category": primary_category,
                "categories": categories,
                "published_date": published_date,
                "updated_date": updated_date,
                "doi": doi,
                "journal_ref": journal_ref,
                "arxiv_url": arxiv_url,
                "pdf_url": pdf_url,
                "raw_hash": raw.raw_hash,
            },
        )

        meta_row = Row(
            target_table="harvest.document_metadata",
            data={
                "source_id": self.source_id,
                "title": title,
                "authors": json.dumps(authors),
                "doi": doi,
                "source_url": arxiv_url,
                "published_date": published_date,
                "document_type": "arxiv_paper",
                "payload": json.dumps({
                    "arxiv_id": arxiv_id_short,
                    "primary_category": primary_category,
                    "categories": categories,
                }),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=arxiv_url,
            published_date=published_date,
            rows=[meta_row, arxiv_row],
            metadata={
                "document_type": "arxiv_paper",
                "arxiv_id": arxiv_id_short,
                "primary_category": primary_category,
                "doi": doi,
                "abstract": abstract,
            },
        )
