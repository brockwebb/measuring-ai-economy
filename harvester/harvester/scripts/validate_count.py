"""Nightly count validation: compare harvester ingest vs FR.gov public count.

Approach: union of tier_1 + tier_2 terms over the prior 30 days. The FR API
returns the public count via the 'count' field of a normal documents.json
request (with per_page=1 to minimize bandwidth). Compare to:

    SELECT count(*) FROM harvest.federal_register_documents
    WHERE (title ILIKE any term OR abstract ILIKE any term)
    AND publication_date BETWEEN ... AND ...

The upstream comparison is approximate — summing per-term counts double-
counts documents matching multiple terms, while the harvester uses distinct
rows. A 5% tolerance accommodates this; tighter accuracy is post-MVP.

Run from the launchd wrapper.
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
_TOLERANCE = 0.05


def _terms() -> list[str]:
    cfg = yaml.safe_load(CONFIG_PATH.read_text())["federal_register"]
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


def _harvester_count(gte: str, lte: str, terms: list[str]) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            ilike_pairs = " OR ".join(["title ILIKE %s OR abstract ILIKE %s"] * len(terms))
            params: list = []
            for t in terms:
                params.extend([f"%{t}%", f"%{t}%"])
            params.extend([gte, lte])
            sql = f"""
                SELECT count(*) FROM harvest.federal_register_documents
                WHERE ({ilike_pairs})
                AND publication_date BETWEEN %s AND %s
            """
            cur.execute(sql, params)
            return cur.fetchone()[0]
    finally:
        conn.close()


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


def main() -> int:
    gte = (date.today() - timedelta(days=30)).isoformat()
    lte = date.today().isoformat()
    terms = _terms()

    upstream_total = 0
    for t in terms:
        upstream_total += _upstream_count(t, gte, lte)

    harvester_total = _harvester_count(gte, lte, terms)

    diff = harvester_total - upstream_total
    if upstream_total == 0:
        ratio = 0.0
    else:
        ratio = abs(diff) / upstream_total

    msg = (
        f"FR count validation {gte}..{lte}\n"
        f"  upstream (sum-of-terms, double-counts overlaps): {upstream_total}\n"
        f"  harvester (distinct rows matching any term):     {harvester_total}\n"
        f"  diff: {diff} ({ratio:.1%})\n"
    )
    print(msg)
    if ratio > _TOLERANCE:
        _notify(
            subject=f"[harvester] FR count validation drift {ratio:.1%}",
            body=msg,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
