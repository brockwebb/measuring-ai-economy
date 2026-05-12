# Harvester Phase 2 (arxiv vertical proof + migration) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate arxiv from the legacy `~/.wintermute/scripts/search_papers.py` to a harvester-pattern fetcher with LLM-driven triage, validate via 3-day parallel-run, then sunset the legacy script. First end-to-end source on the new evolution-era foundation.

**Architecture:** `ArxivFetcher` extends `HttpApiFetcher` (Phase 1) targeting `export.arxiv.org/api/query`. `ArxivETL` parses the Atom response into `harvest.document_metadata` + `harvest.arxiv_papers` rows. `LlmTriage` calls Claude via subprocess against `research_axes.yaml` and decorates the runner's emitted markdown plus writes a structured row to `harvest.triage_results`. The legacy `search_papers.py` keeps running alongside for a 3-day window; we compare output via a new `harvester compare-sources` CLI; once the harvester output reaches ≥95% of legacy's coverage and triage scores correlate (Spearman > 0.85), we atomically cut over. `arxiv_llm_triage.py` and `paper_keywords.yaml` content folds in during cutover.

**Tech Stack:** Python 3.12, uv (existing), feedparser/httpx/psycopg/pyarrow (existing), Claude CLI for triage subprocess (no new deps).

**Parent spec:** `docs/superpowers/specs/2026-05-11-harvester-evolution-design.md` §7 Phase 2.

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch strategy:** create `feat/harvester-phase2-arxiv` from `main` before Task 1.

**Operational note:** Tasks 1–10 are the build. Task 11 starts the parallel run. Task 12 is the cutover (gated by 3 days of green parallel output). Task 13 is the 7-day post-cutover stability monitor. Build tasks can land in one session; the verification + cutover spans 10 calendar days.

---

## File Structure

**Created in this plan:**

```
measuring-ai-economy/
├── harvester/
│   ├── harvester/
│   │   ├── fetchers/
│   │   │   └── arxiv.py                   [NEW] ArxivFetcher
│   │   ├── etl/
│   │   │   └── arxiv.py                   [NEW] ArxivETL
│   │   ├── triage/
│   │   │   ├── __init__.py                MODIFIED (replace stub)
│   │   │   ├── llm_triage.py              [NEW] LlmTriage class
│   │   │   ├── prompts.py                 [NEW] prompt templates
│   │   │   └── research_axes.yaml         [NEW] migrated copy of axes
│   │   ├── runner.py                      MODIFIED — triage hook
│   │   ├── cli.py                         MODIFIED — compare-sources subcommand
│   │   ├── config/sources.yaml            MODIFIED — add arxiv source
│   │   └── schemas/
│   │       ├── 004_self_improvement.sql   [NEW]
│   │       └── 005_arxiv_papers.sql       [NEW]
│   └── tests/
│       ├── test_fetcher_arxiv.py
│       ├── test_etl_arxiv.py
│       ├── test_triage_llm.py
│       ├── test_runner_triage_hook.py
│       ├── test_cli_compare_sources.py
│       └── fixtures/arxiv/
│           ├── api_page_1.xml
│           ├── paper_ml.input.xml         (one Atom <entry>)
│           ├── paper_econ.input.xml
│           ├── paper_stat.input.xml
│           ├── paper_cs.input.xml
│           ├── paper_ml.expected.json
│           ├── paper_econ.expected.json
│           ├── paper_stat.expected.json
│           └── paper_cs.expected.json
└── ops/launchd/
    └── (copies of) harvest_arxiv.sh, com.wintermute.harvest-arxiv.plist

~/.wintermute/
├── scripts/_sunset/                       [NEW dir, populated at Task 12 cutover]
│   ├── 2026-05-XX-search_papers.py
│   ├── 2026-05-XX-arxiv_llm_triage.py
│   └── 2026-05-XX-paper_keywords.yaml
└── scripts/jobs/harvest_arxiv.sh          [NEW launchd wrapper]

~/Library/LaunchAgents/
└── com.wintermute.harvest-arxiv.plist     [NEW plist]
```

---

## Tasks

### Task 1: Branch + research_axes.yaml migration + triage subpackage scaffolding

**Files:**
- Create: `harvester/harvester/triage/research_axes.yaml` (copy of ~/.wintermute/sources/research_axes.yaml)
- Modify: `harvester/harvester/triage/__init__.py` (stub → proper marker)

- [ ] **Step 1: Branch from main**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git checkout main
git checkout -b feat/harvester-phase2-arxiv
git branch --show-current
```

Expected: `feat/harvester-phase2-arxiv`

- [ ] **Step 2: Copy research_axes.yaml into the harvester package**

```bash
cp /Users/brock/.wintermute/sources/research_axes.yaml \
   /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/harvester/triage/research_axes.yaml
```

- [ ] **Step 3: Add a header comment to the in-package copy noting its origin**

Read the file, then prepend an explanatory comment block (insert before the existing `# Wintermute — Research Axes` line):

```yaml
# Harvester triage rubric — copy migrated from ~/.wintermute/sources/research_axes.yaml.
# The harvester package owns this file from this point; subsequent edits go here.
# The ~/.wintermute/sources/research_axes.yaml file remains for non-harvester callers
# (e.g., legacy drain_pdf_inbox.py) until they're sunsetted in their own follow-up.
#
```

- [ ] **Step 4: Replace `harvester/harvester/triage/__init__.py` with a proper package marker**

```python
"""Harvester triage subsystem.

LLM-driven per-axis scoring against the research_axes.yaml rubric.
Writes structured TriageResult rows into harvest.triage_results with
stochastic provenance recorded in harvest.stochastic_provenance.
"""
```

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/triage/__init__.py harvester/harvester/triage/research_axes.yaml
git commit -m "feat(harvester): bootstrap Phase 2 — migrate research_axes.yaml

Copies the canonical rubric (v0.3.0) from ~/.wintermute/sources into the
harvester package. The .wintermute copy stays in place for non-harvester
callers (drain_pdf_inbox etc.) and gets sunsetted in a separate spec.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Migration 004 — self-improvement tables

**Files:**
- Create: `harvester/harvester/schemas/004_self_improvement.sql`

Phase 2 only populates `triage_results` in this batch. The other tables (`co_sources`, `expansion_candidates`, `failure_patterns`) land here but stay empty until Phase 3 fills them. That's intentional — one migration, future-proof schema, no need for a second migration in Phase 3.

- [ ] **Step 1: Write migration SQL**

Create `harvester/harvester/schemas/004_self_improvement.sql`:

```sql
-- Migration 004: Self-improvement tables.
-- Phase 2 populates triage_results; Phase 3 populates the rest.

BEGIN;

-- Expansion candidates: papers/authors/terms proposed by adaptive loops (Phase 3)
CREATE TABLE IF NOT EXISTS harvest.expansion_candidates (
    id              BIGSERIAL PRIMARY KEY,
    kind            TEXT NOT NULL CHECK (kind IN ('paper', 'author', 'term')),
    payload         JSONB NOT NULL,
    parent_doc_id   BIGINT REFERENCES harvest.document_metadata(doc_id),
    depth           INTEGER NOT NULL DEFAULT 1 CHECK (depth BETWEEN 1 AND 3),
    score           REAL,
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed', 'approved', 'rejected', 'ingested')),
    proposed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     TEXT,
    UNIQUE (kind, payload)
);
CREATE INDEX IF NOT EXISTS expansion_candidates_kind_status_idx
    ON harvest.expansion_candidates (kind, status, score DESC);

-- Cross-source co-occurrence ledger (Phase 3)
CREATE TABLE IF NOT EXISTS harvest.co_sources (
    id              BIGSERIAL PRIMARY KEY,
    canonical_key   TEXT NOT NULL,
    canonical_kind  TEXT NOT NULL CHECK (canonical_kind IN ('doi', 'content_hash', 'url')),
    source_id       TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (canonical_key, source_id, source_url)
);
CREATE INDEX IF NOT EXISTS co_sources_key_idx
    ON harvest.co_sources (canonical_key, canonical_kind);

CREATE OR REPLACE VIEW harvest.co_occurrence AS
SELECT canonical_key,
       canonical_kind,
       array_agg(DISTINCT source_id ORDER BY source_id) AS sources,
       count(DISTINCT source_id) AS source_count,
       count(*) AS total_encounters,
       min(first_seen_at) AS first_seen,
       max(first_seen_at) AS latest_seen
FROM harvest.co_sources
GROUP BY canonical_key, canonical_kind;

-- Failure pattern clustering (Phase 3)
CREATE TABLE IF NOT EXISTS harvest.failure_patterns (
    id              BIGSERIAL PRIMARY KEY,
    source_id       TEXT NOT NULL,
    error_signature TEXT NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    sample_error    TEXT,
    mitigation_status TEXT DEFAULT 'unaddressed'
                    CHECK (mitigation_status IN ('unaddressed', 'in_progress', 'mitigated', 'wontfix')),
    UNIQUE (source_id, error_signature)
);
CREATE INDEX IF NOT EXISTS failure_patterns_source_idx
    ON harvest.failure_patterns (source_id, last_seen_at DESC);

-- run_log gains a post-extraction signal (saturation monitor reads this)
ALTER TABLE harvest.run_log
    ADD COLUMN IF NOT EXISTS new_graph_nodes INTEGER;

-- Triage results (Phase 2 populates this on every arxiv document)
CREATE TABLE IF NOT EXISTS harvest.triage_results (
    doc_id          BIGINT PRIMARY KEY REFERENCES harvest.document_metadata(doc_id),
    score           REAL NOT NULL,
    axes            JSONB NOT NULL,
    reason          TEXT,
    rubric_version  TEXT NOT NULL,
    model_id        TEXT,
    prompt_hash     TEXT,
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed        BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS triage_results_score_idx
    ON harvest.triage_results (score DESC, scored_at DESC);

-- Saturation view (read-only, derived; Phase 3 alerting reads this)
CREATE OR REPLACE VIEW harvest.saturation AS
SELECT source_id,
       date_trunc('day', started_at) AS day,
       sum(items_fetched) AS total_fetched,
       sum(items_deposited) AS total_deposited,
       CASE WHEN sum(items_fetched) > 0
            THEN sum(items_deposited)::float / sum(items_fetched)
            ELSE 0
       END AS deposit_ratio,
       sum(new_graph_nodes) AS new_nodes
FROM harvest.run_log
WHERE status = 'completed'
GROUP BY source_id, date_trunc('day', started_at)
ORDER BY day DESC;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('004_self_improvement.sql', 'PLACEHOLDER_SHA', 'Self-improvement tables (Phase 2-3 substrate)')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 2: Apply migration via the runner**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester migrate
```

Expected: `Applying 004_self_improvement.sql (...)` then `Applied 1 migration(s).`

- [ ] **Step 3: Verify tables exist**

```bash
psql -d wintermute -c "\dt harvest.*"
```

Expected: 14 tables (previous 10 + expansion_candidates + co_sources + failure_patterns + triage_results). Plus `harvest.saturation` and `harvest.co_occurrence` views (visible via `\dv harvest.*`).

```bash
psql -d wintermute -c "\dv harvest.*"
```

Expected: 2 views.

- [ ] **Step 4: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/schemas/004_self_improvement.sql
git commit -m "feat(harvester): migration 004 — self-improvement tables

Adds expansion_candidates, co_sources (+ co_occurrence view),
failure_patterns, triage_results tables plus run_log.new_graph_nodes
column and the saturation view. Phase 2 populates triage_results; the
rest fill in during Phase 3 (citation chain, co-occurrence, saturation
monitor, failure classifier).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Migration 005 — arxiv_papers analytical table

**Files:**
- Create: `harvester/harvester/schemas/005_arxiv_papers.sql`

- [ ] **Step 1: Write migration**

Create `harvester/harvester/schemas/005_arxiv_papers.sql`:

```sql
-- Migration 005: arxiv_papers — densely-typed analytical table.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.arxiv_papers (
    id                  BIGSERIAL PRIMARY KEY,
    arxiv_id            TEXT NOT NULL UNIQUE,        -- e.g., "2305.12345" or "2305.12345v2"
    arxiv_id_short      TEXT NOT NULL,                -- version-stripped: "2305.12345"
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    primary_category    TEXT,                          -- e.g., "cs.AI"
    categories          TEXT[] NOT NULL DEFAULT '{}',
    published_date      DATE NOT NULL,
    updated_date        DATE,
    doi                 TEXT,
    journal_ref         TEXT,
    arxiv_url           TEXT NOT NULL,                 -- canonical abstract page URL
    pdf_url             TEXT,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS arxiv_papers_published_idx
    ON harvest.arxiv_papers (published_date DESC);
CREATE INDEX IF NOT EXISTS arxiv_papers_primary_cat_idx
    ON harvest.arxiv_papers (primary_category);
CREATE INDEX IF NOT EXISTS arxiv_papers_categories_gin_idx
    ON harvest.arxiv_papers USING GIN (categories);
CREATE INDEX IF NOT EXISTS arxiv_papers_doi_idx
    ON harvest.arxiv_papers (doi) WHERE doi IS NOT NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('005_arxiv_papers.sql', 'PLACEHOLDER_SHA', 'arxiv_papers analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 2: Apply**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester migrate
```

Expected: `Applying 005_arxiv_papers.sql (...)` then `Applied 1 migration(s).`

- [ ] **Step 3: Verify**

```bash
psql -d wintermute -c "\d harvest.arxiv_papers" | head -20
```

Expected: column list including arxiv_id, title, authors (jsonb), primary_category, categories (text[]), published_date, doi.

- [ ] **Step 4: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/schemas/005_arxiv_papers.sql
git commit -m "feat(harvester): migration 005 — arxiv_papers table

Densely-typed analytical table for arxiv documents: arxiv_id with and
without version suffix, primary_category + categories array (GIN
indexed), published/updated dates, DOI, journal_ref. Joins via raw_hash
or doi to document_metadata.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Capture arxiv API fixture + ArxivFetcher

**Files:**
- Create: `harvester/tests/fixtures/arxiv/api_page_1.xml`
- Create: `harvester/harvester/fetchers/arxiv.py`
- Create: `harvester/tests/test_fetcher_arxiv.py`

- [ ] **Step 1: Capture a real arxiv API response sample**

```bash
mkdir -p /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/arxiv
curl -s 'http://export.arxiv.org/api/query?search_query=cat:cs.AI&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending' \
  -o /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/arxiv/api_page_1.xml
```

Verify reasonable size:

```bash
ls -la /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/arxiv/api_page_1.xml
```

Expected: file at least ~10KB.

- [ ] **Step 2: Write failing test at `harvester/tests/test_fetcher_arxiv.py`**

```python
"""Tests for ArxivFetcher."""

import re
from pathlib import Path

import pytest

from harvester.fetchers.arxiv import ArxivFetcher
from harvester.manifest import RawArchive


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "arxiv"


def test_arxiv_fetcher_yields_one_per_entry(tmp_path, httpx_mock):
    feed = (FIXTURE_DIR / "api_page_1.xml").read_text()
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^http://export\.arxiv\.org/api/query.*"),
        text=feed,
        is_reusable=True,
    )

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = ArxivFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({
        "categories": ["cs.AI"],
        "per_page": 5,
        "max_pages": 1,
    }))
    assert len(payloads) >= 1
    for p in payloads:
        assert p.source_id == "arxiv"
        assert p.raw_hash.startswith("sha256:")
        assert p.source_url.startswith("http://arxiv.org/abs/") or p.source_url.startswith("https://arxiv.org/abs/")


def test_arxiv_fetcher_respects_seen(tmp_path, httpx_mock):
    feed = (FIXTURE_DIR / "api_page_1.xml").read_text()
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^http://export\.arxiv\.org/api/query.*"),
        text=feed,
        is_reusable=True,
    )

    # Fetch once to learn what URLs come back, then re-fetch with all-but-one seen
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher_a = ArxivFetcher(archive=archive)
    first = list(fetcher_a.iter_payloads({"categories": ["cs.AI"], "per_page": 5, "max_pages": 1}))
    assert first

    # Now use a fresh archive and fetcher, seed seen with all but the first URL
    archive2 = RawArchive(root=tmp_path / "raw2", manifest_path=tmp_path / "m2.parquet")
    fetcher_b = ArxivFetcher(archive=archive2)
    seen = {p.source_url for p in first[1:]}
    second = list(fetcher_b.iter_payloads({"categories": ["cs.AI"], "per_page": 5, "max_pages": 1}, seen=seen))
    assert len(second) == 1
    assert second[0].source_url == first[0].source_url


def test_arxiv_fetcher_rate_limit_is_polite(tmp_path):
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = ArxivFetcher(archive=archive)
    rl = fetcher.rate_limit_spec()
    assert rl.requests_per_second <= 0.5  # arxiv asks for 3+ sec between requests
```

- [ ] **Step 3: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_arxiv.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement `harvester/harvester/fetchers/arxiv.py`**

```python
"""arxiv fetcher.

API: http://export.arxiv.org/api/query (Atom XML)
Auth: none.
Rate limit: arxiv asks for 3+ sec between requests. We pace at 1 req per 3 sec
(0.333 req/sec).
Pagination: ?start=N&max_results=M.

Note: arxiv's API returns Atom even from the HTTP/JSON-API-style endpoint, so
this fetcher does the XML parsing inline rather than reusing RssFetcher (the
Atom is wrapped in arxiv-specific OpenSearch metadata that feedparser handles
but the raw bytes we archive are XML, not JSON).
"""

from __future__ import annotations

from typing import Any, Iterable

import feedparser
import httpx

from harvester.fetchers.base import Fetcher
from harvester.types import RateLimit, RawPayload


_BASE_URL = "http://export.arxiv.org/api/query"
_DEFAULT_PER_PAGE = 50
_DEFAULT_MAX_PAGES = 5
_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"


class ArxivFetcher(Fetcher):
    source_id = "arxiv"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(
            requests_per_second=0.333,  # 3 sec between requests per arxiv guidance
            max_retries=3,
            backoff_seconds=[5, 15, 60],
        )

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        """Yield one RawPayload per arxiv entry matching the query.

        Query shape:
            {
                "categories": ["cs.AI", "stat.ML"],     # OR-joined into cat:X OR cat:Y
                "keyword": "knowledge graph agent",     # adds AND all:"keyword"
                "per_page": 50,
                "max_pages": 5,
                "sort_by": "submittedDate",
                "sort_order": "descending",
            }
        """
        seen = seen or set()
        per_page = int(query.get("per_page", _DEFAULT_PER_PAGE))
        max_pages = int(query.get("max_pages", _DEFAULT_MAX_PAGES))

        with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=30) as client:
            for page in range(max_pages):
                self._pace()
                params = self._build_params(query, page=page, per_page=per_page)
                resp = client.get(_BASE_URL, params=params)
                resp.raise_for_status()
                xml_text = resp.text

                # Cache the raw XML bytes per *entry* (not per page) so each entry
                # is independently provenanced; archive.write() will dedupe by sha.
                parsed = feedparser.parse(xml_text)
                entries = list(parsed.entries)
                if not entries:
                    break

                for entry in entries:
                    abs_url = self._canonical_url(entry)
                    if abs_url and abs_url in seen:
                        continue
                    entry_bytes = self._entry_to_bytes(entry)
                    yield self.archive.write(
                        source_id=self.source_id,
                        source_url=abs_url,
                        request_params={
                            **params,
                            "arxiv_id": getattr(entry, "id", ""),
                        },
                        content=entry_bytes,
                        content_type="application/xml",
                    )

                if len(entries) < per_page:
                    break

    @staticmethod
    def _build_params(query: dict[str, Any], *, page: int, per_page: int) -> dict[str, Any]:
        parts: list[str] = []
        if categories := query.get("categories"):
            cat_or = " OR ".join(f"cat:{c}" for c in categories)
            parts.append(f"({cat_or})")
        if keyword := query.get("keyword"):
            # quote-wrap the keyword for arxiv multi-term query
            parts.append(f'all:"{keyword}"')
        search_query = " AND ".join(parts) if parts else "all:*"
        return {
            "search_query": search_query,
            "start": page * per_page,
            "max_results": per_page,
            "sortBy": query.get("sort_by", "submittedDate"),
            "sortOrder": query.get("sort_order", "descending"),
        }

    @staticmethod
    def _canonical_url(entry: Any) -> str:
        """Return the abs URL for an arxiv entry. Prefer the 'alternate' link."""
        for link in entry.get("links", []):
            if link.get("rel") == "alternate" and link.get("href"):
                return link["href"]
        return entry.get("id", "")

    @staticmethod
    def _entry_to_bytes(entry: Any) -> bytes:
        """Serialize a single feedparser entry deterministically.

        feedparser entries don't round-trip cleanly to bytes; we serialize as a
        canonical JSON-shaped dict so re-parsing yields stable results.
        """
        import json
        record = {
            "id": entry.get("id"),
            "title": entry.get("title"),
            "summary": entry.get("summary"),
            "published": entry.get("published"),
            "updated": entry.get("updated"),
            "authors": [a.get("name") for a in entry.get("authors", []) if a.get("name")],
            "tags": [t.get("term") for t in entry.get("tags", []) if t.get("term")],
            "links": [{"rel": l.get("rel"), "href": l.get("href"), "type": l.get("type")}
                      for l in entry.get("links", [])],
            "arxiv_primary_category": entry.get("arxiv_primary_category", {}).get("term")
                if isinstance(entry.get("arxiv_primary_category"), dict) else None,
            "arxiv_doi": entry.get("arxiv_doi"),
            "arxiv_journal_ref": entry.get("arxiv_journal_ref"),
        }
        return json.dumps(record, sort_keys=True).encode("utf-8")
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_arxiv.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/fetchers/arxiv.py harvester/tests/test_fetcher_arxiv.py harvester/tests/fixtures/arxiv/api_page_1.xml
git commit -m "feat(harvester): ArxivFetcher (export.arxiv.org Atom API)

Inherits Fetcher directly (not HttpApiFetcher) because arxiv returns
Atom XML rather than JSON. Serializes each entry as canonical JSON bytes
to the archive (stable round-trip). Paces at 0.333 req/sec (arxiv asks
for 3+ sec between calls). Supports category + keyword search.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Capture 4 single-entry fixtures + ArxivETL with golden samples

**Files:**
- Create: `harvester/tests/fixtures/arxiv/paper_{ml,econ,stat,cs}.input.json` (4 files; the fetcher serializes entries as JSON-shaped dict bytes)
- Create: `harvester/harvester/etl/arxiv.py`
- Create: `harvester/tests/test_etl_arxiv.py`
- Create: `harvester/harvester/scripts/regen_arxiv_golden_samples.py`
- Create: `harvester/tests/fixtures/arxiv/paper_{ml,econ,stat,cs}.expected.json` (after regen)

- [ ] **Step 1: Extract 4 representative entries from the captured fixture**

The fetcher's `_entry_to_bytes` serializes entries as JSON-shaped dicts, so the ETL's input fixtures are also JSON. Use a one-off helper:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python <<'PY'
import json
import feedparser
from pathlib import Path

FIXTURE_DIR = Path("tests/fixtures/arxiv")
xml = (FIXTURE_DIR / "api_page_1.xml").read_text()
parsed = feedparser.parse(xml)
entries = list(parsed.entries)
print(f"Found {len(entries)} entries; saving up to 4.")

# Pick 4 entries — for fixture diversity, we want different primary categories
# if possible. Fall back to first 4 if not.
seen_cats: dict[str, int] = {}
chosen: list = []
for e in entries:
    cat = e.get("arxiv_primary_category", {}).get("term", "unknown")
    if cat not in seen_cats and len(chosen) < 4:
        seen_cats[cat] = len(chosen)
        chosen.append(e)
while len(chosen) < 4 and len(chosen) < len(entries):
    for e in entries:
        if e not in chosen:
            chosen.append(e)
            break

labels = ["ml", "econ", "stat", "cs"]
for i, e in enumerate(chosen[:4]):
    record = {
        "id": e.get("id"),
        "title": e.get("title"),
        "summary": e.get("summary"),
        "published": e.get("published"),
        "updated": e.get("updated"),
        "authors": [a.get("name") for a in e.get("authors", []) if a.get("name")],
        "tags": [t.get("term") for t in e.get("tags", []) if t.get("term")],
        "links": [{"rel": l.get("rel"), "href": l.get("href"), "type": l.get("type")}
                  for l in e.get("links", [])],
        "arxiv_primary_category": e.get("arxiv_primary_category", {}).get("term")
            if isinstance(e.get("arxiv_primary_category"), dict) else None,
        "arxiv_doi": e.get("arxiv_doi"),
        "arxiv_journal_ref": e.get("arxiv_journal_ref"),
    }
    out = FIXTURE_DIR / f"paper_{labels[i]}.input.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True))
    print(f"Wrote {out.name} (category: {record.get('arxiv_primary_category')})")
PY
```

Expected: 4 input.json files written. If fewer than 4 entries were captured, re-run the fetcher curl from Task 4 with `max_results=20`.

Verify:
```bash
ls /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/arxiv/paper_*.input.json
```

Expected: 4 files.

- [ ] **Step 2: Write failing tests at `harvester/tests/test_etl_arxiv.py`**

```python
"""Golden-sample tests for the arxiv ETL."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from harvester.etl.arxiv import ArxivETL
from harvester.types import RawPayload

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "arxiv"


def _make_payload(input_path: Path) -> RawPayload:
    return RawPayload(
        raw_hash="sha256:test",
        file_path=input_path,
        content_type="application/xml",
        fetched_at=datetime(2026, 5, 12, 7, 0, 0),
        source_id="arxiv",
        source_url=json.loads(input_path.read_text()).get("id", ""),
        request_params={},
    )


@pytest.mark.parametrize("name", ["ml", "econ", "stat", "cs"])
def test_parse_matches_golden_sample(name):
    input_path = FIXTURE_DIR / f"paper_{name}.input.json"
    expected_path = FIXTURE_DIR / f"paper_{name}.expected.json"
    raw = _make_payload(input_path)

    etl = ArxivETL()
    doc = etl.parse(raw)

    assert len(doc.rows) >= 2, "expected document_metadata + arxiv_papers rows"

    expected = json.loads(expected_path.read_text())
    actual = {
        "title": doc.title,
        "source_url": doc.source_url,
        "published_date": doc.published_date.isoformat() if doc.published_date else None,
        "rows": [
            {"target_table": r.target_table, "data": _normalize_for_compare(r.data)}
            for r in doc.rows
        ],
        "metadata": doc.metadata,
    }
    assert actual == expected, f"ETL output diverged from {name}.expected.json"


def _normalize_for_compare(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_arxiv.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement `harvester/harvester/etl/arxiv.py`**

```python
"""arxiv ETL.

Parses the JSON-shaped entry dict (produced by ArxivFetcher._entry_to_bytes)
into rows for:
  - harvest.document_metadata (thin, generic)
  - harvest.arxiv_papers (dense, source-shaped)

doi: extracted from arxiv_doi (set by arxiv when the paper has a DOI; many
don't). The metadata row's doi field gets the same value.

arxiv_id: derived from the entry's "id" URL (e.g.,
http://arxiv.org/abs/2305.12345v2). arxiv_id_short strips the trailing
"v\\d+" suffix for canonical lookup.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/([^/?#]+)")
_VERSION_SUFFIX_RE = re.compile(r"v\d+$")


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def _extract_arxiv_ids(entry_id: str | None) -> tuple[str, str]:
    """Return (full_id, short_id). full_id may have version, short_id has no version."""
    if not entry_id:
        return "", ""
    m = _ARXIV_ID_RE.search(entry_id)
    if not m:
        return "", ""
    full = m.group(1)
    short = _VERSION_SUFFIX_RE.sub("", full)
    return full, short


def _abs_url_from_links(links: list[dict[str, Any]]) -> str:
    for link in links:
        if link.get("rel") == "alternate" and link.get("href"):
            return link["href"]
    return ""


def _pdf_url_from_links(links: list[dict[str, Any]]) -> str | None:
    for link in links:
        if link.get("type") == "application/pdf" and link.get("href"):
            return link["href"]
    return None


class ArxivETL(ETL):
    source_id = "arxiv"
    expected_schema_version = 5

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())

        title = (record.get("title") or "").strip()
        # arxiv titles often have embedded newlines + multi-space — normalize
        title = " ".join(title.split())[:5000]

        abstract = (record.get("summary") or "").strip() or None
        if abstract:
            abstract = " ".join(abstract.split())

        authors = record.get("authors") or []
        categories = record.get("tags") or []
        primary_category = record.get("arxiv_primary_category")
        published_date = _date_or_none(record.get("published"))
        updated_date = _date_or_none(record.get("updated"))
        doi = record.get("arxiv_doi")
        journal_ref = record.get("arxiv_journal_ref")
        links = record.get("links") or []
        arxiv_url = _abs_url_from_links(links)
        pdf_url = _pdf_url_from_links(links)

        arxiv_id_full, arxiv_id_short = _extract_arxiv_ids(record.get("id"))

        arxiv_row = Row(
            target_table="harvest.arxiv_papers",
            data={
                "arxiv_id": arxiv_id_full,
                "arxiv_id_short": arxiv_id_short,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "primary_category": primary_category,
                "categories": categories,
                "published_date": published_date,
                "updated_date": updated_date,
                "doi": doi,
                "journal_ref": journal_ref,
                "arxiv_url": arxiv_url,
                "pdf_url": pdf_url,
                "raw_hash": raw.raw_hash,
            },
        )

        meta_row = Row(
            target_table="harvest.document_metadata",
            data={
                "source_id": self.source_id,
                "title": title,
                "authors": json.dumps(authors),
                "doi": doi,
                "source_url": arxiv_url,
                "published_date": published_date,
                "document_type": "arxiv_paper",
                "payload": json.dumps({
                    "arxiv_id": arxiv_id_short,
                    "primary_category": primary_category,
                    "categories": categories,
                }),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=arxiv_url,
            published_date=published_date,
            rows=[meta_row, arxiv_row],
            metadata={
                "document_type": "arxiv_paper",
                "arxiv_id": arxiv_id_short,
                "primary_category": primary_category,
                "doi": doi,
                "abstract": abstract,
            },
        )
```

- [ ] **Step 5: Write the regen helper at `harvester/harvester/scripts/regen_arxiv_golden_samples.py`**

```python
"""One-off helper to regenerate arxiv golden-sample expected files.

Usage: uv run python -m harvester.scripts.regen_arxiv_golden_samples
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from harvester.etl.arxiv import ArxivETL
from harvester.types import RawPayload


FIXTURE_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "arxiv"


def _normalize(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def main() -> None:
    etl = ArxivETL()
    for name in ("ml", "econ", "stat", "cs"):
        input_path = FIXTURE_DIR / f"paper_{name}.input.json"
        if not input_path.exists():
            print(f"SKIP {name} (no input)")
            continue
        raw = RawPayload(
            raw_hash="sha256:test",
            file_path=input_path,
            content_type="application/xml",
            fetched_at=datetime(2026, 5, 12, 7, 0, 0),
            source_id="arxiv",
            source_url=json.loads(input_path.read_text()).get("id", ""),
            request_params={},
        )
        doc = etl.parse(raw)
        expected = {
            "title": doc.title,
            "source_url": doc.source_url,
            "published_date": doc.published_date.isoformat() if doc.published_date else None,
            "rows": [
                {"target_table": r.target_table, "data": _normalize(r.data)}
                for r in doc.rows
            ],
            "metadata": doc.metadata,
        }
        out_path = FIXTURE_DIR / f"paper_{name}.expected.json"
        out_path.write_text(json.dumps(expected, indent=2, sort_keys=True))
        print(f"WROTE {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the regen helper**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python -m harvester.scripts.regen_arxiv_golden_samples
```

Expected: 4 `WROTE ...` lines.

- [ ] **Step 7: Inspect one expected file to confirm sanity**

```bash
head -50 /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/arxiv/paper_ml.expected.json
```

Verify: title non-empty, published_date YYYY-MM-DD, 2 rows (document_metadata + arxiv_papers), arxiv_id non-empty, primary_category present.

- [ ] **Step 8: Run the golden-sample tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_arxiv.py -v
```

Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/etl/arxiv.py
git add harvester/harvester/scripts/regen_arxiv_golden_samples.py
git add harvester/tests/test_etl_arxiv.py
git add harvester/tests/fixtures/arxiv/paper_*.input.json
git add harvester/tests/fixtures/arxiv/paper_*.expected.json
git commit -m "feat(harvester): ArxivETL + golden samples for 4 categories

Parses JSON-serialized arxiv entries into (document_metadata, arxiv_papers)
rows. Four golden-sample fixtures cover different primary_categories from
real API output. Normalizes title whitespace, extracts arxiv_id with and
without version suffix, captures DOI + journal_ref when present.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: LlmTriage class with Claude subprocess + prompts

**Files:**
- Create: `harvester/harvester/triage/prompts.py`
- Create: `harvester/harvester/triage/llm_triage.py`
- Create: `harvester/tests/test_triage_llm.py`

- [ ] **Step 1: Write failing tests at `harvester/tests/test_triage_llm.py`**

```python
"""Tests for LlmTriage (Claude subprocess mocked)."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harvester.triage.llm_triage import LlmTriage, TriageResult
from harvester.types import ParsedDoc, Row


AXES_PATH = Path(__file__).parent.parent / "harvester" / "triage" / "research_axes.yaml"


def _make_parsed(title="Test paper on diffusion models",
                 abstract="We study diffusion models in latent space.") -> ParsedDoc:
    return ParsedDoc(
        title=title,
        source_url="https://example.com/paper",
        published_date=date(2026, 5, 12),
        rows=[Row(target_table="harvest.document_metadata", data={"title": title})],
        metadata={"abstract": abstract, "document_type": "arxiv_paper"},
    )


@patch("harvester.triage.llm_triage.subprocess.run")
def test_triage_parses_claude_response(mock_run):
    """Claude returns valid JSON; we parse it into TriageResult."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "score": 0.72,
            "axes": {
                "stochastic_dynamics_info_geometry": 0.72,
                "canine_cognition_behavior": 0.0,
            },
            "reason": "Diffusion models hit the stochastic dynamics axis directly.",
        }),
        stderr="",
    )

    triage = LlmTriage(model_id="claude-sonnet-4-6", axes_yaml=AXES_PATH)
    result = triage.score(_make_parsed())

    assert isinstance(result, TriageResult)
    assert result.score == 0.72
    assert result.axes["stochastic_dynamics_info_geometry"] == 0.72
    assert "diffusion" in result.reason.lower()
    assert result.rubric_version  # non-empty (from yaml)
    assert result.model_id == "claude-sonnet-4-6"
    assert len(result.prompt_hash) == 64


@patch("harvester.triage.llm_triage.subprocess.run")
def test_triage_raises_on_invalid_json(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
    triage = LlmTriage(model_id="claude-sonnet-4-6", axes_yaml=AXES_PATH)
    with pytest.raises(RuntimeError, match="not JSON"):
        triage.score(_make_parsed())


@patch("harvester.triage.llm_triage.subprocess.run")
def test_triage_raises_on_nonzero_exit(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="claude failed")
    triage = LlmTriage(model_id="claude-sonnet-4-6", axes_yaml=AXES_PATH)
    with pytest.raises(RuntimeError, match="triage call failed"):
        triage.score(_make_parsed())


@patch("harvester.triage.llm_triage.subprocess.run")
def test_triage_clamps_score_to_unit_interval(mock_run):
    """If Claude returns a score outside [0, 1], we clamp it."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"score": 1.5, "axes": {}, "reason": "max relevance"}),
        stderr="",
    )
    triage = LlmTriage(model_id="claude-sonnet-4-6", axes_yaml=AXES_PATH)
    result = triage.score(_make_parsed())
    assert 0.0 <= result.score <= 1.0
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_triage_llm.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `harvester/harvester/triage/prompts.py`**

```python
"""Prompt templates for LLM triage."""

from __future__ import annotations


def build_triage_prompt(*, title: str, abstract: str, axes_yaml_text: str) -> str:
    """Build the user prompt for a single-document triage call.

    Claude is given the full axes registry plus the doc; we ask for per-axis
    scores plus a headline and a short reason. JSON output enforced via prompt
    + --output-format json on the CLI.
    """
    return (
        "You are triaging a single document against a research-axes rubric.\n\n"
        "Rubric (YAML):\n\n"
        "```yaml\n"
        f"{axes_yaml_text}\n"
        "```\n\n"
        "Document:\n\n"
        f"Title: {title}\n\n"
        f"Abstract: {abstract or '(no abstract)'}\n\n"
        "Task:\n"
        "- Score the document 0.0–1.0 on each axis from the rubric.\n"
        "- The headline `score` is the maximum across axes (or your judgment if the doc spans multiple axes meaningfully).\n"
        "- `reason` is one short sentence explaining the headline.\n\n"
        "Respond with JSON only, no commentary:\n"
        "{\n"
        '  "score": float (0.0–1.0),\n'
        '  "axes": { "<axis_name>": float, ... },\n'
        '  "reason": "..."\n'
        "}"
    )
```

- [ ] **Step 4: Implement `harvester/harvester/triage/llm_triage.py`**

```python
"""LLM triage — Claude subprocess against research_axes.yaml.

Migrated from ~/.wintermute/tools/arxiv_llm_triage.py with two changes:
1. Uses Claude via subprocess instead of GPT via OpenAI HTTP API.
2. Returns structured TriageResult instead of mutating frontmatter.

The runner is responsible for persisting the result to harvest.triage_results.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from harvester.triage.prompts import build_triage_prompt
from harvester.types import ParsedDoc


_CLAUDE_BIN = os.environ.get("HARVESTER_CLAUDE_BIN", "claude")


@dataclass(frozen=True)
class TriageResult:
    score: float                   # 0.0–1.0 headline
    axes: dict[str, float]         # per-axis breakdown
    reason: str                    # 1-sentence justification
    rubric_version: str            # from research_axes.yaml
    model_id: str                  # which Claude
    prompt_hash: str               # SHA256 of rendered prompt + input


class LlmTriage:
    def __init__(self, *, model_id: str, axes_yaml: Path) -> None:
        self._model_id = model_id
        self._axes_yaml_path = axes_yaml
        self._axes_yaml_text = axes_yaml.read_text()
        loaded = yaml.safe_load(self._axes_yaml_text) or {}
        self._rubric_version = str(loaded.get("rubric_version", "0.0.0"))

    def score(self, parsed: ParsedDoc) -> TriageResult:
        title = parsed.title or ""
        abstract = (parsed.metadata or {}).get("abstract") or ""
        prompt = build_triage_prompt(
            title=title,
            abstract=abstract,
            axes_yaml_text=self._axes_yaml_text,
        )
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        proc = subprocess.run(
            [_CLAUDE_BIN, "-p", prompt, "--output-format", "json",
             "--model", self._model_id],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"triage call failed (exit {proc.returncode}): {proc.stderr.strip()}")

        try:
            response = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"triage response not JSON: {e}; stdout: {proc.stdout[:200]}")

        # Claude CLI wraps tool output; the actual structured response may be
        # nested under "result" or "content". Try common shapes.
        body = response
        if isinstance(response, dict) and "result" in response and isinstance(response["result"], (dict, str)):
            body = response["result"]
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    pass

        if not isinstance(body, dict):
            raise RuntimeError(f"triage response shape unexpected: {response!r:.200}")

        score = float(body.get("score", 0.0))
        score = max(0.0, min(1.0, score))  # clamp
        axes = body.get("axes") or {}
        axes = {k: float(v) for k, v in axes.items() if isinstance(v, (int, float))}
        reason = str(body.get("reason", ""))[:1000]

        return TriageResult(
            score=score,
            axes=axes,
            reason=reason,
            rubric_version=self._rubric_version,
            model_id=self._model_id,
            prompt_hash=prompt_hash,
        )
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_triage_llm.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/triage/prompts.py harvester/harvester/triage/llm_triage.py harvester/tests/test_triage_llm.py
git commit -m "feat(harvester): LlmTriage with Claude subprocess

Migrated from ~/.wintermute/tools/arxiv_llm_triage.py with two changes:
- Claude subprocess instead of GPT/OpenAI HTTP.
- Structured TriageResult dataclass instead of frontmatter mutation.

Reads research_axes.yaml at construction, captures rubric_version.
Records prompt_hash for stochastic provenance. Clamps score to [0,1].
Handles Claude CLI's nested 'result' wrapper.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Runner triage hook integration

**Files:**
- Modify: `harvester/harvester/runner.py`
- Create: `harvester/tests/test_runner_triage_hook.py`

- [ ] **Step 1: Write failing test at `harvester/tests/test_runner_triage_hook.py`**

```python
"""Tests for the runner's triage hook."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.triage.llm_triage import TriageResult


@pytest.fixture
def clean_triage_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.triage_results WHERE doc_id IN (SELECT doc_id FROM harvest.document_metadata WHERE source_id = 'triage_test')")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'triage_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'triage_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.triage_results WHERE doc_id IN (SELECT doc_id FROM harvest.document_metadata WHERE source_id = 'triage_test')")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'triage_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'triage_test'")
        conn.commit()
    finally:
        conn.close()


def _fake_triage_result():
    return TriageResult(
        score=0.65,
        axes={"stochastic_dynamics_info_geometry": 0.65},
        reason="Diffusion model paper.",
        rubric_version="0.3.0",
        model_id="claude-sonnet-4-6",
        prompt_hash="a" * 64,
    )


@patch("harvester.runner.LlmTriage")
def test_runner_writes_triage_when_enabled(mock_triage_cls, clean_triage_state, tmp_path):
    """When triage_enabled=True, runner calls triage and persists results."""
    from harvester.types import RawPayload, ParsedDoc, Row
    from datetime import datetime

    mock_triage = MagicMock()
    mock_triage.score.return_value = _fake_triage_result()
    mock_triage_cls.return_value = mock_triage

    config = RunnerConfig(
        source_id="triage_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=5,
        triage_enabled=True,
        triage_model="claude-sonnet-4-6",
        triage_axes_yaml=Path(__file__).parent.parent / "harvester" / "triage" / "research_axes.yaml",
    )

    payload = RawPayload(
        raw_hash="sha256:abc",
        file_path=tmp_path / "fake.json",
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 7, 0, 0),
        source_id="triage_test",
        source_url="https://example.com/p1",
        request_params={},
    )
    (tmp_path / "fake.json").write_text("{}")

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "triage_test"
        expected_schema_version = 5
        def parse(self, raw):
            return ParsedDoc(
                title="Test",
                source_url=raw.source_url,
                published_date=date(2026, 5, 12),
                rows=[Row(target_table="harvest.document_metadata", data={
                    "source_id": "triage_test",
                    "title": "Test",
                    "source_url": raw.source_url,
                })],
                metadata={"abstract": "An abstract."},
            )
        def to_rows(self, parsed):
            return parsed.rows

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    mock_triage.score.assert_called_once()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.score, t.rubric_version, t.model_id
                FROM harvest.triage_results t
                JOIN harvest.document_metadata d ON d.doc_id = t.doc_id
                WHERE d.source_id = 'triage_test'
                """
            )
            row = cur.fetchone()
            assert row is not None
            score, rubric, model = row
            assert score == pytest.approx(0.65)
            assert rubric == "0.3.0"
            assert model == "claude-sonnet-4-6"
    finally:
        conn.close()


def test_runner_skips_triage_when_disabled(clean_triage_state, tmp_path):
    """triage_enabled=False (default) — no LlmTriage instantiated, no triage_results row."""
    from harvester.types import RawPayload, ParsedDoc, Row
    from datetime import datetime

    config = RunnerConfig(
        source_id="triage_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=5,
        triage_enabled=False,
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None): return iter([])
    class FakeETL:
        source_id = "triage_test"
        expected_schema_version = 5

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})
    # No errors; no triage performed (zero payloads anyway). Sanity check that
    # runner config accepts the new fields with defaults.
    assert runner.triage is None
```

- [ ] **Step 2: Verify failure** (RunnerConfig doesn't yet have triage_enabled / triage_model / triage_axes_yaml; Runner doesn't have `triage` attribute or hook)

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_runner_triage_hook.py -v
```

Expected: TypeError or AttributeError.

- [ ] **Step 3: Extend `RunnerConfig` and `Runner`**

Read the existing `harvester/harvester/runner.py`, then make these targeted edits:

(a) Add to imports section at top:

```python
from harvester.triage.llm_triage import LlmTriage
```

(b) Add fields to `RunnerConfig` dataclass (after the existing `scout_base_url` field):

```python
@dataclass
class RunnerConfig:
    source_id: str
    archive_root: Path
    manifest_path: Path
    inbox_dir: Path
    inbox_backpressure_max: int
    expected_schema_version: int
    scout_base_url: str | None = None
    triage_enabled: bool = False
    triage_model: str = "claude-sonnet-4-6"
    triage_axes_yaml: Path | None = None
    triage_threshold: float = 0.4
```

(c) In `Runner.__init__`, after the existing scout assignment, add:

```python
        self.triage: LlmTriage | None = None
        if config.triage_enabled and config.triage_axes_yaml is not None:
            self.triage = LlmTriage(
                model_id=config.triage_model,
                axes_yaml=config.triage_axes_yaml,
            )
```

(d) In `_drive`, between the loader call and emit_markdown — after `loader.load(rows, run_id=run_id)` and BEFORE `inbox_path = emit_markdown(...)` — add the triage call:

```python
                triage_score = None
                if self.triage is not None:
                    try:
                        tr = self.triage.score(parsed)
                        triage_score = tr.score
                        self._record_triage_result(conn, parsed, tr)
                        parsed.metadata["triage_score"] = tr.score
                        parsed.metadata["triage_reason"] = tr.reason
                        if tr.score < self.config.triage_threshold:
                            parsed.metadata["triage_below_threshold"] = True
                    except Exception as e:
                        parsed.metadata["triage_error"] = str(e)
```

(e) Add `_record_triage_result` method to the Runner class (near `_record_fetched_item`):

```python
    def _record_triage_result(self, conn: psycopg.Connection, parsed: ParsedDoc, tr) -> None:
        """Persist a TriageResult to harvest.triage_results.

        Joins to harvest.document_metadata by (source_id, source_url) to find
        the doc_id. Must run after loader.load() has inserted the metadata row.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT doc_id FROM harvest.document_metadata
                WHERE source_id = %s AND source_url = %s
                ORDER BY doc_id DESC LIMIT 1
                """,
                (self.config.source_id, parsed.source_url),
            )
            row = cur.fetchone()
            if not row:
                return  # metadata row not found; skip (defensive)
            doc_id = row[0]
            cur.execute(
                """
                INSERT INTO harvest.triage_results
                    (doc_id, score, axes, reason, rubric_version, model_id, prompt_hash)
                VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
                ON CONFLICT (doc_id) DO UPDATE
                SET score = EXCLUDED.score,
                    axes = EXCLUDED.axes,
                    reason = EXCLUDED.reason,
                    rubric_version = EXCLUDED.rubric_version,
                    model_id = EXCLUDED.model_id,
                    prompt_hash = EXCLUDED.prompt_hash,
                    scored_at = now()
                """,
                (doc_id, tr.score, json.dumps(tr.axes), tr.reason,
                 tr.rubric_version, tr.model_id, tr.prompt_hash),
            )
        conn.commit()
```

You'll also need to import `ParsedDoc` if not already imported. Check the existing imports.

- [ ] **Step 4: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_runner_triage_hook.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/runner.py harvester/tests/test_runner_triage_hook.py
git commit -m "feat(harvester): runner triage hook

RunnerConfig gains triage_enabled / triage_model / triage_axes_yaml /
triage_threshold fields. When enabled, the runner instantiates LlmTriage
and scores each parsed document post-load, persisting to
harvest.triage_results and decorating parsed.metadata so the normalizer
emits triage_score / triage_reason / triage_below_threshold in the
inbox markdown frontmatter.

Triage failures don't fail the doc — they record triage_error in metadata
and continue. Honors the existing rule: triage is metadata, not a gate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Wire arxiv into sources.yaml + CLI surface

**Files:**
- Modify: `harvester/harvester/config/sources.yaml`

- [ ] **Step 1: Read existing sources.yaml + add arxiv block**

Append the arxiv source to `harvester/harvester/config/sources.yaml`:

```yaml
arxiv:
  fetcher: harvester.fetchers.arxiv.ArxivFetcher
  etl: harvester.etl.arxiv.ArxivETL
  rolling_window_days: 30
  inbox_backpressure_max: 5000
  daily_cost_ceiling_usd: 5.00
  expected_schema_version: 5
  triage_enabled: true
  triage_threshold: 0.4
  triage_model: "claude-sonnet-4-6"
  scout_base_url: "https://arxiv.org"
  categories:
    # Core AI / ML categories
    - "cs.AI"
    - "cs.LG"
    - "cs.CL"
    - "stat.ML"
    # Economics measurement
    - "econ.GN"
    - "econ.EM"
    # Control / dynamics
    - "math.OC"
    - "stat.AP"
  # Tier-1 keywords folded in from ~/.wintermute/sources/paper_keywords.yaml
  tier_1_terms:
    - "knowledge graph agent"
    - "agent memory architecture"
    - "RAG retrieval augmented generation"
    - "entity extraction named entity recognition"
    - "research reproducibility provenance"
    - "survey methodology federal statistics"
    - "MCP model context protocol tool use"
    - "meta-learning few-shot"
    - "graph neural network knowledge base"
    - "multi-agent coordination planning"
    - "document understanding information extraction"
    - "research pipeline automation"
    - "entity resolution record linkage"
    - "knowledge graph deduplication entity alignment"
    - "confidence threshold entity matching"
    - "TAC-KBP knowledge base population"
    - "OAEI ontology alignment evaluation"
    - "knowledge graph completion link prediction"
    - "belief revision knowledge base update AGM"
  tier_2_terms: []
```

- [ ] **Step 2: Modify `cli.py`'s `run` command to support the arxiv query shape**

The existing `run` command builds a query dict tailored to federal_register (term + type + publication_date_*). arxiv needs (categories + keyword). Make the CLI aware of source-specific query construction.

The simplest approach: have the CLI pass through the source's `categories` config to the query, and use `keyword` instead of `term` for non-FR sources. Edit `harvester/harvester/cli.py` — find the `for term in terms:` loop inside `run()`. Replace it with:

```python
    total = 0
    for term in (terms or [None]):
        q: dict[str, Any] = {
            "per_page": 100,
            "max_pages": 10,
        }
        if source == "federal_register":
            q.update({
                "term": term,
                "type": cfg.get("document_types", []),
                "publication_date_gte": pub_gte,
                "publication_date_lte": pub_lte,
            })
        else:
            # Generic shape: categories from config + keyword from terms (if any).
            if cats := cfg.get("categories"):
                q["categories"] = cats
            if term:
                q["keyword"] = term
        label = repr(term) if term else "(no-keyword)"
        typer.echo(f"--- running {source} for term: {label}")
        result = runner.run(q)
        typer.echo(
            f"run_id={result.run_id} status={result.status} "
            f"fetched={result.items_fetched} deposited={result.items_deposited} "
            f"failed={result.items_failed}"
        )
        total += result.items_deposited
        if limit and total >= limit:
            typer.echo(f"Hit limit ({limit}); stopping.")
            break
```

Also modify the `RunnerConfig` construction inside `run()` to pull `triage_enabled` etc. from `cfg`:

Find the `config = RunnerConfig(...)` block and replace with:

```python
    config = RunnerConfig(
        source_id=source,
        archive_root=archive_root,
        manifest_path=manifest_path,
        inbox_dir=_staging_dir(),
        inbox_backpressure_max=int(cfg.get("inbox_backpressure_max", 5000)),
        expected_schema_version=int(cfg.get("expected_schema_version", 2)),
        scout_base_url=cfg.get("scout_base_url"),
        triage_enabled=bool(cfg.get("triage_enabled", False)),
        triage_model=str(cfg.get("triage_model", "claude-sonnet-4-6")),
        triage_axes_yaml=(Path(__file__).parent / "triage" / "research_axes.yaml")
            if cfg.get("triage_enabled") else None,
        triage_threshold=float(cfg.get("triage_threshold", 0.4)),
    )
```

Add `from typing import Any` if not present.

- [ ] **Step 3: Dry-run verification**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run arxiv --tier=tier_1 --limit=2 --dry-run 2>&1 | head -3
```

Expected: prints `DRY RUN: source=arxiv, terms=[...], window=..., limit=2`.

- [ ] **Step 4: Run full test suite — nothing should break**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/config/sources.yaml harvester/harvester/cli.py
git commit -m "feat(harvester): wire arxiv into sources.yaml + CLI

sources.yaml: adds arxiv source with categories (cs.AI/LG/CL, stat.ML,
econ.GN/EM, math.OC, stat.AP), tier_1 keywords migrated from
~/.wintermute/sources/paper_keywords.yaml, triage_enabled=true with
threshold 0.4, scout_base_url=https://arxiv.org.

cli.py: generalizes query construction — FR keeps its (term+type+date)
shape; non-FR sources get (categories + keyword). RunnerConfig now
threads triage_enabled / triage_model / triage_axes_yaml /
triage_threshold from per-source config.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: CLI `harvester compare-sources` for parallel-run verification

**Files:**
- Modify: `harvester/harvester/cli.py`
- Create: `harvester/tests/test_cli_compare_sources.py`

- [ ] **Step 1: Write failing test**

Create `harvester/tests/test_cli_compare_sources.py`:

```python
"""Tests for harvester compare-sources CLI."""

import subprocess
import pytest

from harvester.db import get_connection


@pytest.fixture
def staged_compare_fixtures():
    """Insert synthetic data for two side-by-side sources:
    legacy arxiv_search staged via Wintermute pre-existing path (simulated as a
    source_id), and the new harvester arxiv source. Compare-sources should
    report diff stats."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id IN ('cmp_old', 'cmp_new')")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id IN ('cmp_old', 'cmp_new')")
            # 10 docs for 'cmp_old', 9 of which overlap with 'cmp_new' (which has 11 total)
            for i in range(10):
                cur.execute(
                    "INSERT INTO harvest.document_metadata (source_id, title, source_url, published_date) "
                    "VALUES ('cmp_old', %s, %s, current_date)",
                    (f"Paper {i}", f"https://arxiv.org/abs/2026.0{i}"),
                )
            for i in range(1, 12):  # 1..11 (overlaps 1..9 with old)
                cur.execute(
                    "INSERT INTO harvest.document_metadata (source_id, title, source_url, published_date) "
                    "VALUES ('cmp_new', %s, %s, current_date)",
                    (f"Paper {i}", f"https://arxiv.org/abs/2026.0{i}"),
                )
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id IN ('cmp_old', 'cmp_new')")
        conn.commit()
    finally:
        conn.close()


def test_compare_sources_reports_overlap_and_diff(staged_compare_fixtures):
    result = subprocess.run(
        ["uv", "run", "harvester", "compare-sources", "cmp_old", "cmp_new",
         "--days", "1"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout
    # 10 in old, 11 in new, 9 in both, 1 only-in-old, 2 only-in-new
    assert "old:" in out and "10" in out
    assert "new:" in out and "11" in out
    assert "both:" in out and "9" in out
    assert "only-in-old:" in out and "1" in out
    assert "only-in-new:" in out and "2" in out
```

- [ ] **Step 2: Verify failure (subcommand doesn't exist)**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_compare_sources.py -v
```

Expected: subprocess non-zero return.

- [ ] **Step 3: Add `compare-sources` subcommand to cli.py**

Append this command function to `harvester/harvester/cli.py` (after the existing `validate` command):

```python
@app.command("compare-sources")
def compare_sources(
    old: str = typer.Argument(..., help="Legacy source_id (e.g., 'arxiv_search_papers')"),
    new: str = typer.Argument(..., help="New source_id (e.g., 'arxiv')"),
    days: int = typer.Option(3, "--days", help="Window in days back from now"),
) -> None:
    """Compare staged-doc volume + overlap between two source_ids.

    Used during the Phase 2 (and future migration) verification windows where
    the legacy script and the new harvester fetcher both run in parallel.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH
                  old_urls AS (
                    SELECT source_url FROM harvest.document_metadata
                    WHERE source_id = %s AND created_at > now() - make_interval(days => %s)
                  ),
                  new_urls AS (
                    SELECT source_url FROM harvest.document_metadata
                    WHERE source_id = %s AND created_at > now() - make_interval(days => %s)
                  )
                SELECT
                  (SELECT count(*) FROM old_urls) AS old_count,
                  (SELECT count(*) FROM new_urls) AS new_count,
                  (SELECT count(*) FROM old_urls o JOIN new_urls n USING (source_url)) AS both_count,
                  (SELECT count(*) FROM old_urls WHERE source_url NOT IN (SELECT source_url FROM new_urls)) AS only_old,
                  (SELECT count(*) FROM new_urls WHERE source_url NOT IN (SELECT source_url FROM old_urls)) AS only_new
                """,
                (old, days, new, days),
            )
            row = cur.fetchone()
            old_n, new_n, both, only_old, only_new = row

        typer.echo(f"=== compare-sources over last {days} days ===")
        typer.echo(f"  old: {old} → {old_n} docs")
        typer.echo(f"  new: {new} → {new_n} docs")
        typer.echo(f"  both: {both} (overlap)")
        typer.echo(f"  only-in-old: {only_old}")
        typer.echo(f"  only-in-new: {only_new}")
        if old_n > 0:
            coverage = both / old_n
            typer.echo(f"  new-vs-old coverage: {coverage:.1%}  (target ≥95% for cutover)")
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_compare_sources.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Verify --help shows new command**

```bash
uv run harvester --help
```

Expected: 6 commands (migrate, scout, run, status, validate, compare-sources).

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/cli.py harvester/tests/test_cli_compare_sources.py
git commit -m "feat(harvester): \`harvester compare-sources\` CLI

Reports old vs new doc counts, overlap, and per-side exclusives over a
configurable window. Used during the Phase 2 3-day verification window
(and future source migrations) to gate the cutover decision: target
≥95% coverage of legacy URLs from the new harvester source.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Launchd wrapper + plist for harvest_arxiv

**Files:**
- Create: `~/.wintermute/scripts/jobs/harvest_arxiv.sh`
- Create: `~/Library/LaunchAgents/com.wintermute.harvest-arxiv.plist`
- Create: `ops/launchd/harvest_arxiv.sh` (copy for repo provenance)
- Create: `ops/launchd/com.wintermute.harvest-arxiv.plist` (copy for repo provenance)

- [ ] **Step 1: Write the wrapper**

Create `~/.wintermute/scripts/jobs/harvest_arxiv.sh`:

```bash
#!/usr/bin/env bash
# Daily arxiv harvest at 23:00 local. Parallel to legacy search_papers.sh
# until Phase 2 cutover.

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_arxiv -- \
    "$UV_BIN" run harvester run arxiv --tier=tier_1
```

```bash
chmod +x /Users/brock/.wintermute/scripts/jobs/harvest_arxiv.sh
```

- [ ] **Step 2: Write the plist**

Create `~/Library/LaunchAgents/com.wintermute.harvest-arxiv.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wintermute.harvest-arxiv</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/brock/.wintermute/scripts/jobs/harvest_arxiv.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>23</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_arxiv.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_arxiv.launchd.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/brock/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 3: Lint + smoke-test the wrapper manually**

```bash
plutil -lint /Users/brock/Library/LaunchAgents/com.wintermute.harvest-arxiv.plist
bash /Users/brock/.wintermute/scripts/jobs/harvest_arxiv.sh
tail -20 /Users/brock/.wintermute/logs/cron/harvest_arxiv.log
```

Expected: plist OK, wrapper completes (likely with deposits=0 if the harvester sees seen URLs from a previous test, or actual deposits on first run).

Note: this is a LIVE run — it will hit arxiv API + call Claude for triage on each paper. Cost: roughly $0.50–$2 depending on volume (Claude Sonnet at ~$3/$15 per million tokens, papers are short).

- [ ] **Step 4: Load the launchd plist**

```bash
launchctl unload /Users/brock/Library/LaunchAgents/com.wintermute.harvest-arxiv.plist 2>/dev/null
launchctl load /Users/brock/Library/LaunchAgents/com.wintermute.harvest-arxiv.plist
launchctl list | grep harvest-arxiv
```

Expected: loaded entry.

- [ ] **Step 5: Copy to ops/ for reproducibility, commit**

```bash
mkdir -p /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd
cp /Users/brock/Library/LaunchAgents/com.wintermute.harvest-arxiv.plist \
   /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd/
cp /Users/brock/.wintermute/scripts/jobs/harvest_arxiv.sh \
   /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd/

cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add ops/launchd/com.wintermute.harvest-arxiv.plist ops/launchd/harvest_arxiv.sh
git commit -m "ops: launchd wrapper + plist for nightly arxiv harvest

Daily at 23:00 local. Runs in parallel to the legacy search_papers
schedule for the 3-day Phase 2 verification window, then becomes
canonical at cutover.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Start the 3-day parallel-run verification

**No code changes.** This task arms the parallel run and establishes the verification protocol. Operationally:

- [ ] **Step 1: Confirm legacy search_papers schedule is still active**

```bash
launchctl list | grep search-papers
plutil -p /Users/brock/Library/LaunchAgents/com.wintermute.search-papers.plist | grep -A2 StartCalendarInterval
```

Expected: loaded entry + a scheduled time.

- [ ] **Step 2: Mark the start of the verification window**

Write a note to track the window. Create `docs/superpowers/notes/phase2-parallel-window.md`:

```markdown
# Phase 2 Parallel-Run Window

**Started:** YYYY-MM-DD HH:MM EDT (fill in)

**Endpoints:**
- Old: `~/.wintermute/scripts/search_papers.py` via existing launchd → staged with source_id varying ("arxiv_paper" in frontmatter; check schema)
- New: `harvester run arxiv` via `com.wintermute.harvest-arxiv` plist → source_id="arxiv"

**Cutover criteria (all must hold for 3 consecutive days):**
1. `harvester compare-sources <legacy_source_id> arxiv --days 1` shows new-vs-old coverage ≥ 95%
2. Triage Spearman correlation > 0.85 on a 50-doc sample (computed offline)
3. No `status='failed'` runs in `harvest.run_log` for `source_id='arxiv'`
4. No regressions in existing FR pipeline

**Daily check command:**
```bash
uv run harvester status
uv run harvester compare-sources <legacy_source_id> arxiv --days 1
psql -d wintermute -c "SELECT score, count(*) FROM harvest.triage_results WHERE doc_id IN (SELECT doc_id FROM harvest.document_metadata WHERE source_id='arxiv' AND created_at > now() - interval '24 hours') GROUP BY score ORDER BY score DESC"
```

**End of window:** YYYY-MM-DD (start + 3 days). Decide cutover or extend.
```

Fill in the actual start datetime. You'll need to determine the legacy source_id by inspecting an existing staged file:

```bash
head -20 "$(ls -t ~/.wintermute/staging/2026-*/wm-*.md 2>/dev/null | head -1)"
```

Look for `source_type:` in the frontmatter; that's likely the legacy source_id. Update the doc accordingly.

- [ ] **Step 3: Commit the parallel-window note**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add docs/superpowers/notes/phase2-parallel-window.md
git commit -m "docs: Phase 2 parallel-run verification window note

Tracks start time, endpoints, cutover criteria, daily check commands.
3-day window per the 37% rule (7-day observation → 3-day decision).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Cutover — sunset legacy scripts (PERFORM AFTER 3-day window passes)

**Do not execute Task 12 in the same session as Tasks 1–11.** Wait for the parallel-run window to produce 3 consecutive days of green compare-sources output and a green triage-correlation check.

**Files:**
- Move: `~/.wintermute/scripts/search_papers.py` → `~/.wintermute/scripts/_sunset/YYYY-MM-DD-search_papers.py`
- Move: `~/.wintermute/tools/arxiv_llm_triage.py` → `~/.wintermute/scripts/_sunset/YYYY-MM-DD-arxiv_llm_triage.py`
- Move: `~/.wintermute/sources/paper_keywords.yaml` → `~/.wintermute/scripts/_sunset/YYYY-MM-DD-paper_keywords.yaml`

- [ ] **Step 1: Verify cutover criteria one final time**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester compare-sources <legacy_source_id> arxiv --days 3
```

Expected: `new-vs-old coverage: ≥95%`. If below, do NOT proceed — investigate first.

```bash
psql -d wintermute -c "SELECT status, count(*) FROM harvest.run_log WHERE source_id='arxiv' AND started_at > now() - interval '3 days' GROUP BY status"
```

Expected: only `completed` rows.

- [ ] **Step 2: Disable legacy launchd jobs**

```bash
launchctl unload /Users/brock/Library/LaunchAgents/com.wintermute.search-papers.plist
launchctl list | grep search-papers
```

Expected: legacy entry gone from the list.

- [ ] **Step 3: Move legacy scripts to `_sunset/`**

```bash
TODAY=$(date '+%Y-%m-%d')
mkdir -p /Users/brock/.wintermute/scripts/_sunset
mv /Users/brock/.wintermute/scripts/search_papers.py \
   /Users/brock/.wintermute/scripts/_sunset/${TODAY}-search_papers.py
mv /Users/brock/.wintermute/tools/arxiv_llm_triage.py \
   /Users/brock/.wintermute/scripts/_sunset/${TODAY}-arxiv_llm_triage.py
mv /Users/brock/.wintermute/sources/paper_keywords.yaml \
   /Users/brock/.wintermute/scripts/_sunset/${TODAY}-paper_keywords.yaml
ls /Users/brock/.wintermute/scripts/_sunset/
```

Expected: three files listed.

- [ ] **Step 4: Check for stragglers — anywhere these scripts are referenced**

```bash
grep -rE "search_papers|arxiv_llm_triage|paper_keywords" \
  ~/.wintermute/ \
  /Users/brock/Documents/GitHub/measuring-ai-economy/ \
  2>/dev/null \
  | grep -v -E "_sunset/|\.git/|\.venv/|tests/fixtures/|node_modules/" \
  | head -20
```

Expected: zero matches (or only matches inside the spec/plan docs themselves, which is fine).

If non-fixture/non-spec references are found, update them to point at the harvester equivalents (or remove them) before proceeding.

- [ ] **Step 5: Drain the existing inbox if anything is queued**

```bash
ls ~/.wintermute/inbox/ 2>/dev/null | head -5
```

- [ ] **Step 6: Commit the sunset action documentation**

Update the `phase2-parallel-window.md` note with the cutover date:

```bash
echo "
**Cutover completed:** YYYY-MM-DD HH:MM EDT
- Legacy launchd disabled: com.wintermute.search-papers
- Legacy scripts moved to ~/.wintermute/scripts/_sunset/
- paper_keywords.yaml content lives in sources.yaml under arxiv.tier_1_terms
- After 7 days post-cutover stable: move to ~/.wintermute/scripts/_sunset/_archive/" >> docs/superpowers/notes/phase2-parallel-window.md

cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add docs/superpowers/notes/phase2-parallel-window.md
git commit -m "docs: Phase 2 cutover completed — legacy scripts sunsetted

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: 7-day post-cutover stability monitor (ongoing duty)

Not a code task. Each morning for 7 days after Task 12 cutover:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester status
psql -d wintermute -c "
SELECT date_trunc('day', started_at) AS day,
       count(*) AS runs,
       sum(items_fetched) AS fetched,
       sum(items_deposited) AS deposited,
       sum(items_failed) AS failed
FROM harvest.run_log
WHERE source_id='arxiv'
  AND started_at > now() - interval '7 days'
GROUP BY 1 ORDER BY 1 DESC;
"
tail -5 ~/.wintermute/logs/cron/harvest_arxiv.log
```

Acceptance: 7 consecutive daily runs with `status='completed'` and `items_failed=0`.

If anything breaks during the 7-day window:
1. `psql -d wintermute -c "SELECT id, error FROM harvest.run_log WHERE source_id='arxiv' AND status='failed' ORDER BY id DESC LIMIT 3"`
2. Reproduce locally
3. Fix on a follow-up branch (`fix/harvester-arxiv-<issue>`)
4. Don't merge to main until 7-day window resets clean

After 7 days stable: Phase 2 is complete. Move `_sunset/` files to `_sunset/_archive/`. Plan Phase 3.

---

## Self-Review

**1. Spec coverage** — every Phase 2 deliverable from §7 of the evolution spec maps to one or more tasks:

| Spec Phase 2 deliverable | Tasks |
|---|---|
| ArxivFetcher + ArxivETL + golden samples (4 paper types) | Tasks 4, 5 |
| Migration 005 (arxiv_papers analytical table) | Task 3 |
| LlmTriage migrated + integrated runner hook | Tasks 6, 7 |
| Migration 004 (self-improvement tables — partial Phase 2 use) | Task 2 |
| 3-day parallel verification | Tasks 9 (compare-sources tooling), 11 (kickoff) |
| Cutover (sunset old script, fold paper_keywords.yaml into sources.yaml) | Tasks 8 (sources.yaml), 12 (sunset moves) |
| Launchd plist + wrapper for harvest_arxiv | Task 10 |

**2. Placeholder scan** — none. Every step has either real code, real commands, or real text content. Task 11 leaves date placeholders (`YYYY-MM-DD`) intentionally — those are operational dates filled at execution time, not plan-author TODOs.

**3. Type consistency** — verified:
- `ArxivFetcher` (Task 4) implements `iter_payloads(query, *, seen=None)` matching the parent `Fetcher` ABC.
- `ArxivETL.parse(raw) → ParsedDoc` (Task 5) matches the `ETL` ABC contract; `expected_schema_version = 5` matches migration 005 number.
- `LlmTriage.score(parsed) → TriageResult` (Task 6) signature is consistent with the runner triage hook (Task 7).
- `TriageResult.score` (float), `axes` (dict[str, float]), `rubric_version`, `model_id`, `prompt_hash` — used identically in Tasks 6 and 7.
- `RunnerConfig` field additions (`triage_enabled`, `triage_model`, `triage_axes_yaml`, `triage_threshold`) — defined in Task 7, threaded by Task 8's CLI changes.
- `compare-sources` SQL (Task 9) joins on `source_url`, which matches the unique key on `harvest.document_metadata (source_id, source_url)` from migration 001.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-harvester-phase2-arxiv.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Tasks 1–10 are the build; Tasks 11–13 are operational (run by user over 10 days).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
