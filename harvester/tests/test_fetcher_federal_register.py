"""Tests for the Federal Register fetcher."""

import json
import re
from pathlib import Path

from harvester.fetchers.federal_register import FederalRegisterFetcher
from harvester.manifest import RawArchive


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "federal_register"


def test_iter_payloads_writes_one_raw_per_result(tmp_path, httpx_mock):
    """Each result in the FR API response becomes one RawPayload."""
    fixture = json.loads((FIXTURE_DIR / "api_page_1.json").read_text())

    # Mock the FR API: every GET request returns the same fixture. We rely on
    # max_pages=1 in the query to stop pagination after one page.
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^https://www\.federalregister\.gov/api/v1/documents\.json.*"),
        json=fixture,
        is_reusable=True,
    )

    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "manifest.parquet")
    fetcher = FederalRegisterFetcher(archive=archive)
    payloads = list(fetcher.iter_payloads({"term": "artificial intelligence", "per_page": 5, "max_pages": 1}))

    assert len(payloads) == len(fixture["results"])
    for p in payloads:
        assert p.source_id == "federal_register"
        assert p.raw_hash.startswith("sha256:")
        assert p.file_path.exists()
        body = json.loads(p.file_path.read_bytes())
        assert "document_number" in body
        assert "title" in body


def test_rate_limit_is_one_per_second(tmp_path):
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "manifest.parquet")
    fetcher = FederalRegisterFetcher(archive=archive)
    rl = fetcher.rate_limit_spec()
    assert rl.requests_per_second == 1.0
