"""RSS/Atom feed fetcher base class.

Uses feedparser to handle both flavors. Subclasses provide feed_urls()
and entry_to_payload_kwargs().
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Iterable

import feedparser
import httpx

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload

_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"


class RssFetcher(Fetcher):
    """Subclasses provide feed_urls() and entry_to_payload_kwargs()."""

    @abstractmethod
    def feed_urls(self, query: dict[str, Any]) -> Iterable[str]: ...

    @abstractmethod
    def entry_to_payload_kwargs(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Return {source_url, content_type, content_bytes} for archive.write()."""

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        seen = seen or set()
        with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=30) as client:
            for feed_url in self.feed_urls(query):
                self._pace()
                resp = client.get(feed_url)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries:
                    kwargs = self.entry_to_payload_kwargs(dict(entry))
                    source_url = kwargs.get("source_url", "")
                    if source_url and source_url in seen:
                        continue
                    yield self.archive.write(
                        source_id=self.source_id,
                        source_url=source_url,
                        request_params={"feed_url": feed_url},
                        content=kwargs["content_bytes"],
                        content_type=kwargs.get("content_type", "application/json"),
                    )
