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
        output_circuit_breaker_max=500,
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


def _seed_recent_deposits(conn, source_id: str, count: int) -> None:
    """Insert `count` deposited fetched_items rows for the given source with
    fresh fetched_at timestamps so they fall inside any reasonable rolling
    window the gate might use.
    """
    with conn.cursor() as cur:
        for i in range(count):
            cur.execute(
                """
                INSERT INTO harvest.fetched_items
                    (item_id, source_id, raw_hash, run_id, inbox_path, status)
                VALUES (%s, %s, %s, NULL, %s, 'deposited')
                """,
                (
                    f"https://example.com/seed/{source_id}/{i}",
                    source_id,
                    f"sha256:seed-{i}",
                    f"/tmp/seed-{i}.md",
                ),
            )
    conn.commit()


def test_runner_aborts_on_circuit_breaker(clean_run_state, tmp_path):
    """Pre-seed 501 deposited rows for the source inside the rolling window;
    the runner should cancel before the fetcher is called.
    """
    conn = get_connection()
    try:
        _seed_recent_deposits(conn, "runner_test", 501)
    finally:
        conn.close()

    config = RunnerConfig(
        source_id="runner_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "manifest.parquet",
        inbox_dir=tmp_path / "inbox",
        output_circuit_breaker_max=500,
        expected_schema_version=2,
        output_circuit_breaker_window_hours=24,
    )

    class FakeFetcher:
        def iter_payloads(self, query, *, seen=None):
            raise AssertionError("should not reach fetcher when circuit breaker fired")

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
            assert "circuit breaker" in (error or "").lower()
            assert "501" in (error or "")
    finally:
        conn.close()


def test_runner_circuit_breaker_is_per_source(clean_run_state, tmp_path):
    """Recent deposits from a DIFFERENT source must not trip this runner's
    gate — the breaker is per-source, not a global staging count.
    """
    conn = get_connection()
    try:
        # Different source — should NOT count against runner_test.
        _seed_recent_deposits(conn, "some_other_source", 1000)
    finally:
        conn.close()

    config = RunnerConfig(
        source_id="runner_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "manifest.parquet",
        inbox_dir=tmp_path / "inbox",
        output_circuit_breaker_max=500,
        expected_schema_version=2,
    )

    class FakeFetcher:
        def iter_payloads(self, query, *, seen=None):
            return iter([])

    class FakeETL:
        source_id = "runner_test"
        expected_schema_version = 2
        def parse(self, raw): ...
        def to_rows(self, parsed): return []

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({"term": "test"})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM harvest.run_log WHERE source_id = 'runner_test' ORDER BY id DESC LIMIT 1"
            )
            (status,) = cur.fetchone()
            assert status == "completed", (
                "runner should have completed normally — other sources' deposits "
                "must not gate this source"
            )
            # Clean up the cross-source seed rows so they don't pollute future runs.
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'some_other_source'")
        conn.commit()
    finally:
        conn.close()


def test_runner_circuit_breaker_respects_window(clean_run_state, tmp_path):
    """Deposits OUTSIDE the rolling window (older than window_hours) should
    not trip the gate. Backdate the seeded rows and confirm the run proceeds.
    """
    conn = get_connection()
    try:
        _seed_recent_deposits(conn, "runner_test", 600)
        # Backdate them so they fall outside a 1-hour window.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE harvest.fetched_items SET fetched_at = now() - interval '2 hours' "
                "WHERE source_id = 'runner_test'"
            )
        conn.commit()
    finally:
        conn.close()

    config = RunnerConfig(
        source_id="runner_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "manifest.parquet",
        inbox_dir=tmp_path / "inbox",
        output_circuit_breaker_max=500,
        expected_schema_version=2,
        output_circuit_breaker_window_hours=1,  # tight window so seeds fall outside
    )

    class FakeFetcher:
        def iter_payloads(self, query, *, seen=None):
            return iter([])

    class FakeETL:
        source_id = "runner_test"
        expected_schema_version = 2
        def parse(self, raw): ...
        def to_rows(self, parsed): return []

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({"term": "test"})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM harvest.run_log WHERE source_id = 'runner_test' ORDER BY id DESC LIMIT 1"
            )
            (status,) = cur.fetchone()
            assert status == "completed", (
                "deposits older than the rolling window must not gate the run"
            )
    finally:
        conn.close()
