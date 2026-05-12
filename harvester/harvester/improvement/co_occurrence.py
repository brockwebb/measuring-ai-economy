"""Cross-source co-occurrence ledger.

When a URL deposited under one source_id is encountered by a different source_id,
the runner records a row in harvest.co_sources before skipping. Builds the
cross-source salience signal: high co_occurrence_count = same content seen
multiple places independently = important.

MVP scope: URL-based matching only (canonical_kind='url'). Content-hash and DOI
matching are out of 3.1 — they need a partial parse before the skip decision and
add measurable cost; we'll add them in a follow-up if the URL signal isn't
sufficient.
"""

from __future__ import annotations

import psycopg


def find_other_source_for_url(
    conn: psycopg.Connection,
    *,
    current_source: str,
    source_url: str,
) -> str | None:
    """Return the source_id of an existing deposit for source_url, IF that
    source_id is different from current_source. Otherwise None."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id FROM harvest.fetched_items
            WHERE item_id = %s AND status = 'deposited' AND source_id != %s
            ORDER BY fetched_at DESC LIMIT 1
            """,
            (source_url, current_source),
        )
        row = cur.fetchone()
        return row[0] if row else None


class CoOccurrenceLedger:
    """Persists cross-source sightings into harvest.co_sources."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def record_url(
        self,
        *,
        canonical_url: str,
        source_id: str,
        source_url: str,
    ) -> None:
        """Upsert a URL-keyed co-occurrence row. Idempotent via UNIQUE constraint."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.co_sources
                    (canonical_key, canonical_kind, source_id, source_url)
                VALUES (%s, 'url', %s, %s)
                ON CONFLICT (canonical_key, source_id, source_url) DO NOTHING
                """,
                (canonical_url, source_id, source_url),
            )
        self._conn.commit()
