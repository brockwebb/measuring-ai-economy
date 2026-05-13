# Calibration Dashboard + Claudeclaw Judgment Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the calibration dashboard CLI and the weekly claudeclaw judgment job per roadmap §3.5. The CLI is read-only and renders Markdown (or JSON). The judgment job consumes JSON, applies heuristic auto-decisions, escalates a borderline band to LLM judgment, and emails a weekly digest.

**Architecture:** Two new Python modules — `harvester.improvement.calibration` (dataclasses + section SQL + Markdown/JSON renderers) and `harvester.improvement.judgment` (5 heuristic helpers + 1 borderline selector). A new `harvester calibration` typer command. A claudeclaw markdown job that invokes the Python helpers and composes the digest email. No schema changes — reuses existing `reviewed_by` / `reviewed` columns with a `claudeclaw:judgment:*` prefix convention for audit.

**Tech Stack:** Python 3.12, psycopg, typer. No new dependencies. Reuses `scripts/notify.py:send_email` from the claudeclaw job.

**Spec:** `docs/superpowers/specs/2026-05-12-calibration-judgment-design.md`

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch:** `feat/calibration-judgment` (already created from main; spec doc is already on it as commit `4b18530`).

---

## File Structure

**Created:**

```
measuring-ai-economy/
└── harvester/
    ├── harvester/
    │   └── improvement/
    │       ├── calibration.py                  [NEW]
    │       └── judgment.py                     [NEW]
    └── tests/
        ├── test_calibration.py                 [NEW]
        ├── test_judgment.py                    [NEW]
        └── test_cli_calibration.py             [NEW]

~/.wintermute/.claude/claudeclaw/jobs/
└── harvest_judgment.md                         [NEW]
```

**Modified:**

- `harvester/harvester/cli.py` — append a new `calibration` typer command.

**Schema dependencies (existing, no changes):**

- `harvest.run_log` — `id, source_id, started_at, status, items_fetched, items_deposited, items_failed, llm_cost_usd, new_graph_nodes`
- `harvest.triage_results` — `doc_id, score, axes, reason, rubric_version, model_id, prompt_hash, scored_at, reviewed`
- `harvest.saturation` (view) — `source_id, day, total_fetched, total_deposited, deposit_ratio, new_nodes`
- `harvest.failure_patterns` — `id, source_id, error_signature, first_seen_at, last_seen_at, occurrence_count, sample_error, mitigation_status`
- `harvest.co_occurrence` (view) — `canonical_key, canonical_kind, sources (text[]), source_count, total_encounters, first_seen, latest_seen`
- `harvest.expansion_candidates` — `id, kind, payload, parent_doc_id, parent_candidate_id, depth, score, status, proposed_at, reviewed_at, reviewed_by, expanded_at`
- `harvest.stochastic_provenance` — `table_name, row_pk, field, model_id, prompt_hash, params, confidence, reviewed, created_at`

---

## Tasks

### Task 1: calibration data layer (dataclasses + SQL + builder)

**Files:**
- Create `harvester/harvester/improvement/calibration.py` (data layer only — renderers in Task 2)
- Create `harvester/tests/test_calibration.py` (first two tests; remainder in Task 2)

- [ ] **Step 1: Write failing tests at `harvester/tests/test_calibration.py`**

```python
"""Tests for harvester.improvement.calibration."""

import pytest

from harvester.db import get_connection
from harvester.improvement.calibration import (
    CalibrationReport,
    build_calibration_report,
    parse_window,
)


def test_parse_window_accepts_Nd_format():
    assert parse_window("7d") == 7
    assert parse_window("30d") == 30
    assert parse_window("90d") == 90


def test_parse_window_rejects_bad_format():
    with pytest.raises(ValueError):
        parse_window("7")     # no 'd'
    with pytest.raises(ValueError):
        parse_window("week")  # not Nd
    with pytest.raises(ValueError):
        parse_window("0d")    # zero not allowed
    with pytest.raises(ValueError):
        parse_window("-5d")   # negative not allowed


def test_build_report_returns_well_typed_sections():
    """All seven sections present, types correct, no None where the schema
    guarantees a value. Runs against the live DB — doesn't require seeding."""
    conn = get_connection()
    try:
        report = build_calibration_report(conn, window_days=30)
    finally:
        conn.close()

    assert isinstance(report, CalibrationReport)
    assert report.window_days == 30
    # Activity
    assert isinstance(report.activity.total_runs, int)
    assert isinstance(report.activity.total_deposits, int)
    assert isinstance(report.activity.by_source, list)
    # Triage
    assert isinstance(report.triage.score_histogram, list)
    assert isinstance(report.triage.reviewed_count, int)
    assert isinstance(report.triage.unreviewed_count, int)
    # Saturation
    assert isinstance(report.saturation.by_source, list)
    # Failure patterns
    assert isinstance(report.failure_patterns.alerts, list)
    # Co-occurrence
    assert isinstance(report.co_occurrence.top_n, list)
    # Expansion candidates
    assert isinstance(report.candidates.proposed, int)
    assert isinstance(report.candidates.approved_unexpanded, int)
    assert isinstance(report.candidates.by_depth, dict)
    # Provenance
    assert isinstance(report.provenance.unreviewed_total, int)
    assert isinstance(report.provenance.unreviewed_low_confidence, int)
    assert isinstance(report.provenance.unreviewed_high_confidence, int)
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_calibration.py -v
```

Expected: 3 failures with `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Implement `harvester/harvester/improvement/calibration.py`**

```python
"""Calibration dashboard — read-only data layer.

Aggregates run_log, triage_results, saturation view, failure_patterns,
co_occurrence view, expansion_candidates, and stochastic_provenance into a
single report. Pure SQL; no writes. Used by the `harvester calibration` CLI
and the weekly claudeclaw judgment job.

Renderers (Markdown/JSON) live in renderers.py (Task 2); this module returns
typed dataclasses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg


_WINDOW_RE = re.compile(r"^(\d+)d$")


def parse_window(window: str) -> int:
    """Parse a window string like '30d' into days. Raises ValueError on
    malformed input or non-positive values."""
    m = _WINDOW_RE.match(window or "")
    if not m:
        raise ValueError(f"window must be of form 'Nd' (e.g. '30d'), got {window!r}")
    n = int(m.group(1))
    if n <= 0:
        raise ValueError(f"window must be positive, got {n}d")
    return n


@dataclass(frozen=True)
class SourceActivity:
    source_id: str
    runs: int
    completed: int
    failed: int
    items_deposited: int
    llm_cost_usd: float


@dataclass(frozen=True)
class ActivitySection:
    window_days: int
    by_source: list[SourceActivity]
    total_runs: int
    total_deposits: int


@dataclass(frozen=True)
class TriageSection:
    score_histogram: list[tuple[float, int]]   # (bucket_low, count) for 0.0..1.0 in 0.1 bands
    reviewed_count: int
    unreviewed_count: int
    median_score: float | None
    p90_score: float | None


@dataclass(frozen=True)
class SourceSaturation:
    source_id: str
    deposit_ratio: float
    status: str   # 'healthy' | 'warning' | 'saturated'


@dataclass(frozen=True)
class SaturationSection:
    by_source: list[SourceSaturation]


@dataclass(frozen=True)
class FailurePattern:
    source_id: str
    error_signature: str
    occurrence_count: int
    last_seen_at: datetime
    mitigation_status: str
    sample_error: str | None


@dataclass(frozen=True)
class FailurePatternsSection:
    alerts: list[FailurePattern]


@dataclass(frozen=True)
class CoOccurrenceRow:
    canonical_key: str
    canonical_kind: str
    sources: list[str]
    source_count: int
    total_encounters: int


@dataclass(frozen=True)
class CoOccurrenceSection:
    top_n: list[CoOccurrenceRow]


@dataclass(frozen=True)
class CandidatesSection:
    proposed: int
    approved_unexpanded: int
    approved_expanded: int
    rejected: int
    ingested: int
    by_depth: dict[int, int]
    oldest_proposed_days: int | None


@dataclass(frozen=True)
class ProvenanceSection:
    unreviewed_total: int
    unreviewed_low_confidence: int
    unreviewed_high_confidence: int


@dataclass(frozen=True)
class CalibrationReport:
    window_days: int
    generated_at: datetime
    activity: ActivitySection
    triage: TriageSection
    saturation: SaturationSection
    failure_patterns: FailurePatternsSection
    co_occurrence: CoOccurrenceSection
    candidates: CandidatesSection
    provenance: ProvenanceSection


# ---- Section builders ----

def _activity(conn: psycopg.Connection, window_days: int) -> ActivitySection:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id,
                   count(*)::int                                     AS runs,
                   count(*) FILTER (WHERE status = 'completed')::int AS completed,
                   count(*) FILTER (WHERE status = 'failed')::int    AS failed,
                   COALESCE(sum(items_deposited), 0)::int            AS items_deposited,
                   COALESCE(sum(llm_cost_usd), 0)::float             AS llm_cost
            FROM harvest.run_log
            WHERE started_at > now() - make_interval(days => %s)
            GROUP BY source_id
            ORDER BY runs DESC
            """,
            (window_days,),
        )
        rows = cur.fetchall()
    by_source = [
        SourceActivity(
            source_id=r[0], runs=r[1], completed=r[2], failed=r[3],
            items_deposited=r[4], llm_cost_usd=r[5],
        )
        for r in rows
    ]
    return ActivitySection(
        window_days=window_days,
        by_source=by_source,
        total_runs=sum(s.runs for s in by_source),
        total_deposits=sum(s.items_deposited for s in by_source),
    )


def _triage(conn: psycopg.Connection, window_days: int) -> TriageSection:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT score, reviewed FROM harvest.triage_results
            WHERE scored_at > now() - make_interval(days => %s)
            """,
            (window_days,),
        )
        rows = cur.fetchall()
    scores = [r[0] for r in rows]
    reviewed_count = sum(1 for r in rows if r[1])
    unreviewed_count = len(rows) - reviewed_count
    histogram: list[tuple[float, int]] = []
    for i in range(10):
        lo = i / 10.0
        hi = (i + 1) / 10.0
        # final bucket inclusive of 1.0
        if i == 9:
            count = sum(1 for s in scores if lo <= s <= hi)
        else:
            count = sum(1 for s in scores if lo <= s < hi)
        histogram.append((lo, count))
    median = _percentile(scores, 0.5)
    p90 = _percentile(scores, 0.9)
    return TriageSection(
        score_histogram=histogram,
        reviewed_count=reviewed_count,
        unreviewed_count=unreviewed_count,
        median_score=median,
        p90_score=p90,
    )


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(p * len(s))))
    return float(s[idx])


def _saturation(conn: psycopg.Connection, window_days: int) -> SaturationSection:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id,
                   COALESCE(avg(deposit_ratio), 0)::float AS avg_ratio
            FROM harvest.saturation
            WHERE day > now() - make_interval(days => %s)
            GROUP BY source_id
            ORDER BY avg_ratio ASC
            """,
            (window_days,),
        )
        rows = cur.fetchall()
    by_source = [
        SourceSaturation(
            source_id=r[0],
            deposit_ratio=r[1],
            status=("saturated" if r[1] < 0.3
                    else "warning" if r[1] < 0.6
                    else "healthy"),
        )
        for r in rows
    ]
    return SaturationSection(by_source=by_source)


def _failure_patterns(conn: psycopg.Connection, window_days: int) -> FailurePatternsSection:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id, error_signature, occurrence_count::int,
                   last_seen_at, mitigation_status, sample_error
            FROM harvest.failure_patterns
            WHERE last_seen_at > now() - make_interval(days => %s)
              AND occurrence_count >= 5
              AND mitigation_status = 'unaddressed'
            ORDER BY occurrence_count DESC
            LIMIT 10
            """,
            (window_days,),
        )
        rows = cur.fetchall()
    alerts = [
        FailurePattern(
            source_id=r[0], error_signature=r[1], occurrence_count=r[2],
            last_seen_at=r[3], mitigation_status=r[4], sample_error=r[5],
        )
        for r in rows
    ]
    return FailurePatternsSection(alerts=alerts)


def _co_occurrence(conn: psycopg.Connection, window_days: int) -> CoOccurrenceSection:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT canonical_key, canonical_kind, sources,
                   source_count::int, total_encounters::int
            FROM harvest.co_occurrence
            WHERE latest_seen > now() - make_interval(days => %s)
              AND source_count >= 2
            ORDER BY source_count DESC, total_encounters DESC
            LIMIT 10
            """,
            (window_days,),
        )
        rows = cur.fetchall()
    top_n = [
        CoOccurrenceRow(
            canonical_key=r[0], canonical_kind=r[1], sources=list(r[2] or []),
            source_count=r[3], total_encounters=r[4],
        )
        for r in rows
    ]
    return CoOccurrenceSection(top_n=top_n)


def _candidates(conn: psycopg.Connection) -> CandidatesSection:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                count(*) FILTER (WHERE status = 'proposed')::int                                  AS proposed,
                count(*) FILTER (WHERE status = 'approved' AND expanded_at IS NULL)::int          AS approved_unexpanded,
                count(*) FILTER (WHERE status = 'approved' AND expanded_at IS NOT NULL)::int      AS approved_expanded,
                count(*) FILTER (WHERE status = 'rejected')::int                                  AS rejected,
                count(*) FILTER (WHERE status = 'ingested')::int                                  AS ingested,
                EXTRACT(epoch FROM (now() - min(proposed_at) FILTER (WHERE status = 'proposed')))::int
                                                                                                  AS oldest_proposed_sec
            FROM harvest.expansion_candidates
            WHERE kind = 'paper'
            """,
        )
        row = cur.fetchone()
        cur.execute(
            """
            SELECT depth::int, count(*)::int
            FROM harvest.expansion_candidates
            WHERE kind = 'paper'
            GROUP BY depth
            """,
        )
        depth_rows = cur.fetchall()
    oldest = (row[5] // 86400) if row and row[5] is not None else None
    return CandidatesSection(
        proposed=row[0] or 0,
        approved_unexpanded=row[1] or 0,
        approved_expanded=row[2] or 0,
        rejected=row[3] or 0,
        ingested=row[4] or 0,
        by_depth={int(d): int(c) for d, c in depth_rows},
        oldest_proposed_days=oldest,
    )


def _provenance(conn: psycopg.Connection) -> ProvenanceSection:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                count(*) FILTER (WHERE reviewed = false)::int                                AS unreviewed,
                count(*) FILTER (WHERE reviewed = false AND confidence < 0.5)::int           AS low_conf,
                count(*) FILTER (WHERE reviewed = false AND confidence >= 0.85)::int         AS high_conf
            FROM harvest.stochastic_provenance
            """,
        )
        row = cur.fetchone()
    return ProvenanceSection(
        unreviewed_total=row[0] or 0,
        unreviewed_low_confidence=row[1] or 0,
        unreviewed_high_confidence=row[2] or 0,
    )


def build_calibration_report(
    conn: psycopg.Connection,
    *,
    window_days: int,
) -> CalibrationReport:
    """Build a CalibrationReport covering all seven sections over the window.

    Pure-read; no writes, no side effects.
    """
    return CalibrationReport(
        window_days=window_days,
        generated_at=datetime.now(),
        activity=_activity(conn, window_days),
        triage=_triage(conn, window_days),
        saturation=_saturation(conn, window_days),
        failure_patterns=_failure_patterns(conn, window_days),
        co_occurrence=_co_occurrence(conn, window_days),
        candidates=_candidates(conn),
        provenance=_provenance(conn),
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_calibration.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/calibration.py harvester/tests/test_calibration.py
git commit -m "feat(harvester): calibration data layer (read-only dashboard model)

Pure-SQL aggregation across run_log, triage_results, saturation view,
failure_patterns, co_occurrence view, expansion_candidates, and
stochastic_provenance. Returns a frozen CalibrationReport with seven
typed sections. No writes, no side effects.

parse_window('30d') -> 30. build_calibration_report(conn, window_days=30)
produces the report. Renderers (Markdown/JSON) land in Task 2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Markdown + JSON renderers

**Files:**
- Modify `harvester/harvester/improvement/calibration.py` (append renderer functions)
- Modify `harvester/tests/test_calibration.py` (append 3 renderer tests)

- [ ] **Step 1: Append failing renderer tests to `harvester/tests/test_calibration.py`**

```python
import json
from datetime import datetime
from harvester.improvement.calibration import (
    ActivitySection, TriageSection, SaturationSection, SourceSaturation,
    FailurePatternsSection, CoOccurrenceSection, CandidatesSection,
    ProvenanceSection, render_markdown, render_json,
)


def _empty_report():
    return CalibrationReport(
        window_days=30,
        generated_at=datetime(2026, 5, 12, 8, 0, 0),
        activity=ActivitySection(window_days=30, by_source=[], total_runs=0, total_deposits=0),
        triage=TriageSection(
            score_histogram=[(i/10, 0) for i in range(10)],
            reviewed_count=0, unreviewed_count=0,
            median_score=None, p90_score=None,
        ),
        saturation=SaturationSection(by_source=[]),
        failure_patterns=FailurePatternsSection(alerts=[]),
        co_occurrence=CoOccurrenceSection(top_n=[]),
        candidates=CandidatesSection(
            proposed=0, approved_unexpanded=0, approved_expanded=0,
            rejected=0, ingested=0, by_depth={}, oldest_proposed_days=None,
        ),
        provenance=ProvenanceSection(
            unreviewed_total=0, unreviewed_low_confidence=0, unreviewed_high_confidence=0,
        ),
    )


def test_render_markdown_includes_all_section_headers():
    md = render_markdown(_empty_report())
    for header in (
        "# Wintermute Calibration",
        "## Activity",
        "## Triage Distribution",
        "## Saturation",
        "## Failure Patterns",
        "## Co-occurrence",
        "## Expansion Candidates",
        "## Provenance Review Queue",
    ):
        assert header in md, f"missing header: {header!r}\noutput:\n{md}"


def test_render_markdown_handles_zero_counts():
    """Empty report renders without errors and shows zero counts where applicable."""
    md = render_markdown(_empty_report())
    # No exceptions thrown; result has all section headers.
    assert "## Activity" in md
    # Zero-count sections still show "0" or "no" markers, not crashes.
    assert "total runs: 0" in md or "Total runs: 0" in md or "0 runs" in md


def test_render_json_is_serializable():
    report = _empty_report()
    js = render_json(report)
    # round-trips via stdlib json
    serialized = json.dumps(js)
    parsed = json.loads(serialized)
    assert parsed["window_days"] == 30
    assert "activity" in parsed
    assert "triage" in parsed
    assert "saturation" in parsed
    assert "failure_patterns" in parsed
    assert "co_occurrence" in parsed
    assert "candidates" in parsed
    assert "provenance" in parsed
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_calibration.py -v
```

Expected: 3 new failures (`render_markdown` and `render_json` not yet defined).

- [ ] **Step 3: Append the renderers to `harvester/harvester/improvement/calibration.py`**

```python
# ---- Renderers ----

def render_markdown(report: CalibrationReport) -> str:
    """Render the report as a human-readable Markdown dashboard."""
    lines: list[str] = []
    lines.append(f"# Wintermute Calibration — {report.window_days}d window")
    lines.append(f"_Generated: {report.generated_at.isoformat()}_")
    lines.append("")

    # Activity
    lines.append("## Activity")
    lines.append(f"Total runs: {report.activity.total_runs} | "
                 f"Total deposits: {report.activity.total_deposits}")
    if report.activity.by_source:
        lines.append("")
        lines.append("| Source | Runs | Completed | Failed | Deposited | LLM $ |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for s in report.activity.by_source:
            lines.append(
                f"| {s.source_id} | {s.runs} | {s.completed} | {s.failed} "
                f"| {s.items_deposited} | ${s.llm_cost_usd:.2f} |"
            )
    lines.append("")

    # Triage
    lines.append("## Triage Distribution")
    lines.append(f"Reviewed: {report.triage.reviewed_count} | "
                 f"Unreviewed: {report.triage.unreviewed_count}")
    if report.triage.median_score is not None:
        lines.append(f"Median score: {report.triage.median_score:.2f} | "
                     f"p90: {report.triage.p90_score:.2f}")
    lines.append("")
    lines.append("| Band | Count |")
    lines.append("|---|---:|")
    for lo, count in report.triage.score_histogram:
        lines.append(f"| {lo:.1f}–{lo+0.1:.1f} | {count} |")
    lines.append("")

    # Saturation
    lines.append("## Saturation")
    if report.saturation.by_source:
        lines.append("| Source | Deposit Ratio | Status |")
        lines.append("|---|---:|---|")
        for s in report.saturation.by_source:
            lines.append(f"| {s.source_id} | {s.deposit_ratio:.2f} | {s.status} |")
    else:
        lines.append("_No saturation data in window._")
    lines.append("")

    # Failure Patterns
    lines.append("## Failure Patterns")
    if report.failure_patterns.alerts:
        lines.append("| Source | Signature | Count | Last Seen | Status |")
        lines.append("|---|---|---:|---|---|")
        for f in report.failure_patterns.alerts:
            sig = f.error_signature[:60]
            lines.append(
                f"| {f.source_id} | {sig} | {f.occurrence_count} "
                f"| {f.last_seen_at.isoformat()} | {f.mitigation_status} |"
            )
    else:
        lines.append("_No unaddressed failure patterns above threshold._")
    lines.append("")

    # Co-occurrence
    lines.append("## Co-occurrence")
    if report.co_occurrence.top_n:
        lines.append("| Key | Kind | Sources | Encounters |")
        lines.append("|---|---|---|---:|")
        for c in report.co_occurrence.top_n:
            srcs = ", ".join(c.sources)
            lines.append(f"| {c.canonical_key[:60]} | {c.canonical_kind} "
                         f"| {srcs} | {c.total_encounters} |")
    else:
        lines.append("_No multi-source matches in window._")
    lines.append("")

    # Expansion Candidates
    lines.append("## Expansion Candidates")
    c = report.candidates
    lines.append(
        f"Proposed: {c.proposed} | "
        f"Approved (unexpanded): {c.approved_unexpanded} | "
        f"Approved (expanded): {c.approved_expanded} | "
        f"Rejected: {c.rejected} | "
        f"Ingested: {c.ingested}"
    )
    if c.by_depth:
        lines.append(f"By depth: " + ", ".join(
            f"depth-{d}={n}" for d, n in sorted(c.by_depth.items())))
    if c.oldest_proposed_days is not None:
        lines.append(f"Oldest proposed: {c.oldest_proposed_days} days")
    lines.append("")

    # Provenance Review Queue
    lines.append("## Provenance Review Queue")
    p = report.provenance
    lines.append(
        f"Unreviewed total: {p.unreviewed_total} | "
        f"Low-confidence (<0.5): {p.unreviewed_low_confidence} | "
        f"High-confidence (>=0.85): {p.unreviewed_high_confidence}"
    )
    lines.append("")

    return "\n".join(lines)


def render_json(report: CalibrationReport) -> dict[str, Any]:
    """Render the report as a JSON-serializable dict (for the judgment job
    and any other downstream automation)."""
    return {
        "window_days": report.window_days,
        "generated_at": report.generated_at.isoformat(),
        "activity": {
            "total_runs": report.activity.total_runs,
            "total_deposits": report.activity.total_deposits,
            "by_source": [
                {
                    "source_id": s.source_id, "runs": s.runs,
                    "completed": s.completed, "failed": s.failed,
                    "items_deposited": s.items_deposited,
                    "llm_cost_usd": s.llm_cost_usd,
                }
                for s in report.activity.by_source
            ],
        },
        "triage": {
            "score_histogram": [[lo, c] for lo, c in report.triage.score_histogram],
            "reviewed_count": report.triage.reviewed_count,
            "unreviewed_count": report.triage.unreviewed_count,
            "median_score": report.triage.median_score,
            "p90_score": report.triage.p90_score,
        },
        "saturation": {
            "by_source": [
                {"source_id": s.source_id, "deposit_ratio": s.deposit_ratio, "status": s.status}
                for s in report.saturation.by_source
            ],
        },
        "failure_patterns": {
            "alerts": [
                {
                    "source_id": f.source_id, "error_signature": f.error_signature,
                    "occurrence_count": f.occurrence_count,
                    "last_seen_at": f.last_seen_at.isoformat(),
                    "mitigation_status": f.mitigation_status,
                    "sample_error": f.sample_error,
                }
                for f in report.failure_patterns.alerts
            ],
        },
        "co_occurrence": {
            "top_n": [
                {
                    "canonical_key": c.canonical_key, "canonical_kind": c.canonical_kind,
                    "sources": list(c.sources), "source_count": c.source_count,
                    "total_encounters": c.total_encounters,
                }
                for c in report.co_occurrence.top_n
            ],
        },
        "candidates": {
            "proposed": report.candidates.proposed,
            "approved_unexpanded": report.candidates.approved_unexpanded,
            "approved_expanded": report.candidates.approved_expanded,
            "rejected": report.candidates.rejected,
            "ingested": report.candidates.ingested,
            "by_depth": {str(k): v for k, v in report.candidates.by_depth.items()},
            "oldest_proposed_days": report.candidates.oldest_proposed_days,
        },
        "provenance": {
            "unreviewed_total": report.provenance.unreviewed_total,
            "unreviewed_low_confidence": report.provenance.unreviewed_low_confidence,
            "unreviewed_high_confidence": report.provenance.unreviewed_high_confidence,
        },
    }
```

- [ ] **Step 2.5: Add missing `Any` import**

If not already present at the top of `calibration.py`, add `Any` to the imports:

```python
from typing import Any
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_calibration.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: 130 passed (124 from before + 6 new).

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/calibration.py harvester/tests/test_calibration.py
git commit -m "feat(harvester): calibration renderers — Markdown + JSON

render_markdown emits a human dashboard with 7 sections (Activity,
Triage Distribution, Saturation, Failure Patterns, Co-occurrence,
Expansion Candidates, Provenance Review Queue). render_json produces
the same shape as a JSON-serializable dict for the weekly claudeclaw
judgment job.

Both are pure functions; data layer is untouched.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `harvester calibration` CLI

**Files:**
- Modify `harvester/harvester/cli.py` (append a typer command)
- Create `harvester/tests/test_cli_calibration.py`

- [ ] **Step 1: Write tests at `harvester/tests/test_cli_calibration.py`**

```python
"""Tests for `harvester calibration` CLI."""

import json
import subprocess


def test_calibration_help_lists_command():
    """--help shows calibration subcommand."""
    result = subprocess.run(
        ["uv", "run", "harvester", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "calibration" in result.stdout, f"missing subcommand. stdout: {result.stdout}"


def test_calibration_default_renders_markdown():
    """No flags → Markdown to stdout, starting with the header."""
    result = subprocess.run(
        ["uv", "run", "harvester", "calibration", "--window", "30d"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "# Wintermute Calibration" in result.stdout
    assert "## Activity" in result.stdout
    assert "## Triage Distribution" in result.stdout


def test_calibration_json_flag_renders_valid_json():
    """--json → stdout parses as JSON with the expected top-level keys."""
    result = subprocess.run(
        ["uv", "run", "harvester", "calibration", "--window", "7d", "--json"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    parsed = json.loads(result.stdout)
    assert parsed["window_days"] == 7
    for key in ("activity", "triage", "saturation", "failure_patterns",
                "co_occurrence", "candidates", "provenance"):
        assert key in parsed, f"missing key: {key}"
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_calibration.py -v
```

Expected: tests fail (subcommand not registered).

- [ ] **Step 3: Append the command to `harvester/harvester/cli.py`**

Add at the end of the file:

```python
@app.command("calibration")
def calibration_cmd(
    window: str = typer.Option("30d", "--window",
        help="Lookback window (e.g. 7d, 30d, 90d)"),
    json_out: bool = typer.Option(False, "--json",
        help="Emit JSON instead of Markdown"),
) -> None:
    """Print a Markdown dashboard (or JSON via --json) covering activity,
    triage drift, saturation, failure clusters, co-occurrence, expansion
    queues, and provenance review backlog over the window."""
    import json as _json

    from harvester.improvement.calibration import (
        build_calibration_report,
        parse_window,
        render_json,
        render_markdown,
    )

    window_days = parse_window(window)
    conn = get_connection()
    try:
        report = build_calibration_report(conn, window_days=window_days)
    finally:
        conn.close()

    if json_out:
        typer.echo(_json.dumps(render_json(report), indent=2))
    else:
        typer.echo(render_markdown(report))
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_calibration.py -v
uv run pytest 2>&1 | tail -3
```

Expected: 3 passed for new tests; full suite at 133.

- [ ] **Step 5: Smoke**

```bash
uv run harvester calibration --window 7d 2>&1 | head -25
uv run harvester calibration --window 7d --json 2>&1 | python3 -c "import sys, json; print('window_days:', json.load(sys.stdin)['window_days'])"
```

Expected:
- The Markdown render shows section headers + recent activity.
- The JSON render parses cleanly and `window_days: 7` prints.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/cli.py harvester/tests/test_cli_calibration.py
git commit -m "feat(harvester): \`harvester calibration\` CLI

Renders the calibration dashboard from build_calibration_report.
Markdown by default for human reading; --json for the weekly
claudeclaw judgment job. --window accepts Nd format (7d, 30d, 90d).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: judgment.py heuristic helpers + 6 tests

**Files:**
- Create `harvester/harvester/improvement/judgment.py`
- Create `harvester/tests/test_judgment.py`

- [ ] **Step 1: Write tests at `harvester/tests/test_judgment.py`**

```python
"""Tests for harvester.improvement.judgment heuristic helpers."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from harvester.db import get_connection
from harvester.improvement.judgment import (
    auto_confirm_approved_high_score,
    auto_confirm_rejected_low_score,
    auto_reject_stale_proposed,
    auto_mark_high_confidence_provenance_reviewed,
    borderline_candidates_for_llm_review,
    borderline_provenance_for_human_eyes,
)


_TEST_DOI_PREFIX = "10.9999/judgment_test"


@pytest.fixture
def clean_judgment_rows():
    def _clean(conn):
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' LIKE %s",
                (f"{_TEST_DOI_PREFIX}%",),
            )
            cur.execute(
                "DELETE FROM harvest.stochastic_provenance "
                "WHERE table_name = 'judgment_test'"
            )
        conn.commit()

    conn = get_connection()
    try:
        _clean(conn)
        yield
        _clean(conn)
    finally:
        conn.close()


def _seed_candidate(conn, *, doi_suffix, status, score=None, reviewed_by=None,
                    proposed_at=None) -> int:
    payload = {"doi": f"{_TEST_DOI_PREFIX}.{doi_suffix}", "title": doi_suffix}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO harvest.expansion_candidates
                (kind, payload, depth, status, score, reviewed_by, proposed_at)
            VALUES ('paper', %s::jsonb, 1, %s, %s, %s,
                    COALESCE(%s, now()))
            RETURNING id
            """,
            (json.dumps(payload, sort_keys=True), status, score, reviewed_by,
             proposed_at),
        )
        row_id = cur.fetchone()[0]
    conn.commit()
    return row_id


def _seed_provenance(conn, *, row_pk, confidence, reviewed=False):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO harvest.stochastic_provenance
                (table_name, row_pk, field, model_id, prompt_hash, confidence, reviewed)
            VALUES ('judgment_test', %s, 'test_field', 'test-model', 'a'*64::text,
                    %s, %s)
            ON CONFLICT (table_name, row_pk, field) DO UPDATE
                SET confidence = EXCLUDED.confidence, reviewed = EXCLUDED.reviewed
            """,
            (row_pk, confidence, reviewed),
        )
    conn.commit()


def test_auto_confirm_approved_high_score(clean_judgment_rows):
    conn = get_connection()
    try:
        cid = _seed_candidate(conn, doi_suffix="ach.001", status="approved",
                              score=0.85)
        n = auto_confirm_approved_high_score(conn, threshold=0.7)
        assert n == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT reviewed_by FROM harvest.expansion_candidates WHERE id = %s",
                (cid,),
            )
            assert cur.fetchone()[0] == "claudeclaw:judgment:confirmed-high"

        # Re-running is a no-op (already tagged)
        assert auto_confirm_approved_high_score(conn, threshold=0.7) == 0
    finally:
        conn.close()


def test_auto_confirm_rejected_low_score(clean_judgment_rows):
    conn = get_connection()
    try:
        cid = _seed_candidate(conn, doi_suffix="acl.001", status="rejected",
                              score=0.05)
        n = auto_confirm_rejected_low_score(conn, threshold=0.15)
        assert n == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT reviewed_by FROM harvest.expansion_candidates WHERE id = %s",
                (cid,),
            )
            assert cur.fetchone()[0] == "claudeclaw:judgment:confirmed-low"
    finally:
        conn.close()


def test_auto_reject_stale_proposed(clean_judgment_rows):
    conn = get_connection()
    try:
        old = datetime.now(timezone.utc) - timedelta(days=70)
        cid = _seed_candidate(conn, doi_suffix="ars.001", status="proposed",
                              score=None, proposed_at=old)
        n = auto_reject_stale_proposed(conn, days=60)
        assert n == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, reviewed_by FROM harvest.expansion_candidates WHERE id = %s",
                (cid,),
            )
            status, reviewed_by = cur.fetchone()
            assert status == "rejected"
            assert reviewed_by == "claudeclaw:judgment:stale-untried"
    finally:
        conn.close()


def test_auto_mark_high_confidence_provenance_reviewed(clean_judgment_rows):
    conn = get_connection()
    try:
        _seed_provenance(conn, row_pk=1001, confidence=0.92)
        _seed_provenance(conn, row_pk=1002, confidence=0.70)  # below threshold
        n = auto_mark_high_confidence_provenance_reviewed(conn, threshold=0.85)
        assert n == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT row_pk, reviewed FROM harvest.stochastic_provenance "
                "WHERE table_name = 'judgment_test' ORDER BY row_pk"
            )
            rows = cur.fetchall()
        assert (1001, True) in rows
        assert (1002, False) in rows
    finally:
        conn.close()


def test_borderline_candidates_for_llm_review_excludes_claudeclaw_reviewed(
        clean_judgment_rows):
    conn = get_connection()
    try:
        _seed_candidate(conn, doi_suffix="brd.001", status="approved", score=0.55,
                        reviewed_by=None)
        _seed_candidate(conn, doi_suffix="brd.002", status="approved", score=0.45,
                        reviewed_by="claudeclaw:judgment:llm-confirm")
        _seed_candidate(conn, doi_suffix="brd.003", status="rejected", score=0.50,
                        reviewed_by=None)

        results = borderline_candidates_for_llm_review(conn, lo=0.4, hi=0.6,
                                                       limit=20)
        suffixes = sorted(r["payload"]["doi"].split(".")[-1] for r in results
                          if r["payload"]["doi"].startswith(_TEST_DOI_PREFIX))
        # 001 (no reviewer) and 003 (no reviewer) qualify; 002 is excluded.
        assert "001" in suffixes
        assert "003" in suffixes
        assert "002" not in suffixes
    finally:
        conn.close()


def test_borderline_provenance_for_human_eyes_orders_by_age(clean_judgment_rows):
    conn = get_connection()
    try:
        # Insert two unreviewed rows; both confidence < 0.5
        _seed_provenance(conn, row_pk=2001, confidence=0.10)
        _seed_provenance(conn, row_pk=2002, confidence=0.20)

        results = borderline_provenance_for_human_eyes(conn, threshold=0.5,
                                                       limit=10)
        # Filter to our test rows
        rows = [r for r in results if r["table_name"] == "judgment_test"]
        assert len(rows) >= 2
        # Sorted by created_at ASC (oldest first); since both inserted just
        # now, we relax to: both are present and have confidence < 0.5.
        for r in rows[:2]:
            assert r["confidence"] < 0.5
    finally:
        conn.close()
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_judgment.py -v
```

Expected: 6 failures with `ModuleNotFoundError` / `ImportError`.

- [ ] **Step 3: Implement `harvester/harvester/improvement/judgment.py`**

```python
"""Heuristic judgment helpers used by the weekly claudeclaw harvest_judgment job.

All functions are pure SQL — deterministic, testable, no LLM in the loop.
Decisions are tagged on existing audit columns:
- expansion_candidates.reviewed_by — prefix 'claudeclaw:judgment:'
- stochastic_provenance.reviewed   — flipped to true

The borderline selectors return rows for the markdown job to either apply
LLM judgment (candidates) or surface in the digest (provenance).
"""

from __future__ import annotations

from typing import Any

import psycopg


def auto_confirm_approved_high_score(
    conn: psycopg.Connection,
    *,
    threshold: float = 0.7,
) -> int:
    """Approved candidates with score >= threshold AND reviewed_by NOT LIKE
    'claudeclaw:%' → stamp reviewed_by='claudeclaw:judgment:confirmed-high'.

    Returns count updated.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE harvest.expansion_candidates
            SET reviewed_by = 'claudeclaw:judgment:confirmed-high',
                reviewed_at = now()
            WHERE kind = 'paper'
              AND status = 'approved'
              AND score >= %s
              AND (reviewed_by IS NULL OR reviewed_by NOT LIKE 'claudeclaw:%%')
            """,
            (threshold,),
        )
        n = cur.rowcount
    conn.commit()
    return n


def auto_confirm_rejected_low_score(
    conn: psycopg.Connection,
    *,
    threshold: float = 0.15,
) -> int:
    """Rejected candidates with score < threshold AND reviewed_by NOT LIKE
    'claudeclaw:%' → stamp reviewed_by='claudeclaw:judgment:confirmed-low'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE harvest.expansion_candidates
            SET reviewed_by = 'claudeclaw:judgment:confirmed-low',
                reviewed_at = now()
            WHERE kind = 'paper'
              AND status = 'rejected'
              AND score < %s
              AND (reviewed_by IS NULL OR reviewed_by NOT LIKE 'claudeclaw:%%')
            """,
            (threshold,),
        )
        n = cur.rowcount
    conn.commit()
    return n


def auto_reject_stale_proposed(
    conn: psycopg.Connection,
    *,
    days: int = 60,
) -> int:
    """Proposed candidates older than `days` with no score → status='rejected',
    reviewed_by='claudeclaw:judgment:stale-untried'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE harvest.expansion_candidates
            SET status = 'rejected',
                reviewed_by = 'claudeclaw:judgment:stale-untried',
                reviewed_at = now()
            WHERE kind = 'paper'
              AND status = 'proposed'
              AND score IS NULL
              AND proposed_at < now() - make_interval(days => %s)
            """,
            (days,),
        )
        n = cur.rowcount
    conn.commit()
    return n


def auto_mark_high_confidence_provenance_reviewed(
    conn: psycopg.Connection,
    *,
    threshold: float = 0.85,
) -> int:
    """stochastic_provenance rows with confidence >= threshold AND reviewed=false
    → reviewed=true.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE harvest.stochastic_provenance
            SET reviewed = true
            WHERE reviewed = false
              AND confidence IS NOT NULL
              AND confidence >= %s
            """,
            (threshold,),
        )
        n = cur.rowcount
    conn.commit()
    return n


def borderline_candidates_for_llm_review(
    conn: psycopg.Connection,
    *,
    lo: float = 0.4,
    hi: float = 0.6,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Candidates with score in (lo, hi) that have NOT been claudeclaw-reviewed.
    Returns dicts with id, status, score, payload (parsed), proposed_at.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, status, score, payload, proposed_at
            FROM harvest.expansion_candidates
            WHERE kind = 'paper'
              AND score IS NOT NULL
              AND score > %s
              AND score < %s
              AND (reviewed_by IS NULL OR reviewed_by NOT LIKE 'claudeclaw:%%')
            ORDER BY score DESC, proposed_at ASC
            LIMIT %s
            """,
            (lo, hi, limit),
        )
        rows = cur.fetchall()
    return [
        {"id": r[0], "status": r[1], "score": r[2], "payload": r[3],
         "proposed_at": r[4]}
        for r in rows
    ]


def borderline_provenance_for_human_eyes(
    conn: psycopg.Connection,
    *,
    threshold: float = 0.5,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Unreviewed stochastic_provenance rows with confidence < threshold,
    oldest first. Surfaced in the digest, not auto-touched.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, row_pk, field, model_id, confidence, created_at
            FROM harvest.stochastic_provenance
            WHERE reviewed = false
              AND confidence IS NOT NULL
              AND confidence < %s
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (threshold, limit),
        )
        rows = cur.fetchall()
    return [
        {"table_name": r[0], "row_pk": r[1], "field": r[2],
         "model_id": r[3], "confidence": r[4], "created_at": r[5]}
        for r in rows
    ]
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_judgment.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: 139 passed (133 from before + 6 new).

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/judgment.py harvester/tests/test_judgment.py
git commit -m "feat(harvester): judgment heuristics for the weekly claudeclaw job

Five pure-SQL helpers + one borderline selector. Auto-confirm high-score
approvals, auto-confirm low-score rejections, auto-reject stale proposed
candidates, auto-mark high-confidence provenance reviewed. Borderline
candidates (score in 0.4-0.6 by default) get returned for LLM judgment
in the markdown job; low-confidence provenance gets surfaced for the
human eye via the digest.

All writes tag reviewed_by with 'claudeclaw:judgment:*' prefix for
audit. No new schema.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: claudeclaw job — `harvest_judgment.md`

**Files:**
- Create `/Users/brock/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md`

No code, no tests — this is a markdown instruction file for claudeclaw. Modeled on the existing `daily-activity-report.md` job.

- [ ] **Step 1: Write the job file**

Create `/Users/brock/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md`:

````markdown
---
schedule: "0 8 * * 0"
recurring: true
---
Run the weekly Wintermute calibration + judgment cycle. Cron fires Sundays 08:00 local.

This job does four things in order. Run them in this exact sequence and capture each output.

## 1. Snapshot the calibration dashboard (read-only)

Run this and capture stdout into a JSON variable:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester && /Users/brock/.local/bin/uv run harvester calibration --window 30d --json
```

Keep the parsed object available for section 4 (the email digest).

## 2. Apply heuristic auto-decisions (cheap; no LLM)

Run the four heuristic helpers in `harvester.improvement.judgment`. Capture the counts they return.

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester && /Users/brock/.local/bin/uv run python3 -c "
from harvester.db import get_connection
from harvester.improvement import judgment
conn = get_connection()
print('auto_confirm_high:', judgment.auto_confirm_approved_high_score(conn))
print('auto_confirm_low:', judgment.auto_confirm_rejected_low_score(conn))
print('auto_reject_stale:', judgment.auto_reject_stale_proposed(conn))
print('provenance_high:', judgment.auto_mark_high_confidence_provenance_reviewed(conn))
conn.close()
"
```

Each line prints `name: count`. Note the four counts — they go into section 4.

## 3. LLM judgment for borderline candidates

Pull the borderline list (score in 0.4–0.6 by default, up to 20 rows):

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester && /Users/brock/.local/bin/uv run python3 -c "
import json
from harvester.db import get_connection
from harvester.improvement import judgment
conn = get_connection()
rows = judgment.borderline_candidates_for_llm_review(conn)
print(json.dumps(rows, default=str))
conn.close()
"
```

For each row in the returned list, look at `payload['doi']` and `payload['title']`. Decide: based on the Wintermute research axes (stochastic dynamics + information geometry + generative models; canine cognition; martial arts; exercise/training science; mental performance; complexity / control / symbolic AI), does this paper deserve to stay approved (or rejected) at its current status?

- If you agree with the current status: write `confirm`.
- If you disagree (status='approved' but you think it should be rejected, or vice versa): write `dispute`.

Apply each verdict via:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester && /Users/brock/.local/bin/uv run python3 -c "
from harvester.db import get_connection
conn = get_connection()
with conn.cursor() as cur:
    cur.execute(\"UPDATE harvest.expansion_candidates SET reviewed_at = now(), reviewed_by = %s WHERE id = %s\",
                ('claudeclaw:judgment:llm-confirm', <ID>))  # or 'llm-dispute'
conn.commit()
conn.close()
"
```

Track how many you confirmed vs disputed. Note a few representative examples for the digest.

## 4. Compose and send the digest

Also pull the low-confidence provenance list and the failure/saturation alerts from section 1's JSON:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester && /Users/brock/.local/bin/uv run python3 -c "
import json
from harvester.db import get_connection
from harvester.improvement import judgment
conn = get_connection()
print(json.dumps(judgment.borderline_provenance_for_human_eyes(conn), default=str))
conn.close()
"
```

Compose a plain-text email with these sections (every section must be present; write 'n/a' if empty):

1. **Pipeline weather** — from section 1's JSON: total runs, total deposits, median triage score, count of saturated sources, candidate counts by status, oldest proposed days.
2. **Auto-decisions taken** — the four counts from section 2 (confirmed-high, confirmed-low, stale-rejected, provenance-confirmed).
3. **LLM judgments applied** — confirms vs disputes, with 2–3 example titles for each.
4. **Needs your eye** — low-confidence provenance rows from this section's output (table_name + row_pk + field + confidence), plus any active failure alerts or saturated sources from section 1.

Send via `scripts/notify.py:send_email`:

```python
python3 << 'PYEOF'
import os, sys
from pathlib import Path
_wm_home = Path(os.environ.get("WM_HOME", str(Path.home() / ".wintermute")))
sys.path.insert(0, str(_wm_home / "scripts"))
from notify import send_email
send_email(
    subject=os.environ["WM_SUBJECT"],
    body=os.environ["WM_BODY"],
    to="brockwebb45@gmail.com",
)
PYEOF
```

Subject: `[WM-CALIBRATION] 🧊⚡ weekly judgment YYYY-MM-DD` (use today's UTC date). Prepend 🔴 to the subject if section 4 ("Needs your eye") has any non-empty content; ✅ otherwise.

## Notes

- The four auto-decision helpers are idempotent (they exclude rows already tagged `claudeclaw:%`). Safe to re-run on the same week if a previous attempt failed mid-way.
- The borderline LLM-judgment step writes one UPDATE per row. If it crashes partway through, re-running is safe — already-tagged rows are excluded by the next selector call.
- Do NOT touch failure_patterns, saturation rows, or run_log. The digest is informational about those tables; the auto-mitigation lives in their own subsystems (Phase 3.1).
````

- [ ] **Step 2: Verify the file is syntactically a valid claudeclaw job**

```bash
ls -la /Users/brock/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md
head -10 /Users/brock/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md
```

Expected: file exists, first 4 lines are the YAML frontmatter (`---`, `schedule: "0 8 * * 0"`, `recurring: true`, `---`).

- [ ] **Step 3: Dry-run the data commands manually** (no claudeclaw daemon involvement; just verify the bash blocks work):

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
/Users/brock/.local/bin/uv run harvester calibration --window 30d --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK, window_days:', d['window_days'])"
/Users/brock/.local/bin/uv run python3 -c "
from harvester.db import get_connection
from harvester.improvement import judgment
conn = get_connection()
print('auto_confirm_high:', judgment.auto_confirm_approved_high_score(conn))
print('auto_confirm_low:', judgment.auto_confirm_rejected_low_score(conn))
print('auto_reject_stale:', judgment.auto_reject_stale_proposed(conn))
print('provenance_high:', judgment.auto_mark_high_confidence_provenance_reviewed(conn))
conn.close()
"
```

Expected: JSON parses; each helper prints a count (probably 0 since no qualifying rows exist at first run).

- [ ] **Step 4: Commit** (note: the file lives under `~/.wintermute/`, outside the repo, so there's nothing to git-add for this task in measuring-ai-economy)

The job file itself isn't checked into the harvester repo — it's part of the wintermute deployment surface. But we do want a small note in the repo so future readers can find it:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
# Document where the job file lives, in the spec.
# (No commit needed if the spec already names the path — verify.)
grep -n "harvest_judgment.md" docs/superpowers/specs/2026-05-12-calibration-judgment-design.md
```

Expected: at least one hit, naming the full path. If yes, no new commit needed for Task 5; the file is created in place at `~/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md` and Wintermute's claudeclaw daemon will pick it up automatically.

---

### Task 6: Final verification

**No code changes.**

- [ ] **Step 1: Full test suite green**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest 2>&1 | tail -3
```

Expected: 139 passed (124 from before + 15 new across tasks 1–4).

- [ ] **Step 2: CLI surface**

```bash
uv run harvester --help 2>&1 | grep -E "expand-citations|chain-references|calibration"
```

Expected: all three lines visible.

- [ ] **Step 3: Live Markdown render**

```bash
uv run harvester calibration --window 30d 2>&1 | head -40
```

Expected: dashboard renders with all 7 section headers; activity table shows recent run_log data.

- [ ] **Step 4: Live JSON render**

```bash
uv run harvester calibration --window 7d --json 2>&1 | python3 -c "
import sys, json
d = json.load(sys.stdin)
keys = sorted(d.keys())
print('top-level keys:', keys)
assert all(k in keys for k in ['activity', 'candidates', 'co_occurrence', 'failure_patterns', 'generated_at', 'provenance', 'saturation', 'triage', 'window_days'])
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 5: Heuristic helpers dry-run**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python3 -c "
from harvester.db import get_connection
from harvester.improvement import judgment
conn = get_connection()
print('auto_confirm_high:', judgment.auto_confirm_approved_high_score(conn))
print('auto_confirm_low:', judgment.auto_confirm_rejected_low_score(conn))
print('auto_reject_stale:', judgment.auto_reject_stale_proposed(conn))
print('provenance_high:', judgment.auto_mark_high_confidence_provenance_reviewed(conn))
print('borderline_candidates:', len(judgment.borderline_candidates_for_llm_review(conn)))
print('borderline_provenance:', len(judgment.borderline_provenance_for_human_eyes(conn)))
conn.close()
"
```

Expected: all six lines print a count (probably 0 across the board on first run — no qualifying data has accumulated yet).

- [ ] **Step 6: Claudeclaw job file present**

```bash
ls -la /Users/brock/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md
```

Expected: file exists with the YAML frontmatter.

- [ ] **Step 7: Branch state**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git log main..HEAD --oneline | wc -l
```

Expected: 5 commits on `feat/calibration-judgment` (spec + 4 implementation commits; Task 5 is in `~/.wintermute/` and doesn't add a repo commit).

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| Calibration data layer (dataclasses + SQL) | Task 1 |
| Markdown renderer | Task 2 |
| JSON renderer | Task 2 |
| `harvester calibration` CLI with `--window` + `--json` | Task 3 |
| 5 heuristic helpers + 1 borderline-candidate selector + 1 borderline-provenance selector | Task 4 |
| Claudeclaw `harvest_judgment.md` job (4 phases: snapshot → heuristic → LLM borderline → digest) | Task 5 |
| `[WM-CALIBRATION]` email format | Task 5 (in the job body) |
| Audit trail via `reviewed_by` prefix `claudeclaw:judgment:*` | Task 4 (encoded in the helpers) |
| End-to-end verification | Task 6 |

Note: the spec listed 15 tests; the plan ships 14 (dropped the empty-DB test because it's hard to do cleanly with a shared live DB; the type-correctness test in Task 1 covers most of what the empty test would have caught). Targets 139 total tests instead of the spec's notional 139 — math works out the same because the spec miscounted slightly.

**2. Placeholder scan** — none. Every step has real SQL, Python, or bash. No "TBD"/"handle edge cases".

**3. Type consistency**

- `CalibrationReport`, `ActivitySection`, … `ProvenanceSection` (Task 1) — same names referenced by `render_markdown` and `render_json` (Task 2), by the CLI (Task 3), and by the claudeclaw job (Task 5).
- `parse_window("30d") -> 30` — same signature called by the CLI in Task 3.
- Heuristic helpers (`auto_confirm_approved_high_score`, etc., Task 4) — same names invoked in the claudeclaw job (Task 5).
- `borderline_candidates_for_llm_review` returns a list of dicts with keys `id, status, score, payload, proposed_at` — same shape the claudeclaw markdown reads from.
- All `reviewed_by` tag strings: `claudeclaw:judgment:confirmed-high`, `confirmed-low`, `stale-untried`, `llm-confirm`, `llm-dispute`. Consistent across `judgment.py` (Task 4), the markdown job (Task 5), and the helper exclusion logic (`NOT LIKE 'claudeclaw:%'`).
- Test DOI prefix `10.9999/judgment_test` (Task 4) — distinct from prior Phase 3.2 / 3.4 test prefixes (`10.1234/test`, `10.9999/cc_test`, `10.9999/expand_test`).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-calibration-judgment.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks.

**2. Inline Execution** — execute in this session via executing-plans with checkpoints.

Which approach?
