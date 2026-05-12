"""Shared SMTP-or-stderr alert helper.

Sends email if WINTERMUTE_SMTP_HOST is set; falls back to stderr log.
Used by saturation and failure_patterns alerts.
"""

from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage


def send_alert(*, subject: str, body: str) -> None:
    """Email via SMTP env config, or log to stderr if not configured."""
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
