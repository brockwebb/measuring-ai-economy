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
