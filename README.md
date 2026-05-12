# Measuring AI Economy

Research project on measuring AI's economic impact — federal statistics, historical IT/technology measurement literature, and current AI policy/regulation.

## What's here

- **`harvester/`** — Python package that fetches, normalizes, and stages documents for downstream knowledge-graph ingestion. Multi-backend fetcher hierarchy (HTTP API, RSS, MCP, crawl4ai, Atom), per-source ETL with golden-sample tests, LLM-driven triage against a research-axes rubric, MUI scout (discovers llms.txt / robots.txt / sitemap.xml / OpenAPI on first contact), Postgres analytical schema, run-log with stochastic provenance.
- **`docs/design/`** — original harvester agent spec + addendum on alternative data sources and cross-dataset normalization.
- **`docs/notes/`** — ontology stack (NAICS/NAPCS/SOC/O\*NET federal spine + ISIC/CPC/ISCO international layer + DCAT/SKOS/PROV-O), ai-measurement research map, sfv-connection notes.
- **`docs/superpowers/specs/`** — design specs for the harvester MVP + evolution (foundations, migration, self-improvement).
- **`docs/superpowers/plans/`** — phased implementation plans (executed via subagent-driven development).
- **`data/manifests/raw_manifest.parquet`** — git-tracked checksum manifest of every raw artifact fetched. Raw bytes themselves are gitignored under `data/raw/`.
- **`ops/launchd/`** — copies of the macOS launchd plists + wrapper scripts that schedule the harvester (kept here for reproducibility).
- **`cc_tasks/`** — scoping notes for follow-on work.

## Status (as of 2026-05-12)

- MVP shipped: Federal Register harvester operational, ~250 docs harvested, three launchd jobs (daily harvest + nightly count validation + weekly manifest integrity).
- Phase 1 (Foundations): MUI scout + multi-backend Fetcher hierarchy merged. 63 tests.
- Phase 2 (arxiv): ArxivFetcher + ArxivETL + LlmTriage merged. 78 tests. Currently in the 3-day parallel-run verification window vs. the legacy `~/.wintermute/scripts/search_papers.py`. Cutover follows.
- Phase 3 (self-improvement): designed, not yet planned in detail. Citation chain expansion + cross-source co-occurrence + saturation monitor + failure pattern classifier.

## Quickstart

```bash
cd harvester
uv sync --extra dev
uv run harvester migrate
uv run harvester scout federal_register --base-url https://www.federalregister.gov
uv run harvester run federal_register --query="artificial intelligence" --limit=5
uv run harvester status
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).

## Author

Brock Webb. Built collaboratively with Claude.
