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

            try:
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
            except Exception:
                # Per-candidate isolation: a single SS error, subprocess.TimeoutExpired
                # from a hung Claude triage, or any other transient must NOT take down
                # the whole batch. Leave the row as 'proposed' for retry.
                self._conn.rollback()
                deferred += 1
                continue

        return {"approved": approved, "rejected": rejected, "deferred": deferred}

    def expand_approved(
        self,
        *,
        max_parents: int = 50,
        ss_fetcher,
        ref_limit: int = 100,
    ) -> dict[str, int]:
        """Fetch references for approved-but-not-yet-expanded candidates,
        enqueue each cited paper (with a DOI) as a depth-2 'proposed' candidate.

        For each approved parent with expanded_at IS NULL:
        1. Pull DOI from payload.
        2. Call ss_fetcher.get_references(f"DOI:{doi}", limit=ref_limit).
           - Raises: deferred++, expanded_at stays NULL, retried next run.
           - Returns (even []): stamp expanded_at, parents_expanded++.
        3. For each cited paper with a DOI, INSERT a depth-2 candidate with
           parent_candidate_id and propagated parent_doc_id. UNIQUE(kind, payload)
           dedups across parents.

        Returns {parents_expanded, refs_enqueued, refs_skipped_no_doi,
                 refs_dedup, deferred}.
        """
        parents_expanded = 0
        refs_enqueued = 0
        refs_skipped_no_doi = 0
        refs_dedup = 0
        deferred = 0

        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, payload, parent_doc_id
                FROM harvest.expansion_candidates
                WHERE kind = 'paper'
                  AND status = 'approved'
                  AND expanded_at IS NULL
                ORDER BY score DESC NULLS LAST, proposed_at ASC
                LIMIT %s
                """,
                (max_parents,),
            )
            parents = cur.fetchall()

        for parent_id, payload, parent_doc_id in parents:
            doi = (payload or {}).get("doi")
            if not doi:
                # Approved without a DOI shouldn't happen (enqueue requires one),
                # but if it does, stamp so we don't loop on it.
                with self._conn.cursor() as cur:
                    cur.execute(
                        "UPDATE harvest.expansion_candidates "
                        "SET expanded_at = now() WHERE id = %s",
                        (parent_id,),
                    )
                self._conn.commit()
                parents_expanded += 1
                continue

            try:
                refs = ss_fetcher.get_references(f"DOI:{doi}", limit=ref_limit)
            except Exception:
                self._conn.rollback()
                deferred += 1
                continue

            for ref in refs:
                external_ids = ref.get("externalIds") if isinstance(ref, dict) else None
                ref_doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None
                if not ref_doi:
                    refs_skipped_no_doi += 1
                    continue
                ref_payload = {
                    "doi": ref_doi,
                    "title": ref.get("title"),
                    "source_url": f"https://www.semanticscholar.org/paper/{ref.get('paperId', '')}",
                }
                with self._conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO harvest.expansion_candidates
                            (kind, payload, parent_doc_id, parent_candidate_id,
                             depth, status)
                        VALUES ('paper', %s::jsonb, %s, %s, 2, 'proposed')
                        ON CONFLICT (kind, payload) DO NOTHING
                        RETURNING id
                        """,
                        (
                            json.dumps(ref_payload, sort_keys=True),
                            parent_doc_id,
                            parent_id,
                        ),
                    )
                    inserted = cur.fetchone()
                if inserted:
                    refs_enqueued += 1
                else:
                    refs_dedup += 1

            with self._conn.cursor() as cur:
                cur.execute(
                    "UPDATE harvest.expansion_candidates "
                    "SET expanded_at = now() WHERE id = %s",
                    (parent_id,),
                )
            self._conn.commit()
            parents_expanded += 1

        return {
            "parents_expanded": parents_expanded,
            "refs_enqueued": refs_enqueued,
            "refs_skipped_no_doi": refs_skipped_no_doi,
            "refs_dedup": refs_dedup,
            "deferred": deferred,
        }
