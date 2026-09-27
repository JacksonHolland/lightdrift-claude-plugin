#!/usr/bin/env python3
"""Offline acceptance-record checker for the Lightdrift image-workflow pilot.

Given the five artifacts a $500 pilot run produces (confirmed brief list,
request log, candidate log, shortlist, and optional buyer-recorded answers),
this utility checks the published acceptance criteria A1-A7 and emits one
machine-readable acceptance record. It makes no network call, needs no API key
and spends no search credit.

It is honest about what it can and cannot establish: A1-A4 are checked from the
run artifacts, while A5-A7 are *buyer-recorded* and are reported as
`unchecked` (and the overall verdict `incomplete`) until the buyer supplies
their answers. The checker never infers a buyer decision from the files.

Usage:
    python3 pilot_acceptance.py \
        --briefs fixtures/briefs-20.json \
        --requests fixtures/requests.jsonl \
        --candidates fixtures/candidates.jsonl \
        --shortlist fixtures/shortlist.json \
        [--buyer buyer-answers.json] \
        [--expected-count 20] \
        [--record acceptance-record.json] \
        [--markdown acceptance-record.md]

Exit codes:
    0  all seven criteria pass
    1  at least one checked criterion fails
    2  malformed or unreadable input / schema error
    3  no failure, but one or more buyer-recorded criteria are unchecked
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CRITERIA = {
    "A1": "the twenty briefs used are the buyer-confirmed list",
    "A2": "one searchable request per brief is produced",
    "A3": "candidates + provenance returned for every brief that returned results",
    "A4": "every candidate row carries its rights fields and a review_status",
    "A5": "usable candidate found for >= 16 of 20 briefs (buyer-recorded)",
    "A6": "required credit/source info survives to the review step (buyer-recorded)",
    "A7": "the buyer can run the handoff on their own briefs (buyer-recorded)",
}

RIGHTS_FIELDS = (
    "license",
    "license_verbatim",
    "commercial",
    "derivatives",
    "share_alike",
    "attribution_required",
    "attribution",
    "provenance_url",
    "basis",
)
REVIEW_STATUSES = (
    "ready_for_editorial_review",
    "needs_attribution_review",
    "needs_rights_review",
)

PASS, FAIL, UNCHECKED = "pass", "fail", "unchecked"


class InputError(Exception):
    """Raised for malformed input; maps to exit code 2."""


def _load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read JSON {path}: {exc}") from exc


def _load_jsonl(path: Path):
    rows = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise InputError(
                        f"malformed JSONL at {path}:{lineno}: {exc}"
                    ) from exc
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    return rows


def _criterion(ident, status, detail, evidence):
    return {
        "id": ident,
        "requirement": CRITERIA[ident],
        "status": status,
        "detail": detail,
        "evidence": evidence,
    }


def check_a1(briefs_doc, requests, expected_count):
    evidence = []
    briefs = briefs_doc.get("briefs")
    if not isinstance(briefs, list):
        raise InputError("briefs file has no 'briefs' array")
    ids = []
    for index, brief in enumerate(briefs):
        if not isinstance(brief, dict) or "id" not in brief:
            raise InputError(f"brief at index {index} has no 'id'")
        ids.append(str(brief["id"]))
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    req_ids = [str(r.get("brief_id")) for r in requests]
    problems = []
    if len(briefs) != expected_count:
        problems.append(f"brief count {len(briefs)} != {expected_count}")
    if duplicates:
        problems.append(f"duplicate brief ids {duplicates}")
    if sorted(ids) != sorted(req_ids):
        problems.append("requested brief ids do not match confirmed brief list")
    status = FAIL if problems else PASS
    evidence.append({"brief_ids": ids, "requests": len(requests)})
    return _criterion(
        "A1",
        status,
        "; ".join(problems) if problems else f"{len(ids)} confirmed briefs match requests",
        evidence,
    )


def check_a2(requests, expected_count):
    problems = []
    if len(requests) != expected_count:
        problems.append(f"request count {len(requests)} != {expected_count}")
    for index, req in enumerate(requests):
        if not isinstance(req, dict) or not req.get("brief_id"):
            problems.append(f"request at index {index} has no brief_id")
        if not req.get("query"):
            problems.append(f"request at index {index} has no query")
    status = FAIL if problems else PASS
    return _criterion(
        "A2",
        status,
        "; ".join(problems) if problems else f"exactly {expected_count} requests",
        [{"requests": len(requests)}],
    )


def check_a3(candidates, brief_ids):
    by_brief = {}
    problems = []
    zero_result = []
    for cand in candidates:
        if not isinstance(cand, dict) or "brief_id" not in cand:
            problems.append("candidate record has no brief_id")
            continue
        brief_id = str(cand["brief_id"])
        response = cand.get("response")
        if not isinstance(response, dict):
            problems.append(f"{brief_id}: no response envelope")
            continue
        results = response.get("results")
        if not isinstance(results, list):
            problems.append(f"{brief_id}: response.results is not a list")
            continue
        by_brief[brief_id] = len(results)
        if len(results) == 0:
            zero_result.append(brief_id)
        for result in results:
            if not isinstance(result, dict):
                problems.append(f"{brief_id}: non-object result")
                continue
            rights = result.get("rights")
            if not isinstance(rights, dict):
                problems.append(f"{brief_id}: result missing rights object")
    missing = [bid for bid in brief_ids if bid not in by_brief]
    if missing:
        problems.append(f"no candidate record for briefs {missing}")
    status = FAIL if problems else PASS
    evidence = [{"candidate_briefs": len(by_brief), "empty_result_briefs": zero_result}]
    return _criterion(
        "A3",
        status,
        "; ".join(problems)
        if problems
        else f"{len(by_brief)} briefs have candidate records ({len(zero_result)} with result_count 0)",
        evidence,
    )


def check_a4(shortlist_doc):
    results = shortlist_doc.get("results")
    if not isinstance(results, list):
        raise InputError("shortlist file has no 'results' array")
    problems = []
    for index, row in enumerate(results):
        if not isinstance(row, dict):
            problems.append(f"shortlist row {index} is not an object")
            continue
        rights = row.get("rights")
        if not isinstance(rights, dict):
            problems.append(f"row {index}: missing rights object")
            continue
        absent = [field for field in RIGHTS_FIELDS if field not in rights]
        if absent:
            problems.append(f"row {index}: rights fields absent {absent}")
        if row.get("review_status") not in REVIEW_STATUSES:
            problems.append(f"row {index}: bad review_status {row.get('review_status')!r}")
    status = FAIL if problems else PASS
    return _criterion(
        "A4",
        status,
        "; ".join(problems) if problems else f"{len(results)} rows carry rights + review_status",
        [{"rows": len(results)}],
    )


def _buyer_criterion(ident, buyer, key, predicate, detail_pass, detail_fail):
    if buyer is None or key not in buyer:
        return _criterion(
            ident,
            UNCHECKED,
            f"{key} not supplied by buyer; requires buyer's acceptance sheet",
            [{"key": key}],
        )
    value = buyer[key]
    ok = predicate(value)
    return _criterion(
        ident,
        PASS if ok else FAIL,
        detail_pass(value) if ok else detail_fail(value),
        [{"key": key, "value": value}],
    )


def check_a5(buyer, expected_count):
    threshold = max(16, expected_count - 4)
    return _buyer_criterion(
        "A5",
        buyer,
        "usable_briefs",
        lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= threshold,
        lambda v: f"buyer reported {v} usable briefs (>= {threshold})",
        lambda v: f"buyer reported {v} usable briefs (< {threshold})",
    )


def check_a6(buyer):
    return _buyer_criterion(
        "A6",
        buyer,
        "attribution_survives",
        lambda v: v is True,
        lambda v: "buyer confirmed credit/source survives for selected assets",
        lambda v: "buyer reported credit/source does not survive",
    )


def check_a7(buyer):
    return _buyer_criterion(
        "A7",
        buyer,
        "handoff_run",
        lambda v: v is True,
        lambda v: "buyer confirmed they ran the handoff on their own briefs",
        lambda v: "buyer reported the handoff was not run",
    )


def _markdown(record):
    lines = [
        "# Image-workflow pilot — acceptance record",
        "",
        f"- Pilot: `image-workflow-pilot-v1`",
        f"- Overall verdict: **{record['verdict']}**",
        f"- Checked: {record['summary']['checked']} / 7 "
        f"(pass {record['summary']['pass']}, fail {record['summary']['fail']}, "
        f"unchecked {record['summary']['unchecked']})",
        f"- Generated from: `{record['source']}`",
        "",
        "| # | Requirement | Status | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for criterion in record["criteria"]:
        detail = str(criterion["detail"]).replace("|", "\\|")
        lines.append(
            f"| {criterion['id']} | {criterion['requirement']} | "
            f"{criterion['status']} | {detail} |"
        )
    lines += [
        "",
        "`unchecked` criteria are buyer-recorded (A5-A7). This file does not",
        "infer a buyer decision; supply a buyer answers file to complete them.",
        "",
    ]
    return "\n".join(lines)


def build_record(args):
    briefs_doc = _load_json(args.briefs)
    requests = _load_jsonl(args.requests)
    candidates = _load_jsonl(args.candidates)
    shortlist_doc = _load_json(args.shortlist)
    buyer = _load_json(args.buyer) if args.buyer else None

    brief_ids = [str(b["id"]) for b in briefs_doc.get("briefs", [])]
    criteria = [
        check_a1(briefs_doc, requests, args.expected_count),
        check_a2(requests, args.expected_count),
        check_a3(candidates, brief_ids),
        check_a4(shortlist_doc),
        check_a5(buyer, args.expected_count),
        check_a6(buyer),
        check_a7(buyer),
    ]
    counts = {PASS: 0, FAIL: 0, UNCHECKED: 0}
    for criterion in criteria:
        counts[criterion["status"]] += 1
    if counts[FAIL]:
        verdict = "not_accepted"
    elif counts[UNCHECKED]:
        verdict = "incomplete"
    else:
        verdict = "accepted"
    return {
        "pilot_id": "image-workflow-pilot-v1",
        "schema_version": 1,
        "source": str(args.briefs.parent),
        "expected_count": args.expected_count,
        "buyer_answers_supplied": buyer is not None,
        "criteria": criteria,
        "summary": {
            "checked": counts[PASS] + counts[FAIL],
            "pass": counts[PASS],
            "fail": counts[FAIL],
            "unchecked": counts[UNCHECKED],
        },
        "verdict": verdict,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--briefs", type=Path, required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument("--buyer", type=Path, default=None)
    parser.add_argument("--expected-count", type=int, default=20)
    parser.add_argument("--record", type=Path, default=None)
    parser.add_argument("--markdown", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        record = build_record(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.record:
        args.record.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(_markdown(record), encoding="utf-8")

    print(json.dumps(record, indent=2, sort_keys=True))
    if record["verdict"] == "accepted":
        return 0
    if record["verdict"] == "not_accepted":
        return 1
    return 3


if __name__ == "__main__":
    sys.exit(main())
