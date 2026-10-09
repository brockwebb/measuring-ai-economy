# Harvester

AI economy measurement harvester. Fetches documents from Federal Register, academic APIs, and alternative data sources; deposits normalized output into Wintermute's inbox for triage and KG ingest.

## Setup

```bash
cd harvester
uv sync
uv pip install --python .venv/bin/python --no-deps --offline -e /Users/brock/GitHub/seldon
uv run harvester migrate
```

The second line installs seldon (editable, no dependencies, no network) so the harvester can read
the machine's model registry and lock through `seldon.models` (seldon AD-035, MODEL-001). Triage
and the MCP fetcher name a registry ROLE (`triage_role: triage` in `sources.yaml`); the lock in
`/Users/brock/GitHub/seldon/models/models.lock.yaml` names the model id and the Claude CLI they
exec, and every call records a served-model receipt (`model_receipt`, migration 012). A config
that names a model id or carries the old `triage_model` key is refused.

seldon is not in `pyproject.toml`: it is a local checkout, and declaring it would make `uv lock`
resolve seldon's whole dependency tree for a module that needs only PyYAML. A plain `uv sync`
removes packages the lockfile does not list, so re-run the install line after one. The scheduled
jobs run `uv sync --inexact` (`~/.wintermute/scripts/jobs/_lib.sh`), which keeps it.

## Run

```bash
uv run harvester run federal_register --query="artificial intelligence" --limit=20
```

## Tests

```bash
uv run pytest
```

See `docs/superpowers/specs/2026-05-11-harvester-design.md` for design.
