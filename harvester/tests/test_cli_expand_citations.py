"""Tests for `harvester expand-citations` CLI."""

import subprocess


def test_expand_citations_help_lists_command():
    """--help shows expand-citations subcommand."""
    result = subprocess.run(
        ["uv", "run", "harvester", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "expand-citations" in result.stdout, f"missing subcommand. stdout: {result.stdout}"


def test_expand_citations_dry_run_does_not_call_api():
    """--dry-run prints what would be processed; does not hit Semantic Scholar."""
    result = subprocess.run(
        ["uv", "run", "harvester", "expand-citations", "--dry-run", "--max-batch", "5"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "DRY RUN" in result.stdout or "would process" in result.stdout.lower()
