"""PubMed ETL.

Pure parse: takes one PubMed MCP record (as JSON bytes from the archive)
and produces a ParsedDoc with rows for harvest.document_metadata and
harvest.pubmed_papers.

PMID is the canonical identifier. If a PMCID is present, the PMC
full-text URL is derived (https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/).
DOI and PMCID may both be absent; both columns are nullable.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from harvester.etl.base import ETL
from harvester.types import ParsedDoc, RawPayload, Row


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _authors(record: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for a in record.get("authors") or []:
        if isinstance(a, dict) and a.get("name"):
            entry: dict[str, str] = {"name": a["name"]}
            if a.get("affiliation"):
                entry["affiliation"] = a["affiliation"]
            out.append(entry)
    return out


def _mesh_terms(record: dict[str, Any]) -> list[str]:
    terms = record.get("mesh_terms") or []
    return [t for t in terms if isinstance(t, str)]


def _pmc_full_text_url(pmcid: str | None) -> str | None:
    if not pmcid:
        return None
    return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"


class PubMedETL(ETL):
    source_id = "pubmed"
    expected_schema_version = 10

    def parse(self, raw: RawPayload) -> ParsedDoc:
        record = json.loads(raw.file_path.read_text())
        pmid = str(record["pmid"])
        title = (record.get("title") or "")[:5000]
        abstract = record.get("abstract")
        authors = _authors(record)
        journal = record.get("journal")
        pub_date = _date_or_none(record.get("publication_date"))
        doi = record.get("doi")
        pmcid = record.get("pmcid")
        mesh_terms = _mesh_terms(record)
        pubmed_url = record.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        pmc_url = _pmc_full_text_url(pmcid)

        dense_row = Row(
            target_table="harvest.pubmed_papers",
            data={
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": json.dumps(authors),
                "journal": journal,
                "publication_date": pub_date,
                "doi": doi,
                "pmcid": pmcid,
                "mesh_terms": mesh_terms,
                "pmc_full_text_url": pmc_url,
                "pubmed_url": pubmed_url,
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
                "source_url": pubmed_url,
                "published_date": pub_date,
                "document_type": "pubmed_paper",
                "payload": json.dumps(
                    {
                        "pmid": pmid,
                        "journal": journal,
                        "pmcid": pmcid,
                        "mesh_terms": mesh_terms,
                    }
                ),
                "raw_hash": raw.raw_hash,
            },
        )

        return ParsedDoc(
            title=title,
            source_url=pubmed_url,
            published_date=pub_date,
            rows=[meta_row, dense_row],
            metadata={
                "pmid": pmid,
                "doi": doi,
                "pmcid": pmcid,
                "mesh_terms": mesh_terms,
                "journal": journal,
            },
        )
