"""Tests for openapi.json parser."""

import json
from pathlib import Path

from harvester.discovery.openapi import parse_openapi

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discovery"


def test_parse_openapi_v3():
    spec_json = (FIXTURE_DIR / "openapi_v3.json").read_text()
    spec = json.loads(spec_json)
    result = parse_openapi(spec)
    assert result["version_kind"] == "openapi3"
    assert result["title"] == "Example API"
    assert "https://api.example.com/v1" in result["servers"]
    assert "/documents" in result["paths"]
    assert "/documents/{id}" in result["paths"]


def test_parse_swagger_v2():
    spec_json = (FIXTURE_DIR / "openapi_v2_swagger.json").read_text()
    spec = json.loads(spec_json)
    result = parse_openapi(spec)
    assert result["version_kind"] == "swagger2"
    assert result["title"] == "Legacy API"
    assert "https://legacy.example.com/api" in result["servers"] or "http://legacy.example.com/api" in result["servers"]
    assert "/items" in result["paths"]


def test_parse_unknown_format_returns_empty():
    result = parse_openapi({"foo": "bar"})
    assert result["version_kind"] == "unknown"
    assert result["paths"] == []
