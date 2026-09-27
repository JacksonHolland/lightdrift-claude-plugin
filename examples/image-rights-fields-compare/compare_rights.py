#!/usr/bin/env python3
"""Render an honest, primary-source comparison of image-API rights fields.

Reads a curated dataset (``datasets/providers.json``) whose every cell carries
the exact field name a provider documents and the source URL, capture file and
verbatim quote it came from. Renders Markdown, HTML, a compact matrix or JSON.
Offline, standard library only, no network, no API key.

This tool does not give legal advice and does not decide whether a license fits
a use. It reports what a provider's own documentation says each response
exposes. It refuses to invent a field or a source: with ``--require-sources``
every claim must name a retrievable capture, and a missing file fails the run.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from typing import Any

DEFAULT_DATASET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets", "providers.json")
NOT_EXPOSED = "not exposed"


class DatasetError(ValueError):
    """Raised when the dataset is malformed."""


def load_dataset(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise DatasetError(f"{path}: file not found") from exc
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{path}: not valid JSON ({exc.msg})") from exc
    if not isinstance(data, dict):
        raise DatasetError(f"{path}: top level must be a JSON object")
    return data


def validate_dataset(data: dict[str, Any]) -> None:
    dimensions = data.get("dimensions")
    providers = data.get("providers")
    if not isinstance(dimensions, list) or not dimensions:
        raise DatasetError("dataset must declare a non-empty 'dimensions' array")
    if not isinstance(providers, list) or not providers:
        raise DatasetError("dataset must declare a non-empty 'providers' array")

    dim_ids = []
    for index, dim in enumerate(dimensions):
        if not isinstance(dim, dict) or not dim.get("id") or not dim.get("label"):
            raise DatasetError(f"dimensions[{index}] must have 'id' and 'label'")
        dim_ids.append(dim["id"])
    if len(set(dim_ids)) != len(dim_ids):
        raise DatasetError("dimension ids must be unique")

    provider_ids = []
    for index, provider in enumerate(providers):
        if not isinstance(provider, dict) or not provider.get("id") or not provider.get("name"):
            raise DatasetError(f"providers[{index}] must have 'id' and 'name'")
        provider_ids.append(provider["id"])
        fields = provider.get("fields")
        if not isinstance(fields, dict):
            raise DatasetError(f"providers[{index}] ('{provider['id']}') must have a 'fields' object")
        missing = [dim for dim in dim_ids if dim not in fields]
        if missing:
            raise DatasetError(
                f"providers[{index}] ('{provider['id']}') is missing dimensions: {', '.join(missing)}"
            )
        for dim in dim_ids:
            claim = fields[dim]
            if not isinstance(claim, dict) or "exposed" not in claim:
                raise DatasetError(
                    f"providers[{index}].fields.{dim} must be an object with 'exposed'"
                )
            if not isinstance(claim["exposed"], bool):
                raise DatasetError(
                    f"providers[{index}].fields.{dim}.exposed must be a boolean"
                )
            if claim["exposed"] and not claim.get("field"):
                raise DatasetError(
                    f"providers[{index}].fields.{dim} is exposed but names no 'field'"
                )
    if len(set(provider_ids)) != len(provider_ids):
        raise DatasetError("provider ids must be unique")


def resolve_capture(capture: str, start_dir: str) -> str | None:
    """Find a capture file, searching the dataset directory then ancestors."""
    current = os.path.abspath(start_dir)
    while True:
        candidate = os.path.join(current, capture)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def source_gaps(data: dict[str, Any], base_dir: str) -> list[str]:
    """Return human-readable problems for sources/captures that are missing."""
    problems: list[str] = []
    for provider in data.get("providers", []):
        for dim_id, claim in provider.get("fields", {}).items():
            source_url = claim.get("source_url")
            capture = claim.get("capture")
            if not source_url:
                problems.append(f"{provider['id']}.{dim_id}: missing source_url")
            if not capture:
                problems.append(f"{provider['id']}.{dim_id}: missing capture")
            elif resolve_capture(capture, base_dir) is None:
                problems.append(f"{provider['id']}.{dim_id}: capture not found at {capture}")
            if not claim.get("quote"):
                problems.append(f"{provider['id']}.{dim_id}: missing verbatim quote")
    for source in data.get("out_of_scope", []):
        capture = source.get("capture")
        if capture and resolve_capture(capture, base_dir) is None:
            problems.append(f"out_of_scope[{source.get('provider')}]: capture not found at {capture}")
    return problems


def _cell_text(claim: dict[str, Any], as_html: bool) -> str:
    if not claim.get("exposed"):
        return NOT_EXPOSED
    field = claim.get("field") or ""
    return html.escape(field) if as_html else field


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Image API rights fields: what each search response actually exposes")
    lines.append("")
    lines.append(
        "Comparison of the field names each provider documents for rights/permission "
        "data in an image search or file-info response. Every cell is sourced; "
        "`not exposed` means the provider's own documentation lists no such field."
    )
    lines.append("")
    dimensions = data["dimensions"]
    providers = data["providers"]
    header = ["Rights dimension"] + [p["name"] for p in providers]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for dim in dimensions:
        row = [dim["label"]]
        for provider in providers:
            row.append(_cell_text(provider["fields"][dim["id"]], as_html=False))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    for provider in providers:
        endpoint = provider.get("endpoint")
        lines.append(f"### {provider['name']}" + (f" ({endpoint})" if endpoint else ""))
        for source in provider.get("primary_sources", []):
            lines.append(f"- {source['url']} (captured at `{source['capture']}`)")
        for note in provider.get("notes", []):
            lines.append(f"- Note: {note}")
        lines.append("")
    if data.get("out_of_scope"):
        lines.append("## Out of scope")
        lines.append("")
        for item in data["out_of_scope"]:
            lines.append(f"- **{item['provider']}**: {item['reason']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html(data: dict[str, Any]) -> str:
    dimensions = data["dimensions"]
    providers = data["providers"]
    head = "".join(f"<th>{html.escape(p['name'])}</th>" for p in providers)
    body_rows = []
    for dim in dimensions:
        cells = "".join(
            f"<td><code>{_cell_text(p['fields'][dim['id']], as_html=True)}</code></td>"
            if p["fields"][dim["id"]].get("exposed")
            else "<td class=\"absent\">not exposed</td>"
            for p in providers
        )
        body_rows.append(
            f"<tr><th scope=\"row\">{html.escape(dim['label'])}</th>{cells}</tr>"
        )
    sources = "".join(
        "<li>"
        + html.escape(p["name"])
        + ": "
        + ", ".join(html.escape(s["url"]) for s in p.get("primary_sources", []))
        + "</li>"
        for p in providers
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>Image API rights fields</title>\n</head>\n<body>\n"
        "<h1>Image API rights fields: what each search response actually exposes</h1>\n"
        "<table>\n<thead><tr><th>Rights dimension</th>" + head + "</tr></thead>\n<tbody>\n"
        + "\n".join(body_rows)
        + "\n</tbody>\n</table>\n<p>Cells show the documented field name. "
        "<em>not exposed</em> means the provider's documentation lists no such field.</p>\n"
        "<h2>Sources</h2>\n<ul>" + sources + "</ul>\n</body>\n</html>\n"
    )


def render_matrix(data: dict[str, Any]) -> str:
    dimensions = data["dimensions"]
    providers = data["providers"]
    lines = ["RIGHTS DIMENSION / " + " | ".join(p["name"] for p in providers)]
    for dim in dimensions:
        cells = []
        for provider in providers:
            cells.append(_cell_text(provider["fields"][dim["id"]], as_html=False) if provider["fields"][dim["id"]].get("exposed") else "-")
        lines.append(f"{dim['label']} / " + " | ".join(cells))
    return "\n".join(lines) + "\n"


def render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


RENDERERS = {
    "markdown": render_markdown,
    "html": render_html,
    "matrix": render_matrix,
    "json": render_json,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="path to providers.json")
    parser.add_argument("--format", choices=sorted(RENDERERS), default="markdown")
    parser.add_argument("--output", help="write to this file instead of stdout")
    parser.add_argument(
        "--require-sources",
        action="store_true",
        help="fail (exit 1) when any claim lacks a source, quote or retrievable capture",
    )
    args = parser.parse_args(argv)

    try:
        data = load_dataset(args.dataset)
        validate_dataset(data)
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.require_sources:
        base_dir = os.path.dirname(os.path.abspath(args.dataset))
        problems = source_gaps(data, base_dir)
        if problems:
            print("error: unresolved sources:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1

    rendered = RENDERERS[args.format](data)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
