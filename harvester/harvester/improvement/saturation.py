"""Saturation monitor.

Reads harvest.saturation view, computes deposit_ratio over a window, emits
SaturationAlert objects. Used by the harvest_saturation_check launchd job
nightly.

Thresholds (from design spec §5.4):
- deposit_ratio < 0.05 over 7+ days → 'alert' severity
- deposit_ratio < 0.20 over 14+ days → 'notice' severity
- otherwise → no alert
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class SaturationAlert:
    source_id: str
    severity: str               # 'alert' | 'notice'
    deposit_ratio: float
    total_fetched: int
    total_deposited: int
    window_days: int
    message: str


class SaturationMonitor:
    """Reads harvest.saturation view, emits alerts based on deposit_ratio."""

    ALERT_RATIO = 0.05
    ALERT_DAYS = 7
    NOTICE_RATIO = 0.20
    NOTICE_DAYS = 14

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def check_alerts(self) -> list[SaturationAlert]:
        alerts: list[SaturationAlert] = []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_id,
                       sum(total_fetched) AS f,
                       sum(total_deposited) AS d,
                       count(*) AS days
                FROM harvest.saturation
                WHERE day > now() - make_interval(days => %s)
                GROUP BY source_id
                """,
                (self.NOTICE_DAYS,),
            )
            rows = cur.fetchall()

        for source_id, fetched, deposited, days in rows:
            if not fetched or fetched == 0:
                continue
            ratio = deposited / fetched
            if days >= self.ALERT_DAYS and ratio < self.ALERT_RATIO:
                alerts.append(SaturationAlert(
                    source_id=source_id,
                    severity="alert",
                    deposit_ratio=ratio,
                    total_fetched=int(fetched),
                    total_deposited=int(deposited),
                    window_days=int(days),
                    message=(
                        f"{source_id} saturated: {deposited}/{fetched} deposited "
                        f"({ratio:.1%}) over {days} days. Consider rubric bump or "
                        f"new seed terms."
                    ),
                ))
            elif days >= self.NOTICE_DAYS and ratio < self.NOTICE_RATIO:
                alerts.append(SaturationAlert(
                    source_id=source_id,
                    severity="notice",
                    deposit_ratio=ratio,
                    total_fetched=int(fetched),
                    total_deposited=int(deposited),
                    window_days=int(days),
                    message=(
                        f"{source_id} approaching saturation: {deposited}/{fetched} "
                        f"deposited ({ratio:.1%}) over {days} days."
                    ),
                ))
        return alerts
