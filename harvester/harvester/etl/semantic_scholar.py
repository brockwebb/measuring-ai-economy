"""Semantic Scholar ETL.

Parses Semantic Scholar paper records (JSON shape from /paper/search response)
into rows for harvest.document_metadata + harvest.semantic_scholar_papers.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


class SemanticScholarETL(ETL):
    source_id = "semantic_scholar"
    expected_schema_version = 6

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())

        ss_paper_id = record.get("paperId") or ""
        title = (record.get("title") or "").strip()[:5000]
        abstract = (record.get("abstract") or "").strip() or None

        external_ids = record.get("externalIds") or {}
        doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None

        authors = [a.get("name") for a in (record.get("authors") or []) if isinstance(a, dict) and a.get("name")]
        venue = record.get("venue") or None
        year = record.get("year")
        published_date = _date_or_none(record.get("publicationDate"))

        oa = record.get("openAccessPdf") or {}
        oa_url = oa.get("url") if isinstance(oa, dict) else None
        s2_url = record.get("url") or f"https://www.semanticscholar.org/paper/{ss_paper_id}"

        ss_row = Row(
            target_table="harvest.semantic_scholar_papers",
            data={
                "ss_paper_id": ss_paper_id,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "venue": venue,
                "year": year,
                "published_date": published_date,
                "s2_url": s2_url,
                "open_access_pdf_url": oa_url,
                "citation_count": record.get("citationCount"),
                "reference_count": record.get("referenceCount"),
                "influential_count": record.get("influentialCitationCount"),
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
                "source_url": s2_url,
                "published_date": published_date,
                "document_type": "semantic_scholar_paper",
                "payload": json.dumps({
                    "ss_paper_id": ss_paper_id,
                    "venue": venue,
                    "year": year,
                    "citation_count": record.get("citationCount"),
                }),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=s2_url,
            published_date=published_date,
            rows=[meta_row, ss_row],
            metadata={
                "document_type": "semantic_scholar_paper",
                "ss_paper_id": ss_paper_id,
                "doi": doi,
                "abstract": abstract,
                "venue": venue,
            },
        )
