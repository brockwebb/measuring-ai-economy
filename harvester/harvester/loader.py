"""Postgres row Loader.

Routes Row objects to their target_table and inserts them in a single
transaction. Stamps created_by_run_id on any row whose target table has
a column by that name (federal_register_documents, document_metadata, ...).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import psycopg

from harvester.types import Row


@dataclass
class LoadResult:
    rows_inserted: int


class Loader:
    """Inserts Row objects into postgres in a single transaction.

    Caller passes a live psycopg.Connection; Loader does not own its
    lifecycle. Commit happens on successful load(); exception triggers
    rollback.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn
        self._table_columns_cache: dict[str, set[str]] = {}

    def load(self, rows: Iterable[Row], *, run_id: int | None) -> LoadResult:
        inserted = 0
        try:
            for row in rows:
                self._insert(row, run_id=run_id)
                inserted += 1
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return LoadResult(rows_inserted=inserted)

    def _insert(self, row: Row, *, run_id: int | None) -> None:
        schema, table = row.target_table.split(".", 1)
        columns = self._columns_for(schema, table)
        data = dict(row.data)
        if run_id is not None and "created_by_run_id" in columns:
            data.setdefault("created_by_run_id", run_id)
        unknown = set(data) - columns
        if unknown:
            raise ValueError(
                f"Row for {row.target_table} has unknown columns: {sorted(unknown)}"
            )
        col_list = list(data.keys())
        placeholders = ", ".join(["%s"] * len(col_list))
        col_sql = ", ".join(col_list)
        with self._conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {schema}.{table} ({col_sql}) VALUES ({placeholders})",
                [data[c] for c in col_list],
            )

    def _columns_for(self, schema: str, table: str) -> set[str]:
        key = f"{schema}.{table}"
        if key in self._table_columns_cache:
            return self._table_columns_cache[key]
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                """,
                (schema, table),
            )
            cols = {row[0] for row in cur.fetchall()}
        if not cols:
            raise ValueError(f"Table {schema}.{table} not found")
        self._table_columns_cache[key] = cols
        return cols
