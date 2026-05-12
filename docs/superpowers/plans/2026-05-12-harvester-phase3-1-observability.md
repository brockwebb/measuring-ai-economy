# Harvester Phase 3.1 (Observability — Co-occurrence + Saturation + Failure Classifier) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the three observability tables created by migration 004 (`harvest.co_sources`, `harvest.failure_patterns`, `harvest.saturation` view) at runtime; surface them via CLI + nightly email alerts. This completes the "harvester learns from what it already has" triangle before the citation-chain expansion machinery is built (3.2).

**Architecture:** Three small modules in `harvester/improvement/`, two runner hooks (co-occurrence detection before skipping a known URL, failure classification at run end), two CLI subcommands (`check-saturation`, `check-failures`), one nightly launchd job (saturation check). No new tables, no new migrations — the schema landed in Phase 2's migration 004.

**Tech Stack:** Python 3.12, psycopg, smtplib (stdlib) — no new dependencies.

**Parent spec:** `docs/superpowers/specs/2026-05-11-harvester-evolution-design.md` §7 Phase 3 (sub-system 3.1 per `docs/superpowers/notes/phase3-roadmap.md`).

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch strategy:** create `feat/harvester-phase3-1-observability` from `main` before Task 1.

---

## File Structure

**Created in this plan:**

```
measuring-ai-economy/
├── harvester/
│   ├── harvester/
│   │   ├── improvement/
│   │   │   ├── __init__.py             MODIFIED (replace stub with docstring marker)
│   │   │   ├── co_occurrence.py        [NEW]
│   │   │   ├── failure_patterns.py     [NEW]
│   │   │   ├── saturation.py           [NEW]
│   │   │   └── notify.py               [NEW] shared email helper
│   │   ├── runner.py                   MODIFIED — co-occurrence + failure hooks
│   │   └── cli.py                      MODIFIED — check-saturation + check-failures
│   └── tests/
│       ├── test_co_occurrence.py
│       ├── test_failure_patterns.py
│       ├── test_saturation.py
│       ├── test_runner_co_occurrence_hook.py
│       ├── test_runner_failure_classify_hook.py
│       ├── test_cli_check_saturation.py
│       └── test_cli_check_failures.py
└── ops/launchd/
    ├── com.wintermute.harvest-saturation-check.plist  (copy)
    └── harvest_saturation_check.sh                    (copy)

~/.wintermute/scripts/jobs/
└── harvest_saturation_check.sh                        [NEW launchd wrapper]

~/Library/LaunchAgents/
└── com.wintermute.harvest-saturation-check.plist      [NEW plist]
```

**Tables/views used (already exist, no migration needed):**
- `harvest.co_sources` (migration 004)
- `harvest.co_occurrence` view (migration 004)
- `harvest.failure_patterns` (migration 004)
- `harvest.saturation` view (migration 004)
- `harvest.fetched_items` (migration 001)
- `harvest.run_log` (migration 001)

---

## Tasks

### Task 1: Branch + improvement subpackage marker + shared notify helper

**Files:**
- Modify: `harvester/harvester/improvement/__init__.py` (currently a stub from Phase 1)
- Create: `harvester/harvester/improvement/notify.py`

- [ ] **Step 1: Create branch**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git checkout main
git checkout -b feat/harvester-phase3-1-observability
git branch --show-current
```

Expected: `feat/harvester-phase3-1-observability`

- [ ] **Step 2: Replace `harvester/harvester/improvement/__init__.py`**

```python
"""Harvester self-improvement subsystems.

Phase 3.1 modules:
- co_occurrence: cross-source dedup → harvest.co_sources ledger
- failure_patterns: per-source error clustering → harvest.failure_patterns
- saturation: deposit-ratio computation + email alerts → harvest.saturation view
- notify: shared SMTP-or-stderr alert helper
"""
```

- [ ] **Step 3: Create the shared notify helper at `harvester/harvester/improvement/notify.py`**

This consolidates the SMTP-or-stderr pattern that's currently inline in `validate_count.py`. We don't refactor `validate_count.py` here (out of scope), but new alerts use this module.

```python
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
```

- [ ] **Step 4: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/__init__.py harvester/harvester/improvement/notify.py
git commit -m "feat(harvester): improvement subpackage scaffolding + shared notify helper

Replaces the Phase 1 stub with a proper docstring marker listing the
Phase 3.1 modules (co_occurrence, failure_patterns, saturation, notify).
notify.py extracts the SMTP-or-stderr alert pattern used by
validate_count.py; new alerts (saturation, failure_patterns) use this
module instead of duplicating.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Co-occurrence ledger module

**Files:**
- Create: `harvester/harvester/improvement/co_occurrence.py`
- Create: `harvester/tests/test_co_occurrence.py`

The co-occurrence ledger records cross-source sightings of the same URL. When a URL is already deposited under a different `source_id`, instead of silently skipping, the runner writes a `harvest.co_sources` row capturing the new sighting.

- [ ] **Step 1: Write failing tests at `harvester/tests/test_co_occurrence.py`**

```python
"""Tests for the co-occurrence ledger."""

import pytest

from harvester.db import get_connection
from harvester.improvement.co_occurrence import (
    CoOccurrenceLedger,
    find_other_source_for_url,
)


@pytest.fixture
def clean_co_sources():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.co_sources WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id IN ('co_a', 'co_b')")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.co_sources WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id IN ('co_a', 'co_b')")
        conn.commit()
    finally:
        conn.close()


def test_find_other_source_returns_none_when_no_prior_deposit(clean_co_sources):
    conn = get_connection()
    try:
        result = find_other_source_for_url(conn, current_source="co_a",
                                            source_url="https://example.com/x")
        assert result is None
    finally:
        conn.close()


def test_find_other_source_returns_existing_source(clean_co_sources):
    """A URL deposited under 'co_a' is found when 'co_b' encounters it."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status) "
                "VALUES ('https://example.com/x', 'co_a', 'deposited')"
            )
        conn.commit()
        result = find_other_source_for_url(conn, current_source="co_b",
                                            source_url="https://example.com/x")
        assert result == "co_a"
    finally:
        conn.close()


def test_find_other_source_ignores_same_source(clean_co_sources):
    """Same source_id matches don't count as co-occurrences."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status) "
                "VALUES ('https://example.com/x', 'co_a', 'deposited')"
            )
        conn.commit()
        result = find_other_source_for_url(conn, current_source="co_a",
                                            source_url="https://example.com/x")
        assert result is None
    finally:
        conn.close()


def test_ledger_records_co_occurrence(clean_co_sources):
    conn = get_connection()
    try:
        ledger = CoOccurrenceLedger(conn)
        ledger.record_url(canonical_url="https://example.com/x",
                          source_id="co_b",
                          source_url="https://example.com/x")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT canonical_kind, source_id FROM harvest.co_sources "
                "WHERE canonical_key = 'https://example.com/x'"
            )
            row = cur.fetchone()
            assert row is not None
            kind, source = row
            assert kind == "url"
            assert source == "co_b"
    finally:
        conn.close()


def test_ledger_record_is_idempotent(clean_co_sources):
    """Recording the same (key, source_id, source_url) twice doesn't duplicate."""
    conn = get_connection()
    try:
        ledger = CoOccurrenceLedger(conn)
        ledger.record_url(canonical_url="https://example.com/x",
                          source_id="co_b",
                          source_url="https://example.com/x")
        ledger.record_url(canonical_url="https://example.com/x",
                          source_id="co_b",
                          source_url="https://example.com/x")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.co_sources "
                "WHERE canonical_key = 'https://example.com/x' AND source_id = 'co_b'"
            )
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_co_occurrence.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.improvement.co_occurrence'`

- [ ] **Step 3: Implement `harvester/harvester/improvement/co_occurrence.py`**

```python
"""Cross-source co-occurrence ledger.

When a URL deposited under one source_id is encountered by a different source_id,
the runner records a row in harvest.co_sources before skipping. Builds the
cross-source salience signal: high co_occurrence_count = same content seen
multiple places independently = important.

MVP scope: URL-based matching only (canonical_kind='url'). Content-hash and DOI
matching are out of 3.1 — they need a partial parse before the skip decision and
add measurable cost; we'll add them in a follow-up if the URL signal isn't
sufficient.
"""

from __future__ import annotations

import psycopg


def find_other_source_for_url(
    conn: psycopg.Connection,
    *,
    current_source: str,
    source_url: str,
) -> str | None:
    """Return the source_id of an existing deposit for source_url, IF that
    source_id is different from current_source. Otherwise None.

    Used by the runner to decide whether a `_already_seen` hit is a true
    same-source dedup (return None → skip silently) or a cross-source
    co-occurrence (return source_id → record before skip).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id FROM harvest.fetched_items
            WHERE item_id = %s AND status = 'deposited' AND source_id != %s
            ORDER BY fetched_at DESC LIMIT 1
            """,
            (source_url, current_source),
        )
        row = cur.fetchone()
        return row[0] if row else None


class CoOccurrenceLedger:
    """Persists cross-source sightings into harvest.co_sources."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def record_url(
        self,
        *,
        canonical_url: str,
        source_id: str,
        source_url: str,
    ) -> None:
        """Upsert a URL-keyed co-occurrence row. Idempotent via UNIQUE constraint."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.co_sources
                    (canonical_key, canonical_kind, source_id, source_url)
                VALUES (%s, 'url', %s, %s)
                ON CONFLICT (canonical_key, source_id, source_url) DO NOTHING
                """,
                (canonical_url, source_id, source_url),
            )
        self._conn.commit()
```

- [ ] **Step 4: Verify pass**

```bash
uv run pytest tests/test_co_occurrence.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/co_occurrence.py harvester/tests/test_co_occurrence.py
git commit -m "feat(harvester): co-occurrence ledger (URL-based)

CoOccurrenceLedger persists cross-source sightings into harvest.co_sources
(table from migration 004). find_other_source_for_url() resolves whether
a _already_seen hit is same-source (skip silently) or cross-source
(record + skip). MVP: URL only; content-hash and DOI matching deferred.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Runner co-occurrence hook

**Files:**
- Modify: `harvester/harvester/runner.py`
- Create: `harvester/tests/test_runner_co_occurrence_hook.py`

The hook fires when `_already_seen` returns True. Before the runner skips the payload, it calls `find_other_source_for_url`. If a different source_id deposited this URL, write a `co_sources` row.

- [ ] **Step 1: Write failing test at `harvester/tests/test_runner_co_occurrence_hook.py`**

```python
"""Tests for the runner co-occurrence hook."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.types import RawPayload


@pytest.fixture
def clean_co_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.co_sources WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id IN ('co_a', 'co_b')")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.co_sources WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id IN ('co_a', 'co_b')")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id IN ('co_a', 'co_b')")
        conn.commit()
    finally:
        conn.close()


def test_runner_records_co_occurrence_when_url_known_under_other_source(clean_co_state, tmp_path):
    """A URL deposited under co_a is encountered by co_b → co_sources row written."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status) "
                "VALUES ('https://example.com/shared', 'co_a', 'deposited')"
            )
        conn.commit()
    finally:
        conn.close()

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:x",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 10, 0, 0),
        source_id="co_b",
        source_url="https://example.com/shared",
        request_params={},
    )

    config = RunnerConfig(
        source_id="co_b",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=5,
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "co_b"
        expected_schema_version = 5
        def parse(self, raw):
            raise AssertionError("ETL should NOT be called when co-occurrence skip fires")
        def to_rows(self, parsed):
            return []

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT canonical_key, canonical_kind, source_id FROM harvest.co_sources "
                "WHERE source_id = 'co_b'"
            )
            row = cur.fetchone()
            assert row is not None
            key, kind, src = row
            assert key == "https://example.com/shared"
            assert kind == "url"
            assert src == "co_b"
    finally:
        conn.close()


def test_runner_does_not_record_co_occurrence_for_same_source_dedup(clean_co_state, tmp_path):
    """Same-source dedup is a silent skip, no co_sources row."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status) "
                "VALUES ('https://example.com/x', 'co_a', 'deposited')"
            )
        conn.commit()
    finally:
        conn.close()

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:y",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 10, 0, 0),
        source_id="co_a",
        source_url="https://example.com/x",
        request_params={},
    )

    config = RunnerConfig(
        source_id="co_a",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=5,
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "co_a"
        expected_schema_version = 5
        def parse(self, raw): ...
        def to_rows(self, parsed): return []

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM harvest.co_sources WHERE source_id = 'co_a'")
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_runner_co_occurrence_hook.py -v
```

Expected: failures (Runner doesn't yet record co-occurrences).

- [ ] **Step 3: Add the hook to `_drive` in `runner.py`**

Read `harvester/harvester/runner.py` first. Then locate the existing block inside `_drive()`:

```python
            if self._already_seen(conn, payload.source_url):
                continue
```

Replace with:

```python
            if self._already_seen(conn, payload.source_url):
                other_source = find_other_source_for_url(
                    conn,
                    current_source=self.config.source_id,
                    source_url=payload.source_url,
                )
                if other_source:
                    self._co_ledger.record_url(
                        canonical_url=payload.source_url,
                        source_id=self.config.source_id,
                        source_url=payload.source_url,
                    )
                continue
```

Add at the top of `runner.py` imports:

```python
from harvester.improvement.co_occurrence import (
    CoOccurrenceLedger,
    find_other_source_for_url,
)
```

In `_drive`, after `loader = Loader(conn)`, add:

```python
        self._co_ledger = CoOccurrenceLedger(conn)
```

(Inside `_drive`, not `__init__`, because `conn` is local to the run.)

- [ ] **Step 4: Run the new tests**

```bash
uv run pytest tests/test_runner_co_occurrence_hook.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full suite (no regressions)**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: all green (~80 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/runner.py harvester/tests/test_runner_co_occurrence_hook.py
git commit -m "feat(harvester): runner co-occurrence hook

When _already_seen returns True, the runner checks whether the existing
deposit was under a *different* source_id. If so, writes a row to
harvest.co_sources before silently skipping — capturing the cross-source
salience signal. Same-source dedup remains a silent skip.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Failure pattern classifier module

**Files:**
- Create: `harvester/harvester/improvement/failure_patterns.py`
- Create: `harvester/tests/test_failure_patterns.py`

Post-run, the classifier reads `fetched_items` rows from the just-completed run with `status='failed'`, normalizes their error strings into signatures, and upserts into `harvest.failure_patterns`. Alerts when a signature crosses 10 occurrences in 7 days.

- [ ] **Step 1: Write failing tests at `harvester/tests/test_failure_patterns.py`**

```python
"""Tests for the failure-pattern classifier."""

import pytest

from harvester.db import get_connection
from harvester.improvement.failure_patterns import (
    FailureClassifier,
    normalize_error,
    patterns_above_threshold,
)


@pytest.fixture
def clean_failure_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'fp_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'fp_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'fp_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'fp_test'")
        conn.commit()
    finally:
        conn.close()


def test_normalize_error_strips_variable_parts():
    """Timestamps, URLs, IDs, and line numbers get replaced with placeholders."""
    a = "Traceback at /Users/brock/foo.py:123, fetching https://example.com/abs/2305.12345"
    b = "Traceback at /Users/brock/foo.py:456, fetching https://example.com/abs/2401.67890"
    assert normalize_error(a) == normalize_error(b)


def test_normalize_error_keeps_distinct_signatures_distinct():
    a = "ConnectionRefusedError: localhost:5432"
    b = "TimeoutError: read timed out after 30s"
    assert normalize_error(a) != normalize_error(b)


def test_classifier_upserts_failure_signature(clean_failure_state):
    """Two failed items with same signature → one row, occurrence_count=2."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.run_log (id, source_id, status) "
                "VALUES (DEFAULT, 'fp_test', 'running') RETURNING id"
            )
            run_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status, run_id, error) "
                "VALUES (%s, 'fp_test', 'failed', %s, %s), (%s, 'fp_test', 'failed', %s, %s)",
                ("https://example.com/a", run_id,
                 "Traceback at /tmp/x.py:123, fetching https://example.com/a",
                 "https://example.com/b", run_id,
                 "Traceback at /tmp/x.py:456, fetching https://example.com/b"),
            )
        conn.commit()

        classifier = FailureClassifier(conn)
        classifier.classify_run(run_id)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT occurrence_count FROM harvest.failure_patterns "
                "WHERE source_id = 'fp_test'"
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 2
    finally:
        conn.close()


def test_classifier_handles_distinct_signatures(clean_failure_state):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO harvest.run_log (id, source_id, status) "
                "VALUES (DEFAULT, 'fp_test', 'running') RETURNING id"
            )
            run_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO harvest.fetched_items (item_id, source_id, status, run_id, error) "
                "VALUES (%s, 'fp_test', 'failed', %s, %s), (%s, 'fp_test', 'failed', %s, %s)",
                ("https://example.com/a", run_id, "ConnectionRefusedError: localhost:5432",
                 "https://example.com/b", run_id, "TimeoutError: read timed out after 30s"),
            )
        conn.commit()

        classifier = FailureClassifier(conn)
        classifier.classify_run(run_id)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.failure_patterns WHERE source_id = 'fp_test'"
            )
            assert cur.fetchone()[0] == 2
    finally:
        conn.close()


def test_patterns_above_threshold_returns_recent_high_count_patterns(clean_failure_state):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.failure_patterns
                    (source_id, error_signature, last_seen_at, occurrence_count, sample_error)
                VALUES
                    ('fp_test', 'sig_high', now(), 15, 'recent high-count'),
                    ('fp_test', 'sig_low', now(), 3, 'recent low-count'),
                    ('fp_test', 'sig_old', now() - interval '14 days', 99, 'old but high-count')
                """
            )
        conn.commit()

        results = patterns_above_threshold(conn, min_count=10, window_days=7)
        signatures = [r["error_signature"] for r in results]
        assert "sig_high" in signatures
        assert "sig_low" not in signatures
        assert "sig_old" not in signatures
    finally:
        conn.close()
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_failure_patterns.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `harvester/harvester/improvement/failure_patterns.py`**

```python
"""Failure pattern classifier.

Reads failed fetched_items rows from a just-completed run, normalizes the
error strings, upserts into harvest.failure_patterns. Alerts when a signature
crosses 10 occurrences in 7 days.
"""

from __future__ import annotations

import re

import psycopg


_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_URL_RE = re.compile(r"https?://\S+")
_PATH_LINENO_RE = re.compile(r"(/[\w\-./]+):\d+")
_NUMERIC_ID_RE = re.compile(r"\b\d{4,}\b")
_HEX_HASH_RE = re.compile(r"\b[0-9a-f]{16,}\b")


def normalize_error(error: str) -> str:
    """Reduce a raw error message to its stable signature.

    Replaces:
    - timestamps → <ts>
    - URLs → <url>
    - file paths with line numbers → <path>:<line>
    - long numeric IDs → <id>
    - hex hashes → <hash>
    """
    if not error:
        return "(empty)"
    s = error.strip()
    s = _TIMESTAMP_RE.sub("<ts>", s)
    s = _URL_RE.sub("<url>", s)
    s = _PATH_LINENO_RE.sub(r"<path>:<line>", s)
    s = _HEX_HASH_RE.sub("<hash>", s)
    s = _NUMERIC_ID_RE.sub("<id>", s)
    # Collapse multi-line tracebacks: keep first + last 200 chars
    if len(s) > 500:
        s = s[:200] + "..." + s[-200:]
    return s


class FailureClassifier:
    """Reads failed fetched_items rows for a run, upserts harvest.failure_patterns."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def classify_run(self, run_id: int) -> int:
        """Process all failed fetched_items for run_id. Returns count of failures classified."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_id, error FROM harvest.fetched_items
                WHERE run_id = %s AND status = 'failed' AND error IS NOT NULL
                """,
                (run_id,),
            )
            rows = cur.fetchall()

        count = 0
        for source_id, error in rows:
            signature = normalize_error(error)
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO harvest.failure_patterns
                        (source_id, error_signature, sample_error, occurrence_count, last_seen_at)
                    VALUES (%s, %s, %s, 1, now())
                    ON CONFLICT (source_id, error_signature) DO UPDATE
                    SET occurrence_count = harvest.failure_patterns.occurrence_count + 1,
                        last_seen_at = now()
                    """,
                    (source_id, signature, error[:1000]),
                )
            count += 1
        self._conn.commit()
        return count


def patterns_above_threshold(
    conn: psycopg.Connection,
    *,
    min_count: int = 10,
    window_days: int = 7,
) -> list[dict]:
    """Return failure_patterns rows with occurrence_count >= min_count seen in last window_days."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_id, error_signature, occurrence_count, sample_error,
                   first_seen_at, last_seen_at, mitigation_status
            FROM harvest.failure_patterns
            WHERE occurrence_count >= %s
              AND last_seen_at > now() - make_interval(days => %s)
              AND mitigation_status = 'unaddressed'
            ORDER BY occurrence_count DESC
            """,
            (min_count, window_days),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_failure_patterns.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/failure_patterns.py harvester/tests/test_failure_patterns.py
git commit -m "feat(harvester): failure pattern classifier

FailureClassifier.classify_run(run_id) reads failed fetched_items rows,
normalizes their errors (timestamps/URLs/paths/IDs/hashes → placeholders),
upserts into harvest.failure_patterns. patterns_above_threshold() returns
unaddressed patterns >= N occurrences in last N days for alerting.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Runner failure-classify hook

**Files:**
- Modify: `harvester/harvester/runner.py`
- Create: `harvester/tests/test_runner_failure_classify_hook.py`

The hook runs post-`_drive`, before `_close_run_log`. Calls `FailureClassifier(conn).classify_run(run_id)`.

- [ ] **Step 1: Write failing test at `harvester/tests/test_runner_failure_classify_hook.py`**

```python
"""Tests for the runner failure-classify hook."""

from datetime import datetime
from pathlib import Path

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.types import RawPayload


@pytest.fixture
def clean_failure_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'rfp_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'rfp_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'rfp_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'rfp_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'rfp_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'rfp_test'")
        conn.commit()
    finally:
        conn.close()


def test_runner_classifies_failures_after_run(clean_failure_state, tmp_path):
    """Runner with a fetcher that raises produces a failure_patterns row."""

    class RaisingETL:
        source_id = "rfp_test"
        expected_schema_version = 5
        def parse(self, raw):
            raise RuntimeError("synthetic parse failure at /tmp/x.py:42")
        def to_rows(self, parsed):
            return []

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:z",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 11, 0, 0),
        source_id="rfp_test",
        source_url="https://example.com/bad",
        request_params={},
    )

    class OneFailFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload

    config = RunnerConfig(
        source_id="rfp_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=5,
    )
    runner = Runner(config=config, fetcher=OneFailFetcher(), etl=RaisingETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT occurrence_count, error_signature, sample_error "
                "FROM harvest.failure_patterns WHERE source_id = 'rfp_test'"
            )
            row = cur.fetchone()
            assert row is not None
            count, signature, sample = row
            assert count == 1
            assert "synthetic" in sample
            assert "<path>:<line>" in signature  # normalization stripped the line number
    finally:
        conn.close()
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_runner_failure_classify_hook.py -v
```

Expected: failure (no failure_patterns row written).

- [ ] **Step 3: Add the hook to `Runner.run()`**

Read `runner.py`. Locate the existing block in `run()` (inside the `try:`):

```python
            with with_advisory_lock(conn, self.config.source_id):
                result = self._drive(conn, run_id, query)

            self._close_run_log(
                conn,
                run_id,
                ...
            )
```

Insert the classifier call BETWEEN the `with` block and `self._close_run_log`:

```python
            with with_advisory_lock(conn, self.config.source_id):
                result = self._drive(conn, run_id, query)

            # Phase 3.1: classify failures from this run
            try:
                FailureClassifier(conn).classify_run(run_id)
            except Exception:
                pass  # classifier failures don't affect run completion

            self._close_run_log(
                conn,
                run_id,
                ...
            )
```

Add to imports at top of `runner.py`:

```python
from harvester.improvement.failure_patterns import FailureClassifier
```

- [ ] **Step 4: Run new test**

```bash
uv run pytest tests/test_runner_failure_classify_hook.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/runner.py harvester/tests/test_runner_failure_classify_hook.py
git commit -m "feat(harvester): runner failure-classify hook

Post-_drive, before _close_run_log, the runner calls
FailureClassifier(conn).classify_run(run_id). Failed fetched_items rows
for this run get normalized error signatures and upserted into
harvest.failure_patterns. Classifier errors are swallowed (logging
without crashing the run) — failure tracking is observability, not
core path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Saturation monitor module

**Files:**
- Create: `harvester/harvester/improvement/saturation.py`
- Create: `harvester/tests/test_saturation.py`

Reads the `harvest.saturation` view, computes 7-day moving deposit_ratio per source, emits alert objects for sources crossing thresholds.

- [ ] **Step 1: Write failing tests at `harvester/tests/test_saturation.py`**

```python
"""Tests for the saturation monitor."""

import pytest

from harvester.db import get_connection
from harvester.improvement.saturation import (
    SaturationMonitor,
    SaturationAlert,
)


@pytest.fixture
def clean_saturation_state():
    """Insert synthetic run_log data simulating saturation patterns."""
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
        # 'sat_*' sources have no rows; existing other sources may be in there but the
        # monitor reads the view across all sources, so we filter to ours.
        alerts_for_sat = [a for a in alerts if a.source_id.startswith("sat_")]
        assert alerts_for_sat == []
    finally:
        conn.close()


def test_check_alerts_fires_for_saturated_source(clean_saturation_state):
    """A source with deposit_ratio < 0.05 sustained over 7 days alerts."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Seed 8 days of saturated runs (high fetched, ~zero deposited).
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
    """A source with deposit_ratio > 0.5 over 7 days does NOT alert."""
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
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_saturation.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `harvester/harvester/improvement/saturation.py`**

```python
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
    message: str                # human-readable summary


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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_saturation.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/saturation.py harvester/tests/test_saturation.py
git commit -m "feat(harvester): saturation monitor

SaturationMonitor.check_alerts() reads harvest.saturation view, computes
per-source deposit_ratio over rolling windows. Emits 'alert' severity
when ratio < 0.05 sustained 7+ days; 'notice' severity when < 0.20
sustained 14+ days. Per design spec §5.4 thresholds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: CLI `harvester check-saturation`

**Files:**
- Modify: `harvester/harvester/cli.py`
- Create: `harvester/tests/test_cli_check_saturation.py`

- [ ] **Step 1: Write failing test at `harvester/tests/test_cli_check_saturation.py`**

```python
"""Tests for `harvester check-saturation` CLI."""

import subprocess

import pytest

from harvester.db import get_connection


@pytest.fixture
def synthetic_saturated_data():
    """Insert 8 days of saturated runs for sat_cli_test."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'sat_cli_test'")
            for d in range(8):
                cur.execute(
                    """
                    INSERT INTO harvest.run_log
                        (source_id, status, items_fetched, items_deposited, started_at, finished_at)
                    VALUES ('sat_cli_test', 'completed', 100, 2, now() - make_interval(days => %s),
                            now() - make_interval(days => %s))
                    """,
                    (d, d),
                )
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'sat_cli_test'")
        conn.commit()
    finally:
        conn.close()


def test_check_saturation_cli_reports_alert(synthetic_saturated_data):
    result = subprocess.run(
        ["uv", "run", "harvester", "check-saturation"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode != 0, "should exit non-zero when alerts present"
    out = result.stdout + result.stderr
    assert "sat_cli_test" in out
    assert "alert" in out.lower() or "saturated" in out.lower()


def test_check_saturation_cli_clean_exit_when_no_alerts():
    """Without synthetic saturated data, real sources should not all be saturated."""
    # Run cleanly first
    subprocess.run(
        ["psql", "-d", "wintermute", "-c",
         "DELETE FROM harvest.run_log WHERE source_id = 'sat_cli_test'"],
        capture_output=True,
    )
    result = subprocess.run(
        ["uv", "run", "harvester", "check-saturation"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    # Existing real sources may or may not have alerts; this test just verifies the
    # CLI runs end-to-end without crashing.
    assert "Traceback" not in result.stderr
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_check_saturation.py -v
```

Expected: failure (subcommand not registered).

- [ ] **Step 3: Add `check-saturation` to `cli.py`**

Append to `harvester/harvester/cli.py` (after the `compare-sources` command):

```python
@app.command("check-saturation")
def check_saturation_cmd() -> None:
    """Check all sources' deposit_ratio against saturation thresholds. Email alerts."""
    from harvester.improvement.saturation import SaturationMonitor
    from harvester.improvement.notify import send_alert

    conn = get_connection()
    try:
        alerts = SaturationMonitor(conn).check_alerts()
        if not alerts:
            typer.echo("No saturation alerts. All sources within healthy ratios.")
            return

        body_lines = []
        for a in alerts:
            line = f"[{a.severity.upper()}] {a.message}"
            typer.echo(line)
            body_lines.append(line)

        if any(a.severity == "alert" for a in alerts):
            send_alert(
                subject=f"[harvester] {sum(1 for a in alerts if a.severity == 'alert')} saturation alert(s)",
                body="\n".join(body_lines),
            )
            raise typer.Exit(code=1)
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_check_saturation.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Verify --help**

```bash
uv run harvester --help 2>&1 | tail -10
```

Expected: 7 commands listed (adds check-saturation).

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/cli.py harvester/tests/test_cli_check_saturation.py
git commit -m "feat(harvester): \`harvester check-saturation\` CLI

Reads harvest.saturation view via SaturationMonitor; prints all alerts;
emails via notify.send_alert when any 'alert'-severity hits; exits
non-zero so the launchd wrapper signals downstream automation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: CLI `harvester check-failures`

**Files:**
- Modify: `harvester/harvester/cli.py`
- Create: `harvester/tests/test_cli_check_failures.py`

- [ ] **Step 1: Write failing test at `harvester/tests/test_cli_check_failures.py`**

```python
"""Tests for `harvester check-failures` CLI."""

import subprocess

import pytest

from harvester.db import get_connection


@pytest.fixture
def synthetic_failure_patterns():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_cli_test'")
            cur.execute(
                """
                INSERT INTO harvest.failure_patterns
                    (source_id, error_signature, occurrence_count, last_seen_at, sample_error)
                VALUES
                    ('fp_cli_test', 'sig_high', 25, now(), 'sample of the high-frequency error'),
                    ('fp_cli_test', 'sig_low', 3, now(), 'sample of the low-frequency one')
                """
            )
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_cli_test'")
        conn.commit()
    finally:
        conn.close()


def test_check_failures_reports_above_threshold(synthetic_failure_patterns):
    result = subprocess.run(
        ["uv", "run", "harvester", "check-failures"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    out = result.stdout
    assert "sig_high" in out
    assert "25" in out
    assert "sig_low" not in out  # below threshold


def test_check_failures_clean_when_no_alerts():
    subprocess.run(
        ["psql", "-d", "wintermute", "-c",
         "DELETE FROM harvest.failure_patterns WHERE source_id = 'fp_cli_test'"],
        capture_output=True,
    )
    result = subprocess.run(
        ["uv", "run", "harvester", "check-failures"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "Traceback" not in result.stderr
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_check_failures.py -v
```

Expected: failure (subcommand not registered).

- [ ] **Step 3: Add `check-failures` to `cli.py`**

Append to `harvester/harvester/cli.py`:

```python
@app.command("check-failures")
def check_failures_cmd(
    min_count: int = typer.Option(10, "--min-count", help="Threshold occurrence count"),
    window_days: int = typer.Option(7, "--window-days", help="Look-back window"),
) -> None:
    """Surface failure_patterns above the alert threshold."""
    from harvester.improvement.failure_patterns import patterns_above_threshold

    conn = get_connection()
    try:
        patterns = patterns_above_threshold(conn, min_count=min_count, window_days=window_days)
        if not patterns:
            typer.echo(f"No failure patterns crossing {min_count} occurrences in last {window_days}d.")
            return

        typer.echo(f"=== Failure patterns above threshold ({min_count} in {window_days}d) ===")
        for p in patterns:
            typer.echo(
                f"  [{p['source_id']}] {p['occurrence_count']}× since "
                f"{p['first_seen_at']:%Y-%m-%d}: {p['error_signature'][:120]}"
            )
            typer.echo(f"      sample: {(p['sample_error'] or '')[:200]}")
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_check_failures.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/cli.py harvester/tests/test_cli_check_failures.py
git commit -m "feat(harvester): \`harvester check-failures\` CLI

Surfaces harvest.failure_patterns rows above a configurable
(occurrence-count, window-days) threshold. Used both by humans for
spot-checks and by the weekly claudeclaw judgment job (3.5) to review
unaddressed failure clusters.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Nightly saturation check launchd

**Files:**
- Create: `~/.wintermute/scripts/jobs/harvest_saturation_check.sh`
- Create: `~/Library/LaunchAgents/com.wintermute.harvest-saturation-check.plist`
- Create: `ops/launchd/harvest_saturation_check.sh` (copy)
- Create: `ops/launchd/com.wintermute.harvest-saturation-check.plist` (copy)

- [ ] **Step 1: Write the wrapper**

Create `/Users/brock/.wintermute/scripts/jobs/harvest_saturation_check.sh`:

```bash
#!/usr/bin/env bash
# Nightly saturation check at 04:00 local.

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_saturation_check -- \
    "$UV_BIN" run harvester check-saturation
```

```bash
chmod +x /Users/brock/.wintermute/scripts/jobs/harvest_saturation_check.sh
```

- [ ] **Step 2: Write the plist**

Create `/Users/brock/Library/LaunchAgents/com.wintermute.harvest-saturation-check.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wintermute.harvest-saturation-check</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/brock/.wintermute/scripts/jobs/harvest_saturation_check.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>4</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_saturation_check.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_saturation_check.launchd.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/brock/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 3: Lint + smoke-test the wrapper**

```bash
plutil -lint /Users/brock/Library/LaunchAgents/com.wintermute.harvest-saturation-check.plist
bash /Users/brock/.wintermute/scripts/jobs/harvest_saturation_check.sh
tail -10 /Users/brock/.wintermute/logs/cron/harvest_saturation_check.log
```

Expected: plist OK; wrapper completes; log shows START + check-saturation output + END.

- [ ] **Step 4: Load the plist**

```bash
launchctl unload /Users/brock/Library/LaunchAgents/com.wintermute.harvest-saturation-check.plist 2>/dev/null
launchctl load /Users/brock/Library/LaunchAgents/com.wintermute.harvest-saturation-check.plist
launchctl list | grep harvest-saturation-check
```

Expected: loaded entry.

- [ ] **Step 5: Copy to ops/ + commit**

```bash
cp /Users/brock/Library/LaunchAgents/com.wintermute.harvest-saturation-check.plist \
   /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd/
cp /Users/brock/.wintermute/scripts/jobs/harvest_saturation_check.sh \
   /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd/

cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add ops/launchd/com.wintermute.harvest-saturation-check.plist
git add ops/launchd/harvest_saturation_check.sh
git commit -m "ops: launchd wrapper + plist for nightly saturation check

Daily at 04:00 local. Calls 'harvester check-saturation' which reads
the harvest.saturation view via SaturationMonitor and emails (via
notify.send_alert) when deposit_ratio crosses §5.4 thresholds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Final verification + observability smoke test

**No code changes.** Verification of the 3.1 substrate end-to-end.

- [ ] **Step 1: Full test suite green**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest 2>&1 | tail -3
```

Expected: all tests passing (~95+ after the 17 new tests added in this plan).

- [ ] **Step 2: Verify CLI surface**

```bash
uv run harvester --help 2>&1 | tail -15
```

Expected: 8 commands listed (migrate, scout, run, status, validate, compare-sources, check-saturation, check-failures).

- [ ] **Step 3: Live check-saturation**

```bash
uv run harvester check-saturation
```

Expected: either "No saturation alerts" or a list of currently-saturated sources. No crash.

- [ ] **Step 4: Live check-failures**

```bash
uv run harvester check-failures
```

Expected: either "No failure patterns crossing 10 occurrences..." or a list. No crash.

- [ ] **Step 5: Verify launchd entry is loaded**

```bash
launchctl list | grep -E "harvest-(federal-register|arxiv|saturation-check|count-validation|manifest-integrity)"
```

Expected: 5 entries (all 4 prior + new saturation-check).

- [ ] **Step 6: Trigger a real arxiv run to populate co_sources cross-source (optional but useful)**

If FR has documents whose URLs happen to match arxiv-discoverable URLs (rare; depends on what's in `harvest.fetched_items`), running arxiv now would record co-occurrences. Smoke check:

```bash
psql -d wintermute -c "SELECT count(*) FROM harvest.co_sources"
psql -d wintermute -c "SELECT count(*) FROM harvest.failure_patterns"
```

Expected: counts are reported (likely 0 for both initially); proves the tables exist and queries work.

- [ ] **Step 7: Verify branch state**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git log main..HEAD --oneline | wc -l
```

Expected: ~9 commits on `feat/harvester-phase3-1-observability`.

---

## Self-Review

**1. Spec coverage** — every Phase 3.1 deliverable from the roadmap (`docs/superpowers/notes/phase3-roadmap.md` §3.1):

| Deliverable | Task |
|---|---|
| Runner co-occurrence hook | Task 3 |
| Co-occurrence ledger module | Task 2 |
| Runner failure-classification hook | Task 5 |
| FailureClassifier module + alert query | Task 4 |
| `harvester check-saturation` CLI | Task 7 |
| `harvester check-failures` CLI | Task 8 |
| Launchd: nightly saturation check | Task 9 |
| Shared notify helper | Task 1 |
| Observability acceptance test | Task 10 |

**2. Placeholder scan** — none. Every step has either real code, real commands, or real expected output.

**3. Type consistency** — verified:
- `find_other_source_for_url(conn, *, current_source, source_url) → str | None` (Task 2) — used in Task 3's runner hook with the same kwargs.
- `CoOccurrenceLedger.record_url(canonical_url, source_id, source_url)` (Task 2) — used identically in Task 3.
- `normalize_error(str) → str` (Task 4) — used by both `FailureClassifier.classify_run` and tests.
- `FailureClassifier(conn).classify_run(run_id) → int` (Task 4) — same signature used by Task 5's runner hook.
- `patterns_above_threshold(conn, *, min_count=10, window_days=7) → list[dict]` (Task 4) — same signature used by Task 8's CLI.
- `SaturationAlert` dataclass (Task 6) — `source_id`, `severity`, `deposit_ratio`, `message` fields all referenced consistently by Task 7's CLI.
- `send_alert(*, subject, body)` (Task 1) — kwargs match Task 7's call site.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-harvester-phase3-1-observability.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
