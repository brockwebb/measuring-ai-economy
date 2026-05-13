"""Tests for CitationChain.expand_approved (seed-feedback loop)."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from harvester.db import get_connection
from harvester.improvement.citation_chain import CitationChain


# All test rows use a distinctive DOI prefix so cleanup is unambiguous.
_TEST_DOI_PREFIX = "10.9999/expand_test"


@pytest.fixture
def clean_expand_candidates():
    """Wipe any leftover test rows before AND after each test.

    Depth-2 rows reference depth-1 via parent_candidate_id (ON DELETE SET NULL),
    so we don't need a strict ordering — but we delete children first anyway
    so the parent_candidate_id chain stays clean for assertions.
    """
    def _clean(conn):
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' LIKE %s",
                (f"{_TEST_DOI_PREFIX}%",),
            )
        conn.commit()

    conn = get_connection()
    try:
        _clean(conn)
        yield
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
