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

    def process_pending(
        self,
        *,
        max_batch: int = 100,
        ss_fetcher,
        triage,
        threshold: float = 0.4,
    ) -> dict[str, int]:
        """Process up to max_batch proposed candidates.

        For each:
        1. Look up by DOI via ss_fetcher.get_paper("DOI:{doi}"). If 404, leave
           as 'proposed' (transient).
        2. Build a ParsedDoc-like input for triage and score via triage.score().
        3. Promote to 'approved' if score >= threshold, else 'rejected'. Record
           the score.

        ss_fetcher: a SemanticScholarFetcher (passed in for test mockability).
        triage: an LlmTriage (also passed in).
        Returns counts: {approved, rejected, deferred}.
        """
        from datetime import date as _date

        from harvester.types import ParsedDoc, Row

        approved = 0
        rejected = 0
        deferred = 0

        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, payload FROM harvest.expansion_candidates
                WHERE kind = 'paper' AND status = 'proposed'
                ORDER BY score DESC NULLS LAST, proposed_at ASC
                LIMIT %s
                """,
                (max_batch,),
            )
            rows = cur.fetchall()

        for candidate_id, payload in rows:
            doi = payload.get("doi")
            if not doi:
                deferred += 1
                continue

            # 1. Verify via Semantic Scholar
            ss_paper = ss_fetcher.get_paper(f"DOI:{doi}")
            if ss_paper is None:
                deferred += 1
                continue

            # 2. Score via LlmTriage
            title = ss_paper.get("title") or payload.get("title") or ""
            abstract = ss_paper.get("abstract") or ""
            parsed = ParsedDoc(
                title=title,
                source_url=f"https://www.semanticscholar.org/paper/{ss_paper.get('paperId', '')}",
                published_date=_date.today(),
                rows=[],
                metadata={"abstract": abstract},
            )
            tr = triage.score(parsed)

            # 3. Promote or reject
            new_status = "approved" if tr.score >= threshold else "rejected"
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE harvest.expansion_candidates
                    SET status = %s,
                        score = %s,
                        reviewed_at = now(),
                        reviewed_by = %s
                    WHERE id = %s
                    """,
                    (new_status, tr.score, f"citation_chain:{tr.model_id}", candidate_id),
                )
            self._conn.commit()

            if new_status == "approved":
                approved += 1
            else:
                rejected += 1

        return {"approved": approved, "rejected": rejected, "deferred": deferred}
