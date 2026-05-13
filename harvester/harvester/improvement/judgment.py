"""Heuristic judgment helpers used by the weekly claudeclaw harvest_judgment job.

All functions are pure SQL — deterministic, testable, no LLM in the loop.
Decisions are tagged on existing audit columns:
- expansion_candidates.reviewed_by — prefix 'claudeclaw:judgment:'
- stochastic_provenance.reviewed   — flipped to true

The borderline selectors return rows for the markdown job to either apply
LLM judgment (candidates) or surface in the digest (provenance).
"""

from __future__ import annotations

from typing import Any

import psycopg


def auto_confirm_approved_high_score(
    conn: psycopg.Connection,
    *,
    threshold: float = 0.7,
) -> int:
    """Approved candidates with score >= threshold AND reviewed_by NOT LIKE
    'claudeclaw:%' → stamp reviewed_by='claudeclaw:judgment:confirmed-high'.

    Returns count updated.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE harvest.expansion_candidates
            SET reviewed_by = 'claudeclaw:judgment:confirmed-high',
                reviewed_at = now()
            WHERE kind = 'paper'
              AND status = 'approved'
              AND score >= %s
              AND (reviewed_by IS NULL OR reviewed_by NOT LIKE 'claudeclaw:%%')
            """,
            (threshold,),
        )
        n = cur.rowcount
    conn.commit()
    return n


def auto_confirm_rejected_low_score(
    conn: psycopg.Connection,
    *,
    threshold: float = 0.15,
) -> int:
    """Rejected candidates with score < threshold AND reviewed_by NOT LIKE
    'claudeclaw:%' → stamp reviewed_by='claudeclaw:judgment:confirmed-low'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE harvest.expansion_candidates
            SET reviewed_by = 'claudeclaw:judgment:confirmed-low',
                reviewed_at = now()
            WHERE kind = 'paper'
              AND status = 'rejected'
              AND score < %s
              AND (reviewed_by IS NULL OR reviewed_by NOT LIKE 'claudeclaw:%%')
            """,
            (threshold,),
        )
        n = cur.rowcount
    conn.commit()
    return n


def auto_reject_stale_proposed(
    conn: psycopg.Connection,
    *,
    days: int = 60,
) -> int:
    """Proposed candidates older than `days` with no score → status='rejected',
    reviewed_by='claudeclaw:judgment:stale-untried'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE harvest.expansion_candidates
            SET status = 'rejected',
                reviewed_by = 'claudeclaw:judgment:stale-untried',
                reviewed_at = now()
            WHERE kind = 'paper'
              AND status = 'proposed'
              AND score IS NULL
              AND proposed_at < now() - make_interval(days => %s)
            """,
            (days,),
        )
        n = cur.rowcount
    conn.commit()
    return n


def auto_mark_high_confidence_provenance_reviewed(
    conn: psycopg.Connection,
    *,
    threshold: float = 0.85,
) -> int:
    """stochastic_provenance rows with confidence >= threshold AND reviewed=false
    → reviewed=true.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE harvest.stochastic_provenance
            SET reviewed = true
            WHERE reviewed = false
              AND confidence IS NOT NULL
              AND confidence >= %s
            """,
            (threshold,),
        )
        n = cur.rowcount
    conn.commit()
    return n


def borderline_candidates_for_llm_review(
    conn: psycopg.Connection,
    *,
    lo: float = 0.4,
    hi: float = 0.6,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Candidates with score in (lo, hi) that have NOT been claudeclaw-reviewed.
    Returns dicts with id, status, score, payload (parsed), proposed_at.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, status, score, payload, proposed_at
            FROM harvest.expansion_candidates
            WHERE kind = 'paper'
              AND score IS NOT NULL
              AND score > %s
              AND score < %s
              AND (reviewed_by IS NULL OR reviewed_by NOT LIKE 'claudeclaw:%%')
            ORDER BY score DESC, proposed_at ASC
            LIMIT %s
            """,
            (lo, hi, limit),
        )
        rows = cur.fetchall()
    return [
        {"id": r[0], "status": r[1], "score": r[2], "payload": r[3],
         "proposed_at": r[4]}
        for r in rows
    ]


def borderline_provenance_for_human_eyes(
    conn: psycopg.Connection,
    *,
    threshold: float = 0.5,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Unreviewed stochastic_provenance rows with confidence < threshold,
    oldest first. Surfaced in the digest, not auto-touched.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, row_pk, field, model_id, confidence, created_at
            FROM harvest.stochastic_provenance
            WHERE reviewed = false
              AND confidence IS NOT NULL
              AND confidence < %s
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (threshold, limit),
        )
        rows = cur.fetchall()
    return [
        {"table_name": r[0], "row_pk": r[1], "field": r[2],
         "model_id": r[3], "confidence": r[4], "created_at": r[5]}
        for r in rows
    ]
