"""Golden-sample tests for the Federal Register ETL."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from harvester.etl.federal_register import (
    FederalRegisterETL,
    _FR_TERMS,
    _match_terms,
)
from harvester.types import RawPayload


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "federal_register"


def _make_payload(input_path: Path) -> RawPayload:
    return RawPayload(
        raw_hash="sha256:test",
        file_path=input_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 11, 22, 0, 0),
        source_id="federal_register",
        source_url=json.loads(input_path.read_text()).get("html_url", ""),
        request_params={},
    )


@pytest.mark.parametrize("name", ["rule", "eo", "notice", "proposed_rule"])
def test_parse_matches_golden_sample(name):
    input_path = FIXTURE_DIR / f"{name}.input.json"
    expected_path = FIXTURE_DIR / f"{name}.expected.json"
    raw = _make_payload(input_path)

    etl = FederalRegisterETL()
    doc = etl.parse(raw)

    assert len(doc.rows) >= 2, "expected at least document_metadata + federal_register_documents rows"

    expected = json.loads(expected_path.read_text())
    actual = {
        "title": doc.title,
        "source_url": doc.source_url,
        "published_date": doc.published_date.isoformat() if doc.published_date else None,
        "rows": [
            {"target_table": r.target_table, "data": _normalize_for_compare(r.data)}
            for r in doc.rows
        ],
        "metadata": doc.metadata,
    }
    assert actual == expected, f"ETL output diverged from golden sample {name}.expected.json"


def _normalize_for_compare(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Precision-tagging unit tests (added 2026-05-18)
#
# The FR API's `conditions[term]` does fulltext search across many fields
# (agencies, document type, action), so it deposits records whose title +
# abstract don't actually contain the search term. The ETL now tags each
# record with `precision_match` + `matched_terms` so downstream retrieval
# can downweight off-term content. These tests pin the matching logic
# (case-insensitive substring across title+abstract, mirrors the validator's
# ILIKE %term% query).
# ---------------------------------------------------------------------------


def test_fr_terms_loaded_from_sources_yaml():
    """The term list must be non-empty and include both tier_1 and tier_2 entries."""
    assert len(_FR_TERMS) >= 10, "expected at least tier_1+tier_2 terms"
    assert "artificial intelligence" in _FR_TERMS
    assert "automated decision" in _FR_TERMS
    # Tier-2 entries should also be loaded:
    assert "Executive Order 14110" in _FR_TERMS


def test_match_terms_case_insensitive_title():
    matched = _match_terms("Use of Artificial Intelligence in Federal Agencies", "", _FR_TERMS)
    assert matched == ["artificial intelligence"]


def test_match_terms_case_insensitive_abstract():
    matched = _match_terms(
        "SEC Rule 17a-4",
        "Addresses Automated Decision processes for market structure",
        _FR_TERMS,
    )
    # "Automated Decision" → matches "automated decision" (case-insensitive).
    assert matched == ["automated decision"]


def test_match_terms_multiple_distinct_terms():
    matched = _match_terms(
        "NIST AI Risk Management Framework Update",
        "Builds on the NIST AI guidance and AI safety practices for foundation model deployment.",
        _FR_TERMS,
    )
    # Should pick up "NIST AI", "AI risk management", "AI safety", "foundation model"
    # at minimum. Don't pin exact ordering — just verify the set membership.
    for expected in ["NIST AI", "AI risk management", "AI safety", "foundation model"]:
        assert expected in matched


def test_match_terms_no_match_returns_empty():
    matched = _match_terms(
        "Foreign-Trade Zone (FTZ) 116 Notification",
        "Production activity notification under 19 CFR part 400.",
        _FR_TERMS,
    )
    assert matched == []


def test_match_terms_handles_none_inputs():
    assert _match_terms(None, None, _FR_TERMS) == []
    assert _match_terms("", "", _FR_TERMS) == []


def test_match_terms_empty_term_list():
    assert _match_terms("Artificial Intelligence Rule", "AI safety stuff", []) == []


def test_parse_stamps_precision_fields_when_off_term(tmp_path):
    """An FR record whose title+abstract don't contain any tier term should
    still be parsed successfully but tagged precision_match=False with an
    empty matched_terms list.
    """
    record = {
        "document_number": "2026-12345",
        "title": "Foreign-Trade Zone 116 Notification",
        "abstract": "Production activity notification under 19 CFR part 400.",
        "type": "Notice",
        "html_url": "https://www.federalregister.gov/documents/2026/05/01/2026-12345/test",
        "publication_date": "2026-05-01",
        "agencies": [{"raw_name": "FOREIGN-TRADE ZONES BOARD", "id": 199}],
    }
    input_path = tmp_path / "off_term.json"
    input_path.write_text(json.dumps(record))
    raw = _make_payload(input_path)

    doc = FederalRegisterETL().parse(raw)

    assert doc.metadata["precision_match"] is False
    assert doc.metadata["matched_terms"] == []
    # And the JSONB payload row should agree:
    meta_row = next(r for r in doc.rows if r.target_table == "harvest.document_metadata")
    payload = json.loads(meta_row.data["payload"])
    assert payload["precision_match"] is False
    assert payload["matched_terms"] == []


def test_parse_stamps_precision_fields_when_on_term(tmp_path):
    """An FR record whose title contains an AI term should be tagged
    precision_match=True with the matched terms in the payload.
    """
    record = {
        "document_number": "2026-99999",
        "title": "Notice on Foundation Model Procurement Standards",
        "abstract": "Guidance on federal acquisition of artificial intelligence systems.",
        "type": "Notice",
        "html_url": "https://www.federalregister.gov/documents/2026/05/01/2026-99999/test",
        "publication_date": "2026-05-01",
        "agencies": [{"raw_name": "GENERAL SERVICES ADMINISTRATION", "id": 219}],
    }
    input_path = tmp_path / "on_term.json"
    input_path.write_text(json.dumps(record))
    raw = _make_payload(input_path)

    doc = FederalRegisterETL().parse(raw)

    assert doc.metadata["precision_match"] is True
    assert "foundation model" in doc.metadata["matched_terms"]
    assert "artificial intelligence" in doc.metadata["matched_terms"]

    meta_row = next(r for r in doc.rows if r.target_table == "harvest.document_metadata")
    payload = json.loads(meta_row.data["payload"])
    assert payload["precision_match"] is True
    assert "foundation model" in payload["matched_terms"]
