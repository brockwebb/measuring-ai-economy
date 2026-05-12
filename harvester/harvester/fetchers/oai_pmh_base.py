"""OAI-PMH fetcher skeleton.

The Open Archives Initiative Protocol for Metadata Harvesting — used by
arxiv, Zenodo, institutional repositories, JSTOR, Europeana, etc. Phase 1
defines the interface; concrete implementation lands in a future spec when
the first OAI-PMH source needs it.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Iterable

from harvester.fetchers.base import Fetcher
from harvester.types import RawPayload


class OaiPmhFetcher(Fetcher):
    """Subclasses set oai_endpoint() and metadata_prefix()."""

    @abstractmethod
    def oai_endpoint(self) -> str: ...

    @abstractmethod
    def metadata_prefix(self) -> str: ...

    def iter_payloads(
        self,
        query: dict[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> Iterable[RawPayload]:
        raise NotImplementedError(
            "OAI-PMH fetcher implementation deferred to a future spec. "
            "Required interface: ListRecords verb, resumptionToken pagination, "
            "metadataPrefix selection. See https://www.openarchives.org/OAI/openarchivesprotocol.html"
        )
