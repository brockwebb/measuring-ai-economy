"""Nightly Federal Register precision + coverage validation.

Previous version computed a "drift" metric:
    drift = abs(harvester_distinct_term_matches - upstream_per_term_sum) / upstream_per_term_sum

This conflated two different problems and made the alert hard to interpret:
the upstream sum double-counts documents matching multiple terms, while the
harvester counts distinct rows. A perfectly-working pipeline routinely fired
"99.5% drift" because the upstream sum was inflated by overlap.

Pivot (2026-05-18, follow-on to ETL precision tagging at commit 2284be9):

  - **Primary metric: precision rate** — of the FR rows deposited in the
    rolling window, what fraction have `payload->>'precision_match' = true`
    (i.e. title or abstract actually contains one of the configured terms,
    not just an agency name or document type that matched the loose FR API
    `conditions[term]` fulltext search). Read directly from the canonical
    metadata stamped at ETL time.

  - **Secondary metric: upstream per-term sum** — kept for context but
    explicitly labeled as "inflated by per-term overlap." Useful for spotting
    fetcher-loss (deposits suddenly drop to 0 while upstream stays nonzero)
    but no longer the basis of the alert.

  - **Alert conditions:**
      1. No deposits at all in window → fetcher loss
      2. Precision rate below configured threshold
         (`federal_register.precision_alert_threshold` in sources.yaml,
         default 0.30) → off-term content dominating

Run from the launchd wrapper `scripts/jobs/harvest_count_validation.sh`.
"""

from __future__ import annotations

import os
import smtplib
import sys
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

import httpx
import yaml

from harvester.db import get_connection

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.yaml"
_BASE_URL = "https://www.federalregister.gov/api/v1/documents.json"
_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"
_DEFAULT_PRECISION_THRESHOLD = 0.30
_DEFAULT_WINDOW_DAYS = 30


def _config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())["federal_register"]


def _terms(cfg: dict) -> list[str]:
    return list(cfg.get("tier_1_terms", [])) + list(cfg.get("tier_2_terms", []))


def _upstream_count(term: str, gte: str, lte: str) -> int:
    params = {
        "conditions[term]": term,
        "conditions[publication_date][gte]": gte,
        "conditions[publication_date][lte]": lte,
        "per_page": 1,
    }
    with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=30) as client:
        resp = client.get(_BASE_URL, params=params)
        resp.raise_for_status()
        return int(resp.json().get("count") or 0)


def _harvester_counts(gte: str, lte: str) -> tuple[int, int]:
    """Return (total_deposited, precision_matched) for the date window.

    Reads from document_metadata.payload — the canonical precision tag
    stamped at ETL parse time. Rows missing the key (shouldn't exist after
    the 2026-05-18 backfill, but defensive) are counted in total but not in
    matched, which is the correct interpretation.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    count(*) AS total,
                    count(*) FILTER (
                        WHERE (payload->>'precision_match')::boolean IS TRUE
                    ) AS matched
                FROM harvest.document_metadata
                WHERE source_id = 'federal_register'
                  AND published_date BETWEEN %s AND %s
                """,
                (gte, lte),
            )
            row = cur.fetchone()
            return int(row[0]), int(row[1])


def _notify(subject: str, body: str) -> None:
    """Send a notification email if SMTP env vars are set; else log to stderr."""
    smtp_host = os.environ.get("WINTERMUTE_SMTP_HOST")
    if not smtp_host:
        print(f"[NOTIFY] {subject}\n{body}", file=sys.stderr)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("WINTERMUTE_SMTP_FROM", "wintermute@localhost")
    msg["To"] = os.environ.get("WINTERMUTE_ALERT_EMAIL", "brockwebb45@gmail.com")
    msg.set_content(body)
    with smtplib.SMTP(smtp_host, int(os.environ.get("WINTERMUTE_SMTP_PORT", 587))) as s:
        s.starttls()
        if pw := os.environ.get("WINTERMUTE_SMTP_PASSWORD"):
            s.login(os.environ.get("WINTERMUTE_SMTP_USER", ""), pw)
        s.send_message(msg)


def _build_report(
    gte: str,
    lte: str,
    total: int,
    matched: int,
    upstream_sum: int,
    threshold: float,
) -> tuple[str, str, bool]:
    """Return (subject, body, alert_fired)."""
    rate = (matched / total) if total else 0.0
    body = (
        f"FR validation {gte}..{lte}\n"
        f"  harvester deposits in window:           {total}\n"
        f"  precision-matched (term in title/abst): {matched}\n"
        f"  precision rate:                         {rate:.1%}\n"
        f"  upstream API per-term sum (inflated):   {upstream_sum}\n"
        f"  threshold:                              {threshold:.0%}\n"
    )
    if total == 0 and upstream_sum > 0:
        subject = "[harvester] FR no deposits in window — fetcher loss?"
        return subject, body, True
    if total == 0:
        # Both zero; nothing to report. Don't alert — could be a quiet window.
        subject = "[harvester] FR validation: window empty (no upstream, no deposits)"
        return subject, body, False
    if rate < threshold:
        subject = (
            f"[harvester] FR precision rate {rate:.1%} below threshold {threshold:.0%}"
        )
        return subject, body, True
    subject = f"[harvester] FR precision rate {rate:.1%} OK"
    return subject, body, False


def main() -> int:
    cfg = _config()
    threshold = float(cfg.get("precision_alert_threshold", _DEFAULT_PRECISION_THRESHOLD))
    window_days = int(cfg.get("validation_window_days", _DEFAULT_WINDOW_DAYS))

    gte = (date.today() - timedelta(days=window_days)).isoformat()
    lte = date.today().isoformat()

    terms = _terms(cfg)
    upstream_sum = sum(_upstream_count(t, gte, lte) for t in terms)
    total, matched = _harvester_counts(gte, lte)

    subject, body, alert_fired = _build_report(
        gte, lte, total, matched, upstream_sum, threshold
    )
    print(body)
    if alert_fired:
        _notify(subject=subject, body=body)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
