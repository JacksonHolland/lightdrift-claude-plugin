#!/usr/bin/env python3
"""Validate a saved Lightdrift ``/v1/search`` response against the published schema.

The validator is offline and standard-library only. By default it checks a saved
response against a bundled snapshot of the ``SearchResponse`` schema extracted
from the published Lightdrift OpenAPI document, and it can instead load a fresh
``openapi.json`` (or a standalone schema) with ``--schema``.

It reports two severities:

* **errors** — the value contradicts the schema's declared type, enum or numeric
  range (for example ``k``-style integers, or an unknown ``query_type``);
* **warnings** — the value is schema-valid but a documented expectation is not
  present (a missing field, a relative file URL, a duplicate asset ID).

Semantic checks are limited to what the documentation states; the tool never
invents a field, a license value or a benchmark. Exit codes: ``0`` clean, ``1``
schema errors (or warnings under ``--strict``) and ``2`` for an unreadable or
malformed response or schema.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.parse import urlparse

JSON_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "null": lambda v: v is None,
}

DEFAULT_SCHEMA = "schema/search-response.schema.json"

RESULT_REQUIREMENTS = ("asset_id", "title", "source", "width", "height", "file", "rights")
RIGHT_REQUIREMENTS = ("license", "attribution", "provenance_url")


class InputError(ValueError):
    pass


def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: not valid JSON ({exc.msg})") from exc


def extract_schema(document: dict[str, Any]) -> dict[str, Any]:
    """Accept a full OpenAPI document, a schema with ``$defs``, or a bare schema."""
    if not isinstance(document, dict):
        raise InputError("schema must be a JSON object")
    schemas = document.get("components", {}).get("schemas", {})
    if isinstance(schemas, dict) and "SearchResponse" in schemas:
        def rewrite(node: Any) -> Any:
            if isinstance(node, dict):
                return {k: (v.replace("#/components/schemas/", "#/$defs/") if k == "$ref" and isinstance(v, str) else rewrite(v)) for k, v in node.items()}
            if isinstance(node, list):
                return [rewrite(v) for v in node]
            return node

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": rewrite(schemas["SearchResponse"].get("properties", {})),
            "$defs": {
                name: rewrite(schemas[name])
                for name in ("Result", "Rights")
                if name in schemas
            },
        }
    if "properties" in document or "$defs" in document:
        return document
    raise InputError("schema does not look like a SearchResponse schema or OpenAPI document")


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    if not ref.startswith("#/"):
        raise InputError(f"unsupported $ref {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node.get(part)
        if node is None:
            raise InputError(f"unresolvable $ref {ref!r}")
    return node


def _type_errors(value: Any, declared: Any) -> list[str]:
    names = declared if isinstance(declared, list) else [declared]
    if any(JSON_TYPES.get(name, lambda _v: True)(value) for name in names):
        return []
    return [f"expected {' or '.join(names)}, got {type(value).__name__}"]


def validate_node(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str, errors: list[dict[str, str]], warnings: list[dict[str, str]]) -> None:
    schema = _resolve(schema, root)

    if "anyOf" in schema:
        branch_errors: list[list[dict[str, str]]] = []
        for option in schema["anyOf"]:
            sub_errors: list[dict[str, str]] = []
            validate_node(value, option, root, path, sub_errors, [])
            branch_errors.append(sub_errors)
        if not any(not branch for branch in branch_errors):
            joined = "; ".join(item["message"] for branch in branch_errors for item in branch)
            errors.append({"path": path, "message": f"matches no allowed shape ({joined})"})
        return

    if "type" in schema:
        for message in _type_errors(value, schema["type"]):
            errors.append({"path": path, "message": message})
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append({"path": path, "message": f"{value!r} is not one of {schema['enum']}"})

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append({"path": path, "message": f"{value} is below the minimum {schema['minimum']}"})
        if "maximum" in schema and value > schema["maximum"]:
            errors.append({"path": path, "message": f"{value} is above the maximum {schema['maximum']}"})

    properties = schema.get("properties")
    if isinstance(properties, dict) and isinstance(value, dict):
        for key, item in value.items():
            if key in properties:
                validate_node(item, properties[key], root, f"{path}.{key}", errors, warnings)
            else:
                warnings.append({"path": f"{path}.{key}", "message": "field is not in the documented schema"})
        return

    if isinstance(schema.get("items"), dict) and isinstance(value, list):
        for index, item in enumerate(value):
            validate_node(item, schema["items"], root, f"{path}[{index}]", errors, warnings)


def _is_absolute_url(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def semantic_checks(response: dict[str, Any], warnings: list[dict[str, str]]) -> None:
    if not isinstance(response.get("query_id"), str) or not response.get("query_id"):
        warnings.append({"path": "query_id", "message": "response has no query_id"})

    results = response.get("results")
    if not isinstance(results, list):
        return
    if not results:
        warnings.append({"path": "results", "message": "response contains no results"})

    seen: dict[str, int] = {}
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        prefix = f"results[{index}]"
        for field in RESULT_REQUIREMENTS:
            if field not in result or result.get(field) in (None, ""):
                warnings.append({"path": f"{prefix}.{field}", "message": f"documented per-result field is absent ({field})"})
        asset_id = result.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            if asset_id in seen:
                warnings.append({"path": f"{prefix}.asset_id", "message": f"duplicate asset_id, also at results[{seen[asset_id]}]"})
            else:
                seen[asset_id] = index
        for field in ("file", "thumb"):
            if field in result and result.get(field) not in (None, "") and not _is_absolute_url(result.get(field)):
                warnings.append({"path": f"{prefix}.{field}", "message": "value is not an absolute http(s) URL"})
        for field in ("width", "height"):
            value = result.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value <= 0:
                warnings.append({"path": f"{prefix}.{field}", "message": f"pixel {field} must be positive"})
        rights = result.get("rights")
        if isinstance(rights, dict):
            for field in RIGHT_REQUIREMENTS:
                if field not in rights or rights.get(field) in (None, ""):
                    warnings.append({"path": f"{prefix}.rights.{field}", "message": f"documented rights field is absent ({field})"})
            if rights.get("attribution_required") is True and not rights.get("attribution"):
                warnings.append({"path": f"{prefix}.rights.attribution", "message": "attribution_required is true but no attribution is declared"})


def validate(response: Any, schema: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    validate_node(response, schema, schema, "$", errors, warnings)
    if isinstance(response, dict):
        semantic_checks(response, warnings)
    return {
        "status": "invalid" if errors else ("warnings" if warnings else "valid"),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a saved Lightdrift /v1/search response against the published schema.")
    parser.add_argument("response", help="path to a saved search response JSON file")
    parser.add_argument("--schema", default=None, help=f"schema or OpenAPI JSON (default: {DEFAULT_SCHEMA})")
    parser.add_argument("--report", help="write a JSON validation report to this path")
    parser.add_argument("--strict", action="store_true", help="exit 1 when warnings are present")
    parser.add_argument("--quiet", action="store_true", help="suppress the human-readable summary on standard error")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        schema_doc = load_json(args.schema or DEFAULT_SCHEMA)
        schema = extract_schema(schema_doc)
        response = load_json(args.response)
    except InputError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2

    report = validate(response, schema)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    if not args.quiet:
        for item in report["errors"]:
            print(f"error: {item['path']}: {item['message']}", file=sys.stderr)
        for item in report["warnings"]:
            print(f"warning: {item['path']}: {item['message']}", file=sys.stderr)
        print(f"{report['status']}: {report['error_count']} error(s), {report['warning_count']} warning(s)", file=sys.stderr)
    if report["error_count"]:
        return 1
    if args.strict and report["warning_count"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
