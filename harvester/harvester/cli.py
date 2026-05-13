"""Harvester CLI."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import typer
import yaml

from harvester.db import get_connection
from harvester.discovery.scout import MuiScout
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


def _staging_dir() -> Path:
    """Drop dir for normalized markdown — staging/YYYY-MM/.

    The harvester's output already has full YAML frontmatter (source_type,
    captured_at, raw_hash, pg_refs, ...) — that's staging format, not inbox
    format. Wintermute's existing inbox→staging drain only handles PDFs, so
    routing through inbox would be a no-op. Drop directly into staging.
    """
    base = Path(os.environ.get("WINTERMUTE_STAGING", str(Path.home() / ".wintermute" / "staging")))
    return base / date.today().strftime("%Y-%m")


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
def scout(
    source: str = typer.Argument(..., help="Source id, e.g., 'federal_register'"),
    base_url: str = typer.Option(..., "--base-url", help="Base URL to probe"),
    force: bool = typer.Option(False, "--force", help="Re-probe even if recent notes exist"),
) -> None:
    """Probe a source's MUI affordances and persist to data_sources.discovery_notes."""
    conn = get_connection()
    try:
        if not force:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT last_scouted_at FROM harvest.data_sources
                    WHERE source_id = %s AND last_scouted_at > now() - interval '90 days'
                    """,
                    (source,),
                )
                if cur.fetchone():
                    typer.echo(f"{source} already scouted recently. Use --force to re-probe.")
                    return

        scout_obj = MuiScout()
        typer.echo(f"Probing {base_url} ...")
        notes = scout_obj.probe(base_url)
        notes_json = json.dumps({
            "base_url": notes.base_url,
            "probed_at": notes.probed_at.isoformat(),
            "llms_txt": notes.llms_txt,
            "robots_rules": notes.robots_rules,
            "sitemap_urls": notes.sitemap_urls,
            "openapi_spec": notes.openapi_spec,
            "rss_feeds": notes.rss_feeds,
            "schema_org_types": notes.schema_org_types,
            "probe_errors": notes.probe_errors,
        })

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.data_sources (source_id, name, discovery_notes, last_scouted_at)
                VALUES (%s, %s, %s::jsonb, now())
                ON CONFLICT (source_id) DO UPDATE
                SET discovery_notes = EXCLUDED.discovery_notes,
                    last_scouted_at = EXCLUDED.last_scouted_at
                """,
                (source, source, notes_json),
            )
        conn.commit()
        typer.echo(f"Scouted {source}: llms_txt={'yes' if notes.llms_txt else 'no'}, "
                   f"robots={'yes' if notes.robots_rules else 'no'}, "
                   f"sitemaps={len(notes.sitemap_urls)}, rss_feeds={len(notes.rss_feeds)}, "
                   f"openapi={'yes' if notes.openapi_spec else 'no'}, "
                   f"schema_org={len(notes.schema_org_types)}, "
                   f"errors={len(notes.probe_errors)}")
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
        inbox_dir=_staging_dir(),
        inbox_backpressure_max=int(cfg.get("inbox_backpressure_max", 5000)),
        expected_schema_version=int(cfg.get("expected_schema_version", 2)),
        scout_base_url=cfg.get("scout_base_url"),
        triage_enabled=bool(cfg.get("triage_enabled", False)),
        triage_model=str(cfg.get("triage_model", "claude-sonnet-4-6")),
        triage_axes_yaml=(Path(__file__).parent / "triage" / "research_axes.yaml")
            if cfg.get("triage_enabled") else None,
        triage_threshold=float(cfg.get("triage_threshold", 0.4)),
    )

    archive = RawArchive(root=config.archive_root, manifest_path=config.manifest_path)
    fetcher = fetcher_cls(archive=archive)
    etl = etl_cls()

    runner = Runner(config=config, fetcher=fetcher, etl=etl)

    total = 0
    for term in (terms or [None]):
        q: dict[str, Any] = {
            "per_page": 100,
            "max_pages": 10,
        }
        if source == "federal_register":
            q.update({
                "term": term,
                "type": cfg.get("document_types", []),
                "publication_date_gte": pub_gte,
                "publication_date_lte": pub_lte,
            })
        else:
            if cats := cfg.get("categories"):
                q["categories"] = cats
            if term:
                q["keyword"] = term
        label = repr(term) if term else "(no-keyword)"
        typer.echo(f"--- running {source} for term: {label}")
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

        typer.echo("\n=== Staging depth (this month) ===")
        staging = _staging_dir()
        if staging.exists():
            typer.echo(f"  {staging}: {sum(1 for _ in staging.iterdir())} files")
        else:
            typer.echo(f"  {staging}: (missing)")

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


@app.command("compare-sources")
def compare_sources(
    old: str = typer.Argument(..., help="Legacy source_id (e.g., 'arxiv_search_papers')"),
    new: str = typer.Argument(..., help="New source_id (e.g., 'arxiv')"),
    days: int = typer.Option(3, "--days", help="Window in days back from now"),
) -> None:
    """Compare staged-doc volume + overlap between two source_ids.

    Used during the Phase 2 (and future migration) verification windows where
    the legacy script and the new harvester fetcher both run in parallel.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH
                  old_urls AS (
                    SELECT source_url FROM harvest.document_metadata
                    WHERE source_id = %s AND created_at > now() - make_interval(days => %s)
                  ),
                  new_urls AS (
                    SELECT source_url FROM harvest.document_metadata
                    WHERE source_id = %s AND created_at > now() - make_interval(days => %s)
                  )
                SELECT
                  (SELECT count(*) FROM old_urls) AS old_count,
                  (SELECT count(*) FROM new_urls) AS new_count,
                  (SELECT count(*) FROM old_urls o JOIN new_urls n USING (source_url)) AS both_count,
                  (SELECT count(*) FROM old_urls WHERE source_url NOT IN (SELECT source_url FROM new_urls)) AS only_old,
                  (SELECT count(*) FROM new_urls WHERE source_url NOT IN (SELECT source_url FROM old_urls)) AS only_new
                """,
                (old, days, new, days),
            )
            row = cur.fetchone()
            old_n, new_n, both, only_old, only_new = row

        typer.echo(f"=== compare-sources over last {days} days ===")
        typer.echo(f"  old: {old} → {old_n} docs")
        typer.echo(f"  new: {new} → {new_n} docs")
        typer.echo(f"  both: {both} (overlap)")
        typer.echo(f"  only-in-old: {only_old}")
        typer.echo(f"  only-in-new: {only_new}")
        if old_n > 0:
            coverage = both / old_n
            typer.echo(f"  new-vs-old coverage: {coverage:.1%}  (target ≥95% for cutover)")
    finally:
        conn.close()


@app.command("check-saturation")
def check_saturation_cmd() -> None:
    """Check all sources' deposit_ratio against saturation thresholds. Email alerts."""
    from harvester.improvement.saturation import SaturationMonitor
    from harvester.improvement.notify import send_alert

    conn = get_connection()
    try:
        alerts = SaturationMonitor(conn).check_alerts()
        if not alerts:
            typer.echo("No saturation alerts. All sources within healthy ratios.")
            return

        body_lines = []
        for a in alerts:
            line = f"[{a.severity.upper()}] {a.message}"
            typer.echo(line)
            body_lines.append(line)

        if any(a.severity == "alert" for a in alerts):
            send_alert(
                subject=f"[harvester] {sum(1 for a in alerts if a.severity == 'alert')} saturation alert(s)",
                body="\n".join(body_lines),
            )
            raise typer.Exit(code=1)
    finally:
        conn.close()


@app.command("check-failures")
def check_failures_cmd(
    min_count: int = typer.Option(10, "--min-count", help="Threshold occurrence count"),
    window_days: int = typer.Option(7, "--window-days", help="Look-back window"),
) -> None:
    """Surface failure_patterns above the alert threshold."""
    from harvester.improvement.failure_patterns import patterns_above_threshold

    conn = get_connection()
    try:
        patterns = patterns_above_threshold(conn, min_count=min_count, window_days=window_days)
        if not patterns:
            typer.echo(f"No failure patterns crossing {min_count} occurrences in last {window_days}d.")
            return

        typer.echo(f"=== Failure patterns above threshold ({min_count} in {window_days}d) ===")
        for p in patterns:
            typer.echo(
                f"  [{p['source_id']}] {p['occurrence_count']}× since "
                f"{p['first_seen_at']:%Y-%m-%d}: {p['error_signature'][:120]}"
            )
            typer.echo(f"      sample: {(p['sample_error'] or '')[:200]}")
    finally:
        conn.close()


@app.command("expand-citations")
def expand_citations_cmd(
    max_batch: int = typer.Option(100, "--max-batch", help="Max proposed candidates to process"),
    threshold: float = typer.Option(0.4, "--threshold", help="Triage score promotion cutoff"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print pending candidates without API calls"),
) -> None:
    """Drive CitationChain.process_pending — verify pending candidates via
    Semantic Scholar + LlmTriage, promote to approved/rejected."""
    from harvester.improvement.citation_chain import CitationChain
    from harvester.fetchers.semantic_scholar import SemanticScholarFetcher
    from harvester.triage.llm_triage import LlmTriage
    from harvester.manifest import RawArchive

    conn = get_connection()
    try:
        if dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM harvest.expansion_candidates "
                    "WHERE kind = 'paper' AND status = 'proposed'"
                )
                pending = cur.fetchone()[0]
            typer.echo(f"DRY RUN: would process up to {max_batch} of {pending} pending candidates "
                       f"(threshold={threshold}).")
            return

        # Real run — instantiate fetcher + triage
        data_root = _data_root()
        archive = RawArchive(
            root=data_root / "raw",
            manifest_path=data_root / "manifests" / "raw_manifest.parquet",
        )
        ss_fetcher = SemanticScholarFetcher(archive=archive)
        triage = LlmTriage(
            model_id="claude-sonnet-4-6",
            axes_yaml=Path(__file__).parent / "triage" / "research_axes.yaml",
        )

        chain = CitationChain(conn)
        result = chain.process_pending(
            max_batch=max_batch,
            ss_fetcher=ss_fetcher,
            triage=triage,
            threshold=threshold,
        )
        typer.echo(
            f"Processed {sum(result.values())} candidates: "
            f"approved={result['approved']} rejected={result['rejected']} "
            f"deferred={result['deferred']}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    app()
