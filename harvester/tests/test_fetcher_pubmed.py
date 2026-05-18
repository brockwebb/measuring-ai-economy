"""Tests for PubMedFetcher (direct NCBI E-utilities path, 2026-05-17).

Replaces the prior MCP-prompt-mediated test surface. Pattern follows
test_fetcher_arxiv.py — direct httpx mocks via the pytest-httpx fixture.
"""

import json
import re
from pathlib import Path

from harvester.fetchers.pubmed import PubMedFetcher
from harvester.manifest import RawArchive
from harvester.types import RateLimit


# ---------------------------------------------------------------------------
# Cheap unit tests — no HTTP
# ---------------------------------------------------------------------------

def _archive(tmp_path: Path) -> RawArchive:
    return RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "m.parquet")


def test_pubmed_fetcher_source_id_is_pubmed(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    assert f.source_id == "pubmed"


def test_pubmed_fetcher_rate_limit_authenticated_rate(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    rl = f.rate_limit_spec()
    assert isinstance(rl, RateLimit)
    # 9 req/sec is the polite rate when authenticated (under NCBI's 10/sec cap)
    assert rl.requests_per_second == 9.0
    assert rl.max_retries == 3


def test_pubmed_fetcher_args_for_query_uses_keyword(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    out = f.args_for_query({"keyword": "machine learning"})
    assert out["term"] == "machine learning"


def test_pubmed_fetcher_args_for_query_accepts_term(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    out = f.args_for_query({"term": "explicit term"})
    assert out["term"] == "explicit term"


def test_pubmed_fetcher_args_for_query_defaults(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    out = f.args_for_query({"keyword": "x"})
    assert out["per_page"] == 50
    assert out["max_pages"] == 4


def test_pubmed_fetcher_iso_date_full(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    assert f._iso_date("2024 Jun 15") == "2024-06-15"


def test_pubmed_fetcher_iso_date_month_only(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    assert f._iso_date("2024 Aug") == "2024-08-01"


def test_pubmed_fetcher_iso_date_year_only(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    assert f._iso_date("2024") == "2024-01-01"


def test_pubmed_fetcher_iso_date_empty(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    assert f._iso_date("") is None


def test_pubmed_fetcher_normalize_full_record(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    summary = {
        "title": "Deep learning",
        "authors": [{"name": "LeCun Y"}, {"name": "Bengio Y"}, {"name": "Hinton G"}],
        "source": "Nature",
        "pubdate": "2015 May 28",
        "articleids": [
            {"idtype": "doi", "value": "10.1038/nature14539"},
            {"idtype": "pmcid", "value": None},
            {"idtype": "pubmed", "value": "26017442"},
        ],
    }
    rec = f._normalize("26017442", summary, "Abstract text.")
    assert rec["pmid"] == "26017442"
    assert rec["title"] == "Deep learning"
    assert rec["abstract"] == "Abstract text."
    assert rec["authors"] == [{"name": "LeCun Y"}, {"name": "Bengio Y"}, {"name": "Hinton G"}]
    assert rec["journal"] == "Nature"
    assert rec["publication_date"] == "2015-05-28"
    assert rec["doi"] == "10.1038/nature14539"
    assert rec["pmcid"] is None
    assert rec["mesh_terms"] == []
    assert rec["url"] == "https://pubmed.ncbi.nlm.nih.gov/26017442/"


def test_pubmed_fetcher_normalize_handles_missing_fields(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    rec = f._normalize("999", {"title": "Sparse record"}, "")
    assert rec["pmid"] == "999"
    assert rec["title"] == "Sparse record"
    assert rec["abstract"] is None
    assert rec["authors"] == []
    assert rec["journal"] is None
    assert rec["publication_date"] is None
    assert rec["doi"] is None
    assert rec["pmcid"] is None
    assert rec["url"] == "https://pubmed.ncbi.nlm.nih.gov/999/"


def test_pubmed_fetcher_normalize_falls_back_to_fulljournalname(tmp_path):
    f = PubMedFetcher(archive=_archive(tmp_path))
    rec = f._normalize("1", {"title": "x", "fulljournalname": "Journal of X"}, "")
    assert rec["journal"] == "Journal of X"


# ---------------------------------------------------------------------------
# Integration: iter_payloads end-to-end via httpx_mock
# ---------------------------------------------------------------------------

_ESEARCH_BODY = json.dumps({
    "esearchresult": {
        "idlist": ["100", "200", "300"],
        "count": "3",
    }
})

_ESUMMARY_BODY = json.dumps({
    "result": {
        "uids": ["100", "200", "300"],
        "100": {
            "title": "First",
            "authors": [{"name": "Smith A"}],
            "source": "Journal A",
            "pubdate": "2024 Jan 5",
            "articleids": [{"idtype": "doi", "value": "10.1/aaa"}],
        },
        "200": {
            "title": "Second",
            "authors": [{"name": "Jones B"}],
            "source": "Journal B",
            "pubdate": "2024 Feb",
            "articleids": [],
        },
        "300": {
            "title": "Third",
            "authors": [],
            "source": "Journal C",
            "pubdate": "2024",
            "articleids": [],
        },
    }
})

_EFETCH_BODY = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>100</PMID>
      <Article><Abstract><AbstractText>Abstract for first.</AbstractText></Abstract></Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>200</PMID>
      <Article><Abstract>
        <AbstractText Label="BACKGROUND">Bg text.</AbstractText>
        <AbstractText Label="METHODS">Methods text.</AbstractText>
      </Abstract></Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>300</PMID>
      <Article></Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


def _wire_eutils_mocks(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r".*esearch\.fcgi.*"),
        text=_ESEARCH_BODY,
        is_reusable=True,
    )
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r".*esummary\.fcgi.*"),
        text=_ESUMMARY_BODY,
        is_reusable=True,
    )
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r".*efetch\.fcgi.*"),
        text=_EFETCH_BODY,
        is_reusable=True,
    )


def test_pubmed_iter_payloads_yields_one_per_pmid(tmp_path, httpx_mock):
    _wire_eutils_mocks(httpx_mock)
    fetcher = PubMedFetcher(archive=_archive(tmp_path))
    payloads = list(fetcher.iter_payloads({"keyword": "test query", "per_page": 3, "max_pages": 1}))
    assert len(payloads) == 3
    for p in payloads:
        assert p.source_id == "pubmed"
        assert p.raw_hash.startswith("sha256:")
        assert p.source_url.startswith("https://pubmed.ncbi.nlm.nih.gov/")


def test_pubmed_iter_payloads_record_has_correct_shape(tmp_path, httpx_mock):
    _wire_eutils_mocks(httpx_mock)
    fetcher = PubMedFetcher(archive=_archive(tmp_path))
    payloads = list(fetcher.iter_payloads({"keyword": "test", "per_page": 3, "max_pages": 1}))
    rec = json.loads(payloads[0].file_path.read_text())
    expected_keys = {"pmid", "title", "abstract", "authors", "journal",
                     "publication_date", "doi", "pmcid", "mesh_terms", "url"}
    assert expected_keys <= set(rec.keys())
    assert rec["pmid"] == "100"
    assert rec["abstract"] == "Abstract for first."
    assert rec["doi"] == "10.1/aaa"
    assert rec["publication_date"] == "2024-01-05"


def test_pubmed_iter_payloads_labeled_abstract_sections(tmp_path, httpx_mock):
    _wire_eutils_mocks(httpx_mock)
    fetcher = PubMedFetcher(archive=_archive(tmp_path))
    payloads = list(fetcher.iter_payloads({"keyword": "test", "per_page": 3, "max_pages": 1}))
    rec_200 = next(json.loads(p.file_path.read_text()) for p in payloads
                   if json.loads(p.file_path.read_text())["pmid"] == "200")
    assert "**BACKGROUND:**" in rec_200["abstract"]
    assert "Bg text." in rec_200["abstract"]
    assert "**METHODS:**" in rec_200["abstract"]


def test_pubmed_iter_payloads_respects_seen(tmp_path, httpx_mock):
    _wire_eutils_mocks(httpx_mock)
    fetcher = PubMedFetcher(archive=_archive(tmp_path))
    seen = {"https://pubmed.ncbi.nlm.nih.gov/200/"}
    payloads = list(fetcher.iter_payloads({"keyword": "test", "per_page": 3, "max_pages": 1}, seen=seen))
    urls = [p.source_url for p in payloads]
    assert "https://pubmed.ncbi.nlm.nih.gov/200/" not in urls
    assert "https://pubmed.ncbi.nlm.nih.gov/100/" in urls
    assert "https://pubmed.ncbi.nlm.nih.gov/300/" in urls


def test_pubmed_iter_payloads_empty_search_stops_pagination(tmp_path, httpx_mock):
    empty_search = json.dumps({"esearchresult": {"idlist": [], "count": "0"}})
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r".*esearch\.fcgi.*"),
        text=empty_search,
        is_reusable=True,
    )
    fetcher = PubMedFetcher(archive=_archive(tmp_path))
    payloads = list(fetcher.iter_payloads({"keyword": "test", "per_page": 5, "max_pages": 5}))
    assert payloads == []


def test_pubmed_iter_payloads_no_term_returns_empty(tmp_path):
    """No keyword/term in query -> generator yields nothing without making HTTP calls."""
    fetcher = PubMedFetcher(archive=_archive(tmp_path))
    payloads = list(fetcher.iter_payloads({"per_page": 5, "max_pages": 1}))
    assert payloads == []
