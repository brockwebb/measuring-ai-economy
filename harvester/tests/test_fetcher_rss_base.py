"""Tests for RssFetcher base."""

from pathlib import Path

from harvester.fetchers.rss_base import RssFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


class _FakeRssFetcher(RssFetcher):
    source_id = "fake_rss"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=2.0)

    def feed_urls(self, query):
        return ["https://example.com/feed.xml"]

    def entry_to_payload_kwargs(self, entry):
        return {
            "source_url": entry.get("link", ""),
            "content_type": "application/json",
            "content_bytes": str(entry).encode("utf-8"),
        }


def test_rss_fetcher_yields_one_per_atom_entry(tmp_path, httpx_mock):
    feed_text = (FIXTURE_DIR / "feed_atom.xml").read_text()
    httpx_mock.add_response(method="GET", url="https://example.com/feed.xml", text=feed_text)
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeRssFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}))
    assert len(payloads) == 2
    urls = [p.source_url for p in payloads]
    assert "https://example.com/posts/1" in urls
    assert "https://example.com/posts/2" in urls


def test_rss_fetcher_yields_one_per_rss2_item(tmp_path, httpx_mock):
    feed_text = (FIXTURE_DIR / "feed_rss2.xml").read_text()
    httpx_mock.add_response(method="GET", url="https://example.com/feed.xml", text=feed_text)
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeRssFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}))
    assert len(payloads) == 2
    urls = [p.source_url for p in payloads]
    assert "https://example.com/items/a" in urls


def test_rss_fetcher_respects_seen(tmp_path, httpx_mock):
    feed_text = (FIXTURE_DIR / "feed_rss2.xml").read_text()
    httpx_mock.add_response(method="GET", url="https://example.com/feed.xml", text=feed_text)
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeRssFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({}, seen={"https://example.com/items/a"}))
    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/items/b"
