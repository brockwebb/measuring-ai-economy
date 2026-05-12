"""DCAT-AP / CKAN catalog fetcher skeleton.

For data portals using the DCAT vocabulary (data.gov, Eurostat, OECD.AI).
Phase 1 defines the interface; concrete implementation lands in a future
spec when the first DCAT source needs it.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


class DcatFetcher(Fetcher):
    """Subclasses set catalog_url() pointing at a DCAT catalog (JSON-LD or RDF)."""

    @abstractmethod
    def catalog_url(self) -> str: ...

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        raise NotImplementedError(
            "DCAT/CKAN fetcher implementation deferred to a future spec. "
            "Required interface: catalog parsing (dcat:dataset + dcat:distribution), "
            "DCAT-AP property extraction, CKAN package_search API. "
            "See https://www.w3.org/TR/vocab-dcat-3/"
        )
