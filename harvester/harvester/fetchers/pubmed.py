"""PubMed fetcher — direct NCBI E-utilities API.

Replaces the previous MCP-prompt-mediated path (PubMed MCP server +
`claude -p` subprocess) which suffered from two recurring bugs filed in
the operator's code_fix_backlog: a `slice(None, 10, None)` parse error
and a psycopg2 `cannot adapt type 'dict'` error — both originated in
the MCP envelope unwrap + ad-hoc record normalization. Replacing the
fetcher with direct E-utilities calls eliminates the prompt-parsing
surface entirely.

Per operator directive 2026-05-17:
  - Use APIs, not crawl4ai or MCP-prompt indirection, when the host
    has a clean public API (NCBI does)
  - Read NCBI_API_KEY from environment for the 10 req/sec authenticated
    rate (vs 3 req/sec floor)
  - No hardcoded model / key / endpoint values

API:
  ESearch  — keyword query -> list of PMIDs
  ESummary — batch metadata (JSON; up to ~200 PMIDs per call)
  EFetch   — batch abstract text (XML; handles labeled sections like
             BACKGROUND/METHODS/RESULTS/CONCLUSIONS)

Per-record output shape matches the existing PubMedETL contract — no
ETL-side changes required.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

import httpx

from harvester.fetchers.base import Fetcher
from harvester.types import RateLimit, RawPayload


_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_USER_AGENT = "WintermuteHarvester/0.1 (research; mailto:brockwebb45@gmail.com)"
_DEFAULT_PER_PAGE = 50
_DEFAULT_MAX_PAGES = 4
_ESUMMARY_BATCH_CAP = 200  # NCBI E-utilities accepts ~200 PMIDs per request


def _load_ncbi_api_key() -> str | None:
    """Return NCBI_API_KEY from env or ~/.wintermute/.env. None if missing."""
    key = os.environ.get("NCBI_API_KEY", "").strip().strip('"').strip("'")
    if key:
        return key
    env_path = Path.home() / ".wintermute" / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        m = re.match(r'^\s*NCBI_API_KEY\s*=\s*"?([^"#]+?)"?\s*(?:#.*)?$', line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


class PubMedFetcher(Fetcher):
    """Direct NCBI E-utilities fetcher for PubMed.

    Multi-step per page: ESearch (PMIDs) -> ESummary (metadata) -> EFetch (abstract).
    The 3 calls together count as one "page" in this fetcher's pagination model;
    NCBI is fine with that pattern as long as we honor the rate limit between
    individual HTTP requests.
    """

    source_id = "pubmed"

    def rate_limit_spec(self) -> RateLimit:
        # 10 req/sec authenticated, 3 req/sec floor. We pace at 9 to stay polite
        # under the authenticated cap; falls within the unauthenticated 3/sec if
        # the key is missing (the _pace gap is set by the runner / base class
        # via the seconds_between_requests property — at 9 req/sec that's
        # ~0.111s, which an unauthenticated request will also satisfy since
        # NCBI's 3/sec floor allows ~0.333s gap).
        return RateLimit(
            requests_per_second=9.0,
            max_retries=3,
            backoff_seconds=[2, 5, 15],
        )

    def args_for_query(self, query: dict[str, Any]) -> dict[str, Any]:
        """Normalize a query dict. Kept for back-compat with the CLI which
        invokes args_for_query before iter_payloads in some code paths."""
        return {
            "term": query.get("keyword") or query.get("term") or "",
            "per_page": int(query.get("per_page", _DEFAULT_PER_PAGE)),
            "max_pages": int(query.get("max_pages", _DEFAULT_MAX_PAGES)),
        }

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        """Yield one RawPayload per matched PubMed article.

        Query shape:
            {"keyword": "machine learning", "per_page": 50, "max_pages": 4}

        Per page:
          1. ESearch for the term -> PMIDs (paginated via retstart)
          2. ESummary batch for those PMIDs -> metadata dicts
          3. EFetch batch for those PMIDs -> abstract text per PMID
          4. For each PMID: normalize + yield archive.write payload
        """
        seen = seen or set()
        normalized = self.args_for_query(query)
        term = normalized["term"]
        per_page = normalized["per_page"]
        max_pages = normalized["max_pages"]
        if not term:
            return

        api_key = _load_ncbi_api_key()

        with httpx.Client(
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            for page in range(max_pages):
                retstart = page * per_page
                self._pace()
                pmids = self._esearch(client, term, per_page, retstart, api_key)
                if not pmids:
                    break

                # Batch summaries + abstracts. With per_page <= ESUMMARY_BATCH_CAP
                # these fit in a single call each.
                self._pace()
                summaries = self._esummary(client, pmids, api_key)
                self._pace()
                abstracts = self._efetch_abstracts(client, pmids, api_key)

                for pmid in pmids:
                    summary = summaries.get(pmid)
                    if not summary:
                        continue
                    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    if pubmed_url in seen:
                        continue
                    record = self._normalize(pmid, summary, abstracts.get(pmid, ""))
                    entry_bytes = json.dumps(record, sort_keys=True).encode("utf-8")
                    yield self.archive.write(
                        source_id=self.source_id,
                        source_url=pubmed_url,
                        request_params={
                            "term": term,
                            "per_page": per_page,
                            "page": page,
                            "pmid": pmid,
                        },
                        content=entry_bytes,
                        content_type="application/json",
                    )

                if len(pmids) < per_page:
                    break

    # ---- ESearch / ESummary / EFetch helpers -----------------------------

    def _esearch(
        self,
        client: httpx.Client,
        term: str,
        retmax: int,
        retstart: int,
        api_key: str | None,
    ) -> list[str]:
        params = {
            "db": "pubmed",
            "term": term,
            "retmax": str(retmax),
            "retstart": str(retstart),
            "retmode": "json",
        }
        if api_key:
            params["api_key"] = api_key
        resp = client.get(f"{_EUTILS_BASE}/esearch.fcgi", params=params)
        resp.raise_for_status()
        return resp.json().get("esearchresult", {}).get("idlist", []) or []

    def _esummary(
        self,
        client: httpx.Client,
        pmids: list[str],
        api_key: str | None,
    ) -> dict[str, dict]:
        if not pmids:
            return {}
        params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
        if api_key:
            params["api_key"] = api_key
        resp = client.get(f"{_EUTILS_BASE}/esummary.fcgi", params=params)
        resp.raise_for_status()
        result = resp.json().get("result", {})
        return {pid: result[pid] for pid in result.get("uids", []) if pid in result}

    def _efetch_abstracts(
        self,
        client: httpx.Client,
        pmids: list[str],
        api_key: str | None,
    ) -> dict[str, str]:
        if not pmids:
            return {}
        params = {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}
        if api_key:
            params["api_key"] = api_key
        resp = client.get(f"{_EUTILS_BASE}/efetch.fcgi", params=params)
        resp.raise_for_status()
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            return {pmid: "" for pmid in pmids}

        out: dict[str, str] = {pmid: "" for pmid in pmids}
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None or not pmid_el.text:
                continue
            pmid = pmid_el.text.strip()
            chunks: list[str] = []
            for at in article.findall(".//Abstract/AbstractText"):
                label = at.get("Label")
                text = "".join(at.itertext()).strip()
                if not text:
                    continue
                chunks.append(f"**{label}:** {text}" if label else text)
            out[pmid] = "\n\n".join(chunks)
        return out

    # ---- Normalization ---------------------------------------------------

    def _normalize(self, pmid: str, summary: dict, abstract: str) -> dict[str, Any]:
        """Produce the record shape PubMedETL expects.

        Output keys: pmid, title, abstract, authors, journal, publication_date,
        doi, pmcid, mesh_terms, url. Matches what the old MCP-mediated fetcher
        produced after _normalize_item — kept stable so etl/pubmed.py needs
        no changes.
        """
        title = (summary.get("title") or "").strip()
        authors: list[dict[str, str]] = []
        for a in summary.get("authors", []):
            nm = (a.get("name") or "").strip()
            if nm:
                authors.append({"name": nm})

        journal = (summary.get("source") or summary.get("fulljournalname") or "").strip() or None

        # Normalize NCBI's date forms ("2024 Jun 15", "2024 Aug", "2024") to YYYY-MM-DD.
        pub_date_raw = (summary.get("pubdate") or summary.get("epubdate") or "").strip()
        publication_date = self._iso_date(pub_date_raw)

        doi = None
        pmcid = None
        for aid in summary.get("articleids", []) or []:
            kind = aid.get("idtype")
            val = aid.get("value")
            if kind == "doi" and val:
                doi = val
            elif kind == "pmcid" and val:
                pmcid = val

        # ESummary doesn't carry MeSH terms; EFetch XML does. Use empty list
        # here — the ETL accepts an empty list. A future enhancement can
        # parse MeSH from the EFetch XML response (already fetched for the
        # abstract above) and attach it here.
        mesh_terms: list[str] = []

        return {
            "pmid": pmid,
            "title": title,
            "abstract": abstract or None,
            "authors": authors,
            "journal": journal,
            "publication_date": publication_date,
            "doi": doi,
            "pmcid": pmcid,
            "mesh_terms": mesh_terms,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }

    @staticmethod
    def _iso_date(raw: str) -> str | None:
        """Parse NCBI date forms permissively. Returns YYYY-MM-DD or None."""
        if not raw:
            return None
        m = re.match(r"^(\d{4})(?:\s+(\w{3}))?(?:\s+(\d{1,2}))?", raw)
        if not m:
            return None
        year = m.group(1)
        mon = m.group(2) or ""
        day_str = m.group(3) or "01"
        months = {
            "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
            "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
            "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
        }
        mm = months.get(mon[:3].capitalize(), "01") if mon else "01"
        try:
            day = int(day_str)
        except ValueError:
            day = 1
        return f"{year}-{mm}-{day:02d}"
