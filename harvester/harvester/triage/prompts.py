"""Prompt templates for LLM triage."""

from __future__ import annotations


def build_triage_prompt(*, title: str, abstract: str, axes_yaml_text: str) -> str:
    """Build the user prompt for a single-document triage call."""
    return (
        "You are triaging a single document against a research-axes rubric.\n\n"
        "Rubric (YAML):\n\n"
        "```yaml\n"
        f"{axes_yaml_text}\n"
        "```\n\n"
        "Document:\n\n"
        f"Title: {title}\n\n"
        f"Abstract: {abstract or '(no abstract)'}\n\n"
        "Task:\n"
        "- Score the document 0.0-1.0 on each axis from the rubric.\n"
        "- The headline `score` is the maximum across axes.\n"
        "- `reason` is one short sentence explaining the headline.\n\n"
        "Respond with JSON only, no commentary:\n"
        "{\n"
        '  "score": float (0.0-1.0),\n'
        '  "axes": { "<axis_name>": float, ... },\n'
        '  "reason": "..."\n'
        "}"
    )
