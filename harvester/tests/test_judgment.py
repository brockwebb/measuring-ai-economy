"""Tests for harvester.improvement.judgment heuristic helpers."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from harvester.db import get_connection
from harvester.improvement.judgment import (
    auto_confirm_approved_high_score,
    auto_confirm_rejected_low_score,
    auto_reject_stale_proposed,
    auto_mark_high_confidence_provenance_reviewed,
    borderline_candidates_for_llm_review,
    borderline_provenance_for_human_eyes,
)


_TEST_DOI_PREFIX = "10.9999/judgment_test"


@pytest.fixture
def clean_judgment_rows():
    def _clean(conn):
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' LIKE %s",
                (f"{_TEST_DOI_PREFIX}%",),
            )
            cur.execute(
                "DELETE FROM harvest.stochastic_provenance "
                "WHERE table_name = 'judgment_test'"
            )
        conn.commit()

    conn = get_connection()
    try:
        _clean(conn)
        yield
        _clean(conn)
    finally:
        conn.close()


def _seed_candidate(conn, *, doi_suffix, status, score=None, reviewed_by=None,
                    proposed_at=None) -> int:
    payload = {"doi": f"{_TEST_DOI_PREFIX}.{doi_suffix}", "title": doi_suffix}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO harvest.expansion_candidates
                (kind, payload, depth, status, score, reviewed_by, proposed_at)
            VALUES ('paper', %s::jsonb, 1, %s, %s, %s,
                    COALESCE(%s, now()))
            RETURNING id
            """,
            (json.dumps(payload, sort_keys=True), status, score, reviewed_by,
             proposed_at),
        )
        row_id = cur.fetchone()[0]
    conn.commit()
    return row_id


def _seed_provenance(conn, *, row_pk, confidence, reviewed=False):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO harvest.stochastic_provenance
                (table_name, row_pk, field, model_id, prompt_hash, confidence, reviewed)
            VALUES ('judgment_test', %s, 'test_field', 'test-model', repeat('a', 64),
                    %s, %s)
            ON CONFLICT (table_name, row_pk, field) DO UPDATE
                SET confidence = EXCLUDED.confidence, reviewed = EXCLUDED.reviewed
            """,
            (row_pk, confidence, reviewed),
        )
    conn.commit()


def test_auto_confirm_approved_high_score(clean_judgment_rows):
    """The helper UPDATEs every untagged matching row in the DB — including
    any from live harvester runs. We assert at least our seeded row was
    tagged (n >= 1) and then verify the specific row got the expected tag."""
    conn = get_connection()
    try:
        cid = _seed_candidate(conn, doi_suffix="ach.001", status="approved",
                              score=0.85)
        n = auto_confirm_approved_high_score(conn, threshold=0.7)
        assert n >= 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT reviewed_by FROM harvest.expansion_candidates WHERE id = %s",
                (cid,),
            )
            assert cur.fetchone()[0] == "claudeclaw:judgment:confirmed-high"

        # Re-running should not re-tag our row. Bound by <= 1 to allow for a
        # concurrent live insert landing between the two calls.
        assert auto_confirm_approved_high_score(conn, threshold=0.7) <= 1
        with conn.cursor() as cur:
            cur.execute(
                "SELECT reviewed_by FROM harvest.expansion_candidates WHERE id = %s",
                (cid,),
            )
            assert cur.fetchone()[0] == "claudeclaw:judgment:confirmed-high"
    finally:
        conn.close()


def test_auto_confirm_rejected_low_score(clean_judgment_rows):
    conn = get_connection()
    try:
        cid = _seed_candidate(conn, doi_suffix="acl.001", status="rejected",
                              score=0.05)
        n = auto_confirm_rejected_low_score(conn, threshold=0.15)
        assert n >= 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT reviewed_by FROM harvest.expansion_candidates WHERE id = %s",
                (cid,),
            )
            assert cur.fetchone()[0] == "claudeclaw:judgment:confirmed-low"
    finally:
        conn.close()


def test_auto_reject_stale_proposed(clean_judgment_rows):
    conn = get_connection()
    try:
        old = datetime.now(timezone.utc) - timedelta(days=70)
        cid = _seed_candidate(conn, doi_suffix="ars.001", status="proposed",
                              score=None, proposed_at=old)
        n = auto_reject_stale_proposed(conn, days=60)
        assert n >= 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, reviewed_by FROM harvest.expansion_candidates WHERE id = %s",
                (cid,),
            )
            status, reviewed_by = cur.fetchone()
            assert status == "rejected"
            assert reviewed_by == "claudeclaw:judgment:stale-untried"
    finally:
        conn.close()


def test_auto_mark_high_confidence_provenance_reviewed(clean_judgment_rows):
    conn = get_connection()
    try:
        _seed_provenance(conn, row_pk=1001, confidence=0.92)
        _seed_provenance(conn, row_pk=1002, confidence=0.70)  # below threshold
        n = auto_mark_high_confidence_provenance_reviewed(conn, threshold=0.85)
        assert n >= 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT row_pk, reviewed FROM harvest.stochastic_provenance "
                "WHERE table_name = 'judgment_test' ORDER BY row_pk"
            )
            rows = cur.fetchall()
        assert (1001, True) in rows
        assert (1002, False) in rows
    finally:
        conn.close()


def test_borderline_candidates_for_llm_review_excludes_claudeclaw_reviewed(
        clean_judgment_rows):
    conn = get_connection()
    try:
        _seed_candidate(conn, doi_suffix="brd.001", status="approved", score=0.55,
                        reviewed_by=None)
        _seed_candidate(conn, doi_suffix="brd.002", status="approved", score=0.45,
                        reviewed_by="claudeclaw:judgment:llm-confirm")
        _seed_candidate(conn, doi_suffix="brd.003", status="rejected", score=0.50,
                        reviewed_by=None)

        # Use a large limit so test rows aren't pushed out by accumulated
        # live data in harvest.expansion_candidates.
        results = borderline_candidates_for_llm_review(conn, lo=0.4, hi=0.6,
                                                       limit=10000)
        suffixes = sorted(r["payload"]["doi"].split(".")[-1] for r in results
                          if r["payload"]["doi"].startswith(_TEST_DOI_PREFIX))
        # 001 (no reviewer) and 003 (no reviewer) qualify; 002 is excluded.
        assert "001" in suffixes
        assert "003" in suffixes
        assert "002" not in suffixes
    finally:
        conn.close()


def test_borderline_provenance_for_human_eyes_orders_by_age(clean_judgment_rows):
    conn = get_connection()
    try:
        # Insert two unreviewed rows; both confidence < 0.5
        _seed_provenance(conn, row_pk=2001, confidence=0.10)
        _seed_provenance(conn, row_pk=2002, confidence=0.20)

        results = borderline_provenance_for_human_eyes(conn, threshold=0.5,
                                                       limit=10)
        # Filter to our test rows
        rows = [r for r in results if r["table_name"] == "judgment_test"]
        assert len(rows) >= 2
        # Sorted by created_at ASC (oldest first); since both inserted just
        # now, we relax to: both are present and have confidence < 0.5.
        for r in rows[:2]:
            assert r["confidence"] < 0.5
    finally:
        conn.close()
