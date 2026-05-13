# Calibration Dashboard + Claudeclaw Judgment Job — Design

**Status:** draft, awaiting review
**Date:** 2026-05-12
**Roadmap link:** `docs/superpowers/notes/phase3-roadmap.md` §3.5

## Goal

Close the human-in-loop review cycle on the wintermute pipeline. Two artifacts:

1. **`harvester calibration --window 30d`** — a deterministic CLI that aggregates the relevant Phase 2–3.3 tables into a single Markdown dashboard (or JSON for downstream consumers). Pure data layer; no LLM, no writes.
2. **`~/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md`** — a weekly claudeclaw job that consumes the dashboard, applies heuristic auto-decisions for confident cases, uses claudeclaw's LLM context for borderline ones, writes back SQL updates, and emails a digest.

## Why this shape

The roadmap explicitly says the calibration CLI is "used by both human + the claudeclaw job as the data source." Splitting the layers gives us:

- A deterministic, testable data source. The dashboard is what it is regardless of LLM weather.
- A judgment layer that can be re-prompted or re-tuned without touching SQL.
- Manual operability — I can run `harvester calibration` anytime to see what the system thinks. The judgment digest is a weekly cadence on top of that.

Rubric stability (weekly 20-doc re-score) is **explicitly deferred** to its own spec — it's a complete sub-system (drift detection, comparison across rubric_version), not a section of the dashboard.

## Architecture

```
       ┌─────────────────────────────────────────────────────────┐
       │                  harvest.* tables                       │
       │  run_log │ triage_results │ saturation (view) │         │
       │  failure_patterns │ co_occurrence (view) │              │
       │  expansion_candidates │ stochastic_provenance           │
       └────────────────────────────┬────────────────────────────┘
                                    │ SELECT
                                    ▼
                  ┌────────────────────────────────┐
                  │  harvester calibration CLI     │
                  │  --window 30d [--json]         │
                  │  (read-only; no writes)        │
                  └──────┬─────────────────────┬───┘
                         │                     │
            Markdown stdout                    JSON stdout
                         │                     │
                  ┌──────▼────┐         ┌──────▼──────────────┐
                  │  human    │         │  claudeclaw         │
                  │  reading  │         │  harvest_judgment   │
                  └───────────┘         │  Sundays 08:00      │
                                        └──────┬──────────────┘
                                               │ heuristic + LLM
                                               ▼
                                ┌──────────────────────────┐
                                │  SQL UPDATES (audit-     │
                                │  tagged reviewed_by) +   │
                                │  [WM-CALIBRATION] email  │
                                └──────────────────────────┘
```

### Components

**1. `harvester.improvement.calibration` — data layer**

New module at `harvester/harvester/improvement/calibration.py`. Pure SQL queries against the existing schema. No new migration needed; all referenced columns already exist (verified against `\d` output during design).

Each section is a function returning a typed dataclass:

```python
@dataclass(frozen=True)
class ActivitySection:
    window_days: int
    by_source: list[SourceActivity]   # source_id, runs, completed, failed, items_deposited, llm_cost
    total_runs: int
    total_deposits: int

@dataclass(frozen=True)
class TriageSection:
    score_histogram: list[tuple[float, int]]   # (bucket_low, count) for 0.0–1.0 in 0.1 bands
    reviewed_count: int
    unreviewed_count: int
    median_score: float | None
    p90_score: float | None

@dataclass(frozen=True)
class SaturationSection:
    by_source: list[SourceSaturation]   # source_id, deposit_ratio, status (healthy|warning|saturated)

@dataclass(frozen=True)
class FailurePatternsSection:
    alerts: list[FailurePattern]   # patterns above alert_threshold

@dataclass(frozen=True)
class CoOccurrenceSection:
    top_n: list[CoOccurrenceRow]   # canonical_key, sources[], source_count, total_encounters

@dataclass(frozen=True)
class CandidatesSection:
    proposed: int
    approved_unexpanded: int
    approved_expanded: int
    rejected: int
    by_depth: dict[int, int]
    oldest_proposed_days: int | None

@dataclass(frozen=True)
class ProvenanceSection:
    unreviewed_total: int
    unreviewed_low_confidence: int    # confidence < 0.5
    unreviewed_high_confidence: int   # confidence >= 0.85
```

A top-level `build_calibration_report(conn, *, window_days: int) -> CalibrationReport` calls each section, returns a frozen aggregate.

A `render_markdown(report) -> str` formats it. A `render_json(report) -> dict` does the JSON variant. Both are pure functions, easy to unit-test.

**2. CLI — `harvester calibration`**

```python
@app.command("calibration")
def calibration_cmd(
    window: str = typer.Option("30d", "--window", help="Lookback (e.g. 7d, 30d, 90d)"),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of Markdown"),
) -> None:
    """Print a Markdown dashboard (or JSON) covering activity, triage drift,
    saturation, failure clusters, co-occurrence, expansion queues, and
    provenance review backlog over the window."""
```

`--window` accepts `Nd` format (`7d`, `30d`, `90d`); parsed to int via a small helper. Other formats are rejected with a clear error. No `--source` filter in this phase (YAGNI; the dashboard is small enough to read whole).

**3. Heuristic judgment helpers — `harvester.improvement.judgment`**

A small module exposing SQL-driven decision routines that the claudeclaw job can run. Keeping these in Python (not inline SQL in the markdown job) means they're testable. Each function takes a conn, applies a single rule, returns a count.

```python
def auto_confirm_approved_high_score(conn, *, threshold: float = 0.7) -> int:
    """Approved candidates where process_pending's score >= threshold AND
    reviewed_by NOT LIKE 'claudeclaw:%' → stamp reviewed_by='claudeclaw:judgment:confirmed-high'.
    Returns count updated."""

def auto_confirm_rejected_low_score(conn, *, threshold: float = 0.15) -> int:
    """Rejected candidates with score < threshold AND reviewed_by NOT LIKE
    'claudeclaw:%' → stamp reviewed_by='claudeclaw:judgment:confirmed-low'."""

def auto_reject_stale_proposed(conn, *, days: int = 60) -> int:
    """Proposed candidates with no score AND proposed_at < now() - interval
    → status='rejected', reviewed_by='claudeclaw:judgment:stale-untried'."""

def auto_mark_high_confidence_provenance_reviewed(conn, *, threshold: float = 0.85) -> int:
    """stochastic_provenance rows with confidence >= threshold AND
    reviewed = false → reviewed = true. (No reviewed_by column on this table.)"""

def borderline_candidates_for_llm_review(conn, *, lo: float = 0.4, hi: float = 0.6,
                                          limit: int = 20) -> list[dict]:
    """Return candidates with score in (lo, hi) that haven't been
    claudeclaw-reviewed. The claudeclaw job applies LLM judgment to these and
    decides confirm/dispute via separate UPDATE."""

def borderline_provenance_for_human_eyes(conn, *, threshold: float = 0.5,
                                          limit: int = 10) -> list[dict]:
    """Return stochastic_provenance rows with confidence < threshold AND
    reviewed = false, oldest first. Surfaces in digest but no auto-write."""
```

These are deterministic SQL; tests are normal psycopg fixtures.

**4. Claudeclaw job — `~/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md`**

```yaml
---
schedule: "0 8 * * 0"
recurring: true
---
```

The body (markdown prose) instructs claudeclaw to:

1. Run `uv run harvester calibration --window 30d --json` (capture output).
2. Run the auto-confirm and auto-reject heuristics by calling the Python helpers (subprocess or inline `python3 -c`). Capture counts.
3. For the borderline_candidates list, claudeclaw reads each one's payload (DOI, title) and applies LLM judgment: confirm or dispute the existing score. Apply the decision via UPDATE: `reviewed_by='claudeclaw:judgment:llm-confirm'` or `'claudeclaw:judgment:llm-dispute'`.
4. Compose an email with sections:
   - **Auto-decisions taken** (counts per heuristic)
   - **LLM judgments applied** (count + sample of confirms / disputes)
   - **Needs your eye** (low-confidence provenance + any saturation/failure alerts)
   - **Pipeline weather** (key numbers from the calibration report — deposit volume, score distribution drift, saturation status)
5. Send via `scripts/notify.py:send_email(subject="[WM-CALIBRATION] 🧊⚡ weekly judgment YYYY-MM-DD", to="brockwebb45@gmail.com")` — same pattern as `daily-activity-report.md`.

Job runs Sunday 08:00 local (well after the chain-references 02:45 cron + buffer for any long-running ingest).

**5. Audit trail**

No new schema. We tag claudeclaw's writes via existing columns:

- `expansion_candidates.reviewed_by` — prefix `claudeclaw:judgment:` for traceability. Existing schema field.
- `stochastic_provenance.reviewed` — flipped to `true` (no `reviewed_by` field on this table; YAGNI to add one).

If we need richer audit later (e.g., "show me everything claudeclaw decided in the last month"), the prefix lets us recover it: `WHERE reviewed_by LIKE 'claudeclaw:judgment:%' AND reviewed_at > now() - interval '30 days'`.

## Data flow

1. Sunday 02:30 — `expand-citations` triages depth-1 + depth-2 proposeds (existing).
2. Sunday 02:45 — `chain-references` expands new approvals into depth-2 candidates (existing, just shipped).
3. Sunday 08:00 — `harvest_judgment` claudeclaw job:
   - `harvester calibration --window 30d --json` → JSON
   - Run auto-confirm + auto-reject heuristics (cheap SQL, no LLM)
   - For each borderline candidate, apply LLM judgment + UPDATE
   - Compose + send `[WM-CALIBRATION]` digest email
4. Anytime — `harvester calibration` for the human eye.

## YAGNI / non-goals

- **No rubric stability** — deferred to its own spec (re-scoring 20 docs with the current rubric, comparing distribution shapes, is a separate concern from "what's in the queue right now").
- **No new audit columns** — the existing `reviewed_by` + `reviewed_at` carry enough provenance for now. If the pattern matures, we can add a dedicated `judgment_log` table.
- **No `--source` filter on calibration** — the dashboard is short; reading the whole thing is fine. If it grows, add later.
- **No alerts/Slack/PagerDuty hooks** — `[WM-CALIBRATION]` email is the existing channel. Daily activity report already uses this convention.
- **No depth-3 escalation in the judgment job** — depth-2 candidates flow through normal `process_pending` next week; the judgment job doesn't special-case them.
- **No dispute resolution** — if claudeclaw disputes a score, it stamps `llm-dispute` and surfaces in the digest. Human picks it up from there. No re-scoring loop (that's rubric_stability's job).

## Testing

Unit tests in `harvester/tests/test_calibration.py`:

1. `test_window_parser_accepts_Nd_format` — `"7d"` → 7, `"30d"` → 30, `"90d"` → 90. `"7"` (no `d`) → raises. `"week"` → raises.
2. `test_build_report_returns_all_sections` — given a seeded DB with at least 1 row per relevant table, all 7 sections are populated, no None where the schema guarantees a value.
3. `test_build_report_handles_empty_db` — given a clean DB, sections render with zero counts and empty lists, no exceptions.
4. `test_render_markdown_includes_all_section_headers` — Markdown output has `## Activity`, `## Triage Distribution`, `## Saturation`, `## Failure Patterns`, `## Co-occurrence`, `## Expansion Candidates`, `## Provenance Review Queue` headers.
5. `test_render_json_is_serializable` — `json.dumps(render_json(report))` succeeds; round-trips with `json.loads`.
6. `test_render_markdown_matches_golden_sample` — render against a small fixed DB state and compare to checked-in `tests/fixtures/calibration/expected_30d.md`. Regen helper provided.

Unit tests in `harvester/tests/test_judgment.py`:

7. `test_auto_confirm_approved_high_score` — seed an approved candidate with score 0.85 + reviewed_by NULL; helper stamps `claudeclaw:judgment:confirmed-high`; rerunning is a no-op.
8. `test_auto_confirm_rejected_low_score` — analogous for rejected/low.
9. `test_auto_reject_stale_proposed` — seed a proposed candidate with proposed_at = now() - interval '70 days' AND score IS NULL; helper sets status='rejected' + reviewed_by='stale-untried'.
10. `test_auto_mark_high_confidence_provenance_reviewed` — seed unreviewed row with confidence=0.9; helper flips reviewed=true.
11. `test_borderline_candidates_for_llm_review_excludes_claudeclaw_reviewed` — rows already tagged `claudeclaw:judgment:*` are not returned.
12. `test_borderline_provenance_for_human_eyes_orders_by_age` — oldest first.

CLI test in `harvester/tests/test_cli_calibration.py`:

13. `test_calibration_help_lists_command` — subcommand visible.
14. `test_calibration_default_renders_markdown` — stdout starts with `# Wintermute Calibration` (or similar top-level header) and contains `## Activity`.
15. `test_calibration_json_flag_renders_valid_json` — stdout parses as JSON, has top-level `window_days` key.

Total: 15 tests. Targets 139 passing (124 from before + 15 new).

Smoke test for the claudeclaw job: run it manually in dry-mode (skip the email send) and inspect the would-be subject/body. No automated CI for the LLM step; verified by the digest itself the first Sunday it fires.

## Implementation order (5 tasks)

1. `calibration.py` module (dataclasses + SQL queries + render_markdown + render_json) + 6 tests.
2. `harvester calibration` CLI + 3 tests + golden-sample fixture.
3. `judgment.py` module (5 heuristic helpers + 1 LLM-borderline selector) + 6 tests.
4. `harvest_judgment.md` claudeclaw job file with full instructions to claudeclaw, including the exact UPDATE SQL templates it uses (see below).
5. Final verification: full suite green, dry-run the calibration CLI, dry-run the judgment job manually.

No launchd plist — claudeclaw schedules its own jobs via the YAML frontmatter, picked up by the running daemon.

### UPDATE SQL templates (claudeclaw uses these verbatim)

To prevent the markdown job from drifting into ad-hoc SQL, the heuristic helpers in `judgment.py` are the authoritative source. The job invokes them like:

```bash
python3 -c "
import sys
sys.path.insert(0, '/Users/brock/Documents/GitHub/measuring-ai-economy/harvester')
from harvester.db import get_connection
from harvester.improvement import judgment
conn = get_connection()
print('auto_confirm_high:', judgment.auto_confirm_approved_high_score(conn))
print('auto_confirm_low:', judgment.auto_confirm_rejected_low_score(conn))
print('auto_reject_stale:', judgment.auto_reject_stale_proposed(conn))
print('provenance_high:', judgment.auto_mark_high_confidence_provenance_reviewed(conn))
"
```

For the LLM-borderline path, claudeclaw runs `judgment.borderline_candidates_for_llm_review(conn)` to fetch a list, reads each row's payload, then for each one runs (inline; not a helper because the verdict is LLM-specific):

```sql
UPDATE harvest.expansion_candidates
SET reviewed_at = now(),
    reviewed_by = %s   -- 'claudeclaw:judgment:llm-confirm' or 'claudeclaw:judgment:llm-dispute'
WHERE id = %s
```

The `reviewed_by` string is the only thing that varies per row. This keeps claudeclaw's SQL surface minimal and predictable.

## Open questions

None blocking. Two to revisit after first live run:

- **Heuristic thresholds (0.7, 0.15, 0.85, 60 days)** — picked from intuition. After 4–6 weeks of digests, tune based on observed false-positive / false-negative rates.
- **Borderline band width (0.4–0.6)** — if too few candidates land here, the LLM judgment never fires. If too many, claudeclaw burns context. Re-tune after seeing real numbers.
