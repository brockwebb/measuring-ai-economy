"""MCP-backed fetcher base class.

Invokes Claude via subprocess with an explicit MCP tool call. Matches the
pattern used by existing Wintermute scripts. Records (prompt_hash, mcp_tool,
args, model_receipt) on request_params for stochastic provenance downstream.

Model selection (seldon AD-035, MODEL-001): a subclass names a registry role in
`model_role`; the call execs the lock's CLI with `--model <id>`, the role's
declared `--effort` (seldon AD-036-R8) and the lock's env block
(harvester.model_launch), and a substituted model raises
`seldon.models.ModelSubstituted` before any item is read. Before AD-035 this
call passed no `--model` at all and ran whatever `claude` on PATH defaulted to.
"""

from __future__ import annotations

import hashlib
import json
from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.manifest import RawArchive
from harvester.model_launch import ResponseNotJson, launch_spec, receipt_for, run_cli
from harvester.types import RawPayload


class McpFetcher(Fetcher):
    """Subclasses set mcp_tool and implement args_for_query / items_from_response.

    Class attributes:
        mcp_tool: Primary MCP tool name (used in default prompt + provenance).
        allowed_tools: All MCP tools this fetcher may invoke. Passed to
            `--allowedTools` so the subprocess call doesn't hit the
            interactive permission prompt. Defaults to [mcp_tool]; subclasses
            that orchestrate multiple tools (e.g. search then get_metadata)
            should override this.
        model_role: The seldon registry role the call runs under (AD-035 R4).
            Required: there is no default model, so a subclass without one is
            refused at construction.
    """

    mcp_tool: str = ""
    allowed_tools: list[str] = []  # empty → derived from mcp_tool at call time
    subprocess_timeout: int = 120  # seconds; override for multi-step prompts
    model_role: str = ""

    def __init__(self, archive: RawArchive) -> None:
        super().__init__(archive)
        if not self.model_role:
            raise ValueError(
                f"{type(self).__name__}.model_role is empty; an MCP fetcher names a seldon "
                f"registry role (AD-035 R4)")
        # Resolved once: a run keeps the lock entry it started with (AD-035 R7).
        self._spec = launch_spec(self.model_role)

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
        cli_args = ["-p", prompt, "--output-format", "json"]
        if tools:
            cli_args += ["--allowedTools"] + tools

        proc = run_cli(self._spec, cli_args, timeout=self.subprocess_timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"MCP call failed (exit {proc.returncode}): {proc.stderr.strip()}")

        try:
            # Raises ModelSubstituted (AD-035 R6) before any item is read.
            response, receipt = receipt_for(self._spec, proc.stdout)
        except ResponseNotJson as e:
            raise RuntimeError(f"MCP {e}") from e

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
                    "model_receipt": receipt,
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
