# Citation-Chain Seed-Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `SemanticScholarFetcher.get_references()` into the citation chain so approved depth-1 candidates produce depth-2 candidates from their reference lists. Expansion runs as a separate phase from triage (separate method, separate CLI command, separate launchd job).

**Architecture:** Migration 007 adds `expanded_at` and `parent_candidate_id` columns to `harvest.expansion_candidates`. A new `CitationChain.expand_approved()` method selects approved-but-unexpanded parents, calls `get_references` per parent, enqueues each cited paper (with a DOI) as a depth-2 'proposed' candidate via `ON CONFLICT (kind, payload) DO NOTHING`, then stamps `expanded_at` on success. A new `harvester chain-references` CLI drives it, and a new Sunday 02:45 launchd job fires it after the existing 02:30 `expand-citations` triage pass.

**Tech Stack:** Python 3.12; reuses existing harvester foundations (CitationChain, SemanticScholarFetcher, LlmTriage stays out of this path). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-12-citation-chain-seed-feedback-design.md`

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch:** `feat/citation-chain-seed-feedback` (already created from main; the spec doc is already on it as commit `0b5c0d1`).

---

## File Structure

**Created:**

```
measuring-ai-economy/
├── harvester/
│   ├── harvester/
│   │   └── schemas/
│   │       └── 007_expansion_chain.sql               [NEW]
│   └── tests/
│       ├── test_citation_chain_expand.py             [NEW]
│       └── test_cli_chain_references.py              [NEW]
└── ops/launchd/
    ├── com.wintermute.harvest-chain-references.plist [NEW]
    └── harvest_chain_references.sh                   [NEW]

~/.wintermute/scripts/jobs/
└── harvest_chain_references.sh                       [NEW launchd wrapper]

~/Library/LaunchAgents/
└── com.wintermute.harvest-chain-references.plist     [NEW plist]
```

**Modified:**

- `harvester/harvester/improvement/citation_chain.py` — append `expand_approved()` method to `CitationChain`.
- `harvester/harvester/cli.py` — append `chain-references` typer command.

**Schema dependencies (existing):**
- `harvest.expansion_candidates` (migration 004, extended by 006-era seed) — receives new columns from migration 007.
- `harvest.schema_migrations` (migration 001) — receives the new migration row.

---

## Tasks

### Task 1: Migration 007 — expanded_at + parent_candidate_id

**Files:** Create `harvester/harvester/schemas/007_expansion_chain.sql`

- [ ] **Step 1: Confirm branch state**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git branch --show-current
git log --oneline -3
```

Expected: branch `feat/citation-chain-seed-feedback`, top commit `0b5c0d1 docs: citation-chain seed-feedback loop design`.

- [ ] **Step 2: Write the migration**

Create `harvester/harvester/schemas/007_expansion_chain.sql`:

```sql
-- Migration 007: Extend harvest.expansion_candidates for the seed-feedback loop.
-- Adds expanded_at to mark which approved candidates have had their reference
-- lists fetched, and parent_candidate_id to link depth-2 candidates back to
-- the approved depth-1 parent that produced them.

BEGIN;

ALTER TABLE harvest.expansion_candidates
    ADD COLUMN IF NOT EXISTS expanded_at TIMESTAMPTZ NULL;

ALTER TABLE harvest.expansion_candidates
    ADD COLUMN IF NOT EXISTS parent_candidate_id BIGINT NULL
        REFERENCES harvest.expansion_candidates(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS expansion_candidates_unexpanded_idx
    ON harvest.expansion_candidates (score DESC NULLS LAST, proposed_at ASC)
    WHERE status = 'approved' AND expanded_at IS NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('007_expansion_chain.sql', 'PLACEHOLDER_SHA',
        'Add expanded_at + parent_candidate_id to expansion_candidates')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 3: Apply**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester migrate
```

Expected: `Applying 007_expansion_chain.sql (...)` then `Applied 1 migration(s).`

- [ ] **Step 4: Verify columns + index**

```bash
psql -d wintermute -c "\d harvest.expansion_candidates" | grep -E "expanded_at|parent_candidate_id|expansion_candidates_unexpanded_idx"
psql -d wintermute -c "SELECT filename, left(sha256, 12) FROM harvest.schema_migrations WHERE filename = '007_expansion_chain.sql'"
```

Expected:
- A row showing `expanded_at | timestamp with time zone`
- A row showing `parent_candidate_id | bigint`
- An index line mentioning `expansion_candidates_unexpanded_idx`
- A non-PLACEHOLDER sha256 prefix

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/schemas/007_expansion_chain.sql
git commit -m "feat(harvester): migration 007 — expansion_candidates chain columns

Adds expanded_at (TIMESTAMPTZ NULL) to mark which approved candidates
have had their reference lists fetched, and parent_candidate_id (self-FK
NULL) to link depth-2 candidates back to the approved depth-1 row they
descended from. Partial index on (score DESC, proposed_at ASC) WHERE
status='approved' AND expanded_at IS NULL keeps the expand_approved
selection cheap.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: CitationChain.expand_approved() — TDD with 6 unit tests

**Files:**
- Create `harvester/tests/test_citation_chain_expand.py`
- Modify `harvester/harvester/improvement/citation_chain.py` (append `expand_approved` method to the existing class)

- [ ] **Step 1: Write the test file at `harvester/tests/test_citation_chain_expand.py`**

```python
"""Tests for CitationChain.expand_approved (seed-feedback loop)."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from harvester.db import get_connection
from harvester.improvement.citation_chain import CitationChain


# All test rows use a distinctive DOI prefix so cleanup is unambiguous.
_TEST_DOI_PREFIX = "10.9999/expand_test"


@pytest.fixture
def clean_expand_candidates():
    """Wipe any leftover test rows before AND after each test.

    Depth-2 rows reference depth-1 via parent_candidate_id (ON DELETE SET NULL),
    so we don't need a strict ordering — but we delete children first anyway
    so the parent_candidate_id chain stays clean for assertions.
    """
    def _clean(conn):
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' LIKE %s",
                (f"{_TEST_DOI_PREFIX}%",),
            )
        conn.commit()

    conn = get_connection()
    try:
        _clean(conn)
        yield
        _clean(conn)
    finally:
        conn.close()


def _seed_approved_parent(conn, *, doi_suffix: str, parent_doc_id=None, score=0.8) -> int:
    """Insert an approved depth-1 candidate; return its id."""
    payload = {"doi": f"{_TEST_DOI_PREFIX}.parent.{doi_suffix}",
               "title": f"Parent {doi_suffix}",
               "source_url": "https://arxiv.org/abs/test"}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO harvest.expansion_candidates
                (kind, payload, parent_doc_id, depth, status, score)
            VALUES ('paper', %s::jsonb, %s, 1, 'approved', %s)
            RETURNING id
            """,
            (json.dumps(payload, sort_keys=True), parent_doc_id, score),
        )
        row_id = cur.fetchone()[0]
    conn.commit()
    return row_id


def _make_ref(ss_id: str, doi: str | None, title: str = "Ref"):
    """Build a Semantic Scholar reference dict in the API response shape."""
    return {
        "paperId": ss_id,
        "title": title,
        "externalIds": ({"DOI": doi} if doi else {}),
    }


def test_expand_approved_writes_depth_2_candidates(clean_expand_candidates):
    """Happy path: approved parent + 3 refs with DOIs → 3 depth-2 candidates,
    parent_candidate_id propagated, parent stamped with expanded_at."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="001")

        mock_ss = MagicMock()
        mock_ss.get_references.return_value = [
            _make_ref("ss_r1", f"{_TEST_DOI_PREFIX}.ref.001", "Ref One"),
            _make_ref("ss_r2", f"{_TEST_DOI_PREFIX}.ref.002", "Ref Two"),
            _make_ref("ss_r3", f"{_TEST_DOI_PREFIX}.ref.003", "Ref Three"),
        ]

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["parents_expanded"] == 1
        assert result["refs_enqueued"] == 3
        assert result["refs_dedup"] == 0
        assert result["refs_skipped_no_doi"] == 0
        assert result["deferred"] == 0

        mock_ss.get_references.assert_called_once_with(
            f"DOI:{_TEST_DOI_PREFIX}.parent.001", limit=100)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload->>'doi', parent_candidate_id, depth, status
                FROM harvest.expansion_candidates
                WHERE parent_candidate_id = %s
                ORDER BY id
                """,
                (parent_id,),
            )
            rows = cur.fetchall()
        assert len(rows) == 3
        for doi, pc_id, depth, status in rows:
            assert doi.startswith(f"{_TEST_DOI_PREFIX}.ref.")
            assert pc_id == parent_id
            assert depth == 2
            assert status == "proposed"

        with conn.cursor() as cur:
            cur.execute(
                "SELECT expanded_at FROM harvest.expansion_candidates WHERE id = %s",
                (parent_id,),
            )
            (stamped,) = cur.fetchone()
        assert stamped is not None
    finally:
        conn.close()


def test_expand_approved_skips_refs_without_doi(clean_expand_candidates):
    """Refs with no externalIds.DOI are dropped; counter increments."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="002")

        mock_ss = MagicMock()
        mock_ss.get_references.return_value = [
            _make_ref("ss_a", f"{_TEST_DOI_PREFIX}.ref.010"),
            _make_ref("ss_b", None),
            _make_ref("ss_c", f"{_TEST_DOI_PREFIX}.ref.011"),
        ]

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["refs_enqueued"] == 2
        assert result["refs_skipped_no_doi"] == 1
        assert result["parents_expanded"] == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.expansion_candidates "
                "WHERE parent_candidate_id = %s",
                (parent_id,),
            )
            assert cur.fetchone()[0] == 2
    finally:
        conn.close()


def test_expand_approved_dedups_across_parents(clean_expand_candidates):
    """Two parents cite the same ref → first inserts, second hits UNIQUE."""
    conn = get_connection()
    try:
        parent_a = _seed_approved_parent(conn, doi_suffix="003", score=0.9)
        parent_b = _seed_approved_parent(conn, doi_suffix="004", score=0.8)

        shared_doi = f"{_TEST_DOI_PREFIX}.ref.020"
        mock_ss = MagicMock()
        mock_ss.get_references.return_value = [_make_ref("ss_shared", shared_doi)]

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        # Two parents processed (score DESC → parent_a first), one ref enqueued,
        # second insert deduped.
        assert result["parents_expanded"] == 2
        assert result["refs_enqueued"] == 1
        assert result["refs_dedup"] == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = %s",
                (shared_doi,),
            )
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()


def test_expand_approved_skips_already_expanded(clean_expand_candidates):
    """Parents with expanded_at NOT NULL are not selected."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="005")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE harvest.expansion_candidates "
                "SET expanded_at = now() WHERE id = %s",
                (parent_id,),
            )
        conn.commit()

        mock_ss = MagicMock()
        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["parents_expanded"] == 0
        mock_ss.get_references.assert_not_called()
    finally:
        conn.close()


def test_expand_approved_stamps_on_empty_refs(clean_expand_candidates):
    """Empty refs list = successful expansion (SS has no refs for this paper).
    Parent gets stamped so we don't retry forever."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="006")

        mock_ss = MagicMock()
        mock_ss.get_references.return_value = []

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["parents_expanded"] == 1
        assert result["refs_enqueued"] == 0
        assert result["deferred"] == 0

        with conn.cursor() as cur:
            cur.execute(
                "SELECT expanded_at FROM harvest.expansion_candidates WHERE id = %s",
                (parent_id,),
            )
            assert cur.fetchone()[0] is not None
    finally:
        conn.close()


def test_expand_approved_defers_on_exception(clean_expand_candidates):
    """get_references raises → parent stays unexpanded, deferred++ ."""
    conn = get_connection()
    try:
        parent_id = _seed_approved_parent(conn, doi_suffix="007")

        mock_ss = MagicMock()
        mock_ss.get_references.side_effect = RuntimeError("transient SS error")

        chain = CitationChain(conn)
        result = chain.expand_approved(max_parents=10, ss_fetcher=mock_ss, ref_limit=100)

        assert result["parents_expanded"] == 0
        assert result["deferred"] == 1
        assert result["refs_enqueued"] == 0

        with conn.cursor() as cur:
            cur.execute(
                "SELECT expanded_at FROM harvest.expansion_candidates WHERE id = %s",
                (parent_id,),
            )
            assert cur.fetchone()[0] is None
    finally:
        conn.close()
```

- [ ] **Step 2: Verify tests fail (method doesn't exist)**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_citation_chain_expand.py -v
```

Expected: 6 failures with `AttributeError: 'CitationChain' object has no attribute 'expand_approved'` (or similar).

- [ ] **Step 3: Add `expand_approved` method to `harvester/harvester/improvement/citation_chain.py`**

Append the following method to the existing `CitationChain` class (alongside `enqueue` and `process_pending`):

```python
    def expand_approved(
        self,
        *,
        max_parents: int = 50,
        ss_fetcher,
        ref_limit: int = 100,
    ) -> dict[str, int]:
        """Fetch references for approved-but-not-yet-expanded candidates,
        enqueue each cited paper (with a DOI) as a depth-2 'proposed' candidate.

        For each approved parent with expanded_at IS NULL:
        1. Pull DOI from payload.
        2. Call ss_fetcher.get_references(f"DOI:{doi}", limit=ref_limit).
           - Raises: deferred++, expanded_at stays NULL, retried next run.
           - Returns (even []): stamp expanded_at, parents_expanded++.
        3. For each cited paper with a DOI, INSERT a depth-2 candidate with
           parent_candidate_id and propagated parent_doc_id. UNIQUE(kind, payload)
           dedups across parents.

        Returns {parents_expanded, refs_enqueued, refs_skipped_no_doi,
                 refs_dedup, deferred}.
        """
        import json as _json

        parents_expanded = 0
        refs_enqueued = 0
        refs_skipped_no_doi = 0
        refs_dedup = 0
        deferred = 0

        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, payload, parent_doc_id
                FROM harvest.expansion_candidates
                WHERE kind = 'paper'
                  AND status = 'approved'
                  AND expanded_at IS NULL
                ORDER BY score DESC NULLS LAST, proposed_at ASC
                LIMIT %s
                """,
                (max_parents,),
            )
            parents = cur.fetchall()

        for parent_id, payload, parent_doc_id in parents:
            doi = (payload or {}).get("doi")
            if not doi:
                # Approved without a DOI shouldn't happen (enqueue requires one),
                # but if it does, stamp so we don't loop on it.
                with self._conn.cursor() as cur:
                    cur.execute(
                        "UPDATE harvest.expansion_candidates "
                        "SET expanded_at = now() WHERE id = %s",
                        (parent_id,),
                    )
                self._conn.commit()
                parents_expanded += 1
                continue

            try:
                refs = ss_fetcher.get_references(f"DOI:{doi}", limit=ref_limit)
            except Exception:
                self._conn.rollback()
                deferred += 1
                continue

            for ref in refs:
                external_ids = ref.get("externalIds") if isinstance(ref, dict) else None
                ref_doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None
                if not ref_doi:
                    refs_skipped_no_doi += 1
                    continue
                ref_payload = {
                    "doi": ref_doi,
                    "title": ref.get("title"),
                    "source_url": f"https://www.semanticscholar.org/paper/{ref.get('paperId', '')}",
                }
                with self._conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO harvest.expansion_candidates
                            (kind, payload, parent_doc_id, parent_candidate_id,
                             depth, status)
                        VALUES ('paper', %s::jsonb, %s, %s, 2, 'proposed')
                        ON CONFLICT (kind, payload) DO NOTHING
                        RETURNING id
                        """,
                        (
                            _json.dumps(ref_payload, sort_keys=True),
                            parent_doc_id,
                            parent_id,
                        ),
                    )
                    inserted = cur.fetchone()
                if inserted:
                    refs_enqueued += 1
                else:
                    refs_dedup += 1

            with self._conn.cursor() as cur:
                cur.execute(
                    "UPDATE harvest.expansion_candidates "
                    "SET expanded_at = now() WHERE id = %s",
                    (parent_id,),
                )
            self._conn.commit()
            parents_expanded += 1

        return {
            "parents_expanded": parents_expanded,
            "refs_enqueued": refs_enqueued,
            "refs_skipped_no_doi": refs_skipped_no_doi,
            "refs_dedup": refs_dedup,
            "deferred": deferred,
        }
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_citation_chain_expand.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run full suite (must still be green)**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: 122 passed (116 from before + 6 new).

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/citation_chain.py harvester/tests/test_citation_chain_expand.py
git commit -m "feat(harvester): CitationChain.expand_approved — depth-2 candidate enqueue

Selects approved candidates with expanded_at IS NULL, fetches each parent's
reference list via SemanticScholarFetcher.get_references, and enqueues
each cited paper (with a DOI) as a depth-2 'proposed' candidate with
parent_candidate_id set and parent_doc_id propagated. UNIQUE (kind,
payload) dedups across parents.

Empty refs list = successful expansion (stamps expanded_at so we don't
retry forever). Exception = deferred (leaves expanded_at NULL).

Counters: {parents_expanded, refs_enqueued, refs_skipped_no_doi,
refs_dedup, deferred}.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: CLI `harvester chain-references`

**Files:**
- Modify `harvester/harvester/cli.py` (append a new typer command after `expand_citations_cmd`)
- Create `harvester/tests/test_cli_chain_references.py`

- [ ] **Step 1: Write tests at `harvester/tests/test_cli_chain_references.py`**

```python
"""Tests for `harvester chain-references` CLI."""

import subprocess


def test_chain_references_help_lists_command():
    """--help shows chain-references subcommand."""
    result = subprocess.run(
        ["uv", "run", "harvester", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "chain-references" in result.stdout, f"missing subcommand. stdout: {result.stdout}"


def test_chain_references_dry_run_does_not_call_api():
    """--dry-run prints what would be expanded; does not hit Semantic Scholar."""
    result = subprocess.run(
        ["uv", "run", "harvester", "chain-references", "--dry-run", "--max-parents", "5"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "DRY RUN" in result.stdout
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_chain_references.py -v
```

Expected: the `dry_run` test fails (subcommand not registered → typer exits non-zero); the help test may pass (substring check on broader stdout — but should fail because "chain-references" isn't yet listed). Either way, at least one test fails.

- [ ] **Step 3: Append a new typer command to `harvester/harvester/cli.py`**

Add at the end of the file:

```python
@app.command("chain-references")
def chain_references_cmd(
    max_parents: int = typer.Option(50, "--max-parents",
        help="Max approved candidates to expand"),
    ref_limit: int = typer.Option(100, "--ref-limit",
        help="Max references to pull per parent"),
    dry_run: bool = typer.Option(False, "--dry-run",
        help="Print pending count without API calls"),
) -> None:
    """Fetch references for approved candidates, enqueue cited papers
    as depth-2 'proposed' candidates."""
    from harvester.improvement.citation_chain import CitationChain
    from harvester.fetchers.semantic_scholar import SemanticScholarFetcher
    from harvester.manifest import RawArchive

    conn = get_connection()
    try:
        if dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM harvest.expansion_candidates "
                    "WHERE kind = 'paper' AND status = 'approved' "
                    "AND expanded_at IS NULL"
                )
                pending = cur.fetchone()[0]
            typer.echo(
                f"DRY RUN: would expand up to {max_parents} of {pending} "
                f"approved-but-unexpanded candidates (ref_limit={ref_limit})."
            )
            return

        data_root = _data_root()
        archive = RawArchive(
            root=data_root / "raw",
            manifest_path=data_root / "manifests" / "raw_manifest.parquet",
        )
        ss_fetcher = SemanticScholarFetcher(archive=archive)

        chain = CitationChain(conn)
        result = chain.expand_approved(
            max_parents=max_parents,
            ss_fetcher=ss_fetcher,
            ref_limit=ref_limit,
        )
        typer.echo(
            f"Expanded {result['parents_expanded']} parents: "
            f"refs_enqueued={result['refs_enqueued']} "
            f"refs_skipped_no_doi={result['refs_skipped_no_doi']} "
            f"refs_dedup={result['refs_dedup']} "
            f"deferred={result['deferred']}"
        )
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_chain_references.py -v
uv run pytest 2>&1 | tail -3
```

Expected: 2 passed for new tests; full suite at 124 passed.

- [ ] **Step 5: Smoke the CLI**

```bash
uv run harvester chain-references --dry-run --max-parents 5
```

Expected: a line like `DRY RUN: would expand up to 5 of 0 approved-but-unexpanded candidates (ref_limit=100).` (0 because no approved candidates yet — the SS API key hasn't landed so process_pending hasn't approved anything.)

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/cli.py harvester/tests/test_cli_chain_references.py
git commit -m "feat(harvester): \`harvester chain-references\` CLI

Drives CitationChain.expand_approved. --dry-run reports pending
count (approved-but-unexpanded) without touching Semantic Scholar.
Real run instantiates SemanticScholarFetcher, expands up to
--max-parents parents at --ref-limit references each, echoes the
five result counters.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Launchd weekly job (Sundays 02:45)

**Files:**
- Create `~/.wintermute/scripts/jobs/harvest_chain_references.sh`
- Create `~/Library/LaunchAgents/com.wintermute.harvest-chain-references.plist`
- Create `ops/launchd/harvest_chain_references.sh` (mirror)
- Create `ops/launchd/com.wintermute.harvest-chain-references.plist` (mirror)

- [ ] **Step 1: Write the wrapper script**

Create `/Users/brock/.wintermute/scripts/jobs/harvest_chain_references.sh`:

```bash
#!/usr/bin/env bash
# Weekly citation-chain reference expansion (Sundays 02:45 local).

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_chain_references -- \
    "$UV_BIN" run harvester chain-references --max-parents 50 --ref-limit 100
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x /Users/brock/.wintermute/scripts/jobs/harvest_chain_references.sh
```

- [ ] **Step 3: Write the plist**

Create `/Users/brock/Library/LaunchAgents/com.wintermute.harvest-chain-references.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wintermute.harvest-chain-references</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/brock/.wintermute/scripts/jobs/harvest_chain_references.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>45</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_chain_references.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_chain_references.launchd.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/brock/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

(Weekday=0 = Sunday; Hour=2 Minute=45 = 02:45 local.)

- [ ] **Step 4: Lint + load**

```bash
plutil -lint /Users/brock/Library/LaunchAgents/com.wintermute.harvest-chain-references.plist
launchctl unload /Users/brock/Library/LaunchAgents/com.wintermute.harvest-chain-references.plist 2>/dev/null
launchctl load /Users/brock/Library/LaunchAgents/com.wintermute.harvest-chain-references.plist
launchctl list | grep harvest-chain-references
```

Expected:
- `plutil` says `OK`.
- `launchctl list` shows a line like `- 0 com.wintermute.harvest-chain-references`.

- [ ] **Step 5: Copy mirrors into the repo**

```bash
cp /Users/brock/Library/LaunchAgents/com.wintermute.harvest-chain-references.plist \
   /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd/
cp /Users/brock/.wintermute/scripts/jobs/harvest_chain_references.sh \
   /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd/
```

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add ops/launchd/com.wintermute.harvest-chain-references.plist
git add ops/launchd/harvest_chain_references.sh
git commit -m "feat(harvester): launchd weekly chain-references job (Sundays 02:45)

Runs 'harvester chain-references --max-parents 50 --ref-limit 100' 15
minutes after the existing expand-citations triage pass. Separate plist
+ wrapper so the operator can disable expansion independently of triage.
Logs to ~/.wintermute/logs/cron/harvest_chain_references.launchd.log.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Final verification

**No code changes.**

- [ ] **Step 1: Full test suite green**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest 2>&1 | tail -3
```

Expected: 124 passed (116 from Phase 3.2 + 6 expand + 2 CLI).

- [ ] **Step 2: CLI surface**

```bash
uv run harvester --help 2>&1 | grep -E "expand-citations|chain-references"
```

Expected: both lines visible.

- [ ] **Step 3: Live dry-run**

```bash
uv run harvester chain-references --dry-run
```

Expected: `DRY RUN: would expand up to 50 of N approved-but-unexpanded candidates (ref_limit=100).` where N matches `SELECT count(*) FROM harvest.expansion_candidates WHERE status='approved' AND expanded_at IS NULL`. At plan time N is expected to be 0 (no approvals exist yet — pending SS API key).

- [ ] **Step 4: Confirm migration applied + schema state**

```bash
psql -d wintermute -c "
SELECT
  count(*) FILTER (WHERE expanded_at IS NULL AND status = 'approved') AS approved_unexpanded,
  count(*) FILTER (WHERE expanded_at IS NOT NULL) AS already_expanded,
  count(*) FILTER (WHERE depth = 2) AS depth_2_rows
FROM harvest.expansion_candidates;
"
```

Expected: all three counts are 0 (no production traffic yet); migration applied without error.

- [ ] **Step 5: Launchd entry loaded**

```bash
launchctl list | grep -E "harvest-(citation-expand|chain-references)"
```

Expected: two entries.

- [ ] **Step 6: Branch state**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git log main..HEAD --oneline | wc -l
```

Expected: 5 commits on `feat/citation-chain-seed-feedback` (spec + 4 implementation tasks).

---

## Self-Review

**1. Spec coverage** — every section of the design doc maps to a task:

| Spec section | Task |
|---|---|
| Migration 007 (expanded_at, parent_candidate_id, partial index) | Task 1 |
| `CitationChain.expand_approved` method | Task 2 |
| 6 unit tests (writes / no-doi / dedup / already-expanded / empty / exception) | Task 2 |
| `harvester chain-references` CLI + 2 tests | Task 3 |
| Launchd Sundays 02:45 plist + wrapper | Task 4 |
| Smoke / operational verification | Task 5 |

**2. Placeholder scan** — none. Every step has real code or a real command.

**3. Type consistency** — verified:
- `CitationChain.expand_approved(*, max_parents, ss_fetcher, ref_limit) -> dict[str, int]` (Task 2) — called identically by the CLI in Task 3.
- `ss_fetcher.get_references(paper_id, *, limit) -> list[dict]` (matches Phase 3.2's `SemanticScholarFetcher.get_references` signature exactly).
- Counter keys `parents_expanded, refs_enqueued, refs_skipped_no_doi, refs_dedup, deferred` (Task 2) — same names referenced in CLI echo (Task 3).
- New columns `expanded_at` and `parent_candidate_id` (Task 1) — referenced in test queries (Task 2), in the selection query inside `expand_approved` (Task 2), in the dry-run count query (Task 3), and in the verification SQL (Task 5).
- Test DOI prefix `10.9999/expand_test.*` (Task 2 only) — distinct from prior tests' prefixes (`10.1234/test`, `10.9999/cc_test`, `10.9999/cc_test.proc`).
- Launchd label `com.wintermute.harvest-chain-references` (Task 4) — referenced in Step 5 `launchctl list` filter and Task 5 verification.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-citation-chain-seed-feedback.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, two-stage review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
