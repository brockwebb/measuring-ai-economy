"""Tests for harvester.etl.pubmed.PubMedETL.

Golden-sample comparison: each input fixture is parsed and compared
field-by-field against the expected fixture (raw_hash mocked).
"""

import json
from datetime import datetime, timezone, date as _date
from pathlib import Path

import pytest

from harvester.etl.pubmed import PubMedETL
from harvester.types import RawPayload


_FXT = Path(__file__).parent / "fixtures" / "pubmed"
_VARIANTS = ["canine_cognition", "bjj_injury", "exercise_phys", "flow_state"]

_FETCHED_AT = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


def _raw_payload_for(name: str, tmp_path: Path) -> RawPayload:
    src = _FXT / f"paper_{name}.input.json"
    dst = tmp_path / src.name
    dst.write_text(src.read_text())
    data = json.loads(src.read_text())
    return RawPayload(
        file_path=dst,
        source_id="pubmed",
        source_url=data["url"],
        raw_hash="sha256:test",
        request_params={"mcp_tool": "mcp__claude_ai_PubMed__search_articles"},
        content_type="application/json",
        fetched_at=_FETCHED_AT,
    )


@pytest.mark.parametrize("variant", _VARIANTS)
def test_pubmed_etl_golden_sample(variant, tmp_path):
    etl = PubMedETL()
    raw = _raw_payload_for(variant, tmp_path)
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
            # Normalize date objects to ISO strings for comparison
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


def test_pubmed_etl_source_id_and_schema_version():
    etl = PubMedETL()
    assert etl.source_id == "pubmed"
    assert etl.expected_schema_version == 10


def test_pubmed_etl_handles_missing_doi_pmcid(tmp_path):
    """A paper without doi or pmcid should still parse — these fields are
    nullable in the schema."""
    src = _FXT / "paper_flow_state.input.json"  # this one has doi=null, pmcid=null
    data = json.loads(src.read_text())
    p = tmp_path / "no_ids.json"
    p.write_text(json.dumps(data))

    raw = RawPayload(
        file_path=p, source_id="pubmed",
        source_url=data["url"],
        raw_hash="sha256:test",
        request_params={},
        content_type="application/json",
        fetched_at=_FETCHED_AT,
    )
    parsed = PubMedETL().parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["doi"] is None
    assert dense_row.data["pmcid"] is None
    assert dense_row.data["pmc_full_text_url"] is None


def test_pubmed_etl_builds_pmc_full_text_url_when_pmcid_present(tmp_path):
    """If pmcid is set, pmc_full_text_url should be derivable."""
    src = _FXT / "paper_canine_cognition.input.json"  # this one has pmcid=PMC10000001
    data = json.loads(src.read_text())
    p = tmp_path / "with_pmcid.json"
    p.write_text(json.dumps(data))

    raw = RawPayload(
        file_path=p, source_id="pubmed",
        source_url=data["url"],
        raw_hash="sha256:test",
        request_params={},
        content_type="application/json",
        fetched_at=_FETCHED_AT,
    )
    parsed = PubMedETL().parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["pmcid"] == "PMC10000001"
    assert dense_row.data["pmc_full_text_url"] == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10000001/"
