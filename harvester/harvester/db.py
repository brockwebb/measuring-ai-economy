"""Postgres connection and advisory lock helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg


def _dsn() -> str:
    """Return the postgres DSN.

    Defaults to the wintermute db on the local Postgres.app socket. Override
    via HARVESTER_PG_DSN environment variable.
    """
    return os.environ.get(
        "HARVESTER_PG_DSN",
        "postgresql:///wintermute",
    )


def get_connection() -> psycopg.Connection:
    """Open a new postgres connection. Caller owns lifecycle."""
    return psycopg.connect(_dsn())


@contextmanager
def with_advisory_lock(conn: psycopg.Connection, key: str) -> Iterator[None]:
    """Acquire a session-level advisory lock keyed by hashtext(key).

    Blocks until the lock is available. Released on context exit.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(hashtext(%s))", (key,))
    try:
        yield
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (key,))
        conn.commit()
