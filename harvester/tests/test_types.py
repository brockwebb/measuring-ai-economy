"""Type-level tests for the harvester data models."""

from datetime import datetime
from pathlib import Path
from harvester.types import RawPayload, Row, ParsedDoc, RateLimit


def test_raw_payload_is_immutable_and_typed():
    payload = RawPayload(
        raw_hash="abc123",
        file_path=Path("/tmp/x.json"),
        content_type="application/json",
        fetched_at=datetime(2026, 5, 11, 22, 0, 0),
        source_id="federal_register",
        source_url="https://example.com/doc",
        request_params={"q": "ai"},
    )
    assert payload.raw_hash == "abc123"
    assert payload.source_id == "federal_register"


def test_row_carries_target_table_and_data():
    row = Row(
        target_table="harvest.federal_register_documents",
        data={"document_number": "2026-12345", "title": "Test"},
    )
    assert row.target_table == "harvest.federal_register_documents"
    assert row.data["document_number"] == "2026-12345"


def test_rate_limit_has_seconds_between_requests():
    rl = RateLimit(requests_per_second=1.0, max_retries=3, backoff_seconds=[2, 5, 15])
    assert rl.seconds_between_requests == 1.0
    assert rl.max_retries == 3
    assert rl.backoff_seconds == [2, 5, 15]


def test_parsed_doc_holds_title_url_payload_and_rows():
    doc = ParsedDoc(
        title="Some Rule",
        source_url="https://example.com/doc",
        published_date=datetime(2026, 5, 11).date(),
        rows=[
            Row(target_table="harvest.federal_register_documents", data={"x": 1}),
        ],
        metadata={"document_type": "Rule"},
    )
    assert doc.title == "Some Rule"
    assert len(doc.rows) == 1
