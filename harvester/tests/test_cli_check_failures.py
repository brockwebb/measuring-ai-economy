"""Tests for `harvester check-failures` CLI."""

import subprocess

import pytest

from harvester.db import get_connection


@pytest.fixture
def synthetic_failure_patterns():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_cli_test'")
            cur.execute(
                """
                INSERT INTO harvest.failure_patterns
                    (source_id, error_signature, occurrence_count, last_seen_at, sample_error)
                VALUES
                    ('fp_cli_test', 'sig_high', 25, now(), 'sample of the high-frequency error'),
                    ('fp_cli_test', 'sig_low', 3, now(), 'sample of the low-frequency one')
                """
            )
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_cli_test'")
        conn.commit()
    finally:
        conn.close()


def test_check_failures_reports_above_threshold(synthetic_failure_patterns):
    result = subprocess.run(
        ["uv", "run", "harvester", "check-failures"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    out = result.stdout
    assert "sig_high" in out
    assert "25" in out
    assert "sig_low" not in out


def test_check_failures_clean_when_no_alerts():
    subprocess.run(
        ["psql", "-d", "wintermute", "-c",
         "DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_cli_test'"],
        capture_output=True,
    )
    result = subprocess.run(
        ["uv", "run", "harvester", "check-failures"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "Traceback" not in result.stderr
