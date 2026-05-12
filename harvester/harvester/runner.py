"""Runner orchestration.

One Runner per (source, run). Acquires advisory lock, checks backpressure,
opens a run_log row, drives fetcher -> etl -> loader -> normalizer for
each payload, updates run_log on completion/failure.
"""

from __future__ import annotations

import json
import subprocess
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from harvester.db import get_connection, with_advisory_lock
from harvester.loader import Loader
from harvester.manifest import RawArchive
from harvester.normalizer import emit_markdown


@dataclass
class RunnerConfig:
    source_id: str
    archive_root: Path
    manifest_path: Path
    inbox_dir: Path
    inbox_backpressure_max: int
    expected_schema_version: int


@dataclass
class RunResult:
    run_id: int
    status: str
    items_fetched: int = 0
    items_deposited: int = 0
    items_failed: int = 0
    error: str | None = None


def _git_sha() -> str:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        dirty = subprocess.call(
            ["git", "diff", "--quiet"], stderr=subprocess.DEVNULL
        )
        return f"{sha}-dirty" if dirty != 0 else sha
    except Exception:
        return "unknown"


class Runner:
    """Drives one harvester invocation end-to-end for a single source."""

    def __init__(self, *, config: RunnerConfig, fetcher, etl) -> None:
        self.config = config
        self.fetcher = fetcher
        self.etl = etl

    def run(self, query: dict[str, Any]) -> RunResult:
        conn = get_connection()
        run_id = self._open_run_log(conn, query)
        try:
            if self._inbox_size() > self.config.inbox_backpressure_max:
                self._close_run_log(
                    conn,
                    run_id,
                    status="cancelled",
                    error=f"inbox backpressure: {self._inbox_size()} > {self.config.inbox_backpressure_max}",
                )
                return RunResult(run_id=run_id, status="cancelled", error="backpressure")

            self._assert_schema_version(conn)

            with with_advisory_lock(conn, self.config.source_id):
                result = self._drive(conn, run_id, query)

            self._close_run_log(
                conn,
                run_id,
                status="completed",
                items_fetched=result.items_fetched,
                items_deposited=result.items_deposited,
                items_failed=result.items_failed,
            )
            result.status = "completed"
            return result
        except Exception:
            tb = traceback.format_exc()
            self._close_run_log(conn, run_id, status="failed", error=tb)
            return RunResult(run_id=run_id, status="failed", error=tb)
        finally:
            conn.close()

    def _drive(self, conn: psycopg.Connection, run_id: int, query: dict[str, Any]) -> RunResult:
        archive = RawArchive(root=self.config.archive_root, manifest_path=self.config.manifest_path)
        self.fetcher.archive = archive
        loader = Loader(conn)

        # Build seen-URL set once per run so the fetcher can skip already-known
        # items BEFORE writing raw bytes. Saves disk + bandwidth on dedup-skipped
        # items. The runner still re-checks below as defense-in-depth.
        seen_urls = self._seen_urls_for_source(conn)

        fetched = 0
        deposited = 0
        failed = 0
        for payload in self.fetcher.iter_payloads(query, seen=seen_urls):
            fetched += 1
            try:
                if self._already_seen(conn, payload.source_url):
                    continue
                parsed = self.etl.parse(payload)
                rows = list(self.etl.to_rows(parsed))
                loader.load(rows, run_id=run_id)
                inbox_path = emit_markdown(
                    parsed,
                    inbox_dir=self.config.inbox_dir,
                    source_id=self.config.source_id,
                    raw_hash=payload.raw_hash,
                    harvester_run_id=run_id,
                    pg_refs=[{"table": r.target_table, "pk": None} for r in rows],
                    expected_schema_version=self.config.expected_schema_version,
                )
                self._record_fetched_item(
                    conn,
                    item_id=payload.source_url,
                    raw_hash=payload.raw_hash,
                    run_id=run_id,
                    inbox_path=str(inbox_path),
                    status="deposited",
                )
                deposited += 1
            except Exception as e:
                failed += 1
                self._record_fetched_item(
                    conn,
                    item_id=payload.source_url,
                    raw_hash=payload.raw_hash,
                    run_id=run_id,
                    inbox_path=None,
                    status="failed",
                    error=str(e),
                )
        return RunResult(
            run_id=run_id, status="running", items_fetched=fetched,
            items_deposited=deposited, items_failed=failed,
        )

    def _inbox_size(self) -> int:
        if not self.config.inbox_dir.exists():
            return 0
        return sum(1 for _ in self.config.inbox_dir.iterdir())

    def _assert_schema_version(self, conn: psycopg.Connection) -> None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM harvest.schema_migrations WHERE id >= %s",
                (self.config.expected_schema_version,),
            )
            applied = cur.fetchone()[0]
        if applied < 1:
            raise RuntimeError(
                f"expected schema_version >= {self.config.expected_schema_version} not applied"
            )

    def _open_run_log(self, conn: psycopg.Connection, query: dict[str, Any]) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.run_log
                    (source_id, code_sha, expected_schema_version, args, status)
                VALUES (%s, %s, %s, %s, 'running')
                RETURNING id
                """,
                (
                    self.config.source_id,
                    _git_sha(),
                    self.config.expected_schema_version,
                    json.dumps(query),
                ),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
        return run_id

    def _close_run_log(
        self,
        conn: psycopg.Connection,
        run_id: int,
        *,
        status: str,
        items_fetched: int = 0,
        items_deposited: int = 0,
        items_failed: int = 0,
        error: str | None = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE harvest.run_log
                SET finished_at = now(),
                    status = %s,
                    items_fetched = %s,
                    items_deposited = %s,
                    items_failed = %s,
                    error = %s
                WHERE id = %s
                """,
                (status, items_fetched, items_deposited, items_failed, error, run_id),
            )
        conn.commit()

    def _already_seen(self, conn: psycopg.Connection, item_id: str) -> bool:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM harvest.fetched_items WHERE item_id = %s AND status = 'deposited'",
                (item_id,),
            )
            return cur.fetchone() is not None

    def _seen_urls_for_source(self, conn: psycopg.Connection) -> set[str]:
        """Return the set of source_urls already deposited for this source.

        Built once at run start and passed into the fetcher so it can skip
        raw-archive writes for known URLs. The runner still re-checks
        per-payload as defense-in-depth.
        """
        with conn.cursor() as cur:
            cur.execute(
                "SELECT item_id FROM harvest.fetched_items "
                "WHERE source_id = %s AND status = 'deposited'",
                (self.config.source_id,),
            )
            return {row[0] for row in cur.fetchall()}

    def _record_fetched_item(
        self,
        conn: psycopg.Connection,
        *,
        item_id: str,
        raw_hash: str,
        run_id: int,
        inbox_path: str | None,
        status: str,
        error: str | None = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO harvest.fetched_items
                    (item_id, source_id, raw_hash, run_id, inbox_path, status, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (item_id) DO UPDATE
                    SET raw_hash = EXCLUDED.raw_hash,
                        run_id = EXCLUDED.run_id,
                        inbox_path = EXCLUDED.inbox_path,
                        status = EXCLUDED.status,
                        error = EXCLUDED.error,
                        fetched_at = now()
                """,
                (item_id, self.config.source_id, raw_hash, run_id, inbox_path, status, error),
            )
        conn.commit()
