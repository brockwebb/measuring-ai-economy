"""Tests for skeleton fetchers (OaiPmh, Dcat, BulkDownload).

These ABCs don't have concrete implementations yet — Phase 1 lays down the
interfaces and Phase 3+ adds real fetchers. Subclasses without implementations
raise NotImplementedError when iter_payloads is called.
"""


import pytest

from harvester.fetchers.oai_pmh_base import OaiPmhFetcher
from harvester.fetchers.dcat_base import DcatFetcher
from harvester.fetchers.bulk_download_base import BulkDownloadFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


def _archive(tmp_path):
    return RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")


class _FakeOaiPmh(OaiPmhFetcher):
    source_id = "fake_oai"
    def rate_limit_spec(self): return RateLimit(requests_per_second=1.0)
    def oai_endpoint(self): return "https://example.com/oai"
    def metadata_prefix(self): return "oai_dc"


class _FakeDcat(DcatFetcher):
    source_id = "fake_dcat"
    def rate_limit_spec(self): return RateLimit(requests_per_second=1.0)
    def catalog_url(self): return "https://example.com/catalog.jsonld"


class _FakeBulk(BulkDownloadFetcher):
    source_id = "fake_bulk"
    def rate_limit_spec(self): return RateLimit(requests_per_second=1.0)
    def snapshot_url(self): return "https://example.com/snapshot.tar.gz"
    def parse_snapshot(self, path): return iter([])


def test_oai_pmh_iter_raises_not_implemented(tmp_path):
    fetcher = _FakeOaiPmh(archive=_archive(tmp_path))
    with pytest.raises(NotImplementedError, match="OAI-PMH"):
        list(fetcher.iter_payloads({}))


def test_dcat_iter_raises_not_implemented(tmp_path):
    fetcher = _FakeDcat(archive=_archive(tmp_path))
    with pytest.raises(NotImplementedError, match="DCAT"):
        list(fetcher.iter_payloads({}))


def test_bulk_download_iter_raises_not_implemented(tmp_path):
    fetcher = _FakeBulk(archive=_archive(tmp_path))
    with pytest.raises(NotImplementedError, match="bulk download"):
        list(fetcher.iter_payloads({}))
