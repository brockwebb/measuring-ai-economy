"""Tests for the runner failure-classify hook."""

from datetime import datetime

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.types import RawPayload


@pytest.fixture
def clean_failure_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'rfp_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'rfp_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'rfp_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'rfp_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'rfp_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'rfp_test'")
        conn.commit()
    finally:
        conn.close()


def test_runner_classifies_failures_after_run(clean_failure_state, tmp_path):
    """Runner with an ETL that raises produces a failure_patterns row."""

    class RaisingETL:
        source_id = "rfp_test"
        expected_schema_version = 5
        def parse(self, raw):
            raise RuntimeError("synthetic parse failure at /tmp/x.py:42")
        def to_rows(self, parsed):
            return []

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:z",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 11, 0, 0),
        source_id="rfp_test",
        source_url="https://example.com/bad",
        request_params={},
    )

    class OneFailFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload

    config = RunnerConfig(
        source_id="rfp_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=5,
    )
    runner = Runner(config=config, fetcher=OneFailFetcher(), etl=RaisingETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT occurrence_count, error_signature, sample_error "
                "FROM harvest.failure_patterns WHERE source_id = 'rfp_test'"
            )
            row = cur.fetchone()
            assert row is not None
            count, signature, sample = row
            assert count == 1
            assert "synthetic" in sample
            assert "<path>:<line>" in signature
    finally:
        conn.close()
