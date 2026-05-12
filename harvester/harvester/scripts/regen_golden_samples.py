"""One-off helper to regenerate FR golden-sample expected files.

Usage: uv run python -m harvester.scripts.regen_golden_samples
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from harvester.etl.federal_register import FederalRegisterETL
from harvester.types import RawPayload


FIXTURE_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "federal_register"


def _normalize(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def main() -> None:
    etl = FederalRegisterETL()
    for name in ("rule", "eo", "notice", "proposed_rule"):
        input_path = FIXTURE_DIR / f"{name}.input.json"
        if not input_path.exists():
            print(f"SKIP {name} (no input)")
            continue
        raw = RawPayload(
            raw_hash="sha256:test",
            file_path=input_path,
            content_type="application/json",
            fetched_at=datetime(2026, 5, 11, 22, 0, 0),
            source_id="federal_register",
            source_url=json.loads(input_path.read_text()).get("html_url", ""),
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
        out_path = FIXTURE_DIR / f"{name}.expected.json"
        out_path.write_text(json.dumps(expected, indent=2, sort_keys=True))
        print(f"WROTE {out_path}")


if __name__ == "__main__":
    main()
