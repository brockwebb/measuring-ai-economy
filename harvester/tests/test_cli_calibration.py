"""Tests for `harvester calibration` CLI."""

import json
import subprocess


def test_calibration_help_lists_command():
    """--help shows calibration subcommand."""
    result = subprocess.run(
        ["uv", "run", "harvester", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "calibration" in result.stdout, f"missing subcommand. stdout: {result.stdout}"


def test_calibration_default_renders_markdown():
    """No flags → Markdown to stdout, starting with the header."""
    result = subprocess.run(
        ["uv", "run", "harvester", "calibration", "--window", "30d"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "# Wintermute Calibration" in result.stdout
    assert "## Activity" in result.stdout
    assert "## Triage Distribution" in result.stdout


def test_calibration_json_flag_renders_valid_json():
    """--json → stdout parses as JSON with the expected top-level keys."""
    result = subprocess.run(
        ["uv", "run", "harvester", "calibration", "--window", "7d", "--json"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    parsed = json.loads(result.stdout)
    assert parsed["window_days"] == 7
    for key in ("activity", "triage", "saturation", "failure_patterns",
                "co_occurrence", "candidates", "provenance"):
        assert key in parsed, f"missing key: {key}"
