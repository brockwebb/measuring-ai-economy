"""SSRN ETL.

Parses one SSRN paper-page markdown (crawled by SsrnFetcher) into a
ParsedDoc with rows for harvest.document_metadata and harvest.ssrn_records.

SSRN doesn't expose a structured API for public scrapers; we parse the
crawl4ai-rendered markdown with heuristic regex against the typical
section labels ('**Authors:**', '**Abstract**', '**JEL Classification:**',
'**DOI:**', '**Posted:**'). Real-world SSRN templates vary; missing
fields degrade to None rather than crashing.

The canonical SSRN ID is extracted from the source_url's abstract_id
parameter, not the body — that's the authoritative identifier and is
always present on the URL.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any
from urllib.parse import urlparse, parse_qs

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


_AUTHORS_RE = re.compile(r"\*\*Authors?:\*\*\s*(.+?)(?:\n|$)", re.IGNORECASE)
_POSTED_RE = re.compile(r"\*\*Posted:\*\*\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_DOI_RE = re.compile(r"\*\*DOI:\*\*\s*(10\.\S+)", re.IGNORECASE)
_JEL_RE = re.compile(r"\*\*JEL Classification:\*\*\s*([^\n]*)", re.IGNORECASE)
_INSTITUTION_RE = re.compile(r"\(([^)]+(?:School|University|Institute|College)[^)]*)\)")
_AUTHOR_NAME_RE = re.compile(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)")


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or "Untitled"
    return "Untitled"


def _extract_abstract(markdown: str) -> str | None:
    """Pulls the paragraph after '**Abstract**' (case-insensitive). Returns
    None if no abstract section found."""
    # Matches bold-label lines: "**JEL Classification:**" (colon inside or outside closing **)
    _SECTION_LABEL_RE = re.compile(r"^\*\*[^*]+:?\*\*:?")

    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("**abstract**"):
            body_lines: list[str] = []
            for follow in lines[i + 1:]:
                stripped = follow.strip()
                if _SECTION_LABEL_RE.match(stripped):
                    break
                if stripped:
                    body_lines.append(stripped)
                elif body_lines:
                    body_lines.append("")
            text = " ".join(s for s in body_lines if s).strip()
            return text or None
    return None


def _extract_authors(markdown: str) -> list[dict[str, str]]:
    """Returns a list of {name, affiliation?} dicts."""
    m = _AUTHORS_RE.search(markdown)
    if not m:
        return []
    raw = m.group(1).strip()
    out: list[dict[str, str]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name_match = _AUTHOR_NAME_RE.search(chunk)
        if not name_match:
            continue
        entry: dict[str, str] = {"name": name_match.group(1)}
        inst_match = _INSTITUTION_RE.search(chunk)
        if inst_match:
            entry["affiliation"] = inst_match.group(1).strip()
        out.append(entry)
    return out


def _extract_date(markdown: str) -> date | None:
    m = _POSTED_RE.search(markdown)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _extract_doi(markdown: str) -> str | None:
    m = _DOI_RE.search(markdown)
    return m.group(1).strip() if m else None


def _extract_jel_codes(markdown: str) -> list[str]:
    m = _JEL_RE.search(markdown)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    codes = re.findall(r"[A-Z]\d{1,3}", raw)
    return codes


def _extract_institution(markdown: str) -> str | None:
    """First institution found in the Authors line, used as the primary
    affiliation for the dense row's institution column."""
    m = _AUTHORS_RE.search(markdown)
    if not m:
        return None
    inst_match = _INSTITUTION_RE.search(m.group(1))
    return inst_match.group(1).strip() if inst_match else None


def _abstract_id_from_url(url: str) -> int:
    """Extract abstract_id from a canonical SSRN paper URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    try:
        return int(params.get("abstract_id", ["0"])[0])
    except (ValueError, TypeError):
        return 0


class SsrnETL(ETL):
    source_id = "ssrn"
    expected_schema_version = 11

    def parse(self, raw: RawPayload) -> ParsedDoc:
        markdown = raw.file_path.read_text()
        title = _extract_title(markdown)
        abstract = _extract_abstract(markdown)
        authors = _extract_authors(markdown)
        pub_date = _extract_date(markdown)
        doi = _extract_doi(markdown)
        jel_codes = _extract_jel_codes(markdown)
        institution = _extract_institution(markdown)
        ssrn_id = _abstract_id_from_url(raw.source_url)
        byte_size = len(markdown)

        dense_row = Row(
            target_table="harvest.ssrn_records",
            data={
                "ssrn_id": ssrn_id,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "doi": doi,
                "publication_date": pub_date,
                "jel_codes": jel_codes,
                "institution": institution,
                "ssrn_url": raw.source_url,
                "byte_size": byte_size,
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
                "source_url": raw.source_url,
                "published_date": pub_date,
                "document_type": "ssrn_paper",
                "payload": json.dumps(
                    {
                        "ssrn_id": ssrn_id,
                        "jel_codes": jel_codes,
                        "institution": institution,
                        "byte_size": byte_size,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=raw.source_url,
            published_date=pub_date,
            rows=[meta_row, dense_row],
            metadata={
                "ssrn_id": ssrn_id,
                "doi": doi,
                "jel_codes": jel_codes,
                "institution": institution,
            },
        )
