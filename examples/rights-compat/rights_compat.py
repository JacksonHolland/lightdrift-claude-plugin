#!/usr/bin/env python3
"""Offline rights-compatibility and credit planner for saved image-search results.

Given a saved Lightdrift-style search response and an intended-use profile, this
tool reports, per asset, whether the source-declared rights flags are compatible
with the intended use, which assets need human review, and a ready-to-publish
credit block for assets that declare an attribution requirement.

It is deliberately conservative. It reads only local files, makes no network
calls, never approves a candidate, and never claims legal clearance. Every report
carries ``rights_clearance: "not_evaluated"``. ``None`` (a missing or null flag)
is treated as unknown and routed to review, not as permission.

Exit codes:
    0  every asset is ok or ok_with_attribution
    1  at least one asset is review or blocked
    2  invalid input

Standard library only. Python 3.10+.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
STATUS_OK = "ok"
STATUS_ATTRIBUTION = "ok_with_attribution"
STATUS_REVIEW = "review"
STATUS_BLOCKED = "blocked"

_USE_KEYS = ("commercial", "derivatives", "share_alike_ok", "attribution_in_output")

# Reasons that block use. These are declared prohibitions, not unknowns.
_BLOCK_REASONS = {
    "license_declares_noncommercial": "The source declares commercial use is not permitted, but commercial use was requested.",
    "license_forbids_derivatives": "The source declares derivatives are not permitted, but derivative use was requested.",
}

# Reasons that require a human decision. These are unknowns or obligations.
_REVIEW_REASONS = {
    "commercial_permission_unknown": "Commercial permission is not declared (null); treat as unknown, not as permission.",
    "derivative_permission_unknown": "Derivative permission is not declared (null); treat as unknown, not as permission.",
    "share_alike_obligation": "The source declares share-alike; the intended use was not marked as accepting that obligation.",
    "attribution_required_but_missing": "Attribution is required but no attribution string is present; hold the asset.",
    "attribution_requirement_unknown": "It is not declared whether attribution is required while attribution in output was requested.",
    "license_unknown": "No normalized license identifier is present; the source's terms were not resolved.",
    "rights_missing": "The asset carries no rights object; nothing about its terms is known.",
}

LIMITATIONS = [
    "This tool reads source-declared metadata; it does not verify the source or the declaration.",
    "It does not assess likeness, trademark, property, model or other rights beyond copyright.",
    "A pass is not legal clearance: rights_clearance remains not_evaluated for every asset.",
    "It does not check revocations or whether a downloaded file matches the selected asset ID.",
    "It does not evaluate where the credit is rendered or whether a CMS preserved it.",
]


class InputError(ValueError):
    """Raised for malformed or inconsistent local input."""


def _load_json(path: Path) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputError(f"{path} is not valid JSON: {exc}") from exc


def load_use_profile(path: Path) -> dict:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise InputError("use profile must be a JSON object")
    missing = [k for k in _USE_KEYS if k not in data]
    if missing:
        raise InputError(f"use profile missing required keys: {', '.join(missing)}")
    for key in _USE_KEYS:
        if not isinstance(data[key], bool):
            raise InputError(f"use profile key {key!r} must be a boolean")
    return {k: data[k] for k in _USE_KEYS}


def _extract_assets(data: object) -> list[dict]:
    """Accept a full search response (results) or a normalized assets list."""
    if isinstance(data, dict) and "results" in data:
        records = data["results"]
    elif isinstance(data, dict) and "assets" in data:
        records = data["assets"]
    elif isinstance(data, list):
        records = data
    else:
        raise InputError("response must contain a 'results' or 'assets' array, or be an array")
    if not isinstance(records, list):
        raise InputError("results/assets must be an array")
    if not records:
        raise InputError("no assets to evaluate")
    seen: set[str] = set()
    assets: list[dict] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise InputError(f"asset at index {index} is not an object")
        asset_id = record.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise InputError(f"asset at index {index} has no non-empty string asset_id")
        if asset_id in seen:
            raise InputError(f"duplicate asset_id {asset_id!r}; de-duplicate inputs before use")
        seen.add(asset_id)
        rights = record.get("rights")
        if rights is not None and not isinstance(rights, dict):
            raise InputError(f"asset {asset_id!r} rights must be an object or null")
        assets.append(
            {
                "asset_id": asset_id,
                "source": record.get("source"),
                "rights": rights,
            }
        )
    return assets


def _tri(value: object) -> bool | None:
    """Return True/False for a declared boolean, None when absent or null."""
    if value is True:
        return True
    if value is False:
        return False
    return None


def _has_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def evaluate_asset(asset: dict, use: dict) -> dict:
    rights = asset.get("rights")
    if not isinstance(rights, dict):
        return {
            "asset_id": asset["asset_id"],
            "status": STATUS_REVIEW,
            "reason_codes": ["rights_missing"],
            "reasons": [_REVIEW_REASONS["rights_missing"]],
            "license": None,
            "attribution": None,
            "provenance_url": None,
        }

    commercial = _tri(rights.get("commercial"))
    derivatives = _tri(rights.get("derivatives"))
    share_alike = _tri(rights.get("share_alike"))
    attribution_required = _tri(rights.get("attribution_required"))
    attribution = rights.get("attribution")
    license_id = rights.get("license")
    provenance_url = rights.get("provenance_url")

    block_codes: list[str] = []
    review_codes: list[str] = []

    if use["commercial"] and commercial is False:
        block_codes.append("license_declares_noncommercial")
    if use["derivatives"] and derivatives is False:
        block_codes.append("license_forbids_derivatives")

    if not block_codes:
        if use["commercial"] and commercial is None:
            review_codes.append("commercial_permission_unknown")
        if use["derivatives"] and derivatives is None:
            review_codes.append("derivative_permission_unknown")
        if (
            use["derivatives"]
            and share_alike is True
            and not use["share_alike_ok"]
        ):
            review_codes.append("share_alike_obligation")
        if attribution_required is True and not _has_text(attribution):
            review_codes.append("attribution_required_but_missing")
        if attribution_required is None and use["attribution_in_output"]:
            review_codes.append("attribution_requirement_unknown")
        if not _has_text(license_id):
            review_codes.append("license_unknown")

    if block_codes:
        status = STATUS_BLOCKED
        codes = block_codes
    elif review_codes:
        status = STATUS_REVIEW
        codes = review_codes
    elif attribution_required is True:
        status = STATUS_ATTRIBUTION
        codes = []
    else:
        status = STATUS_OK
        codes = []

    reasons = [
        _BLOCK_REASONS[c] if c in _BLOCK_REASONS else _REVIEW_REASONS[c] for c in codes
    ]
    return {
        "asset_id": asset["asset_id"],
        "status": status,
        "reason_codes": codes,
        "reasons": reasons,
        "license": license_id if _has_text(license_id) else None,
        "attribution": attribution if _has_text(attribution) else None,
        "provenance_url": provenance_url if _has_text(provenance_url) else None,
    }


def _credit_line(decision: dict) -> str:
    text = decision["attribution"].strip()
    if decision["provenance_url"]:
        return f"- {text} ({decision['provenance_url']})"
    return f"- {text}"


def build_report(data: object, use: dict) -> dict:
    assets = _extract_assets(data)
    decisions = [evaluate_asset(a, use) for a in assets]
    decisions.sort(key=lambda d: d["asset_id"])
    summary = {
        "assets": len(decisions),
        "ok": sum(1 for d in decisions if d["status"] == STATUS_OK),
        "ok_with_attribution": sum(1 for d in decisions if d["status"] == STATUS_ATTRIBUTION),
        "review": sum(1 for d in decisions if d["status"] == STATUS_REVIEW),
        "blocked": sum(1 for d in decisions if d["status"] == STATUS_BLOCKED),
    }
    credit_decisions = [
        d
        for d in decisions
        if d["attribution"]
        and d["status"] in (STATUS_OK, STATUS_ATTRIBUTION)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "rights_compat.py",
        "rights_clearance": "not_evaluated",
        "use_profile": dict(use),
        "summary": summary,
        "decisions": decisions,
        "credit_lines": [_credit_line(d) for d in credit_decisions],
        "limitations": LIMITATIONS,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Image rights compatibility report",
        "",
        "> `rights_clearance: not_evaluated` — this report is a review aid, not legal clearance.",
        "",
        "## Intended use",
        "",
    ]
    for key in _USE_KEYS:
        lines.append(f"- {key}: `{str(report['use_profile'][key]).lower()}`")
    s = report["summary"]
    lines += [
        "",
        "## Summary",
        "",
        f"- assets: {s['assets']}",
        f"- ok: {s['ok']}",
        f"- ok_with_attribution: {s['ok_with_attribution']}",
        f"- review: {s['review']}",
        f"- blocked: {s['blocked']}",
        "",
        "## Per-asset decisions",
        "",
        "| asset_id | status | license | reason codes |",
        "| --- | --- | --- | --- |",
    ]
    for d in report["decisions"]:
        codes = ", ".join(d["reason_codes"]) or "-"
        lines.append(
            f"| {d['asset_id']} | {d['status']} | {d['license'] or '-'} | {codes} |"
        )
    lines += ["", "## Credit block", ""]
    if report["credit_lines"]:
        lines += report["credit_lines"]
    else:
        lines.append("_No asset in this set both passed and requires attribution._")
    lines += ["", "## Limitations", ""]
    lines += [f"- {item}" for item in report["limitations"]]
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check saved image-search rights against an intended use and build credits."
    )
    parser.add_argument("response", type=Path, help="saved search response or normalized assets JSON")
    parser.add_argument("use_profile", type=Path, help="intended-use profile JSON")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="output format (default: json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write the report here instead of stdout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        data = _load_json(args.response)
        use = load_use_profile(args.use_profile)
        report = build_report(data, use)
    except InputError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    if args.format == "markdown":
        rendered = render_markdown(report)
    else:
        rendered = json.dumps(report, indent=2) + "\n"

    if args.output is not None:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"error": f"cannot write {args.output}: {exc}"}), file=sys.stderr)
            return 2
    else:
        sys.stdout.write(rendered)

    return 0 if report["summary"]["review"] == 0 and report["summary"]["blocked"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
