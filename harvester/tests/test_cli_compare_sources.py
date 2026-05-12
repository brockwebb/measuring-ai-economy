"""Tests for harvester compare-sources CLI."""

import subprocess
import pytest

from harvester.db import get_connection


@pytest.fixture
def staged_compare_fixtures():
    """Insert synthetic data for two side-by-side sources.

    10 docs for 'cmp_old', 11 for 'cmp_new', with 9 overlapping URLs.
    Expected: 1 only-in-old, 2 only-in-new, 9 both.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id IN ('cmp_old', 'cmp_new')")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id IN ('cmp_old', 'cmp_new')")
            for i in range(10):
                cur.execute(
                    "INSERT INTO harvest.document_metadata (source_id, title, source_url, published_date) "
                    "VALUES ('cmp_old', %s, %s, current_date)",
                    (f"Paper {i}", f"https://arxiv.org/abs/2026.0{i}"),
                )
            for i in range(1, 12):
                cur.execute(
                    "INSERT INTO harvest.document_metadata (source_id, title, source_url, published_date) "
                    "VALUES ('cmp_new', %s, %s, current_date)",
                    (f"Paper {i}", f"https://arxiv.org/abs/2026.0{i}"),
                )
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id IN ('cmp_old', 'cmp_new')")
        conn.commit()
    finally:
        conn.close()


def test_compare_sources_reports_overlap_and_diff(staged_compare_fixtures):
    result = subprocess.run(
        ["uv", "run", "harvester", "compare-sources", "cmp_old", "cmp_new",
         "--days", "1"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout
    assert "old:" in out and "10" in out
    assert "new:" in out and "11" in out
    assert "both:" in out and "9" in out
    assert "only-in-old:" in out and "1" in out
    assert "only-in-new:" in out and "2" in out
