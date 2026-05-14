"""PubMed fetcher.

Backed by the PubMed MCP server (mcp__claude_ai_PubMed__search_articles).
Calls the MCP tool via the McpFetcher base, which shells out to `claude -p`
and parses the JSON response. Each query term produces one MCP call →
one search response → up to `max_results` items.

The MCP response shape may be either the tool's raw JSON envelope
({"results": [...]}) or Claude's --output-format json wrapping
({"type": "result", "result": "<json string>", ...}). items_from_response
handles both.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from harvester.fetchers.mcp_base import McpFetcher
from harvester.types import RateLimit


class PubMedFetcher(McpFetcher):
    source_id = "pubmed"
    mcp_tool = "mcp__claude_ai_PubMed__search_articles"

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
            "max_results": int(query.get("per_page", 10)),
        }

    def items_from_response(self, response: dict[str, Any]) -> Iterable[dict[str, Any]]:
        # Unwrap Claude's --output-format json envelope if present. The
        # `result` field is a string containing the tool's actual JSON.
        body = response
        if isinstance(response, dict) and isinstance(response.get("result"), str):
            try:
                body = json.loads(response["result"])
            except json.JSONDecodeError:
                # Result was free-form text, not JSON. Nothing to extract.
                return []

        if not isinstance(body, dict):
            return []
        return body.get("results", [])
