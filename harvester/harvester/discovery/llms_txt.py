"""Parser for /llms.txt files (https://llmstxt.org).

The format is markdown-flavored:
- First H1 line is the site title
- Optional blockquote summary (lines starting with >)
- Optional ## section headers, each followed by bullet lists like
  - [label](url): description
"""

from __future__ import annotations

import re
from typing import Any

_TITLE_RE = re.compile(r"^#\s+(.+)$")
_SECTION_RE = re.compile(r"^##\s+(.+)$")
_BLOCKQUOTE_RE = re.compile(r"^>\s*(.*)$")
_LINK_RE = re.compile(r"^-\s+\[([^\]]+)\]\(([^)]+)\)(?::\s+(.+))?$")


def parse_llms_txt(text: str) -> dict[str, Any]:
    """Parse an llms.txt string into structured dict.

    Returns:
        {
            "title": str | None,
            "summary": str | None,
            "sections": {section_name: [{"label": ..., "url": ..., "description": ...}, ...]},
        }
    """
    title: str | None = None
    summary_lines: list[str] = []
    sections: dict[str, list[dict[str, str | None]]] = {}
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        m_section = _SECTION_RE.match(line)
        if m_section:
            current_section = m_section.group(1).strip()
            sections.setdefault(current_section, [])
            continue

        if title is None:
            m_title = _TITLE_RE.match(line)
            if m_title:
                title = m_title.group(1).strip()
                continue

        if current_section is None:
            m_blockquote = _BLOCKQUOTE_RE.match(line)
            if m_blockquote:
                summary_lines.append(m_blockquote.group(1).strip())
                continue

        if current_section is not None:
            m_link = _LINK_RE.match(line)
            if m_link:
                sections[current_section].append({
                    "label": m_link.group(1),
                    "url": m_link.group(2),
                    "description": m_link.group(3),
                })

    summary = " ".join(s for s in summary_lines if s).strip() or None
    return {"title": title, "summary": summary, "sections": sections}
