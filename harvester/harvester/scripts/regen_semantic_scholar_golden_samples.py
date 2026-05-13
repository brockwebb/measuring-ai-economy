"""Regenerate Semantic Scholar golden-sample expected files.

Usage: uv run python -m harvester.scripts.regen_semantic_scholar_golden_samples
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from harvester.etl.semantic_scholar import SemanticScholarETL
from harvester.types import RawPayload


FIXTURE_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "semantic_scholar"


def _normalize(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def main() -> None:
    etl = SemanticScholarETL()
    for i in range(1, 5):
        input_path = FIXTURE_DIR / f"paper_{i}.input.json"
        if not input_path.exists():
            print(f"SKIP paper_{i} (no input)")
            continue
        raw = RawPayload(
            raw_hash="sha256:test",
            file_path=input_path,
            content_type="application/json",
            fetched_at=datetime(2026, 5, 12, 7, 0, 0),
            source_id="semantic_scholar",
            source_url=json.loads(input_path.read_text()).get("url", ""),
            request_params={},
        )
        doc = etl.parse(raw)
        expected = {
            "title": doc.title,
            "source_url": doc.source_url,
            "published_date": doc.published_date.isoformat() if doc.published_date else None,
            "rows": [
                {"target_table": r.target_table, "data": _normalize(r.data)}
                for r in doc.rows
            ],
            "metadata": doc.metadata,
        }
        out_path = FIXTURE_DIR / f"paper_{i}.expected.json"
        out_path.write_text(json.dumps(expected, indent=2, sort_keys=True))
        print(f"WROTE {out_path}")


if __name__ == "__main__":
    main()
