# Harvester Evolution — Foundations, Migration, Self-Improvement Design Spec

**Project:** measuring-ai-economy + Wintermute pipeline
**Date:** 2026-05-11
**Status:** Design approved; ready for implementation planning
**Parent specs:**
- `docs/superpowers/specs/2026-05-11-harvester-design.md` (MVP)
- `docs/design/harvester-agent-spec.md` v0.1.0
- `docs/design/harvester-agent-spec-addendum-a.md`

---

## 1. Purpose and scope

The harvester MVP (parent spec) shipped a working baseline: a Federal Register vertical slice with rigorous provenance and TEVV. It has two architectural gaps that this spec addresses:

1. **No self-improvement.** The harvester gets faster as `harvest.fetched_items` grows (dedup), but it doesn't learn. Citation chains, term discovery, author following, saturation detection — all pinned in the design but unimplemented.

2. **Underused MUI affordances.** Sources publish `llms.txt`, `robots.txt`, `sitemap.xml`, `.well-known/openapi.json`, RSS — we ignore all of it. Wintermute also has accumulated working tools (`crawl4ai`, MCP subprocess calls, an arxiv LLM triage tool) that operate in parallel to the harvester package without integration.

This spec defines:
- **Foundations**: MUI scout module + multi-backend fetcher hierarchy (HTTP API, crawl4ai, MCP, RSS) + ABCs for OAI-PMH, DCAT, BulkDownload
- **Migration**: sunset of `~/.wintermute/scripts/search_papers.py`, `drain_url_c4a.py`, `tools/arxiv_llm_triage.py` and re-implementation as harvester components
- **Self-improvement**: co-occurrence ledger, citation chain expansion, saturation monitor, failure pattern classifier, integrated LLM triage

Guiding principle (from operator feedback): **the harvester aims for *enough to know*, not *everything*.** Apply the 37% rule — be selective, dedupe aggressively, prefer concept-once-source-many over completeness. The graph stays tight.

---

## 2. Architecture overview

```
┌── harvester package (existing, extended) ────────────────────────────────┐
│                                                                            │
│  fetchers/                                                                 │
│  ├── base.py              Fetcher ABC (existing — extended with seen kwarg)│
│  ├── http_api.py          [NEW] HttpApiFetcher (extracted from FR pattern) │
│  ├── crawl4ai_base.py     [NEW] Crawl4aiFetcher                            │
│  ├── mcp_base.py          [NEW] McpFetcher (claude subprocess)             │
│  ├── rss_base.py          [NEW] RssFetcher                                 │
│  ├── oai_pmh_base.py      [NEW] OaiPmhFetcher ABC only (skeleton)          │
│  ├── dcat_base.py         [NEW] DcatFetcher ABC only (skeleton)            │
│  ├── bulk_download_base.py [NEW] BulkDownloadFetcher ABC only (skeleton)   │
│  ├── federal_register.py  (existing — refactored to inherit HttpApiFetcher)│
│  ├── arxiv.py             [NEW] HttpApi + RSS                              │
│  ├── zenodo.py            [NEW] HttpApi + crawl4ai for HTML pages          │
│  ├── ssrn.py              [NEW] crawl4ai-only                              │
│  ├── url_drain.py         [NEW] crawl4ai-only, single-URL                  │
│  └── pubmed.py            [NEW] MCP-backed                                 │
│                                                                            │
│  discovery/                                                                │
│  ├── scout.py             [NEW] MuiScout orchestrator                     │
│  ├── llms_txt.py          [NEW] llms.txt parser                          │
│  ├── sitemap.py           [NEW] sitemap.xml parser                       │
│  ├── robots.py            [NEW] robots.txt parser                        │
│  └── openapi.py           [NEW] .well-known/openapi.json discovery       │
│                                                                            │
│  improvement/             [NEW]                                            │
│  ├── co_occurrence.py     cross-source dedup → co_sources edges          │
│  ├── citation_chain.py    Semantic Scholar reference expansion           │
│  ├── saturation.py        deposit_ratio computation + alerts             │
│  └── failure_patterns.py  per-source error clustering                    │
│                                                                            │
│  triage/                  [NEW]                                            │
│  └── llm_triage.py        adapted from .wintermute/tools/arxiv_llm_triage│
│                                                                            │
│  etl/                     (existing, extended)                            │
│  ├── federal_register.py  (existing)                                       │
│  ├── arxiv.py             [NEW] per-source ETL                            │
│  ├── zenodo.py            [NEW]                                            │
│  ├── ssrn.py              [NEW]                                            │
│  ├── url_drain.py         [NEW]                                            │
│  └── pubmed.py            [NEW]                                            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

┌── Postgres harvest schema (extended) ────────────────────────────────────┐
│  + harvest.data_sources.discovery_notes (jsonb)    MUI scout cache       │
│  + harvest.data_sources.last_scouted_at             when last probed      │
│  + harvest.expansion_candidates                     citation/author/term  │
│  + harvest.co_sources                               cross-source ledger   │
│  + harvest.co_occurrence (view)                     aggregated co-counts  │
│  + harvest.failure_patterns                         clustered errors      │
│  + harvest.run_log.new_graph_nodes                  post-extraction count │
│  + harvest.triage_results                           structured triage     │
│  + harvest.saturation (view)                        deposit_ratio per day │
└────────────────────────────────────────────────────────────────────────────┘

┌── Existing Wintermute scripts ───────────────────────────────────────────┐
│  ~/.wintermute/scripts/                                                   │
│  ├── search_papers.py     SUNSET (→ ArxivFetcher + ZenodoFetcher + Ssrn) │
│  ├── drain_url_c4a.py     SUNSET (→ UrlDrainFetcher)                     │
│  └── stage_document.py    KEEP (used by other non-harvester flows)        │
│  ~/.wintermute/tools/                                                     │
│  └── arxiv_llm_triage.py  SUNSET (→ harvester/triage/llm_triage.py)      │
│  ~/.wintermute/sources/                                                   │
│  └── paper_keywords.yaml  SUNSET (content folded into harvester sources)  │
│                                                                            │
│  Sunset path: move to ~/.wintermute/scripts/_sunset/<date>-<name>          │
│  After 7 days post-cutover stable: move to _sunset/_archive/               │
│  After 90 days: deletable                                                  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component contracts

### 3.1 Fetcher hierarchy

The existing `Fetcher` ABC's contract is unchanged:

```python
class Fetcher(ABC):
    source_id: str
    def __init__(self, archive: RawArchive) -> None: ...
    @abstractmethod
    def rate_limit_spec(self) -> RateLimit: ...
    @abstractmethod
    def iter_payloads(self, query: dict, *, seen: set[str] | None = None) -> Iterable[RawPayload]: ...
    def _pace(self) -> None: ...
```

Five new helper bases factor out recurring patterns:

```python
class HttpApiFetcher(Fetcher):
    """For sources with paginated JSON APIs (FR, OpenAlex, Semantic Scholar)."""
    @abstractmethod
    def base_url(self) -> str: ...
    @abstractmethod
    def build_params(self, query: dict, *, page: int) -> dict: ...
    @abstractmethod
    def extract_items(self, response_body: dict) -> Iterable[dict]: ...
    @abstractmethod
    def item_to_payload_kwargs(self, item: dict) -> dict:
        """Return {source_url, content_type, content_bytes} for archive.write()."""
    # iter_payloads supplied by base: loop pages, pace, seen-check, archive.write

class Crawl4aiFetcher(Fetcher):
    """For HTML/JS-heavy sources. Lifted from drain_url_c4a.py."""
    @abstractmethod
    def urls_to_crawl(self, query: dict) -> Iterable[str]: ...
    def crawl_config(self) -> "CrawlerRunConfig":
        """Default: headless, excludes nav/header/footer/script/style.
        Override for source-specific extraction (CSS selectors, wait conditions)."""
    last_known_good_selector: str | None = None  # sentinel; verified before extract

class McpFetcher(Fetcher):
    """For sources accessible via MCP tools (PubMed, Hugging Face, etc.)."""
    mcp_tool: str   # e.g., "mcp__claude_ai_PubMed__search_articles"
    @abstractmethod
    def args_for_query(self, query: dict) -> dict: ...
    @abstractmethod
    def items_from_response(self, response: dict) -> Iterable[dict]: ...
    # iter_payloads supplied by base: subprocess to claude with MCP tool call, parse JSON

class RssFetcher(Fetcher):
    """For sources offering RSS/Atom feeds."""
    @abstractmethod
    def feed_urls(self, query: dict) -> Iterable[str]: ...
    @abstractmethod
    def entry_to_payload_kwargs(self, entry: dict) -> dict: ...

class OaiPmhFetcher(Fetcher):
    """ABC stub for OAI-PMH protocol. NotImplementedError in Phase 1."""
    @abstractmethod
    def oai_endpoint(self) -> str: ...
    @abstractmethod
    def metadata_prefix(self) -> str: ...

class DcatFetcher(Fetcher):
    """ABC stub for DCAT-AP / CKAN catalogs. NotImplementedError in Phase 1."""
    @abstractmethod
    def catalog_url(self) -> str: ...

class BulkDownloadFetcher(Fetcher):
    """ABC stub for snapshot-based sources. NotImplementedError in Phase 1."""
    @abstractmethod
    def snapshot_url(self) -> str: ...
    @abstractmethod
    def parse_snapshot(self, path: Path) -> Iterable[dict]: ...
```

### 3.2 MUI scout

```python
@dataclass(frozen=True)
class DiscoveryNotes:
    base_url: str
    probed_at: datetime
    llms_txt: dict | None          # parsed /llms.txt
    robots_rules: dict | None      # parsed /robots.txt
    sitemap_urls: list[str]        # discovered via /sitemap.xml or robots
    openapi_spec: dict | None      # parsed /.well-known/openapi.json
    rss_feeds: list[str]           # <link rel="alternate" type="application/rss+xml"> hrefs
    schema_org_types: list[str]    # JSON-LD @type values found on the base page
    probe_errors: dict[str, str]   # per-endpoint error if any (404, timeout, parse error)

class MuiScout:
    def probe(self, base_url: str) -> DiscoveryNotes: ...
```

DiscoveryNotes persists to `harvest.data_sources.discovery_notes`. CLI: `harvester scout <source_id> [--force]`. Runner consults cached notes via `_has_recent_discovery_notes()` (refreshes if `last_scouted_at` is null or > 90 days old).

### 3.3 Self-improvement contracts

```python
# co-occurrence — integrated into runner; no separate class needed
# Triggered when payload.source_url is NOT in seen but content/DOI matches existing harvest.document_metadata row from a different source_id

class CitationChain:
    def __init__(self, semantic_scholar_client): ...
    def enqueue(self, parsed: ParsedDoc, parent_run_id: int) -> int:
        """Extract references from a paper, score against seeds, write to
        expansion_candidates. Returns count of candidates added."""
    def process_pending(self, max_batch: int = 100) -> ExpansionBatchResult:
        """Process proposed candidates: verify via Semantic Scholar, score,
        promote/reject. Called by weekly launchd job."""

class SaturationMonitor:
    def compute(self, source_id: str, window_days: int = 7) -> SaturationMetric: ...
    def check_alerts(self) -> list[SaturationAlert]: ...
    # Alert thresholds (in config): deposit_ratio < 0.05 for 7d → alert; < 0.20 for 14d → notice

class FailureClassifier:
    def classify(self, run_id: int) -> list[FailurePattern]:
        """Read failed items from harvest.fetched_items, normalize errors, upsert into
        harvest.failure_patterns. Called synchronously at end of each run."""
    def check_alerts(self) -> list[FailureAlert]:
        """Surface patterns crossing 10 occurrences in 7 days."""
```

### 3.4 LLM Triage

```python
@dataclass(frozen=True)
class TriageResult:
    score: float                   # 0.0–1.0 headline
    axes: dict[str, float]         # per-axis breakdown
    reason: str                    # 1-2 sentence justification
    rubric_version: str            # version of research_axes.yaml in use
    model_id: str                  # e.g., "claude-sonnet-4-6"
    prompt_hash: str               # SHA of rendered prompt + input

class LlmTriage:
    def __init__(self, *, model_id: str, axes_yaml: Path): ...
    def score(self, parsed: ParsedDoc) -> TriageResult: ...
```

Integrated into the runner as an optional per-source post-ETL hook. Configured via `sources.yaml`:

```yaml
arxiv:
  triage_enabled: true
  triage_threshold: 0.4      # below this: stage but flag (not gate)
  triage_model: claude-sonnet-4-6
  triage_axes: research_axes.yaml

federal_register:
  triage_enabled: false      # FR docs all stage; downstream decides
```

Honors the existing principle: triage is metadata, not a gate.

---

## 4. Storage extensions

### 4.1 Migration `003_mui_scout.sql`

```sql
ALTER TABLE harvest.data_sources
    ADD COLUMN IF NOT EXISTS discovery_notes JSONB,
    ADD COLUMN IF NOT EXISTS last_scouted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS data_sources_scouted_idx
    ON harvest.data_sources (last_scouted_at DESC NULLS LAST);
```

### 4.2 Migration `004_self_improvement.sql`

```sql
-- Expansion candidates: papers/authors/terms proposed by adaptive loops
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

-- Cross-source co-occurrence ledger
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

-- Failure pattern clustering
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

-- run_log gains a post-extraction signal
ALTER TABLE harvest.run_log
    ADD COLUMN IF NOT EXISTS new_graph_nodes INTEGER;

-- Triage results (structured triage replaces float-only)
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
```

### 4.3 Saturation view (derived)

```sql
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
```

Saturation rule: when `deposit_ratio < 0.05` sustained 7+ days for a source, the source has saturated against current queries. Triggers a "consider Discovery Layer or rubric bump" alert.

---

## 5. Data flow + integration points

### 5.1 Runner extensions

```python
def run(self, query: dict) -> RunResult:
    conn = get_connection()
    run_id = self._open_run_log(conn, query)
    try:
        if self._inbox_size() > self.config.inbox_backpressure_max:
            self._close_run_log(conn, run_id, status="cancelled", error="backpressure")
            return RunResult(run_id=run_id, status="cancelled", error="backpressure")

        self._assert_schema_version(conn)

        # NEW: MUI scout on first contact (cached after first run)
        if not self._has_recent_discovery_notes(conn):
            self._scout_and_persist(conn)

        with with_advisory_lock(conn, self.config.source_id):
            seen_urls = self._seen_urls_for_source(conn)
            result = self._drive(conn, run_id, query, seen_urls)

        # NEW: failure pattern classification on this run's failures
        self._classify_failures(conn, run_id)

        self._close_run_log(conn, run_id, status="completed", ...)
        return result
    except Exception:
        ...

def _drive(self, conn, run_id, query, seen_urls):
    archive = RawArchive(...)
    self.fetcher.archive = archive
    loader = Loader(conn)

    fetched = 0
    deposited = 0
    failed = 0
    for payload in self.fetcher.iter_payloads(query, seen=seen_urls):
        fetched += 1
        try:
            if self._already_seen(conn, payload.source_url):
                continue

            # NEW: cross-source co-occurrence check
            co = self._check_co_occurrence(conn, payload)
            if co:
                self._record_co_occurrence(conn, payload, co)
                continue

            parsed = self.etl.parse(payload)

            # NEW: optional triage hook
            if self.config.triage_enabled and self.triage is not None:
                triage_result = self.triage.score(parsed)
                self._record_triage(conn, parsed, triage_result)
                parsed.metadata["triage_score"] = triage_result.score
                if triage_result.score < self.config.triage_threshold:
                    parsed.metadata["triage_below_threshold"] = True

            rows = list(self.etl.to_rows(parsed))
            loader.load(rows, run_id=run_id)
            inbox_path = emit_markdown(parsed, ...)

            # NEW: enqueue citation chain expansion (async; processed by weekly job)
            if parsed.metadata.get("doi") and self.config.citation_chain_enabled:
                self._enqueue_citation_expansion(conn, parsed, run_id)

            self._record_fetched_item(conn, item_id=payload.source_url, ...)
            deposited += 1
        except Exception as e:
            failed += 1
            self._record_fetched_item(conn, status="failed", error=str(e), ...)

    return RunResult(...)
```

### 5.2 Co-occurrence detection

Lookup order (cheapest first):
1. **`raw_hash` match** — exact bytes seen before from a different source
2. **DOI match** — when ParsedDoc carries one; requires partial parse before final skip decision
3. **URL canonicalization match** — same URL with normalized scheme/fragment/trailing slash

Co-occurrence isn't free: it requires a partial parse to extract DOI for case 2. We pay parse cost only on the dedup-skip path (new URLs go through the normal flow). Cost measured in Phase 2 verification window.

### 5.3 Citation chain expansion (async)

- Synchronous enqueue: write proposed candidate to `harvest.expansion_candidates`
- Asynchronous processing: weekly launchd job `harvest_citation_expand.sh` runs `harvester expand-citations --max-batch 100`
- The expand-citations command:
  1. Fetches up to N proposed candidates ordered by score DESC
  2. For each, calls Semantic Scholar to verify + score
  3. Promotes to `approved` or `rejected` based on threshold
  4. Approved candidates added as seeds for the appropriate source's next run

### 5.4 Saturation monitoring

Nightly job `harvester check-saturation`:
- Reads `harvest.saturation` view, computes 7-day moving deposit_ratio per source
- If ratio < 0.05 for 7+ days → email Brock ("source X saturated")
- If ratio < 0.20 for 14+ days → quieter notice in morning brief

### 5.5 Failure pattern classification

Post-run, the runner reads its run's failed items from `harvest.fetched_items`, normalizes errors (strip line numbers, timestamps, varying URL paths), upserts into `harvest.failure_patterns`. Common signatures crossing 10 occurrences in 7 days trigger alerts. Mitigations tracked via `mitigation_status`.

### 5.6 Triage integration

Triage path is opt-in per source via `sources.yaml`. Triage results decorate the markdown frontmatter (`triage_score`, `triage_axes`, `triage_below_threshold`) but never block staging. Honors existing CLAUDE.md rule: triage is metadata, not a gate.

---

## 6. Migration plan (old script sunset)

### 6.1 Inventory + new owners

| Old artifact | Function | New owner |
|---|---|---|
| `scripts/search_papers.py` | Search arxiv/zenodo/ssrn | `ArxivFetcher`, `ZenodoFetcher`, `SsrnFetcher` (`sources.yaml`-registered) |
| `scripts/drain_url_c4a.py` | Single-URL crawl4ai drain | `UrlDrainFetcher` + CLI `harvester drain-url <URL>` |
| `tools/arxiv_llm_triage.py` | LLM triage of arxiv papers | `harvester.triage.llm_triage` (integrated as runner hook) |
| `sources/paper_keywords.yaml` | Keyword config | Content folded into per-fetcher `tier_1_terms` in `sources.yaml` |
| `scripts/stage_document.py` | Generic stager | **KEEP** (used by non-harvester flows) |
| `scripts/jobs/extract_arxiv.sh` | Picks staged arxiv paper for extraction | **KEEP** (extraction layer, not harvester) |
| `scripts/jobs/search_papers.sh` | Launchd wrapper | Repointed to `harvester run arxiv && harvester run zenodo && harvester run ssrn` |
| `~/Library/LaunchAgents/com.wintermute.search-papers.plist` | Schedule | Repointed to new wrapper |

### 6.2 Migration sequence (per source)

1. **Build the new harvester fetcher + tests, but don't sunset anything yet.** Both paths run in parallel.
2. **3-day parallel verification window:**
   - Old script + new harvester both run on their schedules
   - `harvester compare-sources <old_label> <new_label> --days 3` reports:
     - Counts of new staged docs per day
     - Specific docs caught/missed (set diff via document URLs)
     - Triage score distribution (Spearman correlation > 0.85 expected)
3. **Sunset cutover (atomic per source):**
   - `launchctl unload` old plist
   - Move old script to `~/.wintermute/scripts/_sunset/<YYYY-MM-DD>-<name>.py`
   - `grep -r` for stragglers; update any callers
   - Verify next new-path run produces equivalent output
4. **7 days post-cutover stable** → archive script (move to `_sunset/_archive/`)
5. **90 days** → deletable

### 6.3 Per-source migration order

1. **arxiv** — first migration. Cleanest source. Phase 2 vertical proof.
2. **zenodo** — similar shape; second.
3. **ssrn** — HTML-heavy; validates crawl4ai backend.
4. **url_drain** — replaces on-demand crawl4ai pattern.
5. **arxiv_llm_triage** — folded into runner triage hook; no separate CLI.

### 6.4 Rollback

If a sunsetted source's new fetcher breaks badly:
1. Restore old script from `_sunset/` (or git history)
2. `launchctl unload` new plist
3. `launchctl load` old plist
4. File a bug; new fetcher gets fixed
5. Re-cutover after green

---

## 7. Phased delivery

### Phase 1 — Foundations (horizontal slice)

**Scope:**
1. MUI scout module + 4 parsers (llms.txt, robots, sitemap, openapi)
2. Fetcher backend ABCs: `HttpApiFetcher`, `Crawl4aiFetcher`, `McpFetcher`, `RssFetcher` (implemented); `OaiPmhFetcher`, `DcatFetcher`, `BulkDownloadFetcher` (skeleton-only)
3. Existing FR fetcher refactored to inherit `HttpApiFetcher` (golden samples still pass)
4. Runner extension: lazy MUI scout on first contact
5. CLI: `harvester scout <source_id>`
6. Migration `003_mui_scout.sql`
7. Test coverage: ~15 new tests covering parsers with pinned fixtures + scout integration

**Acceptance:** `harvester scout federal_register` populates discovery_notes; existing FR pipeline still passes count validation; all 26+ MVP tests still pass + new tests green.

### Phase 2 — Vertical proof (arxiv end-to-end + migration)

**Scope:**
1. `ArxivFetcher` (HttpApi + RSS) + `ArxivETL` + golden samples for 4 paper types
2. Migration `005_arxiv_papers.sql` (per-source analytical table)
3. `LlmTriage` migrated from `arxiv_llm_triage.py` + integrated runner hook
4. Migration `004_self_improvement.sql` (triage_results, co_sources, expansion_candidates, failure_patterns — tables created even though not all populated yet)
5. 3-day parallel verification: old `search_papers.py` + new harvester both running
6. Cutover: old script moved to `_sunset/`; `paper_keywords.yaml` content folded into `sources.yaml`
7. Launchd plist + wrapper for `harvest_arxiv`

**Acceptance:** arxiv staged-doc volume within ±5% of old script during 3-day window; triage Spearman correlation > 0.85 on 50-doc sample; 7 consecutive daily runs post-cutover with no manual intervention.

### Phase 3 — Scale-out + self-improvement loops

**Scope:**
1. Remaining source migrations: zenodo, ssrn, url_drain (each follows Phase 2 pattern)
2. New sources: pubmed (MCP-backed), Semantic Scholar (used by citation_chain)
3. `CitationChain` machinery: post-ETL enqueue + weekly batch processor
4. Co-occurrence ledger populated at runtime (runner hooks wired in Phase 1, populated now)
5. `SaturationMonitor` + nightly check + email alerts
6. `FailureClassifier` + alert threshold
7. CLI: `harvester calibration --window 30d` — combined dashboard query
8. **New claudeclaw judgment job** (`harvest_judgment.md`): weekly review pass that processes proposed expansion candidates, classifies new sources by normalization category (1-4), and reviews unverified stochastic provenance rows. This is the LLM-judgment counterpart to all the launchd-deterministic jobs — created here because Phase 3 is the first phase needing it.

**Acceptance:**
- At least one citation-chain expansion candidate auto-promoted to a fetch
- At least one saturation alert fires OR `check-saturation` cleanly reports "no saturation yet"
- 7 consecutive nightly runs across all migrated sources with no manual intervention
- All sunset scripts in `_sunset/` (or `_sunset/_archive/` per timeline)

### Out of all three phases (deferred to future specs)

- **Author following loop** — needs more data accumulation first
- **Term discovery** — needs NLP infra (Spacy/YAKE) — separate dependency review
- **Score-driven query reordering** — needs feedback signal accumulation
- **Rubric versioning batch re-evaluation** — needs rubric stability + a version-bump trigger
- **Concrete impls** for `OaiPmhFetcher`, `DcatFetcher`, `BulkDownloadFetcher` (ABCs only in Phase 1)
- **Discovery Layer activation logic** — saturation alert is the *trigger*; the layer itself is its own design

---

## 8. TEVV regime extensions

### 8.1 New deterministic tests

| Component | Test type |
|---|---|
| MUI scout parsers (llms.txt, robots, sitemap, openapi) | Pinned fixtures for 5 llms.txt variants, 3 robots, 3 sitemap, 2 openapi; golden samples like FR ETL |
| HttpApiFetcher | FR golden samples still pass after refactor |
| Crawl4aiFetcher | Mocked crawl4ai responses; sentinel selector verified before extract |
| RssFetcher | Pinned feed fixtures (Atom + RSS 2.0) |
| McpFetcher | Mocked subprocess; live integration test gated by env var |

### 8.2 New stochastic tracking

| Component | Provenance recorded |
|---|---|
| Triage results | `{table: 'harvest.triage_results', row_pk, field: 'score'}` → `harvest.stochastic_provenance` |
| MCP fetcher responses | `{model_id, prompt_hash, tool_args}` → `harvest.stochastic_provenance` |
| Citation chain expansion | `{model_id, prompt_hash}` if LLM scoring used |

### 8.3 New cadenced checks

| Check | Cadence | Mechanism |
|---|---|---|
| Rubric stability | weekly | 20-doc fixture re-scored against current rubric; >0.15 delta vs. previous week alerts |
| Citation expansion review | weekly | claudeclaw judgment job promotes/rejects proposed candidates |
| Saturation check | nightly | new launchd job computes view + emails on threshold |
| Failure pattern aggregation | post-run | runner-side; alerts at 10-occurrence threshold |

### 8.4 Verification windows

- Phase 2 arxiv migration: 3-day parallel run (per 37% rule of a 1-week observation window)
- Phase 3 per-source migrations: 3-day parallel run each
- Phase 3 acceptance: 7-day post-cutover stable

---

## 9. Risks + mitigations

### 9.1 Risks mitigated in implementation

| Risk | Mitigation |
|---|---|
| MCP subprocess overhead | Batch where possible; cache MCP tool schemas; consider Python MCP SDK in future iteration |
| Co-occurrence parse-before-skip cost | Parse cost paid only on dedup-skip path (new-URL path unchanged); measure in Phase 2 |
| crawl4ai brittleness on layout changes | `last_known_good_selector` sentinel CSS verified before extraction; selector miss → loud failure |
| Stochastic provenance jsonb bloat | Side-table model (indexed by `(table_name, row_pk, field)`); only populated when stochastic step fed the row |
| Triage model drift | Weekly rubric_stability test on 20-doc fixture set; >0.15 score delta alerts |
| Parallel-run window disk churn | 3-day window; raw archive dedups by sha256; bounded |
| Citation chain runaway | Hard depth cap of 3; manual review of expansion_candidates before fetch; configurable weekly batch limit |
| Saturation false-positive | Threshold requires sustained 7+ days under ratio |

### 9.2 Risks acknowledged but not mitigated here

| Risk | Why deferred |
|---|---|
| MCP server availability | Wintermute already depends on MCP for other workflows; degrades same as rest |
| Semantic Scholar rate limits | Phase 3 problem; tune backoff in flight; 80k req/day at 1 req/sec gives ample headroom |
| Old-script callers we missed | `grep -r` covers cron paths; 3-day parallel window catches the rest; bounded risk |

### 9.3 Open questions resolved (with defaults)

| Question | Default |
|---|---|
| MCP fetcher: subprocess `claude` or Python MCP SDK? | Subprocess for Phase 1 (proven pattern); migrate to SDK if performance bites |
| Citation chain depth cap | 3 (matches design spec §8) |
| Expansion candidate review cadence | Weekly via claudeclaw judgment job |
| Triage rubric storage | Versioned YAML in `sources/research_axes.yaml`; each triage records `rubric_version` |
| Failure pattern alert threshold | 10 occurrences in 7 days (loose; tighten with data) |
| Saturation deposit_ratio threshold | 0.05 for 7d (alert), 0.20 for 14d (notice) |
| Sunset script disposition | 7d post-cutover → `_sunset/_archive/`; 90d → deletable |
| Old `paper_keywords.yaml` content | Folded into `sources.yaml` per-fetcher `tier_1_terms`; original moves to `_sunset/` |
| Discovery Layer activation | Out of scope; saturation alert is the trigger; the layer itself gets its own design |

---

## 10. Implementation phase ordering (preview for writing-plans handoff)

Phase 1 (Foundations) → standalone `writing-plans` output, separate cc_task:
- Scaffolding for discovery/, improvement/, triage/ subpackages
- Migration 003 (mui_scout)
- Migration 004 (self_improvement — tables created, not yet populated)
- MUI scout parsers + scout orchestrator + tests
- Fetcher backend ABCs + tests (concrete implementations for HttpApi/Crawl4ai/Mcp/Rss; skeletons for OaiPmh/Dcat/BulkDownload)
- Refactor existing FR fetcher to inherit HttpApiFetcher
- Runner extensions (lazy scout, hook stubs for triage/co-occurrence/citation_chain/failure)
- CLI: `harvester scout <source_id>`

Phase 2 (Vertical proof) → separate `writing-plans` output, separate cc_task:
- ArxivFetcher + ArxivETL + golden samples
- Migration 005 (arxiv_papers analytical table)
- LlmTriage migration + runner triage hook
- Verification: `harvester compare-sources` CLI
- Parallel-run launchd entries
- Cutover automation script
- Sunset of `search_papers.py` + `arxiv_llm_triage.py` + `paper_keywords.yaml`

Phase 3 (Scale-out + self-improvement) → multiple `writing-plans` outputs, multiple cc_tasks:
- One per migration: ZenodoFetcher, SsrnFetcher, UrlDrainFetcher, PubMedFetcher, SemanticScholarFetcher
- CitationChain machinery + weekly launchd job
- Co-occurrence ledger population
- SaturationMonitor + nightly job
- FailureClassifier + alerts
- Calibration dashboard CLI

---

## 11. What this spec does NOT cover

- The existing harvester MVP architecture (parent spec)
- Wintermute's existing pipeline behavior (drain, extraction, KG load) beyond the staging boundary
- Concrete impls for OAI-PMH, DCAT-AP, BulkDownload fetchers (skeletons only)
- Discovery Layer activation logic
- Author following / term discovery / score-driven query reordering / rubric versioning batch re-evaluation (deferred)
- New sources beyond what's listed (BLS/BEA/Census/Ramp/USPTO/USASpending/Eurostat/OECD remain post-MVP, post-Phase-3 backlog)
- Modifications to Wintermute's existing `extract_arxiv.sh` or other extraction-side jobs
