"""Tests for the runner orchestration."""

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig


@pytest.fixture
def clean_run_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'runner_test'")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'runner_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'runner_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'runner_test'")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'runner_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'runner_test'")
        conn.commit()
    finally:
        conn.close()


def test_runner_writes_run_log_completed_on_success(clean_run_state, tmp_path):
    config = RunnerConfig(
        source_id="runner_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "manifest.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=2,
    )

    class FakeFetcher:
        def iter_payloads(self, query, *, seen=None):
            return iter([])

    class FakeETL:
        source_id = "runner_test"
        expected_schema_version = 2
        def parse(self, raw):
            raise AssertionError("should not be called with empty iter")
        def to_rows(self, parsed):
            return parsed.rows

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({"term": "test"})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, items_fetched FROM harvest.run_log WHERE source_id = 'runner_test'"
            )
            status, fetched = cur.fetchone()
            assert status == "completed"
            assert fetched == 0
    finally:
        conn.close()


def test_runner_aborts_on_backpressure(clean_run_state, tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for i in range(501):
        (inbox / f"x{i}.md").write_text("")

    config = RunnerConfig(
        source_id="runner_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "manifest.parquet",
        inbox_dir=inbox,
        inbox_backpressure_max=500,
        expected_schema_version=2,
    )

    class FakeFetcher:
        def iter_payloads(self, query):
            raise AssertionError("should not reach fetcher when backpressured")

    class FakeETL:
        source_id = "runner_test"
        expected_schema_version = 2
        def parse(self, raw): ...
        def to_rows(self, parsed): ...

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({"term": "test"})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, error FROM harvest.run_log WHERE source_id = 'runner_test' ORDER BY id DESC LIMIT 1"
            )
            status, error = cur.fetchone()
            assert status == "cancelled"
            assert "backpressure" in (error or "").lower()
    finally:
        conn.close()
