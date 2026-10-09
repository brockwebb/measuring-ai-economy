"""Launching the Claude CLI under seldon AD-035: role, lock, receipt.

Every Claude CLI call this harvester makes goes through here (the triage scorer and the MCP
fetcher base). Model selection is not this repository's decision: the operator's registry and
lock in seldon (`models/registry.yaml`, `models/models.lock.yaml`) are, read through
`seldon.models`, the one accessor on this machine (AD-035 R1).

- A config names a ROLE (R4). :func:`config_role` refuses a model id, a family alias, or the
  pre-AD-035 key that named a model, so a stale config fails loudly instead of being read.
- :func:`launch_spec` resolves the role once, when the launcher is built: a run keeps the lock
  entry it started with to the end (R7).
- :func:`run_cli` execs the lock's CLI (never `claude` on PATH), passes `--model <id>` and
  `switchModelsOnFlag: false` (R3, R6), and lays the lock's four `ANTHROPIC_DEFAULT_*_MODEL` ids
  over the child's environment so CLI background calls follow the lock too (R3).
- :func:`receipt_for` returns the envelope and the receipt `{requested, served, side_models, ok}`
  (the caller stores it beside the call's other facts) and raises `seldon.models.ModelSubstituted` (`model_substituted`) when the answering model is
  not the requested one; the caller's unit stops and its output is not used (R6).

The harvester venv carries seldon as an editable install (see harvester/README.md, Setup).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from seldon import models


class ConfigNamesModel(ValueError):
    """A config value names a model (id or alias) where AD-035 R4 requires a registry role."""


def config_role(cfg: dict, *, role_key: str, legacy_key: str, default: str) -> str:
    """The registry role a config block names under `role_key`, else `default`.

    Refuses `legacy_key` (the key that named a model before AD-035) whatever its value, and a
    `role_key` value that is a model id or a family alias. Whether the role exists in the
    registry is checked when the launcher resolves it (`seldon.models.UnknownRole`).
    """
    if legacy_key in cfg:
        raise ConfigNamesModel(
            f"config key {legacy_key!r} ({cfg[legacy_key]!r}) named a model; configs name a "
            f"registry role under {role_key!r} instead (seldon AD-035 R4)")
    role = str(cfg.get(role_key, default))
    if models.MODEL_ID_RE.search(role) or role in models.ALIASES:
        raise ConfigNamesModel(
            f"{role_key}: {role!r} is a model, not a role; name a role from seldon "
            f"models/registry.yaml (seldon AD-035 R4)")
    return role


def launch_spec(role: str) -> dict:
    """`seldon.models.launch_spec(role)`, plus a check that the lock's CLI exists to be exec'd."""
    spec = models.launch_spec(role)
    if not Path(spec["cli_path"]).is_file():
        raise models.ModelsError(
            f"the lock's CLI {spec['cli_path']} (version {spec['cli_version']}) does not exist; "
            f"run `seldon models refresh` (seldon AD-035 R2)")
    return spec


def run_cli(spec: dict, cli_args: list[str], *, timeout: int) -> subprocess.CompletedProcess:
    """Exec the lock's CLI with `cli_args` then the spec's `--model`/`--settings` args."""
    cmd = [spec["cli_path"], *cli_args, *spec["args"]]
    env = {**os.environ, **spec["env"]}
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


class ResponseNotJson(RuntimeError):
    """The CLI's stdout holds no JSON envelope at all."""


def receipt_for(spec: dict, stdout: str) -> tuple[dict, dict]:
    """`(envelope, receipt)` for one call.

    Raises :class:`ResponseNotJson` when stdout holds no JSON object, and `ModelSubstituted` when
    the served model is not the requested one, including an envelope with no `modelUsage`: a
    reply that cannot show which model answered is not used.
    """
    envelope = models.last_result_envelope(stdout)
    if envelope is None:
        raise ResponseNotJson(f"response not JSON; stdout: {(stdout or '')[:200]}")
    receipt = models.check_receipt(spec["model"], envelope)
    return envelope, receipt
