"""Tests for the runner's triage hook.

MODEL-001 (seldon AD-035): the fake result and the config used to pin `claude-sonnet-4-6`. The
runner now takes a registry role (`triage_role`) and a TriageResult carries the served-model
receipt, so the fixtures name the fixture lock's id (tests/conftest.py) and the receipt column.
"""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.triage.llm_triage import TriageResult
from harvester.types import ParsedDoc, RawPayload, Row
from tests.conftest import FIXTURE_IDS

AXES_PATH = Path(__file__).parent.parent / "harvester" / "triage" / "research_axes.yaml"
RECEIPT = {"requested": FIXTURE_IDS["sonnet"], "served": FIXTURE_IDS["sonnet"],
           "side_models": [FIXTURE_IDS["haiku"]], "ok": True}


@pytest.fixture
def clean_triage_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.triage_results WHERE doc_id IN (SELECT doc_id FROM harvest.document_metadata WHERE source_id = 'triage_test')")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'triage_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'triage_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'triage_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.triage_results WHERE doc_id IN (SELECT doc_id FROM harvest.document_metadata WHERE source_id = 'triage_test')")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'triage_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'triage_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'triage_test'")
        conn.commit()
    finally:
        conn.close()


def _fake_triage_result():
    return TriageResult(
        score=0.65,
        axes={"stochastic_dynamics_info_geometry": 0.65},
        reason="Diffusion model paper.",
        rubric_version="0.3.0",
        model_id=FIXTURE_IDS["sonnet"],
        prompt_hash="a" * 64,
        model_receipt=RECEIPT,
    )


@patch("harvester.runner.LlmTriage")
def test_runner_writes_triage_when_enabled(mock_triage_cls, clean_triage_state, tmp_path):
    mock_triage = MagicMock()
    mock_triage.score.return_value = _fake_triage_result()
    mock_triage_cls.return_value = mock_triage

    config = RunnerConfig(
        source_id="triage_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        output_circuit_breaker_max=500,
        expected_schema_version=5,
        triage_enabled=True,
        triage_role="triage",
        triage_axes_yaml=AXES_PATH,
    )

    fake_file = tmp_path / "fake.json"
    fake_file.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:abc",
        file_path=fake_file,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 7, 0, 0),
        source_id="triage_test",
        source_url="https://example.com/p1",
        request_params={},
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "triage_test"
        expected_schema_version = 5
        def parse(self, raw):
            return ParsedDoc(
                title="Test",
                source_url=raw.source_url,
                published_date=date(2026, 5, 12),
                rows=[Row(target_table="harvest.document_metadata", data={
                    "source_id": "triage_test",
                    "title": "Test",
                    "source_url": raw.source_url,
                })],
                metadata={"abstract": "An abstract."},
            )
        def to_rows(self, parsed):
            return parsed.rows

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    mock_triage.score.assert_called_once()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.score, t.rubric_version, t.model_id, t.model_receipt
                FROM harvest.triage_results t
                JOIN harvest.document_metadata d ON d.doc_id = t.doc_id
                WHERE d.source_id = 'triage_test'
                """
            )
            row = cur.fetchone()
            assert row is not None
            score, rubric, model, receipt = row
            assert score == pytest.approx(0.65)
            assert rubric == "0.3.0"
            assert model == FIXTURE_IDS["sonnet"]
            assert receipt == RECEIPT
    finally:
        conn.close()


def test_runner_skips_triage_when_disabled(clean_triage_state, tmp_path):
    config = RunnerConfig(
        source_id="triage_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        output_circuit_breaker_max=500,
        expected_schema_version=5,
        triage_enabled=False,
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None): return iter([])
    class FakeETL:
        source_id = "triage_test"
        expected_schema_version = 5

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})
    assert runner.triage is None


def test_runner_drops_triage_from_a_substituted_model(clean_triage_state, seldon_models_home,
                                                      tmp_path):
    """AD-035 R6: a served model that is not the requested one stops the triage unit. No score
    is recorded; the deposit carries the refusal and its receipt."""
    seldon_models_home.serve("claude-sonnet-1-0")
    config = RunnerConfig(
        source_id="triage_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        output_circuit_breaker_max=500,
        expected_schema_version=5,
        triage_enabled=True,
        triage_role="triage",
        triage_axes_yaml=AXES_PATH,
    )
    fake_file = tmp_path / "fake.json"
    fake_file.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:def",
        file_path=fake_file,
        content_type="application/json",
        fetched_at=datetime(2026, 10, 9, 7, 0, 0),
        source_id="triage_test",
        source_url="https://example.com/substituted",
        request_params={},
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "triage_test"
        expected_schema_version = 5
        def parse(self, raw):
            return ParsedDoc(
                title="Test",
                source_url=raw.source_url,
                published_date=date(2026, 10, 9),
                rows=[Row(target_table="harvest.document_metadata", data={
                    "source_id": "triage_test",
                    "title": "Test",
                    "source_url": raw.source_url,
                })],
                metadata={"abstract": "An abstract."},
            )
        def to_rows(self, parsed):
            return parsed.rows

    result = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL()).run({})
    assert result.status == "completed", result.error
    assert len(seldon_models_home.calls()) == 1

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) FROM harvest.triage_results t
                JOIN harvest.document_metadata d ON d.doc_id = t.doc_id
                WHERE d.source_id = 'triage_test'
                """
            )
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()

    [deposit] = list((tmp_path / "inbox").rglob("*.md"))
    front = yaml.safe_load(deposit.read_text().split("---")[1])
    assert "model_substituted" in front["triage_error"]
    assert front["triage_model_receipt"]["served"] == "claude-sonnet-1-0"
    assert front["triage_model_receipt"]["requested"] == FIXTURE_IDS["sonnet"]
    assert "triage_score" not in front
