"""PubMed fetcher.

Backed by the PubMed MCP server. Each query uses a two-step MCP prompt:
  1. mcp__claude_ai_PubMed__search_articles → returns pmids
  2. mcp__claude_ai_PubMed__get_article_metadata → returns full records

Both steps run in a single `claude -p` subprocess (Claude orchestrates the
tool calls). The prompt instructs Claude to return a JSON object with a
"results" key containing the full article array.

items_from_response handles three real envelope shapes from claude --output-format json:
  (a) {"type": "result", "result": "<plain json string>", ...}
  (b) {"type": "result", "result": "```json\\n{...}\\n```", ...}  ← markdown-fenced
  (c) {"results": [...]} — tool output passed through directly (test fixtures)
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from harvester.fetchers.mcp_base import McpFetcher
from harvester.types import RateLimit

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class PubMedFetcher(McpFetcher):
    source_id = "pubmed"
    mcp_tool = "mcp__claude_ai_PubMed__search_articles"

    # Both MCP tools must be pre-approved so the subprocess call doesn't
    # hit the interactive permission prompt.
    allowed_tools = [
        "mcp__claude_ai_PubMed__search_articles",
        "mcp__claude_ai_PubMed__get_article_metadata",
    ]

    # Two-step prompt (search → get_metadata) takes ~40-60s wall clock.
    # 240s gives comfortable headroom without blocking the runner indefinitely.
    subprocess_timeout = 240

    # Hard cap on max_results: each MCP call = one claude -p subprocess +
    # two PubMed tool calls (search + get_metadata) + triage on every paper.
    # 5 papers per term × 10 terms = 50/night, well under the daily cost ceiling.
    # (Keeping at 10 for the search arg is fine since get_metadata does one batch
    # call regardless of count; the wall-clock cost is search + 1 metadata call.)
    _MAX_RESULTS_CAP = 5

    def rate_limit_spec(self) -> RateLimit:
        # MCP calls go through `claude -p` subprocess. Each call is heavy
        # (Claude inference + tool dispatch) — pace conservatively.
        return RateLimit(
            requests_per_second=0.5,  # 1 call per 2 seconds
            max_retries=2,
            backoff_seconds=[5, 30],
        )

    def args_for_query(self, query: dict[str, Any]) -> dict[str, Any]:
        return {
            "query": query.get("keyword", ""),
            "max_results": min(int(query.get("per_page", 10)), self._MAX_RESULTS_CAP),
        }

    def _build_mcp_prompt(self, args: dict[str, Any]) -> str:
        """Two-step prompt: search → get_metadata → return full article JSON.

        search_articles returns only pmids; get_article_metadata returns full
        records. Ask Claude to execute both in sequence and return a single
        {"results": [...]} JSON object with no commentary or markdown fences.
        """
        query = args["query"]
        max_results = args["max_results"]
        return (
            f"You have two PubMed MCP tools available: "
            f"mcp__claude_ai_PubMed__search_articles and "
            f"mcp__claude_ai_PubMed__get_article_metadata.\n\n"
            f"Step 1: Call mcp__claude_ai_PubMed__search_articles with "
            f"query={json.dumps(query)} and max_results={max_results}.\n\n"
            f"Step 2: Take all pmids from the search result and call "
            f"mcp__claude_ai_PubMed__get_article_metadata with those pmids.\n\n"
            f"Step 3: Return ONLY a JSON object with a single key 'results' "
            f"whose value is the array of article records from get_article_metadata. "
            f"No commentary, no markdown fences, no extra keys."
        )

    def items_from_response(self, response: dict[str, Any]) -> Iterable[dict[str, Any]]:
        """Extract article list from claude --output-format json envelope.

        Handles three shapes produced by different claude CLI versions:
          (a) result is a plain JSON string
          (b) result is a markdown-fenced JSON string (```json\\n{...}\\n```)
          (c) response is already the unwrapped tool output (test fixtures /
              direct dict pass-through)
        In cases (a) and (b) the inner JSON is expected to be {"results": [...]}.
        """
        body = response

        # Unwrap Claude's --output-format json envelope if present.
        if isinstance(response, dict) and "result" in response:
            inner = response["result"]
            if isinstance(inner, str):
                # Strip markdown code fence if present (shape b).
                m = _FENCE_RE.search(inner)
                text = m.group(1).strip() if m else inner.strip()
                try:
                    body = json.loads(text)
                except json.JSONDecodeError:
                    return []
            elif isinstance(inner, dict):
                # Shape where result is already a parsed dict.
                body = inner
            else:
                return []

        if not isinstance(body, dict):
            return []
        return [self._normalize_item(r) for r in body.get("results", [])]

    @staticmethod
    def _normalize_item(record: dict[str, Any]) -> dict[str, Any]:
        """Normalize a get_article_metadata record to the canonical shape.

        get_article_metadata may return nested or flat shapes depending on the
        PubMed MCP server version:

        identifiers field:
          {"pmid": "...", "doi": "...", "pii": "..."}  ← pmid may be here
          or pmid may already be at top-level

        authors field (three observed shapes):
          ["Full Name", ...]                            ← flat strings
          [{"last_name": ..., "fore_name": ..., ...}]  ← structured dicts
          [{"name": ..., "affiliation": ...}]           ← canonical dict form

        publication_date field:
          "YYYY-MM-DD"                                  ← ISO string
          {"year": "YYYY", "month": "MM", "day": "DD"} ← structured dict

        keywords vs mesh_terms:
          keywords: [...]   ← what get_article_metadata returns
          mesh_terms: [...] ← what the ETL expects

        Output is normalized to the ETL's expected canonical shape.
        """
        # Flatten pmid from identifiers if needed
        ids = record.get("identifiers") or {}
        pmid = str(record.get("pmid") or ids.get("pmid") or "")
        doi = record.get("doi") or ids.get("doi")
        pmcid = record.get("pmcid") or ids.get("pmcid")

        # Normalize publication_date: dict → ISO string
        pub_date = record.get("publication_date")
        if isinstance(pub_date, dict):
            y = pub_date.get("year", "")
            m = pub_date.get("month", "01").zfill(2)
            d = pub_date.get("day", "01").zfill(2)
            pub_date = f"{y}-{m}-{d}" if y else None

        # Normalize authors to [{"name": str}] form
        raw_authors = record.get("authors") or []
        authors: list[dict[str, str]] = []
        for a in raw_authors:
            if isinstance(a, str):
                authors.append({"name": a})
            elif isinstance(a, dict):
                if a.get("name"):
                    # Already canonical form
                    entry: dict[str, str] = {"name": a["name"]}
                    if a.get("affiliation"):
                        entry["affiliation"] = a["affiliation"]
                    authors.append(entry)
                elif a.get("last_name") or a.get("fore_name"):
                    # Structured form from get_article_metadata
                    parts = [a.get("fore_name", ""), a.get("last_name", "")]
                    full = " ".join(p for p in parts if p).strip()
                    if full:
                        authors.append({"name": full})

        # Map keywords → mesh_terms (MeSH terms may not be present; use keywords as proxy)
        mesh_terms = record.get("mesh_terms") or record.get("keywords") or []

        # Normalize journal: may be a string or {"title": ..., "iso_abbreviation": ...} dict
        raw_journal = record.get("journal")
        if isinstance(raw_journal, dict):
            journal: str | None = raw_journal.get("title") or raw_journal.get("iso_abbreviation")
        else:
            journal = raw_journal  # str or None

        return {
            "pmid": pmid,
            "title": record.get("title") or "",
            "abstract": record.get("abstract"),
            "authors": authors,
            "journal": journal,
            "publication_date": pub_date,
            "doi": doi,
            "pmcid": pmcid,
            "mesh_terms": [t for t in mesh_terms if isinstance(t, str)],
            "url": record.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""),
        }
