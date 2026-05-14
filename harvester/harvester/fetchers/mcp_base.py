"""MCP-backed fetcher base class.

Invokes Claude via subprocess with an explicit MCP tool call. Matches the
pattern used by existing Wintermute scripts. Records (prompt_hash, mcp_tool,
args) on request_params for stochastic provenance downstream.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


_CLAUDE_BIN = os.environ.get("HARVESTER_CLAUDE_BIN", "claude")


class McpFetcher(Fetcher):
    """Subclasses set mcp_tool and implement args_for_query / items_from_response.

    Class attributes:
        mcp_tool: Primary MCP tool name (used in default prompt + provenance).
        allowed_tools: All MCP tools this fetcher may invoke. Passed to
            `--allowedTools` so the subprocess call doesn't hit the
            interactive permission prompt. Defaults to [mcp_tool]; subclasses
            that orchestrate multiple tools (e.g. search then get_metadata)
            should override this.
    """

    mcp_tool: str = ""
    allowed_tools: list[str] = []  # empty → derived from mcp_tool at call time
    subprocess_timeout: int = 120  # seconds; override for multi-step prompts

    @abstractmethod
    def args_for_query(self, query: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def items_from_response(self, response: dict[str, Any]) -> Iterable[dict[str, Any]]: ...

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        seen = seen or set()
        self._pace()
        args = self.args_for_query(query)
        prompt = self._build_mcp_prompt(args)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        tools = self.allowed_tools or ([self.mcp_tool] if self.mcp_tool else [])
        cmd = [_CLAUDE_BIN, "-p", prompt, "--output-format", "json"]
        if tools:
            cmd += ["--allowedTools"] + tools

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.subprocess_timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"MCP call failed (exit {proc.returncode}): {proc.stderr.strip()}")

        try:
            response = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"MCP response was not JSON: {e}; stdout: {proc.stdout[:200]}")

        for item in self.items_from_response(response):
            source_url = item.get("url") or item.get("source_url") or ""
            if source_url and source_url in seen:
                continue
            content = json.dumps(item, sort_keys=True).encode("utf-8")
            yield self.archive.write(
                source_id=self.source_id,
                source_url=source_url,
                request_params={
                    "mcp_tool": self.mcp_tool,
                    "args": args,
                    "prompt_hash": prompt_hash,
                },
                content=content,
                content_type="application/json",
            )

    def _build_mcp_prompt(self, args: dict[str, Any]) -> str:
        """Build the prompt for invoking the MCP tool. Override for custom shape."""
        return (
            f"Call the {self.mcp_tool} tool with these arguments and return ONLY the "
            f"tool's raw JSON output, no commentary:\n\n{json.dumps(args, indent=2)}"
        )
