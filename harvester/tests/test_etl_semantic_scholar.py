"""Golden-sample tests for the Semantic Scholar ETL."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from harvester.etl.semantic_scholar import SemanticScholarETL
from harvester.types import RawPayload

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semantic_scholar"


def _make_payload(input_path: Path) -> RawPayload:
    return RawPayload(
        raw_hash="sha256:test",
        file_path=input_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 7, 0, 0),
        source_id="semantic_scholar",
        source_url=json.loads(input_path.read_text()).get("url", ""),
        request_params={},
    )


@pytest.mark.parametrize("idx", [1, 2, 3, 4])
def test_parse_matches_golden_sample(idx):
    input_path = FIXTURE_DIR / f"paper_{idx}.input.json"
    expected_path = FIXTURE_DIR / f"paper_{idx}.expected.json"
    raw = _make_payload(input_path)

    etl = SemanticScholarETL()
    doc = etl.parse(raw)
    assert len(doc.rows) >= 2

    expected = json.loads(expected_path.read_text())
    actual = {
        "title": doc.title,
        "source_url": doc.source_url,
        "published_date": doc.published_date.isoformat() if doc.published_date else None,
        "rows": [
            {"target_table": r.target_table, "data": _normalize(r.data)}
            for r in doc.rows
        ],
        "metadata": doc.metadata,
    }
    assert actual == expected, f"ETL output diverged from paper_{idx}.expected.json"


def _normalize(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
