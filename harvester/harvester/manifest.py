"""Raw archive on disk + git-tracked parquet manifest.

Raw bytes land in {root}/{source_id}/{YYYY-MM}/{sha256}.{ext}. The
manifest is appended atomically by reading existing rows, adding the new
row, and rewriting. For small-to-medium volumes this is fine; if the
manifest grows past ~10M rows we can switch to chunked parquet files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from harvester.types import RawPayload


_MANIFEST_SCHEMA = pa.schema(
    [
        pa.field("raw_hash", pa.string()),
        pa.field("source_id", pa.string()),
        pa.field("source_url", pa.string()),
        pa.field("fetched_at", pa.timestamp("us", tz="UTC")),
        pa.field("request_params_json", pa.string()),
        pa.field("content_type", pa.string()),
        pa.field("byte_size", pa.int64()),
        pa.field("file_path_relative", pa.string()),
    ]
)


_EXT_FROM_CONTENT_TYPE: dict[str, str] = {
    "application/json": "json",
    "application/xml": "xml",
    "text/xml": "xml",
    "text/html": "html",
    "text/plain": "txt",
    "application/pdf": "pdf",
}


def _ext_for(content_type: str) -> str:
    primary = content_type.split(";", 1)[0].strip().lower()
    return _EXT_FROM_CONTENT_TYPE.get(primary, "bin")


@dataclass
class RawArchive:
    """Writes raw bytes to disk under root and appends rows to a parquet manifest."""

    root: Path
    manifest_path: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        source_id: str,
        source_url: str,
        request_params: dict[str, Any],
        content: bytes,
        content_type: str,
    ) -> RawPayload:
        sha = hashlib.sha256(content).hexdigest()
        now = datetime.now(timezone.utc)
        yyyy_mm = now.strftime("%Y-%m")
        ext = _ext_for(content_type)

        rel_dir = Path(source_id) / yyyy_mm
        rel_path = rel_dir / f"{sha}.{ext}"
        abs_path = self.root / rel_path

        if not abs_path.exists():
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(content)

        self._append_manifest_row(
            {
                "raw_hash": sha,
                "source_id": source_id,
                "source_url": source_url,
                "fetched_at": now,
                "request_params_json": json.dumps(request_params, sort_keys=True),
                "content_type": content_type,
                "byte_size": len(content),
                "file_path_relative": str(rel_path),
            }
        )

        return RawPayload(
            raw_hash=f"sha256:{sha}",
            file_path=abs_path,
            content_type=content_type,
            fetched_at=now,
            source_id=source_id,
            source_url=source_url,
            request_params=request_params,
        )

    def _append_manifest_row(self, row: dict[str, Any]) -> None:
        new_table = pa.Table.from_pylist([row], schema=_MANIFEST_SCHEMA)
        if self.manifest_path.exists():
            existing = pq.read_table(self.manifest_path)
            combined = pa.concat_tables([existing, new_table])
        else:
            combined = new_table
        pq.write_table(combined, self.manifest_path)
