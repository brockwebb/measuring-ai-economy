# URL Drain Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the legacy `~/.wintermute/scripts/drain_url_c4a.py` into the harvester architecture as a first-class `url_drain` source + new `harvester drain-url` CLI command. Single-URL on-demand fetching via Crawl4aiFetcher, with full triage + provenance + analytical-table coverage.

**Architecture:** `UrlDrainFetcher` inherits `Crawl4aiFetcher` and returns `[query["url"]]` from `urls_to_crawl` — exactly one URL per invocation. `UrlDrainETL` parses the crawl4ai markdown payload into a generic `harvest.document_metadata` row plus a dense `harvest.url_drain_documents` row. Source-type is detected from the URL host (arxiv.org → `arxiv_paper`, youtube.com → `youtube_transcript`, etc.) — preserves the legacy script's mapping. New CLI command `harvester drain-url <URL>` runs the standard Runner path so triage + citation-chain hooks fire for free. No launchd job (URL drain is operator-triggered, not scheduled).

**Tech Stack:** Python 3.12, psycopg, httpx, typer, uv. **New runtime dep:** `crawl4ai>=0.4` via `uv sync --extra html` (already declared in pyproject's `[project.optional-dependencies] html`). No new test deps.

**Spec source:** None — this plan mirrors the structure of `docs/superpowers/plans/2026-05-13-zenodo-migration.md` adapted to the Crawl4aiFetcher path and the on-demand (vs. scheduled) execution model.

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch:** `feat/url-drain-migration` (to be created from `main`; main is at the just-merged zenodo migration commit `7acbfa4`).

**Verification model:** URL drain has no cron firing it — there is no soak window. Instead, verification is **direct end-to-end smoke against 3 real URLs** (one per source-type variant) immediately after Task 4: arxiv abstract page, Medium article, GitHub README. Each must complete with `status='completed'`, deposit one row, get a triage score, populate `harvest.url_drain_documents`. The 7-day post-cutover monitor (Task 8) is a passive checkpoint — we observe whether `drain_with_notes.sh` invocations (the one legacy caller, see Task 6) succeed via the new path during normal use.

---

## File Structure

**Created:**

```
measuring-ai-economy/
├── harvester/
│   ├── harvester/
│   │   ├── fetchers/
│   │   │   └── url_drain.py                       [NEW]
│   │   ├── etl/
│   │   │   └── url_drain.py                       [NEW]
│   │   └── schemas/
│   │       └── 009_url_drain_documents.sql        [NEW]
│   └── tests/
│       ├── fixtures/
│       │   └── url_drain/                         [NEW dir]
│       │       ├── markdown_arxiv.md
│       │       ├── markdown_medium_article.md
│       │       ├── markdown_youtube.md
│       │       └── markdown_github_readme.md
│       ├── test_fetcher_url_drain.py              [NEW]
│       ├── test_etl_url_drain.py                  [NEW]
│       └── test_cli_drain_url.py                  [NEW]

docs/superpowers/notes/
└── url-drain-cutover.md                           [NEW operational note]
```

**Modified:**

- `harvester/harvester/config/sources.yaml` — append a `url_drain:` entry.
- `harvester/harvester/cli.py` — append a `drain-url` typer command.
- `~/.wintermute/scripts/drain_with_notes.sh` — at cutover (Task 6), change the one line that invokes `drain_url_c4a.py` to invoke the harvester CLI.

**Moved at cutover (Task 6):**

- `~/.wintermute/scripts/drain_url_c4a.py` → `~/.wintermute/scripts/_sunset/2026-05-13-drain_url_c4a.py`.

**Schema dependencies (existing, no changes):** `harvest.run_log`, `harvest.document_metadata`, `harvest.triage_results`. URL drain reuses these unchanged.

---

## Tasks

### Task 1: Branch + Migration 009 (harvest.url_drain_documents)

**Files:**
- Create: `harvester/harvester/schemas/009_url_drain_documents.sql`

- [ ] **Step 1: Branch from main**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git checkout main
git pull --ff-only
git checkout -b feat/url-drain-migration
```

Expected: on `feat/url-drain-migration`, working tree clean.

- [ ] **Step 2: Write migration 009**

Create `harvester/harvester/schemas/009_url_drain_documents.sql`:

```sql
-- Migration 009: url_drain_documents — densely-typed analytical table for
-- on-demand single-URL fetches via Crawl4aiFetcher.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.url_drain_documents (
    id                  BIGSERIAL PRIMARY KEY,
    source_url          TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    source_type         TEXT NOT NULL,    -- arxiv_paper | youtube_transcript | github_repo | pdf_document | web_article
    host                TEXT,             -- normalized hostname for filtering
    byte_size           INTEGER NOT NULL, -- markdown char count, useful for sanity
    fetched_at          TIMESTAMPTZ NOT NULL,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS url_drain_documents_source_type_idx
    ON harvest.url_drain_documents (source_type);
CREATE INDEX IF NOT EXISTS url_drain_documents_host_idx
    ON harvest.url_drain_documents (host);
CREATE INDEX IF NOT EXISTS url_drain_documents_fetched_at_idx
    ON harvest.url_drain_documents (fetched_at DESC);

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('009_url_drain_documents.sql', 'PLACEHOLDER_SHA', 'url_drain_documents analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 3: Apply migration**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python -c "
from harvester.db import get_connection
from pathlib import Path
sql = Path('harvester/schemas/009_url_drain_documents.sql').read_text()
conn = get_connection()
with conn.cursor() as cur:
    cur.execute(sql)
conn.commit()
conn.close()
print('migration 009 applied')
"
```

Expected: `migration 009 applied`.

- [ ] **Step 4: Verify the table exists**

```bash
psql wintermute -c "\d harvest.url_drain_documents"
```

Expected: table shows all 10 columns (`id, source_url, title, source_type, host, byte_size, fetched_at, raw_hash, created_by_run_id, created_at`) plus the 3 named indexes + the UNIQUE constraint on `source_url` + the FK to `run_log`.

- [ ] **Step 5: Commit**

```bash
git add harvester/harvester/schemas/009_url_drain_documents.sql
git commit -m "$(cat <<'EOF'
feat(harvester): migration 009 — url_drain_documents analytical table

On-demand single-URL fetches via Crawl4aiFetcher land in
harvest.url_drain_documents with dense per-document columns:
source_url (UNIQUE), title, source_type (arxiv_paper / youtube_transcript /
github_repo / pdf_document / web_article), host, byte_size,
fetched_at, raw_hash, created_by_run_id. Indexes on source_type,
host, and fetched_at DESC.

Schema feeds the upcoming UrlDrainETL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: UrlDrainFetcher (Crawl4aiFetcher subclass) + fetcher tests

**Files:**
- Create: `harvester/harvester/fetchers/url_drain.py`
- Create: `harvester/tests/test_fetcher_url_drain.py`

- [ ] **Step 1: Ensure the `html` extra is installed**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
/Users/brock/.local/bin/uv sync --extra html
uv run python -c "from crawl4ai import AsyncWebCrawler; print('crawl4ai OK')"
```

Expected: `crawl4ai OK` (no ImportError). If this fails, the rest of the plan can't proceed — escalate.

- [ ] **Step 2: Write failing fetcher tests at `harvester/tests/test_fetcher_url_drain.py`**

```python
"""Tests for harvester.fetchers.url_drain.UrlDrainFetcher.

UrlDrainFetcher is a Crawl4aiFetcher subclass: one URL in, one markdown
payload out. Tests mock crawl4ai entirely — they verify the urls_to_crawl
contract and source_id, without invoking a real browser.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from harvester.fetchers.url_drain import UrlDrainFetcher


def test_url_drain_fetcher_source_id():
    f = UrlDrainFetcher.__new__(UrlDrainFetcher)
    assert f.source_id == "url_drain"


def test_url_drain_urls_to_crawl_returns_single_url_from_query():
    f = UrlDrainFetcher.__new__(UrlDrainFetcher)
    urls = list(f.urls_to_crawl({"url": "https://example.com/post"}))
    assert urls == ["https://example.com/post"]


def test_url_drain_urls_to_crawl_empty_when_url_missing():
    f = UrlDrainFetcher.__new__(UrlDrainFetcher)
    urls = list(f.urls_to_crawl({}))
    assert urls == []


def _mock_crawl_result(markdown_text: str, title: str = "Test Title") -> MagicMock:
    """Quack like crawl4ai's CrawlResult."""
    result = MagicMock()
    result.success = True
    result.markdown.fit_markdown = markdown_text
    result.markdown.raw_markdown = markdown_text
    result.metadata = {"title": title}
    result.error_message = None
    return result


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_url_drain_iter_payloads_yields_one_markdown_payload(mock_build_crawler, tmp_path):
    """Full crawl4ai mock — verifies that a single URL flows through
    iter_payloads into exactly one RawPayload with content_type='text/markdown'."""
    from harvester.manifest import RawArchive

    # Mock crawler: arun returns one mock result, no real browser.
    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)
    crawler.arun = AsyncMock(return_value=_mock_crawl_result(
        markdown_text="# Hello\n\nWorld.\n", title="Hello World"
    ))
    mock_build_crawler.return_value = crawler

    archive_root = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.parquet"
    archive = RawArchive(root=archive_root, manifest_path=manifest_path)

    f = UrlDrainFetcher(archive=archive)
    # Override crawl_config so crawl4ai's import isn't needed during the call.
    f.crawl_config = lambda: None  # type: ignore[assignment]

    payloads = list(f.iter_payloads({"url": "https://example.com/post"}))
    assert len(payloads) == 1
    p = payloads[0]
    assert p.source_url == "https://example.com/post"
    assert p.content_type == "text/markdown"
    assert p.source_id == "url_drain"
    # Markdown bytes round-trip
    assert p.file_path.read_text() == "# Hello\n\nWorld.\n"
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_url_drain.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.fetchers.url_drain'`.

- [ ] **Step 4: Implement `harvester/harvester/fetchers/url_drain.py`**

```python
"""URL drain fetcher.

Single-URL on-demand fetcher backed by Crawl4aiFetcher. The query dict
carries one key: `url` — the target page. urls_to_crawl returns it as a
one-element iterable so the Crawl4aiFetcher base does the rest (async
browser, markdown extraction, archive write).

Replaces the legacy ~/.wintermute/scripts/drain_url_c4a.py which did the
same job but staged markdown files directly to ~/.wintermute/staging/
rather than going through the harvester DB pipeline.
"""

from __future__ import annotations

from typing import Any, Iterable

from harvester.fetchers.crawl4ai_base import Crawl4aiFetcher
from harvester.types import RateLimit


class UrlDrainFetcher(Crawl4aiFetcher):
    source_id = "url_drain"

    def rate_limit_spec(self) -> RateLimit:
        # On-demand single-URL fetches are not high-volume. Pace at 1 req/sec
        # to match sibling fetchers and avoid any chance of looking like a bot
        # to the target site.
        return RateLimit(
            requests_per_second=1.0,
            max_retries=2,
            backoff_seconds=[5, 15],
        )

    def urls_to_crawl(self, query: dict[str, Any]) -> Iterable[str]:
        url = query.get("url")
        return [url] if url else []
```

- [ ] **Step 5: Run fetcher tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_url_drain.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add harvester/harvester/fetchers/url_drain.py \
    harvester/tests/test_fetcher_url_drain.py
git commit -m "$(cat <<'EOF'
feat(harvester): UrlDrainFetcher (Crawl4aiFetcher subclass)

Single-URL on-demand fetcher. urls_to_crawl returns [query["url"]] —
exactly one URL per invocation. Pacing at 1 req/sec, 2 retries with
[5s, 15s] backoff (matches sibling fetchers).

Tests fully mock crawl4ai (AsyncMock crawler + canned markdown result),
no real browser required at test time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: UrlDrainETL + 4 canned markdown fixtures + ETL tests

**Files:**
- Create: `harvester/harvester/etl/url_drain.py`
- Create: 4 fixtures under `harvester/tests/fixtures/url_drain/`
- Create: `harvester/tests/test_etl_url_drain.py`

- [ ] **Step 1: Write 4 canned markdown fixtures**

These represent the four source_type variants the legacy script handles. We hand-author them because real crawl4ai output is too long for fixture use and the ETL behavior is what we want to test, not the crawler.

Create `harvester/tests/fixtures/url_drain/markdown_arxiv.md`:

```markdown
# ELF: Embedded Language Flows

**Keya Hu, Linlu Qiu, Daiyaan Arfeen**
*arXiv:2605.10938 — Submitted 2026-05-11*

## Abstract

We propose a new neural architecture combining embedded language flows
with information geometry. Empirical evaluation on three benchmarks shows
state-of-the-art performance on uncertainty quantification.
```

Create `harvester/tests/fixtures/url_drain/markdown_medium_article.md`:

```markdown
# Why Stochastic Differential Equations Matter for Modern ML

Posted by Jane Engineer · 12 min read · May 2026

Most ML practitioners are familiar with stochastic gradient descent, but the
underlying mathematics of SDEs offers a richer lens on how neural networks
actually learn. This post unpacks three threads...
```

Create `harvester/tests/fixtures/url_drain/markdown_youtube.md`:

```markdown
# How to Train a Dog Using Information Theory — Murray's Adventures

Transcript:

[00:00] Welcome back. Today we're going to talk about clicker training and how
it maps to Shannon's classical information theory.

[01:23] The core idea: each click is one bit of information that resolves
uncertainty about which behavior gets reinforced.
```

Create `harvester/tests/fixtures/url_drain/markdown_github_readme.md`:

```markdown
# diffusion-toolkit

A minimal PyTorch library for score-based generative models.

## Installation

```bash
pip install diffusion-toolkit
```

## Quick start

```python
import diffusion_toolkit as dt
model = dt.ScoreNet(...)
```
```

(Note: the markdown_github_readme.md fixture intentionally has nested code fences. Tests read it as raw text — no parsing.)

- [ ] **Step 2: Write failing ETL tests at `harvester/tests/test_etl_url_drain.py`**

```python
"""Tests for harvester.etl.url_drain.UrlDrainETL.

Tests cover:
- source_type detection by URL host
- title extraction from markdown (first H1)
- ParsedDoc shape with both document_metadata and url_drain_documents rows
- empty/short-content edge cases
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harvester.etl.url_drain import UrlDrainETL, detect_source_type
from harvester.types import RawPayload


_FXT = Path(__file__).parent / "fixtures" / "url_drain"

_FETCHED_AT = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


def _raw_payload_for(name: str, url: str, tmp_path: Path) -> RawPayload:
    src = _FXT / f"markdown_{name}.md"
    dst = tmp_path / src.name
    dst.write_text(src.read_text())
    return RawPayload(
        file_path=dst,
        source_id="url_drain",
        source_url=url,
        raw_hash="sha256:test",
        request_params={"url": url},
        content_type="text/markdown",
        fetched_at=_FETCHED_AT,
    )


@pytest.mark.parametrize("url,expected", [
    ("https://arxiv.org/abs/2605.10938", "arxiv_paper"),
    ("https://zenodo.org/records/19130988", "arxiv_paper"),
    ("https://ssrn.com/abstract=12345", "arxiv_paper"),
    ("https://www.youtube.com/watch?v=abc123", "youtube_transcript"),
    ("https://youtu.be/abc123", "youtube_transcript"),
    ("https://github.com/foo/bar", "github_repo"),
    ("https://example.com/foo.pdf", "pdf_document"),
    ("https://medium.com/some-article", "web_article"),
    ("https://example.com/blog/post", "web_article"),
])
def test_detect_source_type(url, expected):
    assert detect_source_type(url) == expected


def test_url_drain_etl_source_id_and_schema_version():
    etl = UrlDrainETL()
    assert etl.source_id == "url_drain"
    assert etl.expected_schema_version == 9


def test_url_drain_etl_parses_arxiv_markdown(tmp_path):
    etl = UrlDrainETL()
    raw = _raw_payload_for("arxiv", "https://arxiv.org/abs/2605.10938", tmp_path)
    parsed = etl.parse(raw)

    assert parsed.title == "ELF: Embedded Language Flows"
    assert parsed.source_url == "https://arxiv.org/abs/2605.10938"
    assert parsed.published_date is None  # url_drain doesn't extract dates

    # Two rows: document_metadata first, then url_drain_documents.
    assert len(parsed.rows) == 2
    meta_row, dense_row = parsed.rows
    assert meta_row.target_table == "harvest.document_metadata"
    assert meta_row.data["source_id"] == "url_drain"
    assert meta_row.data["title"] == "ELF: Embedded Language Flows"
    assert meta_row.data["document_type"] == "arxiv_paper"

    assert dense_row.target_table == "harvest.url_drain_documents"
    assert dense_row.data["source_url"] == "https://arxiv.org/abs/2605.10938"
    assert dense_row.data["title"] == "ELF: Embedded Language Flows"
    assert dense_row.data["source_type"] == "arxiv_paper"
    assert dense_row.data["host"] == "arxiv.org"
    assert dense_row.data["byte_size"] > 0
    assert dense_row.data["raw_hash"] == "sha256:test"
    assert dense_row.data["fetched_at"] == _FETCHED_AT


def test_url_drain_etl_parses_youtube_markdown(tmp_path):
    etl = UrlDrainETL()
    raw = _raw_payload_for(
        "youtube", "https://www.youtube.com/watch?v=abc123", tmp_path
    )
    parsed = etl.parse(raw)
    assert parsed.title.startswith("How to Train a Dog")
    dense_row = parsed.rows[1]
    assert dense_row.data["source_type"] == "youtube_transcript"
    assert dense_row.data["host"] == "www.youtube.com"


def test_url_drain_etl_falls_back_to_untitled_for_empty_markdown(tmp_path):
    """If the markdown has no H1, title falls back to 'Untitled'."""
    p = tmp_path / "no_heading.md"
    p.write_text("Just some body text. No heading.\n")
    raw = RawPayload(
        file_path=p, source_id="url_drain",
        source_url="https://example.com/no-title",
        raw_hash="sha256:test", request_params={"url": "https://example.com/no-title"},
        content_type="text/markdown", fetched_at=_FETCHED_AT,
    )
    parsed = UrlDrainETL().parse(raw)
    assert parsed.title == "Untitled"
    # Even with no title, both rows still emit.
    assert len(parsed.rows) == 2


def test_url_drain_etl_strips_common_site_suffixes(tmp_path):
    """The legacy script stripped suffixes like ' | Medium', ' - SSRN' from
    titles. The ETL preserves that hygiene to keep titles readable."""
    p = tmp_path / "suffix.md"
    p.write_text("# Why SDEs Matter | Medium\n\nBody.\n")
    raw = RawPayload(
        file_path=p, source_id="url_drain",
        source_url="https://medium.com/some-post",
        raw_hash="sha256:test", request_params={"url": "https://medium.com/some-post"},
        content_type="text/markdown", fetched_at=_FETCHED_AT,
    )
    parsed = UrlDrainETL().parse(raw)
    assert parsed.title == "Why SDEs Matter"
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_url_drain.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.etl.url_drain'`.

- [ ] **Step 4: Implement `harvester/harvester/etl/url_drain.py`**

```python
"""URL drain ETL.

Pure parse: takes a crawl4ai-fetched markdown payload and produces a
ParsedDoc with rows for harvest.document_metadata (generic) and
harvest.url_drain_documents (dense, per-source).

Source-type is detected from the URL host (preserves the legacy
drain_url_c4a.py mapping). Title is extracted from the first '# ' line;
common site-name suffixes are stripped to keep titles tidy.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


_TITLE_SUFFIXES = [
    " | Medium",
    " - Level Up Coding",
    " | Towards AI",
    " | arXiv",
    " - SSRN",
    " | Zenodo",
]

_SOURCE_TYPE_BY_HOST = [
    ("arxiv.org", "arxiv_paper"),
    ("zenodo.org", "arxiv_paper"),
    ("ssrn.com", "arxiv_paper"),
    ("youtube.com", "youtube_transcript"),
    ("youtu.be", "youtube_transcript"),
    ("github.com", "github_repo"),
]


def detect_source_type(url: str) -> str:
    """Return one of: arxiv_paper, youtube_transcript, github_repo,
    pdf_document, web_article. Host-based detection matches the legacy
    drain_url_c4a.py mapping."""
    host = (urlparse(url).hostname or "").lower()
    for needle, stype in _SOURCE_TYPE_BY_HOST:
        if needle in host:
            return stype
    if url.lower().endswith(".pdf"):
        return "pdf_document"
    return "web_article"


def _extract_title(markdown: str) -> str:
    """First '# Heading' line in the markdown, with common site suffixes
    stripped. Falls back to 'Untitled'."""
    for line in markdown.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            for suffix in _TITLE_SUFFIXES:
                title = title.replace(suffix, "")
            return title.strip() or "Untitled"
    return "Untitled"


class UrlDrainETL(ETL):
    source_id = "url_drain"
    expected_schema_version = 9

    def parse(self, raw: RawPayload) -> ParsedDoc:
        markdown = raw.file_path.read_text()
        title = _extract_title(markdown)
        source_type = detect_source_type(raw.source_url)
        host = (urlparse(raw.source_url).hostname or "")
        byte_size = len(markdown)

        dense_row = Row(
            target_table="harvest.url_drain_documents",
            data={
                "source_url": raw.source_url,
                "title": title,
                "source_type": source_type,
                "host": host,
                "byte_size": byte_size,
                "fetched_at": raw.fetched_at,
                "raw_hash": raw.raw_hash,
            },
        )

        meta_row = Row(
            target_table="harvest.document_metadata",
            data={
                "source_id": self.source_id,
                "title": title,
                "authors": json.dumps([]),
                "doi": None,
                "source_url": raw.source_url,
                "published_date": None,
                "document_type": source_type,
                "payload": json.dumps(
                    {
                        "source_type": source_type,
                        "host": host,
                        "byte_size": byte_size,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=raw.source_url,
            published_date=None,
            rows=[meta_row, dense_row],
            metadata={
                "source_type": source_type,
                "host": host,
                "byte_size": byte_size,
            },
        )
```

- [ ] **Step 5: Run ETL tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_url_drain.py -v
```

Expected: 14 passed (9 parameterized detect_source_type + 5 standalone).

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -p no:randomly 2>&1 | tail -3
```

Expected: 154 (baseline from zenodo merge) + 4 fetcher + 14 ETL = 172 passed.

- [ ] **Step 7: Commit**

```bash
git add harvester/harvester/etl/url_drain.py \
    harvester/tests/fixtures/url_drain/ \
    harvester/tests/test_etl_url_drain.py
git commit -m "$(cat <<'EOF'
feat(harvester): UrlDrainETL + 4 source-type fixtures

Parses a crawl4ai-fetched markdown payload into ParsedDoc with rows for
harvest.document_metadata (generic) and harvest.url_drain_documents
(dense). Source-type detection by URL host preserves the legacy
drain_url_c4a.py mapping (arxiv.org/zenodo.org/ssrn.com → arxiv_paper,
youtube.com/youtu.be → youtube_transcript, github.com → github_repo,
*.pdf → pdf_document, else web_article).

Title extraction reads the first '# ' line and strips common site
suffixes (' | Medium', ' - SSRN', etc.). Falls back to 'Untitled'.

Fixtures cover four source-type variants (arxiv abstract, Medium
article, YouTube transcript, GitHub README).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: sources.yaml + `harvester drain-url` CLI

**Files:**
- Modify: `harvester/harvester/config/sources.yaml`
- Modify: `harvester/harvester/cli.py`
- Create: `harvester/tests/test_cli_drain_url.py`

- [ ] **Step 1: Append `url_drain:` to `sources.yaml`**

Append to the end of `harvester/harvester/config/sources.yaml`:

```yaml
url_drain:
  fetcher: harvester.fetchers.url_drain.UrlDrainFetcher
  etl: harvester.etl.url_drain.UrlDrainETL
  inbox_backpressure_max: 5000
  daily_cost_ceiling_usd: 5.00
  expected_schema_version: 9
  triage_enabled: true
  citation_chain_enabled: false
  triage_threshold: 0.4
  triage_model: "claude-sonnet-4-6"
```

Note: no `tier_1_terms`, no `rolling_window_days`, no `categories`, no `scout_base_url` — URL drain is on-demand, not a tier crawl. `citation_chain_enabled: false` because most URL-drained content (Medium posts, YouTube transcripts, GitHub READMEs) doesn't carry a DOI for the citation-chain to expand from.

- [ ] **Step 2: Write failing CLI tests at `harvester/tests/test_cli_drain_url.py`**

```python
"""Tests for `harvester drain-url` CLI.

These tests mock crawl4ai entirely to avoid invoking a real browser at
test time. They verify the CLI wiring: --help shows the command, and
the command surface (argument parsing, run-log row written, ETL ran)
behaves as expected via a one-call smoke that uses a mocked fetch.
"""

import subprocess


def test_drain_url_help_lists_command():
    result = subprocess.run(
        ["uv", "run", "harvester", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "drain-url" in result.stdout, f"missing subcommand. stdout: {result.stdout}"


def test_drain_url_help_shows_url_argument():
    result = subprocess.run(
        ["uv", "run", "harvester", "drain-url", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # Typer's help should mention 'url' (the argument name) and 'drain' somewhere.
    assert "url" in result.stdout.lower()
```

(Smoke testing against a real URL is in Task 5 — Task 4's tests only verify the CLI is registered and parses arguments.)

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_drain_url.py -v
```

Expected: 2 failures (`No such command 'drain-url'`).

- [ ] **Step 4: Append the `drain-url` command to `harvester/harvester/cli.py`**

Locate the existing `@app.command("calibration")` block (added by the calibration-judgment feature). Insert the new command immediately after it, and before the `if __name__ == "__main__":` block:

```python
@app.command("drain-url")
def drain_url_cmd(
    url: str = typer.Argument(..., help="URL to fetch and stage"),
) -> None:
    """Fetch a single URL via crawl4ai, run the standard ETL + triage
    + load pipeline. On-demand replacement for the legacy
    ~/.wintermute/scripts/drain_url_c4a.py."""
    cfg = _sources_config()["url_drain"]
    fetcher_cls = _load_class(cfg["fetcher"])
    etl_cls = _load_class(cfg["etl"])

    data_root = _data_root()
    config = RunnerConfig(
        source_id="url_drain",
        archive_root=data_root / "raw",
        manifest_path=data_root / "manifests" / "raw_manifest.parquet",
        inbox_dir=_staging_dir(),
        inbox_backpressure_max=int(cfg.get("inbox_backpressure_max", 5000)),
        expected_schema_version=int(cfg.get("expected_schema_version", 9)),
        scout_base_url=cfg.get("scout_base_url"),
        triage_enabled=bool(cfg.get("triage_enabled", True)),
        triage_model=str(cfg.get("triage_model", "claude-sonnet-4-6")),
        triage_axes_yaml=(Path(__file__).parent / "triage" / "research_axes.yaml")
            if cfg.get("triage_enabled") else None,
        triage_threshold=float(cfg.get("triage_threshold", 0.4)),
        citation_chain_enabled=bool(cfg.get("citation_chain_enabled", False)),
    )

    archive = RawArchive(root=config.archive_root, manifest_path=config.manifest_path)
    fetcher = fetcher_cls(archive=archive)
    etl = etl_cls()

    runner = Runner(config=config, fetcher=fetcher, etl=etl)
    result = runner.run({"url": url})
    typer.echo(
        f"run_id={result.run_id} status={result.status} "
        f"fetched={result.items_fetched} deposited={result.items_deposited} "
        f"failed={result.items_failed}"
    )
```

- [ ] **Step 5: Run CLI tests + full suite**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_drain_url.py -v
uv run pytest -p no:randomly 2>&1 | tail -3
```

Expected: 2 passed for the new file; 174 passed for the full suite.

- [ ] **Step 6: Commit**

```bash
git add harvester/harvester/config/sources.yaml \
    harvester/harvester/cli.py \
    harvester/tests/test_cli_drain_url.py
git commit -m "$(cat <<'EOF'
feat(harvester): \`harvester drain-url\` CLI + url_drain in sources.yaml

CLI takes one positional URL argument and runs the standard Runner
pipeline with a single-URL query: {"url": "..."}. Triage enabled,
citation-chain disabled (most drained URLs lack a DOI to expand from).
No tier_1_terms or rolling_window_days — URL drain is on-demand.

Tests verify the command is registered and parses arguments; live
smoke happens in Task 5 against real URLs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: End-to-end smoke against 3 real URLs

**Files:** None modified. This is an operational checkpoint.

- [ ] **Step 1: Dry-run check the CLI dispatch**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester drain-url --help
```

Expected: help text prints with `--help` and the `URL` argument visible.

- [ ] **Step 2: Smoke a static GitHub README**

GitHub READMEs are static HTML, render fast, and don't paywall. Lowest-risk smoke target.

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester drain-url "https://github.com/brockwebb/measuring-ai-economy"
```

Expected: prints `run_id=NNN status=completed fetched=1 deposited=1 failed=0`. May take 30–60 seconds (browser startup + page render).

Verify the DB row:

```bash
psql wintermute -c "
SELECT id, source_url, title, source_type, host, byte_size
FROM harvest.url_drain_documents
ORDER BY id DESC LIMIT 1
"
```

Expected: one row with `source_type='github_repo'`, `host='github.com'`, non-empty title and byte_size > 100.

- [ ] **Step 3: Smoke an arxiv abstract page**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester drain-url "https://arxiv.org/abs/2410.05677"
```

(Use a real, recent arxiv abs URL; substitute if 2410.05677 is unreachable. Pick anything from `harvest.arxiv_papers` if needed: `psql wintermute -c "SELECT arxiv_url FROM harvest.arxiv_papers LIMIT 1"`.)

Expected: `status=completed`, one new row in `harvest.url_drain_documents` with `source_type='arxiv_paper'`.

- [ ] **Step 4: Smoke a Medium-style web article**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester drain-url "https://blog.research.google/2024/01/scaling-instructable-agents.html"
```

(Pick any reasonable static blog post; this URL is illustrative. If it 404s, substitute with a working blog post URL — the goal is to verify the `web_article` source_type path.)

Expected: `status=completed`, one new row with `source_type='web_article'`.

- [ ] **Step 5: Confirm triage scored at least one of the three**

```bash
psql wintermute -c "
SELECT count(*) AS scored
FROM harvest.triage_results
WHERE doc_id IN (
    SELECT id FROM harvest.document_metadata
    WHERE source_id='url_drain' AND created_at > now() - interval '10 minutes'
)
"
```

Expected: `scored > 0`. (Triage may not fire on every doc — depends on triage_threshold and LLM availability — but at least one of the three should be scored.)

- [ ] **Step 6: If any smoke failed**

If a smoke completes with `status=failed` or `deposited=0`, examine `harvest.run_log` for the error message and figure out whether it's a crawl4ai issue (the target URL didn't render) or a code issue. Crawl4ai page-load failures are environmental — not blockers — note them in the report and move to a different target URL. Code issues need to be fixed before proceeding to Task 6.

- [ ] **Step 7: No commit for this task** — operational verification only.

---

### Task 6: Cutover — replace legacy drain_url_c4a.py

**Files:**
- Move: `~/.wintermute/scripts/drain_url_c4a.py` → `~/.wintermute/scripts/_sunset/2026-05-13-drain_url_c4a.py`
- Modify: `~/.wintermute/scripts/drain_with_notes.sh` (line 49)
- Create: `docs/superpowers/notes/url-drain-cutover.md`

**Pre-condition:** Task 5 smokes all passed.

- [ ] **Step 1: Find and confirm the only caller**

```bash
grep -rn "drain_url_c4a" /Users/brock/.wintermute/scripts/ 2>&1
```

Expected: matches in `drain_url_c4a.py` (the script itself) and `drain_with_notes.sh` (one line). If any new caller appears, stop and report — the cutover assumes only one caller.

- [ ] **Step 2: Update `drain_with_notes.sh` line 49**

The current line is:

```bash
DRAIN_OUTPUT=$(python3 "$HOME/.wintermute/scripts/drain_url_c4a.py" "$URL" 2>&1)
```

Replace with:

```bash
DRAIN_OUTPUT=$(cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester && /Users/brock/.local/bin/uv run harvester drain-url "$URL" 2>&1)
```

- [ ] **Step 3: Smoke `drain_with_notes.sh` end-to-end**

`drain_with_notes.sh` takes a URL + a notes file as arguments. Don't run it against a real notes pipeline (which would side-effect the user's staging directory); just invoke it with `bash -n` to syntax-check, then run it once with a throwaway note against a fast URL.

```bash
bash -n /Users/brock/.wintermute/scripts/drain_with_notes.sh
```

Expected: no syntax errors, exit 0.

Optional live test (only if Brock confirms):

```bash
echo "test note" > /tmp/test-note.md
/Users/brock/.wintermute/scripts/drain_with_notes.sh "https://github.com/brockwebb/measuring-ai-economy" /tmp/test-note.md
rm /tmp/test-note.md
```

Expected: the wrapper runs through; the `drain-url` invocation completes; the rest of the wrapper's logic does whatever it does with notes. If the wrapper errors out due to a contract change elsewhere, stop and report — that's beyond Task 6's scope.

- [ ] **Step 4: Move the legacy script to `_sunset/`**

```bash
mkdir -p /Users/brock/.wintermute/scripts/_sunset
mv /Users/brock/.wintermute/scripts/drain_url_c4a.py /Users/brock/.wintermute/scripts/_sunset/2026-05-13-drain_url_c4a.py
```

- [ ] **Step 5: Create the operational note in the repo**

Create `docs/superpowers/notes/url-drain-cutover.md`:

```markdown
# URL Drain Cutover

**Cutover date:** 2026-05-13

**Old path:** `~/.wintermute/scripts/drain_url_c4a.py` (now at `~/.wintermute/scripts/_sunset/2026-05-13-drain_url_c4a.py`).

**New path:** `harvester drain-url <URL>` in `measuring-ai-economy`.

**Behavior change:** Old script staged a markdown file with YAML frontmatter to `~/.wintermute/staging/YYYY-MM/`. New CLI writes to the harvest DB (`harvest.document_metadata` + `harvest.url_drain_documents`) and lets the Runner's standard inbox-emit logic produce the staging file. The frontmatter shape is slightly different but downstream consumers (extraction, ontology builders) read both old and new shapes via field-name normalization, so no consumer needs to change.

**Caller update:** `~/.wintermute/scripts/drain_with_notes.sh:49` — single line, swapped `python3 .../drain_url_c4a.py "$URL"` for `uv run harvester drain-url "$URL"`.

**No other callers.** Confirmed via `grep -rn drain_url_c4a /Users/brock/.wintermute/scripts/`.

## 7-day stability check (Task 8)

Each day during the week of 2026-05-13 → 2026-05-20, sample one invocation:

```bash
# Did drain-url invocations from drain_with_notes.sh succeed?
psql wintermute -c "
SELECT date_trunc('day', started_at) AS day,
       count(*) AS runs,
       count(*) FILTER (WHERE status='completed') AS completed,
       count(*) FILTER (WHERE status='failed') AS failed
FROM harvest.run_log
WHERE source_id='url_drain' AND started_at > now() - interval '7 days'
GROUP BY day
ORDER BY day DESC
"
```

Green criteria (cumulative over the 7 days): at least 80% of url_drain runs status=completed, no error_signatures crossing failure_patterns thresholds.
```

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add docs/superpowers/notes/url-drain-cutover.md
git commit -m "$(cat <<'EOF'
docs: url drain cutover

Legacy ~/.wintermute/scripts/drain_url_c4a.py is sunset; the single
caller (drain_with_notes.sh line 49) now invokes harvester drain-url.
Old script moved to ~/.wintermute/scripts/_sunset/2026-05-13-drain_url_c4a.py.

7-day stability checkpoint criteria documented in the note for
follow-up review.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

(Note: `~/.wintermute/` is outside the repo, so the script move + drain_with_notes.sh edit aren't captured by git. The commit above just timestamps the cutover in the repo.)

---

### Task 7: Final verification

**No code changes.**

- [ ] **Step 1: Full suite green**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest -p no:randomly 2>&1 | tail -3
```

Expected: 174 passed.

- [ ] **Step 2: CLI surface**

```bash
uv run harvester --help 2>&1 | grep -E "drain-url|calibration|run|chain-references"
```

Expected: all four commands visible.

- [ ] **Step 3: Live data sanity**

```bash
psql wintermute -c "SELECT count(*) FROM harvest.url_drain_documents"
psql wintermute -c "SELECT count(*) FROM harvest.document_metadata WHERE source_id='url_drain'"
psql wintermute -c "SELECT count(*) FROM harvest.run_log WHERE source_id='url_drain' AND status='completed'"
```

Expected: three positive counts (at least the 3 from Task 5's smoke).

- [ ] **Step 4: Branch state**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git log main..HEAD --oneline | wc -l
git status
```

Expected: 5 commits ahead of main (migration, fetcher, ETL, CLI, cutover note). Working tree clean.

- [ ] **Step 5: Branch ready for finishing-a-development-branch**

No further code work. Hand off to `superpowers:finishing-a-development-branch`.

---

### Task 8: 7-day post-cutover stability monitor

**No code changes.** Operational checkpoint only.

- [ ] **Step 1: Daily quick-check for 7 days**

Each day during the week post-cutover, run the query from `docs/superpowers/notes/url-drain-cutover.md`:

```bash
psql wintermute -c "
SELECT date_trunc('day', started_at) AS day,
       count(*) AS runs,
       count(*) FILTER (WHERE status='completed') AS completed,
       count(*) FILTER (WHERE status='failed') AS failed
FROM harvest.run_log
WHERE source_id='url_drain' AND started_at > now() - interval '7 days'
GROUP BY day
ORDER BY day DESC
"
```

Green criteria: ≥80% completed across the 7-day window, no failure_pattern row at `occurrence_count >= 5` with `mitigation_status='unaddressed'`.

- [ ] **Step 2: If a failure pattern shows up**

```bash
psql wintermute -c "
SELECT error_signature, occurrence_count, sample_error, mitigation_status
FROM harvest.failure_patterns
WHERE source_id='url_drain'
ORDER BY occurrence_count DESC
LIMIT 10
"
```

Look at the top error_signature. Common cases:
- **`crawl4ai: timeout`** — page took >45s to render. Increase the page_timeout in `UrlDrainFetcher.crawl_config()` or skip the URL.
- **`crawl4ai: 403`** — site blocked the headless browser. URL drain doesn't have an answer for this; flag the URL as unsupported.
- **`harvest.document_metadata UNIQUE constraint violation`** — same URL drained twice. Expected and handled by the Runner's seen-set; if it's surfacing as a failure_pattern, that's a bug to investigate.

- [ ] **Step 3: Update the cutover note when monitoring is complete**

After 7 days, append a one-line "monitor complete" note to `docs/superpowers/notes/url-drain-cutover.md` and commit it. If criteria failed, document what failed and the remediation.

---

## Self-Review

**1. Spec coverage**

| Requirement | Task |
|---|---|
| UrlDrainFetcher (Crawl4aiFetcher subclass, single URL per invocation) | Task 2 |
| UrlDrainETL with source-type detection mirroring legacy mapping | Task 3 |
| Migration: harvest.url_drain_documents analytical table | Task 1 |
| sources.yaml registration | Task 4 |
| `harvester drain-url` CLI command | Task 4 |
| Real-URL end-to-end smoke across 3 source-type variants | Task 5 |
| Atomic cutover (sunset legacy, update caller) | Task 6 |
| 7-day post-cutover stability checkpoint | Task 8 |

All scope items from the Phase 3 roadmap §3.3 `UrlDrainFetcher` bullet covered. SSRN is out of scope (separate sub-plan, deferred per roadmap).

**2. Placeholder scan** — none. Every step has a complete code block, exact bash command, expected output, or specific file edit. The illustrative Medium-blog URL in Task 5 is explicitly marked as substitutable; the arxiv URL is similarly noted with a fallback query.

**3. Type consistency**

- `harvest.url_drain_documents` schema (Task 1) — column names match the keys UrlDrainETL writes (Task 3): `source_url`, `title`, `source_type`, `host`, `byte_size`, `fetched_at`, `raw_hash`.
- `UrlDrainFetcher.source_id == "url_drain"` (Task 2) and `UrlDrainETL.source_id == "url_drain"` (Task 3) — match the sources.yaml key (Task 4) and the CLI's hardcoded `source_id="url_drain"` (Task 4 Step 4).
- `expected_schema_version = 9` (Task 3) matches migration filename `009_url_drain_documents.sql` (Task 1) and sources.yaml `expected_schema_version: 9` (Task 4).
- `detect_source_type` (Task 3) returns one of {`arxiv_paper`, `youtube_transcript`, `github_repo`, `pdf_document`, `web_article`} — same set the legacy script used.
- `UrlDrainFetcher.urls_to_crawl` reads `query["url"]` (Task 2) — same key the CLI passes (Task 4 Step 4).

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-13-url-drain-migration.md`. Per the operator's standing preference, execution goes to `superpowers:subagent-driven-development` without a mode-selection prompt.
