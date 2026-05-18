"""Tests for the runner co-occurrence hook."""

from datetime import datetime

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.types import RawPayload


@pytest.fixture
def clean_co_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.co_sources WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id IN ('co_a', 'co_b')")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.co_sources WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id IN ('co_a', 'co_b')")
        conn.commit()
    finally:
        conn.close()


def test_runner_records_co_occurrence_when_url_known_under_other_source(clean_co_state, tmp_path):
    """A URL deposited under co_a is encountered by co_b → co_sources row written."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status) "
                "VALUES ('https://example.com/shared', 'co_a', 'deposited')"
            )
        conn.commit()
    finally:
        conn.close()

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:x",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 10, 0, 0),
        source_id="co_b",
        source_url="https://example.com/shared",
        request_params={},
    )

    config = RunnerConfig(
        source_id="co_b",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        output_circuit_breaker_max=500,
        expected_schema_version=5,
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "co_b"
        expected_schema_version = 5
        def parse(self, raw):
            raise AssertionError("ETL should NOT be called when co-occurrence skip fires")
        def to_rows(self, parsed):
            return []

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT canonical_key, canonical_kind, source_id FROM harvest.co_sources "
                "WHERE source_id = 'co_b'"
            )
            row = cur.fetchone()
            assert row is not None
            key, kind, src = row
            assert key == "https://example.com/shared"
            assert kind == "url"
            assert src == "co_b"
    finally:
        conn.close()


def test_runner_does_not_record_co_occurrence_for_same_source_dedup(clean_co_state, tmp_path):
    """Same-source dedup is a silent skip, no co_sources row."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status) "
                "VALUES ('https://example.com/x', 'co_a', 'deposited')"
            )
        conn.commit()
    finally:
        conn.close()

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:y",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 10, 0, 0),
        source_id="co_a",
        source_url="https://example.com/x",
        request_params={},
    )

    config = RunnerConfig(
        source_id="co_a",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        output_circuit_breaker_max=500,
        expected_schema_version=5,
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "co_a"
        expected_schema_version = 5
        def parse(self, raw): ...
        def to_rows(self, parsed): return []

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM harvest.co_sources WHERE source_id = 'co_a'")
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()
