"""Citation chain expansion.

Two modes:
- enqueue() — synchronous. Called from the runner post-ETL. Writes a proposed
  candidate to harvest.expansion_candidates for each parent paper with a DOI.
  Cheap: no network calls.
- process_pending() — asynchronous. Called by a weekly launchd job. Picks the
  top N proposed candidates, verifies via Semantic Scholar API + scores against
  research_axes via LlmTriage, promotes to approved/rejected. (Implemented in
  Task 7.)

Approved candidates feed back into the harvester as new seeds (future work —
the seed-feedback loop is its own follow-on plan; for 3.2 MVP, approved
candidates sit in the table for human / claudeclaw review.)
"""

from __future__ import annotations

import json

import psycopg

from harvester.types import ParsedDoc


class CitationChain:
    """Cross-source citation expansion machinery."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def enqueue(
        self,
        parsed: ParsedDoc,
        *,
        parent_run_id: int | None,
        parent_doc_id: int | None,
    ) -> int:
        """Queue a citation-expansion candidate for this paper.

        Returns count of candidates added (0 or 1). Idempotent via the
        UNIQUE (kind, payload) constraint on expansion_candidates.
        """
        doi = (parsed.metadata or {}).get("doi")
        if not doi:
            return 0

        payload = {
            "doi": doi,
            "title": parsed.title,
            "source_url": parsed.source_url,
        }
        # Preserve any extra "origin" or context the caller wants tracked
        if origin := (parsed.metadata or {}).get("origin"):
            payload["origin"] = origin

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.expansion_candidates
                    (kind, payload, parent_doc_id, depth, status)
                VALUES ('paper', %s::jsonb, %s, 1, 'proposed')
                ON CONFLICT (kind, payload) DO NOTHING
                RETURNING id
                """,
                (json.dumps(payload, sort_keys=True), parent_doc_id),
            )
            row = cur.fetchone()
        self._conn.commit()
        return 1 if row else 0
