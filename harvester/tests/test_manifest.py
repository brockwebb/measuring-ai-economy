"""Tests for the raw archive + parquet manifest."""

from pathlib import Path
import pyarrow.parquet as pq

from harvester.manifest import RawArchive


def test_archive_writes_bytes_and_returns_payload(tmp_path):
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "manifest.parquet")
    payload = archive.write(
        source_id="federal_register",
        source_url="https://example.com/doc",
        request_params={"q": "ai"},
        content=b'{"hello": "world"}',
        content_type="application/json",
    )
    assert payload.raw_hash.startswith("sha256:")
    assert payload.file_path.exists()
    assert payload.file_path.read_bytes() == b'{"hello": "world"}'
    assert payload.source_id == "federal_register"


def test_archive_appends_to_manifest(tmp_path):
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "manifest.parquet")
    archive.write(
        source_id="federal_register",
        source_url="https://example.com/doc-1",
        request_params={"q": "ai"},
        content=b"first",
        content_type="text/plain",
    )
    archive.write(
        source_id="federal_register",
        source_url="https://example.com/doc-2",
        request_params={"q": "ai"},
        content=b"second",
        content_type="text/plain",
    )
    table = pq.read_table(tmp_path / "manifest.parquet")
    assert table.num_rows == 2
    urls = table.column("source_url").to_pylist()
    assert "https://example.com/doc-1" in urls
    assert "https://example.com/doc-2" in urls


def test_archive_deduplicates_by_hash(tmp_path):
    """Writing identical content twice should reuse the existing file but still append manifest rows."""
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "manifest.parquet")
    p1 = archive.write(
        source_id="federal_register",
        source_url="https://example.com/doc",
        request_params={},
        content=b"identical",
        content_type="text/plain",
    )
    p2 = archive.write(
        source_id="federal_register",
        source_url="https://example.com/doc",
        request_params={},
        content=b"identical",
        content_type="text/plain",
    )
    assert p1.raw_hash == p2.raw_hash
    assert p1.file_path == p2.file_path
    # Manifest gets both rows — provenance preservation
    table = pq.read_table(tmp_path / "manifest.parquet")
    assert table.num_rows == 2


def test_archive_writes_under_yyyy_mm_subdir(tmp_path):
    archive = RawArchive(root=tmp_path / "raw", manifest_path=tmp_path / "manifest.parquet")
    p = archive.write(
        source_id="federal_register",
        source_url="https://example.com/doc",
        request_params={},
        content=b"x",
        content_type="text/plain",
    )
    parts = p.file_path.relative_to(tmp_path / "raw").parts
    assert parts[0] == "federal_register"
    # parts[1] should be YYYY-MM
    yyyy, mm = parts[1].split("-")
    assert len(yyyy) == 4 and len(mm) == 2
