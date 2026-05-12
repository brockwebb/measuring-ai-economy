"""Tests for the saturation monitor."""

import pytest

from harvester.db import get_connection
from harvester.improvement.saturation import (
    SaturationMonitor,
    SaturationAlert,
)


@pytest.fixture
def clean_saturation_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.run_log WHERE source_id LIKE 'sat_%'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.run_log WHERE source_id LIKE 'sat_%'")
        conn.commit()
    finally:
        conn.close()


def test_check_alerts_returns_empty_when_no_data(clean_saturation_state):
    conn = get_connection()
    try:
        monitor = SaturationMonitor(conn)
        alerts = monitor.check_alerts()
        alerts_for_sat = [a for a in alerts if a.source_id.startswith("sat_")]
        assert alerts_for_sat == []
    finally:
        conn.close()


def test_check_alerts_fires_for_saturated_source(clean_saturation_state):
    """A source with deposit_ratio < 0.05 sustained over 7 days alerts."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for d in range(8):
                cur.execute(
                    """
                    INSERT INTO harvest.run_log
                        (source_id, status, items_fetched, items_deposited, started_at, finished_at)
                    VALUES ('sat_saturated', 'completed', 100, 2, now() - make_interval(days => %s),
                            now() - make_interval(days => %s))
                    """,
                    (d, d),
                )
        conn.commit()

        monitor = SaturationMonitor(conn)
        alerts = monitor.check_alerts()
        alerts_for_saturated = [a for a in alerts if a.source_id == "sat_saturated"]
        assert len(alerts_for_saturated) == 1
        alert = alerts_for_saturated[0]
        assert alert.severity == "alert"
        assert alert.deposit_ratio < 0.05
    finally:
        conn.close()


def test_check_alerts_does_not_fire_for_healthy_source(clean_saturation_state):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for d in range(8):
                cur.execute(
                    """
                    INSERT INTO harvest.run_log
                        (source_id, status, items_fetched, items_deposited, started_at, finished_at)
                    VALUES ('sat_healthy', 'completed', 100, 80, now() - make_interval(days => %s),
                            now() - make_interval(days => %s))
                    """,
                    (d, d),
                )
        conn.commit()

        monitor = SaturationMonitor(conn)
        alerts = monitor.check_alerts()
        alerts_for_healthy = [a for a in alerts if a.source_id == "sat_healthy"]
        assert alerts_for_healthy == []
    finally:
        conn.close()


def test_check_alerts_emits_notice_for_moderate_saturation(clean_saturation_state):
    """Deposit ratio between 0.05 and 0.20 over 14 days → notice not alert."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for d in range(15):
                cur.execute(
                    """
                    INSERT INTO harvest.run_log
                        (source_id, status, items_fetched, items_deposited, started_at, finished_at)
                    VALUES ('sat_moderate', 'completed', 100, 10, now() - make_interval(days => %s),
                            now() - make_interval(days => %s))
                    """,
                    (d, d),
                )
        conn.commit()

        monitor = SaturationMonitor(conn)
        alerts = monitor.check_alerts()
        alerts_for_moderate = [a for a in alerts if a.source_id == "sat_moderate"]
        assert len(alerts_for_moderate) == 1
        alert = alerts_for_moderate[0]
        assert alert.severity == "notice"
    finally:
        conn.close()
