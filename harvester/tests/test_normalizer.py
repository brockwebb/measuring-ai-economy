"""Tests for the inbox markdown normalizer."""

from datetime import date
import yaml

from harvester.normalizer import emit_markdown
from harvester.types import ParsedDoc, Row


def test_emit_writes_frontmatter_and_body(tmp_path):
    doc = ParsedDoc(
        title="Test FR Document",
        source_url="https://example.com/doc",
        published_date=date(2026, 5, 11),
        rows=[
            Row(target_table="harvest.document_metadata", data={"source_id": "federal_register"}),
            Row(target_table="harvest.federal_register_documents", data={"document_number": "2026-12345"}),
        ],
        metadata={
            "document_type": "Rule",
            "agencies": ["Department of Commerce"],
            "document_number": "2026-12345",
            "abstract": "This rule does things.",
        },
    )
    inbox_path = emit_markdown(
        doc,
        inbox_dir=tmp_path,
        source_id="federal_register",
        raw_hash="sha256:abc",
        harvester_run_id=42,
        pg_refs=[
            {"table": "harvest.document_metadata", "pk": 100},
            {"table": "harvest.federal_register_documents", "pk": 200},
        ],
        expected_schema_version=2,
    )
    text = inbox_path.read_text()
    assert text.startswith("---\n")
    parts = text.split("---\n", 2)
    assert len(parts) >= 3, "expected three sections: empty, frontmatter, body"
    frontmatter = yaml.safe_load(parts[1])
    body = parts[2]

    assert frontmatter["title"] == "Test FR Document"
    assert frontmatter["source_url"] == "https://example.com/doc"
    assert frontmatter["source_type"] == "federal_register"
    assert frontmatter["raw_hash"] == "sha256:abc"
    assert frontmatter["harvester_run_id"] == 42
    assert frontmatter["expected_schema_version"] == 2
    assert frontmatter["pg_refs"] == [
        {"table": "harvest.document_metadata", "pk": 100},
        {"table": "harvest.federal_register_documents", "pk": 200},
    ]
    assert "This rule does things." in body
    assert "Test FR Document" in body


def test_emit_path_includes_doc_id(tmp_path):
    doc = ParsedDoc(
        title="X",
        source_url="https://example.com/y",
        published_date=date(2026, 5, 11),
        rows=[],
        metadata={"document_number": "2026-99999"},
    )
    path = emit_markdown(
        doc,
        inbox_dir=tmp_path,
        source_id="federal_register",
        raw_hash="sha256:zzz",
        harvester_run_id=1,
        pg_refs=[],
        expected_schema_version=2,
    )
    assert path.parent == tmp_path
    assert path.name.endswith(".md")
    assert "2026-99999" in path.name or "zzz" in path.name
