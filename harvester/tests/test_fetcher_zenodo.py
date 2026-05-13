"""Tests for harvester.fetchers.zenodo.ZenodoFetcher."""

import json
from pathlib import Path

import pytest

from harvester.fetchers.zenodo import ZenodoFetcher


_FIXTURE = Path(__file__).parent / "fixtures" / "zenodo" / "api_page_1.json"


def test_zenodo_fetcher_source_id_is_zenodo():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    assert f.source_id == "zenodo"


def test_zenodo_fetcher_base_url():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    assert f.base_url() == "https://zenodo.org/api/records"


def test_zenodo_fetcher_build_params_includes_keyword_and_pagination():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    params = f.build_params({"keyword": "diffusion model", "per_page": 20}, page=2)
    assert params["q"] == "diffusion model"
    assert params["page"] == 2
    assert params["size"] == 20
    assert params["type"] == "publication"
    assert params["status"] == "published"
    assert params["sort"] == "mostrecent"


def test_zenodo_fetcher_build_params_supports_resource_type_override():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    params = f.build_params({"keyword": "foo", "type": "dataset"}, page=1)
    assert params["type"] == "dataset"


def test_zenodo_fetcher_extract_items_reads_hits_hits():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    body = json.loads(_FIXTURE.read_text())
    items = list(f.extract_items(body))
    assert len(items) > 0
    # Sanity: each hit has an id and metadata
    for item in items[:3]:
        assert "id" in item
        assert "metadata" in item


def test_zenodo_fetcher_item_to_payload_kwargs_uses_canonical_url():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    body = json.loads(_FIXTURE.read_text())
    item = body["hits"]["hits"][0]
    kwargs = f.item_to_payload_kwargs(item)
    assert kwargs["source_url"].startswith("https://zenodo.org/records/")
    assert kwargs["content_type"] == "application/json"
    assert isinstance(kwargs["content_bytes"], bytes)
    # Sorted JSON => deterministic raw_hash later
    reparsed = json.loads(kwargs["content_bytes"])
    assert reparsed["id"] == item["id"]


def test_zenodo_fetcher_build_params_appends_publication_date_range():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    params = f.build_params(
        {
            "keyword": "diffusion model",
            "publication_date_gte": "2026-01-01",
            "publication_date_lte": "2026-05-01",
        },
        page=1,
    )
    assert params["q"] == (
        "diffusion model AND publication_date:[2026-01-01 TO 2026-05-01]"
    )


def test_zenodo_fetcher_build_params_date_range_with_empty_term_strips_leading_space():
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    params = f.build_params(
        {
            "publication_date_gte": "2026-01-01",
            "publication_date_lte": "2026-05-01",
        },
        page=1,
    )
    # With no term, the concatenation starts with a leading space that .strip() removes.
    assert params["q"] == "AND publication_date:[2026-01-01 TO 2026-05-01]"


def test_zenodo_fetcher_build_params_caps_per_page_at_25():
    """Zenodo's unauthenticated API returns 400 for size > 25. The CLI
    defaults per_page to 100, so the fetcher must cap aggressively."""
    f = ZenodoFetcher.__new__(ZenodoFetcher)
    params = f.build_params({"keyword": "test", "per_page": 100}, page=1)
    assert params["size"] == 25
