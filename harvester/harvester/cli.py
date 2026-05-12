"""Harvester CLI.

Entry point: `harvester` (set in pyproject.toml [project.scripts]).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import typer

from harvester.db import get_connection

app = typer.Typer(help="Harvester CLI for the AI economy measurement project.")


@app.callback()
def _root() -> None:
    """Force subcommand mode (so `harvester migrate` is a subcommand,
    not the only command merged into the root)."""


SCHEMAS_DIR = Path(__file__).parent / "schemas"


def _migrations() -> list[Path]:
    """Return migration files in lexicographic order."""
    return sorted(SCHEMAS_DIR.glob("*.sql"))


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _applied_migrations(conn) -> set[str]:
    """Return filenames of already-applied migrations."""
    with conn.cursor() as cur:
        # Bootstrap: the schema_migrations table may not exist on a fresh db
        cur.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'harvest' AND tablename = 'schema_migrations'
            )
            """
        )
        if not cur.fetchone()[0]:
            return set()
        cur.execute("SELECT filename FROM harvest.schema_migrations")
        return {row[0] for row in cur.fetchall()}


@app.command()
def migrate() -> None:
    """Apply pending schema migrations in order."""
    conn = get_connection()
    try:
        applied = _applied_migrations(conn)
        pending = [m for m in _migrations() if m.name not in applied]
        if not pending:
            typer.echo("No pending migrations.")
            return

        for migration in pending:
            sha = _sha256_of(migration)
            sql = migration.read_text().replace("PLACEHOLDER_SHA", sha)
            typer.echo(f"Applying {migration.name} ({sha[:12]}...)")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        typer.echo(f"Applied {len(pending)} migration(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    app()
