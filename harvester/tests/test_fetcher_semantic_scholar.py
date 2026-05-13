"""Tests for SemanticScholarFetcher."""

import re
from pathlib import Path

import pytest

from harvester.fetchers.semantic_scholar import SemanticScholarFetcher
from harvester.manifest import RawArchive


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semantic_scholar"


def test_semantic_scholar_yields_one_per_result(tmp_path, httpx_mock):
    fixture = (FIXTURE_DIR / "search_page_1.json").read_text()
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://api\.semanticscholar\.org/graph/v1/paper/search.*"),
        text=fixture,
        is_reusable=True,
    )

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = SemanticScholarFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({
        "keyword": "knowledge graph agent",
        "per_page": 10,
        "max_pages": 1,
    }))

    assert len(payloads) >= 1
    for p in payloads:
        assert p.source_id == "semantic_scholar"
        assert p.raw_hash.startswith("sha256:")
        assert p.source_url


def test_semantic_scholar_respects_seen(tmp_path, httpx_mock):
    fixture = (FIXTURE_DIR / "search_page_1.json").read_text()
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://api\.semanticscholar\.org/graph/v1/paper/search.*"),
        text=fixture,
        is_reusable=True,
    )

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher_a = SemanticScholarFetcher(archive=archive)
    first = list(fetcher_a.iter_payloads({"keyword": "x", "per_page": 10, "max_pages": 1}))
    assert first

    archive2 = RawArchive(root=tmp_path / "raw2", manifest_path=tmp_path / "m2.parquet")
    fetcher_b = SemanticScholarFetcher(archive=archive2)
    seen = {p.source_url for p in first[1:]}
    second = list(fetcher_b.iter_payloads({"keyword": "x", "per_page": 10, "max_pages": 1}, seen=seen))
    assert len(second) == 1
    assert second[0].source_url == first[0].source_url


def test_semantic_scholar_rate_limit(tmp_path):
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = SemanticScholarFetcher(archive=archive)
    rl = fetcher.rate_limit_spec()
    # 1 req/sec unauthenticated, up to 10 with key — both <= 10
    assert 0 < rl.requests_per_second <= 10
