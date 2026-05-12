"""Tests for HttpApiFetcher base."""

import json
import re

from harvester.fetchers.http_api import HttpApiFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


class _FakeHttpApiFetcher(HttpApiFetcher):
    source_id = "fake"

    def rate_limit_spec(self) -> RateLimit:
        return RateLimit(requests_per_second=10.0)

    def base_url(self) -> str:
        return "https://api.example.com/v1/items"

    def build_params(self, query, *, page):
        return {"q": query.get("q", ""), "page": page, "per_page": query.get("per_page", 50)}

    def extract_items(self, body):
        return body.get("results", [])

    def item_to_payload_kwargs(self, item):
        return {
            "source_url": item["url"],
            "content_type": "application/json",
            "content_bytes": json.dumps(item, sort_keys=True).encode("utf-8"),
        }


def test_http_api_fetcher_yields_payloads(tmp_path, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://api\.example\.com/v1/items.*"),
        json={"results": [
            {"id": 1, "url": "https://example.com/a"},
            {"id": 2, "url": "https://example.com/b"},
        ]},
        is_reusable=True,
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeHttpApiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "foo", "per_page": 2, "max_pages": 1}))
    assert len(payloads) == 2
    urls = [p.source_url for p in payloads]
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls


def test_http_api_fetcher_honors_seen_set(tmp_path, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://api\.example\.com/v1/items.*"),
        json={"results": [
            {"id": 1, "url": "https://example.com/a"},
            {"id": 2, "url": "https://example.com/b"},
        ]},
        is_reusable=True,
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeHttpApiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "foo", "per_page": 2, "max_pages": 1},
                                          seen={"https://example.com/a"}))
    assert len(payloads) == 1
    assert payloads[0].source_url == "https://example.com/b"


def test_http_api_fetcher_stops_on_empty_page(tmp_path, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://api\.example\.com/v1/items.*"),
        json={"results": []},
        is_reusable=True,
    )
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = _FakeHttpApiFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"q": "foo", "max_pages": 5}))
    assert payloads == []
