"""Tests for `harvester chain-references` CLI."""

import subprocess


def test_chain_references_help_lists_command():
    """--help shows chain-references subcommand."""
    result = subprocess.run(
        ["uv", "run", "harvester", "--help"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert "chain-references" in result.stdout, f"missing subcommand. stdout: {result.stdout}"


def test_chain_references_dry_run_does_not_call_api():
    """--dry-run prints what would be expanded; does not hit Semantic Scholar."""
    result = subprocess.run(
        ["uv", "run", "harvester", "chain-references", "--dry-run", "--max-parents", "5"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "DRY RUN" in result.stdout
