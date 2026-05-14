# PubMed via MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PubMed as a first-class harvester source using the `McpFetcher` pattern. Proves the MCP-tool-call transport against a real connector (`mcp__claude_ai_PubMed__search_articles`), brings biomedical literature into the pipeline, and feeds Wintermute's KG via the existing extraction pipeline.

**Architecture:** `PubMedFetcher` inherits `McpFetcher` — the base class shells out to `claude -p <prompt> --output-format json` per query, where the prompt instructs Claude to call the named MCP tool. `PubMedETL` parses one PubMed record into a generic `harvest.document_metadata` row plus a dense `harvest.pubmed_papers` row mirroring the shape of `harvest.arxiv_papers` and `harvest.zenodo_records`. Migration 010 adds the analytical table. Triage + citation-chain both enabled — papers with DOIs flow into `harvest.expansion_candidates` like other sources.

**Tech Stack:** Python 3.12, psycopg, typer, uv, `claude` CLI (already on PATH and used by daemon). No new Python dependencies. **No new MCP SDK required** — the McpFetcher base already implements subprocess-to-claude-CLI transport.

**Spec source:** Roadmap §3.4 in `docs/superpowers/notes/phase3-roadmap.md`. This plan mirrors `docs/superpowers/plans/2026-05-13-zenodo-migration.md` and `docs/superpowers/plans/2026-05-13-url-drain-migration.md` structurally, adapted to the McpFetcher path and the new-source-no-cutover model.

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch:** `feat/pubmed-mcp` (from `main`; main is at the url-drain merge commit `670d930` plus the cleanup commit `3216114`).

**Verification model:** PubMed is a brand-new source with no legacy to cut over. Verification = a **3-day soak**: daily runs must succeed (`status='completed'`, `fetched>0`, `deposited>0`), triage produces scores, no new failure_patterns alerted. Plus a **smoke step that costs real claude-CLI calls** to exercise the MCP transport end-to-end before scheduling nightly.

**Cost note:** Each MCP call is a `claude -p` subprocess (uses Brock's Claude Max account). One subprocess per tier term per nightly run. The plan caps tier_1 at ~10 terms initially — that's 10 calls/night ≈ small. Triage adds another ~N calls per deposited doc. `daily_cost_ceiling_usd: 2.00` in sources.yaml as a soft alert (the Runner respects ceilings only in some paths; this is documentation as much as enforcement).

---

## File Structure

**Created:**

```
measuring-ai-economy/
├── harvester/
│   ├── harvester/
│   │   ├── fetchers/
│   │   │   └── pubmed.py                          [NEW]
│   │   ├── etl/
│   │   │   └── pubmed.py                          [NEW]
│   │   └── schemas/
│   │       └── 010_pubmed_papers.sql              [NEW]
│   └── tests/
│       ├── fixtures/
│       │   └── pubmed/                            [NEW dir]
│       │       ├── search_response_canine.json
│       │       ├── paper_canine_cognition.input.json
│       │       ├── paper_canine_cognition.expected.json
│       │       ├── paper_bjj_injury.input.json
│       │       ├── paper_bjj_injury.expected.json
│       │       ├── paper_exercise_phys.input.json
│       │       ├── paper_exercise_phys.expected.json
│       │       ├── paper_flow_state.input.json
│       │       └── paper_flow_state.expected.json
│       ├── test_fetcher_pubmed.py                 [NEW]
│       └── test_etl_pubmed.py                     [NEW]

~/Library/LaunchAgents/
└── com.wintermute.harvest-pubmed.plist            [NEW]

~/.wintermute/scripts/jobs/
└── harvest_pubmed.sh                              [NEW]

docs/superpowers/notes/
└── pubmed-soak-window.md                          [NEW operational note]
```

**Modified:**

- `harvester/harvester/config/sources.yaml` — append a `pubmed:` entry.

**Schema dependencies (existing, no changes):** `harvest.run_log`, `harvest.document_metadata`, `harvest.triage_results`, `harvest.expansion_candidates`. All populated by Runner; no migration needed beyond 010.

---

## Tasks

### Task 1: Branch + Migration 010 (harvest.pubmed_papers)

**Files:**
- Create: `harvester/harvester/schemas/010_pubmed_papers.sql`

- [ ] **Step 1: Branch from main**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git checkout main
git pull --ff-only
git checkout -b feat/pubmed-mcp
```

Expected: on `feat/pubmed-mcp`, working tree clean.

- [ ] **Step 2: Write migration 010**

Create `harvester/harvester/schemas/010_pubmed_papers.sql`:

```sql
-- Migration 010: pubmed_papers — densely-typed analytical table for the
-- PubMed source. Backed by the PubMed MCP server (mcp__claude_ai_PubMed_*).

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.pubmed_papers (
    id                  BIGSERIAL PRIMARY KEY,
    pmid                TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    journal             TEXT,
    publication_date    DATE,
    doi                 TEXT,
    pmcid               TEXT,
    mesh_terms          TEXT[] NOT NULL DEFAULT '{}',
    pmc_full_text_url   TEXT,
    pubmed_url          TEXT NOT NULL,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS pubmed_papers_published_idx
    ON harvest.pubmed_papers (publication_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS pubmed_papers_mesh_gin_idx
    ON harvest.pubmed_papers USING GIN (mesh_terms);
CREATE INDEX IF NOT EXISTS pubmed_papers_doi_idx
    ON harvest.pubmed_papers (doi) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS pubmed_papers_pmcid_idx
    ON harvest.pubmed_papers (pmcid) WHERE pmcid IS NOT NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('010_pubmed_papers.sql', 'PLACEHOLDER_SHA', 'pubmed_papers analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 3: Apply migration**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python -c "
from harvester.db import get_connection
from pathlib import Path
sql = Path('harvester/schemas/010_pubmed_papers.sql').read_text()
conn = get_connection()
with conn.cursor() as cur:
    cur.execute(sql)
conn.commit()
conn.close()
print('migration 010 applied')
"
```

Expected: `migration 010 applied`.

- [ ] **Step 4: Verify the table**

```bash
psql wintermute -c "\d harvest.pubmed_papers"
```

Expected: 14 columns (`id, pmid, title, abstract, authors, journal, publication_date, doi, pmcid, mesh_terms, pmc_full_text_url, pubmed_url, raw_hash, created_by_run_id, created_at`), 4 named indexes + pkey + UNIQUE on `pmid`, FK to `harvest.run_log(id)`.

- [ ] **Step 5: Commit**

```bash
git add harvester/harvester/schemas/010_pubmed_papers.sql
git commit -m "$(cat <<'EOF'
feat(harvester): migration 010 — pubmed_papers analytical table

Mirrors arxiv_papers and zenodo_records: dense per-document columns
(pmid UNIQUE, title, abstract, authors JSONB, journal, publication_date,
doi, pmcid, mesh_terms TEXT[], pmc_full_text_url, pubmed_url, raw_hash).
GIN index on mesh_terms (for MeSH-based filtering), partial indexes on
doi and pmcid (sparse but useful for cross-source linkage).

Schema feeds the upcoming PubMedETL via the McpFetcher path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: PubMedFetcher (McpFetcher subclass) + tests

**Files:**
- Create: `harvester/harvester/fetchers/pubmed.py`
- Create: `harvester/tests/test_fetcher_pubmed.py`
- Create: `harvester/tests/fixtures/pubmed/search_response_canine.json` (one captured-shape fixture)

- [ ] **Step 1: Author a synthetic MCP search-response fixture**

We can't easily capture a real PubMed MCP response without first triggering it through claude CLI (chicken-and-egg). Instead, hand-author one that matches the documented schema of `mcp__claude_ai_PubMed__search_articles`. This is the search-results envelope the fetcher will receive after Claude unwrapping; the actual production response shape will be verified during Task 5 smoke and the fixture/code can be tweaked then if needed.

Create `harvester/tests/fixtures/pubmed/search_response_canine.json`:

```json
{
  "results": [
    {
      "pmid": "37001234",
      "title": "Operant conditioning paradigms in domestic dogs: a systematic review",
      "abstract": "We review 84 studies of operant conditioning protocols applied to canine learning, with emphasis on working dogs and behavioral plasticity. Results suggest a robust effect of variable-ratio reinforcement on retention.",
      "authors": [
        {"name": "Smith, J", "affiliation": "Tufts Cummings School"},
        {"name": "Johnson, M", "affiliation": "University of Lincoln"}
      ],
      "journal": "Journal of Comparative Psychology",
      "publication_date": "2026-03-15",
      "doi": "10.1037/com0000999",
      "pmcid": "PMC10000001",
      "mesh_terms": ["Conditioning, Operant", "Dogs", "Learning", "Behavior, Animal"],
      "url": "https://pubmed.ncbi.nlm.nih.gov/37001234/"
    },
    {
      "pmid": "37001235",
      "title": "Canine cognition: episodic-like memory revisited",
      "abstract": "We replicate Fugazza et al. with a larger sample (n=42) and find consistent evidence for episodic-like memory in dogs across breeds.",
      "authors": [
        {"name": "Garcia, R", "affiliation": "Eotvos Lorand University"}
      ],
      "journal": "Animal Cognition",
      "publication_date": "2026-02-20",
      "doi": "10.1007/s10071-026-0123-4",
      "pmcid": null,
      "mesh_terms": ["Memory, Episodic", "Dogs", "Cognition"],
      "url": "https://pubmed.ncbi.nlm.nih.gov/37001235/"
    }
  ]
}
```

- [ ] **Step 2: Write failing fetcher tests at `harvester/tests/test_fetcher_pubmed.py`**

```python
"""Tests for harvester.fetchers.pubmed.PubMedFetcher.

PubMedFetcher is an McpFetcher subclass: query in, JSON tool-response out
via `claude -p` subprocess. Tests mock subprocess.run entirely so no real
Claude calls happen at test time.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harvester.fetchers.pubmed import PubMedFetcher


_FIXTURE = Path(__file__).parent / "fixtures" / "pubmed" / "search_response_canine.json"


def test_pubmed_fetcher_source_id_is_pubmed():
    f = PubMedFetcher.__new__(PubMedFetcher)
    assert f.source_id == "pubmed"


def test_pubmed_fetcher_mcp_tool_is_search_articles():
    f = PubMedFetcher.__new__(PubMedFetcher)
    assert f.mcp_tool == "mcp__claude_ai_PubMed__search_articles"


def test_pubmed_fetcher_args_for_query_maps_keyword_to_query():
    f = PubMedFetcher.__new__(PubMedFetcher)
    args = f.args_for_query({"keyword": "canine cognition", "per_page": 5})
    assert args["query"] == "canine cognition"
    assert args["max_results"] == 5


def test_pubmed_fetcher_args_for_query_defaults_max_results():
    f = PubMedFetcher.__new__(PubMedFetcher)
    args = f.args_for_query({"keyword": "BJJ injury"})
    assert args["query"] == "BJJ injury"
    assert args["max_results"] == 10


def test_pubmed_fetcher_items_from_response_extracts_results_list():
    f = PubMedFetcher.__new__(PubMedFetcher)
    response = json.loads(_FIXTURE.read_text())
    items = list(f.items_from_response(response))
    assert len(items) == 2
    assert items[0]["pmid"] == "37001234"
    assert items[0]["url"].startswith("https://pubmed.ncbi.nlm.nih.gov/")


def test_pubmed_fetcher_items_from_response_handles_empty():
    f = PubMedFetcher.__new__(PubMedFetcher)
    items = list(f.items_from_response({"results": []}))
    assert items == []


def test_pubmed_fetcher_items_from_response_unwraps_claude_result_field(tmp_path):
    """If subprocess returns claude's --output-format json shape (with a 'result'
    field that itself contains the tool JSON as a string), unwrap before iterating."""
    f = PubMedFetcher.__new__(PubMedFetcher)
    # Claude's CLI may return: {"type": "result", "result": "<tool's json as string>", ...}
    inner = json.dumps({"results": [{"pmid": "1", "title": "x", "url": "https://pubmed.ncbi.nlm.nih.gov/1/"}]})
    wrapped = {"type": "result", "result": inner, "session_id": "abc"}
    items = list(f.items_from_response(wrapped))
    assert len(items) == 1
    assert items[0]["pmid"] == "1"


@patch("harvester.fetchers.mcp_base.subprocess.run")
def test_pubmed_iter_payloads_yields_one_payload_per_result(mock_run, tmp_path):
    """End-to-end mock: subprocess returns search response, fetcher yields
    one RawPayload per result, content_type='application/json'."""
    from harvester.manifest import RawArchive

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=_FIXTURE.read_text(),
        stderr="",
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    f = PubMedFetcher(archive=archive)
    payloads = list(f.iter_payloads({"keyword": "canine cognition"}))

    assert len(payloads) == 2
    for p in payloads:
        assert p.content_type == "application/json"
        assert p.source_id == "pubmed"
        assert p.source_url.startswith("https://pubmed.ncbi.nlm.nih.gov/")
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_pubmed.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.fetchers.pubmed'`.

- [ ] **Step 4: Implement `harvester/harvester/fetchers/pubmed.py`**

```python
"""PubMed fetcher.

Backed by the PubMed MCP server (mcp__claude_ai_PubMed__search_articles).
Calls the MCP tool via the McpFetcher base, which shells out to `claude -p`
and parses the JSON response. Each query term produces one MCP call →
one search response → up to `max_results` items.

The MCP response shape may be either the tool's raw JSON envelope
({"results": [...]}) or Claude's --output-format json wrapping
({"type": "result", "result": "<json string>", ...}). items_from_response
handles both.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from harvester.fetchers.mcp_base import McpFetcher
from harvester.types import RateLimit


class PubMedFetcher(McpFetcher):
    source_id = "pubmed"
    mcp_tool = "mcp__claude_ai_PubMed__search_articles"

    def rate_limit_spec(self) -> RateLimit:
        # MCP calls go through `claude -p` subprocess. Each call is heavy
        # (Claude inference + tool dispatch) — pace conservatively.
        return RateLimit(
            requests_per_second=0.5,  # 1 call per 2 seconds
            max_retries=2,
            backoff_seconds=[5, 30],
        )

    def args_for_query(self, query: dict[str, Any]) -> dict[str, Any]:
        return {
            "query": query.get("keyword", ""),
            "max_results": int(query.get("per_page", 10)),
        }

    def items_from_response(self, response: dict[str, Any]) -> Iterable[dict[str, Any]]:
        # Unwrap Claude's --output-format json envelope if present. The
        # `result` field is a string containing the tool's actual JSON.
        body = response
        if isinstance(response, dict) and isinstance(response.get("result"), str):
            try:
                body = json.loads(response["result"])
            except json.JSONDecodeError:
                # Result was free-form text, not JSON. Nothing to extract.
                return []

        if not isinstance(body, dict):
            return []
        return body.get("results", [])
```

- [ ] **Step 5: Run fetcher tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_pubmed.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add harvester/harvester/fetchers/pubmed.py \
    harvester/tests/fixtures/pubmed/search_response_canine.json \
    harvester/tests/test_fetcher_pubmed.py
git commit -m "$(cat <<'EOF'
feat(harvester): PubMedFetcher (McpFetcher subclass)

Calls mcp__claude_ai_PubMed__search_articles via the McpFetcher base
class, which shells out to `claude -p`. args_for_query maps the
runner's {keyword, per_page} query into the MCP tool's {query, max_results}
arg shape. items_from_response handles both the raw tool envelope
({"results": [...]}) and Claude's --output-format json wrapping
({"type": "result", "result": "<json string>", ...}).

Pacing at 0.5 req/sec (each call is a `claude -p` subprocess, so
slower than HTTP). 2 retries with [5s, 30s] backoff.

Captured a synthetic search-response fixture (2 canine-cognition results)
for testing. Real-shape verification happens at Task 5 live smoke.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: PubMedETL + 4 golden samples + ETL tests

**Files:**
- Create: `harvester/harvester/etl/pubmed.py`
- Create: 4 `paper_<variant>.input.json` + 4 `paper_<variant>.expected.json` fixtures under `harvester/tests/fixtures/pubmed/`
- Create: `harvester/tests/test_etl_pubmed.py`

- [ ] **Step 1: Hand-author 4 single-record input fixtures**

These 4 fixtures span the research-axes coverage we expect from PubMed: canine cognition, BJJ injury (martial-arts), exercise physiology, flow state (mental-training).

Create `harvester/tests/fixtures/pubmed/paper_canine_cognition.input.json`:

```json
{
  "pmid": "37001234",
  "title": "Operant conditioning paradigms in domestic dogs: a systematic review",
  "abstract": "We review 84 studies of operant conditioning protocols applied to canine learning, with emphasis on working dogs and behavioral plasticity.",
  "authors": [
    {"name": "Smith, J", "affiliation": "Tufts Cummings School"},
    {"name": "Johnson, M", "affiliation": "University of Lincoln"}
  ],
  "journal": "Journal of Comparative Psychology",
  "publication_date": "2026-03-15",
  "doi": "10.1037/com0000999",
  "pmcid": "PMC10000001",
  "mesh_terms": ["Conditioning, Operant", "Dogs", "Learning", "Behavior, Animal"],
  "url": "https://pubmed.ncbi.nlm.nih.gov/37001234/"
}
```

Create `harvester/tests/fixtures/pubmed/paper_bjj_injury.input.json`:

```json
{
  "pmid": "37005678",
  "title": "Shoulder injury patterns in Brazilian jiu-jitsu: a 5-year retrospective",
  "abstract": "We retrospectively analyzed 412 shoulder injuries from competitive BJJ athletes. Submission-related injuries account for 38% of cases, with the kimura position the leading vector.",
  "authors": [
    {"name": "Rodrigues, P", "affiliation": "São Paulo Sports Medicine Institute"}
  ],
  "journal": "American Journal of Sports Medicine",
  "publication_date": "2026-01-12",
  "doi": "10.1177/03635465261234567",
  "pmcid": null,
  "mesh_terms": ["Martial Arts", "Shoulder Injuries", "Athletic Injuries"],
  "url": "https://pubmed.ncbi.nlm.nih.gov/37005678/"
}
```

Create `harvester/tests/fixtures/pubmed/paper_exercise_phys.input.json`:

```json
{
  "pmid": "37009999",
  "title": "Hypertrophy responses to high-load vs low-load resistance training: meta-analysis",
  "abstract": "We pooled 67 studies (n=2,341) comparing >70% 1RM vs <50% 1RM protocols with matched volume. Hypertrophy effects converge when volume is equated; strength gains favor high-load.",
  "authors": [
    {"name": "Schoenfeld, B", "affiliation": "Lehman College CUNY"},
    {"name": "Grgic, J"}
  ],
  "journal": "Sports Medicine",
  "publication_date": "2026-04-01",
  "doi": "10.1007/s40279-026-01999-9",
  "pmcid": "PMC11111111",
  "mesh_terms": ["Resistance Training", "Hypertrophy", "Muscle Strength"],
  "url": "https://pubmed.ncbi.nlm.nih.gov/37009999/"
}
```

Create `harvester/tests/fixtures/pubmed/paper_flow_state.input.json`:

```json
{
  "pmid": "37011111",
  "title": "Neural correlates of flow state in elite athletes during high-pressure performance",
  "abstract": "fMRI during a high-pressure perceptual-motor task revealed reduced default mode network activity and elevated dorsolateral prefrontal engagement in flow-state reports.",
  "authors": [
    {"name": "Anderson, K"},
    {"name": "Tan, L"}
  ],
  "journal": "Journal of Sport and Exercise Psychology",
  "publication_date": "2026-02-28",
  "doi": null,
  "pmcid": null,
  "mesh_terms": ["Athletic Performance", "Flow State", "Magnetic Resonance Imaging"],
  "url": "https://pubmed.ncbi.nlm.nih.gov/37011111/"
}
```

- [ ] **Step 2: Write failing ETL tests at `harvester/tests/test_etl_pubmed.py`**

```python
"""Tests for harvester.etl.pubmed.PubMedETL.

Golden-sample comparison: each input fixture is parsed and compared
field-by-field against the expected fixture (raw_hash mocked).
"""

import json
from datetime import datetime, timezone, date as _date
from pathlib import Path

import pytest

from harvester.etl.pubmed import PubMedETL
from harvester.types import RawPayload


_FXT = Path(__file__).parent / "fixtures" / "pubmed"
_VARIANTS = ["canine_cognition", "bjj_injury", "exercise_phys", "flow_state"]

_FETCHED_AT = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


def _raw_payload_for(name: str, tmp_path: Path) -> RawPayload:
    src = _FXT / f"paper_{name}.input.json"
    dst = tmp_path / src.name
    dst.write_text(src.read_text())
    data = json.loads(src.read_text())
    return RawPayload(
        file_path=dst,
        source_id="pubmed",
        source_url=data["url"],
        raw_hash="sha256:test",
        request_params={"mcp_tool": "mcp__claude_ai_PubMed__search_articles"},
        content_type="application/json",
        fetched_at=_FETCHED_AT,
    )


@pytest.mark.parametrize("variant", _VARIANTS)
def test_pubmed_etl_golden_sample(variant, tmp_path):
    etl = PubMedETL()
    raw = _raw_payload_for(variant, tmp_path)
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
            # Normalize date objects to ISO strings for comparison
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


def test_pubmed_etl_source_id_and_schema_version():
    etl = PubMedETL()
    assert etl.source_id == "pubmed"
    assert etl.expected_schema_version == 10


def test_pubmed_etl_handles_missing_doi_pmcid(tmp_path):
    """A paper without doi or pmcid should still parse — these fields are
    nullable in the schema."""
    src = _FXT / "paper_flow_state.input.json"  # this one has doi=null, pmcid=null
    data = json.loads(src.read_text())
    p = tmp_path / "no_ids.json"
    p.write_text(json.dumps(data))

    raw = RawPayload(
        file_path=p, source_id="pubmed",
        source_url=data["url"],
        raw_hash="sha256:test",
        request_params={},
        content_type="application/json",
        fetched_at=_FETCHED_AT,
    )
    parsed = PubMedETL().parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["doi"] is None
    assert dense_row.data["pmcid"] is None
    assert dense_row.data["pmc_full_text_url"] is None


def test_pubmed_etl_builds_pmc_full_text_url_when_pmcid_present(tmp_path):
    """If pmcid is set, pmc_full_text_url should be derivable."""
    src = _FXT / "paper_canine_cognition.input.json"  # this one has pmcid=PMC10000001
    data = json.loads(src.read_text())
    p = tmp_path / "with_pmcid.json"
    p.write_text(json.dumps(data))

    raw = RawPayload(
        file_path=p, source_id="pubmed",
        source_url=data["url"],
        raw_hash="sha256:test",
        request_params={},
        content_type="application/json",
        fetched_at=_FETCHED_AT,
    )
    parsed = PubMedETL().parse(raw)
    dense_row = parsed.rows[1]
    assert dense_row.data["pmcid"] == "PMC10000001"
    assert dense_row.data["pmc_full_text_url"] == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10000001/"
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_pubmed.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.etl.pubmed'`.

- [ ] **Step 4: Implement `harvester/harvester/etl/pubmed.py`**

```python
"""PubMed ETL.

Pure parse: takes one PubMed MCP record (as JSON bytes from the archive)
and produces a ParsedDoc with rows for harvest.document_metadata and
harvest.pubmed_papers.

PMID is the canonical identifier. If a PMCID is present, the PMC
full-text URL is derived (https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/).
DOI and PMCID may both be absent; both columns are nullable.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _authors(record: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for a in record.get("authors") or []:
        if isinstance(a, dict) and a.get("name"):
            entry: dict[str, str] = {"name": a["name"]}
            if a.get("affiliation"):
                entry["affiliation"] = a["affiliation"]
            out.append(entry)
    return out


def _mesh_terms(record: dict[str, Any]) -> list[str]:
    terms = record.get("mesh_terms") or []
    return [t for t in terms if isinstance(t, str)]


def _pmc_full_text_url(pmcid: str | None) -> str | None:
    if not pmcid:
        return None
    return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"


class PubMedETL(ETL):
    source_id = "pubmed"
    expected_schema_version = 10

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())
        pmid = str(record["pmid"])
        title = (record.get("title") or "")[:5000]
        abstract = record.get("abstract")
        authors = _authors(record)
        journal = record.get("journal")
        pub_date = _date_or_none(record.get("publication_date"))
        doi = record.get("doi")
        pmcid = record.get("pmcid")
        mesh_terms = _mesh_terms(record)
        pubmed_url = record.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        pmc_url = _pmc_full_text_url(pmcid)

        dense_row = Row(
            target_table="harvest.pubmed_papers",
            data={
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "journal": journal,
                "publication_date": pub_date,
                "doi": doi,
                "pmcid": pmcid,
                "mesh_terms": mesh_terms,
                "pmc_full_text_url": pmc_url,
                "pubmed_url": pubmed_url,
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
                "source_url": pubmed_url,
                "published_date": pub_date,
                "document_type": "pubmed_paper",
                "payload": json.dumps(
                    {
                        "pmid": pmid,
                        "journal": journal,
                        "pmcid": pmcid,
                        "mesh_terms": mesh_terms,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=pubmed_url,
            published_date=pub_date,
            rows=[meta_row, dense_row],
            metadata={
                "pmid": pmid,
                "doi": doi,
                "pmcid": pmcid,
                "mesh_terms": mesh_terms,
                "journal": journal,
            },
        )
```

- [ ] **Step 5: Generate the 4 expected fixtures by running the ETL and snapshotting**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python3 - <<'PYEOF'
import json
from datetime import date
from pathlib import Path
from harvester.etl.pubmed import PubMedETL
from harvester.types import RawPayload
from datetime import datetime, timezone

FETCHED_AT = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)

fxt = Path("tests/fixtures/pubmed")
for v in ["canine_cognition", "bjj_injury", "exercise_phys", "flow_state"]:
    src = fxt / f"paper_{v}.input.json"
    data = json.loads(src.read_text())
    raw = RawPayload(
        file_path=src,
        source_id="pubmed",
        source_url=data["url"],
        raw_hash="sha256:test",
        request_params={},
        content_type="application/json",
        fetched_at=FETCHED_AT,
    )
    parsed = PubMedETL().parse(raw)
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

Expected: 4 `paper_*.expected.json` files written. Open one and sanity-check: 2 rows, first is `harvest.document_metadata`, second is `harvest.pubmed_papers`, fields populated correctly (especially `pmc_full_text_url` derived from `pmcid` for canine_cognition + exercise_phys, null for bjj_injury + flow_state).

- [ ] **Step 6: Run ETL tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_pubmed.py -v
```

Expected: 7 passed (4 parameterized + 3 standalone).

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -p no:randomly 2>&1 | tail -3
```

Expected: 174 (post-url-drain baseline) + 8 fetcher + 7 ETL = 189 passed.

- [ ] **Step 8: Commit**

```bash
git add harvester/harvester/etl/pubmed.py \
    harvester/tests/fixtures/pubmed/paper_*.json \
    harvester/tests/test_etl_pubmed.py
git commit -m "$(cat <<'EOF'
feat(harvester): PubMedETL + 4 golden samples (canine/BJJ/exercise/flow)

Parses one PubMed MCP record into ParsedDoc with rows for
harvest.document_metadata and harvest.pubmed_papers. Extracts authors
with optional affiliations, mesh_terms array, journal, ISO publication
date. Derives pmc_full_text_url from pmcid when present.

Golden samples span the research axes that should generate hits from
PubMed: canine cognition (axis 2, Murray-aligned), BJJ injury
(axis 3 martial-arts adjacent), exercise physiology (axis 4 training
science), flow state neuroimaging (axis 5 mental training).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: sources.yaml entry + dry-run

**Files:**
- Modify: `harvester/harvester/config/sources.yaml`

- [ ] **Step 1: Append the `pubmed:` entry**

Append to the end of `harvester/harvester/config/sources.yaml`:

```yaml
pubmed:
  fetcher: harvester.fetchers.pubmed.PubMedFetcher
  etl: harvester.etl.pubmed.PubMedETL
  rolling_window_days: 30
  inbox_backpressure_max: 5000
  daily_cost_ceiling_usd: 2.00
  expected_schema_version: 10
  triage_enabled: true
  citation_chain_enabled: true
  triage_threshold: 0.4
  triage_model: "claude-sonnet-4-6"
  scout_base_url: "https://pubmed.ncbi.nlm.nih.gov"
  per_page: 10
  max_pages: 1
  tier_1_terms:
    - "canine cognition"
    - "dog behavior training"
    - "BJJ injury prevention"
    - "MMA biomechanics injury"
    - "strength training hypertrophy meta-analysis"
    - "exercise physiology performance"
    - "flow state athletes neural correlates"
    - "psychological resilience grit"
    - "working dog learning"
    - "operant conditioning canine"
  tier_2_terms: []
```

Notes on the choices:
- **`rolling_window_days: 30`** — PubMed has decades of literature, but we want recent + cumulative. The MCP tool itself doesn't filter on date; the field is informational unless the args_for_query is extended later.
- **`per_page: 10` + `max_pages: 1`** — each tier term = 1 MCP call = 10 candidate papers. Conservative for the cost model; can expand later.
- **10 tier_1_terms** — spans research axes 2 (canine), 3 (martial arts), 4 (exercise), 5 (mental training). Avoids overlap with arxiv's CS/ML focus.
- **`citation_chain_enabled: true`** — PubMed DOIs feed the existing CitationChain machinery (Semantic Scholar references). Free side benefit.

- [ ] **Step 2: Dry-run**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run pubmed --tier=tier_1 --dry-run
```

Expected: `DRY RUN: source=pubmed, terms=[...10 terms...], window=YYYY-MM-DD..YYYY-MM-DD, limit=0`. No exceptions.

- [ ] **Step 3: Commit**

```bash
git add harvester/harvester/config/sources.yaml
git commit -m "$(cat <<'EOF'
feat(harvester): register pubmed source in sources.yaml

10 tier_1 terms across Wintermute's research axes: canine cognition,
dog behavior, BJJ/MMA injury, strength + hypertrophy meta-analyses,
exercise physiology, flow state neuroscience, performance psychology,
working-dog learning.

per_page=10, max_pages=1 → 10 MCP calls/night nominally. Triage enabled,
citation-chain enabled (PubMed DOIs flow into the existing expansion
machinery via Semantic Scholar).

Smoke against live MCP transport happens in Task 5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: End-to-end smoke against the live PubMed MCP

**Files:** None modified. Operational checkpoint that exercises real `claude -p` calls + the PubMed MCP server.

**Cost reminder:** This step makes real LLM-mediated MCP calls against Brock's Claude Max account. Each `harvester run` invocation against a term = one `claude -p` subprocess. Triage scoring of each deposited paper = additional Claude calls. Cap with `--query` + small limits to keep cost contained during smoke.

- [ ] **Step 1: Single-term, low-limit smoke**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run pubmed --query "canine cognition" --limit 3
```

Expected (wall-clock 30–90s): one line like `run_id=NNNN status=completed fetched=3 deposited=3 failed=0`. The subprocess may take 30–60s for the first MCP-tool dispatch.

Verify:

```bash
psql wintermute -c "
SELECT id, source_id, status, items_fetched, items_deposited, items_failed
FROM harvest.run_log
WHERE source_id='pubmed' ORDER BY id DESC LIMIT 3
"
psql wintermute -c "
SELECT pmid, title, journal, publication_date, jsonb_array_length(authors) AS n_authors, array_length(mesh_terms, 1) AS n_mesh
FROM harvest.pubmed_papers ORDER BY id DESC LIMIT 5
"
```

Expected: at least one `status='completed'` run; rows in `harvest.pubmed_papers` with non-null `pmid`, `title`, `journal`, sensible MeSH term counts (`n_mesh` typically 3–10).

- [ ] **Step 2: If the smoke produced `status='failed'` or `deposited=0`**

Most likely causes, in order of probability:

1. **`items_from_response` shape mismatch.** Claude's actual return format under `--output-format json` may differ from the fixture/test assumptions. Run the raw subprocess once manually to see:
   ```bash
   claude -p 'Call the mcp__claude_ai_PubMed__search_articles tool with these arguments and return ONLY the tool"s raw JSON output, no commentary: {"query": "canine cognition", "max_results": 3}' --output-format json | head -100
   ```
   Inspect the structure. If `result` is a string of free-form text rather than JSON, the prompt may need tightening, OR `items_from_response` may need to extract from a different shape. Adjust the fetcher's `items_from_response`, add a regression test against the captured real response, re-run smoke.

2. **The PubMed MCP server isn't reachable from the harvester's claude CLI session.** The MCP connectors are tied to claude.ai, not the local `claude` CLI. Verify by running:
   ```bash
   claude -p 'List your available MCP tools' --output-format json | head -50
   ```
   If `mcp__claude_ai_PubMed__search_articles` is not in the list, the MCP server isn't connected for the CLI context. Resolution may require running claude CLI in a context that has the connector attached (e.g., from claude.ai integration). If this turns out to be a hard block, escalate — the plan's transport assumption is wrong.

3. **Subprocess timeout (120s).** Increase via `HARVESTER_CLAUDE_BIN=...` is the wrong knob; the timeout is hardcoded. If hitting it, bump it in `mcp_base.py` (out of scope for this plan unless persistent).

Document the resolution in `docs/superpowers/notes/pubmed-soak-window.md` once Task 6 creates that file.

- [ ] **Step 3: If smoke succeeded — broader smoke**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run pubmed --tier=tier_1 --limit 30
```

Cap with `--limit 30` so total deposit across all 10 terms stops at 30 papers. Expected wall-clock: 5–15 minutes.

Verify counts grow:

```bash
psql wintermute -c "SELECT count(*) FROM harvest.pubmed_papers"
psql wintermute -c "
SELECT (request_params->>'mcp_tool') AS tool, count(*) AS runs, sum(items_deposited) AS total
FROM harvest.run_log
WHERE source_id='pubmed' AND started_at > now() - interval '1 hour'
GROUP BY tool
"
```

Expected: `count(*)` increased by tens; `total` ≈ 30 (the limit cap).

- [ ] **Step 4: No commit for this task** — operational only.

---

### Task 6: Launchd wrapper + plist + soak-window note

**Files:**
- Create: `~/.wintermute/scripts/jobs/harvest_pubmed.sh`
- Create: `~/Library/LaunchAgents/com.wintermute.harvest-pubmed.plist`
- Create: `docs/superpowers/notes/pubmed-soak-window.md`

**Pre-condition:** Task 5 smoke succeeded.

- [ ] **Step 1: Write the wrapper script**

Create `/Users/brock/.wintermute/scripts/jobs/harvest_pubmed.sh`:

```bash
#!/usr/bin/env bash
# Daily PubMed harvest at 22:00 local.

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

run_job harvest_pubmed -- \
    "$UV_BIN" run harvester run pubmed --tier=tier_1
```

```bash
chmod +x /Users/brock/.wintermute/scripts/jobs/harvest_pubmed.sh
```

- [ ] **Step 2: Write the plist**

Create `/Users/brock/Library/LaunchAgents/com.wintermute.harvest-pubmed.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wintermute.harvest-pubmed</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/brock/.wintermute/scripts/jobs/harvest_pubmed.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>22</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_pubmed.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_pubmed.launchd.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/brock/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

**Schedule rationale:** 22:00 (10 PM) is off-peak. Existing sources: arxiv 23:00, zenodo 23:30. PubMed at 22:00 keeps the nightly window orderly.

- [ ] **Step 3: Run the wrapper directly to verify**

```bash
# Run via the wrapper rather than launchd, to catch wiring bugs early.
# Limit via env var to keep cost contained — the wrapper uses --tier=tier_1
# (no limit). To smoke without burning all 10 terms, temporarily run the
# underlying command manually:
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
"$UV_BIN" sync --inexact
uv run harvester run pubmed --query "operant conditioning canine" --limit 3
echo "exit=$?"
```

Expected: `exit=0`, run logs to `~/.wintermute/logs/cron/harvest_pubmed.log` (if you ran via the wrapper) or to stdout (if you ran the underlying CLI).

If running the wrapper directly is preferred (to test the full pipeline including log capture):

```bash
/Users/brock/.wintermute/scripts/jobs/harvest_pubmed.sh
echo "exit=$?"
tail -20 /Users/brock/.wintermute/logs/cron/harvest_pubmed.log
```

This will run all 10 tier_1 terms (~10–20 minutes wall clock + cost). Skip this and rely on Task 5's smoke + the direct CLI test above if cost-constrained.

- [ ] **Step 4: Load the launchd agent**

```bash
launchctl load /Users/brock/Library/LaunchAgents/com.wintermute.harvest-pubmed.plist
launchctl list | grep harvest-pubmed
```

Expected: one line `- 0 com.wintermute.harvest-pubmed` (no exit code yet).

- [ ] **Step 5: Write the soak-window note**

Create `docs/superpowers/notes/pubmed-soak-window.md`:

```markdown
# PubMed Migration — 3-Day Soak Window

**Started:** [fill in actual date+time when launchd was loaded — Task 6 Step 4]

**Source:** `pubmed` via `mcp__claude_ai_PubMed__search_articles` (Claude MCP transport).

**Cron:** `com.wintermute.harvest-pubmed` fires daily at 22:00 local; wraps `harvester run pubmed --tier=tier_1` (10 terms; 10 MCP calls/night).

**Cost model:** Each MCP call = 1 `claude -p` subprocess invocation. Triage adds 1 Claude call per deposited paper. Daily cost ceiling soft-capped at $2.00 in sources.yaml.

## Daily check (run each morning during the soak)

\`\`\`bash
# 1. Did the nightly cron fire and complete?
tail -30 /Users/brock/.wintermute/logs/cron/harvest_pubmed.log

# 2. Run-log: every run for the last 24h
psql wintermute -c "
SELECT id, source_id, status, items_fetched, items_deposited, items_failed, started_at
FROM harvest.run_log
WHERE source_id='pubmed' AND started_at > now() - interval '24 hours'
ORDER BY id DESC
"

# 3. Per-term deposit rate
psql wintermute -c "
SELECT (request_params->>'q') AS term,
       count(*) AS runs,
       sum(items_fetched) AS fetched,
       sum(items_deposited) AS deposited
FROM harvest.run_log
WHERE source_id='pubmed' AND started_at > now() - interval '24 hours'
GROUP BY term
ORDER BY deposited DESC
"

# 4. Triage scoring
psql wintermute -c "
SELECT count(*) AS scored, avg(score)::numeric(4,2) AS avg_score
FROM harvest.triage_results
WHERE doc_id IN (
    SELECT id FROM harvest.document_metadata
    WHERE source_id='pubmed' AND created_at > now() - interval '24 hours'
)
"

# 5. Failure patterns
psql wintermute -c "
SELECT error_signature, occurrence_count, last_seen_at, mitigation_status
FROM harvest.failure_patterns
WHERE source_id='pubmed' AND last_seen_at > now() - interval '24 hours'
"

# 6. Cost sanity (rough proxy: count of runs × $0.10 typical)
psql wintermute -c "
SELECT sum(items_fetched + items_deposited) AS claude_calls_approx
FROM harvest.run_log
WHERE source_id='pubmed' AND started_at > now() - interval '24 hours'
"
\`\`\`

## Green criteria (all three for 3 consecutive days)

1. ≥1 status='completed' run per day with sum(items_deposited) > 0.
2. ≥30% of deposited docs have a triage score recorded (PubMed papers should reliably trigger triage given title+abstract richness).
3. No failure_patterns row crosses occurrence_count >= 5 with mitigation_status='unaddressed'.
4. Daily cost proxy stays under $5 (red flag if approaching $10).

## Notes on edge cases

- **MCP response shape changes:** Claude's `--output-format json` envelope may differ over time. If `items_from_response` starts returning 0 items unexpectedly, capture the raw stdout and check shape (see Task 5 Step 2 diagnostic command).
- **PubMed MCP server availability:** The connector is hosted; outages on Anthropic's side surface as `status='failed'`. Auto-recovers when MCP comes back.
```

(Note: the inner triple-backticks are intentional. Use a Python heredoc to write the file cleanly — `\`\`\`bash` blocks must appear as literal text inside the outer markdown.)

- [ ] **Step 6: Commit the operational note**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git add docs/superpowers/notes/pubmed-soak-window.md
git commit -m "$(cat <<'EOF'
docs: pubmed migration soak-window checkpoint

3-day operational note. Differs from arxiv/zenodo because each call
hits the MCP transport (claude -p subprocess) rather than a public
REST API — daily cost proxy added to the green criteria. Schedule
22:00 local, 10 tier_1 terms covering canine/martial-arts/exercise/
mental-training axes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

(The wrapper script + plist live outside the repo and don't get a git commit. The note above is the in-repo record.)

---

### Task 7: Final verification

**No code changes.**

- [ ] **Step 1: Full suite green**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest -p no:randomly 2>&1 | tail -3
```

Expected: 189 passed.

- [ ] **Step 2: CLI surface**

```bash
uv run harvester run pubmed --tier=tier_1 --dry-run | head -3
```

Expected: dry-run line with 10 terms.

- [ ] **Step 3: Live data sanity**

```bash
psql wintermute -c "SELECT count(*) FROM harvest.pubmed_papers"
psql wintermute -c "SELECT count(*) FROM harvest.document_metadata WHERE source_id='pubmed'"
psql wintermute -c "SELECT count(*) FROM harvest.run_log WHERE source_id='pubmed' AND status='completed'"
psql wintermute -c "SELECT count(*) FROM harvest.triage_results WHERE doc_id IN (SELECT id FROM harvest.document_metadata WHERE source_id='pubmed')"
```

Expected: four positive counts (at least the smoke deposits + triage scores).

- [ ] **Step 4: Launchd loaded**

```bash
launchctl list | grep harvest-pubmed
```

Expected: one line showing the agent loaded.

- [ ] **Step 5: Branch state**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git log main..HEAD --oneline
git status
```

Expected: 5 commits ahead of main (migration + fetcher + ETL + sources.yaml + soak-window note). Working tree clean.

- [ ] **Step 6: Hand off**

No further code. Hand to `superpowers:finishing-a-development-branch` per the standing workflow.

---

## Self-Review

**1. Spec coverage**

| Requirement | Task |
|---|---|
| PubMedFetcher (McpFetcher subclass) | Task 2 |
| PubMedETL with golden samples spanning research axes | Task 3 |
| Migration 010: harvest.pubmed_papers analytical table | Task 1 |
| sources.yaml registration with tier_1_terms | Task 4 |
| Live smoke against real MCP transport | Task 5 |
| Launchd nightly job (22:00) | Task 6 |
| 3-day soak window with green criteria + cost proxy | Task 6 |
| Final verification | Task 7 |

Plus roadmap §3.4's "rubric_version may need bump" note — explicitly **deferred**: current research_axes covers canine + martial-arts + exercise + mental-training adequately for the chosen tier_1 terms. If post-launch monitoring reveals systematic low-scoring of relevant biomedical literature, bump the rubric in a follow-up (out of scope here).

**2. Placeholder scan** — none. Every step has explicit code, exact commands, expected output. The "fill in actual date+time" in the operational note is a runtime value the operator fills in; clearly marked.

**3. Type consistency**

- `harvest.pubmed_papers` schema (Task 1) columns match `PubMedETL` dense_row data keys (Task 3): `pmid, title, abstract, authors, journal, publication_date, doi, pmcid, mesh_terms, pmc_full_text_url, pubmed_url, raw_hash`.
- `PubMedFetcher.source_id == "pubmed"` (Task 2), `PubMedETL.source_id == "pubmed"` (Task 3), sources.yaml key `pubmed:` (Task 4) — consistent.
- `expected_schema_version = 10` (Task 3 ETL) matches migration filename `010_pubmed_papers.sql` (Task 1) and sources.yaml `expected_schema_version: 10` (Task 4).
- `PubMedFetcher.mcp_tool == "mcp__claude_ai_PubMed__search_articles"` (Task 2) — matches the connector tool name from session-start system context.
- Canonical URL pattern `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` consistent across fetcher (item_to_payload_kwargs in the MCP envelope) and ETL (`pubmed_url` derivation).
- PMC URL pattern `https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/` consistent in `_pmc_full_text_url` (Task 3) and the test assertion (Task 3 Step 2).

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-13-pubmed-via-mcp.md`. Per the operator's standing preference, execution goes to `superpowers:subagent-driven-development` without a mode-selection prompt.
