"""Weekly manifest-integrity check.

Samples N rows from the parquet manifest, verifies each file exists at
the recorded path with the recorded sha256. Mismatches indicate silent
disk corruption or file deletion.

Run from launchd weekly. Exit non-zero on any mismatch.
"""

from __future__ import annotations

import hashlib
import os
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq

_MANIFEST = Path(
    os.environ.get(
        "HARVESTER_MANIFEST",
        str(Path(__file__).parent.parent.parent.parent / "data" / "manifests" / "raw_manifest.parquet"),
    )
)
_RAW_ROOT = Path(
    os.environ.get(
        "HARVESTER_RAW_ROOT",
        str(Path(__file__).parent.parent.parent.parent / "data" / "raw"),
    )
)
_SAMPLE_N = 50


def main() -> int:
    if not _MANIFEST.exists():
        print(f"[verify_manifest] manifest missing: {_MANIFEST}", file=sys.stderr)
        return 0
    table = pq.read_table(_MANIFEST)
    rows = table.to_pylist()
    if not rows:
        print("[verify_manifest] manifest empty")
        return 0
    sample = random.sample(rows, min(_SAMPLE_N, len(rows)))
    failures: list[tuple[str, str]] = []
    for row in sample:
        path = _RAW_ROOT / row["file_path_relative"]
        if not path.exists():
            failures.append((row["raw_hash"], f"missing: {path}"))
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha != row["raw_hash"]:
            failures.append((row["raw_hash"], f"sha mismatch (got {sha[:12]}) at {path}"))
    print(f"[verify_manifest] sampled {len(sample)} rows; {len(failures)} failures")
    for raw_hash, msg in failures:
        print(f"  {raw_hash[:16]}... {msg}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
