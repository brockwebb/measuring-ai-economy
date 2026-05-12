"""Failure pattern classifier.

Reads failed fetched_items rows from a just-completed run, normalizes the
error strings, upserts into harvest.failure_patterns. Alerts when a signature
crosses 10 occurrences in 7 days.
"""

from __future__ import annotations

import re

import psycopg


_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_URL_RE = re.compile(r"https?://\S+")
_PATH_LINENO_RE = re.compile(r"(/[\w\-./]+):\d+")
_NUMERIC_ID_RE = re.compile(r"\b\d{4,}\b")
_HEX_HASH_RE = re.compile(r"\b[0-9a-f]{16,}\b")


def normalize_error(error: str) -> str:
    """Reduce a raw error message to its stable signature."""
    if not error:
        return "(empty)"
    s = error.strip()
    s = _TIMESTAMP_RE.sub("<ts>", s)
    s = _URL_RE.sub("<url>", s)
    s = _PATH_LINENO_RE.sub(r"<path>:<line>", s)
    s = _HEX_HASH_RE.sub("<hash>", s)
    s = _NUMERIC_ID_RE.sub("<id>", s)
    if len(s) > 500:
        s = s[:200] + "..." + s[-200:]
    return s


class FailureClassifier:
    """Reads failed fetched_items rows for a run, upserts harvest.failure_patterns."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def classify_run(self, run_id: int) -> int:
        """Process all failed fetched_items for run_id. Returns count of failures classified."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_id, error FROM harvest.fetched_items
                WHERE run_id = %s AND status = 'failed' AND error IS NOT NULL
                """,
                (run_id,),
            )
            rows = cur.fetchall()

        count = 0
        for source_id, error in rows:
            signature = normalize_error(error)
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO harvest.failure_patterns
                        (source_id, error_signature, sample_error, occurrence_count, last_seen_at)
                    VALUES (%s, %s, %s, 1, now())
                    ON CONFLICT (source_id, error_signature) DO UPDATE
                    SET occurrence_count = harvest.failure_patterns.occurrence_count + 1,
                        last_seen_at = now()
                    """,
                    (source_id, signature, error[:1000]),
                )
            count += 1
        self._conn.commit()
        return count


def patterns_above_threshold(
    conn: psycopg.Connection,
    *,
    min_count: int = 10,
    window_days: int = 7,
) -> list[dict]:
    """Return failure_patterns rows with occurrence_count >= min_count seen in last window_days."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id, error_signature, occurrence_count, sample_error,
                   first_seen_at, last_seen_at, mitigation_status
            FROM harvest.failure_patterns
            WHERE occurrence_count >= %s
              AND last_seen_at > now() - make_interval(days => %s)
              AND mitigation_status = 'unaddressed'
            ORDER BY occurrence_count DESC
            """,
            (min_count, window_days),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
