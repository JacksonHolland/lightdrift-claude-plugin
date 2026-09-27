#!/usr/bin/env python3
"""Emit publishing metadata from a saved Lightdrift search response.

Turns a saved ``/v1/search`` (or ``/v1/similar``) response body into
Schema.org ``ImageObject`` JSON-LD, Open Graph ``og:image`` meta tags and a
plain-text credit line. Offline, standard library only, no network, no key.

This tool does not decide rights. It copies the source-declared values it is
given and refuses to invent a license URL, creator or display name that the
source did not provide. Review the result before publishing.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.parse import urlparse

SCHEMA_CONTEXT = "https://schema.org"
TRACKED_URL_NOTE = (
    "contentUrl is a Lightdrift tracked URL that redirects (302) to a "
    "short-lived signed link; confirm your publishing pipeline follows "
    "redirects or replace it with a stable URL you control."
)


def load_response(path: str) -> dict[str, Any]:
    """Load and minimally validate a saved search response envelope."""
    with open(path, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc.msg})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a JSON object")
    results = data.get("results")
    if not isinstance(results, list):
        raise ValueError(f"{path}: 'results' must be an array")
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: results[{index}] must be an object")
    return data


def _is_absolute_url(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def describe_result(result: dict[str, Any], query_id: Any = None) -> dict[str, Any]:
    """Return a conservative, source-only description of one result."""
    rights = result.get("rights")
    rights = rights if isinstance(rights, dict) else {}

    warnings: list[str] = []
    asset_id = _text(result.get("asset_id"))
    if not asset_id:
        warnings.append("missing asset_id")

    name = _text(result.get("title"))
    if not name:
        warnings.append("no title: structured data and og:image:alt will lack a caption")

    content_url = result.get("file")
    if not _is_absolute_url(content_url):
        warnings.append("file is not an absolute URL; it is omitted from structured data and Open Graph")

    attribution = _text(rights.get("attribution"))
    attribution_required = rights.get("attribution_required")
    if attribution_required is True and not attribution:
        warnings.append("attribution_required is true but no attribution text is present")

    provenance_url = rights.get("provenance_url")
    if provenance_url is not None and not _is_absolute_url(provenance_url):
        warnings.append("rights.provenance_url is not an absolute URL; isBasedOn is omitted")

    license_value = rights.get("license")
    license_url = license_value if _is_absolute_url(license_value) else None
    if license_value is not None and license_url is None:
        warnings.append("rights.license is an identifier, not a URL; 'license' is omitted from JSON-LD")

    if not rights:
        warnings.append("no rights object present: license and credit are unknown")

    width = _int_or_none(result.get("width"))
    height = _int_or_none(result.get("height"))
    if width is None or height is None:
        warnings.append("missing width and/or height; intrinsic-size hints are incomplete")

    return {
        "asset_id": asset_id,
        "query_id": _text(query_id),
        "name": name,
        "content_url": content_url if _is_absolute_url(content_url) else None,
        "content_url_raw": _text(content_url),
        "thumbnail_url": result.get("thumb") if _is_absolute_url(result.get("thumb")) else None,
        "width": width,
        "height": height,
        "attribution": attribution,
        "attribution_required": attribution_required if isinstance(attribution_required, bool) else None,
        "provenance_url": provenance_url if _is_absolute_url(provenance_url) else None,
        "license_id": license_value if isinstance(license_value, str) else None,
        "license_url": license_url,
        "source": _text(result.get("source")),
        "rights_present": bool(rights),
        "warnings": warnings,
    }


def build_image_object(desc: dict[str, Any]) -> dict[str, Any]:
    """Build a Schema.org ImageObject from a description; omit unknown fields."""
    obj: dict[str, Any] = {"@type": "ImageObject"}
    if desc["asset_id"]:
        obj["identifier"] = desc["asset_id"]
    if desc["name"]:
        obj["name"] = desc["name"]
    if desc["content_url"]:
        obj["contentUrl"] = desc["content_url"]
    if desc["thumbnail_url"]:
        obj["thumbnailUrl"] = desc["thumbnail_url"]
    if desc["width"] is not None:
        obj["width"] = desc["width"]
    if desc["height"] is not None:
        obj["height"] = desc["height"]
    if desc["attribution"]:
        obj["creditText"] = desc["attribution"]
    if desc["provenance_url"]:
        obj["isBasedOn"] = desc["provenance_url"]
    if desc["license_url"]:
        obj["license"] = desc["license_url"]
    return obj


def build_graph(response: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-LD document: one ImageObject, or an @graph for many."""
    query_id = response.get("query_id")
    descriptions = [describe_result(item, query_id) for item in response.get("results", [])]
    objects = [build_image_object(desc) for desc in descriptions]
    if len(objects) == 1:
        return {"@context": SCHEMA_CONTEXT, **objects[0]}
    return {"@context": SCHEMA_CONTEXT, "@graph": objects}


def build_opengraph(desc: dict[str, Any]) -> dict[str, str]:
    """Build Open Graph image tags; requires an absolute image URL."""
    tags: dict[str, str] = {}
    if desc["content_url"]:
        tags["og:image"] = desc["content_url"]
        tags["og:image:secure_url"] = desc["content_url"]
    if desc["width"] is not None:
        tags["og:image:width"] = str(desc["width"])
    if desc["height"] is not None:
        tags["og:image:height"] = str(desc["height"])
    if desc["name"]:
        tags["og:image:alt"] = desc["name"]
    return tags


def render_opengraph_html(tags: dict[str, str]) -> str:
    """Render tags as escaped <meta> lines, preserving insertion order."""
    lines = []
    for prop, content in tags.items():
        escaped = (
            content.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        lines.append(f'<meta property="{prop}" content="{escaped}" />')
    return "\n".join(lines)


def build_credit(desc: dict[str, Any]) -> str:
    """Compose a plain credit line from declared attribution and provenance."""
    parts = []
    if desc["attribution"]:
        parts.append(desc["attribution"])
    if desc["provenance_url"]:
        parts.append(desc["provenance_url"])
    if not parts:
        return ""
    return " — ".join(parts)


def build_report(response: dict[str, Any], path: str) -> dict[str, Any]:
    """Build the human-review report that accompanies the emitted metadata."""
    query_id = response.get("query_id")
    descriptions = [describe_result(item, query_id) for item in response.get("results", [])]
    warnings = [f"{d['asset_id'] or 'result'}: {w}" for d in descriptions for w in d["warnings"]]
    return {
        "input": path,
        "query_id": query_id,
        "result_count": len(descriptions),
        "rights_not_evaluated": True,
        "tracked_url_note": TRACKED_URL_NOTE,
        "results": [
            {
                "asset_id": d["asset_id"],
                "name": d["name"],
                "content_url": d["content_url_raw"],
                "content_url_is_absolute": _is_absolute_url(d["content_url_raw"]),
                "width": d["width"],
                "height": d["height"],
                "source": d["source"],
                "rights_present": d["rights_present"],
                "license_id": d["license_id"],
                "license_url_used": d["license_url"],
                "attribution_required": d["attribution_required"],
                "credit": build_credit(d),
                "warnings": d["warnings"],
            }
            for d in descriptions
        ],
        "warnings": warnings,
    }


def is_complete(desc: dict[str, Any]) -> bool:
    """A result is publish-ready for image SEO when these fields exist."""
    if not desc["asset_id"]:
        return False
    if not desc["name"]:
        return False
    if not desc["content_url"]:
        return False
    if desc["width"] is None or desc["height"] is None:
        return False
    return True


def _format_output(fmt: str, response: dict[str, Any], descriptions: list[dict[str, Any]], pretty: bool) -> str:
    indent = 2 if pretty else None
    if fmt == "jsonld":
        return json.dumps(build_graph(response), indent=indent, ensure_ascii=False)
    if fmt == "opengraph":
        tags = build_opengraph(descriptions[0]) if descriptions else {}
        return render_opengraph_html(tags)
    if fmt == "credit":
        return "\n".join(credit for credit in (build_credit(d) for d in descriptions) if credit)
    if fmt == "report":
        return json.dumps(build_report(response, ""), indent=indent, ensure_ascii=False)
    if fmt == "all":
        blocks = {
            "jsonld": json.loads(_format_output("jsonld", response, descriptions, pretty)),
            "opengraph": render_opengraph_html(build_opengraph(descriptions[0])) if descriptions else "",
            "credit": [build_credit(d) for d in descriptions],
        }
        return json.dumps(blocks, indent=indent, ensure_ascii=False)
    raise ValueError(f"unknown format: {fmt}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("response", help="path to a saved /v1/search response JSON file")
    parser.add_argument(
        "--format",
        choices=["jsonld", "opengraph", "credit", "report", "all"],
        default="jsonld",
        help="output to emit (default: jsonld)",
    )
    parser.add_argument("--pretty", action="store_true", help="indent JSON output")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="exit 1 when a result lacks asset_id, title, absolute file URL, width or height",
    )
    args = parser.parse_args(argv)

    try:
        response = load_response(args.response)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    descriptions = [describe_result(item, response.get("query_id")) for item in response.get("results", [])]

    try:
        output = _format_output(args.format, response, descriptions, args.pretty)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if output:
        print(output)

    if args.require_complete:
        incomplete = [d["asset_id"] or "result" for d in descriptions if not is_complete(d)]
        if incomplete:
            print(
                "incomplete results (need asset_id, title, absolute file URL, width, height): "
                + ", ".join(incomplete),
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
