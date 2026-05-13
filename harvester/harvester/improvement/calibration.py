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
