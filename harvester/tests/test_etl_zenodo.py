"""Tests for harvester.etl.zenodo.ZenodoETL.

Golden-sample comparison: for each input fixture, ZenodoETL.parse() must
produce a ParsedDoc whose rows match the expected fixture field-by-field
(raw_hash mocked to a known value).
"""

import json
from datetime import date as _date, datetime, timezone
from pathlib import Path

import pytest

from harvester.etl.zenodo import ZenodoETL
from harvester.types import RawPayload


_FXT = Path(__file__).parent / "fixtures" / "zenodo"
_VARIANTS = ["article", "preprint", "conference", "dataset"]

_FETCHED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _raw_payload_for(name: str, tmp_path: Path) -> RawPayload:
    src = _FXT / f"record_{name}.input.json"
    dst = tmp_path / src.name
    dst.write_text(src.read_text())
    return RawPayload(
        file_path=dst,
        source_id="zenodo",
        source_url=f"https://zenodo.org/records/{json.loads(src.read_text())['id']}",
        raw_hash="sha256:test",
        request_params={},
        content_type="application/json",
        fetched_at=_FETCHED_AT,
    )


@pytest.mark.parametrize("variant", _VARIANTS)
def test_zenodo_etl_golden_sample(variant, tmp_path):
    etl = ZenodoETL()
    raw = _raw_payload_for(variant, tmp_path)
    parsed = etl.parse(raw)

    expected_path = _FXT / f"record_{variant}.expected.json"
    expected = json.loads(expected_path.read_text())

    # Compare ParsedDoc shape to expected.
    assert parsed.title == expected["title"]
    assert parsed.source_url == expected["source_url"]
    # published_date is a date or None; expected stores as string or null.
    if expected["published_date"] is None:
        assert parsed.published_date is None
    else:
        assert parsed.published_date.isoformat() == expected["published_date"]

    # Compare row count + target_tables.
    assert len(parsed.rows) == len(expected["rows"])
    for actual_row, expected_row in zip(parsed.rows, expected["rows"]):
        assert actual_row.target_table == expected_row["target_table"]
        # Compare data dict key-by-key; JSON-encoded fields compared as parsed.
        for key, exp_val in expected_row["data"].items():
            act_val = actual_row.data.get(key)
            # Normalize date objects to ISO strings for comparison.
            if isinstance(act_val, _date):
                act_val = act_val.isoformat()
            if isinstance(exp_val, str) and exp_val.startswith(("[", "{")):
                # JSON-encoded value
                assert json.loads(act_val) == json.loads(exp_val), (
                    f"{variant}.{actual_row.target_table}.{key}"
                )
            else:
                assert act_val == exp_val, (
                    f"{variant}.{actual_row.target_table}.{key}: "
                    f"got {act_val!r}, expected {exp_val!r}"
                )


def test_zenodo_etl_source_id_and_schema_version():
    etl = ZenodoETL()
    assert etl.source_id == "zenodo"
    assert etl.expected_schema_version == 8


def test_zenodo_etl_handles_missing_publication_date(tmp_path):
    """A record without metadata.publication_date should produce
    published_date=None, not crash."""
    src = _FXT / "record_article.input.json"
    data = json.loads(src.read_text())
    data["metadata"].pop("publication_date", None)
    p = tmp_path / "no_date.json"
    p.write_text(json.dumps(data))

    raw = RawPayload(
        file_path=p, source_id="zenodo",
        source_url="https://zenodo.org/records/x",
        raw_hash="sha256:test", request_params={},
        content_type="application/json",
        fetched_at=_FETCHED_AT,
    )
    parsed = ZenodoETL().parse(raw)
    assert parsed.published_date is None
