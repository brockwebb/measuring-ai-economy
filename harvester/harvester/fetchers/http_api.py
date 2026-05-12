"""HTTP API fetcher base class.

Factors out the recurring pattern used by Federal Register, OpenAlex,
Semantic Scholar, PubMed REST, etc.: paginate a JSON endpoint with seen-aware
skipping and rate-limited GETs, writing each item to the raw archive.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Iterable

import httpx

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload

_DEFAULT_PER_PAGE = 50
_DEFAULT_MAX_PAGES = 10
_USER_AGENT = "WintermuteHarvester/0.1 (research; brockwebb45@gmail.com)"


class HttpApiFetcher(Fetcher):
    """Subclasses implement base_url, build_params, extract_items, item_to_payload_kwargs."""

    @abstractmethod
    def base_url(self) -> str: ...

    @abstractmethod
    def build_params(self, query: dict[str, Any], *, page: int) -> dict[str, Any]: ...

    @abstractmethod
    def extract_items(self, response_body: dict[str, Any]) -> Iterable[dict[str, Any]]: ...

    @abstractmethod
    def item_to_payload_kwargs(self, item: dict[str, Any]) -> dict[str, Any]:
        """Return {source_url, content_type, content_bytes} for archive.write()."""

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        per_page = int(query.get("per_page", _DEFAULT_PER_PAGE))
        max_pages = int(query.get("max_pages", _DEFAULT_MAX_PAGES))
        seen = seen or set()

        with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=30) as client:
            for page in range(1, max_pages + 1):
                self._pace()
                params = self.build_params(query, page=page)
                resp = client.get(self.base_url(), params=params)
                resp.raise_for_status()
                body = resp.json()
                items = list(self.extract_items(body))
                if not items:
                    break

                for item in items:
                    kwargs = self.item_to_payload_kwargs(item)
                    source_url = kwargs.get("source_url", "")
                    if source_url and source_url in seen:
                        continue
                    yield self.archive.write(
                        source_id=self.source_id,
                        source_url=source_url,
                        request_params={**params, "item_index": kwargs.get("item_index")},
                        content=kwargs["content_bytes"],
                        content_type=kwargs.get("content_type", "application/json"),
                    )

                if len(items) < per_page:
                    break
