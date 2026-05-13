"""Tests for the runner citation-chain enqueue hook."""

from datetime import date, datetime
from pathlib import Path

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.types import ParsedDoc, RawPayload, Row


@pytest.fixture
def clean_cc_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates WHERE payload->>'doi' LIKE '10.9999/cc_test%'")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'cc_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'cc_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'cc_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates WHERE payload->>'doi' LIKE '10.9999/cc_test%'")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'cc_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'cc_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'cc_test'")
        conn.commit()
    finally:
        conn.close()


def test_runner_enqueues_when_citation_chain_enabled(clean_cc_state, tmp_path):
    """citation_chain_enabled=True + parsed.metadata.doi present → candidate row."""

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:cc1",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 12, 0, 0),
        source_id="cc_test",
        source_url="https://example.com/cc1",
        request_params={},
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "cc_test"
        expected_schema_version = 6
        def parse(self, raw):
            return ParsedDoc(
                title="A paper with DOI",
                source_url=raw.source_url,
                published_date=date(2026, 5, 12),
                rows=[Row(target_table="harvest.document_metadata", data={
                    "source_id": "cc_test",
                    "title": "A paper with DOI",
                    "source_url": raw.source_url,
                    "doi": "10.9999/cc_test.001",
                })],
                metadata={"doi": "10.9999/cc_test.001"},
            )
        def to_rows(self, parsed):
            return parsed.rows

    config = RunnerConfig(
        source_id="cc_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=6,
        citation_chain_enabled=True,
    )
    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, payload->>'doi' FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.001'"
            )
            row = cur.fetchone()
            assert row is not None
            status, doi = row
            assert status == "proposed"
            assert doi == "10.9999/cc_test.001"
    finally:
        conn.close()


def test_runner_does_not_enqueue_when_disabled(clean_cc_state, tmp_path):
    """citation_chain_enabled=False (default) → no candidates even with DOI."""

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:cc2",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 12, 0, 0),
        source_id="cc_test",
        source_url="https://example.com/cc2",
        request_params={},
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "cc_test"
        expected_schema_version = 6
        def parse(self, raw):
            return ParsedDoc(
                title="Paper",
                source_url=raw.source_url,
                published_date=date(2026, 5, 12),
                rows=[Row(target_table="harvest.document_metadata", data={
                    "source_id": "cc_test",
                    "title": "Paper",
                    "source_url": raw.source_url,
                    "doi": "10.9999/cc_test.002",
                })],
                metadata={"doi": "10.9999/cc_test.002"},
            )
        def to_rows(self, parsed):
            return parsed.rows

    config = RunnerConfig(
        source_id="cc_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=6,
        citation_chain_enabled=False,
    )
    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.002'"
            )
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()
