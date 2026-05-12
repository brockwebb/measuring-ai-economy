# Harvester Foundations (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MUI scout module + multi-backend Fetcher hierarchy (HttpApi, Crawl4ai, Mcp, Rss + skeletons for OaiPmh/Dcat/BulkDownload), refactor the existing Federal Register fetcher onto the new HttpApiFetcher base, and persist scout findings in `harvest.data_sources.discovery_notes`. Unblocks all subsequent source migrations.

**Architecture:** Foundations land as a horizontal slice — every new piece is in place before any source migrates to use them. The existing FR pipeline acts as the regression test: if its 4 golden samples still pass after the FR fetcher inherits HttpApiFetcher, the abstraction is validated. crawl4ai is wired as a lazy optional dep (`uv sync --extra html`) so Phase 1 doesn't force the heavy Playwright/chromium install.

**Tech Stack:** Python 3.12, uv (existing), psycopg (existing), httpx (existing), pytest + pytest-httpx (existing), feedparser (new — RSS parsing), beautifulsoup4 (new — schema.org JSON-LD extraction), crawl4ai (new, optional extra), pyyaml (existing).

**Parent spec:** `docs/superpowers/specs/2026-05-11-harvester-evolution-design.md`

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch strategy:** create `feat/harvester-foundations` from `main` before Task 1.

---

## File Structure

**Created in this plan:**

```
measuring-ai-economy/
├── harvester/
│   ├── pyproject.toml                          # MODIFIED — add deps + optional extra
│   └── harvester/
│       ├── discovery/                          # NEW subpackage
│       │   ├── __init__.py
│       │   ├── scout.py                        # MuiScout orchestrator
│       │   ├── types.py                        # DiscoveryNotes dataclass
│       │   ├── llms_txt.py                     # parse /llms.txt
│       │   ├── robots.py                       # parse /robots.txt
│       │   ├── sitemap.py                      # parse /sitemap.xml
│       │   └── openapi.py                      # parse /.well-known/openapi.json
│       ├── fetchers/
│       │   ├── http_api.py                     # NEW HttpApiFetcher base
│       │   ├── crawl4ai_base.py                # NEW Crawl4aiFetcher base
│       │   ├── mcp_base.py                     # NEW McpFetcher base
│       │   ├── rss_base.py                     # NEW RssFetcher base
│       │   ├── oai_pmh_base.py                 # NEW skeleton ABC
│       │   ├── dcat_base.py                    # NEW skeleton ABC
│       │   ├── bulk_download_base.py           # NEW skeleton ABC
│       │   └── federal_register.py             # MODIFIED — inherits HttpApiFetcher
│       ├── improvement/                        # NEW subpackage (stubs only in Phase 1)
│       │   └── __init__.py
│       ├── triage/                             # NEW subpackage (stub only in Phase 1)
│       │   └── __init__.py
│       ├── schemas/
│       │   └── 003_mui_scout.sql               # NEW migration
│       ├── runner.py                           # MODIFIED — lazy scout hook
│       └── cli.py                              # MODIFIED — `harvester scout` subcommand
│   └── tests/
│       ├── test_discovery_types.py             # DiscoveryNotes
│       ├── test_discovery_llms_txt.py          # llms.txt parser
│       ├── test_discovery_robots.py            # robots parser
│       ├── test_discovery_sitemap.py           # sitemap parser
│       ├── test_discovery_openapi.py           # openapi parser
│       ├── test_discovery_scout.py             # MuiScout integration
│       ├── test_fetcher_http_api.py            # HttpApiFetcher
│       ├── test_fetcher_crawl4ai_base.py       # Crawl4aiFetcher (mocked)
│       ├── test_fetcher_mcp_base.py            # McpFetcher (mocked subprocess)
│       ├── test_fetcher_rss_base.py            # RssFetcher
│       ├── test_fetcher_skeletons.py           # OaiPmh/Dcat/BulkDownload NotImplementedError
│       ├── test_runner_scout_hook.py           # Runner scout integration
│       ├── test_cli_scout.py                   # CLI scout subcommand
│       └── fixtures/discovery/
│           ├── llms_txt_valid.txt
│           ├── llms_txt_malformed.txt
│           ├── llms_txt_with_sections.txt
│           ├── robots_simple.txt
│           ├── robots_with_sitemap.txt
│           ├── robots_with_disallow.txt
│           ├── sitemap_basic.xml
│           ├── sitemap_index.xml
│           ├── sitemap_with_priorities.xml
│           ├── openapi_v3.json
│           ├── openapi_v2_swagger.json
│           └── html_with_jsonld.html
```

**Modified:** `harvester/pyproject.toml`, `harvester/harvester/fetchers/federal_register.py`, `harvester/harvester/runner.py`, `harvester/harvester/cli.py`.

---

## Tasks

### Task 1: Scaffold subpackages + dependencies + feature branch

**Files:**
- Modify: `harvester/pyproject.toml`
- Create: `harvester/harvester/discovery/__init__.py`
- Create: `harvester/harvester/improvement/__init__.py`
- Create: `harvester/harvester/triage/__init__.py`
- Create: `harvester/tests/fixtures/discovery/.gitkeep`

- [ ] **Step 1: Create feature branch**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git checkout main
git pull --ff-only
git checkout -b feat/harvester-foundations
git branch --show-current
```

Expected: `feat/harvester-foundations`

- [ ] **Step 2: Create subpackage directories**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
mkdir -p harvester/harvester/discovery
mkdir -p harvester/harvester/improvement
mkdir -p harvester/harvester/triage
mkdir -p harvester/tests/fixtures/discovery
touch harvester/harvester/discovery/__init__.py
touch harvester/harvester/improvement/__init__.py
touch harvester/harvester/triage/__init__.py
touch harvester/tests/fixtures/discovery/.gitkeep
```

- [ ] **Step 3: Add new deps to pyproject.toml**

Read `harvester/pyproject.toml`, locate the `[project] dependencies` block, and edit to add `feedparser` and `beautifulsoup4`. Add a new `[project.optional-dependencies] html` extra with `crawl4ai`.

Resulting `[project]` block should look like:

```toml
[project]
name = "harvester"
version = "0.1.0"
description = "AI economy measurement harvester — feeds Wintermute pipeline"
requires-python = ">=3.12"
dependencies = [
    "psycopg[binary]>=3.2",
    "httpx>=0.27",
    "pyarrow>=17",
    "pydantic>=2.7",
    "typer>=0.12",
    "pyyaml>=6.0",
    "neo4j>=5.20",
    "tenacity>=8.5",
    "feedparser>=6.0",
    "beautifulsoup4>=4.12",
]

[project.scripts]
harvester = "harvester.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-httpx>=0.30",
    "ruff>=0.5",
    "mypy>=1.10",
]
html = [
    "crawl4ai>=0.4",
]
```

(Other sections unchanged.)

- [ ] **Step 4: Sync deps**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv sync --extra dev
```

Expected: resolves and installs feedparser + beautifulsoup4. crawl4ai is NOT installed (it's in the optional `html` extra; Phase 1 doesn't need it; mocked in tests).

- [ ] **Step 5: Verify imports**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python -c "import feedparser; import bs4; print('feedparser', feedparser.__version__); print('bs4', bs4.__version__)"
```

Expected: prints versions for both, no ImportError.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/pyproject.toml harvester/uv.lock harvester/harvester/discovery/__init__.py harvester/harvester/improvement/__init__.py harvester/harvester/triage/__init__.py harvester/tests/fixtures/discovery/.gitkeep
git commit -m "feat(harvester): scaffold Phase 1 subpackages + deps

Adds discovery/, improvement/, triage/ subpackages (improvement and triage
are stubs in Phase 1, populated in Phases 2-3). Pins feedparser + bs4 as
runtime deps. crawl4ai is in a new optional 'html' extra — Phase 1 mocks
it, Phase 2 needs it for arxiv/zenodo/ssrn.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Migration 003 — discovery_notes columns on data_sources

**Files:**
- Create: `harvester/harvester/schemas/003_mui_scout.sql`

- [ ] **Step 1: Write the migration**

Create `harvester/harvester/schemas/003_mui_scout.sql`:

```sql
-- Migration 003: MUI scout discovery notes on data_sources.

BEGIN;

ALTER TABLE harvest.data_sources
    ADD COLUMN IF NOT EXISTS discovery_notes JSONB,
    ADD COLUMN IF NOT EXISTS last_scouted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS data_sources_scouted_idx
    ON harvest.data_sources (last_scouted_at DESC NULLS LAST);

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('003_mui_scout.sql', 'PLACEHOLDER_SHA', 'MUI scout discovery_notes column on data_sources')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 2: Apply via the runner**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester migrate
```

Expected: `Applying 003_mui_scout.sql (...)` then `Applied 1 migration(s).`

- [ ] **Step 3: Verify column exists**

```bash
psql -d wintermute -c "\d harvest.data_sources" | grep -E "discovery_notes|last_scouted_at"
```

Expected: two lines, one for `discovery_notes jsonb` and one for `last_scouted_at timestamp with time zone`.

- [ ] **Step 4: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/schemas/003_mui_scout.sql
git commit -m "feat(harvester): migration 003 — discovery_notes columns

Adds discovery_notes (jsonb) + last_scouted_at (timestamptz) to
harvest.data_sources. Idempotent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: DiscoveryNotes dataclass

**Files:**
- Create: `harvester/harvester/discovery/types.py`
- Create: `harvester/tests/test_discovery_types.py`

- [ ] **Step 1: Write failing test**

Create `harvester/tests/test_discovery_types.py`:

```python
"""Tests for discovery dataclasses."""

from datetime import datetime, timezone

from harvester.discovery.types import DiscoveryNotes


def test_discovery_notes_constructor():
    notes = DiscoveryNotes(
        base_url="https://example.com",
        probed_at=datetime(2026, 5, 11, 22, 0, 0, tzinfo=timezone.utc),
        llms_txt={"intro": "Hello"},
        robots_rules={"User-agent": "*", "Disallow": "/private"},
        sitemap_urls=["https://example.com/sitemap.xml"],
        openapi_spec=None,
        rss_feeds=["https://example.com/feed.xml"],
        schema_org_types=["Article"],
        probe_errors={},
    )
    assert notes.base_url == "https://example.com"
    assert notes.llms_txt == {"intro": "Hello"}
    assert "Article" in notes.schema_org_types
    assert notes.openapi_spec is None
    assert notes.probe_errors == {}


def test_discovery_notes_is_frozen():
    notes = DiscoveryNotes(
        base_url="https://example.com",
        probed_at=datetime.now(timezone.utc),
        llms_txt=None,
        robots_rules=None,
        sitemap_urls=[],
        openapi_spec=None,
        rss_feeds=[],
        schema_org_types=[],
        probe_errors={},
    )
    try:
        notes.base_url = "https://other.com"  # type: ignore
    except Exception as e:
        assert "frozen" in str(e).lower() or "can't set attribute" in str(e).lower() or "cannot assign" in str(e).lower()
    else:
        raise AssertionError("DiscoveryNotes should be frozen")
```

- [ ] **Step 2: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_types.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.discovery.types'`

- [ ] **Step 3: Implement DiscoveryNotes**

Create `harvester/harvester/discovery/types.py`:

```python
"""Discovery dataclasses for MUI scout results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DiscoveryNotes:
    """Result of probing a source's machine-readable affordances.

    Persisted as JSON into harvest.data_sources.discovery_notes.
    Empty collections/None mean "probed but not found"; probe_errors
    captures fetch failures per endpoint.
    """

    base_url: str
    probed_at: datetime
    llms_txt: dict[str, Any] | None         # parsed sections from /llms.txt
    robots_rules: dict[str, Any] | None     # parsed groups from /robots.txt
    sitemap_urls: list[str]                  # URLs discovered via /sitemap.xml or robots
    openapi_spec: dict[str, Any] | None     # parsed /.well-known/openapi.json or /openapi.json
    rss_feeds: list[str]                     # <link rel="alternate" type="application/rss+xml"> hrefs
    schema_org_types: list[str]              # JSON-LD @type values found on the base page
    probe_errors: dict[str, str] = field(default_factory=dict)  # endpoint -> error message
```

- [ ] **Step 4: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_types.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/discovery/types.py harvester/tests/test_discovery_types.py
git commit -m "feat(harvester): DiscoveryNotes dataclass

Frozen dataclass capturing MUI scout output: llms.txt, robots, sitemap,
openapi, RSS, schema.org types, plus per-endpoint probe errors. Will be
persisted as JSON into harvest.data_sources.discovery_notes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: llms.txt parser

**Files:**
- Create: `harvester/harvester/discovery/llms_txt.py`
- Create: `harvester/tests/fixtures/discovery/llms_txt_valid.txt`
- Create: `harvester/tests/fixtures/discovery/llms_txt_malformed.txt`
- Create: `harvester/tests/fixtures/discovery/llms_txt_with_sections.txt`
- Create: `harvester/tests/test_discovery_llms_txt.py`

The llms.txt spec (https://llmstxt.org) defines a markdown-flavored format with:
- An H1 title (first line)
- Optional blockquote summary
- Optional ## section headers with bullet lists of `[label](url): description`

- [ ] **Step 1: Create three fixtures**

Create `harvester/tests/fixtures/discovery/llms_txt_valid.txt`:

```markdown
# Example Corp

> Example Corp builds widgets for the modern internet.

## Docs

- [Getting Started](https://example.com/docs/start): How to install and run.
- [API Reference](https://example.com/docs/api): Full endpoint reference.

## Optional

- [Blog](https://example.com/blog): Engineering posts.
```

Create `harvester/tests/fixtures/discovery/llms_txt_malformed.txt`:

```markdown
just a plain text file with no structure and no markdown headers at all but a URL might appear: https://example.com/foo
```

Create `harvester/tests/fixtures/discovery/llms_txt_with_sections.txt`:

```markdown
# OpenAlex

> OpenAlex is a fully open catalog of the global research system.

## API

- [API Docs](https://docs.openalex.org/): Complete reference.
- [OpenAPI](https://api.openalex.org/openapi.json): Machine-readable spec.

## Bulk

- [Snapshots](https://docs.openalex.org/download-all-data/openalex-snapshot): Quarterly bulk download.
```

- [ ] **Step 2: Write failing tests**

Create `harvester/tests/test_discovery_llms_txt.py`:

```python
"""Tests for llms.txt parser."""

from pathlib import Path

from harvester.discovery.llms_txt import parse_llms_txt

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_parse_valid_llms_txt():
    text = (FIXTURE_DIR / "llms_txt_valid.txt").read_text()
    result = parse_llms_txt(text)
    assert result["title"] == "Example Corp"
    assert "widgets" in result["summary"]
    assert "Docs" in result["sections"]
    docs = result["sections"]["Docs"]
    assert any(link["url"] == "https://example.com/docs/start" for link in docs)
    assert any(link["url"] == "https://example.com/docs/api" for link in docs)
    assert "Optional" in result["sections"]


def test_parse_malformed_llms_txt_returns_minimal_dict():
    """A file with no recognizable structure parses to {title: None, summary: None, sections: {}}."""
    text = (FIXTURE_DIR / "llms_txt_malformed.txt").read_text()
    result = parse_llms_txt(text)
    assert result["title"] is None
    assert result["sections"] == {}


def test_parse_with_optional_section():
    text = (FIXTURE_DIR / "llms_txt_with_sections.txt").read_text()
    result = parse_llms_txt(text)
    assert result["title"] == "OpenAlex"
    assert "API" in result["sections"]
    assert "Bulk" in result["sections"]
    api_links = result["sections"]["API"]
    assert any(link["url"].endswith("openapi.json") for link in api_links)


def test_parse_empty_string():
    result = parse_llms_txt("")
    assert result["title"] is None
    assert result["sections"] == {}
```

- [ ] **Step 3: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_llms_txt.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.discovery.llms_txt'`

- [ ] **Step 4: Implement parser**

Create `harvester/harvester/discovery/llms_txt.py`:

```python
"""Parser for /llms.txt files (https://llmstxt.org).

The format is markdown-flavored:
- First H1 line is the site title
- Optional blockquote summary (lines starting with >)
- Optional ## section headers, each followed by bullet lists like
  - [label](url): description
"""

from __future__ import annotations

import re
from typing import Any

_TITLE_RE = re.compile(r"^#\s+(.+)$")
_SECTION_RE = re.compile(r"^##\s+(.+)$")
_BLOCKQUOTE_RE = re.compile(r"^>\s*(.*)$")
_LINK_RE = re.compile(r"^-\s+\[([^\]]+)\]\(([^)]+)\)(?::\s+(.+))?$")


def parse_llms_txt(text: str) -> dict[str, Any]:
    """Parse an llms.txt string into structured dict.

    Returns:
        {
            "title": str | None,
            "summary": str | None,
            "sections": {section_name: [{"label": ..., "url": ..., "description": ...}, ...]},
        }
    """
    title: str | None = None
    summary_lines: list[str] = []
    sections: dict[str, list[dict[str, str | None]]] = {}
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        m_section = _SECTION_RE.match(line)
        if m_section:
            current_section = m_section.group(1).strip()
            sections.setdefault(current_section, [])
            continue

        if title is None:
            m_title = _TITLE_RE.match(line)
            if m_title:
                title = m_title.group(1).strip()
                continue

        if current_section is None:
            m_blockquote = _BLOCKQUOTE_RE.match(line)
            if m_blockquote:
                summary_lines.append(m_blockquote.group(1).strip())
                continue

        if current_section is not None:
            m_link = _LINK_RE.match(line)
            if m_link:
                sections[current_section].append({
                    "label": m_link.group(1),
                    "url": m_link.group(2),
                    "description": m_link.group(3),
                })

    summary = " ".join(s for s in summary_lines if s).strip() or None
    return {"title": title, "summary": summary, "sections": sections}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_llms_txt.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/discovery/llms_txt.py harvester/tests/test_discovery_llms_txt.py harvester/tests/fixtures/discovery/llms_txt_*.txt
git commit -m "feat(harvester): llms.txt parser

Parses the llmstxt.org markdown format: H1 title, blockquote summary,
H2 sections with bullet-list links. Returns structured dict. Malformed
input parses to a minimal dict (title=None, sections={}).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: robots.txt parser

**Files:**
- Create: `harvester/harvester/discovery/robots.py`
- Create: `harvester/tests/fixtures/discovery/robots_simple.txt`
- Create: `harvester/tests/fixtures/discovery/robots_with_sitemap.txt`
- Create: `harvester/tests/fixtures/discovery/robots_with_disallow.txt`
- Create: `harvester/tests/test_discovery_robots.py`

- [ ] **Step 1: Create fixtures**

Create `harvester/tests/fixtures/discovery/robots_simple.txt`:

```
User-agent: *
Allow: /
```

Create `harvester/tests/fixtures/discovery/robots_with_sitemap.txt`:

```
User-agent: *
Disallow: /private/

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-news.xml
```

Create `harvester/tests/fixtures/discovery/robots_with_disallow.txt`:

```
User-agent: GPTBot
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /
Crawl-delay: 10
```

- [ ] **Step 2: Write failing tests**

Create `harvester/tests/test_discovery_robots.py`:

```python
"""Tests for robots.txt parser."""

from pathlib import Path

from harvester.discovery.robots import parse_robots_txt

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_parse_simple_robots():
    text = (FIXTURE_DIR / "robots_simple.txt").read_text()
    result = parse_robots_txt(text)
    assert "*" in result["groups"]
    star_group = result["groups"]["*"]
    assert star_group["allow"] == ["/"]
    assert star_group["disallow"] == []
    assert result["sitemaps"] == []


def test_parse_robots_with_sitemap():
    text = (FIXTURE_DIR / "robots_with_sitemap.txt").read_text()
    result = parse_robots_txt(text)
    assert "*" in result["groups"]
    assert result["groups"]["*"]["disallow"] == ["/private/"]
    assert "https://example.com/sitemap.xml" in result["sitemaps"]
    assert "https://example.com/sitemap-news.xml" in result["sitemaps"]


def test_parse_robots_with_multiple_groups_and_crawl_delay():
    text = (FIXTURE_DIR / "robots_with_disallow.txt").read_text()
    result = parse_robots_txt(text)
    assert "GPTBot" in result["groups"]
    assert "CCBot" in result["groups"]
    assert "*" in result["groups"]
    assert result["groups"]["GPTBot"]["disallow"] == ["/"]
    assert "/admin/" in result["groups"]["*"]["disallow"]
    assert result["groups"]["*"]["crawl_delay"] == 10


def test_parse_empty_robots():
    result = parse_robots_txt("")
    assert result["groups"] == {}
    assert result["sitemaps"] == []
```

- [ ] **Step 3: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_robots.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement parser**

Create `harvester/harvester/discovery/robots.py`:

```python
"""Parser for /robots.txt files.

Honors the de facto robots.txt format:
- User-agent: <name>    groups directives by agent
- Allow: <path>         path the agent may visit
- Disallow: <path>      path the agent may not visit
- Crawl-delay: <seconds> minimum seconds between requests
- Sitemap: <url>         file-level sitemap declaration (not per-agent)
"""

from __future__ import annotations

from typing import Any


def parse_robots_txt(text: str) -> dict[str, Any]:
    """Parse a robots.txt string.

    Returns:
        {
            "groups": {
                "<agent>": {"allow": [paths], "disallow": [paths], "crawl_delay": int | None},
                ...
            },
            "sitemaps": [urls],
        }
    """
    groups: dict[str, dict[str, Any]] = {}
    sitemaps: list[str] = []
    current_agent: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()

        if key == "user-agent":
            current_agent = value
            groups.setdefault(current_agent, {"allow": [], "disallow": [], "crawl_delay": None})
        elif key == "allow" and current_agent is not None:
            groups[current_agent]["allow"].append(value)
        elif key == "disallow" and current_agent is not None:
            groups[current_agent]["disallow"].append(value)
        elif key == "crawl-delay" and current_agent is not None:
            try:
                groups[current_agent]["crawl_delay"] = int(value)
            except ValueError:
                pass
        elif key == "sitemap":
            sitemaps.append(value)

    return {"groups": groups, "sitemaps": sitemaps}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_robots.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/discovery/robots.py harvester/tests/test_discovery_robots.py harvester/tests/fixtures/discovery/robots_*.txt
git commit -m "feat(harvester): robots.txt parser

Parses User-agent groups (Allow, Disallow, Crawl-delay) and file-level
Sitemap declarations. Handles comments and empty lines. Empty input
returns empty groups + empty sitemaps.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: sitemap.xml parser

**Files:**
- Create: `harvester/harvester/discovery/sitemap.py`
- Create: `harvester/tests/fixtures/discovery/sitemap_basic.xml`
- Create: `harvester/tests/fixtures/discovery/sitemap_index.xml`
- Create: `harvester/tests/fixtures/discovery/sitemap_with_priorities.xml`
- Create: `harvester/tests/test_discovery_sitemap.py`

- [ ] **Step 1: Create fixtures**

Create `harvester/tests/fixtures/discovery/sitemap_basic.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
    <lastmod>2026-05-01</lastmod>
  </url>
  <url>
    <loc>https://example.com/page2</loc>
    <lastmod>2026-05-02</lastmod>
  </url>
</urlset>
```

Create `harvester/tests/fixtures/discovery/sitemap_index.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-2025.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-2026.xml</loc>
  </sitemap>
</sitemapindex>
```

Create `harvester/tests/fixtures/discovery/sitemap_with_priorities.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/important</loc>
    <priority>1.0</priority>
    <changefreq>daily</changefreq>
  </url>
  <url>
    <loc>https://example.com/footer</loc>
    <priority>0.1</priority>
    <changefreq>yearly</changefreq>
  </url>
</urlset>
```

- [ ] **Step 2: Write failing tests**

Create `harvester/tests/test_discovery_sitemap.py`:

```python
"""Tests for sitemap.xml parser."""

from pathlib import Path

from harvester.discovery.sitemap import parse_sitemap

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_parse_basic_sitemap_returns_urls():
    xml = (FIXTURE_DIR / "sitemap_basic.xml").read_text()
    result = parse_sitemap(xml)
    assert result["kind"] == "urlset"
    urls = [u["loc"] for u in result["entries"]]
    assert "https://example.com/page1" in urls
    assert "https://example.com/page2" in urls


def test_parse_sitemap_index_returns_subsitemaps():
    xml = (FIXTURE_DIR / "sitemap_index.xml").read_text()
    result = parse_sitemap(xml)
    assert result["kind"] == "index"
    sub_urls = [s["loc"] for s in result["entries"]]
    assert "https://example.com/sitemap-2025.xml" in sub_urls
    assert "https://example.com/sitemap-2026.xml" in sub_urls


def test_parse_sitemap_with_priorities():
    xml = (FIXTURE_DIR / "sitemap_with_priorities.xml").read_text()
    result = parse_sitemap(xml)
    assert result["kind"] == "urlset"
    by_loc = {u["loc"]: u for u in result["entries"]}
    assert by_loc["https://example.com/important"]["priority"] == "1.0"
    assert by_loc["https://example.com/important"]["changefreq"] == "daily"


def test_parse_invalid_xml_returns_empty():
    result = parse_sitemap("not xml at all")
    assert result["kind"] == "unknown"
    assert result["entries"] == []
```

- [ ] **Step 3: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_sitemap.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement parser**

Create `harvester/harvester/discovery/sitemap.py`:

```python
"""Parser for sitemap.xml (https://www.sitemaps.org/protocol.html).

Two flavors:
- urlset: contains <url> entries with <loc>, optional <lastmod>, <priority>, <changefreq>
- sitemapindex: contains <sitemap> entries pointing to other sitemap files
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def parse_sitemap(xml_text: str) -> dict[str, Any]:
    """Parse a sitemap XML string.

    Returns:
        {
            "kind": "urlset" | "index" | "unknown",
            "entries": [{"loc": str, "lastmod": str | None, "priority": str | None,
                         "changefreq": str | None}, ...],
        }
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {"kind": "unknown", "entries": []}

    tag = root.tag.rsplit("}", 1)[-1]  # strip namespace
    entries: list[dict[str, Any]] = []

    if tag == "urlset":
        for url_el in root.findall("sm:url", _NS):
            entry = _extract(url_el, ("loc", "lastmod", "priority", "changefreq"))
            entries.append(entry)
        return {"kind": "urlset", "entries": entries}

    if tag == "sitemapindex":
        for sm_el in root.findall("sm:sitemap", _NS):
            entry = _extract(sm_el, ("loc", "lastmod"))
            entries.append(entry)
        return {"kind": "index", "entries": entries}

    return {"kind": "unknown", "entries": []}


def _extract(element: ET.Element, fields: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        child = element.find(f"sm:{f}", _NS)
        out[f] = child.text.strip() if (child is not None and child.text) else None
    return out
```

- [ ] **Step 5: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_sitemap.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/discovery/sitemap.py harvester/tests/test_discovery_sitemap.py harvester/tests/fixtures/discovery/sitemap_*.xml
git commit -m "feat(harvester): sitemap.xml parser

Handles both urlset (concrete URLs) and sitemapindex (pointers to other
sitemaps) per sitemaps.org/protocol.html. Returns structured entries
including lastmod/priority/changefreq when present. Invalid XML returns
empty result rather than raising.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: openapi.json parser

**Files:**
- Create: `harvester/harvester/discovery/openapi.py`
- Create: `harvester/tests/fixtures/discovery/openapi_v3.json`
- Create: `harvester/tests/fixtures/discovery/openapi_v2_swagger.json`
- Create: `harvester/tests/test_discovery_openapi.py`

- [ ] **Step 1: Create fixtures**

Create `harvester/tests/fixtures/discovery/openapi_v3.json`:

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "Example API",
    "version": "1.0.0",
    "description": "A sample API for testing."
  },
  "servers": [
    {"url": "https://api.example.com/v1"}
  ],
  "paths": {
    "/documents": {
      "get": {
        "summary": "List documents",
        "parameters": [
          {"name": "q", "in": "query", "schema": {"type": "string"}}
        ]
      }
    },
    "/documents/{id}": {
      "get": {
        "summary": "Get a document"
      }
    }
  }
}
```

Create `harvester/tests/fixtures/discovery/openapi_v2_swagger.json`:

```json
{
  "swagger": "2.0",
  "info": {
    "title": "Legacy API",
    "version": "0.1.0"
  },
  "host": "legacy.example.com",
  "basePath": "/api",
  "paths": {
    "/items": {
      "get": {"summary": "List items"}
    }
  }
}
```

- [ ] **Step 2: Write failing tests**

Create `harvester/tests/test_discovery_openapi.py`:

```python
"""Tests for openapi.json parser."""

import json
from pathlib import Path

from harvester.discovery.openapi import parse_openapi

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_parse_openapi_v3():
    spec_json = (FIXTURE_DIR / "openapi_v3.json").read_text()
    spec = json.loads(spec_json)
    result = parse_openapi(spec)
    assert result["version_kind"] == "openapi3"
    assert result["title"] == "Example API"
    assert "https://api.example.com/v1" in result["servers"]
    assert "/documents" in result["paths"]
    assert "/documents/{id}" in result["paths"]


def test_parse_swagger_v2():
    spec_json = (FIXTURE_DIR / "openapi_v2_swagger.json").read_text()
    spec = json.loads(spec_json)
    result = parse_openapi(spec)
    assert result["version_kind"] == "swagger2"
    assert result["title"] == "Legacy API"
    assert "https://legacy.example.com/api" in result["servers"] or "http://legacy.example.com/api" in result["servers"]
    assert "/items" in result["paths"]


def test_parse_unknown_format_returns_empty():
    result = parse_openapi({"foo": "bar"})
    assert result["version_kind"] == "unknown"
    assert result["paths"] == []
```

- [ ] **Step 3: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_openapi.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement parser**

Create `harvester/harvester/discovery/openapi.py`:

```python
"""Parser for OpenAPI / Swagger spec JSON.

Handles both:
- OpenAPI 3.x (top-level "openapi" key, "servers" array)
- Swagger 2.0 (top-level "swagger" key, "host" + "basePath")
"""

from __future__ import annotations

from typing import Any


def parse_openapi(spec: dict[str, Any]) -> dict[str, Any]:
    """Parse an OpenAPI/Swagger spec dict.

    Returns:
        {
            "version_kind": "openapi3" | "swagger2" | "unknown",
            "title": str | None,
            "version": str | None,
            "servers": [base_url, ...],
            "paths": [route, ...],
        }
    """
    if "openapi" in spec and str(spec.get("openapi", "")).startswith("3"):
        return _parse_openapi_v3(spec)
    if str(spec.get("swagger", "")) == "2.0":
        return _parse_swagger_v2(spec)
    return {"version_kind": "unknown", "title": None, "version": None, "servers": [], "paths": []}


def _parse_openapi_v3(spec: dict[str, Any]) -> dict[str, Any]:
    info = spec.get("info") or {}
    servers = [s.get("url") for s in spec.get("servers", []) if isinstance(s, dict) and s.get("url")]
    paths = list((spec.get("paths") or {}).keys())
    return {
        "version_kind": "openapi3",
        "title": info.get("title"),
        "version": info.get("version"),
        "servers": servers,
        "paths": paths,
    }


def _parse_swagger_v2(spec: dict[str, Any]) -> dict[str, Any]:
    info = spec.get("info") or {}
    host = spec.get("host")
    base = spec.get("basePath", "")
    schemes = spec.get("schemes") or ["https"]
    servers = [f"{scheme}://{host}{base}" for scheme in schemes if host]
    paths = list((spec.get("paths") or {}).keys())
    return {
        "version_kind": "swagger2",
        "title": info.get("title"),
        "version": info.get("version"),
        "servers": servers,
        "paths": paths,
    }
```

- [ ] **Step 5: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_openapi.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/discovery/openapi.py harvester/tests/test_discovery_openapi.py harvester/tests/fixtures/discovery/openapi_*.json
git commit -m "feat(harvester): OpenAPI / Swagger spec parser

Handles OpenAPI 3.x (servers array) and Swagger 2.0 (host+basePath).
Extracts title, version, server base URLs, and path list. Unknown
formats return empty result rather than raising.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: MuiScout orchestrator

**Files:**
- Create: `harvester/harvester/discovery/scout.py`
- Create: `harvester/tests/fixtures/discovery/html_with_jsonld.html`
- Create: `harvester/tests/test_discovery_scout.py`

- [ ] **Step 1: Create HTML fixture for JSON-LD extraction**

Create `harvester/tests/fixtures/discovery/html_with_jsonld.html`:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Example</title>
  <link rel="alternate" type="application/rss+xml" title="Feed" href="https://example.com/feed.xml">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Hello world"
  }
  </script>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Example Corp"
  }
  </script>
</head>
<body><h1>Example</h1></body>
</html>
```

- [ ] **Step 2: Write failing tests**

Create `harvester/tests/test_discovery_scout.py`:

```python
"""Tests for the MuiScout orchestrator."""

from pathlib import Path

import pytest

from harvester.discovery.scout import MuiScout

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_scout_with_full_mui_present(httpx_mock):
    """Source publishes llms.txt, robots.txt, sitemap, openapi, and JSON-LD."""
    base = "https://example.com"
    httpx_mock.add_response(method="GET", url=f"{base}/llms.txt",
                            text=(FIXTURE_DIR / "llms_txt_valid.txt").read_text())
    httpx_mock.add_response(method="GET", url=f"{base}/robots.txt",
                            text=(FIXTURE_DIR / "robots_with_sitemap.txt").read_text())
    httpx_mock.add_response(method="GET", url=f"{base}/sitemap.xml",
                            text=(FIXTURE_DIR / "sitemap_basic.xml").read_text())
    httpx_mock.add_response(method="GET", url=f"{base}/.well-known/openapi.json",
                            json={"openapi": "3.0.3", "info": {"title": "T", "version": "1"},
                                  "paths": {"/foo": {}}, "servers": [{"url": "https://api.example.com"}]})
    httpx_mock.add_response(method="GET", url=base,
                            text=(FIXTURE_DIR / "html_with_jsonld.html").read_text())

    scout = MuiScout()
    notes = scout.probe(base)

    assert notes.base_url == base
    assert notes.llms_txt is not None
    assert notes.llms_txt["title"] == "Example Corp"
    assert notes.robots_rules is not None
    assert "*" in notes.robots_rules["groups"]
    assert "https://example.com/page1" in notes.sitemap_urls
    assert notes.openapi_spec is not None
    assert notes.openapi_spec["title"] == "T"
    assert "https://example.com/feed.xml" in notes.rss_feeds
    assert "Article" in notes.schema_org_types
    assert "Organization" in notes.schema_org_types
    assert notes.probe_errors == {}


def test_scout_with_all_404(httpx_mock):
    """Source publishes none of the MUI affordances."""
    base = "https://bare.example.com"
    for path in ["/llms.txt", "/robots.txt", "/sitemap.xml", "/.well-known/openapi.json", "/openapi.json"]:
        httpx_mock.add_response(method="GET", url=f"{base}{path}", status_code=404, is_optional=True)
    httpx_mock.add_response(method="GET", url=base, text="<html><body>nothing</body></html>", is_optional=True)

    scout = MuiScout()
    notes = scout.probe(base)

    assert notes.llms_txt is None
    assert notes.robots_rules is None
    assert notes.sitemap_urls == []
    assert notes.openapi_spec is None
    assert notes.rss_feeds == []
    assert notes.schema_org_types == []


def test_scout_with_malformed_llms_txt(httpx_mock):
    base = "https://malformed.example.com"
    httpx_mock.add_response(method="GET", url=f"{base}/llms.txt",
                            text=(FIXTURE_DIR / "llms_txt_malformed.txt").read_text())
    for path in ["/robots.txt", "/sitemap.xml", "/.well-known/openapi.json", "/openapi.json"]:
        httpx_mock.add_response(method="GET", url=f"{base}{path}", status_code=404, is_optional=True)
    httpx_mock.add_response(method="GET", url=base, text="<html></html>", is_optional=True)

    scout = MuiScout()
    notes = scout.probe(base)
    assert notes.llms_txt is not None
    assert notes.llms_txt["title"] is None
```

- [ ] **Step 3: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_scout.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement MuiScout**

Create `harvester/harvester/discovery/scout.py`:

```python
"""MUI scout — probes a source's machine-readable affordances."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from harvester.discovery.llms_txt import parse_llms_txt
from harvester.discovery.openapi import parse_openapi
from harvester.discovery.robots import parse_robots_txt
from harvester.discovery.sitemap import parse_sitemap
from harvester.discovery.types import DiscoveryNotes


class MuiScout:
    """Probes /llms.txt, /robots.txt, /sitemap.xml, /.well-known/openapi.json,
    and the base page's <link rel='alternate' type='application/rss+xml'> and
    <script type='application/ld+json'> elements."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def probe(self, base_url: str) -> DiscoveryNotes:
        """Make all probes and assemble DiscoveryNotes. No exceptions escape —
        probe errors are captured in probe_errors."""
        base = base_url.rstrip("/")
        probe_errors: dict[str, str] = {}

        llms_txt = self._fetch_llms_txt(base, probe_errors)
        robots = self._fetch_robots(base, probe_errors)
        sitemap_urls = self._collect_sitemap_urls(base, robots, probe_errors)
        openapi_spec = self._fetch_openapi(base, probe_errors)
        rss_feeds, schema_types = self._fetch_base_page(base, probe_errors)

        return DiscoveryNotes(
            base_url=base,
            probed_at=datetime.now(timezone.utc),
            llms_txt=llms_txt,
            robots_rules=robots,
            sitemap_urls=sitemap_urls,
            openapi_spec=openapi_spec,
            rss_feeds=rss_feeds,
            schema_org_types=schema_types,
            probe_errors=probe_errors,
        )

    def _fetch_llms_txt(self, base: str, errors: dict[str, str]) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=self._timeout) as c:
                resp = c.get(f"{base}/llms.txt")
                if resp.status_code != 200:
                    return None
                return parse_llms_txt(resp.text)
        except Exception as e:
            errors["llms_txt"] = str(e)
            return None

    def _fetch_robots(self, base: str, errors: dict[str, str]) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=self._timeout) as c:
                resp = c.get(f"{base}/robots.txt")
                if resp.status_code != 200:
                    return None
                return parse_robots_txt(resp.text)
        except Exception as e:
            errors["robots_txt"] = str(e)
            return None

    def _collect_sitemap_urls(self, base: str, robots: dict[str, Any] | None,
                              errors: dict[str, str]) -> list[str]:
        urls: list[str] = []
        # Try the default sitemap
        try:
            with httpx.Client(timeout=self._timeout) as c:
                resp = c.get(f"{base}/sitemap.xml")
                if resp.status_code == 200:
                    parsed = parse_sitemap(resp.text)
                    if parsed["kind"] == "urlset":
                        urls.extend(e["loc"] for e in parsed["entries"] if e.get("loc"))
                    elif parsed["kind"] == "index":
                        urls.extend(e["loc"] for e in parsed["entries"] if e.get("loc"))
        except Exception as e:
            errors["sitemap"] = str(e)

        # Also include sitemap URLs from robots.txt
        if robots and robots.get("sitemaps"):
            for s in robots["sitemaps"]:
                if s and s not in urls:
                    urls.append(s)
        return urls

    def _fetch_openapi(self, base: str, errors: dict[str, str]) -> dict[str, Any] | None:
        """Try /.well-known/openapi.json first, then /openapi.json."""
        for path in ["/.well-known/openapi.json", "/openapi.json"]:
            try:
                with httpx.Client(timeout=self._timeout) as c:
                    resp = c.get(f"{base}{path}")
                    if resp.status_code == 200:
                        try:
                            spec = resp.json()
                        except json.JSONDecodeError:
                            continue
                        return parse_openapi(spec)
            except Exception as e:
                errors[f"openapi:{path}"] = str(e)
        return None

    def _fetch_base_page(self, base: str, errors: dict[str, str]) -> tuple[list[str], list[str]]:
        """Fetch base URL and extract <link rel='alternate' type='application/rss+xml'>
        and <script type='application/ld+json'> @type values."""
        rss_feeds: list[str] = []
        schema_types: list[str] = []
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as c:
                resp = c.get(base)
                if resp.status_code != 200:
                    return rss_feeds, schema_types
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.find_all("link", rel="alternate"):
                    if link.get("type") == "application/rss+xml" and link.get("href"):
                        rss_feeds.append(link["href"])
                for script in soup.find_all("script", type="application/ld+json"):
                    if not script.string:
                        continue
                    try:
                        data = json.loads(script.string)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and "@type" in data:
                        t = data["@type"]
                        if isinstance(t, str):
                            schema_types.append(t)
                        elif isinstance(t, list):
                            schema_types.extend(str(x) for x in t)
        except Exception as e:
            errors["base_page"] = str(e)
        return rss_feeds, schema_types
```

- [ ] **Step 5: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_discovery_scout.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/discovery/scout.py harvester/tests/test_discovery_scout.py harvester/tests/fixtures/discovery/html_with_jsonld.html
git commit -m "feat(harvester): MuiScout orchestrator

Probes llms.txt, robots.txt, sitemap.xml, .well-known/openapi.json (with
/openapi.json fallback), and the base page for RSS feed <link> elements
and JSON-LD @type values. No exceptions escape — per-endpoint errors
captured in probe_errors. Returns DiscoveryNotes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: HttpApiFetcher base class

**Files:**
- Create: `harvester/harvester/fetchers/http_api.py`
- Create: `harvester/tests/test_fetcher_http_api.py`

- [ ] **Step 1: Write failing test (defines the contract via a fake subclass)**

Create `harvester/tests/test_fetcher_http_api.py`:

```python
"""Tests for HttpApiFetcher base."""

import json
from pathlib import Path

from harvester.fetchers.http_api import HttpApiFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


class _FakeHttpApiFetcher(HttpApiFetcher):
    source_id = "fake"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=10.0)

    def base_url(self) -> str:
        return "https://api.example.com/v1/items"

    def build_params(self, query, *, page):
        return {"q": query.get("q", ""), "page": page, "per_page": query.get("per_page", 50)}

    def extract_items(self, body):
        return body.get("results", [])

    def item_to_payload_kwargs(self, item):
        return {
            "source_url": item["url"],
            "content_type": "application/json",
            "content_bytes": json.dumps(item, sort_keys=True).encode("utf-8"),
        }


def test_http_api_fetcher_yields_payloads(tmp_path, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url__startswith="https://api.example.com/v1/items",
        json={"results": [
            {"id": 1, "url": "https://example.com/a"},
            {"id": 2, "url": "https://example.com/b"},
        ]},
        is_reusable=True,
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeHttpApiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "foo", "per_page": 2, "max_pages": 1}))
    assert len(payloads) == 2
    urls = [p.source_url for p in payloads]
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls


def test_http_api_fetcher_honors_seen_set(tmp_path, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url__startswith="https://api.example.com/v1/items",
        json={"results": [
            {"id": 1, "url": "https://example.com/a"},
            {"id": 2, "url": "https://example.com/b"},
        ]},
        is_reusable=True,
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeHttpApiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "foo", "per_page": 2, "max_pages": 1},
                                          seen={"https://example.com/a"}))
    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/b"


def test_http_api_fetcher_stops_on_empty_page(tmp_path, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url__startswith="https://api.example.com/v1/items",
        json={"results": []},
        is_reusable=True,
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeHttpApiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "foo", "max_pages": 5}))
    assert payloads == []
```

- [ ] **Step 2: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_http_api.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement HttpApiFetcher**

Create `harvester/harvester/fetchers/http_api.py`:

```python
"""HTTP API fetcher base class.

Factors out the recurring pattern used by Federal Register, OpenAlex,
Semantic Scholar, PubMed REST, etc.: paginate a JSON endpoint with seen-aware
skipping and rate-limited GETs, writing each item to the raw archive.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Iterable

import httpx

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload

_DEFAULT_PER_PAGE = 50
_DEFAULT_MAX_PAGES = 10
_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"


class HttpApiFetcher(Fetcher):
    """Subclasses implement build_params, extract_items, item_to_payload_kwargs."""

    @abstractmethod
    def base_url(self) -> str: ...

    @abstractmethod
    def build_params(self, query: dict[str, Any], *, page: int) -> dict[str, Any]: ...

    @abstractmethod
    def extract_items(self, response_body: dict[str, Any]) -> Iterable[dict[str, Any]]: ...

    @abstractmethod
    def item_to_payload_kwargs(self, item: dict[str, Any]) -> dict[str, Any]:
        """Return {source_url, content_type, content_bytes} for archive.write()."""

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        per_page = int(query.get("per_page", _DEFAULT_PER_PAGE))
        max_pages = int(query.get("max_pages", _DEFAULT_MAX_PAGES))
        seen = seen or set()

        with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=30) as client:
            for page in range(1, max_pages + 1):
                self._pace()
                params = self.build_params(query, page=page)
                resp = client.get(self.base_url(), params=params)
                resp.raise_for_status()
                body = resp.json()
                items = list(self.extract_items(body))
                if not items:
                    break

                for item in items:
                    kwargs = self.item_to_payload_kwargs(item)
                    source_url = kwargs.get("source_url", "")
                    if source_url and source_url in seen:
                        continue
                    yield self.archive.write(
                        source_id=self.source_id,
                        source_url=source_url,
                        request_params={**params, "item_index": kwargs.get("item_index")},
                        content=kwargs["content_bytes"],
                        content_type=kwargs.get("content_type", "application/json"),
                    )

                if len(items) < per_page:
                    break
```

- [ ] **Step 4: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_http_api.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/fetchers/http_api.py harvester/tests/test_fetcher_http_api.py
git commit -m "feat(harvester): HttpApiFetcher base class

Factors out the FR-style pagination pattern: subclasses provide
base_url(), build_params(), extract_items(), item_to_payload_kwargs().
Handles seen-aware skipping, per-page rate limiting, and early-stop
on empty/partial pages. Reusable for OpenAlex, Semantic Scholar,
PubMed REST, arxiv, etc.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Refactor FederalRegisterFetcher onto HttpApiFetcher

**Files:**
- Modify: `harvester/harvester/fetchers/federal_register.py`

This is the abstraction validation test: if the existing golden samples still pass after this refactor, the HttpApiFetcher contract is sound.

- [ ] **Step 1: Replace the FR fetcher body**

Replace the entire content of `harvester/harvester/fetchers/federal_register.py` with:

```python
"""Federal Register fetcher.

API: https://www.federalregister.gov/developers/documentation/api/v1
Auth: none.
Rate limit: undocumented; we pace at 1 req/sec to be polite.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from harvester.fetchers.http_api import HttpApiFetcher
from harvester.types import RateLimit


_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"


class FederalRegisterFetcher(HttpApiFetcher):
    source_id = "federal_register"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(
            requests_per_second=1.0,
            max_retries=3,
            backoff_seconds=[2, 5, 15, 60],
        )

    def base_url(self) -> str:
        return "https://www.federalregister.gov/api/v1/documents.json"

    def build_params(self, query: dict[str, Any], *, page: int) -> dict[str, Any]:
        per_page = int(query.get("per_page", 100))
        params: dict[str, Any] = {
            "per_page": per_page,
            "page": page,
            "order": query.get("order", "newest"),
        }
        if "term" in query:
            params["conditions[term]"] = query["term"]
        if "type" in query:
            params["conditions[type][]"] = query["type"]
        if "publication_date_gte" in query:
            params["conditions[publication_date][gte]"] = query["publication_date_gte"]
        if "publication_date_lte" in query:
            params["conditions[publication_date][lte]"] = query["publication_date_lte"]
        return params

    def extract_items(self, body: dict[str, Any]) -> Iterable[dict[str, Any]]:
        return body.get("results", [])

    def item_to_payload_kwargs(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_url": item.get("html_url") or item.get("pdf_url") or "",
            "content_type": "application/json",
            "content_bytes": json.dumps(item, sort_keys=True).encode("utf-8"),
            "item_index": item.get("document_number"),
        }
```

- [ ] **Step 2: Run existing FR tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_federal_register.py tests/test_etl_federal_register.py -v
```

Expected: 6 passed (2 fetcher tests + 4 ETL golden samples). The fetcher tests verify behavior; ETL golden samples verify the parse output didn't shift.

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest 2>&1 | tail -5
```

Expected: all tests pass (~40+ at this point).

- [ ] **Step 4: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/fetchers/federal_register.py
git commit -m "refactor(harvester): FR fetcher inherits HttpApiFetcher

Replaces the inline pagination + httpx loop with the HttpApiFetcher
template method pattern. Golden samples unchanged. Validates the
abstraction works for the canonical case.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Crawl4aiFetcher base class

**Files:**
- Create: `harvester/harvester/fetchers/crawl4ai_base.py`
- Create: `harvester/tests/test_fetcher_crawl4ai_base.py`

The crawl4ai dependency is in the optional `html` extra. Phase 1 doesn't install it; tests mock it.

- [ ] **Step 1: Write failing tests**

Create `harvester/tests/test_fetcher_crawl4ai_base.py`:

```python
"""Tests for Crawl4aiFetcher base (with crawl4ai mocked)."""

from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from harvester.fetchers.crawl4ai_base import Crawl4aiFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


class _FakeCrawl4aiFetcher(Crawl4aiFetcher):
    source_id = "fake_crawl"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=2.0)

    def urls_to_crawl(self, query):
        return ["https://example.com/a", "https://example.com/b"]


def _mock_crawl_result(url: str, markdown: str):
    """Build a MagicMock that quacks like a CrawlResult."""
    result = MagicMock()
    result.url = url
    result.markdown = MagicMock(fit_markdown=markdown, raw_markdown=markdown)
    result.success = True
    result.html = f"<html><body>{markdown}</body></html>"
    return result


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_crawl4ai_fetcher_yields_one_per_url(mock_build_crawler, tmp_path):
    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)
    crawler.arun = AsyncMock(side_effect=lambda url, config=None: _mock_crawl_result(url, f"# Page at {url}"))
    mock_build_crawler.return_value = crawler

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeCrawl4aiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}))

    assert len(payloads) == 2
    assert all(p.content_type == "text/markdown" for p in payloads)
    urls = [p.source_url for p in payloads]
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_crawl4ai_fetcher_respects_seen(mock_build_crawler, tmp_path):
    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)
    crawler.arun = AsyncMock(side_effect=lambda url, config=None: _mock_crawl_result(url, "# x"))
    mock_build_crawler.return_value = crawler

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeCrawl4aiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}, seen={"https://example.com/a"}))

    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/b"
```

- [ ] **Step 2: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_crawl4ai_base.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement Crawl4aiFetcher**

Create `harvester/harvester/fetchers/crawl4ai_base.py`:

```python
"""Crawl4ai-backed fetcher base class.

For HTML/JS-heavy sources where a real browser-equivalent extractor is needed.
Lazy-imports crawl4ai so the harvester package can be installed without the
heavy chromium dep — install with `uv sync --extra html` when needed.
"""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


def _build_crawler() -> Any:
    """Construct an AsyncWebCrawler. Lazy import so missing crawl4ai
    only fails at runtime, not import time. Override in tests via mock."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig
    except ImportError as e:
        raise RuntimeError(
            "crawl4ai not installed. Install with: uv sync --extra html"
        ) from e
    return AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False))


class Crawl4aiFetcher(Fetcher):
    """Subclasses provide urls_to_crawl(); optionally override crawl_config()."""

    last_known_good_selector: str | None = None  # sentinel CSS; verified pre-extract

    @abstractmethod
    def urls_to_crawl(self, query: dict[str, Any]) -> Iterable[str]: ...

    def crawl_config(self) -> Any:
        """Default crawl config. Override for source-specific tuning."""
        from crawl4ai import CrawlerRunConfig
        return CrawlerRunConfig(
            excluded_tags=["nav", "header", "footer", "aside", "script", "style"],
            exclude_external_links=True,
            verbose=False,
        )

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        seen = seen or set()
        urls = [u for u in self.urls_to_crawl(query) if u not in seen]
        if not urls:
            return
        # crawl4ai is async; bridge to sync iterator
        for url, markdown in asyncio.run(self._crawl_all(urls)):
            self._pace()
            yield self.archive.write(
                source_id=self.source_id,
                source_url=url,
                request_params={"url": url},
                content=markdown.encode("utf-8"),
                content_type="text/markdown",
            )

    async def _crawl_all(self, urls: list[str]) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        crawler = _build_crawler()
        async with crawler:
            config = self.crawl_config() if callable(getattr(self, "crawl_config", None)) else None
            for url in urls:
                try:
                    result = await crawler.arun(url, config=config)
                    md = (result.markdown.fit_markdown
                          if getattr(result.markdown, "fit_markdown", None)
                          else getattr(result.markdown, "raw_markdown", "") or "")
                    results.append((url, md))
                except Exception:
                    # Skip individual URL failures; surface via runner failure classifier
                    continue
        return results
```

- [ ] **Step 4: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_crawl4ai_base.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/fetchers/crawl4ai_base.py harvester/tests/test_fetcher_crawl4ai_base.py
git commit -m "feat(harvester): Crawl4aiFetcher base class

Lazy-imports crawl4ai so installation is optional (uv sync --extra html).
Subclasses provide urls_to_crawl(); default crawl config excludes
nav/header/footer/aside/script/style. Async crawl bridged to sync iter
via asyncio.run. Respects seen-set per Fetcher contract.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: McpFetcher base class

**Files:**
- Create: `harvester/harvester/fetchers/mcp_base.py`
- Create: `harvester/tests/test_fetcher_mcp_base.py`

McpFetcher invokes Claude via subprocess with an explicit MCP tool call. The subprocess pattern is what Wintermute's existing scripts use.

- [ ] **Step 1: Write failing tests**

Create `harvester/tests/test_fetcher_mcp_base.py`:

```python
"""Tests for McpFetcher base (with subprocess mocked)."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harvester.fetchers.mcp_base import McpFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


class _FakeMcpFetcher(McpFetcher):
    source_id = "fake_mcp"
    mcp_tool = "mcp__test__search"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=1.0)

    def args_for_query(self, query):
        return {"q": query.get("q", "")}

    def items_from_response(self, response):
        return response.get("results", [])


@patch("harvester.fetchers.mcp_base.subprocess.run")
def test_mcp_fetcher_yields_one_per_item(mock_run, tmp_path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "results": [
                {"url": "https://example.com/a", "title": "A"},
                {"url": "https://example.com/b", "title": "B"},
            ]
        }),
        stderr="",
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "ai"}))

    assert len(payloads) == 2
    assert all(p.content_type == "application/json" for p in payloads)


@patch("harvester.fetchers.mcp_base.subprocess.run")
def test_mcp_fetcher_respects_seen(mock_run, tmp_path):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "results": [
                {"url": "https://example.com/a"},
                {"url": "https://example.com/b"},
            ]
        }),
        stderr="",
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "ai"}, seen={"https://example.com/a"}))

    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/b"


@patch("harvester.fetchers.mcp_base.subprocess.run")
def test_mcp_fetcher_raises_on_nonzero_exit(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="oh no")
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeMcpFetcher(archive=archive)
    with pytest.raises(RuntimeError, match="MCP call failed"):
        list(fetcher.iter_payloads({"q": "x"}))
```

- [ ] **Step 2: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_mcp_base.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement McpFetcher**

Create `harvester/harvester/fetchers/mcp_base.py`:

```python
"""MCP-backed fetcher base class.

Invokes Claude via subprocess with an explicit MCP tool call. Matches the
pattern used by existing Wintermute scripts. Records (model_id, prompt_hash,
tool_args) for stochastic provenance.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


_CLAUDE_BIN = os.environ.get("HARVESTER_CLAUDE_BIN", "claude")


class McpFetcher(Fetcher):
    """Subclasses set mcp_tool and implement args_for_query / items_from_response."""

    mcp_tool: str = ""  # e.g., "mcp__claude_ai_PubMed__search_articles"

    @abstractmethod
    def args_for_query(self, query: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def items_from_response(self, response: dict[str, Any]) -> Iterable[dict[str, Any]]: ...

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        seen = seen or set()
        self._pace()
        args = self.args_for_query(query)
        prompt = self._build_mcp_prompt(args)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        proc = subprocess.run(
            [_CLAUDE_BIN, "-p", prompt, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"MCP call failed (exit {proc.returncode}): {proc.stderr.strip()}")

        try:
            response = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"MCP response was not JSON: {e}; stdout: {proc.stdout[:200]}")

        for item in self.items_from_response(response):
            source_url = item.get("url") or item.get("source_url") or ""
            if source_url and source_url in seen:
                continue
            content = json.dumps(item, sort_keys=True).encode("utf-8")
            yield self.archive.write(
                source_id=self.source_id,
                source_url=source_url,
                request_params={
                    "mcp_tool": self.mcp_tool,
                    "args": args,
                    "prompt_hash": prompt_hash,
                },
                content=content,
                content_type="application/json",
            )

    def _build_mcp_prompt(self, args: dict[str, Any]) -> str:
        """Build the prompt for invoking the MCP tool. Override for custom shape."""
        return (
            f"Call the {self.mcp_tool} tool with these arguments and return ONLY the "
            f"tool's raw JSON output, no commentary:\n\n{json.dumps(args, indent=2)}"
        )
```

- [ ] **Step 4: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_mcp_base.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/fetchers/mcp_base.py harvester/tests/test_fetcher_mcp_base.py
git commit -m "feat(harvester): McpFetcher base class

Subprocess to claude with explicit MCP tool call. Subclasses set
mcp_tool, implement args_for_query() and items_from_response(). Records
prompt_hash in request_params for stochastic provenance. Raises on
non-zero claude exit or non-JSON response.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: RssFetcher base class

**Files:**
- Create: `harvester/harvester/fetchers/rss_base.py`
- Create: `harvester/tests/test_fetcher_rss_base.py`
- Create: `harvester/tests/fixtures/discovery/feed_atom.xml`
- Create: `harvester/tests/fixtures/discovery/feed_rss2.xml`

- [ ] **Step 1: Create feed fixtures**

Create `harvester/tests/fixtures/discovery/feed_atom.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom Feed</title>
  <link href="https://example.com/feed.xml" rel="self"/>
  <updated>2026-05-11T22:00:00Z</updated>
  <id>urn:uuid:example-feed</id>
  <entry>
    <title>First post</title>
    <link href="https://example.com/posts/1"/>
    <id>urn:uuid:example-post-1</id>
    <updated>2026-05-10T12:00:00Z</updated>
    <summary>First post summary.</summary>
  </entry>
  <entry>
    <title>Second post</title>
    <link href="https://example.com/posts/2"/>
    <id>urn:uuid:example-post-2</id>
    <updated>2026-05-11T12:00:00Z</updated>
    <summary>Second post summary.</summary>
  </entry>
</feed>
```

Create `harvester/tests/fixtures/discovery/feed_rss2.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example RSS 2.0 Feed</title>
    <link>https://example.com/</link>
    <description>Example feed.</description>
    <item>
      <title>Item A</title>
      <link>https://example.com/items/a</link>
      <guid>https://example.com/items/a</guid>
      <description>Item A description.</description>
    </item>
    <item>
      <title>Item B</title>
      <link>https://example.com/items/b</link>
      <guid>https://example.com/items/b</guid>
      <description>Item B description.</description>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Write failing tests**

Create `harvester/tests/test_fetcher_rss_base.py`:

```python
"""Tests for RssFetcher base."""

from pathlib import Path

from harvester.fetchers.rss_base import RssFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


class _FakeRssFetcher(RssFetcher):
    source_id = "fake_rss"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=2.0)

    def feed_urls(self, query):
        return ["https://example.com/feed.xml"]

    def entry_to_payload_kwargs(self, entry):
        return {
            "source_url": entry.get("link", ""),
            "content_type": "application/json",
            "content_bytes": str(entry).encode("utf-8"),
        }


def test_rss_fetcher_yields_one_per_atom_entry(tmp_path, httpx_mock):
    feed_text = (FIXTURE_DIR / "feed_atom.xml").read_text()
    httpx_mock.add_response(method="GET", url="https://example.com/feed.xml", text=feed_text)
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeRssFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}))
    assert len(payloads) == 2
    urls = [p.source_url for p in payloads]
    assert "https://example.com/posts/1" in urls
    assert "https://example.com/posts/2" in urls


def test_rss_fetcher_yields_one_per_rss2_item(tmp_path, httpx_mock):
    feed_text = (FIXTURE_DIR / "feed_rss2.xml").read_text()
    httpx_mock.add_response(method="GET", url="https://example.com/feed.xml", text=feed_text)
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeRssFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}))
    assert len(payloads) == 2
    urls = [p.source_url for p in payloads]
    assert "https://example.com/items/a" in urls


def test_rss_fetcher_respects_seen(tmp_path, httpx_mock):
    feed_text = (FIXTURE_DIR / "feed_rss2.xml").read_text()
    httpx_mock.add_response(method="GET", url="https://example.com/feed.xml", text=feed_text)
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeRssFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}, seen={"https://example.com/items/a"}))
    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/items/b"
```

- [ ] **Step 3: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_rss_base.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement RssFetcher**

Create `harvester/harvester/fetchers/rss_base.py`:

```python
"""RSS/Atom feed fetcher base class.

Uses feedparser to handle both flavors. Subclasses provide feed_urls()
and entry_to_payload_kwargs().
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Iterable

import feedparser
import httpx

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload

_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"


class RssFetcher(Fetcher):
    """Subclasses provide feed_urls() and entry_to_payload_kwargs()."""

    @abstractmethod
    def feed_urls(self, query: dict[str, Any]) -> Iterable[str]: ...

    @abstractmethod
    def entry_to_payload_kwargs(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Return {source_url, content_type, content_bytes} for archive.write()."""

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        seen = seen or set()
        with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=30) as client:
            for feed_url in self.feed_urls(query):
                self._pace()
                resp = client.get(feed_url)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries:
                    kwargs = self.entry_to_payload_kwargs(dict(entry))
                    source_url = kwargs.get("source_url", "")
                    if source_url and source_url in seen:
                        continue
                    yield self.archive.write(
                        source_id=self.source_id,
                        source_url=source_url,
                        request_params={"feed_url": feed_url},
                        content=kwargs["content_bytes"],
                        content_type=kwargs.get("content_type", "application/json"),
                    )
```

- [ ] **Step 5: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_rss_base.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/fetchers/rss_base.py harvester/tests/test_fetcher_rss_base.py harvester/tests/fixtures/discovery/feed_*.xml
git commit -m "feat(harvester): RssFetcher base class

Uses feedparser to handle both Atom 1.0 and RSS 2.0. Subclasses provide
feed_urls() and entry_to_payload_kwargs(). Per-entry seen-skip honored.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Skeleton fetchers (OAI-PMH, DCAT, BulkDownload)

**Files:**
- Create: `harvester/harvester/fetchers/oai_pmh_base.py`
- Create: `harvester/harvester/fetchers/dcat_base.py`
- Create: `harvester/harvester/fetchers/bulk_download_base.py`
- Create: `harvester/tests/test_fetcher_skeletons.py`

These are ABCs with no concrete impl — Phase 1 just lays down the interfaces. Tests assert NotImplementedError when iter_payloads is called.

- [ ] **Step 1: Write tests first**

Create `harvester/tests/test_fetcher_skeletons.py`:

```python
"""Tests for skeleton fetchers (OaiPmh, Dcat, BulkDownload).

These ABCs don't have concrete implementations yet — Phase 1 lays down the
interfaces and Phase 3+ adds real fetchers. Subclasses without implementations
raise NotImplementedError when iter_payloads is called.
"""

import pytest

from harvester.fetchers.oai_pmh_base import OaiPmhFetcher
from harvester.fetchers.dcat_base import DcatFetcher
from harvester.fetchers.bulk_download_base import BulkDownloadFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit
from pathlib import Path


def _archive(tmp_path):
    return RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")


class _FakeOaiPmh(OaiPmhFetcher):
    source_id = "fake_oai"
    def rate_limit_spec(self): return RateLimit(requests_per_second=1.0)
    def oai_endpoint(self): return "https://example.com/oai"
    def metadata_prefix(self): return "oai_dc"


class _FakeDcat(DcatFetcher):
    source_id = "fake_dcat"
    def rate_limit_spec(self): return RateLimit(requests_per_second=1.0)
    def catalog_url(self): return "https://example.com/catalog.jsonld"


class _FakeBulk(BulkDownloadFetcher):
    source_id = "fake_bulk"
    def rate_limit_spec(self): return RateLimit(requests_per_second=1.0)
    def snapshot_url(self): return "https://example.com/snapshot.tar.gz"
    def parse_snapshot(self, path): return iter([])


def test_oai_pmh_iter_raises_not_implemented(tmp_path):
    fetcher = _FakeOaiPmh(archive=_archive(tmp_path))
    with pytest.raises(NotImplementedError, match="OAI-PMH"):
        list(fetcher.iter_payloads({}))


def test_dcat_iter_raises_not_implemented(tmp_path):
    fetcher = _FakeDcat(archive=_archive(tmp_path))
    with pytest.raises(NotImplementedError, match="DCAT"):
        list(fetcher.iter_payloads({}))


def test_bulk_download_iter_raises_not_implemented(tmp_path):
    fetcher = _FakeBulk(archive=_archive(tmp_path))
    with pytest.raises(NotImplementedError, match="bulk download"):
        list(fetcher.iter_payloads({}))
```

- [ ] **Step 2: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_skeletons.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement skeletons**

Create `harvester/harvester/fetchers/oai_pmh_base.py`:

```python
"""OAI-PMH fetcher skeleton.

The Open Archives Initiative Protocol for Metadata Harvesting — used by
arxiv, Zenodo, institutional repositories, JSTOR, Europeana, etc. Phase 1
defines the interface; concrete implementation lands in a future spec when
the first OAI-PMH source needs it.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


class OaiPmhFetcher(Fetcher):
    """Subclasses set oai_endpoint() and metadata_prefix()."""

    @abstractmethod
    def oai_endpoint(self) -> str: ...

    @abstractmethod
    def metadata_prefix(self) -> str: ...

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        raise NotImplementedError(
            "OAI-PMH fetcher implementation deferred to a future spec. "
            "Required interface: ListRecords verb, resumptionToken pagination, "
            "metadataPrefix selection. See https://www.openarchives.org/OAI/openarchivesprotocol.html"
        )
```

Create `harvester/harvester/fetchers/dcat_base.py`:

```python
"""DCAT-AP / CKAN catalog fetcher skeleton.

For data portals using the DCAT vocabulary (data.gov, Eurostat, OECD.AI).
Phase 1 defines the interface; concrete implementation lands in a future
spec when the first DCAT source needs it.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


class DcatFetcher(Fetcher):
    """Subclasses set catalog_url() pointing at a DCAT catalog (JSON-LD or RDF)."""

    @abstractmethod
    def catalog_url(self) -> str: ...

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        raise NotImplementedError(
            "DCAT/CKAN fetcher implementation deferred to a future spec. "
            "Required interface: catalog parsing (dcat:dataset + dcat:distribution), "
            "DCAT-AP property extraction, CKAN package_search API. "
            "See https://www.w3.org/TR/vocab-dcat-3/"
        )
```

Create `harvester/harvester/fetchers/bulk_download_base.py`:

```python
"""Bulk download fetcher skeleton.

For sources offering full-snapshot downloads (Common Crawl, Wikipedia dumps,
PubMed Central FTP, OpenAlex snapshots). Phase 1 defines the interface;
concrete implementation lands in a future spec.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


class BulkDownloadFetcher(Fetcher):
    """Subclasses set snapshot_url() and implement parse_snapshot()."""

    @abstractmethod
    def snapshot_url(self) -> str: ...

    @abstractmethod
    def parse_snapshot(self, path: Path) -> Iterable[dict[str, Any]]: ...

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        raise NotImplementedError(
            "Bulk download fetcher implementation deferred to a future spec. "
            "Required interface: snapshot download (resumable), local cache, "
            "parse_snapshot streaming, per-record archive.write() with seen-skip."
        )
```

- [ ] **Step 4: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_skeletons.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/fetchers/oai_pmh_base.py harvester/harvester/fetchers/dcat_base.py harvester/harvester/fetchers/bulk_download_base.py harvester/tests/test_fetcher_skeletons.py
git commit -m "feat(harvester): skeleton fetchers (OAI-PMH, DCAT, BulkDownload)

ABCs without concrete impl — defines the interface contract so downstream
code can import them. iter_payloads raises NotImplementedError with a
clear message pointing at the relevant spec. Concrete implementations
land in future specs when the first user appears.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 15: Runner lazy scout integration

**Files:**
- Modify: `harvester/harvester/runner.py`
- Create: `harvester/tests/test_runner_scout_hook.py`

- [ ] **Step 1: Write failing test**

Create `harvester/tests/test_runner_scout_hook.py`:

```python
"""Tests for the runner's lazy scout integration."""

from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.discovery.types import DiscoveryNotes


@pytest.fixture
def clean_scout_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.data_sources WHERE source_id = 'scout_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'scout_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.data_sources WHERE source_id = 'scout_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'scout_test'")
        conn.commit()
    finally:
        conn.close()


def _fake_notes():
    return DiscoveryNotes(
        base_url="https://example.com",
        probed_at=datetime.now(timezone.utc),
        llms_txt={"title": "Test"},
        robots_rules=None,
        sitemap_urls=[],
        openapi_spec=None,
        rss_feeds=[],
        schema_org_types=[],
        probe_errors={},
    )


@patch("harvester.runner.MuiScout")
def test_runner_scouts_on_first_run(mock_scout_cls, clean_scout_state, tmp_path):
    mock_scout = MagicMock()
    mock_scout.probe.return_value = _fake_notes()
    mock_scout_cls.return_value = mock_scout

    config = RunnerConfig(
        source_id="scout_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=3,
    )

    class FakeFetcher:
        def iter_payloads(self, q, *, seen=None): return iter([])
    class FakeETL:
        source_id = "scout_test"
        expected_schema_version = 3
        def parse(self, raw): ...
        def to_rows(self, parsed): return []

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.scout_base_url = "https://example.com"
    runner.run({})

    mock_scout.probe.assert_called_once()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT discovery_notes, last_scouted_at FROM harvest.data_sources WHERE source_id = 'scout_test'"
            )
            row = cur.fetchone()
            assert row is not None
            notes, scouted_at = row
            assert notes["base_url"] == "https://example.com"
            assert scouted_at is not None
    finally:
        conn.close()


@patch("harvester.runner.MuiScout")
def test_runner_skips_scout_on_recent_run(mock_scout_cls, clean_scout_state, tmp_path):
    """If last_scouted_at is recent, scout is NOT called again."""
    mock_scout = MagicMock()
    mock_scout.probe.return_value = _fake_notes()
    mock_scout_cls.return_value = mock_scout

    # Seed an existing recent scout
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.data_sources (source_id, name, last_scouted_at, discovery_notes)
                VALUES ('scout_test', 'Test', now(), '{}'::jsonb)
                ON CONFLICT (source_id) DO UPDATE SET last_scouted_at = now()
                """
            )
        conn.commit()
    finally:
        conn.close()

    config = RunnerConfig(
        source_id="scout_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=3,
    )

    class FakeFetcher:
        def iter_payloads(self, q, *, seen=None): return iter([])
    class FakeETL:
        source_id = "scout_test"
        expected_schema_version = 3

    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.scout_base_url = "https://example.com"
    runner.run({})

    mock_scout.probe.assert_not_called()
```

- [ ] **Step 2: Run, verify fail**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_runner_scout_hook.py -v
```

Expected: failures because Runner doesn't yet have `_has_recent_discovery_notes`, `_scout_and_persist`, or `scout_base_url`.

- [ ] **Step 3: Add scout integration to runner**

Edit `harvester/harvester/runner.py`. Add import for `MuiScout`:

```python
from harvester.discovery.scout import MuiScout
```

Add attribute `scout_base_url: str | None = None` to `RunnerConfig` (so callers can specify what URL to scout):

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
```

Add `scout_base_url` and `_scout` attributes to `Runner.__init__` (allow override):

```python
class Runner:
    def __init__(self, *, config: RunnerConfig, fetcher, etl) -> None:
        self.config = config
        self.fetcher = fetcher
        self.etl = etl
        self.scout_base_url: str | None = config.scout_base_url
        self._scout = MuiScout()
```

Add scout hook to `run()`. Inside the try block after `_assert_schema_version` and before the advisory lock acquisition, add:

```python
        if self.scout_base_url and not self._has_recent_discovery_notes(conn):
            self._scout_and_persist(conn)
```

Add the two methods at the end of the class:

```python
    def _has_recent_discovery_notes(self, conn: psycopg.Connection) -> bool:
        """Return True if data_sources has a row for this source with last_scouted_at
        in the last 90 days."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT last_scouted_at
                FROM harvest.data_sources
                WHERE source_id = %s AND last_scouted_at > now() - interval '90 days'
                """,
                (self.config.source_id,),
            )
            return cur.fetchone() is not None

    def _scout_and_persist(self, conn: psycopg.Connection) -> None:
        """Probe MUI affordances and persist to data_sources."""
        if not self.scout_base_url:
            return
        notes = self._scout.probe(self.scout_base_url)
        notes_json = json.dumps({
            "base_url": notes.base_url,
            "probed_at": notes.probed_at.isoformat(),
            "llms_txt": notes.llms_txt,
            "robots_rules": notes.robots_rules,
            "sitemap_urls": notes.sitemap_urls,
            "openapi_spec": notes.openapi_spec,
            "rss_feeds": notes.rss_feeds,
            "schema_org_types": notes.schema_org_types,
            "probe_errors": notes.probe_errors,
        })
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.data_sources (source_id, name, discovery_notes, last_scouted_at)
                VALUES (%s, %s, %s::jsonb, now())
                ON CONFLICT (source_id) DO UPDATE
                SET discovery_notes = EXCLUDED.discovery_notes,
                    last_scouted_at = EXCLUDED.last_scouted_at
                """,
                (self.config.source_id, self.config.source_id, notes_json),
            )
        conn.commit()
```

- [ ] **Step 4: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_runner_scout_hook.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Verify nothing else broke**

```bash
uv run pytest 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/runner.py harvester/tests/test_runner_scout_hook.py
git commit -m "feat(harvester): runner lazy MUI scout hook

Runner now probes a source's MUI affordances on first contact and caches
the result in harvest.data_sources.discovery_notes. Re-probes after 90
days. RunnerConfig gains a scout_base_url field (None disables scouting
for that source). MuiScout class can be mocked via runner.MuiScout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 16: CLI `harvester scout` subcommand

**Files:**
- Modify: `harvester/harvester/cli.py`
- Create: `harvester/tests/test_cli_scout.py`

- [ ] **Step 1: Write failing tests**

Create `harvester/tests/test_cli_scout.py`:

```python
"""Tests for `harvester scout` CLI."""

import json
import subprocess
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest

from harvester.db import get_connection
from harvester.discovery.types import DiscoveryNotes


@pytest.fixture
def clean_scout_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.data_sources WHERE source_id = 'cli_scout_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.data_sources WHERE source_id = 'cli_scout_test'")
        conn.commit()
    finally:
        conn.close()


def test_scout_cli_persists_notes(clean_scout_state):
    """`harvester scout <source_id> --base-url <url>` writes to data_sources."""
    result = subprocess.run(
        ["uv", "run", "harvester", "scout", "federal_register",
         "--base-url", "https://www.federalregister.gov"],
        capture_output=True, text=True,
    )
    # We don't assert exit code 0 (might 404 on some endpoints) — just that it persists notes
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT discovery_notes, last_scouted_at FROM harvest.data_sources WHERE source_id = 'federal_register'"
            )
            row = cur.fetchone()
            assert row is not None, f"No discovery_notes persisted. stdout: {result.stdout}, stderr: {result.stderr}"
            notes, scouted_at = row
            assert notes is not None
            assert scouted_at is not None
    finally:
        conn.close()
```

Note: this test hits the real FR site. We could mock, but this is also a live integration check — useful for the smoke test at end of phase.

- [ ] **Step 2: Run, verify fail (or pre-existing source already scouted)**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
# Clear federal_register scout state first
psql -d wintermute -c "DELETE FROM harvest.data_sources WHERE source_id = 'federal_register'"
uv run pytest tests/test_cli_scout.py -v
```

Expected: failure — `scout` subcommand doesn't exist yet.

- [ ] **Step 3: Add `scout` subcommand to cli.py**

Edit `harvester/harvester/cli.py`. Add imports at top:

```python
import json
from harvester.discovery.scout import MuiScout
```

Add the new command after `migrate`:

```python
@app.command()
def scout(
    source: str = typer.Argument(..., help="Source id, e.g., 'federal_register'"),
    base_url: str = typer.Option(..., "--base-url", help="Base URL to probe"),
    force: bool = typer.Option(False, "--force", help="Re-probe even if recent notes exist"),
) -> None:
    """Probe a source's MUI affordances and persist to data_sources.discovery_notes."""
    conn = get_connection()
    try:
        if not force:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT last_scouted_at FROM harvest.data_sources
                    WHERE source_id = %s AND last_scouted_at > now() - interval '90 days'
                    """,
                    (source,),
                )
                if cur.fetchone():
                    typer.echo(f"{source} already scouted recently. Use --force to re-probe.")
                    return

        scout_obj = MuiScout()
        typer.echo(f"Probing {base_url} ...")
        notes = scout_obj.probe(base_url)
        notes_json = json.dumps({
            "base_url": notes.base_url,
            "probed_at": notes.probed_at.isoformat(),
            "llms_txt": notes.llms_txt,
            "robots_rules": notes.robots_rules,
            "sitemap_urls": notes.sitemap_urls,
            "openapi_spec": notes.openapi_spec,
            "rss_feeds": notes.rss_feeds,
            "schema_org_types": notes.schema_org_types,
            "probe_errors": notes.probe_errors,
        })

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.data_sources (source_id, name, discovery_notes, last_scouted_at)
                VALUES (%s, %s, %s::jsonb, now())
                ON CONFLICT (source_id) DO UPDATE
                SET discovery_notes = EXCLUDED.discovery_notes,
                    last_scouted_at = EXCLUDED.last_scouted_at
                """,
                (source, source, notes_json),
            )
        conn.commit()
        typer.echo(f"Scouted {source}: llms_txt={'yes' if notes.llms_txt else 'no'}, "
                   f"robots={'yes' if notes.robots_rules else 'no'}, "
                   f"sitemaps={len(notes.sitemap_urls)}, rss_feeds={len(notes.rss_feeds)}, "
                   f"openapi={'yes' if notes.openapi_spec else 'no'}, "
                   f"schema_org={len(notes.schema_org_types)}, "
                   f"errors={len(notes.probe_errors)}")
    finally:
        conn.close()
```

- [ ] **Step 4: Run, verify pass**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
psql -d wintermute -c "DELETE FROM harvest.data_sources WHERE source_id = 'federal_register'"
uv run pytest tests/test_cli_scout.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Verify help shows scout subcommand**

```bash
uv run harvester --help
```

Expected: 5 commands listed — migrate, run, status, validate, scout.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/cli.py harvester/tests/test_cli_scout.py
git commit -m "feat(harvester): \`harvester scout\` CLI subcommand

Probes a source's MUI affordances (llms.txt, robots, sitemap, openapi,
RSS, JSON-LD) and persists to data_sources.discovery_notes. Skips
re-probe if last_scouted_at is < 90 days; --force overrides. Prints a
one-line summary of what was found.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 17: Final verification + integration smoke test

**Files:** none modified — this is acceptance verification.

- [ ] **Step 1: Full test suite green**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest -v 2>&1 | tail -5
```

Expected: all tests passed. Count should be ~40+ (26 original MVP + ~15 new).

- [ ] **Step 2: Live scout against federal_register**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
psql -d wintermute -c "DELETE FROM harvest.data_sources WHERE source_id = 'federal_register'"
uv run harvester scout federal_register --base-url https://www.federalregister.gov
```

Expected: prints "Probing..." then a summary line. Exit code 0.

- [ ] **Step 3: Verify notes persisted**

```bash
psql -d wintermute -c "SELECT source_id, last_scouted_at, discovery_notes->>'base_url' as base_url, jsonb_array_length(discovery_notes->'sitemap_urls') as sitemap_count, jsonb_array_length(discovery_notes->'rss_feeds') as rss_count FROM harvest.data_sources WHERE source_id = 'federal_register'"
```

Expected: one row with non-null `last_scouted_at` and a `base_url` value.

- [ ] **Step 4: Verify FR pipeline still passes end-to-end**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run federal_register --query="artificial intelligence" --limit=2
```

Expected: completes successfully with `fetched`/`deposited`/`failed` counts. Most likely `deposited=0` because dedup catches everything (we already have 246 from prior runs).

- [ ] **Step 5: Count validation still passes**

```bash
uv run python -m harvester.scripts.validate_count 2>&1 | head -10
```

Expected: prints validation summary. (Exit code 1 if drift exceeds threshold — that's fine, it's expected from the limited prior runs.)

- [ ] **Step 6: Commit (if any tweaks made during verification)**

If no commits needed: done. Otherwise:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add -A
git commit -m "fix(harvester): final verification touch-ups

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage** — every Phase 1 deliverable from the design spec §7 maps to one or more tasks:

| Spec Phase 1 deliverable | Tasks |
|---|---|
| MUI scout module + 4 parsers (llms.txt, robots, sitemap, openapi) | Tasks 3 (types), 4 (llms.txt), 5 (robots), 6 (sitemap), 7 (openapi), 8 (MuiScout) |
| Fetcher backend ABCs (HttpApi, Crawl4ai, Mcp, Rss) | Tasks 9, 11, 12, 13 |
| Skeleton ABCs (OaiPmh, Dcat, BulkDownload) | Task 14 |
| Refactor existing FR fetcher onto HttpApiFetcher | Task 10 |
| Runner extension: lazy MUI scout | Task 15 |
| CLI: `harvester scout <source_id>` | Task 16 |
| Migration 003_mui_scout.sql | Task 2 |
| Test coverage: ~15 new tests | Tasks 3-16 (each adds tests; total ~25 new test cases) |

**2. Placeholder scan** — none. Every step has either real code, real commands, or real expected output.

**3. Type consistency** — verified across tasks:
- `DiscoveryNotes` defined in Task 3, used by Tasks 8, 15, 16
- `MuiScout` defined in Task 8, used by Tasks 15, 16
- `HttpApiFetcher` defined in Task 9, used by Task 10 (FR refactor)
- `Crawl4aiFetcher` / `McpFetcher` / `RssFetcher` defined in Tasks 11/12/13 — Phase 2/3 will use them; not used within Phase 1 itself.
- `RunnerConfig.scout_base_url` added in Task 15 — referenced in Task 16's CLI integration via the runner's existing pattern.
- `parse_llms_txt`, `parse_robots_txt`, `parse_sitemap`, `parse_openapi` — function names consistent across parser modules and the MuiScout call sites.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-harvester-foundations-phase1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
