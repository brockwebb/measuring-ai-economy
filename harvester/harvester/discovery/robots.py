"""Parser for /robots.txt files.

Honors the de facto robots.txt format:
- User-agent: <name>    groups directives by agent
- Allow: <path>         path the agent may visit
- Disallow: <path>      path the agent may not visit
- Crawl-delay: <seconds> minimum seconds between requests
- Sitemap: <url>         file-level sitemap declaration (not per-agent)
"""

from __future__ import annotations

from typing import Any


def parse_robots_txt(text: str) -> dict[str, Any]:
    """Parse a robots.txt string.

    Returns:
        {
            "groups": {
                "<agent>": {"allow": [paths], "disallow": [paths], "crawl_delay": int | None},
                ...
            },
            "sitemaps": [urls],
        }
    """
    groups: dict[str, dict[str, Any]] = {}
    sitemaps: list[str] = []
    current_agent: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()

        if key == "user-agent":
            current_agent = value
            groups.setdefault(current_agent, {"allow": [], "disallow": [], "crawl_delay": None})
        elif key == "allow" and current_agent is not None:
            groups[current_agent]["allow"].append(value)
        elif key == "disallow" and current_agent is not None:
            groups[current_agent]["disallow"].append(value)
        elif key == "crawl-delay" and current_agent is not None:
            try:
                groups[current_agent]["crawl_delay"] = int(value)
            except ValueError:
                pass
        elif key == "sitemap":
            sitemaps.append(value)

    return {"groups": groups, "sitemaps": sitemaps}
