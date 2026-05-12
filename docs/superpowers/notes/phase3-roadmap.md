# Phase 3 Roadmap

**Parent spec:** `docs/superpowers/specs/2026-05-11-harvester-evolution-design.md` §7 Phase 3

Phase 3 decomposes into 5 independent sub-plans. Each ships on its own; later sub-plans depend on earlier ones only through table existence + Phase 1/2 substrate. Per the brainstorming skill's "If the spec covers multiple independent subsystems... help decompose into sub-projects."

## Sub-plans

### 3.1 — Co-occurrence + Saturation + Failure classifier *(planned next)*

**Goal:** complete the observability + cross-source-learning triangle the harvester has been missing. The data structures already exist (migration 004 created `harvest.co_sources`, `harvest.failure_patterns`, `harvest.saturation` view). This sub-plan populates them at runtime and surfaces them via nightly checks.

**Scope:**
- Runner co-occurrence hook: when an item is already-seen under a *different* `source_id`, record to `harvest.co_sources` before skipping.
- Runner failure-classification hook: post-run, cluster failed `fetched_items` rows by normalized error signature into `harvest.failure_patterns`.
- `harvester check-saturation` CLI: reads `harvest.saturation` view, emails on deposit_ratio < 0.05 for 7+ days.
- Launchd: `harvest_saturation_check` (nightly).
- `harvester check-failures` CLI: surfaces failure_patterns crossing the 10-occurrence threshold.

**Depends on:** Phase 1 substrate (Runner, RawArchive) + migration 004 (already shipped).

**Approx tasks:** ~8

**Acceptance:** at least one co-occurrence row written cross-source (e.g., same arxiv paper hits both FR citation context and arxiv direct), at least one nightly saturation check fires cleanly, at least one failure pattern alerted or "no patterns yet."

---

### 3.2 — SemanticScholarFetcher + CitationChain machinery

**Goal:** the canonical adaptive loop — papers cite other papers, the harvester follows those citations selectively.

**Scope:**
- `SemanticScholarFetcher` (inherits `HttpApiFetcher`) — paginates `https://api.semanticscholar.org/graph/v1/`. Uses free API key. Outputs typed rows to a new analytical table.
- Migration 006: `harvest.semantic_scholar_papers` (mirror of arxiv_papers shape).
- `harvester.improvement.citation_chain.CitationChain` class:
  - `enqueue(parsed, parent_run_id)` — sync, writes proposed candidates to `harvest.expansion_candidates` (table from migration 004).
  - `process_pending(max_batch=100)` — verifies via Semantic Scholar, scores against research_axes, promotes to approved/rejected.
- Runner post-ETL hook: enqueue candidates when `parsed.metadata.doi` is set + source is in citation-chain whitelist.
- `harvester expand-citations` CLI: drives `process_pending`.
- Launchd: `harvest_citation_expand` (weekly Sundays 02:30).

**Depends on:** 3.1 failure classifier (citation-chain failures get clustered like everything else), Phase 1 HttpApiFetcher base, Phase 2 triage rubric (citation scoring reuses LlmTriage axes).

**Approx tasks:** ~12

**Acceptance:** at least one expansion candidate proposed by the runtime hook, weekly batch processor approves at least one and rejects at least one, approved candidate's URL appears in a subsequent arxiv harvest as a fetch (not just as an expansion proposal).

---

### 3.3 — Remaining source migrations (zenodo + ssrn + url_drain)

**Goal:** sunset the rest of `~/.wintermute/scripts/search_papers.py` + `drain_url_c4a.py`. Volume scale-out using the patterns proven in Phase 2.

**Scope:** Each is a Phase-2-shaped sub-sub-plan:
- ZenodoFetcher (REST API; possibly HttpApiFetcher subclass)
- SsrnFetcher (HTML-heavy; Crawl4aiFetcher subclass — requires `uv sync --extra html` on the production host)
- UrlDrainFetcher (single-URL via Crawl4aiFetcher; pairs with a new CLI `harvester drain-url`)
- For each: ETL, golden samples, sources.yaml entry, 3-day parallel verification window, atomic cutover, 7-day stability monitor.

**Depends on:** Phase 1 Crawl4aiFetcher base + `[html]` extra dependency installed on production. Each sub-sub-plan is independent of the others (zenodo can ship before ssrn).

**Approx tasks:** ~25 (≈ 3 × Phase 2 size) — split into 3 separate writing-plans outputs.

**Acceptance:** each source: count match ≥95% vs legacy over 3-day window, no failed runs over 7-day post-cutover window.

---

### 3.4 — New sources via MCP (pubmed)

**Goal:** prove the McpFetcher pattern with a real MCP server. Pubmed MCP is already installed in Brock's environment.

**Scope:**
- PubMedFetcher (inherits `McpFetcher`) — calls `mcp__claude_ai_PubMed__search_articles`.
- PubMedETL + golden samples.
- Migration 007: `harvest.pubmed_papers` analytical table.
- Triage enabled (medical-relevance axes may need additions to `research_axes.yaml` — bump rubric_version).
- Launchd entry.

**Depends on:** Phase 1 McpFetcher base. No prior pubmed pipeline → no migration step, just a new source.

**Approx tasks:** ~8

**Acceptance:** end-to-end run produces ≥ 10 pubmed papers in `harvest.pubmed_papers` with triage scores, ≥ 7 daily runs clean.

---

### 3.5 — claudeclaw judgment job + calibration dashboard CLI

**Goal:** close the human-in-loop review cycle. Brock-or-claudeclaw periodically reviews queues, calibration drifts, expansion proposals — using a unified surface.

**Scope:**
- `~/.wintermute/.claude/claudeclaw/jobs/harvest_judgment.md` — weekly. Reviews: proposed expansion candidates (3.2), unreviewed stochastic_provenance rows (Phase 2 triage), failure_patterns crossing alert threshold (3.1), saturation alerts (3.1). Promotes/rejects via SQL updates; emails a summary digest.
- `harvester calibration --window 30d` CLI: outputs Markdown dashboard from `harvest.run_log` + `harvest.triage_results` + `harvest.saturation` + `harvest.failure_patterns` + `harvest.co_occurrence` + `harvest.expansion_candidates`. Used by both human + the claudeclaw job as the data source.
- Optional: `harvester.improvement.rubric_stability` — weekly 20-doc re-score check (flagged in design spec §8.2).

**Depends on:** 3.1 (failure_patterns populated) + 3.2 (expansion_candidates populated). claudeclaw infrastructure already in production.

**Approx tasks:** ~6

**Acceptance:** one weekly claudeclaw judgment run produces a summary email, calibration CLI renders all sections without error, at least one expansion candidate or stochastic_provenance row reviewed via the digest.

---

## Recommended order

```
3.1  (Co-occurrence + Saturation + Failure)            ← next
  │
  ├─ 3.2  (SemanticScholarFetcher + CitationChain)
  │   │
  │   └─ 3.5  (claudeclaw judgment + calibration CLI)
  │
  └─ 3.4  (PubMed via MCP)                              (parallel-able with 3.2)

3.3  (zenodo + ssrn + url_drain migrations)             (parallel-able with everything;
                                                         independent of 3.1/3.2/3.4/3.5)
```

**Rationale for 3.1 first:** smallest scope, completes observability, unblocks 3.2's failure clustering, gives the harvester actual self-improvement signal before adding new sources.

**3.5 must follow 3.2:** judgment job has nothing to review until 3.2 fills the expansion candidates table.

**3.3 can ship anytime:** independent path. Could even be done in parallel sessions while the learning machinery is being built.

## Out of Phase 3 entirely (deferred to Phase 4 or later)

From the evolution spec §7 "out of all three phases":
- Author following loop (#3 from §8 list) — needs more data accumulation first
- Term discovery — needs NLP infra (Spacy/YAKE), separate dependency review
- Score-driven query reordering — needs feedback signal accumulation
- Rubric versioning batch re-evaluation — needs rubric stability + a version-bump trigger
- Concrete implementations for OAI-PMH / DCAT / BulkDownload fetchers (ABCs only as of Phase 1)
- Discovery Layer activation logic — saturation alerts trigger it; the layer itself is its own design

These get their own roadmap when Phase 3 is complete and the saturation signal indicates we're ready.
