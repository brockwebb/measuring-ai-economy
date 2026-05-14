"""Tests for CitationChain (enqueue + process_pending)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from harvester.db import get_connection
from harvester.improvement.citation_chain import CitationChain
from harvester.types import ParsedDoc, Row
from datetime import date


@pytest.fixture
def clean_candidates():
    """Wipe leftover test rows AND quarantine live 'proposed' candidates so
    process_pending only operates on test-seeded rows.

    process_pending selects `WHERE status='proposed'` with `LIMIT max_batch`
    ordered by proposed_at — if live data has 10+ proposed rows, the seeded
    test row never gets processed. We move live 'proposed' rows to 'rejected'
    before the test (the schema's CHECK constraint only allows
    {'proposed','approved','rejected','ingested'}, so we use one of the
    allowed statuses as a sentinel), then restore at teardown.
    """
    def _clean(conn):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates "
                        "WHERE payload->>'origin' = 'citation_chain_test'")
        conn.commit()

    def _quarantine_live_proposed(conn):
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE harvest.expansion_candidates
                SET status = 'rejected'
                WHERE status = 'proposed'
                  AND (payload->>'origin' IS NULL
                       OR payload->>'origin' != 'citation_chain_test')
                RETURNING id
                """,
            )
            return [r[0] for r in cur.fetchall()]

    def _restore_quarantine(conn, ids):
        if not ids:
            return
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE harvest.expansion_candidates SET status = 'proposed' "
                "WHERE id = ANY(%s) AND status = 'rejected'",
                (ids,),
            )
        conn.commit()

    conn = get_connection()
    try:
        _clean(conn)
        quarantined = _quarantine_live_proposed(conn)
        conn.commit()
        try:
            yield
        finally:
            _restore_quarantine(conn, quarantined)
            _clean(conn)
    finally:
        conn.close()


def _parsed_with_doi(doi: str) -> ParsedDoc:
    return ParsedDoc(
        title="Test paper",
        source_url="https://arxiv.org/abs/test",
        published_date=date(2026, 5, 12),
        rows=[Row(target_table="harvest.document_metadata", data={"title": "Test", "doi": doi})],
        metadata={"doi": doi, "origin": "citation_chain_test"},
    )


def test_enqueue_writes_proposed_candidate(clean_candidates):
    conn = get_connection()
    try:
        chain = CitationChain(conn)
        parsed = _parsed_with_doi("10.1234/test.5678")
        n = chain.enqueue(parsed, parent_run_id=None, parent_doc_id=None)
        assert n == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT kind, status, payload->>'doi', depth FROM harvest.expansion_candidates "
                "WHERE payload->>'origin' = 'citation_chain_test'"
            )
            row = cur.fetchone()
            assert row is not None
            kind, status, doi, depth = row
            assert kind == "paper"
            assert status == "proposed"
            assert doi == "10.1234/test.5678"
            assert depth == 1
    finally:
        conn.close()


def test_enqueue_returns_zero_when_no_doi(clean_candidates):
    """No DOI in parsed.metadata → no candidate enqueued."""
    conn = get_connection()
    try:
        chain = CitationChain(conn)
        parsed = ParsedDoc(
            title="No-DOI paper",
            source_url="https://example.com/x",
            published_date=date(2026, 5, 12),
            rows=[Row(target_table="harvest.document_metadata", data={"title": "x"})],
            metadata={"origin": "citation_chain_test"},
        )
        n = chain.enqueue(parsed, parent_run_id=None, parent_doc_id=None)
        assert n == 0
    finally:
        conn.close()


def test_enqueue_idempotent_on_repeat_call(clean_candidates):
    """Calling enqueue twice for the same DOI → still one candidate (UNIQUE on payload)."""
    conn = get_connection()
    try:
        chain = CitationChain(conn)
        parsed = _parsed_with_doi("10.1234/dup.0001")
        chain.enqueue(parsed, parent_run_id=None, parent_doc_id=None)
        chain.enqueue(parsed, parent_run_id=None, parent_doc_id=None)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.expansion_candidates "
                "WHERE payload->>'origin' = 'citation_chain_test' "
                "AND payload->>'doi' = '10.1234/dup.0001'"
            )
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()


def test_process_pending_promotes_high_score_candidate(clean_candidates):
    """A proposed candidate that Semantic Scholar verifies + LlmTriage scores
    >= threshold gets status='approved'."""
    conn = get_connection()
    try:
        # Seed a proposed candidate
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.expansion_candidates
                    (kind, payload, depth, status)
                VALUES ('paper', %s::jsonb, 1, 'proposed')
                """,
                (json.dumps({"doi": "10.9999/cc_test.proc1", "title": "Verified paper",
                             "origin": "citation_chain_test"}),),
            )
        conn.commit()

        # Mock SemanticScholar lookup + LlmTriage score
        mock_ss = MagicMock()
        mock_ss.get_paper.return_value = {
            "paperId": "ss_abc123",
            "title": "Verified paper",
            "abstract": "We study X.",
            "externalIds": {"DOI": "10.9999/cc_test.proc1"},
        }
        mock_triage = MagicMock()
        mock_triage_result = MagicMock(score=0.72, axes={"x": 0.72},
                                       reason="relevant",
                                       rubric_version="0.3.0",
                                       model_id="claude-sonnet-4-6",
                                       prompt_hash="a"*64)
        mock_triage.score.return_value = mock_triage_result

        chain = CitationChain(conn)
        chain.process_pending(
            max_batch=10,
            ss_fetcher=mock_ss,
            triage=mock_triage,
            threshold=0.4,
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, score FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.proc1'"
            )
            row = cur.fetchone()
            assert row is not None
            status, score = row
            assert status == "approved"
            assert score == pytest.approx(0.72)
    finally:
        conn.close()


def test_process_pending_rejects_low_score(clean_candidates):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.expansion_candidates
                    (kind, payload, depth, status)
                VALUES ('paper', %s::jsonb, 1, 'proposed')
                """,
                (json.dumps({"doi": "10.9999/cc_test.proc2", "title": "Off-topic",
                             "origin": "citation_chain_test"}),),
            )
        conn.commit()

        mock_ss = MagicMock()
        mock_ss.get_paper.return_value = {
            "paperId": "ss_def456",
            "title": "Off-topic",
            "abstract": "A study of moss.",
            "externalIds": {"DOI": "10.9999/cc_test.proc2"},
        }
        mock_triage = MagicMock()
        mock_triage_result = MagicMock(score=0.05, axes={},
                                       reason="off-axis",
                                       rubric_version="0.3.0",
                                       model_id="claude-sonnet-4-6",
                                       prompt_hash="b"*64)
        mock_triage.score.return_value = mock_triage_result

        chain = CitationChain(conn)
        chain.process_pending(
            max_batch=10,
            ss_fetcher=mock_ss,
            triage=mock_triage,
            threshold=0.4,
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, score FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.proc2'"
            )
            row = cur.fetchone()
            assert row is not None
            status, score = row
            assert status == "rejected"
            assert score == pytest.approx(0.05)
    finally:
        conn.close()


def test_process_pending_skips_when_paper_not_found(clean_candidates):
    """SS returns 404 → candidate stays 'proposed' (deferred)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.expansion_candidates
                    (kind, payload, depth, status)
                VALUES ('paper', %s::jsonb, 1, 'proposed')
                """,
                (json.dumps({"doi": "10.9999/cc_test.notfound",
                             "origin": "citation_chain_test"}),),
            )
        conn.commit()

        mock_ss = MagicMock()
        mock_ss.get_paper.return_value = None  # 404
        mock_triage = MagicMock()

        chain = CitationChain(conn)
        chain.process_pending(
            max_batch=10,
            ss_fetcher=mock_ss,
            triage=mock_triage,
            threshold=0.4,
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.notfound'"
            )
            row = cur.fetchone()
            # Stays proposed — we retry next batch (could 404 transiently)
            assert row[0] == "proposed"

        mock_triage.score.assert_not_called()
    finally:
        conn.close()
