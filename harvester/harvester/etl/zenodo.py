"""Zenodo ETL.

Pure parse: takes a Zenodo API record (one hit) and produces a ParsedDoc
with rows for harvest.document_metadata and harvest.zenodo_records.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    s = value[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _authors(record: dict[str, Any]) -> list[dict[str, str]]:
    creators = record.get("metadata", {}).get("creators") or []
    out: list[dict[str, str]] = []
    for c in creators:
        if isinstance(c, dict):
            name = c.get("name") or c.get("orcid") or ""
            if name:
                entry: dict[str, str] = {"name": name}
                if c.get("affiliation"):
                    entry["affiliation"] = c["affiliation"]
                if c.get("orcid"):
                    entry["orcid"] = c["orcid"]
                out.append(entry)
    return out


def _resource_type(record: dict[str, Any]) -> tuple[str | None, str | None]:
    rt = record.get("metadata", {}).get("resource_type") or {}
    return rt.get("type"), rt.get("subtype")


def _keywords(record: dict[str, Any]) -> list[str]:
    kws = record.get("metadata", {}).get("keywords") or []
    return [k for k in kws if isinstance(k, str)]


class ZenodoETL(ETL):
    source_id = "zenodo"
    expected_schema_version = 8

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())
        meta = record.get("metadata", {}) or {}
        zid = int(record["id"])
        url = f"https://zenodo.org/records/{zid}"
        pub_date = _date_or_none(meta.get("publication_date"))
        authors = _authors(record)
        rtype, rsubtype = _resource_type(record)
        keywords = _keywords(record)
        doi = record.get("doi") or meta.get("doi")
        title = (meta.get("title") or "")[:5000]
        abstract = meta.get("description")

        zen_row = Row(
            target_table="harvest.zenodo_records",
            data={
                "zenodo_id": zid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "resource_type": rtype,
                "resource_subtype": rsubtype,
                "keywords": keywords,
                "publication_date": pub_date,
                "license": (meta.get("license") or {}).get("id"),
                "zenodo_url": url,
                "raw_hash": raw.raw_hash,
            },
        )

        meta_row = Row(
            target_table="harvest.document_metadata",
            data={
                "source_id": self.source_id,
                "title": title,
                "authors": json.dumps(authors),
                "doi": doi,
                "source_url": url,
                "published_date": pub_date,
                "document_type": rsubtype or rtype or "publication",
                "payload": json.dumps(
                    {
                        "zenodo_id": zid,
                        "resource_type": rtype,
                        "resource_subtype": rsubtype,
                        "keywords": keywords,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=url,
            published_date=pub_date,
            rows=[meta_row, zen_row],
            metadata={
                "zenodo_id": zid,
                "doi": doi,
                "resource_type": rtype,
                "resource_subtype": rsubtype,
            },
        )
