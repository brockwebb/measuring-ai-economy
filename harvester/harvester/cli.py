"""Harvester CLI."""

from __future__ import annotations

import hashlib
import importlib
import os
from datetime import date, timedelta
from pathlib import Path

import typer
import yaml

from harvester.db import get_connection
from harvester.manifest import RawArchive
from harvester.runner import Runner, RunnerConfig

app = typer.Typer(help="Harvester CLI for the AI economy measurement project.")

SCHEMAS_DIR = Path(__file__).parent / "schemas"
CONFIG_PATH = Path(__file__).parent / "config" / "sources.yaml"


@app.callback()
def _root() -> None:
    """Harvester CLI. Use one of the subcommands below."""


def _migrations() -> list[Path]:
    return sorted(SCHEMAS_DIR.glob("*.sql"))


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _applied_migrations(conn) -> set[str]:
    with conn.cursor() as cur:
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


def _load_class(dotted: str):
    mod_path, cls_name = dotted.rsplit(".", 1)
    return getattr(importlib.import_module(mod_path), cls_name)


def _sources_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def _data_root() -> Path:
    # measuring-ai-economy/data/
    return Path(__file__).parent.parent.parent / "data"


def _inbox_dir() -> Path:
    return Path(os.environ.get("WINTERMUTE_INBOX", str(Path.home() / ".wintermute" / "inbox")))


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


@app.command()
def run(
    source: str = typer.Argument(..., help="Source id, e.g., 'federal_register'"),
    query: str | None = typer.Option(None, "--query", help="Override query term"),
    tier: str = typer.Option("tier_1", help="tier_1 | tier_2 | both"),
    limit: int = typer.Option(0, help="Max items (0 = no limit)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan, don't execute"),
) -> None:
    """Run the harvester for a given source."""
    cfg = _sources_config()[source]
    fetcher_cls = _load_class(cfg["fetcher"])
    etl_cls = _load_class(cfg["etl"])

    terms: list[str] = []
    if query:
        terms = [query]
    else:
        if tier in ("tier_1", "both"):
            terms.extend(cfg.get("tier_1_terms", []))
        if tier in ("tier_2", "both"):
            terms.extend(cfg.get("tier_2_terms", []))

    rolling = int(cfg.get("rolling_window_days", 60))
    pub_gte = (date.today() - timedelta(days=rolling)).isoformat()
    pub_lte = date.today().isoformat()

    if dry_run:
        typer.echo(f"DRY RUN: source={source}, terms={terms}, window={pub_gte}..{pub_lte}, limit={limit}")
        return

    data_root = _data_root()
    archive_root = data_root / "raw"
    manifest_path = data_root / "manifests" / "raw_manifest.parquet"

    config = RunnerConfig(
        source_id=source,
        archive_root=archive_root,
        manifest_path=manifest_path,
        inbox_dir=_inbox_dir(),
        inbox_backpressure_max=int(cfg.get("inbox_backpressure_max", 500)),
        expected_schema_version=int(cfg.get("expected_schema_version", 2)),
    )

    archive = RawArchive(root=config.archive_root, manifest_path=config.manifest_path)
    fetcher = fetcher_cls(archive=archive)
    etl = etl_cls()

    runner = Runner(config=config, fetcher=fetcher, etl=etl)

    total = 0
    for term in terms:
        q = {
            "term": term,
            "type": cfg.get("document_types", []),
            "publication_date_gte": pub_gte,
            "publication_date_lte": pub_lte,
            "per_page": 100,
            "max_pages": 10,
        }
        typer.echo(f"--- running {source} for term: {term!r}")
        result = runner.run(q)
        typer.echo(
            f"run_id={result.run_id} status={result.status} "
            f"fetched={result.items_fetched} deposited={result.items_deposited} "
            f"failed={result.items_failed}"
        )
        total += result.items_deposited
        if limit and total >= limit:
            typer.echo(f"Hit limit ({limit}); stopping.")
            break


@app.command()
def status() -> None:
    """Show last 5 runs per source + queue depth + recent errors."""
    conn = get_connection()
    try:
        typer.echo("=== Recent runs ===")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_id, id, started_at, status, items_fetched, items_deposited, items_failed
                FROM harvest.run_log
                ORDER BY started_at DESC
                LIMIT 10
                """
            )
            rows = cur.fetchall()
        for source_id, rid, started, st, f, d, fa in rows:
            typer.echo(f"  [{started:%Y-%m-%d %H:%M}] {source_id} run_id={rid} {st} f={f} d={d} fail={fa}")

        typer.echo("\n=== Inbox depth ===")
        inbox = _inbox_dir()
        if inbox.exists():
            typer.echo(f"  {inbox}: {sum(1 for _ in inbox.iterdir())} files")
        else:
            typer.echo(f"  {inbox}: (missing)")

        typer.echo("\n=== Errors last 24h ===")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_id, count(*) FROM harvest.run_log
                WHERE status IN ('failed', 'cancelled')
                  AND started_at > now() - interval '24 hours'
                GROUP BY source_id
                """
            )
            for source_id, n in cur.fetchall():
                typer.echo(f"  {source_id}: {n}")
    finally:
        conn.close()


@app.command()
def validate(source: str = typer.Argument(...)) -> None:
    """Run golden-sample tests for a source."""
    import subprocess
    r = subprocess.run(
        ["uv", "run", "pytest", f"tests/test_etl_{source}.py", "-v"],
        cwd=Path(__file__).parent.parent,
    )
    raise typer.Exit(r.returncode)


if __name__ == "__main__":
    app()
