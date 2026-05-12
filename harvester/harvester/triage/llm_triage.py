"""LLM triage — Claude subprocess against research_axes.yaml.

Migrated from ~/.wintermute/tools/arxiv_llm_triage.py with two changes:
1. Uses Claude via subprocess instead of GPT via OpenAI HTTP API.
2. Returns structured TriageResult instead of mutating frontmatter.

The runner is responsible for persisting the result to harvest.triage_results.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from harvester.triage.prompts import build_triage_prompt
from harvester.types import ParsedDoc


_CLAUDE_BIN = os.environ.get("HARVESTER_CLAUDE_BIN", "claude")


@dataclass(frozen=True)
class TriageResult:
    score: float
    axes: dict[str, float]
    reason: str
    rubric_version: str
    model_id: str
    prompt_hash: str


class LlmTriage:
    def __init__(self, *, model_id: str, axes_yaml: Path) -> None:
        self._model_id = model_id
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

        proc = subprocess.run(
            [_CLAUDE_BIN, "-p", prompt, "--output-format", "json",
             "--model", self._model_id],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"triage call failed (exit {proc.returncode}): {proc.stderr.strip()}")

        try:
            response = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"triage response not JSON: {e}; stdout: {proc.stdout[:200]}")

        # Claude CLI wraps tool output; the actual structured response may be
        # nested under "result" or "content". Try common shapes.
        body = response
        if isinstance(response, dict) and "result" in response and isinstance(response["result"], (dict, str)):
            body = response["result"]
            if isinstance(body, str):
                try:
                    body = json.loads(body)
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
            model_id=self._model_id,
            prompt_hash=prompt_hash,
        )
