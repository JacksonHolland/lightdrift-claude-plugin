#!/usr/bin/env python3
"""Turn a saved Lightdrift search response into an editorial shortlist export.

Editorial teams often review candidates in a spreadsheet before publishing. A
saved ``/v1/search`` response is nested JSON, which does not paste cleanly into
one. This offline utility reads a saved response and writes:

  * a CSV with one row per result, with rights fields flattened into columns;
  * a JSON shortlist that keeps the complete ``rights`` object per result.

It preserves source declarations and flags rows that still need human review.
It never calls Lightdrift, downloads an image or spends search credits.

Exit codes
    0   the export was written
    1   --strict was set and at least one row lacks required rights fields
    2   usage/input error (unreadable input, missing results array, ...)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

CSV_COLUMNS = [
    "row_index",
    "asset_id",
    "score",
    "title",
    "source",
    "ai_generated",
    "width",
    "height",
    "file_url",
    "thumb_url",
    "rights_license",
    "rights_license_verbatim",
    "rights_commercial",
    "rights_attribution_required",
    "rights_derivatives",
    "rights_share_alike",
    "rights_attribution",
    "rights_provenance_url",
    "rights_basis",
    "review_status",
]

_REVIEW_READY = "ready_for_editorial_review"
_REVIEW_ATTRIBUTION = "needs_attribution_review"
_REVIEW_RIGHTS = "needs_rights_review"


class InputError(Exception):
    """Usage/input problem (exit code 2)."""


def load_results(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise InputError(f"{path} must be an object with a top-level 'results' array")
    return data


def review_status(rights: object) -> str:
    if not isinstance(rights, dict) or not rights:
        return _REVIEW_RIGHTS
    if rights.get("attribution_required") and not rights.get("attribution"):
        return _REVIEW_ATTRIBUTION
    if not rights.get("license"):
        return _REVIEW_RIGHTS
    return _REVIEW_READY


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    return str(value)


def row_for(index: int, result: dict) -> dict:
    rights = result.get("rights") if isinstance(result.get("rights"), dict) else {}
    return {
        "row_index": index,
        "asset_id": result.get("asset_id"),
        "score": result.get("score"),
        "title": result.get("title"),
        "source": result.get("source"),
        "ai_generated": result.get("ai_generated"),
        "width": result.get("width"),
        "height": result.get("height"),
        "file_url": result.get("file"),
        "thumb_url": result.get("thumb"),
        "rights_license": rights.get("license"),
        "rights_license_verbatim": rights.get("license_verbatim"),
        "rights_commercial": rights.get("commercial"),
        "rights_attribution_required": rights.get("attribution_required"),
        "rights_derivatives": rights.get("derivatives"),
        "rights_share_alike": rights.get("share_alike"),
        "rights_attribution": rights.get("attribution"),
        "rights_provenance_url": rights.get("provenance_url"),
        "rights_basis": rights.get("basis"),
        "review_status": review_status(rights),
    }


def build_shortlist(data: dict) -> tuple[str, list[dict]]:
    rows = [
        row_for(i, r if isinstance(r, dict) else {})
        for i, r in enumerate(data["results"])
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row[k]) for k in CSV_COLUMNS})
    csv_text = buffer.getvalue()

    json_rows = []
    for result, row in zip(data["results"], rows):
        rights = result.get("rights") if isinstance(result.get("rights"), dict) else {}
        json_rows.append(
            {
                "row_index": row["row_index"],
                "asset_id": result.get("asset_id"),
                "title": result.get("title"),
                "source": result.get("source"),
                "width": result.get("width"),
                "height": result.get("height"),
                "file": result.get("file"),
                "thumb": result.get("thumb"),
                "rights": rights,
                "review_status": row["review_status"],
            }
        )
    return csv_text, json_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path)
    parser.add_argument("--format", choices=["csv", "json", "both"], default="both")
    parser.add_argument("--output", type=Path, help="base path; suffix added per format")
    parser.add_argument("--stdout", action="store_true", help="print the CSV to stdout")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any row needs rights review")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        data = load_results(args.input)
        csv_text, json_rows = build_shortlist(data)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    needs_review = [r for r in json_rows if r["review_status"] != _REVIEW_READY]

    if args.output:
        base = args.output
        if args.format in ("csv", "both"):
            base.with_suffix(".csv").write_text(csv_text, encoding="utf-8")
        if args.format in ("json", "both"):
            payload = {"query_id": data.get("query_id"), "results": json_rows}
            base.with_suffix(".json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    elif args.format == "json":
        sys.stdout.write(
            json.dumps({"query_id": data.get("query_id"), "results": json_rows}, indent=2) + "\n"
        )
    else:
        sys.stdout.write(csv_text)

    if not args.quiet:
        print(
            f"{len(json_rows)} rows, {len(needs_review)} needing review",
            file=sys.stderr,
        )

    if args.strict and needs_review:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
