"""Tests for CitationChain.expand_approved (seed-feedback loop)."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from harvester.db import get_connection
from harvester.improvement.citation_chain import CitationChain


# All test rows use a distinctive DOI prefix so cleanup is unambiguous.
_TEST_DOI_PREFIX = "10.9999/expand_test"


_QUARANTINE_SENTINEL = "1970-01-01 00:00:00+00"


@pytest.fixture
def clean_expand_candidates():
    """Wipe leftover test rows AND quarantine live approved-pending parents
    so the helper only operates on our seeded test data.

    expand_approved() picks up any approved candidate without expanded_at —
    including rows from concurrent live harvester runs. We stamp those with
    a sentinel expanded_at so the helper skips them, run the test, then
    restore them at teardown. The sentinel `1970-01-01` lets us identify
    exactly which rows we quarantined (avoiding races with rows the helper
    legitimately expanded during the test).
    """
    def _clean(conn):
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' LIKE %s",
                (f"{_TEST_DOI_PREFIX}%",),
            )
        conn.commit()

    def _quarantine_live_pending(conn):
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE harvest.expansion_candidates
                SET expanded_at = %s::timestamptz
                WHERE status = 'approved'
                  AND expanded_at IS NULL
                  AND (payload->>'doi' IS NULL
                       OR payload->>'doi' NOT LIKE %s)
                RETURNING id
                """,
                (_QUARANTINE_SENTINEL, f"{_TEST_DOI_PREFIX}%"),
            )
            return [r[0] for r in cur.fetchall()]

    def _restore_quarantine(conn, ids):
        if not ids:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE harvest.expansion_candidates
                SET expanded_at = NULL
                WHERE id = ANY(%s) AND expanded_at = %s::timestamptz
                """,
                (ids, _QUARANTINE_SENTINEL),
            )
        conn.commit()

    conn = get_connection()
    try:
        _clean(conn)
        quarantined = _quarantine_live_pending(conn)
        conn.commit()
        try:
            yield
        finally:
            _restore_quarantine(conn, quarantined)
            _clean(conn)
    finally:
        conn.close()


def _seed_approved_parent(conn, *, doi_suffix: str, parent_doc_id=None, score=0.8) -> int:
    """Insert an approved depth-1 candidate; return its id."""
    payload = {"doi": f"{_TEST_DOI_PREFIX}.parent.{doi_suffix}",
               "title": f"Parent {doi_suffix}",
               "source_url": "https://arxiv.org/abs/test"}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO harvest.expansion_candidates
                (kind, payload, parent_doc_id, depth, status, score)
            VALUES ('paper', %s::jsonb, %s, 1, 'approved', %s)
            RETURNING id
            """,
            (json.dumps(payload, sort_keys=True), parent_doc_id, score),
        )
        row_id = cur.fetchone()[0]
    conn.commit()
    return row_id


def _make_ref(ss_id: str, doi: str | None, title: str = "Ref"):
    """Build a Semantic Scholar reference dict in the API response shape."""
    return {
        "paperId": ss_id,
        "title": title,
        "externalIds": ({"DOI": doi} if doi else {}),
    }


def test_expand_approved_writes_depth_2_candidates(clean_expand_candidates):
    """Happy path: approved parent + 3 refs with DOIs → 3 depth-2 candidates,
    parent_candidate_id propagated, parent stamped with expanded_at."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="001")

        mock_ss = MagicMock()
        mock_ss.get_references.return_value = [
            _make_ref("ss_r1", f"{_TEST_DOI_PREFIX}.ref.001", "Ref One"),
            _make_ref("ss_r2", f"{_TEST_DOI_PREFIX}.ref.002", "Ref Two"),
            _make_ref("ss_r3", f"{_TEST_DOI_PREFIX}.ref.003", "Ref Three"),
        ]

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["parents_expanded"] == 1
        assert result["refs_enqueued"] == 3
        assert result["refs_dedup"] == 0
        assert result["refs_skipped_no_doi"] == 0
        assert result["deferred"] == 0

        mock_ss.get_references.assert_called_once_with(
            f"DOI:{_TEST_DOI_PREFIX}.parent.001", limit=100)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload->>'doi', parent_candidate_id, depth, status
                FROM harvest.expansion_candidates
                WHERE parent_candidate_id = %s
                ORDER BY id
                """,
                (parent_id,),
            )
            rows = cur.fetchall()
        assert len(rows) == 3
        for doi, pc_id, depth, status in rows:
            assert doi.startswith(f"{_TEST_DOI_PREFIX}.ref.")
            assert pc_id == parent_id
            assert depth == 2
            assert status == "proposed"

        with conn.cursor() as cur:
            cur.execute(
                "SELECT expanded_at FROM harvest.expansion_candidates WHERE id = %s",
                (parent_id,),
            )
            (stamped,) = cur.fetchone()
        assert stamped is not None
    finally:
        conn.close()


def test_expand_approved_skips_refs_without_doi(clean_expand_candidates):
    """Refs with no externalIds.DOI are dropped; counter increments."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="002")

        mock_ss = MagicMock()
        mock_ss.get_references.return_value = [
            _make_ref("ss_a", f"{_TEST_DOI_PREFIX}.ref.010"),
            _make_ref("ss_b", None),
            _make_ref("ss_c", f"{_TEST_DOI_PREFIX}.ref.011"),
        ]

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["refs_enqueued"] == 2
        assert result["refs_skipped_no_doi"] == 1
        assert result["parents_expanded"] == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.expansion_candidates "
                "WHERE parent_candidate_id = %s",
                (parent_id,),
            )
            assert cur.fetchone()[0] == 2
    finally:
        conn.close()


def test_expand_approved_dedups_across_parents(clean_expand_candidates):
    """Two parents cite the same ref → first inserts, second hits UNIQUE."""
    conn = get_connection()
    try:
        parent_a = _seed_approved_parent(conn, doi_suffix="003", score=0.9)
        parent_b = _seed_approved_parent(conn, doi_suffix="004", score=0.8)

        shared_doi = f"{_TEST_DOI_PREFIX}.ref.020"
        mock_ss = MagicMock()
        mock_ss.get_references.return_value = [_make_ref("ss_shared", shared_doi)]

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        # Two parents processed (score DESC → parent_a first), one ref enqueued,
        # second insert deduped.
        assert result["parents_expanded"] == 2
        assert result["refs_enqueued"] == 1
        assert result["refs_dedup"] == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = %s",
                (shared_doi,),
            )
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()


def test_expand_approved_skips_already_expanded(clean_expand_candidates):
    """Parents with expanded_at NOT NULL are not selected."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="005")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE harvest.expansion_candidates "
                "SET expanded_at = now() WHERE id = %s",
                (parent_id,),
            )
        conn.commit()

        mock_ss = MagicMock()
        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["parents_expanded"] == 0
        mock_ss.get_references.assert_not_called()
    finally:
        conn.close()


def test_expand_approved_stamps_on_empty_refs(clean_expand_candidates):
    """Empty refs list = successful expansion (SS has no refs for this paper).
    Parent gets stamped so we don't retry forever."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="006")

        mock_ss = MagicMock()
        mock_ss.get_references.return_value = []

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["parents_expanded"] == 1
        assert result["refs_enqueued"] == 0
        assert result["deferred"] == 0

        with conn.cursor() as cur:
            cur.execute(
                "SELECT expanded_at FROM harvest.expansion_candidates WHERE id = %s",
                (parent_id,),
            )
            assert cur.fetchone()[0] is not None
    finally:
        conn.close()


def test_expand_approved_defers_on_exception(clean_expand_candidates):
    """get_references raises → parent stays unexpanded, deferred++ ."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="007")

        mock_ss = MagicMock()
        mock_ss.get_references.side_effect = RuntimeError("transient SS error")

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["parents_expanded"] == 0
        assert result["deferred"] == 1
        assert result["refs_enqueued"] == 0

        with conn.cursor() as cur:
            cur.execute(
                "SELECT expanded_at FROM harvest.expansion_candidates WHERE id = %s",
                (parent_id,),
            )
            assert cur.fetchone()[0] is None
    finally:
        conn.close()
