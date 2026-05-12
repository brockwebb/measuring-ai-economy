"""Tests for LlmTriage (Claude subprocess mocked)."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harvester.triage.llm_triage import LlmTriage, TriageResult
from harvester.types import ParsedDoc, Row


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


@patch("harvester.triage.llm_triage.subprocess.run")
def test_triage_parses_claude_response(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "score": 0.72,
            "axes": {
                "stochastic_dynamics_info_geometry": 0.72,
                "canine_cognition_behavior": 0.0,
            },
            "reason": "Diffusion models hit the stochastic dynamics axis directly.",
        }),
        stderr="",
    )

    triage = LlmTriage(model_id="claude-sonnet-4-6", axes_yaml=AXES_PATH)
    result = triage.score(_make_parsed())

    assert isinstance(result, TriageResult)
    assert result.score == 0.72
    assert result.axes["stochastic_dynamics_info_geometry"] == 0.72
    assert "diffusion" in result.reason.lower()
    assert result.rubric_version
    assert result.model_id == "claude-sonnet-4-6"
    assert len(result.prompt_hash) == 64


@patch("harvester.triage.llm_triage.subprocess.run")
def test_triage_raises_on_invalid_json(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
    triage = LlmTriage(model_id="claude-sonnet-4-6", axes_yaml=AXES_PATH)
    with pytest.raises(RuntimeError, match="not JSON"):
        triage.score(_make_parsed())


@patch("harvester.triage.llm_triage.subprocess.run")
def test_triage_raises_on_nonzero_exit(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="claude failed")
    triage = LlmTriage(model_id="claude-sonnet-4-6", axes_yaml=AXES_PATH)
    with pytest.raises(RuntimeError, match="triage call failed"):
        triage.score(_make_parsed())


@patch("harvester.triage.llm_triage.subprocess.run")
def test_triage_clamps_score_to_unit_interval(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"score": 1.5, "axes": {}, "reason": "max relevance"}),
        stderr="",
    )
    triage = LlmTriage(model_id="claude-sonnet-4-6", axes_yaml=AXES_PATH)
    result = triage.score(_make_parsed())
    assert 0.0 <= result.score <= 1.0
