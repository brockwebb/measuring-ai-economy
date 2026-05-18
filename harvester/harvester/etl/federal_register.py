"""Federal Register ETL.

Pure parse: takes the FR API record (one document) and produces the
ParsedDoc with rows for harvest.document_metadata and
harvest.federal_register_documents.

Per-record precision tagging (added 2026-05-18):
The FR API's `conditions[term]` does fulltext search across MANY fields
(title, abstract, agencies, document type, action, etc.) — broader than
just title+abstract. Result: 294 deposited rows, only ~6 match
AI/ML keywords in title/abstract; validate_count.py correctly flagged
99.5% drift. Per the operator's chosen fix #2 of 4 candidates (re-score
at ETL, preserve data, let downstream filter): each record now gets
`precision_match` (bool) + `matched_terms` (list) stamped into the
document_metadata.payload JSONB. Retrieval/triage layer can filter or
downweight; the deposited row stays in place for audit + future re-scoring
under refined rubrics.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value).date() if "T" in value else date.fromisoformat(value)


def _load_fr_terms() -> list[str]:
    """Load FR tier_1 + tier_2 terms from sources.yaml at module load time.

    Single source of truth — same list the fetcher queries against, same
    list the validator uses for ILIKE checks. No hardcoded duplication
    per [[feedback-no-hardcoding-config-first]].
    """
    cfg_path = Path(__file__).parent.parent / "config" / "sources.yaml"
    try:
        cfg = yaml.safe_load(cfg_path.read_text())
        fr = cfg.get("federal_register", {}) or {}
        return list(fr.get("tier_1_terms", [])) + list(fr.get("tier_2_terms", []))
    except Exception:
        return []


# Cached at module load. If sources.yaml changes, the harvester service
# needs to restart to pick it up — same pattern as the rest of the config.
_FR_TERMS: list[str] = _load_fr_terms()


def _match_terms(title: str | None, abstract: str | None, terms: list[str]) -> list[str]:
    """Return the subset of terms that substring-match (case-insensitive)
    against the concatenated title + abstract. Mirrors the validator's
    ILIKE %term% logic so the validator's drift reading and the ETL's
    precision_match agree on the same boundary.
    """
    haystack = ((title or "") + " " + (abstract or "")).lower()
    return [t for t in terms if t.lower() in haystack]


def _extract_agencies(record: dict[str, Any]) -> tuple[list[str], list[int]]:
    agencies = record.get("agencies") or []
    names: list[str] = []
    ids: list[int] = []
    for a in agencies:
        if isinstance(a, dict):
            if "raw_name" in a and a["raw_name"]:
                names.append(a["raw_name"])
            elif "name" in a and a["name"]:
                names.append(a["name"])
            if a.get("id") is not None:
                ids.append(int(a["id"]))
    return names, ids


def _extract_eo_number(record: dict[str, Any]) -> int | None:
    eo = record.get("executive_order_number")
    if eo is None:
        return None
    try:
        return int(eo)
    except (TypeError, ValueError):
        return None


class FederalRegisterETL(ETL):
    source_id = "federal_register"
    expected_schema_version = 2

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())
        agencies, agency_ids = _extract_agencies(record)
        pub_date = _date_or_none(record.get("publication_date"))

        # Precision tagging — does the title/abstract actually contain any of
        # the configured FR terms? Used to mark off-term API hits without
        # dropping them (preserves data per the bamboo principle).
        matched_terms = _match_terms(
            record.get("title"), record.get("abstract"), _FR_TERMS
        )
        precision_match = bool(matched_terms)

        fr_row = Row(
            target_table="harvest.federal_register_documents",
            data={
                "document_number": record["document_number"],
                "title": record.get("title", "")[:5000],
                "abstract": record.get("abstract"),
                "document_type": record.get("type") or "Unknown",
                "presidential_document_type": record.get("presidential_document_type"),
                "executive_order_number": _extract_eo_number(record),
                "publication_date": pub_date,
                "effective_date": _date_or_none(record.get("effective_on")),
                "signing_date": _date_or_none(record.get("signing_date")),
                "agencies": agencies,
                "agency_ids": agency_ids,
                "cfr_references": json.dumps(record.get("cfr_references", [])),
                "citation": record.get("citation"),
                "page_length": record.get("page_length"),
                "html_url": record.get("html_url", ""),
                "pdf_url": record.get("pdf_url"),
                "full_text_xml_url": record.get("full_text_xml_url"),
                "body_html_url": record.get("body_html_url"),
                "body_text": record.get("body"),
                "docket_ids": record.get("docket_ids") or [],
                "regulations_dot_gov_url": record.get("regulations_dot_gov_url"),
                "raw_hash": raw.raw_hash,
            },
        )

        meta_row = Row(
            target_table="harvest.document_metadata",
            data={
                "source_id": self.source_id,
                "title": record.get("title", "")[:5000],
                "authors": json.dumps([]),
                "doi": None,
                "source_url": record.get("html_url", ""),
                "published_date": pub_date,
                "document_type": record.get("type") or "Unknown",
                "payload": json.dumps(
                    {
                        "agencies": agencies,
                        "citation": record.get("citation"),
                        "document_number": record["document_number"],
                        "matched_terms": matched_terms,
                        "precision_match": precision_match,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=record.get("title", "")[:5000],
            source_url=record.get("html_url", ""),
            published_date=pub_date,
            rows=[meta_row, fr_row],
            metadata={
                "document_type": record.get("type") or "Unknown",
                "agencies": agencies,
                "document_number": record["document_number"],
                "matched_terms": matched_terms,
                "precision_match": precision_match,
            },
        )
