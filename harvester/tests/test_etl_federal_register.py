"""Golden-sample tests for the Federal Register ETL."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from harvester.etl.federal_register import FederalRegisterETL
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
