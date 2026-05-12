"""Tests for `harvester scout` CLI."""

import subprocess

import pytest

from harvester.db import get_connection


@pytest.fixture
def clean_fr_scout_state():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM harvest.data_sources WHERE source_id = 'federal_register'")
        conn.commit()
        yield
        # No teardown — scout state from this test is real, may be useful for later
    finally:
        conn.close()


def test_scout_cli_persists_notes(clean_fr_scout_state):
    """`harvester scout federal_register --base-url https://www.federalregister.gov`
    writes a discovery_notes row.

    This hits the real FR site; treat the network result as "best effort" but the
    persistence behavior must be deterministic."""
    result = subprocess.run(
        ["uv", "run", "harvester", "scout", "federal_register",
         "--base-url", "https://www.federalregister.gov"],
        capture_output=True, text=True,
        cwd="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester",
    )
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT discovery_notes, last_scouted_at FROM harvest.data_sources WHERE source_id = 'federal_register'"
            )
            row = cur.fetchone()
            assert row is not None, (
                f"No discovery_notes persisted. exit={result.returncode}, "
                f"stdout: {result.stdout!r}, stderr: {result.stderr!r}"
            )
            notes, scouted_at = row
            assert notes is not None
            assert scouted_at is not None
    finally:
        conn.close()
