# SSRN Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the SSRN block of `~/.wintermute/scripts/search_papers.py` into the harvester architecture as a first-class `ssrn` source. Two-stage Crawl4ai flow (search page → paper pages). Closes the roadmap §3.3 source-migrations trilogy (zenodo + url_drain + ssrn).

**Architecture:** `SsrnFetcher` inherits `Crawl4aiFetcher` but **overrides `iter_payloads` entirely** for the two-stage flow: (1) crawl SSRN's `/sol3/results.cfm` search page for a keyword, (2) regex-extract `abstract_id` paper URLs from the rendered markdown, (3) crawl each paper page. `SsrnETL` parses one paper page's markdown into a generic `harvest.document_metadata` row plus a dense `harvest.ssrn_records` row. Migration 011 adds the analytical table. Conservative rate limits — SSRN blocks aggressive scrapers.

**Tech Stack:** Python 3.12, psycopg, httpx, typer, uv, `crawl4ai` (`uv sync --extra html`, already installed). No new dependencies.

**Heads-up — marginal source value:** SSRN's strengths are economics, finance, law, behavioral econ. Wintermute's research axes are stochastic dynamics, canine cognition, martial arts, exercise/training science, mental performance, complexity. Overlap is narrow — mostly stochastic models in financial math and SDE applications. **The tier_1 set is intentionally small (8 terms)** and focused on that overlap. After the 3-day soak, the operational note (Task 6) calls for an explicit value evaluation: if triage scores stay below 0.3 average or deposit-rate is < 30% of fetched, retire the source via `launchctl unload`. Don't grow the corpus just because the source ships.

**Risks:**
- **SSRN bot detection.** Known to issue 403s + captcha redirects against headless browsers. Crawl4ai's Playwright defaults handle the basics, but persistent blocks may surface during smoke. The fetcher paces at 0.2 req/sec (1 req per 5s) and uses long backoffs.
- **HTML structure drift.** SSRN's paper pages are CFM-rendered; HTML can change. The ETL parses with heuristic regex against markdown — flagged in the plan as "fragile, refine on smoke."

**Spec source:** Roadmap §3.3 in `docs/superpowers/notes/phase3-roadmap.md`. Plan mirrors `docs/superpowers/plans/2026-05-13-zenodo-migration.md` and `2026-05-13-url-drain-migration.md` structurally.

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch:** `feat/ssrn-migration` (from `main`; main is at the fix-merge commit `741a5e7`).

**Verification model:** 3-day soak with value-evaluation gate. Cutover sunsets the SSRN block of `search_papers.py` (the last source in that legacy script — after this, the script can be archived in full).

---

## File Structure

**Created:**

```
measuring-ai-economy/
├── harvester/
│   ├── harvester/
│   │   ├── fetchers/
│   │   │   └── ssrn.py                            [NEW]
│   │   ├── etl/
│   │   │   └── ssrn.py                            [NEW]
│   │   └── schemas/
│   │       └── 011_ssrn_records.sql               [NEW]
│   └── tests/
│       ├── fixtures/
│       │   └── ssrn/                              [NEW dir]
│       │       ├── search_page_sde.md             (synthetic markdown of search results)
│       │       ├── paper_sde_finance.md           (synthetic paper-page markdown)
│       │       ├── paper_sde_finance.expected.json
│       │       ├── paper_info_geometry.md
│       │       ├── paper_info_geometry.expected.json
│       │       ├── paper_wasserstein.md
│       │       └── paper_wasserstein.expected.json
│       ├── test_fetcher_ssrn.py                   [NEW]
│       └── test_etl_ssrn.py                       [NEW]

~/Library/LaunchAgents/
└── com.wintermute.harvest-ssrn.plist              [NEW]

~/.wintermute/scripts/jobs/
└── harvest_ssrn.sh                                [NEW]

docs/superpowers/notes/
└── ssrn-soak-window.md                            [NEW operational note + value gate]
```

**Modified:**

- `harvester/harvester/config/sources.yaml` — append `ssrn:` entry.
- `~/.wintermute/scripts/search_papers.py` — at cutover (Task 7), remove the SSRN block. After this commit the script's only remaining work is bookkeeping (the arxiv + zenodo + ssrn paths are all gone).

**Schema dependencies (existing, no changes):** `harvest.run_log`, `harvest.document_metadata`, `harvest.triage_results`. No external schema changes beyond migration 011.

---

## Tasks

### Task 1: Branch + Migration 011 (harvest.ssrn_records)

**Files:**
- Create: `harvester/harvester/schemas/011_ssrn_records.sql`

- [ ] **Step 1: Branch from main**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git checkout main
git pull --ff-only
git checkout -b feat/ssrn-migration
```

Expected: on `feat/ssrn-migration`, working tree clean (modulo the typical `data/manifests/raw_manifest.parquet` ambient modification).

- [ ] **Step 2: Write migration 011**

Create `harvester/harvester/schemas/011_ssrn_records.sql`:

```sql
-- Migration 011: ssrn_records — densely-typed analytical table for the SSRN
-- source. Two-stage Crawl4ai flow (search → paper page) lands one row per
-- paper page.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.ssrn_records (
    id                  BIGSERIAL PRIMARY KEY,
    ssrn_id             BIGINT NOT NULL UNIQUE,            -- abstract_id from URL
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    doi                 TEXT,
    publication_date    DATE,
    jel_codes           TEXT[] NOT NULL DEFAULT '{}',      -- Journal of Economic Literature codes
    institution         TEXT,
    ssrn_url            TEXT NOT NULL,
    byte_size           INTEGER NOT NULL,                  -- markdown char count
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ssrn_records_published_idx
    ON harvest.ssrn_records (publication_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ssrn_records_jel_gin_idx
    ON harvest.ssrn_records USING GIN (jel_codes);
CREATE INDEX IF NOT EXISTS ssrn_records_doi_idx
    ON harvest.ssrn_records (doi) WHERE doi IS NOT NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('011_ssrn_records.sql', 'PLACEHOLDER_SHA', 'ssrn_records analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 3: Apply migration**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python -c "
from harvester.db import get_connection
from pathlib import Path
sql = Path('harvester/schemas/011_ssrn_records.sql').read_text()
conn = get_connection()
with conn.cursor() as cur:
    cur.execute(sql)
conn.commit()
conn.close()
print('migration 011 applied')
"
```

Expected: `migration 011 applied`.

- [ ] **Step 4: Verify the table**

```bash
psql wintermute -c "\d harvest.ssrn_records"
```

Expected: 13 columns total (`id, ssrn_id, title, abstract, authors, doi, publication_date, jel_codes, institution, ssrn_url, byte_size, raw_hash, created_by_run_id, created_at`), 3 named indexes + pkey + UNIQUE on `ssrn_id`, FK to `harvest.run_log(id)`.

- [ ] **Step 5: Commit**

```bash
git add harvester/harvester/schemas/011_ssrn_records.sql
git commit -m "$(cat <<'EOF'
feat(harvester): migration 011 — ssrn_records analytical table

Dense per-paper columns mirroring arxiv_papers + zenodo_records:
ssrn_id (UNIQUE — the SSRN abstract_id from the URL), title, abstract,
authors (JSONB), doi (often external), publication_date, jel_codes
(TEXT[] — SSRN's Journal of Economic Literature classification),
institution, ssrn_url, byte_size, raw_hash, created_by_run_id.

GIN index on jel_codes (topic discovery), partial index on doi
(cross-source linkage), DESC NULLS LAST on publication_date.

Schema feeds the upcoming SsrnETL via the two-stage Crawl4ai path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: SsrnFetcher (Crawl4aiFetcher with two-stage flow) + tests

**Files:**
- Create: `harvester/harvester/fetchers/ssrn.py`
- Create: `harvester/tests/test_fetcher_ssrn.py`
- Create: `harvester/tests/fixtures/ssrn/search_page_sde.md`

- [ ] **Step 1: Create the fixtures directory + a synthetic search-page fixture**

```bash
mkdir -p /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/ssrn
```

Create `harvester/tests/fixtures/ssrn/search_page_sde.md`:

```markdown
# SSRN Search Results: "stochastic differential equations"

## Most Recent Results

### Stochastic Differential Equations in Finance: A Survey
*Posted: 2026-04-15 | Pages: 42*
[Read Full Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1234567)

### Information Geometry of Diffusion Processes
*Posted: 2026-03-22 | Pages: 28*
[Read Full Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345678)

### Wasserstein Distance and Robust Portfolio Optimization
*Posted: 2026-02-10 | Pages: 35*
[Read Full Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3456789)
```

This is a hand-authored fixture — real SSRN output may differ, but the regex extraction only needs the `abstract_id=NNNNNNN` pattern to be present.

- [ ] **Step 2: Write failing fetcher tests at `harvester/tests/test_fetcher_ssrn.py`**

```python
"""Tests for harvester.fetchers.ssrn.SsrnFetcher.

SsrnFetcher overrides iter_payloads for a two-stage Crawl4ai flow:
  Stage 1: crawl the SSRN search page for a keyword
  Stage 2: regex-extract abstract_id URLs from the search markdown
  Stage 3: crawl each paper page

Tests mock crawl4ai entirely via the same _build_crawler hook used by
test_fetcher_url_drain.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from harvester.fetchers.ssrn import SsrnFetcher


_FXT = Path(__file__).parent / "fixtures" / "ssrn"


def test_ssrn_fetcher_source_id():
    f = SsrnFetcher.__new__(SsrnFetcher)
    assert f.source_id == "ssrn"


def test_ssrn_fetcher_search_url_includes_keyword():
    f = SsrnFetcher.__new__(SsrnFetcher)
    url = f._search_url({"keyword": "stochastic differential equations"})
    assert "papers.ssrn.com/sol3/results.cfm" in url
    assert "stochastic%20differential%20equations" in url or "stochastic+differential+equations" in url


def test_ssrn_fetcher_search_url_empty_keyword_returns_empty():
    f = SsrnFetcher.__new__(SsrnFetcher)
    assert f._search_url({}) == ""
    assert f._search_url({"keyword": ""}) == ""


def test_ssrn_fetcher_parse_paper_urls_extracts_abstract_ids():
    f = SsrnFetcher.__new__(SsrnFetcher)
    markdown = (_FXT / "search_page_sde.md").read_text()
    urls = f._parse_paper_urls(markdown, max_results=5)
    assert len(urls) == 3
    assert all("papers.cfm?abstract_id=" in u for u in urls)
    assert "1234567" in urls[0]


def test_ssrn_fetcher_parse_paper_urls_respects_max_results():
    f = SsrnFetcher.__new__(SsrnFetcher)
    markdown = (_FXT / "search_page_sde.md").read_text()
    urls = f._parse_paper_urls(markdown, max_results=2)
    assert len(urls) == 2


def test_ssrn_fetcher_parse_paper_urls_dedupes_repeats():
    """SSRN search pages sometimes link the same paper twice (title + 'read more')."""
    f = SsrnFetcher.__new__(SsrnFetcher)
    md = "[a](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=999)\n[b](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=999)"
    urls = f._parse_paper_urls(md, max_results=10)
    assert len(urls) == 1


def _mock_crawl_result(markdown_text: str) -> MagicMock:
    result = MagicMock()
    result.success = True
    result.markdown.fit_markdown = markdown_text
    result.markdown.raw_markdown = markdown_text
    result.metadata = {}
    result.error_message = None
    return result


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_ssrn_iter_payloads_two_stage_flow(mock_build_crawler, tmp_path):
    """End-to-end mock: search-page crawl → parse → paper crawl. Verifies
    iter_payloads yields one RawPayload per parsed paper URL."""
    from harvester.manifest import RawArchive

    search_md = (_FXT / "search_page_sde.md").read_text()
    paper_md_template = "# Paper Title {n}\n\nAbstract text here."

    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)

    async def fake_arun(url, config=None):
        if "results.cfm" in url:
            return _mock_crawl_result(search_md)
        # paper page
        return _mock_crawl_result(paper_md_template.format(n=url.rsplit("=", 1)[-1]))

    crawler.arun = AsyncMock(side_effect=fake_arun)
    mock_build_crawler.return_value = crawler

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    f = SsrnFetcher(archive=archive)
    f.crawl_config = lambda: None  # type: ignore[assignment]

    payloads = list(f.iter_payloads({"keyword": "stochastic differential equations", "per_page": 5}))
    assert len(payloads) == 3
    for p in payloads:
        assert p.source_id == "ssrn"
        assert p.content_type == "text/markdown"
        assert "papers.cfm?abstract_id=" in p.source_url


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_ssrn_iter_payloads_handles_empty_search_results(mock_build_crawler, tmp_path):
    """Search page with no abstract_id links → fetcher yields no payloads."""
    from harvester.manifest import RawArchive

    crawler = MagicMock()
    crawler.__aenter__ = AsyncMock(return_value=crawler)
    crawler.__aexit__ = AsyncMock(return_value=None)
    crawler.arun = AsyncMock(return_value=_mock_crawl_result("# No results"))
    mock_build_crawler.return_value = crawler

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    f = SsrnFetcher(archive=archive)
    f.crawl_config = lambda: None  # type: ignore[assignment]

    payloads = list(f.iter_payloads({"keyword": "no-results"}))
    assert payloads == []


@patch("harvester.fetchers.crawl4ai_base._build_crawler")
def test_ssrn_iter_payloads_empty_keyword_yields_nothing(mock_build_crawler, tmp_path):
    """No keyword → no search → no crawler invocation at all."""
    from harvester.manifest import RawArchive

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    f = SsrnFetcher(archive=archive)

    payloads = list(f.iter_payloads({}))
    assert payloads == []
    mock_build_crawler.assert_not_called()
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_ssrn.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.fetchers.ssrn'`.

- [ ] **Step 4: Implement `harvester/harvester/fetchers/ssrn.py`**

```python
"""SSRN fetcher.

Two-stage Crawl4ai flow because SSRN's search page returns a list of papers
that must be parsed before individual paper pages can be fetched:

  Stage 1: crawl https://papers.ssrn.com/sol3/results.cfm?...  for a keyword
  Stage 2: regex out /sol3/papers.cfm?abstract_id=NNNNNNN URLs from the
           rendered markdown
  Stage 3: crawl each paper page

The base Crawl4aiFetcher only supports a single static URL list (via
urls_to_crawl). We override iter_payloads entirely to drive the two-stage
flow. Conservative pacing (0.2 req/sec) because SSRN aggressively blocks
headless browsers.

Replaces the SSRN block of ~/.wintermute/scripts/search_papers.py.
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from typing import Any, Iterable

from harvester.fetchers.crawl4ai_base import Crawl4aiFetcher
from harvester.types import RateLimit, RawPayload


_SEARCH_URL_TEMPLATE = (
    "https://papers.ssrn.com/sol3/results.cfm"
    "?txtbox_Keywords={query}"
    "&subjectId=&jrnlid=&absid=&cls=&stype=1&evtid=&Network=&crit=&orderby=0"
    "&crtest=&recid=&txtbox_Title=&txtbox_Author=&pn=0"
)

_PAPER_URL_RE = re.compile(
    r"https?://papers\.ssrn\.com/sol3/papers\.cfm\?abstract_id=(\d+)"
)


class SsrnFetcher(Crawl4aiFetcher):
    source_id = "ssrn"

    def rate_limit_spec(self) -> RateLimit:
        # SSRN aggressively rate-limits and blocks headless browsers (403,
        # captcha redirects). Pace at 0.2 req/sec (1 req per 5 sec) with
        # long backoffs.
        return RateLimit(
            requests_per_second=0.2,
            max_retries=3,
            backoff_seconds=[10, 30, 120],
        )

    def crawl_config(self) -> Any:
        # Override to lengthen page_timeout — SSRN's CFM-rendered pages are
        # slow. wait_until="networkidle" ensures dynamic content has settled.
        from crawl4ai import CrawlerRunConfig
        return CrawlerRunConfig(
            excluded_tags=["nav", "header", "footer", "aside", "script", "style"],
            exclude_external_links=True,
            verbose=False,
            page_timeout=60000,  # 60 sec
        )

    def urls_to_crawl(self, query: dict[str, Any]) -> Iterable[str]:
        """Unused — we override iter_payloads. Returns [] to satisfy the
        abstract method contract."""
        return []

    def _search_url(self, query: dict[str, Any]) -> str:
        keyword = (query.get("keyword") or "").strip()
        if not keyword:
            return ""
        return _SEARCH_URL_TEMPLATE.format(query=urllib.parse.quote(keyword))

    def _parse_paper_urls(self, search_markdown: str, *, max_results: int) -> list[str]:
        """Extract canonical paper URLs from a crawled search-results
        markdown. De-duplicates by abstract_id (the same paper can appear
        as both title-link and 'read more' link). Caps at max_results."""
        seen_ids: set[str] = set()
        urls: list[str] = []
        for abstract_id in _PAPER_URL_RE.findall(search_markdown):
            if abstract_id in seen_ids:
                continue
            seen_ids.add(abstract_id)
            urls.append(
                f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={abstract_id}"
            )
            if len(urls) >= max_results:
                break
        return urls

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        seen = seen or set()
        search_url = self._search_url(query)
        if not search_url:
            return  # nothing to do without a keyword

        # Stage 1: search page
        self._pace()
        results = asyncio.run(self._crawl_all([search_url]))
        if not results:
            return
        _, search_md = results[0]

        # Stage 2: parse paper URLs
        max_results = int(query.get("per_page", 10))
        paper_urls = [u for u in self._parse_paper_urls(search_md, max_results=max_results) if u not in seen]
        if not paper_urls:
            return

        # Stage 3: crawl each paper page
        for url, markdown in asyncio.run(self._crawl_all(paper_urls)):
            self._pace()
            yield self.archive.write(
                source_id=self.source_id,
                source_url=url,
                request_params={"keyword": query.get("keyword"), "search_url": search_url},
                content=markdown.encode("utf-8"),
                content_type="text/markdown",
            )
```

- [ ] **Step 5: Run fetcher tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_ssrn.py -v
```

Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add harvester/harvester/fetchers/ssrn.py \
    harvester/tests/fixtures/ssrn/search_page_sde.md \
    harvester/tests/test_fetcher_ssrn.py
git commit -m "$(cat <<'EOF'
feat(harvester): SsrnFetcher (Crawl4aiFetcher with two-stage flow)

SSRN's search page returns a paper list, not paper content. We override
iter_payloads (rather than just urls_to_crawl) to drive a two-stage flow:
crawl the search page, regex out abstract_id paper URLs, then crawl each
paper page. Reuses Crawl4aiFetcher._crawl_all for both stages.

Conservative pacing (0.2 req/sec, [10s, 30s, 120s] backoff) because SSRN
aggressively blocks headless browsers — known to issue 403s + captcha
redirects. page_timeout extended to 60s; SSRN's CFM rendering is slow.

Tests mock crawl4ai entirely via the _build_crawler hook (the same
pattern url_drain uses). 9 tests covering: source_id, search URL
construction, regex extraction (incl. dedup by abstract_id and
max_results cap), end-to-end mocked two-stage flow, empty-search
handling, empty-keyword short-circuit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: SsrnETL + 3 golden samples + ETL tests

**Files:**
- Create: `harvester/harvester/etl/ssrn.py`
- Create: 3 `paper_<variant>.md` + 3 `paper_<variant>.expected.json` fixtures under `harvester/tests/fixtures/ssrn/`
- Create: `harvester/tests/test_etl_ssrn.py`

- [ ] **Step 1: Hand-author 3 paper-page markdown fixtures**

These are synthetic — real SSRN markdown may differ. Verification against live shape happens at Task 5 smoke.

Create `harvester/tests/fixtures/ssrn/paper_sde_finance.md`:

```markdown
# Stochastic Differential Equations in Finance: A Survey

**Authors:** Jane Researcher (Wharton School), John Coauthor (MIT Sloan)

**Posted:** 2026-04-15

**Abstract**

We survey applications of stochastic differential equations to financial
modeling, covering Itô calculus, Black-Scholes, and recent extensions to
rough volatility models.

**JEL Classification:** C58, G12, G13

**DOI:** 10.2139/ssrn.1234567

[Download PDF](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID1234567_code.pdf)
```

Create `harvester/tests/fixtures/ssrn/paper_info_geometry.md`:

```markdown
# Information Geometry of Diffusion Processes

**Authors:** Alice Smith (Stanford)

**Posted:** 2026-03-22

**Abstract**

This paper develops the information-geometric structure underlying
diffusion processes on Riemannian manifolds. We connect the
Fisher-Rao metric to score-based generative models.

**JEL Classification:** C14, C44

[Read Full Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345678)
```

Create `harvester/tests/fixtures/ssrn/paper_wasserstein.md`:

```markdown
# Wasserstein Distance and Robust Portfolio Optimization

**Authors:** Bob Jones, Carol Lee

**Posted:** 2026-02-10

**Abstract**

We apply Wasserstein distributionally robust optimization to mean-variance
portfolio selection.

**JEL Classification:**

[Read Full Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3456789)
```

(Note: the wasserstein paper intentionally has empty JEL Classification + no DOI line to exercise the nullable paths.)

- [ ] **Step 2: Write failing ETL tests at `harvester/tests/test_etl_ssrn.py`**

```python
"""Tests for harvester.etl.ssrn.SsrnETL.

The ETL parses crawled paper-page markdown (heuristic regex against
labeled sections like '**Authors:**', '**Abstract**', '**JEL Classification:**').
Real SSRN output may differ slightly across paper templates; the smoke
step verifies live extraction quality.
"""

import json
from datetime import datetime, timezone, date as _date
from pathlib import Path

import pytest

from harvester.etl.ssrn import SsrnETL
from harvester.types import RawPayload


_FXT = Path(__file__).parent / "fixtures" / "ssrn"
_VARIANTS = ["sde_finance", "info_geometry", "wasserstein"]

_FETCHED_AT = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


def _raw_payload_for(name: str, abstract_id: str, tmp_path: Path) -> RawPayload:
    src = _FXT / f"paper_{name}.md"
    dst = tmp_path / src.name
    dst.write_text(src.read_text())
    return RawPayload(
        file_path=dst,
        source_id="ssrn",
        source_url=f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={abstract_id}",
        raw_hash="sha256:test",
        request_params={"keyword": "test"},
        content_type="text/markdown",
        fetched_at=_FETCHED_AT,
    )


@pytest.mark.parametrize("variant,abstract_id", [
    ("sde_finance", "1234567"),
    ("info_geometry", "2345678"),
    ("wasserstein", "3456789"),
])
def test_ssrn_etl_golden_sample(variant, abstract_id, tmp_path):
    etl = SsrnETL()
    raw = _raw_payload_for(variant, abstract_id, tmp_path)
    parsed = etl.parse(raw)

    expected_path = _FXT / f"paper_{variant}.expected.json"
    expected = json.loads(expected_path.read_text())

    assert parsed.title == expected["title"]
    assert parsed.source_url == expected["source_url"]
    if expected["published_date"] is None:
        assert parsed.published_date is None
    else:
        assert parsed.published_date.isoformat() == expected["published_date"]

    assert len(parsed.rows) == len(expected["rows"])
    for actual_row, expected_row in zip(parsed.rows, expected["rows"]):
        assert actual_row.target_table == expected_row["target_table"]
        for key, exp_val in expected_row["data"].items():
            act_val = actual_row.data.get(key)
            if isinstance(act_val, _date):
                act_val = act_val.isoformat()
            if isinstance(exp_val, str) and exp_val.startswith(("[", "{")):
                assert json.loads(act_val) == json.loads(exp_val), (
                    f"{variant}.{actual_row.target_table}.{key}"
                )
            else:
                assert act_val == exp_val, (
                    f"{variant}.{actual_row.target_table}.{key}: "
                    f"got {act_val!r}, expected {exp_val!r}"
                )


def test_ssrn_etl_source_id_and_schema_version():
    etl = SsrnETL()
    assert etl.source_id == "ssrn"
    assert etl.expected_schema_version == 11


def test_ssrn_etl_extracts_abstract_id_from_url(tmp_path):
    """SSRN ID is sourced from the URL, not the body — the canonical
    identifier always matches the source_url's abstract_id param."""
    etl = SsrnETL()
    raw = _raw_payload_for("sde_finance", "9999999", tmp_path)
    parsed = etl.parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["ssrn_id"] == 9999999


def test_ssrn_etl_handles_missing_jel_codes(tmp_path):
    """The wasserstein fixture intentionally has an empty JEL Classification
    line — should parse as an empty list, not crash."""
    etl = SsrnETL()
    raw = _raw_payload_for("wasserstein", "3456789", tmp_path)
    parsed = etl.parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["jel_codes"] == []


def test_ssrn_etl_handles_missing_doi(tmp_path):
    """Wasserstein paper has no DOI line — doi should be None."""
    etl = SsrnETL()
    raw = _raw_payload_for("wasserstein", "3456789", tmp_path)
    parsed = etl.parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["doi"] is None


def test_ssrn_etl_falls_back_to_untitled_for_no_h1(tmp_path):
    p = tmp_path / "no_h1.md"
    p.write_text("Just body text, no heading.\n\n**Authors:** Someone\n")
    raw = RawPayload(
        file_path=p, source_id="ssrn",
        source_url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=99",
        raw_hash="sha256:test",
        request_params={},
        content_type="text/markdown",
        fetched_at=_FETCHED_AT,
    )
    parsed = SsrnETL().parse(raw)
    assert parsed.title == "Untitled"
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_ssrn.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.etl.ssrn'`.

- [ ] **Step 4: Implement `harvester/harvester/etl/ssrn.py`**

```python
"""SSRN ETL.

Parses one SSRN paper-page markdown (crawled by SsrnFetcher) into a
ParsedDoc with rows for harvest.document_metadata and harvest.ssrn_records.

SSRN doesn't expose a structured API for public scrapers; we parse the
crawl4ai-rendered markdown with heuristic regex against the typical
section labels ('**Authors:**', '**Abstract**', '**JEL Classification:**',
'**DOI:**', '**Posted:**'). Real-world SSRN templates vary; missing
fields degrade to None rather than crashing.

The canonical SSRN ID is extracted from the source_url's abstract_id
parameter, not the body — that's the authoritative identifier and is
always present on the URL.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any
from urllib.parse import urlparse, parse_qs

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


_AUTHORS_RE = re.compile(r"\*\*Authors?:\*\*\s*(.+?)(?:\n|$)", re.IGNORECASE)
_POSTED_RE = re.compile(r"\*\*Posted:\*\*\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_DOI_RE = re.compile(r"\*\*DOI:\*\*\s*(10\.\S+)", re.IGNORECASE)
_JEL_RE = re.compile(r"\*\*JEL Classification:\*\*\s*([^\n]*)", re.IGNORECASE)
_INSTITUTION_RE = re.compile(r"\(([^)]+(?:School|University|Institute|College)[^)]*)\)")
_AUTHOR_NAME_RE = re.compile(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)")


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or "Untitled"
    return "Untitled"


def _extract_abstract(markdown: str) -> str | None:
    """Pulls the paragraph after '**Abstract**' (case-insensitive). Returns
    None if no abstract section found."""
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("**abstract**"):
            # Skip blank lines after the header, collect until next bold-section header.
            body_lines: list[str] = []
            for follow in lines[i + 1:]:
                stripped = follow.strip()
                if stripped.startswith("**") and stripped.endswith(":**"):
                    break
                if stripped:
                    body_lines.append(stripped)
                elif body_lines:
                    # Allow a single blank line within the abstract.
                    body_lines.append("")
            text = " ".join(s for s in body_lines if s).strip()
            return text or None
    return None


def _extract_authors(markdown: str) -> list[dict[str, str]]:
    """Returns a list of {name, affiliation?} dicts."""
    m = _AUTHORS_RE.search(markdown)
    if not m:
        return []
    raw = m.group(1).strip()
    out: list[dict[str, str]] = []
    # Split on comma between author entries; each entry may have a
    # parenthesized institution.
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name_match = _AUTHOR_NAME_RE.search(chunk)
        if not name_match:
            continue
        entry: dict[str, str] = {"name": name_match.group(1)}
        inst_match = _INSTITUTION_RE.search(chunk)
        if inst_match:
            entry["affiliation"] = inst_match.group(1).strip()
        out.append(entry)
    return out


def _extract_date(markdown: str) -> date | None:
    m = _POSTED_RE.search(markdown)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _extract_doi(markdown: str) -> str | None:
    m = _DOI_RE.search(markdown)
    return m.group(1).strip() if m else None


def _extract_jel_codes(markdown: str) -> list[str]:
    m = _JEL_RE.search(markdown)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    # JEL codes are 1-3 alphanumeric chars; split on commas / whitespace
    codes = re.findall(r"[A-Z]\d{1,3}", raw)
    return codes


def _extract_institution(markdown: str) -> str | None:
    """First institution found in the Authors line, used as the primary
    affiliation for the dense row's institution column."""
    m = _AUTHORS_RE.search(markdown)
    if not m:
        return None
    inst_match = _INSTITUTION_RE.search(m.group(1))
    return inst_match.group(1).strip() if inst_match else None


def _abstract_id_from_url(url: str) -> int:
    """Extract abstract_id from a canonical SSRN paper URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    try:
        return int(params.get("abstract_id", ["0"])[0])
    except (ValueError, TypeError):
        return 0


class SsrnETL(ETL):
    source_id = "ssrn"
    expected_schema_version = 11

    def parse(self, raw: RawPayload) -> ParsedDoc:
        markdown = raw.file_path.read_text()
        title = _extract_title(markdown)
        abstract = _extract_abstract(markdown)
        authors = _extract_authors(markdown)
        pub_date = _extract_date(markdown)
        doi = _extract_doi(markdown)
        jel_codes = _extract_jel_codes(markdown)
        institution = _extract_institution(markdown)
        ssrn_id = _abstract_id_from_url(raw.source_url)
        byte_size = len(markdown)

        dense_row = Row(
            target_table="harvest.ssrn_records",
            data={
                "ssrn_id": ssrn_id,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "doi": doi,
                "publication_date": pub_date,
                "jel_codes": jel_codes,
                "institution": institution,
                "ssrn_url": raw.source_url,
                "byte_size": byte_size,
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
                "source_url": raw.source_url,
                "published_date": pub_date,
                "document_type": "ssrn_paper",
                "payload": json.dumps(
                    {
                        "ssrn_id": ssrn_id,
                        "jel_codes": jel_codes,
                        "institution": institution,
                        "byte_size": byte_size,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=raw.source_url,
            published_date=pub_date,
            rows=[meta_row, dense_row],
            metadata={
                "ssrn_id": ssrn_id,
                "doi": doi,
                "jel_codes": jel_codes,
                "institution": institution,
            },
        )
```

- [ ] **Step 5: Generate the 3 expected fixtures by snapshotting the ETL output**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python3 - <<'PYEOF'
import json
from datetime import date, datetime, timezone
from pathlib import Path
from harvester.etl.ssrn import SsrnETL
from harvester.types import RawPayload

FETCHED_AT = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
fxt = Path("tests/fixtures/ssrn")

for v, aid in [("sde_finance", "1234567"), ("info_geometry", "2345678"), ("wasserstein", "3456789")]:
    src = fxt / f"paper_{v}.md"
    raw = RawPayload(
        file_path=src, source_id="ssrn",
        source_url=f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={aid}",
        raw_hash="sha256:test",
        request_params={"keyword": "test"},
        content_type="text/markdown",
        fetched_at=FETCHED_AT,
    )
    parsed = SsrnETL().parse(raw)
    out = {
        "title": parsed.title,
        "source_url": parsed.source_url,
        "published_date": parsed.published_date.isoformat() if parsed.published_date else None,
        "rows": [{"target_table": r.target_table, "data": {
            k: (v.isoformat() if isinstance(v, date) else v)
            for k, v in r.data.items()
        }} for r in parsed.rows],
    }
    (fxt / f"paper_{v}.expected.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"wrote paper_{v}.expected.json")
PYEOF
```

Expected: 3 `paper_*.expected.json` files. Open one (sde_finance) and verify: 2 rows, 1st is `harvest.document_metadata`, 2nd is `harvest.ssrn_records`, `authors` is a JSON-encoded list with at least one entry, `jel_codes` is `["C58", "G12", "G13"]`, `doi` is `"10.2139/ssrn.1234567"`.

- [ ] **Step 6: Run ETL tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_ssrn.py -v
```

Expected: 8 passed (3 parameterized + 5 standalone).

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -p no:randomly 2>&1 | tail -3
```

Expected: 197 baseline + 9 fetcher + 8 ETL = 214 passed.

- [ ] **Step 8: Commit**

```bash
git add harvester/harvester/etl/ssrn.py \
    harvester/tests/fixtures/ssrn/paper_*.md \
    harvester/tests/fixtures/ssrn/paper_*.expected.json \
    harvester/tests/test_etl_ssrn.py
git commit -m "$(cat <<'EOF'
feat(harvester): SsrnETL + 3 golden samples

Parses crawled SSRN paper-page markdown via heuristic regex against
labeled sections (Authors, Abstract, Posted, DOI, JEL Classification).
The canonical ssrn_id is sourced from source_url's abstract_id param —
the body's content varies by template but the URL is authoritative.

Golden samples (sde_finance, info_geometry, wasserstein) span typical
SSRN paper shapes. The wasserstein fixture intentionally lacks JEL
codes and DOI to exercise the nullable paths.

Real SSRN HTML may diverge from the synthetic fixtures; live smoke at
Task 5 will surface any extraction gaps for refinement.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: sources.yaml entry + dry-run

**Files:**
- Modify: `harvester/harvester/config/sources.yaml`

- [ ] **Step 1: Append the `ssrn:` entry**

Append to the end of `harvester/harvester/config/sources.yaml`:

```yaml
ssrn:
  fetcher: harvester.fetchers.ssrn.SsrnFetcher
  etl: harvester.etl.ssrn.SsrnETL
  rolling_window_days: 30
  inbox_backpressure_max: 5000
  daily_cost_ceiling_usd: 1.00
  expected_schema_version: 11
  triage_enabled: true
  citation_chain_enabled: true
  triage_threshold: 0.4
  triage_model: "claude-sonnet-4-6"
  scout_base_url: "https://papers.ssrn.com"
  per_page: 10              # papers per search term per night
  max_pages: 1              # no pagination yet (search page 0 only)
  tier_1_terms:
    - "stochastic differential equations finance"
    - "information geometry econometrics"
    - "Wasserstein distance portfolio optimization"
    - "rough volatility models"
    - "score-based generative model finance"
    - "uncertainty quantification economics"
    - "Fokker-Planck financial mathematics"
    - "neural SDE option pricing"
  tier_2_terms: []
```

Rationale for the choices:
- **`rolling_window_days: 30`** — recent SSRN posts; not deep-archive search.
- **`daily_cost_ceiling_usd: 1.00`** — soft cap; SSRN itself is free but triage costs apply.
- **`per_page: 10`** + `max_pages: 1` → up to 10 papers per term per night = 80 papers/night ceiling across 8 terms.
- **8 tier_1 terms** all in the stochastic-dynamics / information-geometry overlap — the narrow SSRN slice that matches Wintermute's research axes. **No martial arts, canine, or mental-training terms** — SSRN won't have them.
- **`citation_chain_enabled: true`** — many SSRN papers have external DOIs that flow into the existing expansion machinery.

- [ ] **Step 2: Dry-run**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run ssrn --tier=tier_1 --dry-run
```

Expected: `DRY RUN: source=ssrn, terms=[...8 terms...], window=YYYY-MM-DD..YYYY-MM-DD, limit=0`.

- [ ] **Step 3: Commit**

```bash
git add harvester/harvester/config/sources.yaml
git commit -m "$(cat <<'EOF'
feat(harvester): register ssrn source in sources.yaml

8 tier_1 terms in the narrow SSRN-vs-Wintermute-axes overlap (stochastic
dynamics, information geometry, Wasserstein optimization, rough volatility,
score-based generative models in finance/economics). Skips terms that
SSRN doesn't cover (martial arts, canine cognition, mental training).

per_page=10 + max_pages=1 → 10 papers/term * 8 terms = 80 papers/night
ceiling. daily_cost_ceiling_usd=1.00 (SSRN itself is free, ceiling is for
triage on deposits).

Live smoke against the real SSRN site happens in Task 5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Live smoke against real SSRN

**Files:** None modified. Operational checkpoint that exercises real crawl4ai + SSRN.

**Critical: SSRN may block headless browsers.** This is the highest-risk step of the migration. Possible outcomes:
- Smoke succeeds → proceed to Task 6.
- Smoke succeeds but extracts garbage (titles/abstracts are wrong) → iterate on `SsrnETL` regex.
- Smoke fails with 403 / captcha → SSRN is blocking. Document and stop; the source may not be viable.

- [ ] **Step 1: Single-term smoke with low limit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run ssrn --query "stochastic differential equations finance" --limit 3
```

Expected wall-clock: 30-90 seconds (slow pacing + 60s page timeout). Result: `run_id=NNNN status=completed fetched=N deposited=M failed=0` where N is between 1 and 3.

Verify:

```bash
psql wintermute -c "
SELECT id, source_id, status, items_fetched, items_deposited, items_failed
FROM harvest.run_log WHERE source_id='ssrn' ORDER BY id DESC LIMIT 3
"
psql wintermute -c "
SELECT ssrn_id, title, jsonb_array_length(authors) AS n_authors,
       array_length(jel_codes, 1) AS n_jel, doi IS NOT NULL AS has_doi,
       byte_size
FROM harvest.ssrn_records ORDER BY id DESC LIMIT 5
"
```

Expected: at least one `status='completed'` run; rows in `harvest.ssrn_records` with non-null `ssrn_id`, `title`, and `byte_size > 500`. JEL codes + DOI may be null on individual papers (they're sparse fields).

- [ ] **Step 2: Failure handling**

**(A) `status='failed'` with 403/captcha in the run_log error column.** SSRN is blocking. Document in the soak-window note (Task 6) and skip Task 6/7 — the source is non-viable. Don't try to engineer around the block; that's a separate spike, not Task 5's scope. Report status BLOCKED.

**(B) `deposited=0` with `fetched>0`.** Items came back from the search but failed the ETL parse (likely no title, no abstract). Open one raw payload from the archive to see what crawl4ai actually returned:

```bash
ls -la /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/data/raw/ssrn/ | tail -5
cat /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/data/raw/ssrn/*/<latest>.txt | head -80
```

Adjust the ETL regex / extractors in `harvester/harvester/etl/ssrn.py`, add a regression test based on the real shape, re-run smoke.

**(C) Extraction succeeded but titles/authors look wrong.** Same diagnostic — capture real shape, refine ETL, add regression test, re-smoke. Cap fixup iterations at 3.

- [ ] **Step 3: If smoke needed ETL fixes, commit**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add harvester/harvester/etl/ssrn.py harvester/tests/test_etl_ssrn.py
git commit -m "$(cat <<'EOF'
fix(harvester): SsrnETL extraction fixes from live smoke

[Describe what real-SSRN shape differed from the synthetic fixtures,
e.g., authors section uses a different label, abstract is wrapped in a
specific div crawl4ai converts as a markdown blockquote, etc.]

Captured the real shape as a new regression-test fixture.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If no ETL fix was needed, skip this commit.

- [ ] **Step 4: Confirm triage scored**

```bash
psql wintermute -c "
SELECT count(*) AS scored, avg(score)::numeric(4,2) AS avg_score
FROM harvest.triage_results
WHERE doc_id IN (
    SELECT id FROM harvest.document_metadata
    WHERE source_id='ssrn' AND created_at > now() - interval '15 minutes'
)
"
```

Expected: `scored > 0`. **If avg_score < 0.3, take note — that's the value-evaluation signal Task 6's soak-window note will use.**

- [ ] **Step 5: No commit if no code changes needed.**

---

### Task 6: Launchd + soak-window note with value gate

**Files:**
- Create: `~/.wintermute/scripts/jobs/harvest_ssrn.sh`
- Create: `~/Library/LaunchAgents/com.wintermute.harvest-ssrn.plist`
- Create: `docs/superpowers/notes/ssrn-soak-window.md`

**Pre-condition:** Task 5 smoke succeeded (i.e., not BLOCKED).

- [ ] **Step 1: Write the wrapper script**

Create `/Users/brock/.wintermute/scripts/jobs/harvest_ssrn.sh`:

```bash
#!/usr/bin/env bash
# Daily SSRN harvest at 22:30 local.

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

# Guard against intermittent venv-state drift where the harvester entrypoint
# script exists but the package itself is uninstalled, producing
# "ModuleNotFoundError: No module named 'harvester'". `uv run` does not detect
# this; `uv sync --inexact` re-registers the editable install without removing
# any extra packages (e.g. dev deps from local pytest runs).
"$UV_BIN" sync --inexact || exit 1

run_job harvest_ssrn -- \
    "$UV_BIN" run harvester run ssrn --tier=tier_1
```

```bash
chmod +x /Users/brock/.wintermute/scripts/jobs/harvest_ssrn.sh
```

- [ ] **Step 2: Write the plist**

Create `/Users/brock/Library/LaunchAgents/com.wintermute.harvest-ssrn.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wintermute.harvest-ssrn</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/brock/.wintermute/scripts/jobs/harvest_ssrn.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>22</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_ssrn.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_ssrn.launchd.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/brock/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Schedule: 22:30 (between pubmed 22:00 and arxiv 23:00). SSRN is slow per request; 8 terms × ~30s/term = ~4 min wall clock.

- [ ] **Step 3: Verify wrapper syntax**

```bash
bash -n /Users/brock/.wintermute/scripts/jobs/harvest_ssrn.sh
echo "syntax exit=$?"
```

Expected: `syntax exit=0`. Do NOT run the wrapper end-to-end here — Task 5 already proved real SSRN works for one term; running all 8 now adds little.

- [ ] **Step 4: Load the launchd agent**

```bash
launchctl load /Users/brock/Library/LaunchAgents/com.wintermute.harvest-ssrn.plist
launchctl list | grep harvest-ssrn
```

Expected: one line `- 0 com.wintermute.harvest-ssrn`.

- [ ] **Step 5: Write the soak-window + value-gate note**

Create `docs/superpowers/notes/ssrn-soak-window.md` via Python heredoc:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
uv run python3 - <<'PYEOF'
from pathlib import Path
import datetime

started = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

content = f"""# SSRN Migration — 3-Day Soak Window + Value Gate

**Started:** {started}

**Source:** `ssrn` via two-stage Crawl4ai (search page → paper pages).

**Cron:** `com.wintermute.harvest-ssrn` fires daily at 22:30 local; runs `harvester run ssrn --tier=tier_1` (8 terms, 10 papers each).

## Why this note has a value gate

SSRN's coverage (econ/finance/law) only marginally overlaps Wintermute's research axes. The tier_1 set targets the narrow overlap (stochastic dynamics in finance + information geometry + Wasserstein optimization), but the source may still underdeliver. **After the 3-day soak, evaluate whether to keep SSRN running or retire it.**

## Daily check (run each morning during the soak)

```bash
# 1. Did the nightly cron fire and complete?
tail -30 /Users/brock/.wintermute/logs/cron/harvest_ssrn.log

# 2. Run-log
psql wintermute -c "
SELECT id, source_id, status, items_fetched, items_deposited, items_failed, started_at
FROM harvest.run_log
WHERE source_id='ssrn' AND started_at > now() - interval '24 hours'
ORDER BY id DESC
"

# 3. Per-term deposit rate
psql wintermute -c "
SELECT (request_params->>'keyword') AS term,
       count(*) AS runs,
       sum(items_fetched) AS fetched,
       sum(items_deposited) AS deposited
FROM harvest.run_log
WHERE source_id='ssrn' AND started_at > now() - interval '24 hours'
GROUP BY term ORDER BY deposited DESC
"

# 4. Triage scoring — THIS IS THE KEY METRIC
psql wintermute -c "
SELECT count(*) AS scored, avg(score)::numeric(4,2) AS avg_score,
       count(*) FILTER (WHERE score >= 0.5) AS high_score_count
FROM harvest.triage_results
WHERE doc_id IN (
    SELECT id FROM harvest.document_metadata
    WHERE source_id='ssrn' AND created_at > now() - interval '24 hours'
)
"

# 5. Failure patterns
psql wintermute -c "
SELECT error_signature, occurrence_count, last_seen_at, mitigation_status
FROM harvest.failure_patterns
WHERE source_id='ssrn' AND last_seen_at > now() - interval '24 hours'
"
```

## Green criteria for keeping SSRN (all four for 3 consecutive days)

1. ≥1 status='completed' run per day with sum(items_deposited) > 0.
2. avg_score ≥ 0.3 across deposited papers (SSRN's value to Wintermute).
3. high_score_count (score ≥ 0.5) ≥ 5 per day on average — SSRN is generating actually-useful hits.
4. No failure_patterns row crosses occurrence_count >= 5 with mitigation_status='unaddressed'. Especially watch for `crawl4ai: 403` patterns — SSRN bot detection.

## Retire criteria — disable the source if ANY of these on day 3

1. avg_score < 0.2 (the corpus is noise).
2. high_score_count < 2 per day (almost nothing useful).
3. Failure pattern crawl4ai: 403 OR crawl4ai: captcha at occurrence_count >= 10 (SSRN is actively blocking).

**Retirement steps:** `launchctl unload /Users/brock/Library/LaunchAgents/com.wintermute.harvest-ssrn.plist`. Remove `ssrn:` from `sources.yaml`. Optionally drop `harvest.ssrn_records` (leave it for historical query — disk is cheap). Update this note: "Retired YYYY-MM-DD: <reason>".

## Cutover note

The SSRN block of `~/.wintermute/scripts/search_papers.py` is sunset at Task 7 of the SSRN migration plan regardless of value-gate outcome — the legacy script is being retired across all sources.
"""

Path("docs/superpowers/notes/ssrn-soak-window.md").write_text(content)
print(f"wrote ssrn-soak-window.md (started={{started}})".format(started=started))
PYEOF
```

- [ ] **Step 6: Commit the note**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add docs/superpowers/notes/ssrn-soak-window.md
git commit -m "$(cat <<'EOF'
docs: ssrn migration soak-window + value-gate checkpoint

3-day operational note with both standard green criteria AND an
explicit retire-if-not-useful gate. SSRN's coverage only marginally
overlaps Wintermute's research axes; if the soak shows avg_score
below 0.3, fewer than 2 high-score hits/day, or persistent
bot-detection blocks, the source should be retired via launchctl
unload + removal from sources.yaml.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Sunset SSRN block of search_papers.py

**Files:**
- Modify: `~/.wintermute/scripts/search_papers.py`

**Pre-condition:** Task 5 smoke succeeded (sources.yaml + cron is live). This cutover happens regardless of the value-gate outcome — the legacy script is being retired across all sources. If SSRN later fails the value gate, both the new harvester source AND the legacy script's SSRN code stay retired.

- [ ] **Step 1: Confirm callers**

```bash
grep -rn "search_zenodo\|search_arxiv\|search_ssrn" /Users/brock/.wintermute/scripts/
```

After the zenodo cutover, the script should only have an SSRN function (`search_ssrn`) remaining. If the SSRN block is also gone, the cutover already happened — skip to Step 4.

- [ ] **Step 2: Edit `~/.wintermute/scripts/search_papers.py`**

Remove the `# Zenodo` and `# SSRN` sections, the `SSRN_API`/`ZENODO_API` constants, and any `search_ssrn(...)` / `search_zenodo(...)` calls in `main()`. After this edit, the script should be effectively empty of source-search logic — at most a stub that prints a deprecation notice.

If the entire script becomes a single deprecation message, move it to `_sunset/`:

```bash
mkdir -p /Users/brock/.wintermute/scripts/_sunset
mv /Users/brock/.wintermute/scripts/search_papers.py /Users/brock/.wintermute/scripts/_sunset/2026-05-13-search_papers.py
```

If there are still meaningful non-source bits (unlikely), leave the file but with the SSRN code removed.

- [ ] **Step 3: Confirm no broken callers**

```bash
grep -rn "search_papers.py" /Users/brock/.wintermute/scripts/ ~/Library/LaunchAgents/com.wintermute.*.plist 2>/dev/null
```

Expected: no hits, or only hits in `_sunset/`. If a launchd plist is still firing the script, disable it:

```bash
# Example: if com.wintermute.search-papers.plist exists and still loads:
launchctl unload /Users/brock/Library/LaunchAgents/com.wintermute.search-papers.plist
mv /Users/brock/Library/LaunchAgents/com.wintermute.search-papers.plist \
   /Users/brock/Library/LaunchAgents/_sunset.com.wintermute.search-papers.plist
```

- [ ] **Step 4: Commit the cutover record**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
# No in-repo files changed (everything happens under ~/.wintermute). But
# document the cutover for posterity.
cat >> docs/superpowers/notes/ssrn-soak-window.md <<'EOF'

## Cutover record

**Date:** $(date -u +%Y-%m-%d)

`~/.wintermute/scripts/search_papers.py` SSRN block removed. The legacy
script is fully retired (all three of arxiv/zenodo/ssrn now live in
harvester). The file (or its remnant) sits under `_sunset/` for history.
EOF

git add docs/superpowers/notes/ssrn-soak-window.md
git commit -m "$(cat <<'EOF'
docs: ssrn cutover — legacy search_papers.py fully retired

The SSRN block was the last remaining source-search in
~/.wintermute/scripts/search_papers.py; arxiv was retired in Phase 2,
zenodo at the zenodo-migration cutover, and SSRN now. Script moved to
~/.wintermute/scripts/_sunset/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Final verification

**No code changes.**

- [ ] **Step 1: Full suite green**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest -p no:randomly 2>&1 | tail -3
```

Expected: 214 passed (197 baseline + 9 fetcher + 8 ETL = 214; or higher if Task 5 smoke added a regression-test fixture).

- [ ] **Step 2: CLI surface**

```bash
uv run harvester run ssrn --tier=tier_1 --dry-run | head -1
```

Expected: dry-run line with 8 terms.

- [ ] **Step 3: Live data**

```bash
psql wintermute -c "SELECT count(*) FROM harvest.ssrn_records"
psql wintermute -c "SELECT count(*) FROM harvest.document_metadata WHERE source_id='ssrn'"
psql wintermute -c "SELECT count(*) FROM harvest.run_log WHERE source_id='ssrn' AND status='completed'"
psql wintermute -c "SELECT count(*) FROM harvest.triage_results WHERE doc_id IN (SELECT id FROM harvest.document_metadata WHERE source_id='ssrn')"
```

Expected: four positive counts (at least the Task 5 smoke deposits).

- [ ] **Step 4: Launchd loaded**

```bash
launchctl list | grep harvest-ssrn
```

Expected: one line showing the agent loaded.

- [ ] **Step 5: Branch state**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git log main..HEAD --oneline
git status
```

Expected: 5–7 commits ahead of main depending on whether Task 5 added a fix commit + whether Task 7 made the optional cutover commit. Working tree clean.

- [ ] **Step 6: Hand off to `superpowers:finishing-a-development-branch`.**

---

## Self-Review

**1. Spec coverage**

| Requirement | Task |
|---|---|
| SsrnFetcher (Crawl4ai two-stage flow) | Task 2 |
| SsrnETL with golden samples | Task 3 |
| Migration 011: harvest.ssrn_records | Task 1 |
| sources.yaml registration | Task 4 |
| Live smoke against real SSRN with refinement loop | Task 5 |
| Launchd nightly job (22:30) | Task 6 |
| 3-day soak window with VALUE GATE | Task 6 |
| Cutover (sunset SSRN block of search_papers.py) | Task 7 |
| Final verification | Task 8 |

All scope items covered. The value-gate criterion is the structural difference from zenodo/pubmed — it's the operational acknowledgment that SSRN's research-axes alignment is marginal.

**2. Placeholder scan** — none. Every step has a complete code block, exact command, or specific file edit. The "[Describe what real-SSRN shape differed...]" placeholder in Task 5 Step 3's commit message template is intentional — it's filled in only if a fix commit is actually made.

**3. Type consistency**

- `harvest.ssrn_records` schema (Task 1) — column names match the keys SsrnETL writes (Task 3): `ssrn_id`, `title`, `abstract`, `authors`, `doi`, `publication_date`, `jel_codes`, `institution`, `ssrn_url`, `byte_size`, `raw_hash`.
- `SsrnFetcher.source_id == "ssrn"` (Task 2), `SsrnETL.source_id == "ssrn"` (Task 3), sources.yaml key `ssrn:` (Task 4) — match.
- `expected_schema_version = 11` (Task 3) matches migration filename `011_ssrn_records.sql` (Task 1) and sources.yaml `expected_schema_version: 11` (Task 4).
- Canonical paper URL pattern `https://papers.ssrn.com/sol3/papers.cfm?abstract_id={id}` consistent across fetcher (item_to_payload_kwargs path), ETL (ssrn_id extraction), and tests.
- The dense_row contains `byte_size` matching the schema column; meta_row.payload also includes byte_size for diagnostics.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-13-ssrn-migration.md`. Per the operator's standing preference, execution goes to `superpowers:subagent-driven-development` without a mode-selection prompt.
