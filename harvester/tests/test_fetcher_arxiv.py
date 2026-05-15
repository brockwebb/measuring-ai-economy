"""Tests for ArxivFetcher."""

import re
from pathlib import Path


from harvester.fetchers.arxiv import ArxivFetcher
from harvester.manifest import RawArchive


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "arxiv"


def test_arxiv_fetcher_yields_one_per_entry(tmp_path, httpx_mock):
    feed = (FIXTURE_DIR / "api_page_1.xml").read_text()
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://export\.arxiv\.org/api/query.*"),
        text=feed,
        is_reusable=True,
    )

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = ArxivFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({
        "categories": ["cs.AI"],
        "per_page": 5,
        "max_pages": 1,
    }))
    assert len(payloads) >= 1
    for p in payloads:
        assert p.source_id == "arxiv"
        assert p.raw_hash.startswith("sha256:")
        assert p.source_url.startswith("http://arxiv.org/abs/") or p.source_url.startswith("https://arxiv.org/abs/")


def test_arxiv_fetcher_respects_seen(tmp_path, httpx_mock):
    feed = (FIXTURE_DIR / "api_page_1.xml").read_text()
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://export\.arxiv\.org/api/query.*"),
        text=feed,
        is_reusable=True,
    )

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher_a = ArxivFetcher(archive=archive)
    first = list(fetcher_a.iter_payloads({"categories": ["cs.AI"], "per_page": 5, "max_pages": 1}))
    assert first

    archive2 = RawArchive(root=tmp_path / "raw2", manifest_path=tmp_path / "m2.parquet")
    fetcher_b = ArxivFetcher(archive=archive2)
    seen = {p.source_url for p in first[1:]}
    second = list(fetcher_b.iter_payloads({"categories": ["cs.AI"], "per_page": 5, "max_pages": 1}, seen=seen))
    assert len(second) == 1
    assert second[0].source_url == first[0].source_url


def test_arxiv_fetcher_rate_limit_is_polite(tmp_path):
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")
    fetcher = ArxivFetcher(archive=archive)
    rl = fetcher.rate_limit_spec()
    assert rl.requests_per_second <= 0.5
