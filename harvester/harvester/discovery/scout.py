"""MUI scout — probes a source's machine-readable affordances."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from harvester.discovery.llms_txt import parse_llms_txt
from harvester.discovery.openapi import parse_openapi
from harvester.discovery.robots import parse_robots_txt
from harvester.discovery.sitemap import parse_sitemap
from harvester.discovery.types import DiscoveryNotes


class MuiScout:
    """Probes /llms.txt, /robots.txt, /sitemap.xml, /.well-known/openapi.json,
    and the base page's <link rel='alternate' type='application/rss+xml'> and
    <script type='application/ld+json'> elements."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def probe(self, base_url: str) -> DiscoveryNotes:
        """Make all probes and assemble DiscoveryNotes. No exceptions escape —
        probe errors are captured in probe_errors."""
        base = base_url.rstrip("/")
        probe_errors: dict[str, str] = {}

        llms_txt = self._fetch_llms_txt(base, probe_errors)
        robots = self._fetch_robots(base, probe_errors)
        sitemap_urls = self._collect_sitemap_urls(base, robots, probe_errors)
        openapi_spec = self._fetch_openapi(base, probe_errors)
        rss_feeds, schema_types = self._fetch_base_page(base, probe_errors)

        return DiscoveryNotes(
            base_url=base,
            probed_at=datetime.now(timezone.utc),
            llms_txt=llms_txt,
            robots_rules=robots,
            sitemap_urls=sitemap_urls,
            openapi_spec=openapi_spec,
            rss_feeds=rss_feeds,
            schema_org_types=schema_types,
            probe_errors=probe_errors,
        )

    def _fetch_llms_txt(self, base: str, errors: dict[str, str]) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=self._timeout) as c:
                resp = c.get(f"{base}/llms.txt")
                if resp.status_code != 200:
                    return None
                return parse_llms_txt(resp.text)
        except Exception as e:
            errors["llms_txt"] = str(e)
            return None

    def _fetch_robots(self, base: str, errors: dict[str, str]) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=self._timeout) as c:
                resp = c.get(f"{base}/robots.txt")
                if resp.status_code != 200:
                    return None
                return parse_robots_txt(resp.text)
        except Exception as e:
            errors["robots_txt"] = str(e)
            return None

    def _collect_sitemap_urls(self, base: str, robots: dict[str, Any] | None,
                              errors: dict[str, str]) -> list[str]:
        urls: list[str] = []
        try:
            with httpx.Client(timeout=self._timeout) as c:
                resp = c.get(f"{base}/sitemap.xml")
                if resp.status_code == 200:
                    parsed = parse_sitemap(resp.text)
                    if parsed["kind"] == "urlset":
                        urls.extend(e["loc"] for e in parsed["entries"] if e.get("loc"))
                    elif parsed["kind"] == "index":
                        urls.extend(e["loc"] for e in parsed["entries"] if e.get("loc"))
        except Exception as e:
            errors["sitemap"] = str(e)

        if robots and robots.get("sitemaps"):
            for s in robots["sitemaps"]:
                if s and s not in urls:
                    urls.append(s)
        return urls

    def _fetch_openapi(self, base: str, errors: dict[str, str]) -> dict[str, Any] | None:
        """Try /.well-known/openapi.json first, then /openapi.json."""
        for path in ["/.well-known/openapi.json", "/openapi.json"]:
            try:
                with httpx.Client(timeout=self._timeout) as c:
                    resp = c.get(f"{base}{path}")
                    if resp.status_code == 200:
                        try:
                            spec = resp.json()
                        except json.JSONDecodeError:
                            continue
                        return parse_openapi(spec)
            except Exception as e:
                errors[f"openapi:{path}"] = str(e)
        return None

    def _fetch_base_page(self, base: str, errors: dict[str, str]) -> tuple[list[str], list[str]]:
        """Fetch base URL and extract <link rel='alternate' type='application/rss+xml'>
        and <script type='application/ld+json'> @type values."""
        rss_feeds: list[str] = []
        schema_types: list[str] = []
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as c:
                resp = c.get(base)
                if resp.status_code != 200:
                    return rss_feeds, schema_types
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.find_all("link", rel="alternate"):
                    if link.get("type") == "application/rss+xml" and link.get("href"):
                        rss_feeds.append(link["href"])
                for script in soup.find_all("script", type="application/ld+json"):
                    if not script.string:
                        continue
                    try:
                        data = json.loads(script.string)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and "@type" in data:
                        t = data["@type"]
                        if isinstance(t, str):
                            schema_types.append(t)
                        elif isinstance(t, list):
                            schema_types.extend(str(x) for x in t)
        except Exception as e:
            errors["base_page"] = str(e)
        return rss_feeds, schema_types
