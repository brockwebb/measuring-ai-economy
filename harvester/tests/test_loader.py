"""Tests for the postgres row Loader."""

import pytest

from harvester.db import get_connection
from harvester.loader import Loader
from harvester.types import Row


@pytest.fixture
def clean_documents_table():
    """Ensure document_metadata is empty before/after each test."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'loader_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'loader_test'")
        conn.commit()
    finally:
        conn.close()


def test_loader_writes_row_to_target_table(clean_documents_table):
    conn = get_connection()
    try:
        loader = Loader(conn)
        loader.load(
            [
                Row(
                    target_table="harvest.document_metadata",
                    data={
                        "source_id": "loader_test",
                        "title": "Test Document",
                        "source_url": "https://example.com/test",
                    },
                )
            ],
            run_id=None,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title FROM harvest.document_metadata WHERE source_id = 'loader_test'"
            )
            assert cur.fetchone()[0] == "Test Document"
    finally:
        conn.close()


def test_loader_stamps_created_by_run_id(clean_documents_table):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.run_log (source_id, status) VALUES ('loader_test', 'running') RETURNING id"
            )
            run_id = cur.fetchone()[0]
        conn.commit()

        loader = Loader(conn)
        loader.load(
            [
                Row(
                    target_table="harvest.document_metadata",
                    data={
                        "source_id": "loader_test",
                        "title": "Stamped",
                        "source_url": "https://example.com/stamped",
                    },
                )
            ],
            run_id=run_id,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT created_by_run_id FROM harvest.document_metadata WHERE source_id = 'loader_test'"
            )
            assert cur.fetchone()[0] == run_id
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'loader_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE id = %s", (run_id,))
        conn.commit()
    finally:
        conn.close()
