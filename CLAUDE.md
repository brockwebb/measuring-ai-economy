# Measuring AI Economy

Research project measuring the AI economy. This repo carries the use-case-specific ETL/harvester code: HTTP and Crawl4ai fetchers, ETL into PostgreSQL `harvest.*` tables, triage, citation-chain expansion, calibration dashboard. Sources currently online: arxiv, zenodo, federal_register, semantic_scholar, url_drain.

## Sister Projects

**Wintermute** (`~/.wintermute/`) is the home for the knowledge graph and the broader knowledge infrastructure (ontology, extraction, Neo4j `wintermute-intake`, calibration review, claudeclaw daemon, persistent memory). All projects feed Wintermute's KG; Wintermute owns the data.

This project does **not** have its own Neo4j or ontology. If a task touches:

- KG ingestion (Cypher, MERGE, node/relationship creation)
- Ontology design (tags, taxonomy, ConceptFamily layer)
- Extraction (Gemini/Claude over staged content)
- Graph analytics (PageRank, community detection, prune)
- AGORA / governance-doc datasets

…it belongs in Wintermute, not here. The boundary was redrawn 2026-05-13 after the AGORA dataset task drifted into this repo.

## Scope here

- `harvester/` — Python package: fetchers, ETL, Runner, CLI (`harvester run <source>`, `harvester drain-url <URL>`, `harvester calibration`, `harvester chain-references`, `harvester expand-citations`).
- `harvester/harvester/schemas/` — PostgreSQL migrations. Migration 009 is current head.
- `harvester/harvester/config/sources.yaml` — registered sources + tier_1/tier_2 terms.
- `docs/superpowers/plans/` — completed implementation plans (calibration-judgment, zenodo-migration, url-drain-migration, etc.).
- `docs/superpowers/notes/` — operational notes (soak windows, cutovers).
- `ops/` — deployment artifacts (launchd plists, source-specific fetch scripts that aren't generic harvester fetchers).
- `cc_tasks/` — project-bootstrap-level tasks. **Not** for KG/ontology work (those go to `~/.wintermute/cc_tasks/`).

## Cron / launchd jobs

Defined under `~/.wintermute/scripts/jobs/` (wrappers source `_lib.sh`) and `~/Library/LaunchAgents/com.wintermute.harvest-*.plist`. Each calls `uv run harvester run <source>` after `uv sync --inexact`. Sources currently scheduled: arxiv, federal_register, zenodo. URL drain is on-demand only (called from `~/.wintermute/scripts/drain_with_notes.sh`).

## Conventions

- Branch per feature: `feat/<short-name>`. Merge with `--no-ff` after green tests.
- TDD with `pytest -p no:randomly`; commit format `feat(harvester): ...` with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.
- Per-source plans live in `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.
- New sources mirror the Phase 2 (arxiv) pattern: migration → fetcher → ETL → sources.yaml + CLI → launchd → soak window → cutover.
