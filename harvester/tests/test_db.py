import pytest
import psycopg
from harvester.db import get_connection, with_advisory_lock


def test_get_connection_returns_live_psycopg_connection():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()


def test_advisory_lock_acquires_and_releases():
    conn = get_connection()
    try:
        with with_advisory_lock(conn, "test_source"):
            # Verify the lock is held by attempting a non-blocking acquisition from another connection
            other = get_connection()
            try:
                with other.cursor() as cur:
                    cur.execute(
                        "SELECT pg_try_advisory_lock(hashtext(%s))",
                        ("test_source",),
                    )
                    got_lock = cur.fetchone()[0]
                    assert got_lock is False, "second acquisition should fail while first holds"
                    if got_lock:  # defensive cleanup if assertion logic ever changes
                        cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", ("test_source",))
            finally:
                other.close()
    finally:
        conn.close()
