"""Tests for CitationChain (enqueue mode only — process_pending tested in Task 7)."""

import json

import pytest

from harvester.db import get_connection
from harvester.improvement.citation_chain import CitationChain
from harvester.types import ParsedDoc, Row
from datetime import date


@pytest.fixture
def clean_candidates():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates "
                        "WHERE payload->>'origin' = 'citation_chain_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates "
                        "WHERE payload->>'origin' = 'citation_chain_test'")
        conn.commit()
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
