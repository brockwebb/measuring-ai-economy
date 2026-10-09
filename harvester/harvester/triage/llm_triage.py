"""LLM triage — Claude subprocess against research_axes.yaml.

Migrated from ~/.wintermute/tools/arxiv_llm_triage.py with two changes:
1. Uses Claude via subprocess instead of GPT via OpenAI HTTP API.
2. Returns structured TriageResult instead of mutating frontmatter.

Model selection (seldon AD-035, MODEL-001): the scorer is built with a registry ROLE, never a model
id. The role resolves through `seldon.models` to the lock's id and CLI once, at construction, and
every call execs that CLI with `--model <id>`, the role's declared `--effort` (seldon AD-036-R8)
and the lock's env block (harvester.model_launch). Each result carries the served-model receipt,
effort included; a substituted model raises
`seldon.models.ModelSubstituted` and the score is not returned.

The runner is responsible for persisting the result to harvest.triage_results.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from harvester.model_launch import ResponseNotJson, launch_spec, receipt_for, run_cli
from harvester.triage.prompts import build_triage_prompt
from harvester.types import ParsedDoc


#: The registry role triage runs under when a config names none (seldon models/registry.yaml
#: `triage`, created for this harvester). A role, not a model id (AD-035 R4).
DEFAULT_TRIAGE_ROLE = "triage"
#: Seconds one triage CLI call may take before it is abandoned.
TRIAGE_TIMEOUT_S = 120


@dataclass(frozen=True)
class TriageResult:
    score: float
    axes: dict[str, float]
    reason: str
    rubric_version: str
    model_id: str
    prompt_hash: str
    #: AD-035 R6: {requested, served, side_models, ok, effort} for the call that produced this
    #: score; `effort` is the level the launch passed (AD-036-R8).
    model_receipt: dict


class LlmTriage:
    def __init__(self, *, role: str, axes_yaml: Path) -> None:
        self._role = role
        self._spec = launch_spec(role)
        self._axes_yaml_path = axes_yaml
        self._axes_yaml_text = axes_yaml.read_text()
        loaded = yaml.safe_load(self._axes_yaml_text) or {}
        self._rubric_version = str(loaded.get("rubric_version", "0.0.0"))

    def score(self, parsed: ParsedDoc) -> TriageResult:
        title = parsed.title or ""
        abstract = (parsed.metadata or {}).get("abstract") or ""
        prompt = build_triage_prompt(
            title=title,
            abstract=abstract,
            axes_yaml_text=self._axes_yaml_text,
        )
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        proc = run_cli(self._spec, ["-p", prompt, "--output-format", "json"],
                       timeout=TRIAGE_TIMEOUT_S)
        if proc.returncode != 0:
            raise RuntimeError(f"triage call failed (exit {proc.returncode}): {proc.stderr.strip()}")

        try:
            # Raises ModelSubstituted (AD-035 R6) before any of the reply is read.
            response, receipt = receipt_for(self._spec, proc.stdout)
        except ResponseNotJson as e:
            raise RuntimeError(f"triage {e}") from e

        # Claude CLI wraps tool output; the actual structured response may be
        # nested under "result" or "content". Try common shapes.
        body = response
        if isinstance(response, dict) and "result" in response and isinstance(response["result"], (dict, str)):
            body = response["result"]
            if isinstance(body, str):
                # Strip markdown code fences (```json ... ``` or ``` ... ```)
                stripped = body.strip()
                if stripped.startswith("```"):
                    lines = stripped.splitlines()
                    # drop first line (```json or ```) and last line (```)
                    inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
                    stripped = inner.strip()
                try:
                    body = json.loads(stripped)
                except json.JSONDecodeError:
                    pass

        if not isinstance(body, dict):
            raise RuntimeError(f"triage response shape unexpected: {response!r:.200}")

        score = float(body.get("score", 0.0))
        score = max(0.0, min(1.0, score))
        axes = body.get("axes") or {}
        axes = {k: float(v) for k, v in axes.items() if isinstance(v, (int, float))}
        reason = str(body.get("reason", ""))[:1000]

        return TriageResult(
            score=score,
            axes=axes,
            reason=reason,
            rubric_version=self._rubric_version,
            model_id=receipt["served"],
            prompt_hash=prompt_hash,
            model_receipt=receipt,
        )
