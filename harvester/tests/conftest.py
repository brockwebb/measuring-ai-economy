"""Shared pytest fixtures."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from seldon import models


#: Fixture lock ids. Deliberately NOT the live lock's ids: a test that passes only because the live
#: lock happens to hold some id is a test of the live lock, not of the launcher (MODEL-001 Part C).
FIXTURE_IDS = {
    "fable": "claude-fable-9-1",
    "opus": "claude-opus-9-5",
    "sonnet": "claude-sonnet-9-5",
    "haiku": "claude-haiku-9-5",
}
FIXTURE_CLI_VERSION = "9.9.999"

#: The fake `claude`: records its argv and the four ANTHROPIC_DEFAULT_*_MODEL variables, then
#: prints one `--output-format json` envelope. It serves the `--model` it was asked for unless
#: `served.txt` beside it names another id, which is how a test plants a substitution. The reply
#: text is `reply.txt` beside it; `top.json`, when present, is merged into the envelope's top level
#: (the MCP fetcher reads its items from there). `modelUsage` carries a small haiku side call first,
#: the shape S-007 measured on the real CLI, so the receipt must pick the answering model.
_FAKE_CLI = r'''#!{python}
import json, os, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
keys = {env_keys!r}
with (here / "calls.jsonl").open("a") as f:
    f.write(json.dumps({{"argv": sys.argv, "env": {{k: os.environ.get(k) for k in keys}}}}) + "\n")
argv = sys.argv[1:]
requested = argv[argv.index("--model") + 1] if "--model" in argv else None
served_file = here / "served.txt"
served = served_file.read_text().strip() if served_file.exists() else requested
envelope = {{}}
top = here / "top.json"
if top.exists():
    envelope.update(json.loads(top.read_text()))
model_usage = {{"{side}": {{"inputTokens": 12, "outputTokens": 3}}}}
if served:
    model_usage[served] = {{"inputTokens": 400, "outputTokens": 57}}
envelope.update({{"type": "result", "is_error": False,
                  "result": (here / "reply.txt").read_text(),
                  "usage": {{"output_tokens": 57}}, "modelUsage": model_usage}})
print(json.dumps(envelope))
'''


class FakeCli:
    """Handle on the fake CLI a test drives: what it served, what it replied, what it was given."""

    def __init__(self, root: Path, home: Path) -> None:
        self.root = root
        self.home = home
        self.path = root / "claude"
        self.ids = dict(FIXTURE_IDS)
        self.reply('{"score": 0.7, "axes": {"stochastic_dynamics_info_geometry": 0.7}, '
                   '"reason": "fixture reply"}')

    def reply(self, text: str, top: dict | None = None) -> None:
        (self.root / "reply.txt").write_text(text)
        top_file = self.root / "top.json"
        if top is None:
            top_file.unlink(missing_ok=True)
        else:
            top_file.write_text(json.dumps(top))

    def serve(self, model_id: str) -> None:
        """Make the next calls report `model_id` as the answering model (a substitution)."""
        (self.root / "served.txt").write_text(model_id)

    def calls(self) -> list[dict]:
        log = self.root / "calls.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


@pytest.fixture
def seldon_models_home(tmp_path, monkeypatch) -> FakeCli:
    """`SELDON_MODELS_HOME` pointed at a tmp dir: a copy of seldon's registry and a fixture lock
    whose `cli.path` is the fake CLI. No test reads the live lock or execs a real CLI."""
    home = tmp_path / "seldon_models"
    home.mkdir()
    source = Path(models.__file__).resolve().parent.parent / "models" / models.REGISTRY_FILE
    shutil.copy(source, home / models.REGISTRY_FILE)

    cli_root = tmp_path / "fake_cli"
    cli_root.mkdir()
    cli = FakeCli(cli_root, home)
    cli.path.write_text(_FAKE_CLI.format(python=sys.executable,
                                         env_keys=sorted(models.FAMILY_ENV.values()),
                                         side=FIXTURE_IDS["haiku"]))
    cli.path.chmod(0o755)

    lock = {
        "schema": 1,
        "resolved_on": "2026-10-09",
        "resolved_at": "2026-10-09T00:00:00Z",
        "cli": {"version": FIXTURE_CLI_VERSION, "path": str(cli.path),
                "npm_package": "@anthropic-ai/claude-code"},
        "families": {fam: {"alias": fam, "model": mid} for fam, mid in FIXTURE_IDS.items()},
        "evidence": "fixture",
    }
    (home / models.LOCK_FILE).write_text(yaml.safe_dump(lock, sort_keys=False))
    monkeypatch.setenv(models.MODELS_HOME_ENV, str(home))
    return cli
