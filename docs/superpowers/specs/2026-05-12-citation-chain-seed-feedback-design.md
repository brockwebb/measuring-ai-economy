# Citation-Chain Seed-Feedback Loop — Design

**Status:** draft, awaiting review
**Date:** 2026-05-12
**Parent:** completes the unfinished scope flagged in the Phase 3.2 final code review (PR #1, merge commit `5b6df49`).

## Goal

Wire `SemanticScholarFetcher.get_references()` into the citation-chain machinery so that approved depth-1 candidates produce depth-2 candidates from their reference lists. Decouple expansion from triage so each phase can run independently on its own schedule.

## Why decouple

The Phase 3.2 design folded reference fetching into `process_pending` would have worked but bound triage and expansion together. Decoupled, the operator can:

- Run triage cheaply on Sundays (deterministic, fast, no API budget anxiety).
- Run expansion separately whenever it makes sense (manual button, separate cron, throttled, retried independently).
- Inspect "which approvals haven't been expanded yet" trivially via SQL.
- Throttle expansion separately if the depth-2 queue grows faster than the triage pool can handle.

At expected steady state — 100 approved parents × ~50 refs each = ~5000 depth-2 candidates per cycle — the throttle handle matters.

## Architecture

Two phases on `harvest.expansion_candidates`:

```
proposed ──[process_pending: SS verify + LlmTriage]──► approved / rejected
                                                          │
                                                          ▼
                                                  ┌───────────────┐
                                                  │ expanded_at?  │
                                                  └─────┬─────────┘
                                                        │ NULL
                                                        ▼
              ┌──[expand_approved: SS get_references]──┘
              │
              ▼
   New depth=2 candidates (status='proposed', parent_candidate_id=…)
              │
              ▼ (next Sunday)
   process_pending picks them up like any other depth-1 candidate
```

### Components

**1. Migration 007 — `harvester/harvester/schemas/007_expansion_chain.sql`**

Adds two columns to `harvest.expansion_candidates`:

- `expanded_at TIMESTAMPTZ NULL` — when this approved candidate's references were fetched. `NULL` = never expanded (or never approved).
- `parent_candidate_id BIGINT NULL REFERENCES harvest.expansion_candidates(id) ON DELETE SET NULL` — links a depth-2 candidate back to the approved depth-1 row it descended from. Self-FK; nullable so depth-1 rows can keep it NULL.

Plus a partial index for the expansion query:

```sql
CREATE INDEX IF NOT EXISTS expansion_candidates_unexpanded_idx
    ON harvest.expansion_candidates (score DESC NULLS LAST, proposed_at ASC)
    WHERE status = 'approved' AND expanded_at IS NULL;
```

No backfill needed — both columns are NULL on existing rows by default.

**2. `CitationChain.expand_approved` — new method in `harvester/harvester/improvement/citation_chain.py`**

```python
def expand_approved(
    self,
    *,
    max_parents: int = 50,
    ss_fetcher,
    ref_limit: int = 100,
) -> dict[str, int]:
    """Fetch references for approved-but-not-yet-expanded candidates,
    enqueue each cited paper as a depth-2 'proposed' candidate.
    Returns {parents_expanded, refs_enqueued, refs_skipped_no_doi,
             refs_dedup, deferred}.
    """
```

Selection:
```sql
SELECT id, payload, parent_doc_id
FROM harvest.expansion_candidates
WHERE kind = 'paper'
  AND status = 'approved'
  AND expanded_at IS NULL
ORDER BY score DESC NULLS LAST, proposed_at ASC
LIMIT max_parents
```

For each parent:
1. Pull DOI from `payload`.
2. Call `ss_fetcher.get_references(f"DOI:{doi}", limit=ref_limit)`. If the call raises, count `deferred++`, leave `expanded_at` NULL, continue to next parent (retried next run). If the call returns successfully — including the empty list — treat as a successful expansion: SS doesn't have references for this paper, retrying forever wastes API budget. Stamp `expanded_at` and count refs as appropriate.
3. For each cited paper in the returned list:
   - Skip if no DOI in `externalIds`, count `refs_skipped_no_doi++` (we use DOI as dedup key — refs without one can't be verified later).
   - Build the depth-2 payload: `{doi, title, source_url}` — same shape `enqueue()` uses.
   - INSERT with `kind='paper'`, `depth=2`, `parent_candidate_id=<parent.id>`, `parent_doc_id=<parent.parent_doc_id>` (propagated so the chain root is preserved), `status='proposed'`. Use `ON CONFLICT (kind, payload) DO NOTHING RETURNING id`.
   - Count `refs_enqueued++` if RETURNING produced a row, else `refs_dedup++`.
4. UPDATE the parent: `expanded_at = now()` (only when step 2 succeeded). Count `parents_expanded++`.
5. Commit per parent. Failures per parent don't poison the batch.

Counter semantics:
- `parents_expanded` — parents successfully processed (API call returned, `expanded_at` stamped). Includes parents with zero refs returned.
- `deferred` — parents where the SS call raised; `expanded_at` left NULL for retry.
- `refs_enqueued` — new depth-2 candidates inserted.
- `refs_skipped_no_doi` — refs returned but dropped for lack of DOI.
- `refs_dedup` — refs that conflicted with existing rows.

Error handling: use the same lazy-import pattern `enqueue/process_pending` already use (no fetcher import at module top).

**3. CLI — `harvester chain-references`** (new subcommand)

```python
@app.command("chain-references")
def chain_references_cmd(
    max_parents: int = typer.Option(50, "--max-parents", help="Max approved candidates to expand"),
    ref_limit: int = typer.Option(100, "--ref-limit", help="Max references to pull per parent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print pending count without API calls"),
) -> None:
    """Fetch references for approved candidates, enqueue cited papers
    as depth-2 candidates."""
```

`--dry-run` prints `"DRY RUN: would expand up to N of M approved-but-unexpanded candidates."` without touching SS.

Real run instantiates `SemanticScholarFetcher`, calls `CitationChain.expand_approved`, echoes the result counters.

**4. Launchd — separate from `expand-citations`**

New job `com.wintermute.harvest-chain-references` fires Sundays at 02:45 (15 minutes after `expand-citations` finishes its triage pass). Separate plist + wrapper so the operator can disable expansion independently of triage.

Wrapper at `~/.wintermute/scripts/jobs/harvest_chain_references.sh`, mirrored to `ops/launchd/`.

## Data flow

1. Sunday 02:30 — `expand-citations` cron: SS verifies proposed depth-1 candidates from arxiv, LlmTriage scores them, status → approved/rejected. (Existing behavior.)
2. Sunday 02:45 — `chain-references` cron: for each `status='approved' AND expanded_at IS NULL`, SS fetches references, dedups, enqueues depth-2 as `status='proposed'`, stamps `expanded_at`.
3. Next Sunday 02:30 — `expand-citations` picks up the new depth-2 proposeds along with any new depth-1 from that week's arxiv ingest. Scores them. Approved depth-2 candidates become eligible for `chain-references` the following week (depth-3 if we ever choose to expand them; schema's depth CHECK allows 1-3).
4. Anytime — manual `harvester chain-references --dry-run` shows the backlog; `--max-parents N` fires a partial batch.

## YAGNI / non-goals

- **No depth-3 expansion in this phase.** The schema allows it; the code doesn't drive it. `process_pending` doesn't check depth before promoting, and `expand_approved` doesn't filter by depth. Both already work for arbitrary depth — but we don't enable it until we see the depth-2 graph and decide whether the LlmTriage signal stays useful at that distance.
- **No reference filtering upfront.** All refs with a DOI get enqueued. Triage filters in the next round. (Pre-filtering hides logic that future-us would want to re-run with different criteria.)
- **No multi-parent provenance tracking.** If 5 approved parents all cite the same ref, `UNIQUE (kind, payload)` dedups to one candidate; we don't record the 5 citation paths. The `harvest.co_sources` co-occurrence ledger already tracks cross-source dedup signal; we don't need a second layer for in-chain dedup.
- **No rate-limit special-casing.** The fetcher's existing 1 req/sec self-pacing + 429 backoff covers `get_references` the same way it covers `get_paper`. With an API key, our own quota; without, shared-pool 429s eat the run and `expanded_at` stays NULL — retried next cron.

## Testing

Unit tests in `harvester/tests/test_citation_chain_expand.py`:

1. `test_expand_approved_writes_depth_2_candidates` — seed one approved depth-1 row; mock `ss_fetcher.get_references` returning 3 refs with DOIs; call `expand_approved`; assert 3 depth-2 proposed candidates exist with correct payload + `parent_candidate_id` + `parent_doc_id` propagated + `expanded_at` set on the parent.
2. `test_expand_approved_skips_refs_without_doi` — refs returned with no `externalIds.DOI` are not enqueued; counter `refs_skipped_no_doi` increments; mocked refs include 2 with DOI, 1 without → 2 enqueued.
3. `test_expand_approved_dedups_across_parents` — two approved parents both cite the same ref; first parent's expansion writes the row, second's hits the UNIQUE constraint; counter `refs_dedup` increments; depth-2 candidate count stays at 1.
4. `test_expand_approved_skips_already_expanded` — pre-stamp `expanded_at` on the parent; method does not call `get_references` for it.
5. `test_expand_approved_stamps_on_empty_refs` — `get_references` returns `[]`; `expanded_at` is stamped; `parents_expanded` counter increments; no depth-2 rows written.
6. `test_expand_approved_defers_on_exception` — `get_references` raises (e.g. `httpx.HTTPStatusError`); `expanded_at` stays NULL; counter `deferred` increments; no depth-2 rows written.

CLI test in `harvester/tests/test_cli_chain_references.py`:

7. `test_chain_references_help_lists_command` — subcommand visible in `--help`.
8. `test_chain_references_dry_run_does_not_call_api` — `--dry-run` exits 0, prints "DRY RUN", no SS calls.

Existing test suite must stay 116/116 green.

## Smoke / operational verification

- `harvester chain-references --dry-run` reports 0 of 0 (no approvals yet — pool is empty at merge time).
- After the SS API key lands and one Sunday `expand-citations` run produces approvals, `harvester chain-references --dry-run` should report N of N where N matches `SELECT count(*) FROM harvest.expansion_candidates WHERE status='approved' AND expanded_at IS NULL`.
- Live run of `harvester chain-references --max-parents 1 --ref-limit 5` against a real approved candidate should: insert ≤5 depth-2 rows, stamp `expanded_at` on the parent, echo counters totalling correctly.

## Tasks (approx)

1. Migration 007 — `expanded_at` + `parent_candidate_id` columns + indices.
2. `CitationChain.expand_approved` + 5 unit tests (TDD).
3. `harvester chain-references` CLI + 2 tests.
4. Launchd plist + wrapper for Sundays 02:45.
5. Operational verification on live DB.

~5 small tasks, similar shape to Phase 3.2's mechanical sections. No new dependencies, no new external services.

## Open questions

None blocking. Two minor things to revisit after first live run:

- Does `ref_limit=100` saturate frequently? If approved parents typically cite 30-50 papers, the limit is fine. If some cite 200+, decide whether to fetch all (multiple paginated calls) or accept truncation.
- Is Sunday 02:45 spacing enough buffer from 02:30? If `expand-citations` ever runs long, the two could overlap. Could chain them in one wrapper if it becomes an issue.
