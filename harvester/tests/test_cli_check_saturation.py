"""Tests for `harvester check-saturation` CLI."""

import subprocess

import pytest

from harvester.db import get_connection


@pytest.fixture
def synthetic_saturated_data():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'sat_cli_test'")
            for d in range(8):
                cur.execute(
                    """
                    INSERT INTO harvest.run_log
                        (source_id, status, items_fetched, items_deposited, started_at, finished_at)
                    VALUES ('sat_cli_test', 'completed', 100, 2, now() - make_interval(days => %s),
                            now() - make_interval(days => %s))
                    """,
                    (d, d),
                )
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'sat_cli_test'")
        conn.commit()
    finally:
        conn.close()


def test_check_saturation_cli_reports_alert(synthetic_saturated_data):
    result = subprocess.run(
        ["uv", "run", "harvester", "check-saturation"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode != 0, "should exit non-zero when alerts present"
    out = result.stdout + result.stderr
    assert "sat_cli_test" in out
    assert "alert" in out.lower() or "saturated" in out.lower()


def test_check_saturation_cli_clean_exit_when_no_alerts():
    subprocess.run(
        ["psql", "-d", "wintermute", "-c",
         "DELETE FROM harvest.run_log WHERE source_id = 'sat_cli_test'"],
        capture_output=True,
    )
    result = subprocess.run(
        ["uv", "run", "harvester", "check-saturation"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "Traceback" not in result.stderr
