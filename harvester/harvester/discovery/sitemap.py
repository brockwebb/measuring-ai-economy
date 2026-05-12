"""Parser for sitemap.xml (https://www.sitemaps.org/protocol.html).

Two flavors:
- urlset: contains <url> entries with <loc>, optional <lastmod>, <priority>, <changefreq>
- sitemapindex: contains <sitemap> entries pointing to other sitemap files
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def parse_sitemap(xml_text: str) -> dict[str, Any]:
    """Parse a sitemap XML string.

    Returns:
        {
            "kind": "urlset" | "index" | "unknown",
            "entries": [{"loc": str, "lastmod": str | None, "priority": str | None,
                         "changefreq": str | None}, ...],
        }
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {"kind": "unknown", "entries": []}

    tag = root.tag.rsplit("}", 1)[-1]
    entries: list[dict[str, Any]] = []

    if tag == "urlset":
        for url_el in root.findall("sm:url", _NS):
            entry = _extract(url_el, ("loc", "lastmod", "priority", "changefreq"))
            entries.append(entry)
        return {"kind": "urlset", "entries": entries}

    if tag == "sitemapindex":
        for sm_el in root.findall("sm:sitemap", _NS):
            entry = _extract(sm_el, ("loc", "lastmod"))
            entries.append(entry)
        return {"kind": "index", "entries": entries}

    return {"kind": "unknown", "entries": []}


def _extract(element: ET.Element, fields: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        child = element.find(f"sm:{f}", _NS)
        out[f] = child.text.strip() if (child is not None and child.text) else None
    return out
