"""Tests for LlmTriage.

MODEL-001 (seldon AD-035): these tests used to patch `subprocess.run` inside llm_triage and build
the scorer with `model_id="claude-sonnet-4-6"`. The scorer now takes a registry role and execs the
lock's CLI through harvester.model_launch, so they run against `seldon_models_home` (a fixture lock
and a fake CLI, tests/conftest.py) and assert the fixture lock's id, never a typed one.
"""

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from harvester import model_launch
from harvester.triage.llm_triage import LlmTriage, TriageResult
from harvester.types import ParsedDoc, Row
from tests.conftest import FIXTURE_IDS


AXES_PATH = Path(__file__).parent.parent / "harvester" / "triage" / "research_axes.yaml"


def _make_parsed(title="Test paper on diffusion models",
                 abstract="We study diffusion models in latent space.") -> ParsedDoc:
    return ParsedDoc(
        title=title,
        source_url="https://example.com/paper",
        published_date=date(2026, 5, 12),
        rows=[Row(target_table="harvest.document_metadata", data={"title": title})],
        metadata={"abstract": abstract, "document_type": "arxiv_paper"},
    )


def _stdout(monkeypatch, *, returncode=0, stdout="", stderr=""):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(model_launch.subprocess, "run", fake_run)


def test_triage_parses_claude_envelope_result_as_string(seldon_models_home):
    """Production claude CLI emits {"type":"result", "result":"<JSON STRING>"}.
    We must unwrap that and parse the inner JSON."""
    seldon_models_home.reply(json.dumps({
        "score": 0.81,
        "axes": {"stochastic_dynamics_info_geometry": 0.81},
        "reason": "Inner reason.",
    }))
    triage = LlmTriage(role="triage", axes_yaml=AXES_PATH)
    result = triage.score(_make_parsed())
    assert result.score == 0.81
    assert result.axes["stochastic_dynamics_info_geometry"] == 0.81
    assert "inner reason" in result.reason.lower()


def test_triage_parses_fenced_result(seldon_models_home):
    seldon_models_home.reply("```json\n" + json.dumps({
        "score": 0.72,
        "axes": {"stochastic_dynamics_info_geometry": 0.72, "canine_cognition_behavior": 0.0},
        "reason": "Diffusion models hit the stochastic dynamics axis directly.",
    }) + "\n```")

    triage = LlmTriage(role="triage", axes_yaml=AXES_PATH)
    result = triage.score(_make_parsed())

    assert isinstance(result, TriageResult)
    assert result.score == 0.72
    assert result.axes["stochastic_dynamics_info_geometry"] == 0.72
    assert "diffusion" in result.reason.lower()
    assert result.rubric_version
    assert result.model_id == FIXTURE_IDS["sonnet"]
    assert result.model_receipt["ok"] is True
    assert len(result.prompt_hash) == 64


def test_triage_raises_on_invalid_json(seldon_models_home, monkeypatch):
    _stdout(monkeypatch, stdout="not json")
    triage = LlmTriage(role="triage", axes_yaml=AXES_PATH)
    with pytest.raises(RuntimeError, match="not JSON"):
        triage.score(_make_parsed())


def test_triage_raises_on_nonzero_exit(seldon_models_home, monkeypatch):
    _stdout(monkeypatch, returncode=1, stderr="claude failed")
    triage = LlmTriage(role="triage", axes_yaml=AXES_PATH)
    with pytest.raises(RuntimeError, match="triage call failed"):
        triage.score(_make_parsed())


def test_triage_clamps_score_to_unit_interval(seldon_models_home):
    seldon_models_home.reply(json.dumps({"score": 1.5, "axes": {}, "reason": "max relevance"}))
    triage = LlmTriage(role="triage", axes_yaml=AXES_PATH)
    result = triage.score(_make_parsed())
    assert 0.0 <= result.score <= 1.0
