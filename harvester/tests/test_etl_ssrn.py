"""Tests for harvester.etl.ssrn.SsrnETL.

The ETL parses crawled paper-page markdown (heuristic regex against
labeled sections like '**Authors:**', '**Abstract**', '**JEL Classification:**').
Real SSRN output may differ slightly across paper templates; the smoke
step verifies live extraction quality.
"""

import json
from datetime import datetime, timezone, date as _date
from pathlib import Path

import pytest

from harvester.etl.ssrn import SsrnETL
from harvester.types import RawPayload


_FXT = Path(__file__).parent / "fixtures" / "ssrn"
_VARIANTS = ["sde_finance", "info_geometry", "wasserstein"]

_FETCHED_AT = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


def _raw_payload_for(name: str, abstract_id: str, tmp_path: Path) -> RawPayload:
    src = _FXT / f"paper_{name}.md"
    dst = tmp_path / src.name
    dst.write_text(src.read_text())
    return RawPayload(
        file_path=dst,
        source_id="ssrn",
        source_url=f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={abstract_id}",
        raw_hash="sha256:test",
        request_params={"keyword": "test"},
        content_type="text/markdown",
        fetched_at=_FETCHED_AT,
    )


@pytest.mark.parametrize("variant,abstract_id", [
    ("sde_finance", "1234567"),
    ("info_geometry", "2345678"),
    ("wasserstein", "3456789"),
])
def test_ssrn_etl_golden_sample(variant, abstract_id, tmp_path):
    etl = SsrnETL()
    raw = _raw_payload_for(variant, abstract_id, tmp_path)
    parsed = etl.parse(raw)

    expected_path = _FXT / f"paper_{variant}.expected.json"
    expected = json.loads(expected_path.read_text())

    assert parsed.title == expected["title"]
    assert parsed.source_url == expected["source_url"]
    if expected["published_date"] is None:
        assert parsed.published_date is None
    else:
        assert parsed.published_date.isoformat() == expected["published_date"]

    assert len(parsed.rows) == len(expected["rows"])
    for actual_row, expected_row in zip(parsed.rows, expected["rows"]):
        assert actual_row.target_table == expected_row["target_table"]
        for key, exp_val in expected_row["data"].items():
            act_val = actual_row.data.get(key)
            if isinstance(act_val, _date):
                act_val = act_val.isoformat()
            if isinstance(exp_val, str) and exp_val.startswith(("[", "{")):
                assert json.loads(act_val) == json.loads(exp_val), (
                    f"{variant}.{actual_row.target_table}.{key}"
                )
            else:
                assert act_val == exp_val, (
                    f"{variant}.{actual_row.target_table}.{key}: "
                    f"got {act_val!r}, expected {exp_val!r}"
                )


def test_ssrn_etl_source_id_and_schema_version():
    etl = SsrnETL()
    assert etl.source_id == "ssrn"
    assert etl.expected_schema_version == 11


def test_ssrn_etl_extracts_abstract_id_from_url(tmp_path):
    """SSRN ID is sourced from the URL, not the body — the canonical
    identifier always matches the source_url's abstract_id param."""
    etl = SsrnETL()
    raw = _raw_payload_for("sde_finance", "9999999", tmp_path)
    parsed = etl.parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["ssrn_id"] == 9999999


def test_ssrn_etl_handles_missing_jel_codes(tmp_path):
    """The wasserstein fixture intentionally has an empty JEL Classification
    line — should parse as an empty list, not crash."""
    etl = SsrnETL()
    raw = _raw_payload_for("wasserstein", "3456789", tmp_path)
    parsed = etl.parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["jel_codes"] == []


def test_ssrn_etl_handles_missing_doi(tmp_path):
    """Wasserstein paper has no DOI line — doi should be None."""
    etl = SsrnETL()
    raw = _raw_payload_for("wasserstein", "3456789", tmp_path)
    parsed = etl.parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["doi"] is None


def test_ssrn_etl_falls_back_to_untitled_for_no_h1(tmp_path):
    p = tmp_path / "no_h1.md"
    p.write_text("Just body text, no heading.\n\n**Authors:** Someone\n")
    raw = RawPayload(
        file_path=p, source_id="ssrn",
        source_url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=99",
        raw_hash="sha256:test",
        request_params={},
        content_type="text/markdown",
        fetched_at=_FETCHED_AT,
    )
    parsed = SsrnETL().parse(raw)
    assert parsed.title == "Untitled"
