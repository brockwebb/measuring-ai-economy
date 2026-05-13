"""Tests for harvester.improvement.calibration."""

import json
from datetime import datetime

import pytest

from harvester.db import get_connection
from harvester.improvement.calibration import (
    ActivitySection,
    CalibrationReport,
    CandidatesSection,
    CoOccurrenceSection,
    FailurePatternsSection,
    ProvenanceSection,
    SaturationSection,
    SourceSaturation,
    TriageSection,
    build_calibration_report,
    parse_window,
    render_json,
    render_markdown,
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
