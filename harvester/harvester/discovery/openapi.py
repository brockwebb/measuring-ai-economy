"""Parser for OpenAPI / Swagger spec JSON.

Handles both:
- OpenAPI 3.x (top-level "openapi" key, "servers" array)
- Swagger 2.0 (top-level "swagger" key, "host" + "basePath")
"""

from __future__ import annotations

from typing import Any


def parse_openapi(spec: dict[str, Any]) -> dict[str, Any]:
    """Parse an OpenAPI/Swagger spec dict.

    Returns:
        {
            "version_kind": "openapi3" | "swagger2" | "unknown",
            "title": str | None,
            "version": str | None,
            "servers": [base_url, ...],
            "paths": [route, ...],
        }
    """
    if "openapi" in spec and str(spec.get("openapi", "")).startswith("3"):
        return _parse_openapi_v3(spec)
    if str(spec.get("swagger", "")) == "2.0":
        return _parse_swagger_v2(spec)
    return {"version_kind": "unknown", "title": None, "version": None, "servers": [], "paths": []}


def _parse_openapi_v3(spec: dict[str, Any]) -> dict[str, Any]:
    info = spec.get("info") or {}
    servers = [s.get("url") for s in spec.get("servers", []) if isinstance(s, dict) and s.get("url")]
    paths = list((spec.get("paths") or {}).keys())
    return {
        "version_kind": "openapi3",
        "title": info.get("title"),
        "version": info.get("version"),
        "servers": servers,
        "paths": paths,
    }


def _parse_swagger_v2(spec: dict[str, Any]) -> dict[str, Any]:
    info = spec.get("info") or {}
    host = spec.get("host")
    base = spec.get("basePath", "")
    schemes = spec.get("schemes") or ["https"]
    servers = [f"{scheme}://{host}{base}" for scheme in schemes if host]
    paths = list((spec.get("paths") or {}).keys())
    return {
        "version_kind": "swagger2",
        "title": info.get("title"),
        "version": info.get("version"),
        "servers": servers,
        "paths": paths,
    }
