"""One-off helper to regenerate arxiv golden-sample expected files.

Usage: uv run python -m harvester.scripts.regen_arxiv_golden_samples
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from harvester.etl.arxiv import ArxivETL
from harvester.types import RawPayload


FIXTURE_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "arxiv"


def _normalize(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def main() -> None:
    etl = ArxivETL()
    for name in ("ml", "econ", "stat", "cs"):
        input_path = FIXTURE_DIR / f"paper_{name}.input.json"
        if not input_path.exists():
            print(f"SKIP {name} (no input)")
            continue
        raw = RawPayload(
            raw_hash="sha256:test",
            file_path=input_path,
            content_type="application/xml",
            fetched_at=datetime(2026, 5, 12, 7, 0, 0),
            source_id="arxiv",
            source_url=json.loads(input_path.read_text()).get("id", ""),
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
        out_path = FIXTURE_DIR / f"paper_{name}.expected.json"
        out_path.write_text(json.dumps(expected, indent=2, sort_keys=True))
        print(f"WROTE {out_path}")


if __name__ == "__main__":
    main()
