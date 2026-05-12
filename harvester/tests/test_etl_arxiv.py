"""Golden-sample tests for the arxiv ETL."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from harvester.etl.arxiv import ArxivETL
from harvester.types import RawPayload

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "arxiv"


def _make_payload(input_path: Path) -> RawPayload:
    return RawPayload(
        raw_hash="sha256:test",
        file_path=input_path,
        content_type="application/xml",
        fetched_at=datetime(2026, 5, 12, 7, 0, 0),
        source_id="arxiv",
        source_url=json.loads(input_path.read_text()).get("id", ""),
        request_params={},
    )


@pytest.mark.parametrize("name", ["ml", "econ", "stat", "cs"])
def test_parse_matches_golden_sample(name):
    input_path = FIXTURE_DIR / f"paper_{name}.input.json"
    expected_path = FIXTURE_DIR / f"paper_{name}.expected.json"
    raw = _make_payload(input_path)

    etl = ArxivETL()
    doc = etl.parse(raw)

    assert len(doc.rows) >= 2, "expected document_metadata + arxiv_papers rows"

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
    assert actual == expected, f"ETL output diverged from {name}.expected.json"


def _normalize_for_compare(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
