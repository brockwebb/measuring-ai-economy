"""Tests for the Federal Register precision/coverage validator.

The validator runs nightly via launchd. These tests pin the alert logic
(precision rate vs threshold, fetcher-loss detection) without exercising
the real HTTP/DB calls.
"""

from __future__ import annotations

from harvester.scripts.validate_count import _build_report


GTE = "2026-04-18"
LTE = "2026-05-18"


def test_above_threshold_does_not_alert():
    subject, body, alerted = _build_report(
        gte=GTE, lte=LTE, total=100, matched=50, upstream_sum=200, threshold=0.30
    )
    assert alerted is False
    assert "50.0%" in body
    assert "OK" in subject


def test_below_threshold_alerts():
    subject, body, alerted = _build_report(
        gte=GTE, lte=LTE, total=294, matched=6, upstream_sum=401, threshold=0.30
    )
    assert alerted is True
    assert "2.0%" in body
    assert "below threshold" in subject
    assert "30%" in subject


def test_zero_deposits_with_upstream_traffic_alerts_fetcher_loss():
    subject, body, alerted = _build_report(
        gte=GTE, lte=LTE, total=0, matched=0, upstream_sum=42, threshold=0.30
    )
    assert alerted is True
    assert "fetcher loss" in subject
    assert "0.0%" in body or "0%" in body


def test_zero_deposits_and_zero_upstream_is_quiet_window():
    """If both upstream and harvester have nothing, the window is just empty
    (e.g. holiday with no FR publications). Don't alert.
    """
    subject, body, alerted = _build_report(
        gte=GTE, lte=LTE, total=0, matched=0, upstream_sum=0, threshold=0.30
    )
    assert alerted is False
    assert "window empty" in subject


def test_exactly_at_threshold_does_not_alert():
    subject, body, alerted = _build_report(
        gte=GTE, lte=LTE, total=10, matched=3, upstream_sum=100, threshold=0.30
    )
    # 3/10 = 30.0% — equal to threshold, not below it.
    assert alerted is False


def test_threshold_is_strictly_less_than():
    """Just under the threshold should alert; the boundary should not."""
    just_below = _build_report(
        gte=GTE, lte=LTE, total=100, matched=29, upstream_sum=300, threshold=0.30
    )
    assert just_below[2] is True
    at_boundary = _build_report(
        gte=GTE, lte=LTE, total=100, matched=30, upstream_sum=300, threshold=0.30
    )
    assert at_boundary[2] is False


def test_report_body_contains_all_metrics():
    _, body, _ = _build_report(
        gte=GTE, lte=LTE, total=294, matched=6, upstream_sum=401, threshold=0.30
    )
    # Each headline number should be present in the email body.
    assert "294" in body
    assert "6" in body
    assert "2.0%" in body
    assert "401" in body
    assert "30%" in body
    assert GTE in body
    assert LTE in body
