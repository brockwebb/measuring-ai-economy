#!/usr/bin/env python3
"""One-shot backfill: stamp precision_match + matched_terms onto every
existing Federal Register row in harvest.document_metadata.

Companion to the 2026-05-18 ETL change (commit 2284be9). New FR deposits
get tagged at parse-time; this script handles the 294 rows deposited
before the ETL change.

Idempotent: only updates rows where payload doesn't already contain a
'precision_match' key.

Usage:
    python scripts/backfill_fr_precision.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Path setup so this runs both as a script and inside the venv
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from harvester.db import get_connection  # noqa: E402
from harvester.etl.federal_register import _FR_TERMS, _match_terms  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing changes.",
    )
    args = parser.parse_args()

    if not _FR_TERMS:
        print("ERROR: no FR terms loaded — check sources.yaml")
        return 1

    print(f"Loaded {len(_FR_TERMS)} FR tier_1+tier_2 terms")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Pull every FR row that lacks the precision_match key, joining the
            # federal_register_documents table so we have the abstract too.
            cur.execute(
                """
                SELECT dm.doc_id, dm.title, fr.abstract, dm.payload
                FROM harvest.document_metadata dm
                LEFT JOIN harvest.federal_register_documents fr
                    ON fr.document_number = dm.payload->>'document_number'
                WHERE dm.source_id = 'federal_register'
                  AND NOT (dm.payload ? 'precision_match')
                """
            )
            rows = cur.fetchall()

        if not rows:
            print("Nothing to backfill — all FR rows already tagged.")
            return 0

        print(f"Backfilling {len(rows)} FR rows…")

        match_count = 0
        updates: list[tuple[str, int]] = []
        for row_id, title, abstract, payload in rows:
            matched = _match_terms(title, abstract, _FR_TERMS)
            new_payload = dict(payload)
            new_payload["matched_terms"] = matched
            new_payload["precision_match"] = bool(matched)
            updates.append((json.dumps(new_payload), row_id))
            if matched:
                match_count += 1

        print(
            f"Of {len(rows)} rows: {match_count} match at least one term "
            f"({match_count / len(rows) * 100:.1f}% precision)"
        )

        if args.dry_run:
            print("DRY-RUN: no writes.")
            return 0

        with conn.cursor() as cur:
            cur.executemany(
                """
                UPDATE harvest.document_metadata
                SET payload = %s::jsonb
                WHERE doc_id = %s
                """,
                updates,
            )
            conn.commit()

        print(f"Updated {len(updates)} rows.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
