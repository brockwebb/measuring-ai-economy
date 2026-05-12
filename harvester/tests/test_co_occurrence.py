"""Tests for the co-occurrence ledger."""

import pytest

from harvester.db import get_connection
from harvester.improvement.co_occurrence import (
    CoOccurrenceLedger,
    find_other_source_for_url,
)


@pytest.fixture
def clean_co_sources():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.co_sources WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id IN ('co_a', 'co_b')")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.co_sources WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id IN ('co_a', 'co_b')")
        conn.commit()
    finally:
        conn.close()


def test_find_other_source_returns_none_when_no_prior_deposit(clean_co_sources):
    conn = get_connection()
    try:
        result = find_other_source_for_url(conn, current_source="co_a",
                                            source_url="https://example.com/x")
        assert result is None
    finally:
        conn.close()


def test_find_other_source_returns_existing_source(clean_co_sources):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status) "
                "VALUES ('https://example.com/x', 'co_a', 'deposited')"
            )
        conn.commit()
        result = find_other_source_for_url(conn, current_source="co_b",
                                            source_url="https://example.com/x")
        assert result == "co_a"
    finally:
        conn.close()


def test_find_other_source_ignores_same_source(clean_co_sources):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status) "
                "VALUES ('https://example.com/x', 'co_a', 'deposited')"
            )
        conn.commit()
        result = find_other_source_for_url(conn, current_source="co_a",
                                            source_url="https://example.com/x")
        assert result is None
    finally:
        conn.close()


def test_ledger_records_co_occurrence(clean_co_sources):
    conn = get_connection()
    try:
        ledger = CoOccurrenceLedger(conn)
        ledger.record_url(canonical_url="https://example.com/x",
                          source_id="co_b",
                          source_url="https://example.com/x")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT canonical_kind, source_id FROM harvest.co_sources "
                "WHERE canonical_key = 'https://example.com/x'"
            )
            row = cur.fetchone()
            assert row is not None
            kind, source = row
            assert kind == "url"
            assert source == "co_b"
    finally:
        conn.close()


def test_ledger_record_is_idempotent(clean_co_sources):
    conn = get_connection()
    try:
        ledger = CoOccurrenceLedger(conn)
        ledger.record_url(canonical_url="https://example.com/x",
                          source_id="co_b",
                          source_url="https://example.com/x")
        ledger.record_url(canonical_url="https://example.com/x",
                          source_id="co_b",
                          source_url="https://example.com/x")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.co_sources "
                "WHERE canonical_key = 'https://example.com/x' AND source_id = 'co_b'"
            )
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()
