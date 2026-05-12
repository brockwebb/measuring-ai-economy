"""CLI tests."""

import subprocess
from harvester.db import get_connection


def test_migrate_command_applies_all_pending():
    """`harvester migrate` should record applied migrations in schema_migrations."""
    # Run migrate via CLI
    result = subprocess.run(
        ["uv", "run", "harvester", "migrate"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"migrate failed: {result.stderr}"

    # Verify the 001 migration is recorded
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT filename, sha256 FROM harvest.schema_migrations "
                "WHERE filename = '001_harvest_init.sql'"
            )
            row = cur.fetchone()
            assert row is not None, "migration 001 not recorded"
            filename, sha = row
            assert filename == "001_harvest_init.sql"
            assert sha != "PLACEHOLDER_SHA", "SHA should be computed at apply time"
            assert len(sha) == 64, "SHA-256 hex digest is 64 chars"
    finally:
        conn.close()


def test_migrate_is_idempotent():
    """Running migrate twice should be a no-op the second time."""
    subprocess.run(["uv", "run", "harvester", "migrate"], check=True)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.schema_migrations "
                "WHERE filename = '001_harvest_init.sql'"
            )
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()
