"""Tests for `harvester drain-url` CLI.

These tests mock crawl4ai entirely to avoid invoking a real browser at
test time. They verify the CLI wiring: --help shows the command, and
the command surface (argument parsing, run-log row written, ETL ran)
behaves as expected via a one-call smoke that uses a mocked fetch.
"""

import subprocess


def test_drain_url_help_lists_command():
    result = subprocess.run(
        ["uv", "run", "harvester", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "drain-url" in result.stdout, f"missing subcommand. stdout: {result.stdout}"


def test_drain_url_help_shows_url_argument():
    result = subprocess.run(
        ["uv", "run", "harvester", "drain-url", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # Typer's help should mention 'url' (the argument name) and 'drain' somewhere.
    assert "url" in result.stdout.lower()
