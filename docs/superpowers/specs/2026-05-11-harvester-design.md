# Harvester Agent — Design Spec

**Project:** measuring-ai-economy + Wintermute pipeline
**Date:** 2026-05-11
**Status:** Design approved; ready for implementation planning
**Parent docs:** `docs/design/harvester-agent-spec.md` v0.1.0, `docs/design/harvester-agent-spec-addendum-a.md`

---

## 1. Purpose and scope

Build an autonomous harvesting agent that fetches documents relevant to measuring AI's economic impact (federal documents, academic literature, alternative data sources) and deposits them into Wintermute's inbox for standard triage → staging → extraction → KG processing.

The harvester is a **data acquisition layer**. It does not analyze, synthesize, or interpret. Its responsibilities are:

1. Fetch raw bytes from upstream sources with full provenance.
2. Persist raw bytes to an immutable archive with a checksum manifest.
3. Normalize fetched content into structured postgres rows + inbox markdown.
4. Hand off to Wintermute's existing pipeline for downstream processing.

Everything beyond this — concept extraction, KG entity creation, concept-level deduplication, finding distillation — is the responsibility of downstream layers (Wintermute extraction + maintenance jobs + claudeclaw judgment passes).

---

## 2. Architecture

### 2.1 Repo split

**Research code** lives in `measuring-ai-economy/` (version-controlled, reproducibility artifact):

```
measuring-ai-economy/
├── harvester/
│   ├── fetchers/             # per-source fetcher modules
│   ├── etl/                  # parse + to_rows per source
│   ├── normalizer/           # source-agnostic inbox markdown emitter
│   ├── source_discovery/     # POST-MVP — crawler for new data sources
│   ├── ontology/             # Neo4j bootstrap scripts
│   ├── schemas/              # numbered SQL migrations
│   ├── tests/                # golden samples + unit tests
│   ├── cli.py                # single entrypoint
│   ├── pyproject.toml
│   └── uv.lock               # pinned for reproducibility
├── data/
│   ├── raw/{source}/{YYYY-MM}/{sha256}.{ext}    # gitignored
│   └── manifests/raw_manifest.parquet            # git-tracked, append-only
├── docs/
│   ├── design/               # original spec + addendum
│   ├── notes/                # ontology stack, research map
│   └── superpowers/specs/    # this document + future design specs
└── cc_tasks/                 # phased work tracking
```

**Operational glue** lives in `~/.wintermute/`:

```
~/.wintermute/
├── scripts/jobs/harvest_*.sh        # thin launchd wrappers; invoke harvester CLI
├── inbox/                           # harvester drops normalized markdown here
└── .claude/claudeclaw/jobs/
    └── harvest_judgment.md          # POST-MVP — weekly review job
```

**Launchd plists** in `~/Library/LaunchAgents/com.wintermute.harvest-*.plist`.

### 2.2 Components

The harvester is a single Python package with cleanly-bounded sub-modules. No monolith; each fetcher, ETL, etc. is self-contained.

```
┌── HARVEST AGENT ────────────────────────────────────────────┐
│                                                              │
│  ┌────────────┐    ┌──────────┐    ┌──────────────────┐    │
│  │ Fetcher    │ →  │ Raw      │ →  │ ETL              │    │
│  │ (per src)  │    │ Archive  │    │ (per src)        │    │
│  └────────────┘    └──────────┘    └──────────────────┘    │
│        ↓                                    ↓                │
│  ┌────────────┐                    ┌──────────────────┐    │
│  │ Manifest   │                    │ Postgres rows    │    │
│  │ (parquet)  │                    │ (harvest schema) │    │
│  └────────────┘                    └──────────────────┘    │
│                                             ↓                │
│                                    ┌──────────────────┐    │
│                                    │ Normalizer       │    │
│                                    │ (→ inbox/)       │    │
│                                    └──────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                          ↓
              ~/.wintermute/inbox/
                          ↓
        Wintermute pipeline (existing):
        triage → staging → extraction → Neo4j KG
```

### 2.3 Data flow

1. Launchd fires `harvest_<source>.sh` at scheduled time.
2. Wrapper sources `_lib.sh`, invokes `harvester run <source> [args]`.
3. Runner acquires postgres advisory lock on `source_id` (prevents concurrent duplicate fetches).
4. Runner checks `harvest.fetched_items` for already-seen refs; skips them.
5. Runner checks `len(~/.wintermute/inbox/)` for backpressure; pauses if above 500.
6. Runner writes `harvest.run_log` row, status='running'.
7. Fetcher's `iter_payloads(query)` yields `RawPayload` objects; each writes raw bytes to `data/raw/` and appends row to `raw_manifest.parquet`.
8. ETL's `parse(raw) → ParsedDoc`, `to_rows(parsed) → Iterable[Row]`.
9. Central `Loader` opens postgres transaction, writes rows to `harvest.<source>_*` tables.
10. Normalizer takes ParsedDoc + row IDs, emits markdown to inbox with frontmatter carrying `pg_refs`, `raw_hash`, `harvester_run_id`.
11. Runner updates `harvest.run_log` row, status='completed', counts captured.
12. Wintermute's existing `drain_inbox` job picks up inbox files for triage → staging → extraction → KG ingest.

---

## 3. Component contracts

### 3.1 Fetcher

```python
class Fetcher(ABC):
    source_id: str

    @abstractmethod
    def iter_payloads(self, query: Query) -> Iterable[RawPayload]: ...

    @abstractmethod
    def rate_limit_spec(self) -> RateLimit: ...
```

- Single method `iter_payloads` — fetcher decides internally whether it's one-step (API returns full docs) or two-step (HTML scrape → per-page fetch). No artificial discover/fetch split.
- `Query` is source-specific; each fetcher declares its own type. CLI parses YAML config into the right `Query` shape.
- Fetcher knows: pagination, authentication, rate limiting, raw-bytes-to-disk.
- Fetcher does **not**: normalize, write to postgres, check `seen.db`, manage the advisory lock. Those live in the runner.
- `RawPayload` carries: `raw_hash`, `file_path`, `content_type`, `fetched_at`, `request_params`, `source_url`, `source_id`.

### 3.2 ETL

```python
class ETL(ABC):
    source_id: str
    expected_schema_version: int   # checked against harvest.schema_migrations at startup

    @abstractmethod
    def parse(self, raw: RawPayload) -> ParsedDoc: ...

    @abstractmethod
    def to_rows(self, parsed: ParsedDoc) -> Iterable[Row]: ...
```

- Pure functions. Testable without a database.
- `expected_schema_version` is a single global integer matching the highest migration applied to `harvest.schema_migrations`. Mismatch on startup = hard fail.
- Stochastic fields (LLM-extracted) write provenance to `harvest.stochastic_provenance` side table, not as a column on the analytical row.

### 3.3 Loader

```python
class Loader:
    def load(self, rows: Iterable[Row], run_id: int) -> LoadResult: ...
```

- Single class, source-agnostic. Routes rows to correct tables by `Row.target_table` attribute.
- Manages transaction boundary. Failure rolls back the batch.
- Stamps `created_by_run_id` on every analytical row.

### 3.4 Normalizer

Source-agnostic. Single module. Takes `ParsedDoc` + the postgres row IDs that were created, emits markdown to inbox.

Frontmatter per `harvester-agent-spec.md` §6.1 plus our additions:
```yaml
pg_refs: [{table: "harvest.federal_register_documents", pk: 12345}]
raw_hash: "sha256:abc..."
harvester_run_id: 42
expected_schema_version: 2
```

### 3.5 CLI

```
harvester run <source> [--query=...] [--limit=N] [--dry-run]
harvester backfill <source> --from=YYYY-MM --to=YYYY-MM
harvester status                # last runs per source, queue depth, errors 24h
harvester validate <source>     # golden-sample tests
harvester migrate               # apply pending schema migrations
harvester expand --review-authors   # POST-MVP — review expansion proposals
```

### 3.6 Runner (cross-cutting)

- Acquires `pg_advisory_lock(hash(source_id))` before invoking fetcher.
- Checks `harvest.fetched_items` for already-seen refs.
- Checks inbox size; pauses if > 500 (backpressure).
- Writes `harvest.run_log` row at start, updates at finish.
- Enforces daily LLM-cost ceiling from config; halts run on overage.

---

## 4. Storage model

### 4.1 Principle

- **Knowledge** lives in Neo4j (entities + relationships + Findings).
- **Data** lives in postgres (raw observations, registries, run state).
- **Raw bytes** live on disk, indexed by a git-tracked parquet manifest.
- The graph holds **addressing** of postgres data (`pg_table`, `pg_pk_column` on Dataset nodes); it does not duplicate values.

### 4.2 Postgres schema `harvest` (in existing `wintermute` db)

**Operational:**
- `run_log` — every harvester invocation: id, source_id, started_at, finished_at, code_sha, expected_schema_version, args jsonb, model_versions jsonb, items_fetched, items_deposited, items_failed, llm_cost_usd, status, error
- `fetched_items` — item_id (URL/DOI normalized), source_id, raw_hash, fetched_at, status, run_id FK, inbox_path, error
- `query_log` — query_id, source_id, query jsonb, executed_at, results_count, new_items_count
- `schema_migrations` — id, sha, applied_at, applied_by, description

**Registries:**
- `data_sources` — source_id PK, name, provider, provider_type, construct, unit_of_analysis, population, sampling_frame, measurement_method, access_url, access_method, normalization_category (1-4), ontology_mappings jsonb, status, discovery_date, last_checked
- `construct_mappings` — construct_id PK, name, definition, ontology_entity, comparable_constructs jsonb, comparison_caveats
- `crosswalks` — crosswalk_id, from_taxonomy, from_code, to_taxonomy, to_code, mapping_type, confidence, source, valid_from, valid_to

**Metadata (thin, generic):**
- `document_metadata` — doc_id, source_id, title, authors jsonb, doi, source_url, published_date, document_type, payload jsonb, raw_hash, created_by_run_id FK

**Analytical observations (dense, source-shaped):**
- `federal_register_documents` — typed columns: document_number, title, type, agencies (text[]), citation, publication_date, full_text_url, body_text, abstract, executive_order_number, etc.
- `ramp_index_observations` — (POST-MVP)
- `btos_adoption_rates` — (POST-MVP)
- `patentsview_grants` — (POST-MVP)
- `usaspending_ai_contracts` — (POST-MVP)
- (one densely-typed table per source where structure is rich enough to warrant it; otherwise use `document_metadata` + payload jsonb)

**Stochastic provenance (side table):**
- `stochastic_provenance` — (table_name, row_pk, field, model_id, prompt_hash, params jsonb, confidence, reviewed). Composite PK on (table_name, row_pk, field). Only populated when stochastic steps fed the row/field.

**Expansion (POST-MVP):**
- `expansion_candidates` — candidate_id, kind (paper|author|term), payload jsonb, parent_id, depth, score, status (proposed|approved|rejected), proposed_at, reviewed_at
- `discovered_authors` — author_name, semantic_scholar_id, discovery_source, paper_count, high_score_count, status

### 4.3 Raw archive

```
measuring-ai-economy/data/raw/
├── federal_register/2026-05/{sha256}.json
├── semantic_scholar/2026-05/{sha256}.json
└── ...
```

- Gitignored. Local disk only initially; future option to back to B2/S3.
- Companion `data/manifests/raw_manifest.parquet` is git-tracked: `raw_hash, source_id, source_url, fetched_at, request_params_json, content_type, byte_size, file_path_relative`.
- Manifest is append-only. Any researcher with the repo can re-fetch from `source_url` and verify against `raw_hash`.

### 4.4 Neo4j entities and edges

**Bootstrap on first install** (per `harvester-agent-spec.md` §9.3, with extensions):

Entity types: `Technology`, `EconomicConstruct`, `MeasurementMethod`, `MeasurementProblem`, `StatisticalProgram`, `Agency`, `Researcher`, `Paper`, `Dataset`, `Benchmark`, `Finding`.

Edge types: `MEASURES`, `APPLIED_TO`, `FAILED_TO_CAPTURE`, `REPLACED_BY`, `ADMINISTERED_BY`, `PRODUCES`, `REGULATES`, `AUTHORED_BY`, `CITES`, `PROPOSES`, `CRITIQUES`, `EXTENDS`, `ANALOGOUS_TO`, `MEASUREMENT_LAG`, `PATTERN_REPEATS`, `PRECEDED_BY`, `CONTEMPORARY_WITH`, plus new edges for Findings: `DERIVED_FROM`, `MEASURES_CONSTRUCT`, `CITES_ROWS`, `EVIDENCE_FOR`, `EVIDENCE_AGAINST`, `CONTRADICTS`.

**Finding node shape:**
```cypher
(:Finding {
    label: "Ramp Mar 2026 paid-AI-vendor adoption = 50.4%",
    summary: "...",
    created_at: datetime(),
    created_by_run_id: 42
})-[:CITES_ROWS {pg_table: "harvest.ramp_index_observations",
                  pg_row_ids: [12345, 12346]}]->(:Dataset {name: "Ramp AI Index"})
```

Finding nodes do not duplicate the postgres value. They exist to make claims, contradictions, and evidence relationships legible in the graph. They are **not auto-generated** from rows — they're created by analysis passes (initially by Brock in narrative mode; eventually by a claudeclaw judgment job).

**Dataset node shape:**
```cypher
(:Dataset {
    name: "Ramp AI Index",
    provider: "Ramp",
    pg_table: "harvest.ramp_index_observations",
    pg_pk_column: "ramp_obs_id"
})-[:MEASURES_CONSTRUCT]->(:Construct {name: "paid_ai_vendor_adoption"})
```

Bootstrap script uses `MERGE` (idempotent) and stamps `bootstrap_version` property on each node so re-runs upgrade rather than duplicate.

---

## 5. Reproducibility / TEVV regime

Three layers, scaled to the kind of correctness each step can offer.

### 5.1 Deterministic layer (fetch → parse → ETL → postgres)

- **Golden samples**: `harvester/tests/fixtures/<source>/*.input.{json,html,pdf}` + `*.expected.{sql,parquet}`. Pytest re-runs `parse + to_rows`, demands bit-exact match. Regression = test failure, blocks deploy.
- **Schema migrations**: numbered, applied via `harvester migrate`, recorded in `harvest.schema_migrations`. ETL's `expected_schema_version` checked at runtime startup; mismatch is hard fail.
- **Count validation**: nightly job per source compares harvester ingest count vs. authoritative upstream count for the same query and time window. For Federal Register, this is the FR API search using the same union of `tier_1` + `tier_2` terms restricted to the prior 30 days; the upstream count comes from the API's `count` response field, the harvester count is `SELECT count(*) FROM harvest.federal_register_documents WHERE publication_date BETWEEN ...`. Diff > ±5% emails Brock.

### 5.2 Stochastic layer (LLM-assisted normalization, finding generation)

- Every stochastic write records into `harvest.stochastic_provenance` with `model_id`, `prompt_hash`, `params`, `confidence`, `reviewed`.
- `prompt_hash` = SHA of rendered prompt template + input. Reproduces the call exactly even if model behavior drifts.
- `reviewed=false` rows go to a review queue; claudeclaw weekly job processes them.
- Hard daily LLM-cost ceiling per source enforced in runner; overage halts and emails.

### 5.3 Run log (cross-cutting)

Every invocation writes one `harvest.run_log` row:
- `code_sha` from `git rev-parse HEAD` at invocation; `-dirty` suffix if working tree dirty (don't block — research workflows have uncommitted work).
- Every analytical row carries `created_by_run_id` FK. Full traceability: row → run → code SHA → schema migration SHA → raw bytes → upstream URL.

### 5.4 Validation cadence

| Check | Cadence | Mechanism |
|---|---|---|
| Golden-sample tests | every commit | pre-push hook |
| Count validation | nightly | launchd cron |
| Stochastic review | weekly | claudeclaw judgment job |
| Manifest integrity | weekly | launchd, samples 50 rows + verifies hash |

---

## 6. Concept-once-source-many: where dedup happens

Wintermute's epistemology: store concepts once, accumulate reinforcement via source-linkage edges, never duplicate. The harvester implements this at three layers of decreasing cost.

### Layer 1 — Identity dedup at fetch boundary (in MVP)

URL / DOI / content_hash matching against `harvest.fetched_items` and Wintermute's `seen.db`. Same NIST guidance arriving via FR + via NBER citation: record co-occurrence, don't re-fetch, don't re-stage.

### Layer 2 — Near-duplicate detection at staging boundary (POST-MVP)

Title-normalized + abstract cosine similarity ≥ 0.95. Catches NBER preprint → journal version, blog post that summarizes a paper we have. Requires pgvector lookup against existing corpus embeddings. Defer until extraction cost pressure justifies it.

### Layer 3 — Concept-level dedup at KG layer (existing Wintermute responsibility)

Extraction produces claims. Same claim from multiple papers → single `Finding`/`Concept` node with multiple `EVIDENCE_FOR` edges, not duplicate nodes. Maintenance jobs (`kg_ontology_maintenance`, `kg_prune`) periodically compact concept clusters. **Not the harvester's job.** Harvester's responsibility is to preserve raw + record rich provenance (title, authors, DOI, abstract, source_url, published_date) so downstream layers can do their work correctly.

---

## 7. MVP scope: Federal Register vertical slice

### 7.1 In MVP

1. Repo scaffolding: `measuring-ai-economy/harvester/` package, own uv-managed venv with `uv.lock` committed, `pyproject.toml`, `.gitignore` for `data/raw/`.
2. Postgres bootstrap migrations:
   - `001_harvest_init.sql` — operational + registry + metadata + stochastic_provenance + schema_migrations tables.
   - `002_federal_register.sql` — densely-typed `federal_register_documents` table.
3. Federal Register fetcher: `fetchers/federal_register.py`. Single-step `iter_payloads`. Rate-limited 1 req/sec. Writes raw JSON + manifest row. Source advisory lock.
4. Federal Register ETL: `etl/federal_register.py`. Pure `parse`, `to_rows`. Deterministic; no LLM. Golden samples for 4 documents: one rule, one EO, one notice, one proposed_rule.
5. Source-agnostic normalizer: emits markdown + frontmatter to `~/.wintermute/inbox/`.
6. CLI: `run`, `migrate`, `validate`, `status`.
7. Launchd wrapper: `~/.wintermute/scripts/jobs/harvest_federal_register.sh` + `com.wintermute.harvest-federal-register.plist`. Daily at 22:00 local.
8. Ontology bootstrap script (`harvester/ontology/bootstrap.py`) — creates Neo4j entities from spec §9.3 with `MERGE` + `bootstrap_version`.
9. TEVV: golden-sample pytest, count-validation nightly script comparing harvester ingest vs FR.gov search count (last 30 days), manifest-integrity weekly check.
10. Run-log + observability: `harvester status` outputs last 5 runs per source, queue depth, error count 24h, manifest row count, raw disk usage.

### 7.2 Tier coverage at MVP launch

`tier_1_current` queries: "artificial intelligence", "machine learning", "generative AI", "automated decision", "algorithmic", "AI risk management", "AI safety", "foundation model".

`tier_2_regulatory` queries: "Executive Order 14110", "Executive Order 14179", "OMB M-24-10", "NIST AI", "AI governance", "automated systems", "predictive analytics" AND "federal".

Tier 3 (statistical methodology) and tier 4 (historical) deferred to post-MVP backfill tasks with explicit pacing.

### 7.3 Out of MVP (deferred to follow-on cc_tasks)

- Semantic Scholar / OpenAlex / NBER fetchers
- BLS / BEA / Census / Fed HTML scrapers
- arXiv econ.GN integration
- Source discovery crawler (Addendum A4)
- Adaptive expansion (citation chains, author following, term discovery)
- Alternative data sources (Ramp, USPTO PatentsView, USASpending, Eurostat, OECD)
- Anchor finding distillation pipeline
- Crosswalks population (NAICS↔Ramp, O*NET↔SOC, CPC↔NAICS)
- LLM-assisted normalization for Cat-3/4 sources
- claudeclaw judgment job (`harvest_judgment.md`)
- Layer-2 near-duplicate detection (pgvector cosine on title+abstract)

### 7.4 Success criteria

- `harvester run federal_register --query="artificial intelligence" --limit=20` succeeds end-to-end.
- 20 rows in `harvest.federal_register_documents` with FKs intact.
- 20 markdown files in `~/.wintermute/inbox/` with proper frontmatter.
- Wintermute's existing `drain_inbox` job picks them up; they appear in `staging/`.
- Count-validation reports ingest vs. FR.gov-search within ±5%.
- Golden-sample tests pass.
- First production run tonight at 22:00 local (2026-05-11).
- Seven consecutive daily launchd runs with no manual intervention.

---

## 8. Adaptive expansion (pinned, deferred)

Three loops, all human-gated via `harvest.expansion_candidates`:

1. **Citation chain** — ingested papers with reference lists score unseen titles against seed keywords, write candidates to `expansion_candidates` with `parent_id`, depth, score, status='proposed'. Hard depth cap 3. Nothing fetched until weekly judgment job promotes `proposed → approved`.
2. **Author following** — authors appearing in 3+ high-scoring papers get candidate rows. Reviewed via `harvester expand --review-authors`.
3. **Term discovery** — deterministic noun-phrase extraction from high-scoring abstracts (no LLM in this loop). Terms in 5+ abstracts get candidate rows. Quarterly review.

Why human-gated: unbounded expansion = unbounded cost + drift. Honors spec's "log but don't fetch beyond depth 3" with real data structure instead of a YAML file.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| FR tier_3/tier_4 volume explosion | MVP runs tier_1 + tier_2 only on 60-day rolling window; historical backfill is a separate cc_task with explicit pacing |
| HTML scrapers brittle (Ramp/BLS/BEA/Fed) | Each scraper needs `last_known_good` sentinel selector that fails loudly on layout change; not in MVP |
| Inbox backpressure | Runner pauses if `len(inbox)` > 500 |
| LLM cost runaway | Hard daily ceiling in runner config; halts run on overage, emails Brock |
| Neo4j bootstrap non-idempotent | `MERGE` + `bootstrap_version` property |
| Silent ETL narrowing (your 2026-01-08 pattern) | Count-validation nightly; golden samples block deploy on regression |
| Concurrent launchd duplicate fetches | Postgres advisory lock per source_id |
| Working tree dirty during research-mode run | `code_sha` records `-dirty` suffix, doesn't block |

---

## 10. Open questions resolved

| Question | Answer |
|---|---|
| MVP launchd cadence for FR | Daily at 22:00 local |
| Tier coverage at MVP launch | tier_1 + tier_2_regulatory |
| Python environment | Own uv-managed venv under `measuring-ai-economy/harvester/`, `uv.lock` committed |
| Ontology bootstrap | Run `bootstrap.py` with §9.3 entities as written; curate later by editing seed YAML |

---

## 11. Implementation phase ordering (preview for writing-plans handoff)

The implementation plan will sequence approximately as follows (to be detailed by `writing-plans`):

1. Scaffolding + venv + pyproject + uv.lock + .gitignore + CI hooks.
2. Postgres migrations 001 + 002; `harvester migrate` working.
3. Manifest parquet format + raw archive directory structure.
4. Fetcher ABC + RawPayload dataclass + rate limiter + advisory lock helper.
5. Federal Register fetcher implementation.
6. ETL ABC + Loader; Federal Register ETL with golden samples.
7. Normalizer module + inbox writer.
8. CLI assembly (`run`, `migrate`, `validate`, `status`).
9. Launchd wrapper + plist + first-run dry-run validation.
10. Neo4j ontology bootstrap script + execution.
11. Count-validation nightly script + plist.
12. Manifest-integrity weekly script + plist.
13. First production run tonight at 22:00.
14. 7-day monitoring window before declaring MVP complete.

---

## 12. What this spec does NOT cover

- Wintermute's existing pipeline behavior (triage, staging, extraction, KG load).
- Concept-level deduplication and finding distillation (downstream of harvester, separate design).
- Crosswalk authoring methodology (separate research artifact under `docs/notes/`).
- Source discovery crawler (Addendum A4 — deferred to post-MVP cc_task).
- The five-Cs triage rubric (parent spec §8 recommendation: test as Wintermute triage upgrade, not harvester responsibility).
