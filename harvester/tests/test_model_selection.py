"""AD-035 (seldon) at the harvester's Claude CLI launchers: role, lock, receipt (MODEL-001 Part C).

Every test runs against `seldon_models_home` (tests/conftest.py): a copy of seldon's registry, a
fixture lock with ids that are not the live lock's, and a fake CLI that records what it was given.
No test reads the live lock or makes a model call.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from seldon import models

from harvester.fetchers.mcp_base import McpFetcher
from harvester.manifest import RawArchive
from harvester.model_launch import ConfigNamesModel, config_role
from harvester.triage.llm_triage import DEFAULT_TRIAGE_ROLE, LlmTriage
from harvester.types import ParsedDoc, RateLimit, Row
from tests.conftest import FIXTURE_IDS

AXES_PATH = Path(__file__).parent.parent / "harvester" / "triage" / "research_axes.yaml"
SOURCES_PATH = Path(__file__).parent.parent / "harvester" / "config" / "sources.yaml"
SETTINGS = {"switchModelsOnFlag": False}


def _parsed() -> ParsedDoc:
    return ParsedDoc(
        title="Diffusion models in latent space",
        source_url="https://example.com/p",
        published_date=date(2026, 10, 9),
        rows=[Row(target_table="harvest.document_metadata", data={"title": "t"})],
        metadata={"abstract": "We study diffusion."},
    )


def _flag(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


# ---------------------------------------------------------------------- triage launcher (R3)

def test_triage_execs_lock_cli_with_lock_model_settings_and_env(seldon_models_home):
    cli = seldon_models_home
    LlmTriage(role="triage", axes_yaml=AXES_PATH).score(_parsed())

    [call] = cli.calls()
    argv = call["argv"]
    assert argv[0] == str(cli.path), "exec path must be the lock's CLI, never PATH claude"
    assert _flag(argv, "--model") == FIXTURE_IDS["sonnet"]
    assert json.loads(_flag(argv, "--settings")) == SETTINGS
    assert _flag(argv, "--output-format") == "json"
    # AD-036-R8: the role's declared effort, on the flag and in the env the CLI's background
    # calls read.
    assert _flag(argv, "--effort") == cli.effort("triage")
    assert call["env"] == {
        "ANTHROPIC_DEFAULT_OPUS_MODEL": FIXTURE_IDS["opus"],
        "ANTHROPIC_DEFAULT_SONNET_MODEL": FIXTURE_IDS["sonnet"],
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": FIXTURE_IDS["haiku"],
        "ANTHROPIC_DEFAULT_FABLE_MODEL": FIXTURE_IDS["fable"],
        models.EFFORT_ENV: cli.effort("triage"),
    }


def test_triage_records_receipt_naming_served_and_side_models(seldon_models_home):
    result = LlmTriage(role="triage", axes_yaml=AXES_PATH).score(_parsed())

    assert result.model_id == FIXTURE_IDS["sonnet"]
    assert result.model_receipt == {
        "requested": FIXTURE_IDS["sonnet"],
        "served": FIXTURE_IDS["sonnet"],
        "side_models": [FIXTURE_IDS["haiku"]],
        "ok": True,
        "effort": seldon_models_home.effort("triage"),
    }
    assert result.score == pytest.approx(0.7)


def test_triage_ignores_path_override_of_cli(seldon_models_home, monkeypatch, tmp_path):
    """HARVESTER_CLAUDE_BIN used to pick the binary; under R3 only the lock does."""
    monkeypatch.setenv("HARVESTER_CLAUDE_BIN", str(tmp_path / "not-a-cli"))
    LlmTriage(role="triage", axes_yaml=AXES_PATH).score(_parsed())
    assert seldon_models_home.calls()[0]["argv"][0] == str(seldon_models_home.path)


# ---------------------------------------------------------------------- the receipt (R6)

def test_triage_substituted_model_stops_the_unit(seldon_models_home):
    seldon_models_home.serve("claude-sonnet-1-0")
    triage = LlmTriage(role="triage", axes_yaml=AXES_PATH)

    with pytest.raises(models.ModelSubstituted) as exc:
        triage.score(_parsed())

    assert exc.value.reason == "model_substituted"
    assert exc.value.receipt["requested"] == FIXTURE_IDS["sonnet"]
    assert exc.value.receipt["served"] == "claude-sonnet-1-0"
    assert exc.value.receipt["ok"] is False
    assert exc.value.receipt["effort"] == seldon_models_home.effort("triage")


@pytest.mark.parametrize("strip", ["effort", "args", "env"])
def test_seldon_without_declared_effort_is_refused(seldon_models_home, monkeypatch, strip):
    """seldon is an unpinned editable install; a checkout older than AD-036-R8 returns a spec with
    no effort, and its launches would run at the served model's own default unrecorded."""
    real = models.launch_spec

    def old_seldon(role):
        spec = real(role)
        if strip == "effort":
            spec["effort"] = None
        elif strip == "args":
            spec["args"] = spec["args"][:-2]
        else:
            spec["env"].pop(models.EFFORT_ENV)
        return spec

    monkeypatch.setattr(models, "launch_spec", old_seldon)
    with pytest.raises(models.ModelsError, match="AD-036-R8"):
        LlmTriage(role="triage", axes_yaml=AXES_PATH)
    assert seldon_models_home.calls() == []


def test_triage_envelope_without_model_usage_is_refused(seldon_models_home, monkeypatch):
    """A reply that cannot show which model answered is not used (R6)."""
    import subprocess

    from harvester import model_launch

    def no_usage(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(
            {"type": "result", "result": '{"score": 0.9, "axes": {}, "reason": "r"}'}), stderr="")

    monkeypatch.setattr(model_launch.subprocess, "run", no_usage)
    with pytest.raises(models.ModelSubstituted):
        LlmTriage(role="triage", axes_yaml=AXES_PATH).score(_parsed())


# ---------------------------------------------------------------------- configs name roles (R4)

def test_config_default_is_the_triage_role():
    assert config_role({}, role_key="triage_role", legacy_key="triage_model",
                       default=DEFAULT_TRIAGE_ROLE) == "triage"
    assert config_role({"triage_role": "triage"}, role_key="triage_role",
                       legacy_key="triage_model", default=DEFAULT_TRIAGE_ROLE) == "triage"


@pytest.mark.parametrize("cfg", [
    {"triage_model": "claude-sonnet-4-6"},
    {"triage_model": "triage"},
    {"triage_role": "claude-sonnet-4-6"},
    {"triage_role": "sonnet"},
])
def test_config_naming_a_model_is_refused(cfg):
    with pytest.raises(ConfigNamesModel, match="AD-035"):
        config_role(cfg, role_key="triage_role", legacy_key="triage_model",
                    default=DEFAULT_TRIAGE_ROLE)


def test_shipped_sources_name_roles_not_models(seldon_models_home):
    cfg = yaml.safe_load(SOURCES_PATH.read_text())
    text = SOURCES_PATH.read_text()
    assert "triage_model" not in text
    assert not models.MODEL_ID_RE.search(text)
    roles = models.role_names()
    enabled = {k: v for k, v in cfg.items() if isinstance(v, dict) and v.get("triage_enabled")}
    assert enabled, "sources.yaml has triage-enabled sources"
    for source, block in enabled.items():
        role = config_role(block, role_key="triage_role", legacy_key="triage_model",
                           default=DEFAULT_TRIAGE_ROLE)
        assert role in roles, f"{source}: triage_role {role!r} is not a registry role"


def test_unknown_role_fails_at_construction(seldon_models_home):
    with pytest.raises(models.UnknownRole):
        LlmTriage(role="no_such_role", axes_yaml=AXES_PATH)


# ---------------------------------------------------------------------- the MCP fetcher launcher

class _RoleMcpFetcher(McpFetcher):
    source_id = "fake_mcp"
    mcp_tool = "mcp__test__search"
    # Any registry role serves here: the fixture registry is a copy of seldon's.
    model_role = "triage"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=1000.0)

    def args_for_query(self, query):
        return {"q": query.get("q", "")}

    def items_from_response(self, response):
        return response.get("results", [])


def test_mcp_fetcher_launches_from_the_lock(seldon_models_home, tmp_path):
    cli = seldon_models_home
    cli.reply("", top={"results": [{"url": "https://example.com/a"}]})
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")

    [payload] = list(_RoleMcpFetcher(archive=archive).iter_payloads({"q": "ai"}))

    [call] = cli.calls()
    argv = call["argv"]
    assert argv[0] == str(cli.path)
    assert _flag(argv, "--model") == FIXTURE_IDS["sonnet"]
    assert json.loads(_flag(argv, "--settings")) == SETTINGS
    assert _flag(argv, "--allowedTools") == "mcp__test__search"
    assert _flag(argv, "--effort") == cli.effort("triage")
    assert call["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == FIXTURE_IDS["sonnet"]
    assert call["env"][models.EFFORT_ENV] == cli.effort("triage")
    assert len(call["env"]) == 5 and all(call["env"].values())
    assert payload.request_params["model_receipt"]["served"] == FIXTURE_IDS["sonnet"]
    assert payload.request_params["model_receipt"]["effort"] == cli.effort("triage")


def test_mcp_fetcher_substitution_stops_the_call(seldon_models_home, tmp_path):
    seldon_models_home.serve("claude-opus-1-0")
    seldon_models_home.reply("", top={"results": [{"url": "https://example.com/a"}]})
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    with pytest.raises(models.ModelSubstituted):
        list(_RoleMcpFetcher(archive=archive).iter_payloads({"q": "ai"}))


def test_mcp_fetcher_without_a_role_is_refused(seldon_models_home, tmp_path):
    class NoRole(_RoleMcpFetcher):
        model_role = ""

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    with pytest.raises(ValueError, match="model_role"):
        NoRole(archive=archive)
    assert seldon_models_home.calls() == []
