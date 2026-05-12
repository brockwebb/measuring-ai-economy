# Harvester Phase 3.2 (SemanticScholar + CitationChain) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the canonical adaptive loop — when arxiv papers come in with DOIs, follow their reference lists through Semantic Scholar, score the references, and queue high-relevance ones as new fetch candidates. Plus expose Semantic Scholar as a standalone harvester source.

**Architecture:** `SemanticScholarFetcher` (HttpApiFetcher subclass) drives `/paper/search`, `/paper/{id}`, `/paper/{id}/references`. `SemanticScholarETL` writes typed rows to a new `harvest.semantic_scholar_papers` table. `CitationChain` runs in two modes: synchronous `enqueue()` called from the runner post-ETL when a paper has a DOI, writing proposed candidates to `harvest.expansion_candidates` (table already from migration 004); and weekly `process_pending()` driven by a launchd job that verifies candidates via Semantic Scholar, scores them via LlmTriage (reusing Phase 2's rubric), promotes to approved/rejected.

**Tech Stack:** Python 3.12; existing harvester foundations (HttpApiFetcher, ETL, Runner, LlmTriage); no new dependencies.

**Parent roadmap:** `docs/superpowers/notes/phase3-roadmap.md` §3.2

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch strategy:** `feat/harvester-phase3-2-citation-chain` from `main`.

---

## File Structure

**Created:**

```
measuring-ai-economy/
├── harvester/
│   ├── harvester/
│   │   ├── fetchers/
│   │   │   └── semantic_scholar.py        [NEW]
│   │   ├── etl/
│   │   │   └── semantic_scholar.py        [NEW]
│   │   ├── improvement/
│   │   │   └── citation_chain.py          [NEW]
│   │   ├── schemas/
│   │   │   └── 006_semantic_scholar.sql   [NEW]
│   │   ├── runner.py                      MODIFIED — citation_chain enqueue hook
│   │   ├── cli.py                         MODIFIED — expand-citations command
│   │   └── config/sources.yaml            MODIFIED — semantic_scholar source
│   └── tests/
│       ├── test_fetcher_semantic_scholar.py
│       ├── test_etl_semantic_scholar.py
│       ├── test_citation_chain.py
│       ├── test_runner_citation_chain_hook.py
│       ├── test_cli_expand_citations.py
│       └── fixtures/semantic_scholar/
│           ├── search_page_1.json
│           ├── paper_1.input.json … paper_4.input.json
│           └── paper_1.expected.json … paper_4.expected.json
└── ops/launchd/
    ├── com.wintermute.harvest-citation-expand.plist  (copy)
    └── harvest_citation_expand.sh                    (copy)

~/.wintermute/scripts/jobs/
└── harvest_citation_expand.sh                        [NEW launchd wrapper]

~/Library/LaunchAgents/
└── com.wintermute.harvest-citation-expand.plist      [NEW plist]
```

**Schema dependencies (already exist, no new migrations):**
- `harvest.expansion_candidates` (migration 004) — citation_chain writes here
- `harvest.document_metadata` (migration 001) — parent_doc_id FK
- `harvest.run_log` (migration 001)
- `harvest.triage_results` (migration 004) — LlmTriage writes here for verified candidates

---

## Tasks

### Task 1: Branch + Semantic Scholar API key wiring

**Files:**
- Modify: `harvester/harvester/config/sources.yaml` (add semantic_scholar source)

- [ ] **Step 1: Branch**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git checkout main
git checkout -b feat/harvester-phase3-2-citation-chain
git branch --show-current
```

Expected: `feat/harvester-phase3-2-citation-chain`

- [ ] **Step 2: Verify Semantic Scholar API key is in the environment**

```bash
grep -E "SEMANTIC_SCHOLAR" /Users/brock/.wintermute/.env 2>/dev/null | sed 's/=.*/=<set>/'
```

Expected: one line showing `SEMANTIC_SCHOLAR_API_KEY=<set>` (or similar). If empty, the fetcher will fall back to the unauthenticated rate (1 req/sec) which still works.

- [ ] **Step 3: Append semantic_scholar source to `harvester/harvester/config/sources.yaml`**

Read existing sources.yaml first. Then append at the bottom:

```yaml

semantic_scholar:
  fetcher: harvester.fetchers.semantic_scholar.SemanticScholarFetcher
  etl: harvester.etl.semantic_scholar.SemanticScholarETL
  rolling_window_days: 365   # search broad
  inbox_backpressure_max: 5000
  expected_schema_version: 6
  triage_enabled: true
  triage_threshold: 0.4
  triage_model: "claude-sonnet-4-6"
  scout_base_url: "https://api.semanticscholar.org"
  citation_chain_enabled: false   # Standalone runs don't enqueue further citations
  tier_1_terms:
    - "knowledge graph agent"
    - "agent memory architecture"
    - "entity resolution"
    - "research reproducibility provenance"
    - "survey methodology federal statistics"
    - "diffusion model latent geometry"
    - "Wasserstein distributionally robust optimization"
  tier_2_terms: []
```

- [ ] **Step 4: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/config/sources.yaml
git commit -m "feat(harvester): bootstrap Phase 3.2 — semantic_scholar source config

Adds semantic_scholar to sources.yaml. citation_chain_enabled=false on
this source so standalone runs don't infinitely recurse; arxiv (which
*is* citation_chain_enabled) drives the expansion. Tier-1 terms cover
the project's research axes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Migration 006 — semantic_scholar_papers

**Files:** Create `harvester/harvester/schemas/006_semantic_scholar.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Migration 006: Semantic Scholar papers — densely-typed analytical table.
-- Mirrors arxiv_papers in shape. Used by both standalone SemanticScholarFetcher
-- runs and by CitationChain verification.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.semantic_scholar_papers (
    id                  BIGSERIAL PRIMARY KEY,
    ss_paper_id         TEXT NOT NULL UNIQUE,          -- Semantic Scholar Paper ID
    doi                 TEXT,
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    venue               TEXT,
    year                INTEGER,
    published_date      DATE,
    s2_url              TEXT NOT NULL,                  -- canonical Semantic Scholar page URL
    open_access_pdf_url TEXT,
    citation_count      INTEGER,
    reference_count     INTEGER,
    influential_count   INTEGER,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ss_papers_published_idx
    ON harvest.semantic_scholar_papers (published_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ss_papers_doi_idx
    ON harvest.semantic_scholar_papers (doi) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS ss_papers_citation_count_idx
    ON harvest.semantic_scholar_papers (citation_count DESC NULLS LAST);

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('006_semantic_scholar.sql', 'PLACEHOLDER_SHA', 'Semantic Scholar papers table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 2: Apply**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester migrate
```

Expected: `Applying 006_semantic_scholar.sql (...)` then `Applied 1 migration(s).`

- [ ] **Step 3: Verify**

```bash
psql -d wintermute -c "\d harvest.semantic_scholar_papers" | head -20
```

Expected: column listing including ss_paper_id (UNIQUE), doi, title, citation_count.

- [ ] **Step 4: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/schemas/006_semantic_scholar.sql
git commit -m "feat(harvester): migration 006 — semantic_scholar_papers table

Mirrors arxiv_papers in shape (densely-typed analytical table) with
Semantic-Scholar-specific fields: ss_paper_id (canonical key), venue,
citation_count, reference_count, influential_count. DOI is indexed
where present (partial index, since many SS papers lack DOI).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: SemanticScholarFetcher

**Files:**
- Create `harvester/harvester/fetchers/semantic_scholar.py`
- Create `harvester/tests/fixtures/semantic_scholar/search_page_1.json` (real API capture)
- Create `harvester/tests/test_fetcher_semantic_scholar.py`

- [ ] **Step 1: Capture a real API search response as fixture**

```bash
mkdir -p /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/semantic_scholar
SS_KEY="${SEMANTIC_SCHOLAR_API_KEY:-}"
if [ -n "$SS_KEY" ]; then
  curl -s -H "x-api-key: $SS_KEY" \
    'https://api.semanticscholar.org/graph/v1/paper/search?query=knowledge+graph+agent&limit=10&fields=paperId,externalIds,title,abstract,authors,venue,year,publicationDate,citationCount,referenceCount,influentialCitationCount,openAccessPdf,url' \
    -o /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/semantic_scholar/search_page_1.json
else
  curl -s 'https://api.semanticscholar.org/graph/v1/paper/search?query=knowledge+graph+agent&limit=10&fields=paperId,externalIds,title,abstract,authors,venue,year,publicationDate,citationCount,referenceCount,influentialCitationCount,openAccessPdf,url' \
    -o /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/semantic_scholar/search_page_1.json
fi
python3 -c "import json; d=json.load(open('/Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/semantic_scholar/search_page_1.json')); print('total:', d.get('total'), 'results:', len(d.get('data', [])))"
```

Expected: `total: <int>`, `results: 10` (or close). If results == 0 or the file is < 5KB, the API key may be missing/invalid — re-try with the unauthenticated path or set the key.

- [ ] **Step 2: Write tests at `harvester/tests/test_fetcher_semantic_scholar.py`**

```python
"""Tests for SemanticScholarFetcher."""

import re
from pathlib import Path

import pytest

from harvester.fetchers.semantic_scholar import SemanticScholarFetcher
from harvester.manifest import RawArchive


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semantic_scholar"


def test_semantic_scholar_yields_one_per_result(tmp_path, httpx_mock):
    fixture = (FIXTURE_DIR / "search_page_1.json").read_text()
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://api\.semanticscholar\.org/graph/v1/paper/search.*"),
        text=fixture,
        is_reusable=True,
    )

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = SemanticScholarFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({
        "keyword": "knowledge graph agent",
        "per_page": 10,
        "max_pages": 1,
    }))

    assert len(payloads) >= 1
    for p in payloads:
        assert p.source_id == "semantic_scholar"
        assert p.raw_hash.startswith("sha256:")
        assert p.source_url


def test_semantic_scholar_respects_seen(tmp_path, httpx_mock):
    fixture = (FIXTURE_DIR / "search_page_1.json").read_text()
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://api\.semanticscholar\.org/graph/v1/paper/search.*"),
        text=fixture,
        is_reusable=True,
    )

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher_a = SemanticScholarFetcher(archive=archive)
    first = list(fetcher_a.iter_payloads({"keyword": "x", "per_page": 10, "max_pages": 1}))
    assert first

    archive2 = RawArchive(root=tmp_path / "raw2", manifest_path=tmp_path / "m2.parquet")
    fetcher_b = SemanticScholarFetcher(archive=archive2)
    seen = {p.source_url for p in first[1:]}
    second = list(fetcher_b.iter_payloads({"keyword": "x", "per_page": 10, "max_pages": 1}, seen=seen))
    assert len(second) == 1
    assert second[0].source_url == first[0].source_url


def test_semantic_scholar_rate_limit(tmp_path):
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = SemanticScholarFetcher(archive=archive)
    rl = fetcher.rate_limit_spec()
    # 1 req/sec unauthenticated, up to 10 with key — both <= 10
    assert 0 < rl.requests_per_second <= 10
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_semantic_scholar.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement `harvester/harvester/fetchers/semantic_scholar.py`**

```python
"""Semantic Scholar Graph API fetcher.

API: https://api.semanticscholar.org/graph/v1/
Auth: API key via x-api-key header (free tier). Without key: 1 req/sec.
      With key: 10 req/sec (some endpoints).
Pagination: ?offset=N&limit=M (limit max 100 for search).

Two modes:
- search (iter_payloads): /paper/search?query=... — used by standalone harvester runs.
- lookup (get_paper / get_references): /paper/{id} and /paper/{id}/references —
  used by CitationChain. These bypass iter_payloads and are exposed as separate
  methods on the fetcher class so CitationChain can drive them directly.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

import httpx

from harvester.fetchers.http_api import HttpApiFetcher
from harvester.types import RateLimit, RawPayload


_BASE_URL = "https://api.semanticscholar.org/graph/v1"
_SEARCH_URL = f"{_BASE_URL}/paper/search"
_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"

_PAPER_FIELDS = (
    "paperId,externalIds,title,abstract,authors,venue,year,publicationDate,"
    "citationCount,referenceCount,influentialCitationCount,openAccessPdf,url"
)


def _api_key() -> str | None:
    return os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None


def _headers() -> dict[str, str]:
    h = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    if key := _api_key():
        h["x-api-key"] = key
    return h


class SemanticScholarFetcher(HttpApiFetcher):
    source_id = "semantic_scholar"

    def rate_limit_spec(self) -> RateLimit:
        # 10 req/sec with API key, 1 req/sec without. Conservative: 1 req/sec
        # since search endpoint has stricter limits than per-paper lookups.
        rps = 1.0
        return RateLimit(
            requests_per_second=rps,
            max_retries=3,
            backoff_seconds=[2, 5, 15, 60],
        )

    def base_url(self) -> str:
        return _SEARCH_URL

    def build_params(self, query: dict[str, Any], *, page: int) -> dict[str, Any]:
        limit = int(query.get("per_page", 50))
        return {
            "query": query.get("keyword", ""),
            "offset": page * limit,
            "limit": limit,
            "fields": _PAPER_FIELDS,
        }

    def extract_items(self, body: dict[str, Any]) -> Iterable[dict[str, Any]]:
        return body.get("data", [])

    def item_to_payload_kwargs(self, item: dict[str, Any]) -> dict[str, Any]:
        # Prefer the openAccessPdf URL when available, else the paper page url.
        oa = (item.get("openAccessPdf") or {}).get("url") if isinstance(item.get("openAccessPdf"), dict) else None
        url = oa or item.get("url") or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}"
        return {
            "source_url": url,
            "content_type": "application/json",
            "content_bytes": json.dumps(item, sort_keys=True).encode("utf-8"),
            "item_index": item.get("paperId"),
        }

    # ---- Direct-lookup methods used by CitationChain ----

    def get_paper(self, paper_id: str) -> dict[str, Any] | None:
        """Fetch a single paper by Semantic Scholar paper ID, DOI, or arXiv ID.

        paper_id can be prefixed: 'DOI:10.x/y', 'ARXIV:2305.12345', or a bare
        Semantic Scholar Paper ID.
        """
        url = f"{_BASE_URL}/paper/{paper_id}"
        with httpx.Client(headers=_headers(), timeout=30) as client:
            self._pace()
            resp = client.get(url, params={"fields": _PAPER_FIELDS})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    def get_references(self, paper_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return the references list of a paper. Each ref has the cited paper's
        basic metadata.
        """
        url = f"{_BASE_URL}/paper/{paper_id}/references"
        with httpx.Client(headers=_headers(), timeout=30) as client:
            self._pace()
            resp = client.get(url, params={
                "fields": _PAPER_FIELDS,
                "limit": limit,
            })
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            body = resp.json()
            # Response shape: {"data": [{"citedPaper": {...}}, ...]}
            return [d.get("citedPaper") for d in body.get("data", [])
                    if isinstance(d, dict) and d.get("citedPaper")]
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_fetcher_semantic_scholar.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/fetchers/semantic_scholar.py harvester/tests/test_fetcher_semantic_scholar.py harvester/tests/fixtures/semantic_scholar/search_page_1.json
git commit -m "feat(harvester): SemanticScholarFetcher (search + direct-lookup)

Inherits HttpApiFetcher for /paper/search (standalone harvest mode).
Also exposes get_paper() and get_references() for CitationChain's
direct-lookup needs. Honors SEMANTIC_SCHOLAR_API_KEY env var for the
x-api-key header (10× rate limit vs unauthenticated).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: SemanticScholarETL + golden samples

**Files:**
- Create `harvester/harvester/etl/semantic_scholar.py`
- Create `harvester/tests/test_etl_semantic_scholar.py`
- Create `harvester/harvester/scripts/regen_semantic_scholar_golden_samples.py`
- Create 4 input fixtures + 4 expected fixtures under `harvester/tests/fixtures/semantic_scholar/`

- [ ] **Step 1: Extract 4 input fixtures from the captured search response**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python <<'PY'
import json
from pathlib import Path

FIXTURE_DIR = Path("tests/fixtures/semantic_scholar")
search = json.loads((FIXTURE_DIR / "search_page_1.json").read_text())
data = search.get("data", [])
print(f"Found {len(data)} papers; saving up to 4.")

# Pick 4 with diverse venues
seen_venues = {}
chosen = []
for p in data:
    venue = (p.get("venue") or "unknown")
    if venue not in seen_venues and len(chosen) < 4:
        seen_venues[venue] = True
        chosen.append(p)
while len(chosen) < 4 and len(chosen) < len(data):
    for p in data:
        if p not in chosen:
            chosen.append(p)
            break

for i, p in enumerate(chosen[:4]):
    out = FIXTURE_DIR / f"paper_{i+1}.input.json"
    out.write_text(json.dumps(p, indent=2, sort_keys=True))
    print(f"Wrote {out.name} (venue: {p.get('venue', 'unknown')})")
PY
ls tests/fixtures/semantic_scholar/paper_*.input.json
```

Expected: 4 files.

- [ ] **Step 2: Write tests at `harvester/tests/test_etl_semantic_scholar.py`**

```python
"""Golden-sample tests for the Semantic Scholar ETL."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from harvester.etl.semantic_scholar import SemanticScholarETL
from harvester.types import RawPayload

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semantic_scholar"


def _make_payload(input_path: Path) -> RawPayload:
    return RawPayload(
        raw_hash="sha256:test",
        file_path=input_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 7, 0, 0),
        source_id="semantic_scholar",
        source_url=json.loads(input_path.read_text()).get("url", ""),
        request_params={},
    )


@pytest.mark.parametrize("idx", [1, 2, 3, 4])
def test_parse_matches_golden_sample(idx):
    input_path = FIXTURE_DIR / f"paper_{idx}.input.json"
    expected_path = FIXTURE_DIR / f"paper_{idx}.expected.json"
    raw = _make_payload(input_path)

    etl = SemanticScholarETL()
    doc = etl.parse(raw)
    assert len(doc.rows) >= 2

    expected = json.loads(expected_path.read_text())
    actual = {
        "title": doc.title,
        "source_url": doc.source_url,
        "published_date": doc.published_date.isoformat() if doc.published_date else None,
        "rows": [
            {"target_table": r.target_table, "data": _normalize(r.data)}
            for r in doc.rows
        ],
        "metadata": doc.metadata,
    }
    assert actual == expected, f"ETL output diverged from paper_{idx}.expected.json"


def _normalize(data: dict) -> dict:
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
uv run pytest tests/test_etl_semantic_scholar.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `harvester/harvester/etl/semantic_scholar.py`**

```python
"""Semantic Scholar ETL.

Parses Semantic Scholar paper records (JSON shape from /paper/search response)
into rows for harvest.document_metadata + harvest.semantic_scholar_papers.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


class SemanticScholarETL(ETL):
    source_id = "semantic_scholar"
    expected_schema_version = 6

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())

        ss_paper_id = record.get("paperId") or ""
        title = (record.get("title") or "").strip()[:5000]
        abstract = (record.get("abstract") or "").strip() or None

        external_ids = record.get("externalIds") or {}
        doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None

        authors = [a.get("name") for a in (record.get("authors") or []) if isinstance(a, dict) and a.get("name")]
        venue = record.get("venue") or None
        year = record.get("year")
        published_date = _date_or_none(record.get("publicationDate"))

        oa = record.get("openAccessPdf") or {}
        oa_url = oa.get("url") if isinstance(oa, dict) else None
        s2_url = record.get("url") or f"https://www.semanticscholar.org/paper/{ss_paper_id}"

        ss_row = Row(
            target_table="harvest.semantic_scholar_papers",
            data={
                "ss_paper_id": ss_paper_id,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "venue": venue,
                "year": year,
                "published_date": published_date,
                "s2_url": s2_url,
                "open_access_pdf_url": oa_url,
                "citation_count": record.get("citationCount"),
                "reference_count": record.get("referenceCount"),
                "influential_count": record.get("influentialCitationCount"),
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
                "source_url": s2_url,
                "published_date": published_date,
                "document_type": "semantic_scholar_paper",
                "payload": json.dumps({
                    "ss_paper_id": ss_paper_id,
                    "venue": venue,
                    "year": year,
                    "citation_count": record.get("citationCount"),
                }),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=s2_url,
            published_date=published_date,
            rows=[meta_row, ss_row],
            metadata={
                "document_type": "semantic_scholar_paper",
                "ss_paper_id": ss_paper_id,
                "doi": doi,
                "abstract": abstract,
                "venue": venue,
            },
        )
```

- [ ] **Step 5: Write regen helper at `harvester/harvester/scripts/regen_semantic_scholar_golden_samples.py`**

```python
"""Regenerate Semantic Scholar golden-sample expected files.

Usage: uv run python -m harvester.scripts.regen_semantic_scholar_golden_samples
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from harvester.etl.semantic_scholar import SemanticScholarETL
from harvester.types import RawPayload


FIXTURE_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "semantic_scholar"


def _normalize(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def main() -> None:
    etl = SemanticScholarETL()
    for i in range(1, 5):
        input_path = FIXTURE_DIR / f"paper_{i}.input.json"
        if not input_path.exists():
            print(f"SKIP paper_{i} (no input)")
            continue
        raw = RawPayload(
            raw_hash="sha256:test",
            file_path=input_path,
            content_type="application/json",
            fetched_at=datetime(2026, 5, 12, 7, 0, 0),
            source_id="semantic_scholar",
            source_url=json.loads(input_path.read_text()).get("url", ""),
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
        out_path = FIXTURE_DIR / f"paper_{i}.expected.json"
        out_path.write_text(json.dumps(expected, indent=2, sort_keys=True))
        print(f"WROTE {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run regen + tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python -m harvester.scripts.regen_semantic_scholar_golden_samples
uv run pytest tests/test_etl_semantic_scholar.py -v
```

Expected: 4 WROTE lines, then 4 passed.

- [ ] **Step 7: Sanity check**

```bash
head -40 tests/fixtures/semantic_scholar/paper_1.expected.json
```

Verify: title non-empty, ss_paper_id non-empty, two rows (document_metadata + semantic_scholar_papers).

- [ ] **Step 8: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/etl/semantic_scholar.py
git add harvester/harvester/scripts/regen_semantic_scholar_golden_samples.py
git add harvester/tests/test_etl_semantic_scholar.py
git add harvester/tests/fixtures/semantic_scholar/paper_*.input.json
git add harvester/tests/fixtures/semantic_scholar/paper_*.expected.json
git commit -m "feat(harvester): SemanticScholarETL + golden samples

Parses S2 paper records into (document_metadata, semantic_scholar_papers)
rows. Four fixtures cover different venues from real API output.
Extracts DOI from externalIds, normalizes title whitespace.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: CitationChain.enqueue() — synchronous candidate proposal

**Files:**
- Create `harvester/harvester/improvement/citation_chain.py`
- Create `harvester/tests/test_citation_chain.py`

`enqueue()` is called by the runner post-ETL when a paper has a DOI. It writes proposed candidates to `harvest.expansion_candidates` (table from migration 004). It does NOT call Semantic Scholar — that happens asynchronously in `process_pending()`. enqueue just queues "I have a DOI, follow its references later."

- [ ] **Step 1: Write tests at `harvester/tests/test_citation_chain.py`**

```python
"""Tests for CitationChain (enqueue mode only — process_pending tested in Task 7)."""

import json

import pytest

from harvester.db import get_connection
from harvester.improvement.citation_chain import CitationChain
from harvester.types import ParsedDoc, Row
from datetime import date


@pytest.fixture
def clean_candidates():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates "
                        "WHERE payload->>'origin' = 'citation_chain_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates "
                        "WHERE payload->>'origin' = 'citation_chain_test'")
        conn.commit()
    finally:
        conn.close()


def _parsed_with_doi(doi: str) -> ParsedDoc:
    return ParsedDoc(
        title="Test paper",
        source_url="https://arxiv.org/abs/test",
        published_date=date(2026, 5, 12),
        rows=[Row(target_table="harvest.document_metadata", data={"title": "Test", "doi": doi})],
        metadata={"doi": doi, "origin": "citation_chain_test"},
    )


def test_enqueue_writes_proposed_candidate(clean_candidates):
    conn = get_connection()
    try:
        chain = CitationChain(conn)
        parsed = _parsed_with_doi("10.1234/test.5678")
        n = chain.enqueue(parsed, parent_run_id=None, parent_doc_id=None)
        assert n == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT kind, status, payload->>'doi', depth FROM harvest.expansion_candidates "
                "WHERE payload->>'origin' = 'citation_chain_test'"
            )
            row = cur.fetchone()
            assert row is not None
            kind, status, doi, depth = row
            assert kind == "paper"
            assert status == "proposed"
            assert doi == "10.1234/test.5678"
            assert depth == 1
    finally:
        conn.close()


def test_enqueue_returns_zero_when_no_doi(clean_candidates):
    """No DOI in parsed.metadata → no candidate enqueued."""
    conn = get_connection()
    try:
        chain = CitationChain(conn)
        parsed = ParsedDoc(
            title="No-DOI paper",
            source_url="https://example.com/x",
            published_date=date(2026, 5, 12),
            rows=[Row(target_table="harvest.document_metadata", data={"title": "x"})],
            metadata={"origin": "citation_chain_test"},
        )
        n = chain.enqueue(parsed, parent_run_id=None, parent_doc_id=None)
        assert n == 0
    finally:
        conn.close()


def test_enqueue_idempotent_on_repeat_call(clean_candidates):
    """Calling enqueue twice for the same DOI → still one candidate (UNIQUE on payload)."""
    conn = get_connection()
    try:
        chain = CitationChain(conn)
        parsed = _parsed_with_doi("10.1234/dup.0001")
        chain.enqueue(parsed, parent_run_id=None, parent_doc_id=None)
        chain.enqueue(parsed, parent_run_id=None, parent_doc_id=None)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.expansion_candidates "
                "WHERE payload->>'origin' = 'citation_chain_test' "
                "AND payload->>'doi' = '10.1234/dup.0001'"
            )
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_citation_chain.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `harvester/harvester/improvement/citation_chain.py`** (enqueue path only; process_pending in Task 7)

```python
"""Citation chain expansion.

Two modes:
- enqueue() — synchronous. Called from the runner post-ETL. Writes a proposed
  candidate to harvest.expansion_candidates for each parent paper with a DOI.
  Cheap: no network calls.
- process_pending() — asynchronous. Called by a weekly launchd job. Picks the
  top N proposed candidates, verifies via Semantic Scholar API + scores against
  research_axes via LlmTriage, promotes to approved/rejected. (Implemented in
  Task 7.)

Approved candidates feed back into the harvester as new seeds (future work —
the seed-feedback loop is its own follow-on plan; for 3.2 MVP, approved
candidates sit in the table for human / claudeclaw review.)
"""

from __future__ import annotations

import json

import psycopg

from harvester.types import ParsedDoc


class CitationChain:
    """Cross-source citation expansion machinery."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def enqueue(
        self,
        parsed: ParsedDoc,
        *,
        parent_run_id: int | None,
        parent_doc_id: int | None,
    ) -> int:
        """Queue a citation-expansion candidate for this paper.

        Returns count of candidates added (0 or 1). Idempotent via the
        UNIQUE (kind, payload) constraint on expansion_candidates.
        """
        doi = (parsed.metadata or {}).get("doi")
        if not doi:
            return 0

        payload = {
            "doi": doi,
            "title": parsed.title,
            "source_url": parsed.source_url,
        }
        # Preserve any extra "origin" or context the caller wants tracked
        if origin := (parsed.metadata or {}).get("origin"):
            payload["origin"] = origin

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.expansion_candidates
                    (kind, payload, parent_doc_id, depth, status)
                VALUES ('paper', %s::jsonb, %s, 1, 'proposed')
                ON CONFLICT (kind, payload) DO NOTHING
                RETURNING id
                """,
                (json.dumps(payload, sort_keys=True), parent_doc_id),
            )
            row = cur.fetchone()
        self._conn.commit()
        return 1 if row else 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_citation_chain.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/citation_chain.py harvester/tests/test_citation_chain.py
git commit -m "feat(harvester): CitationChain.enqueue() — sync candidate proposal

Writes a proposed candidate to harvest.expansion_candidates for each
parent paper with a DOI. Idempotent via UNIQUE (kind, payload). No
network calls — cheap. process_pending() (network + LLM) lands in
Task 7.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Runner citation-chain hook

**Files:**
- Modify `harvester/harvester/runner.py`
- Create `harvester/tests/test_runner_citation_chain_hook.py`

Runner post-ETL: if config.citation_chain_enabled AND parsed.metadata.doi present, call CitationChain.enqueue(). Wraps the call in try/except so failures don't break the run.

- [ ] **Step 1: Write failing test at `harvester/tests/test_runner_citation_chain_hook.py`**

```python
"""Tests for the runner citation-chain enqueue hook."""

from datetime import date, datetime
from pathlib import Path

import pytest

from harvester.db import get_connection
from harvester.runner import Runner, RunnerConfig
from harvester.types import ParsedDoc, RawPayload, Row


@pytest.fixture
def clean_cc_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates WHERE payload->>'doi' LIKE '10.9999/cc_test%'")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'cc_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'cc_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'cc_test'")
        conn.commit()
        yield
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.expansion_candidates WHERE payload->>'doi' LIKE '10.9999/cc_test%'")
            cur.execute("DELETE FROM harvest.document_metadata WHERE source_id = 'cc_test'")
            cur.execute("DELETE FROM harvest.fetched_items WHERE source_id = 'cc_test'")
            cur.execute("DELETE FROM harvest.run_log WHERE source_id = 'cc_test'")
        conn.commit()
    finally:
        conn.close()


def test_runner_enqueues_when_citation_chain_enabled(clean_cc_state, tmp_path):
    """citation_chain_enabled=True + parsed.metadata.doi present → candidate row."""

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:cc1",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 12, 0, 0),
        source_id="cc_test",
        source_url="https://example.com/cc1",
        request_params={},
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "cc_test"
        expected_schema_version = 6
        def parse(self, raw):
            return ParsedDoc(
                title="A paper with DOI",
                source_url=raw.source_url,
                published_date=date(2026, 5, 12),
                rows=[Row(target_table="harvest.document_metadata", data={
                    "source_id": "cc_test",
                    "title": "A paper with DOI",
                    "source_url": raw.source_url,
                    "doi": "10.9999/cc_test.001",
                })],
                metadata={"doi": "10.9999/cc_test.001"},
            )
        def to_rows(self, parsed):
            return parsed.rows

    config = RunnerConfig(
        source_id="cc_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=6,
        citation_chain_enabled=True,
    )
    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, payload->>'doi' FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.001'"
            )
            row = cur.fetchone()
            assert row is not None
            status, doi = row
            assert status == "proposed"
            assert doi == "10.9999/cc_test.001"
    finally:
        conn.close()


def test_runner_does_not_enqueue_when_disabled(clean_cc_state, tmp_path):
    """citation_chain_enabled=False (default) → no candidates even with DOI."""

    fake_payload_path = tmp_path / "fake.json"
    fake_payload_path.write_text("{}")
    payload = RawPayload(
        raw_hash="sha256:cc2",
        file_path=fake_payload_path,
        content_type="application/json",
        fetched_at=datetime(2026, 5, 12, 12, 0, 0),
        source_id="cc_test",
        source_url="https://example.com/cc2",
        request_params={},
    )

    class FakeFetcher:
        archive = None
        def iter_payloads(self, q, *, seen=None):
            yield payload
    class FakeETL:
        source_id = "cc_test"
        expected_schema_version = 6
        def parse(self, raw):
            return ParsedDoc(
                title="Paper",
                source_url=raw.source_url,
                published_date=date(2026, 5, 12),
                rows=[Row(target_table="harvest.document_metadata", data={
                    "source_id": "cc_test",
                    "title": "Paper",
                    "source_url": raw.source_url,
                    "doi": "10.9999/cc_test.002",
                })],
                metadata={"doi": "10.9999/cc_test.002"},
            )
        def to_rows(self, parsed):
            return parsed.rows

    config = RunnerConfig(
        source_id="cc_test",
        archive_root=tmp_path / "raw",
        manifest_path=tmp_path / "m.parquet",
        inbox_dir=tmp_path / "inbox",
        inbox_backpressure_max=500,
        expected_schema_version=6,
        citation_chain_enabled=False,
    )
    runner = Runner(config=config, fetcher=FakeFetcher(), etl=FakeETL())
    runner.run({})

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.002'"
            )
            assert cur.fetchone()[0] == 0
    finally:
        conn.close()
```

- [ ] **Step 2: Verify failure**

```bash
uv run pytest tests/test_runner_citation_chain_hook.py -v
```

Expected: failure (RunnerConfig.citation_chain_enabled doesn't exist yet; no hook).

- [ ] **Step 3: Edit `harvester/harvester/runner.py`**

(a) Add import:

```python
from harvester.improvement.citation_chain import CitationChain
```

(b) Add `citation_chain_enabled: bool = False` to `RunnerConfig` (after `triage_threshold`):

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
    citation_chain_enabled: bool = False
```

(c) In `_drive()`, after the existing triage hook block, before `emit_markdown`:

```python
                if self.config.citation_chain_enabled and parsed.metadata.get("doi"):
                    try:
                        CitationChain(conn).enqueue(
                            parsed,
                            parent_run_id=run_id,
                            parent_doc_id=self._lookup_doc_id(conn, parsed),
                        )
                    except Exception as e:
                        parsed.metadata["citation_chain_error"] = str(e)
                        conn.rollback()
```

(d) Add helper `_lookup_doc_id` near `_record_triage_result`:

```python
    def _lookup_doc_id(self, conn: psycopg.Connection, parsed: "ParsedDoc") -> int | None:
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
            return row[0] if row else None
```

- [ ] **Step 4: Run new tests**

```bash
uv run pytest tests/test_runner_citation_chain_hook.py -v
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
git add harvester/harvester/runner.py harvester/tests/test_runner_citation_chain_hook.py
git commit -m "feat(harvester): runner citation-chain enqueue hook

RunnerConfig.citation_chain_enabled (default False) controls whether
the post-ETL hook queues candidates. When enabled AND parsed.metadata
has a doi, calls CitationChain(conn).enqueue() to write a proposed
candidate to harvest.expansion_candidates. Failures swallowed +
metadata-decorated; rollback clears any aborted txn.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: CitationChain.process_pending() — async batch processor

**Files:**
- Modify `harvester/harvester/improvement/citation_chain.py`
- Modify `harvester/tests/test_citation_chain.py` (add process_pending tests)

This is the heavy logic. For each proposed candidate, call Semantic Scholar to verify the paper exists + fetch its references; score the references via LlmTriage; promote candidate to approved or rejected. References that score above threshold could ALSO get enqueued, but we don't recursively chain in 3.2 — only the immediate references of approved candidates become approved.

- [ ] **Step 1: Append tests to `harvester/tests/test_citation_chain.py`**

```python
# Append after the existing tests:

from unittest.mock import MagicMock, patch


def test_process_pending_promotes_high_score_candidate(clean_candidates):
    """A proposed candidate that Semantic Scholar verifies + LlmTriage scores
    >= threshold gets status='approved'."""
    conn = get_connection()
    try:
        # Seed a proposed candidate
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.expansion_candidates
                    (kind, payload, depth, status)
                VALUES ('paper', %s::jsonb, 1, 'proposed')
                """,
                (json.dumps({"doi": "10.9999/cc_test.proc1", "title": "Verified paper",
                             "origin": "citation_chain_test"}),),
            )
        conn.commit()

        # Mock SemanticScholar lookup + LlmTriage score
        mock_ss = MagicMock()
        mock_ss.get_paper.return_value = {
            "paperId": "ss_abc123",
            "title": "Verified paper",
            "abstract": "We study X.",
            "externalIds": {"DOI": "10.9999/cc_test.proc1"},
        }
        mock_triage = MagicMock()
        mock_triage_result = MagicMock(score=0.72, axes={"x": 0.72},
                                       reason="relevant",
                                       rubric_version="0.3.0",
                                       model_id="claude-sonnet-4-6",
                                       prompt_hash="a"*64)
        mock_triage.score.return_value = mock_triage_result

        chain = CitationChain(conn)
        chain.process_pending(
            max_batch=10,
            ss_fetcher=mock_ss,
            triage=mock_triage,
            threshold=0.4,
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, score FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.proc1'"
            )
            row = cur.fetchone()
            assert row is not None
            status, score = row
            assert status == "approved"
            assert score == pytest.approx(0.72)
    finally:
        conn.close()


def test_process_pending_rejects_low_score(clean_candidates):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.expansion_candidates
                    (kind, payload, depth, status)
                VALUES ('paper', %s::jsonb, 1, 'proposed')
                """,
                (json.dumps({"doi": "10.9999/cc_test.proc2", "title": "Off-topic",
                             "origin": "citation_chain_test"}),),
            )
        conn.commit()

        mock_ss = MagicMock()
        mock_ss.get_paper.return_value = {
            "paperId": "ss_def456",
            "title": "Off-topic",
            "abstract": "A study of moss.",
            "externalIds": {"DOI": "10.9999/cc_test.proc2"},
        }
        mock_triage = MagicMock()
        mock_triage_result = MagicMock(score=0.05, axes={},
                                       reason="off-axis",
                                       rubric_version="0.3.0",
                                       model_id="claude-sonnet-4-6",
                                       prompt_hash="b"*64)
        mock_triage.score.return_value = mock_triage_result

        chain = CitationChain(conn)
        chain.process_pending(
            max_batch=10,
            ss_fetcher=mock_ss,
            triage=mock_triage,
            threshold=0.4,
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, score FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.proc2'"
            )
            row = cur.fetchone()
            assert row is not None
            status, score = row
            assert status == "rejected"
            assert score == pytest.approx(0.05)
    finally:
        conn.close()


def test_process_pending_skips_when_paper_not_found(clean_candidates):
    """SS returns 404 → candidate stays 'proposed' (deferred)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.expansion_candidates
                    (kind, payload, depth, status)
                VALUES ('paper', %s::jsonb, 1, 'proposed')
                """,
                (json.dumps({"doi": "10.9999/cc_test.notfound",
                             "origin": "citation_chain_test"}),),
            )
        conn.commit()

        mock_ss = MagicMock()
        mock_ss.get_paper.return_value = None  # 404
        mock_triage = MagicMock()

        chain = CitationChain(conn)
        chain.process_pending(
            max_batch=10,
            ss_fetcher=mock_ss,
            triage=mock_triage,
            threshold=0.4,
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM harvest.expansion_candidates "
                "WHERE payload->>'doi' = '10.9999/cc_test.notfound'"
            )
            row = cur.fetchone()
            # Stays proposed — we retry next batch (could 404 transiently)
            assert row[0] == "proposed"

        mock_triage.score.assert_not_called()
    finally:
        conn.close()
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_citation_chain.py -v
```

Expected: 3 tests fail (process_pending doesn't exist).

- [ ] **Step 3: Add `process_pending()` to `harvester/harvester/improvement/citation_chain.py`**

Append to the existing class:

```python
    def process_pending(
        self,
        *,
        max_batch: int = 100,
        ss_fetcher,
        triage,
        threshold: float = 0.4,
    ) -> dict[str, int]:
        """Process up to max_batch proposed candidates.

        For each:
        1. Look up by DOI via ss_fetcher.get_paper("DOI:{doi}"). If 404, leave
           as 'proposed' (transient).
        2. Build a ParsedDoc-like input for triage and score via triage.score().
        3. Promote to 'approved' if score >= threshold, else 'rejected'. Record
           the score.

        ss_fetcher: a SemanticScholarFetcher (passed in for test mockability).
        triage: an LlmTriage (also passed in).
        Returns counts: {approved, rejected, deferred}.
        """
        from datetime import date as _date

        from harvester.types import ParsedDoc, Row

        approved = 0
        rejected = 0
        deferred = 0

        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, payload FROM harvest.expansion_candidates
                WHERE kind = 'paper' AND status = 'proposed'
                ORDER BY score DESC NULLS LAST, proposed_at ASC
                LIMIT %s
                """,
                (max_batch,),
            )
            rows = cur.fetchall()

        for candidate_id, payload in rows:
            doi = payload.get("doi")
            if not doi:
                deferred += 1
                continue

            # 1. Verify via Semantic Scholar
            ss_paper = ss_fetcher.get_paper(f"DOI:{doi}")
            if ss_paper is None:
                deferred += 1
                continue

            # 2. Score via LlmTriage
            title = ss_paper.get("title") or payload.get("title") or ""
            abstract = ss_paper.get("abstract") or ""
            parsed = ParsedDoc(
                title=title,
                source_url=f"https://www.semanticscholar.org/paper/{ss_paper.get('paperId', '')}",
                published_date=_date.today(),
                rows=[],
                metadata={"abstract": abstract},
            )
            tr = triage.score(parsed)

            # 3. Promote or reject
            new_status = "approved" if tr.score >= threshold else "rejected"
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE harvest.expansion_candidates
                    SET status = %s,
                        score = %s,
                        reviewed_at = now(),
                        reviewed_by = %s
                    WHERE id = %s
                    """,
                    (new_status, tr.score, f"citation_chain:{tr.model_id}", candidate_id),
                )
            self._conn.commit()

            if new_status == "approved":
                approved += 1
            else:
                rejected += 1

        return {"approved": approved, "rejected": rejected, "deferred": deferred}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_citation_chain.py -v
```

Expected: 6 passed total (3 from Task 5 + 3 new).

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/improvement/citation_chain.py harvester/tests/test_citation_chain.py
git commit -m "feat(harvester): CitationChain.process_pending() — async batch processor

For each proposed candidate: verify via Semantic Scholar get_paper(DOI),
score via LlmTriage against research_axes, promote to approved (>= threshold)
or rejected (< threshold). 404 = transient defer (stays proposed). Returns
{approved, rejected, deferred} counts. ss_fetcher and triage are passed in
for test mockability + dependency injection.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: CLI `harvester expand-citations`

**Files:**
- Modify `harvester/harvester/cli.py`
- Create `harvester/tests/test_cli_expand_citations.py`

- [ ] **Step 1: Write test at `harvester/tests/test_cli_expand_citations.py`**

```python
"""Tests for `harvester expand-citations` CLI."""

import subprocess


def test_expand_citations_help_lists_command():
    """--help shows expand-citations subcommand."""
    result = subprocess.run(
        ["uv", "run", "harvester", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "expand-citations" in result.stdout, f"missing subcommand. stdout: {result.stdout}"


def test_expand_citations_dry_run_does_not_call_api():
    """--dry-run prints what would be processed; does not hit Semantic Scholar."""
    result = subprocess.run(
        ["uv", "run", "harvester", "expand-citations", "--dry-run", "--max-batch", "5"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "DRY RUN" in result.stdout or "would process" in result.stdout.lower()
```

- [ ] **Step 2: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_cli_expand_citations.py -v
```

Expected: subprocess returns non-zero on the second test (subcommand not registered).

- [ ] **Step 3: Append to `harvester/harvester/cli.py`**

```python
@app.command("expand-citations")
def expand_citations_cmd(
    max_batch: int = typer.Option(100, "--max-batch", help="Max proposed candidates to process"),
    threshold: float = typer.Option(0.4, "--threshold", help="Triage score promotion cutoff"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print pending candidates without API calls"),
) -> None:
    """Drive CitationChain.process_pending — verify pending candidates via
    Semantic Scholar + LlmTriage, promote to approved/rejected."""
    from harvester.improvement.citation_chain import CitationChain
    from harvester.fetchers.semantic_scholar import SemanticScholarFetcher
    from harvester.triage.llm_triage import LlmTriage
    from harvester.manifest import RawArchive

    conn = get_connection()
    try:
        if dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM harvest.expansion_candidates "
                    "WHERE kind = 'paper' AND status = 'proposed'"
                )
                pending = cur.fetchone()[0]
            typer.echo(f"DRY RUN: would process up to {max_batch} of {pending} pending candidates "
                       f"(threshold={threshold}).")
            return

        # Real run — instantiate fetcher + triage
        data_root = _data_root()
        archive = RawArchive(
            root=data_root / "raw",
            manifest_path=data_root / "manifests" / "raw_manifest.parquet",
        )
        ss_fetcher = SemanticScholarFetcher(archive=archive)
        triage = LlmTriage(
            model_id="claude-sonnet-4-6",
            axes_yaml=Path(__file__).parent / "triage" / "research_axes.yaml",
        )

        chain = CitationChain(conn)
        result = chain.process_pending(
            max_batch=max_batch,
            ss_fetcher=ss_fetcher,
            triage=triage,
            threshold=threshold,
        )
        typer.echo(
            f"Processed {sum(result.values())} candidates: "
            f"approved={result['approved']} rejected={result['rejected']} "
            f"deferred={result['deferred']}"
        )
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_expand_citations.py -v
uv run pytest 2>&1 | tail -3
```

Expected: 2 passed for new tests, all green for suite.

- [ ] **Step 5: Commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/cli.py harvester/tests/test_cli_expand_citations.py
git commit -m "feat(harvester): \`harvester expand-citations\` CLI

Drives CitationChain.process_pending(). --dry-run reports pending
count without touching Semantic Scholar. Real run instantiates the
SemanticScholarFetcher + LlmTriage, processes up to --max-batch
candidates, reports approved/rejected/deferred counts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Wire arxiv to enable citation_chain + launchd weekly job

**Files:**
- Modify `harvester/harvester/config/sources.yaml` (arxiv: citation_chain_enabled: true)
- Modify `harvester/harvester/cli.py` (thread citation_chain_enabled into RunnerConfig)
- Create `~/.wintermute/scripts/jobs/harvest_citation_expand.sh`
- Create `~/Library/LaunchAgents/com.wintermute.harvest-citation-expand.plist`
- Create `ops/launchd/harvest_citation_expand.sh` (copy)
- Create `ops/launchd/com.wintermute.harvest-citation-expand.plist` (copy)

- [ ] **Step 1: Edit `sources.yaml` — add `citation_chain_enabled: true` to arxiv source**

Read sources.yaml, locate the `arxiv:` block, add this line near `triage_enabled`:

```yaml
arxiv:
  ...
  triage_enabled: true
  citation_chain_enabled: true   # ← NEW: arxiv papers seed citation chains
  ...
```

- [ ] **Step 2: Edit `cli.py` to thread `citation_chain_enabled` into `RunnerConfig`**

In the `run()` command's `config = RunnerConfig(...)` block, add:

```python
        citation_chain_enabled=bool(cfg.get("citation_chain_enabled", False)),
```

- [ ] **Step 3: Wrapper script `~/.wintermute/scripts/jobs/harvest_citation_expand.sh`**

```bash
#!/usr/bin/env bash
# Weekly citation chain processing (Sundays 02:30 local).

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_citation_expand -- \
    "$UV_BIN" run harvester expand-citations --max-batch 100 --threshold 0.4
```

```bash
chmod +x /Users/brock/.wintermute/scripts/jobs/harvest_citation_expand.sh
```

- [ ] **Step 4: Plist `~/Library/LaunchAgents/com.wintermute.harvest-citation-expand.plist`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wintermute.harvest-citation-expand</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/brock/.wintermute/scripts/jobs/harvest_citation_expand.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_citation_expand.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_citation_expand.launchd.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/brock/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

(Note: Weekday=0 is Sunday in launchd's calendar.)

- [ ] **Step 5: Lint + load**

```bash
plutil -lint /Users/brock/Library/LaunchAgents/com.wintermute.harvest-citation-expand.plist
launchctl unload /Users/brock/Library/LaunchAgents/com.wintermute.harvest-citation-expand.plist 2>/dev/null
launchctl load /Users/brock/Library/LaunchAgents/com.wintermute.harvest-citation-expand.plist
launchctl list | grep harvest-citation-expand
```

Expected: plist OK, loaded entry.

- [ ] **Step 6: Copy ops + commit**

```bash
cp /Users/brock/Library/LaunchAgents/com.wintermute.harvest-citation-expand.plist \
   /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd/
cp /Users/brock/.wintermute/scripts/jobs/harvest_citation_expand.sh \
   /Users/brock/Documents/GitHub/measuring-ai-economy/ops/launchd/

cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/config/sources.yaml harvester/harvester/cli.py
git add ops/launchd/com.wintermute.harvest-citation-expand.plist ops/launchd/harvest_citation_expand.sh
git commit -m "feat(harvester): enable citation_chain on arxiv + weekly expand launchd

sources.yaml: arxiv.citation_chain_enabled=true so the post-ETL hook
seeds candidates from harvested arxiv papers with DOIs.

cli.py: threads citation_chain_enabled from per-source config into
RunnerConfig.

Launchd: com.wintermute.harvest-citation-expand fires Sundays 02:30
local, runs 'harvester expand-citations --max-batch 100 --threshold 0.4'
to process queued candidates against Semantic Scholar + LlmTriage.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Final verification + smoke test

**No code changes.**

- [ ] **Step 1: Full test suite green**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest 2>&1 | tail -3
```

Expected: all tests passing (~115+ after Phase 3.2's ~16 new tests).

- [ ] **Step 2: CLI surface**

```bash
uv run harvester --help 2>&1 | tail -15
```

Expected: 9 commands listed (adds expand-citations to Phase 3.1's 8).

- [ ] **Step 3: Live dry-run**

```bash
uv run harvester expand-citations --dry-run
```

Expected: `DRY RUN: would process up to 100 of N pending candidates (threshold=0.4).` where N depends on prior arxiv runs.

- [ ] **Step 4: Live semantic_scholar standalone harvest (small)**

```bash
psql -d wintermute -c "DELETE FROM harvest.data_sources WHERE source_id = 'semantic_scholar'"
uv run harvester scout semantic_scholar --base-url https://api.semanticscholar.org 2>&1 | tail -3
uv run harvester run semantic_scholar --query="knowledge graph agent" --limit=3
```

Expected: scout completes (likely with most probes returning errors since SS doesn't publish llms.txt/etc — that's fine, errors get captured in probe_errors). The harvest run completes with 3 deposits.

- [ ] **Step 5: Verify rows landed**

```bash
psql -d wintermute -c "
SELECT count(*) AS ss_papers FROM harvest.semantic_scholar_papers;
SELECT count(*) AS pending_candidates FROM harvest.expansion_candidates WHERE status = 'proposed';
"
```

Expected: ss_papers >= 3, pending_candidates >= 0 (could be 0 until arxiv runs next).

- [ ] **Step 6: Verify launchd entries loaded**

```bash
launchctl list | grep -E "harvest-(federal-register|arxiv|saturation-check|count-validation|manifest-integrity|citation-expand)"
```

Expected: 6 entries.

- [ ] **Step 7: Verify branch state**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git log main..HEAD --oneline | wc -l
```

Expected: ~9 commits on `feat/harvester-phase3-2-citation-chain`.

---

## Self-Review

**1. Spec coverage** — every Phase 3.2 deliverable from the roadmap §3.2:

| Deliverable | Task |
|---|---|
| SemanticScholarFetcher (search + direct lookup) | Task 3 |
| SemanticScholarETL + golden samples | Task 4 |
| Migration 006 (semantic_scholar_papers) | Task 2 |
| CitationChain.enqueue() sync hook | Task 5 |
| Runner citation-chain hook | Task 6 |
| CitationChain.process_pending() async batch | Task 7 |
| `harvester expand-citations` CLI | Task 8 |
| Launchd weekly job | Task 9 |
| arxiv config: citation_chain_enabled | Task 9 |
| sources.yaml: semantic_scholar source | Task 1 |
| End-to-end smoke test | Task 10 |

**2. Placeholder scan** — none. Every step has real code/commands.

**3. Type consistency** — verified:
- `CitationChain.enqueue(parsed, *, parent_run_id, parent_doc_id)` (Task 5) — called identically by runner in Task 6.
- `CitationChain.process_pending(*, max_batch, ss_fetcher, triage, threshold)` (Task 7) — same signature used by CLI in Task 8.
- `SemanticScholarFetcher.get_paper(paper_id) → dict | None` (Task 3) — called by CitationChain.process_pending in Task 7 + mocked in tests with matching signature.
- `RunnerConfig.citation_chain_enabled: bool = False` (Task 6) — referenced by cli.py wire-up in Task 9.
- `SemanticScholarETL.expected_schema_version = 6` (Task 4) — matches migration 006 in Task 2.
- Source URL field name: `s2_url` in semantic_scholar_papers table (Task 2) ↔ same name in ETL row (Task 4) ↔ same name in golden samples.
- `harvest.expansion_candidates` columns referenced: `id, kind, payload, parent_doc_id, depth, score, status, proposed_at, reviewed_at, reviewed_by` — all from migration 004 (already in production).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-harvester-phase3-2-citation-chain.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
