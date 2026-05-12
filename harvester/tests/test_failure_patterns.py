"""Tests for the failure-pattern classifier."""

import pytest

from harvester.db import get_connection
from harvester.improvement.failure_patterns import (
    FailureClassifier,
    normalize_error,
    patterns_above_threshold,
)


@pytest.fixture
def clean_failure_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'fp_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'fp_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'fp_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'fp_test'")
        conn.commit()
    finally:
        conn.close()


def test_normalize_error_strips_variable_parts():
    a = "Traceback at /Users/brock/foo.py:123, fetching https://example.com/abs/2305.12345"
    b = "Traceback at /Users/brock/foo.py:456, fetching https://example.com/abs/2401.67890"
    assert normalize_error(a) == normalize_error(b)


def test_normalize_error_keeps_distinct_signatures_distinct():
    a = "ConnectionRefusedError: localhost:5432"
    b = "TimeoutError: read timed out after 30s"
    assert normalize_error(a) != normalize_error(b)


def test_classifier_upserts_failure_signature(clean_failure_state):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.run_log (id, source_id, status) "
                "VALUES (DEFAULT, 'fp_test', 'running') RETURNING id"
            )
            run_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status, run_id, error) "
                "VALUES (%s, 'fp_test', 'failed', %s, %s), (%s, 'fp_test', 'failed', %s, %s)",
                ("https://example.com/a", run_id,
                 "Traceback at /tmp/x.py:123, fetching https://example.com/a",
                 "https://example.com/b", run_id,
                 "Traceback at /tmp/x.py:456, fetching https://example.com/b"),
            )
        conn.commit()

        classifier = FailureClassifier(conn)
        classifier.classify_run(run_id)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT occurrence_count FROM harvest.failure_patterns "
                "WHERE source_id = 'fp_test'"
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 2
    finally:
        conn.close()


def test_classifier_handles_distinct_signatures(clean_failure_state):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.run_log (id, source_id, status) "
                "VALUES (DEFAULT, 'fp_test', 'running') RETURNING id"
            )
            run_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status, run_id, error) "
                "VALUES (%s, 'fp_test', 'failed', %s, %s), (%s, 'fp_test', 'failed', %s, %s)",
                ("https://example.com/a", run_id, "ConnectionRefusedError: localhost:5432",
                 "https://example.com/b", run_id, "TimeoutError: read timed out after 30s"),
            )
        conn.commit()

        classifier = FailureClassifier(conn)
        classifier.classify_run(run_id)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.failure_patterns WHERE source_id = 'fp_test'"
            )
            assert cur.fetchone()[0] == 2
    finally:
        conn.close()


def test_patterns_above_threshold_returns_recent_high_count_patterns(clean_failure_state):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.failure_patterns
                    (source_id, error_signature, last_seen_at, occurrence_count, sample_error)
                VALUES
                    ('fp_test', 'sig_high', now(), 15, 'recent high-count'),
                    ('fp_test', 'sig_low', now(), 3, 'recent low-count'),
                    ('fp_test', 'sig_old', now() - interval '14 days', 99, 'old but high-count')
                """
            )
        conn.commit()

        results = patterns_above_threshold(conn, min_count=10, window_days=7)
        signatures = [r["error_signature"] for r in results]
        assert "sig_high" in signatures
        assert "sig_low" not in signatures
        assert "sig_old" not in signatures
    finally:
        conn.close()
