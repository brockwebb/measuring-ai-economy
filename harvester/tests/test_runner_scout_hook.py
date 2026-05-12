"""Tests for the runner's lazy scout integration."""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.discovery.types import DiscoveryNotes


@pytest.fixture
def clean_scout_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.data_sources WHERE source_id = 'scout_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'scout_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.data_sources WHERE source_id = 'scout_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'scout_test'")
        conn.commit()
    finally:
        conn.close()


def _fake_notes():
    return DiscoveryNotes(
        base_url="https://example.com",
        probed_at=datetime.now(timezone.utc),
        llms_txt={"title": "Test"},
        robots_rules=None,
        sitemap_urls=[],
        openapi_spec=None,
        rss_feeds=[],
        schema_org_types=[],
        probe_errors={},
    )


@patch("harvester.runner.MuiScout")
def test_runner_scouts_on_first_run(mock_scout_cls, clean_scout_state, tmp_path):
    mock_scout = MagicMock()
    mock_scout.probe.return_value = _fake_notes()
    mock_scout_cls.return_value = mock_scout

    config = RunnerConfig(
        source_id="scout_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=3,
        scout_base_url="https://example.com",
    )

    class FakeFetcher:
        def iter_payloads(self, q, *, seen=None): return iter([])
    class FakeETL:
        source_id = "scout_test"
        expected_schema_version = 3
        def parse(self, raw): ...
        def to_rows(self, parsed): return []

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    mock_scout.probe.assert_called_once()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT discovery_notes, last_scouted_at FROM harvest.data_sources WHERE source_id = 'scout_test'"
            )
            row = cur.fetchone()
            assert row is not None
            notes, scouted_at = row
            assert notes["base_url"] == "https://example.com"
            assert scouted_at is not None
    finally:
        conn.close()


@patch("harvester.runner.MuiScout")
def test_runner_skips_scout_on_recent_run(mock_scout_cls, clean_scout_state, tmp_path):
    """If last_scouted_at is recent, scout is NOT called again."""
    mock_scout = MagicMock()
    mock_scout.probe.return_value = _fake_notes()
    mock_scout_cls.return_value = mock_scout

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.data_sources (source_id, name, last_scouted_at, discovery_notes)
                VALUES ('scout_test', 'Test', now(), '{}'::jsonb)
                ON CONFLICT (source_id) DO UPDATE SET last_scouted_at = now()
                """
            )
        conn.commit()
    finally:
        conn.close()

    config = RunnerConfig(
        source_id="scout_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=3,
        scout_base_url="https://example.com",
    )

    class FakeFetcher:
        def iter_payloads(self, q, *, seen=None): return iter([])
    class FakeETL:
        source_id = "scout_test"
        expected_schema_version = 3

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    mock_scout.probe.assert_not_called()
