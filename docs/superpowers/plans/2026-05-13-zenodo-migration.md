# Zenodo Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Zenodo source from the legacy `~/.wintermute/scripts/search_papers.py` into the harvester architecture as a first-class `zenodo` source — JSON HTTP fetcher + ETL + analytical table + nightly launchd job — and sunset the zenodo path in the legacy script. Mirrors Phase 2 (arxiv) but simpler: triage and citation-chain infrastructure are already wired.

**Architecture:** `ZenodoFetcher` inherits `HttpApiFetcher` (Zenodo returns clean JSON, no XML parsing needed — simpler than ArxivFetcher). `ZenodoETL` parses each record into a generic `harvest.document_metadata` row plus a dense `harvest.zenodo_records` row mirroring the shape of `harvest.arxiv_papers`. Migration 008 adds the analytical table. The new source registers via `harvester/config/sources.yaml` and runs through the existing Runner. A new launchd plist + bash wrapper schedules it nightly at 23:30 local (offset from arxiv's 23:00 to avoid contention).

**Tech Stack:** Python 3.12, psycopg, httpx, typer, uv. No new dependencies. Reuses HttpApiFetcher, Runner, RawArchive, LlmTriage, CitationChain.

**Spec:** No standalone spec doc — this plan mirrors `docs/superpowers/plans/2026-05-12-harvester-phase2-arxiv.md` structurally; the design is "do what arxiv did, for zenodo, on the simpler HttpApiFetcher path."

**Working directory:** `/Users/brock/Documents/GitHub/measuring-ai-economy/`

**Branch:** `feat/zenodo-migration` (to be created from main; main is at the calibration-judgment merge commit `eac6713`).

**Verification model (differs from Phase 2):** The legacy zenodo path stages markdown to `~/.wintermute/staging/` and never wrote to `harvest.document_metadata`, so `harvester compare-sources` is not applicable. Verification is a **3-day soak test**: daily runs must succeed (`status='completed'`, `fetched>0`, `deposited>0`), triage produces scores, no new failure_patterns alerted. Cutover is gated on the soak passing, not on coverage overlap.

---

## File Structure

**Created:**

```
measuring-ai-economy/
├── harvester/
│   ├── harvester/
│   │   ├── fetchers/
│   │   │   └── zenodo.py                          [NEW]
│   │   ├── etl/
│   │   │   └── zenodo.py                          [NEW]
│   │   └── schemas/
│   │       └── 008_zenodo_records.sql             [NEW]
│   └── tests/
│       ├── fixtures/
│       │   └── zenodo/                            [NEW dir]
│       │       ├── api_page_1.json
│       │       ├── record_article.input.json
│       │       ├── record_article.expected.json
│       │       ├── record_preprint.input.json
│       │       ├── record_preprint.expected.json
│       │       ├── record_conference.input.json
│       │       ├── record_conference.expected.json
│       │       ├── record_dataset.input.json
│       │       └── record_dataset.expected.json
│       ├── test_fetcher_zenodo.py                 [NEW]
│       └── test_etl_zenodo.py                     [NEW]

~/Library/LaunchAgents/
└── com.wintermute.harvest-zenodo.plist            [NEW]

~/.wintermute/scripts/jobs/
└── harvest_zenodo.sh                              [NEW]

docs/superpowers/notes/
└── zenodo-parallel-window.md                      [NEW operational note]
```

**Modified:**

- `harvester/harvester/config/sources.yaml` — append a `zenodo:` entry.
- `~/.wintermute/scripts/search_papers.py` — at cutover, remove the Zenodo block (Task 7).

**Schema dependencies (existing, no changes):**

- `harvest.run_log`, `harvest.document_metadata`, `harvest.triage_results`, `harvest.failure_patterns`, `harvest.expansion_candidates` — all populated by the Runner harness; no migration needed.

---

## Tasks

### Task 1: Branch + Migration 008 (harvest.zenodo_records)

**Files:**
- Create: `harvester/harvester/schemas/008_zenodo_records.sql`

- [ ] **Step 1: Branch from main**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git checkout main
git pull --ff-only
git checkout -b feat/zenodo-migration
```

Expected: on `feat/zenodo-migration`, working tree clean.

- [ ] **Step 2: Write migration 008**

Create `harvester/harvester/schemas/008_zenodo_records.sql`:

```sql
-- Migration 008: zenodo_records — densely-typed analytical table.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.zenodo_records (
    id                  BIGSERIAL PRIMARY KEY,
    zenodo_id           BIGINT NOT NULL UNIQUE,
    doi                 TEXT,
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    resource_type       TEXT,
    resource_subtype    TEXT,
    keywords            TEXT[] NOT NULL DEFAULT '{}',
    publication_date    DATE,
    license             TEXT,
    zenodo_url          TEXT NOT NULL,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS zenodo_records_published_idx
    ON harvest.zenodo_records (publication_date DESC);
CREATE INDEX IF NOT EXISTS zenodo_records_resource_type_idx
    ON harvest.zenodo_records (resource_type, resource_subtype);
CREATE INDEX IF NOT EXISTS zenodo_records_keywords_gin_idx
    ON harvest.zenodo_records USING GIN (keywords);
CREATE INDEX IF NOT EXISTS zenodo_records_doi_idx
    ON harvest.zenodo_records (doi) WHERE doi IS NOT NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('008_zenodo_records.sql', 'PLACEHOLDER_SHA', 'zenodo_records analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
```

- [ ] **Step 3: Apply migration**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python -c "
from harvester.db import get_connection
from pathlib import Path
sql = Path('harvester/schemas/008_zenodo_records.sql').read_text()
conn = get_connection()
with conn.cursor() as cur:
    cur.execute(sql)
conn.commit()
conn.close()
print('migration 008 applied')
"
```

Expected: `migration 008 applied`.

- [ ] **Step 4: Verify the table exists with the expected shape**

```bash
psql wintermute -c "\d harvest.zenodo_records"
```

Expected: table prints with all columns and indexes from the migration.

- [ ] **Step 5: Commit**

```bash
git add harvester/harvester/schemas/008_zenodo_records.sql
git commit -m "$(cat <<'EOF'
feat(harvester): migration 008 — zenodo_records analytical table

Mirrors the shape of harvest.arxiv_papers: dense per-source columns
(zenodo_id, doi, resource_type/subtype, keywords TEXT[], license,
zenodo_url, raw_hash, created_by_run_id) with GIN index on keywords
and partial index on doi. Schema feeds the upcoming ZenodoETL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: ZenodoFetcher (HttpApiFetcher subclass) + fetcher tests

**Files:**
- Create: `harvester/harvester/fetchers/zenodo.py`
- Create: `harvester/tests/fixtures/zenodo/api_page_1.json` (captured fixture)
- Create: `harvester/tests/test_fetcher_zenodo.py`

- [ ] **Step 1: Capture a real Zenodo API page as a fixture**

```bash
mkdir -p /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/zenodo
curl -s 'https://zenodo.org/api/records?q=%22stochastic+differential+equations%22&type=publication&sort=mostrecent&size=10&status=published' \
    > /Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/zenodo/api_page_1.json
python3 -c "import json,sys; d=json.load(open('/Users/brock/Documents/GitHub/measuring-ai-economy/harvester/tests/fixtures/zenodo/api_page_1.json')); print('hits:', len(d.get('hits',{}).get('hits',[]))); print('total:', d.get('hits',{}).get('total'))"
```

Expected: at least 5 hits, total > 0. If the search returns nothing, swap the `q=` term to `"diffusion model"` and re-capture.

- [ ] **Step 2: Write failing fetcher tests at `harvester/tests/test_fetcher_zenodo.py`**

```python
"""Tests for harvester.fetchers.zenodo.ZenodoFetcher."""

import json
from pathlib import Path

import pytest

from harvester.fetchers.zenodo import ZenodoFetcher


_FIXTURE = Path(__file__).parent / "fixtures" / "zenodo" / "api_page_1.json"


def test_zenodo_fetcher_source_id_is_zenodo():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    assert f.source_id == "zenodo"


def test_zenodo_fetcher_base_url():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    assert f.base_url() == "https://zenodo.org/api/records"


def test_zenodo_fetcher_build_params_includes_term_and_pagination():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    params = f.build_params({"term": "diffusion model", "per_page": 20}, page=2)
    assert params["q"] == "diffusion model"
    assert params["page"] == 2
    assert params["size"] == 20
    assert params["type"] == "publication"
    assert params["status"] == "published"
    assert params["sort"] == "mostrecent"


def test_zenodo_fetcher_build_params_supports_resource_type_override():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    params = f.build_params({"term": "foo", "type": "dataset"}, page=1)
    assert params["type"] == "dataset"


def test_zenodo_fetcher_extract_items_reads_hits_hits():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    body = json.loads(_FIXTURE.read_text())
    items = list(f.extract_items(body))
    assert len(items) > 0
    # Sanity: each hit has an id and metadata
    for item in items[:3]:
        assert "id" in item
        assert "metadata" in item


def test_zenodo_fetcher_item_to_payload_kwargs_uses_canonical_url():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    body = json.loads(_FIXTURE.read_text())
    item = body["hits"]["hits"][0]
    kwargs = f.item_to_payload_kwargs(item)
    assert kwargs["source_url"].startswith("https://zenodo.org/records/")
    assert kwargs["content_type"] == "application/json"
    assert isinstance(kwargs["content_bytes"], bytes)
    # Sorted JSON => deterministic raw_hash later
    reparsed = json.loads(kwargs["content_bytes"])
    assert reparsed["id"] == item["id"]
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_zenodo.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.fetchers.zenodo'`.

- [ ] **Step 4: Implement `harvester/harvester/fetchers/zenodo.py`**

```python
"""Zenodo fetcher.

API: https://developers.zenodo.org/#records
Auth: none for public records.
Rate limit: unauthenticated cap is ~60 req/min; we pace at 1 req/sec.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from harvester.fetchers.http_api import HttpApiFetcher
from harvester.types import RateLimit


class ZenodoFetcher(HttpApiFetcher):
    source_id = "zenodo"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(
            requests_per_second=1.0,
            max_retries=3,
            backoff_seconds=[2, 5, 15, 60],
        )

    def base_url(self) -> str:
        return "https://zenodo.org/api/records"

    def build_params(self, query: dict[str, Any], *, page: int) -> dict[str, Any]:
        per_page = int(query.get("per_page", 50))
        params: dict[str, Any] = {
            "q": query.get("term", ""),
            "page": page,
            "size": per_page,
            "type": query.get("type", "publication"),
            "status": query.get("status", "published"),
            "sort": query.get("sort", "mostrecent"),
        }
        if "publication_date_gte" in query and "publication_date_lte" in query:
            # Zenodo supports range filters via the q string only.
            params["q"] = (
                f'{params["q"]} AND publication_date:'
                f'[{query["publication_date_gte"]} TO {query["publication_date_lte"]}]'
            ).strip()
        return params

    def extract_items(self, body: dict[str, Any]) -> Iterable[dict[str, Any]]:
        return body.get("hits", {}).get("hits", [])

    def item_to_payload_kwargs(self, item: dict[str, Any]) -> dict[str, Any]:
        zid = item.get("id")
        url = f"https://zenodo.org/records/{zid}" if zid else ""
        return {
            "source_url": url,
            "content_type": "application/json",
            "content_bytes": json.dumps(item, sort_keys=True).encode("utf-8"),
            "item_index": zid,
        }
```

- [ ] **Step 5: Run fetcher tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_fetcher_zenodo.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add harvester/harvester/fetchers/zenodo.py \
    harvester/tests/fixtures/zenodo/api_page_1.json \
    harvester/tests/test_fetcher_zenodo.py
git commit -m "$(cat <<'EOF'
feat(harvester): ZenodoFetcher (HttpApiFetcher subclass)

Paginates https://zenodo.org/api/records with q/type/status/sort/size
params, defaults to type=publication+status=published+sort=mostrecent.
1 req/sec pacing matches Zenodo's polite unauthenticated quota.
item_to_payload_kwargs emits canonical https://zenodo.org/records/{id}
URLs and sorted-JSON bytes for deterministic raw_hash.

Captured api_page_1.json fixture (10 stochastic-differential-equations
hits) covers extract_items + item_to_payload_kwargs paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: ZenodoETL + 4 golden samples + ETL tests

**Files:**
- Create: `harvester/harvester/etl/zenodo.py`
- Create: 4 `record_<variant>.input.json` + 4 `record_<variant>.expected.json` fixtures under `harvester/tests/fixtures/zenodo/`
- Create: `harvester/tests/test_etl_zenodo.py`

- [ ] **Step 1: Extract 4 representative single-record fixtures from the API page**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python3 - <<'PYEOF'
import json
from pathlib import Path

fxt_dir = Path("tests/fixtures/zenodo")
hits = json.loads((fxt_dir / "api_page_1.json").read_text())["hits"]["hits"]

# Pick variants by resource subtype. Print what's available, then write 4.
by_subtype = {}
for h in hits:
    sub = (h.get("metadata", {}).get("resource_type") or {}).get("subtype", "_none")
    by_subtype.setdefault(sub, h)

print("available subtypes:", list(by_subtype.keys()))

variant_map = {
    "article": "article",
    "preprint": "preprint",
    "conference-paper": "conference",
    "_none": "dataset",  # fallback bucket — we'll re-label its subtype below
}

for sub, label in variant_map.items():
    if sub in by_subtype:
        h = by_subtype[sub]
        if sub == "_none":
            # If we used the fallback, fake a 'dataset' marker so the ETL sees it.
            h.setdefault("metadata", {}).setdefault("resource_type", {})["type"] = "dataset"
            h["metadata"]["resource_type"]["subtype"] = None
        (fxt_dir / f"record_{label}.input.json").write_text(json.dumps(h, indent=2, sort_keys=True))
        print(f"wrote record_{label}.input.json (zenodo_id={h.get('id')})")
PYEOF
```

Expected: 4 `record_*.input.json` files created. If the API page doesn't contain all four subtypes, the script writes only what's available — manually re-run with a different fixture page or hand-edit the missing variants from a single hit.

- [ ] **Step 2: Write failing ETL tests at `harvester/tests/test_etl_zenodo.py`**

```python
"""Tests for harvester.etl.zenodo.ZenodoETL.

Golden-sample comparison: for each input fixture, ZenodoETL.parse() must
produce a ParsedDoc whose rows match the expected fixture field-by-field
(raw_hash mocked to a known value).
"""

import json
from pathlib import Path

import pytest

from harvester.etl.zenodo import ZenodoETL
from harvester.types import RawPayload


_FXT = Path(__file__).parent / "fixtures" / "zenodo"
_VARIANTS = ["article", "preprint", "conference", "dataset"]


def _raw_payload_for(name: str, tmp_path: Path) -> RawPayload:
    src = _FXT / f"record_{name}.input.json"
    dst = tmp_path / src.name
    dst.write_text(src.read_text())
    return RawPayload(
        file_path=dst,
        source_id="zenodo",
        source_url=f"https://zenodo.org/records/{json.loads(src.read_text())['id']}",
        raw_hash="sha256:test",
        request_params={},
    )


@pytest.mark.parametrize("variant", _VARIANTS)
def test_zenodo_etl_golden_sample(variant, tmp_path):
    etl = ZenodoETL()
    raw = _raw_payload_for(variant, tmp_path)
    parsed = etl.parse(raw)

    expected_path = _FXT / f"record_{variant}.expected.json"
    expected = json.loads(expected_path.read_text())

    # Compare ParsedDoc shape to expected.
    assert parsed.title == expected["title"]
    assert parsed.source_url == expected["source_url"]
    # published_date is a date or None; expected stores as string or null.
    if expected["published_date"] is None:
        assert parsed.published_date is None
    else:
        assert parsed.published_date.isoformat() == expected["published_date"]

    # Compare row count + target_tables.
    assert len(parsed.rows) == len(expected["rows"])
    for actual_row, expected_row in zip(parsed.rows, expected["rows"]):
        assert actual_row.target_table == expected_row["target_table"]
        # Compare data dict key-by-key; JSON-encoded fields compared as parsed.
        for key, exp_val in expected_row["data"].items():
            act_val = actual_row.data.get(key)
            if isinstance(exp_val, str) and exp_val.startswith(("[", "{")):
                # JSON-encoded value
                assert json.loads(act_val) == json.loads(exp_val), (
                    f"{variant}.{actual_row.target_table}.{key}"
                )
            else:
                assert act_val == exp_val, (
                    f"{variant}.{actual_row.target_table}.{key}: "
                    f"got {act_val!r}, expected {exp_val!r}"
                )


def test_zenodo_etl_source_id_and_schema_version():
    etl = ZenodoETL()
    assert etl.source_id == "zenodo"
    assert etl.expected_schema_version == 8


def test_zenodo_etl_handles_missing_publication_date(tmp_path):
    """A record without metadata.publication_date should produce
    published_date=None, not crash."""
    src = _FXT / "record_article.input.json"
    data = json.loads(src.read_text())
    data["metadata"].pop("publication_date", None)
    p = tmp_path / "no_date.json"
    p.write_text(json.dumps(data))

    raw = RawPayload(
        file_path=p, source_id="zenodo",
        source_url="https://zenodo.org/records/x",
        raw_hash="sha256:test", request_params={},
    )
    parsed = ZenodoETL().parse(raw)
    assert parsed.published_date is None
```

- [ ] **Step 3: Verify failure**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_zenodo.py -v
```

Expected: `ModuleNotFoundError: No module named 'harvester.etl.zenodo'`.

- [ ] **Step 4: Implement `harvester/harvester/etl/zenodo.py`**

```python
"""Zenodo ETL.

Pure parse: takes a Zenodo API record (one hit) and produces a ParsedDoc
with rows for harvest.document_metadata and harvest.zenodo_records.
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
    s = value[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _authors(record: dict[str, Any]) -> list[dict[str, str]]:
    creators = record.get("metadata", {}).get("creators") or []
    out: list[dict[str, str]] = []
    for c in creators:
        if isinstance(c, dict):
            name = c.get("name") or c.get("orcid") or ""
            if name:
                entry: dict[str, str] = {"name": name}
                if c.get("affiliation"):
                    entry["affiliation"] = c["affiliation"]
                if c.get("orcid"):
                    entry["orcid"] = c["orcid"]
                out.append(entry)
    return out


def _resource_type(record: dict[str, Any]) -> tuple[str | None, str | None]:
    rt = record.get("metadata", {}).get("resource_type") or {}
    return rt.get("type"), rt.get("subtype")


def _keywords(record: dict[str, Any]) -> list[str]:
    kws = record.get("metadata", {}).get("keywords") or []
    return [k for k in kws if isinstance(k, str)]


class ZenodoETL(ETL):
    source_id = "zenodo"
    expected_schema_version = 8

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())
        meta = record.get("metadata", {}) or {}
        zid = int(record["id"])
        url = f"https://zenodo.org/records/{zid}"
        pub_date = _date_or_none(meta.get("publication_date"))
        authors = _authors(record)
        rtype, rsubtype = _resource_type(record)
        keywords = _keywords(record)
        doi = record.get("doi") or meta.get("doi")
        title = (meta.get("title") or "")[:5000]
        abstract = meta.get("description")

        zen_row = Row(
            target_table="harvest.zenodo_records",
            data={
                "zenodo_id": zid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "resource_type": rtype,
                "resource_subtype": rsubtype,
                "keywords": keywords,
                "publication_date": pub_date,
                "license": (meta.get("license") or {}).get("id"),
                "zenodo_url": url,
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
                "source_url": url,
                "published_date": pub_date,
                "document_type": rsubtype or rtype or "publication",
                "payload": json.dumps(
                    {
                        "zenodo_id": zid,
                        "resource_type": rtype,
                        "resource_subtype": rsubtype,
                        "keywords": keywords,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=url,
            published_date=pub_date,
            rows=[meta_row, zen_row],
            metadata={
                "zenodo_id": zid,
                "doi": doi,
                "resource_type": rtype,
                "resource_subtype": rsubtype,
            },
        )
```

- [ ] **Step 5: Generate the 4 expected fixtures by running the ETL once and snapshotting**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run python3 - <<'PYEOF'
import json
from datetime import date
from pathlib import Path
from harvester.etl.zenodo import ZenodoETL
from harvester.types import RawPayload

fxt = Path("tests/fixtures/zenodo")
for v in ["article", "preprint", "conference", "dataset"]:
    src = fxt / f"record_{v}.input.json"
    if not src.exists():
        print(f"SKIP {v}: input missing")
        continue
    raw = RawPayload(
        file_path=src, source_id="zenodo",
        source_url=f"https://zenodo.org/records/{json.loads(src.read_text())['id']}",
        raw_hash="sha256:test", request_params={},
    )
    parsed = ZenodoETL().parse(raw)
    out = {
        "title": parsed.title,
        "source_url": parsed.source_url,
        "published_date": parsed.published_date.isoformat() if parsed.published_date else None,
        "rows": [{"target_table": r.target_table, "data": {
            k: (v.isoformat() if isinstance(v, date) else v)
            for k, v in r.data.items()
        }} for r in parsed.rows],
    }
    (fxt / f"record_{v}.expected.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"wrote record_{v}.expected.json")
PYEOF
```

Expected: 4 `record_*.expected.json` files written. Manually open one and sanity-check the shape: 2 rows, target_tables are `harvest.document_metadata` and `harvest.zenodo_records`, fields look right.

- [ ] **Step 6: Run ETL tests**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest tests/test_etl_zenodo.py -v
```

Expected: 6 passed (4 parameterized + 2 standalone).

- [ ] **Step 7: Run full suite to catch regressions**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: count = previous (139) + 12 new (6 fetcher + 6 ETL) = 151 passed.

- [ ] **Step 8: Commit**

```bash
git add harvester/harvester/etl/zenodo.py \
    harvester/tests/fixtures/zenodo/record_*.json \
    harvester/tests/test_etl_zenodo.py
git commit -m "$(cat <<'EOF'
feat(harvester): ZenodoETL + 4 golden samples (article/preprint/conference/dataset)

Parses one Zenodo API record into ParsedDoc with rows for
harvest.document_metadata (generic) and harvest.zenodo_records (dense).
Extracts authors with optional affiliation+orcid, resource_type+subtype,
keywords array, license id, and ISO publication_date. Missing date or
DOI fields produce None rather than crashing.

Golden samples cover the four resource_type subtypes the legacy script
typically returns. Test compares parsed output field-by-field against
snapshotted expected JSON.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: sources.yaml entry + dry-run smoke

**Files:**
- Modify: `harvester/harvester/config/sources.yaml`

- [ ] **Step 1: Append the `zenodo:` entry to `sources.yaml`**

Append to the end of `harvester/harvester/config/sources.yaml`:

```yaml
zenodo:
  fetcher: harvester.fetchers.zenodo.ZenodoFetcher
  etl: harvester.etl.zenodo.ZenodoETL
  rolling_window_days: 30
  inbox_backpressure_max: 5000
  daily_cost_ceiling_usd: 5.00
  expected_schema_version: 8
  triage_enabled: true
  citation_chain_enabled: true
  triage_threshold: 0.4
  triage_model: "claude-sonnet-4-6"
  scout_base_url: "https://zenodo.org"
  tier_1_terms:
    - "stochastic differential equations"
    - "diffusion model"
    - "information geometry"
    - "Wasserstein distributionally robust optimization"
    - "Fokker-Planck"
    - "score-based generative model"
    - "uncertainty quantification deep learning"
    - "neural SDE"
    - "latent space geometry"
    - "model calibration probabilistic"
    - "canine cognition"
    - "dog behavior training"
    - "BJJ Brazilian jiu-jitsu"
    - "MMA training science"
    - "strength training hypertrophy"
    - "performance psychology grit"
    - "flow state athletes"
    - "Shannon information theory"
    - "control systems PID"
    - "symbolic AI knowledge graph"
  tier_2_terms: []
```

- [ ] **Step 2: Dry-run to verify the entry parses**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run zenodo --tier=tier_1 --dry-run
```

Expected: prints `DRY RUN: source=zenodo, terms=[...20 terms...], window=YYYY-MM-DD..YYYY-MM-DD, limit=0`. No exceptions.

- [ ] **Step 3: Live single-term run with low limit, to catch wiring bugs**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run harvester run zenodo --query "stochastic differential equations" --limit 3
```

Expected: a run finishes with `status=completed`, `fetched>=1`, `deposited>=1`. Check `harvest.run_log`:

```bash
psql wintermute -c "SELECT id, source_id, status, items_fetched, items_deposited, items_failed FROM harvest.run_log WHERE source_id='zenodo' ORDER BY id DESC LIMIT 3"
```

Expected: at least one row with `status='completed'`, positive `items_fetched` and `items_deposited`.

- [ ] **Step 4: Verify the analytical table populated**

```bash
psql wintermute -c "SELECT count(*) FROM harvest.zenodo_records"
psql wintermute -c "SELECT zenodo_id, title, resource_type, resource_subtype FROM harvest.zenodo_records ORDER BY id DESC LIMIT 5"
```

Expected: count > 0; sample rows have non-null `zenodo_id`, `title`, and a `resource_type` like `publication`.

- [ ] **Step 5: Commit**

```bash
git add harvester/harvester/config/sources.yaml
git commit -m "$(cat <<'EOF'
feat(harvester): register zenodo source in sources.yaml

20 tier_1 terms spanning Wintermute's research axes (stochastic
dynamics, information geometry, generative models; canine cognition;
martial arts + training science; mental performance; complexity).
30-day rolling window, triage enabled, citation-chain enabled,
expected_schema_version pinned to 8.

Live smoke run with --query "stochastic differential equations"
--limit 3 produced a completed run with non-zero fetched+deposited
and a populated harvest.zenodo_records row.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Launchd wrapper + plist

**Files:**
- Create: `~/.wintermute/scripts/jobs/harvest_zenodo.sh`
- Create: `~/Library/LaunchAgents/com.wintermute.harvest-zenodo.plist`

**Note:** These two files live outside the repo (under `~/.wintermute/` and `~/Library/LaunchAgents/`). They are part of the Wintermute deployment surface, not the harvester codebase. No git commit captures them; the operational note (Task 6) records their installation.

- [ ] **Step 1: Write the wrapper script**

Create `/Users/brock/.wintermute/scripts/jobs/harvest_zenodo.sh`:

```bash
#!/usr/bin/env bash
# Daily Zenodo harvest at 23:30 local.

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

run_job harvest_zenodo -- \
    "$UV_BIN" run harvester run zenodo --tier=tier_1
```

```bash
chmod +x /Users/brock/.wintermute/scripts/jobs/harvest_zenodo.sh
```

- [ ] **Step 2: Write the plist**

Create `/Users/brock/Library/LaunchAgents/com.wintermute.harvest-zenodo.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wintermute.harvest-zenodo</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/brock/.wintermute/scripts/jobs/harvest_zenodo.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>23</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_zenodo.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/brock/.wintermute/logs/cron/harvest_zenodo.launchd.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/brock/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 3: Verify the wrapper runs cleanly when invoked directly**

```bash
/Users/brock/.wintermute/scripts/jobs/harvest_zenodo.sh
echo "exit=$?"
tail -10 /Users/brock/.wintermute/logs/cron/harvest_zenodo.log
```

Expected: `exit=0`. Last log lines show `START`, run logs for several terms, and `END exit=0`. At least some runs should show `status=completed fetched>0 deposited>0`.

- [ ] **Step 4: Load the launchd agent**

```bash
launchctl load /Users/brock/Library/LaunchAgents/com.wintermute.harvest-zenodo.plist
launchctl list | grep harvest-zenodo
```

Expected: one line `- 0 com.wintermute.harvest-zenodo` (the dash is no-exit-code-yet, which is correct before its first fire).

- [ ] **Step 5: No commit for this task** — files live outside the repo.

---

### Task 6: Start 3-day parallel-window operational note

**Files:**
- Create: `docs/superpowers/notes/zenodo-parallel-window.md`

This task creates the operational checkpoint that the daily soak-test reviews against. No code.

- [ ] **Step 1: Write the operational note**

Create `docs/superpowers/notes/zenodo-parallel-window.md`:

```markdown
# Zenodo Migration — 3-Day Soak Window

**Started:** [fill in actual date+time of Task 5 Step 4 — when launchd was loaded]

**Old endpoint:** `~/.wintermute/scripts/search_papers.py` zenodo block (stages markdown to `~/.wintermute/staging/`; not in harvest DB).

**New endpoint:** `harvester run zenodo --tier=tier_1` via `com.wintermute.harvest-zenodo` (lands in `harvest.document_metadata` + `harvest.zenodo_records`).

**Verification model:** Soak test, not coverage overlap. Legacy zenodo never wrote to the harvest DB, so `harvester compare-sources` is not applicable.

## Daily check (run each morning during the soak)

```bash
# 1. Did the nightly cron fire and complete?
tail -30 /Users/brock/.wintermute/logs/cron/harvest_zenodo.log

# 2. Run-log: every run for the last 24h
psql wintermute -c "
SELECT id, source_id, status, items_fetched, items_deposited, items_failed, started_at
FROM harvest.run_log
WHERE source_id='zenodo' AND started_at > now() - interval '24 hours'
ORDER BY id DESC
"

# 3. Per-term deposit rate (look for terms returning 0 systematically)
psql wintermute -c "
SELECT (request_params->>'q') AS term,
       count(*) AS runs,
       sum(items_fetched) AS fetched,
       sum(items_deposited) AS deposited
FROM harvest.run_log
WHERE source_id='zenodo' AND started_at > now() - interval '24 hours'
GROUP BY term
ORDER BY deposited DESC
"

# 4. Triage scoring is happening
psql wintermute -c "
SELECT count(*) AS scored, avg(score)::numeric(4,2) AS avg_score
FROM harvest.triage_results
WHERE doc_id IN (
    SELECT id FROM harvest.document_metadata
    WHERE source_id='zenodo' AND created_at > now() - interval '24 hours'
)
"

# 5. No new failure_patterns alerted
psql wintermute -c "
SELECT error_signature, occurrence_count, last_seen_at, mitigation_status
FROM harvest.failure_patterns
WHERE source_id='zenodo' AND last_seen_at > now() - interval '24 hours'
"
```

## Green criteria (all three for 3 consecutive days)

1. ≥1 `status='completed'` run in `harvest.run_log` per day, with sum(items_deposited) > 0.
2. ≥10% of deposited docs have a triage score recorded (LLM is reaching them).
3. No `harvest.failure_patterns` row crosses `occurrence_count >= 5` with `mitigation_status='unaddressed'`.

If a criterion fails on day N, restart the 3-day clock and root-cause the failure before continuing.

## Cutover

When all three days pass:
1. Update this note: "Cutover date: YYYY-MM-DD"
2. Proceed to Task 7 (sunset legacy zenodo path).
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/notes/zenodo-parallel-window.md
git commit -m "$(cat <<'EOF'
docs: zenodo migration soak-window checkpoint

3-day operational note with daily verification queries and the three
green-criteria gates. Differs from Phase 2 arxiv: legacy zenodo never
wrote to the harvest DB, so compare-sources is N/A; verification is
pure soak (run completion + triage coverage + no new failure clusters).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Stop here** — the next ~72 hours are operational, not code. Resume at Task 7 only after the soak window passes per the note's green criteria.

---

### Task 7: Cutover — remove zenodo from `~/.wintermute/scripts/search_papers.py`

**Files:**
- Modify: `~/.wintermute/scripts/search_papers.py`

**Pre-condition:** Task 6 soak passed (3 consecutive days, all green criteria).

- [ ] **Step 1: Confirm soak passed**

Re-run the daily check from `zenodo-parallel-window.md` one final time. Confirm all three green criteria hold. If any fails, do not proceed.

- [ ] **Step 2: Edit `~/.wintermute/scripts/search_papers.py` to remove the Zenodo block**

The legacy script contains three source blocks: arxiv (already sunset), zenodo (this task), ssrn (still active). Edit:

1. Remove the `# ----- Zenodo -----` section (lines ~125–175 in the current file) — the `ZENODO_API` constant, the `search_zenodo()` function, and any docstring references in the module header.
2. Remove `zenodo` from the `--sources` default list in `argparse` setup (if present).
3. Remove `search_zenodo(...)` calls from `main()`.
4. Keep the SSRN block and the dedup machinery untouched.

The exact diff depends on the script's current state; do not rewrite the file from scratch — edit minimally.

- [ ] **Step 3: Smoke-test the edited script**

```bash
python3 /Users/brock/.wintermute/scripts/search_papers.py --sources ssrn --dry-run --max 1
```

Expected: SSRN path still works; no zenodo references in the output. The script exits 0.

- [ ] **Step 4: Update the parallel-window note**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
# Edit docs/superpowers/notes/zenodo-parallel-window.md, append at the bottom:
# ## Cutover
# **Date:** YYYY-MM-DD
# Removed search_zenodo() and ZENODO_API from ~/.wintermute/scripts/search_papers.py.
# Legacy staging halted; new pipeline is authoritative.
```

- [ ] **Step 5: Commit the note update**

```bash
git add docs/superpowers/notes/zenodo-parallel-window.md
git commit -m "$(cat <<'EOF'
docs: zenodo cutover complete

Soak window passed all three green criteria over the 3-day check.
Removed search_zenodo() and ZENODO_API from
~/.wintermute/scripts/search_papers.py; new harvester pipeline is
now the authoritative zenodo source.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Note: `~/.wintermute/scripts/search_papers.py` is outside the repo, so its edits aren't captured by git. The commit above just timestamps the cutover in the repo's operational record.

---

### Task 8: 7-day post-cutover stability monitor + final verification

**No new files.** Operational checkpoint only.

- [ ] **Step 1: Daily quick-check for 7 days post-cutover**

Each day, run:

```bash
psql wintermute -c "
SELECT date_trunc('day', started_at) AS day,
       count(*)                    AS runs,
       count(*) FILTER (WHERE status='completed') AS completed,
       count(*) FILTER (WHERE status='failed')    AS failed,
       sum(items_deposited)        AS deposited
FROM harvest.run_log
WHERE source_id='zenodo' AND started_at > now() - interval '8 days'
GROUP BY day
ORDER BY day DESC
"
```

Expected each day: `failed=0`, `deposited>0`, `runs >= 1`.

- [ ] **Step 2: Final test suite + CLI smoke**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv run pytest 2>&1 | tail -3
uv run harvester --help 2>&1 | grep -E "run|calibration|compare-sources"
uv run harvester run zenodo --tier=tier_1 --dry-run | head -3
```

Expected: full suite green (≥151 passed); CLI surface shows the existing commands; dry-run prints the expected source/terms/window line.

- [ ] **Step 3: Verify zenodo is producing triage-scored docs**

```bash
psql wintermute -c "
SELECT count(*) AS docs_scored
FROM harvest.triage_results tr
JOIN harvest.document_metadata dm ON dm.id = tr.doc_id
WHERE dm.source_id='zenodo' AND tr.scored_at > now() - interval '7 days'
"
```

Expected: `docs_scored > 0`.

- [ ] **Step 4: Verify citation-chain candidates are flowing**

```bash
psql wintermute -c "
SELECT count(*) AS candidates_from_zenodo
FROM harvest.expansion_candidates
WHERE parent_doc_id IN (
    SELECT id FROM harvest.document_metadata
    WHERE source_id='zenodo' AND created_at > now() - interval '7 days'
)
"
```

Expected: `candidates_from_zenodo > 0` (assumes at least one zenodo paper had a DOI eligible for citation expansion). If 0, that's a soft signal — zenodo DOIs may be underrepresented in the soak window; not a blocker.

- [ ] **Step 5: Final note + branch ready to merge**

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy
git log main..HEAD --oneline
git status
```

Expected: 5 commits on `feat/zenodo-migration` ahead of main (migration + fetcher + ETL + sources.yaml + soak-window note + cutover note = up to 6 depending on whether the operational notes batch). Working tree clean.

At this point the branch is ready for the `superpowers:finishing-a-development-branch` skill — merge, push, or PR per operator preference.

---

## Self-Review

**1. Spec coverage**

| Requirement | Task |
|---|---|
| ZenodoFetcher (HttpApiFetcher subclass) | Task 2 |
| ZenodoETL with golden samples | Task 3 |
| Migration: harvest.zenodo_records analytical table | Task 1 |
| sources.yaml registration | Task 4 |
| Launchd nightly job | Task 5 |
| 3-day parallel verification window | Task 6 |
| Atomic cutover (sunset legacy zenodo) | Task 7 |
| 7-day stability monitor | Task 8 |

All scope items from the Phase 3 roadmap §3.3 zenodo bullet covered. The `Crawl4aiFetcher` and `[html]` extra are SSRN concerns, not zenodo's — out of scope.

**2. Placeholder scan** — none. Every step has a complete code block, exact bash command, expected output, or specific file edit. The one templated string (`[fill in actual date+time of Task 5 Step 4]` in the operational note) is a runtime value the operator fills in; it's marked explicitly.

**3. Type consistency**

- `harvest.zenodo_records` schema (Task 1) — column names match the keys ZenodoETL writes (Task 3): `zenodo_id`, `doi`, `title`, `abstract`, `authors`, `resource_type`, `resource_subtype`, `keywords`, `publication_date`, `license`, `zenodo_url`, `raw_hash`.
- `ZenodoFetcher.source_id == "zenodo"` (Task 2) and `ZenodoETL.source_id == "zenodo"` (Task 3) — match the sources.yaml key (Task 4).
- `expected_schema_version = 8` (Task 3) matches migration filename `008_zenodo_records.sql` (Task 1) and sources.yaml `expected_schema_version: 8` (Task 4).
- `base_url() == "https://zenodo.org/api/records"` (Task 2) matches the URL the captured fixture comes from (Task 2 Step 1).
- Canonical source URL pattern `https://zenodo.org/records/{id}` consistent across fetcher (item_to_payload_kwargs), ETL (meta_row + zen_row), and soak-window queries.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-13-zenodo-migration.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks.

**2. Inline Execution** — execute in this session via executing-plans, sequential tasks with checkpoints.

Which approach?
