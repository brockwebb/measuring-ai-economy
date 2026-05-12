# Harvester

AI economy measurement harvester. Fetches documents from Federal Register, academic APIs, and alternative data sources; deposits normalized output into Wintermute's inbox for triage and KG ingest.

## Setup

```bash
cd harvester
uv sync
uv run harvester migrate
```

## Run

```bash
uv run harvester run federal_register --query="artificial intelligence" --limit=20
```

## Tests

```bash
uv run pytest
```

See `docs/superpowers/specs/2026-05-11-harvester-design.md` for design.
