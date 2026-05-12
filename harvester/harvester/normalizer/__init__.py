"""Inbox markdown normalizer.

Source-agnostic. Takes a ParsedDoc + the postgres row IDs that were
created + harvester run metadata and emits a markdown file with YAML
frontmatter to ~/.wintermute/inbox/ (or test inbox path).

Frontmatter shape follows the design spec §3.4 and the parent spec §6.1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from harvester.types import ParsedDoc


def emit_markdown(
    doc: ParsedDoc,
    *,
    inbox_dir: Path,
    source_id: str,
    raw_hash: str,
    harvester_run_id: int,
    pg_refs: list[dict[str, Any]],
    expected_schema_version: int,
) -> Path:
    """Write a markdown file with frontmatter to inbox_dir. Return its path."""
    inbox_dir.mkdir(parents=True, exist_ok=True)
    doc_id = _doc_id(source_id, doc, raw_hash)
    out_path = inbox_dir / f"{doc_id}.md"

    frontmatter = {
        "id": doc_id,
        "source_url": doc.source_url,
        "source_type": source_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "title": doc.title,
        "published_date": doc.published_date.isoformat() if doc.published_date else None,
        "raw_hash": raw_hash,
        "harvester_run_id": harvester_run_id,
        "expected_schema_version": expected_schema_version,
        "pg_refs": pg_refs,
        "harvest_campaign": "ai-economy-measurement",
        **{k: v for k, v in doc.metadata.items() if k not in {"abstract", "body"}},
    }

    body = _render_body(doc)

    yaml_text = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    out_path.write_text(f"---\n{yaml_text}---\n\n{body}\n")
    return out_path


def _doc_id(source_id: str, doc: ParsedDoc, raw_hash: str) -> str:
    """Stable, filename-safe identifier."""
    doc_number = doc.metadata.get("document_number")
    if doc_number:
        return f"harvest-{source_id}-{doc_number}"
    short_hash = raw_hash.split(":", 1)[-1][:12]
    return f"harvest-{source_id}-{short_hash}"


def _render_body(doc: ParsedDoc) -> str:
    parts = [f"# {doc.title}", ""]
    if abstract := doc.metadata.get("abstract"):
        parts.append("## Abstract")
        parts.append("")
        parts.append(abstract.strip())
        parts.append("")
    if agencies := doc.metadata.get("agencies"):
        parts.append(f"**Agencies:** {', '.join(agencies)}")
        parts.append("")
    if doc_number := doc.metadata.get("document_number"):
        parts.append(f"**Document number:** {doc_number}")
        parts.append("")
    parts.append(f"**Source:** {doc.source_url}")
    if doc.published_date:
        parts.append(f"**Published:** {doc.published_date.isoformat()}")
    return "\n".join(parts)
