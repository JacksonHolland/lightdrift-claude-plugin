"""Expand an image shortlist with Lightdrift similar-image search (/v1/similar).

This Python 3.10+ standard-library utility takes seed asset IDs from a saved
``/v1/search`` or ``/v1/similar`` response (and/or the command line), then plans
or performs a bounded set of ``/v1/similar`` lookups and merges every response
into one identity-deduplicated shortlist that keeps the source-declared rights.

Two safety properties matter:

* The default is a **plan**: nothing is sent and no credits are spent until the
  caller passes ``--live`` and supplies an API key in ``LIGHTDRIFT_API_KEY``.
* Saved responses can be merged offline with ``--expansion`` so a run is
  reproducible without a key, network or search credit.

It never retries ambiguously. A ``404`` seed is skipped; a ``402``
(``credits_exhausted``), ``403`` (``paid_feature``: find-similar needs a paid
plan) or ``429`` aborts the remainder, and a ``5xx`` aborts rather than
spending credits. On 402/403 the error body's ``upgrade_url`` is kept in the
report so the user can upgrade. It never
forwards the API key to a returned file URL.

This is a plan/merge helper, not a rights decision. Permissions come from the
source's declarations and must be reviewed before publication.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

SCHEMA = "similar-expand/1"
DEFAULT_BASE_URL = "https://api.lightdrift.ai"
RESULTS_PER_CREDIT = 10  # 1 credit per 10 results requested, rounded up, minimum 1


class InputError(ValueError):
    """Raised for malformed local input. Maps to exit code 2."""


def _reject_constant(value: str):
    raise InputError("non-finite JSON constant: %s" % value)


def strict_json(text: str):
    """Parse JSON, rejecting duplicate object keys and non-finite constants."""

    def _hook(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise InputError("duplicate JSON key: %r" % (key,))
            seen[key] = value
        return seen

    return json.loads(text, object_pairs_hook=_hook, parse_constant=_reject_constant)


def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return strict_json(handle.read())
    except OSError as exc:
        raise InputError("cannot read %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise InputError("invalid JSON in %s: %s" % (path, exc))


def _asset_id_of(item):
    if not isinstance(item, dict):
        raise InputError("result is not an object")
    asset_id = item.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise InputError("result is missing a non-empty asset_id")
    return asset_id


def extract_seed_asset_ids(response, source_label: str):
    """Return ordered, de-duplicated asset IDs from a saved response body."""
    if not isinstance(response, dict):
        raise InputError("%s is not a JSON object" % source_label)
    results = response.get("results")
    if not isinstance(results, list):
        raise InputError("%s has no results array" % source_label)
    seeds = []
    for item in results:
        asset_id = _asset_id_of(item)
        if asset_id not in seeds:
            seeds.append(asset_id)
    return seeds


def credits_per_request(k: int) -> int:
    """Credits reserved for one /v1/similar call: ceil(k / 10), minimum 1."""
    return max(1, -(-k // RESULTS_PER_CREDIT))


def plan_expansion(seeds, k, max_seeds, budget_credits=None):
    """Return a deterministic plan dict; no network and no mutation."""
    if k < 1 or k > 100:
        raise InputError("k must be between 1 and 100")
    if max_seeds < 1:
        raise InputError("max_seeds must be at least 1")
    if budget_credits is not None and budget_credits < 0:
        raise InputError("budget_credits must be non-negative")

    selected = list(seeds)[:max_seeds]
    planned_credits = credits_per_request(k) * len(selected)
    blocked = budget_credits is not None and planned_credits > budget_credits
    return {
        "seeds": selected,
        "seeds_available": len(seeds),
        "seeds_skipped": max(0, len(seeds) - len(selected)),
        "planned_requests": len(selected),
        "planned_credits": planned_credits,
        "budget_credits": budget_credits,
        "blocked": blocked,
    }


def merge_expansions(records):
    """Merge ``{"seed": str, "response": SearchResponse}`` records.

    De-duplicates results by ``asset_id``, accumulates every seed that found an
    asset, and keeps the first observed result object per asset. The result is
    deterministic for a given record order.
    """
    by_id = {}
    order = []
    request_log = []
    for record in records:
        if not isinstance(record, dict):
            raise InputError("expansion record is not an object")
        seed = record.get("seed")
        if not isinstance(seed, str) or not seed.strip():
            raise InputError("expansion record is missing a seed")
        response = record.get("response")
        if not isinstance(response, dict) or not isinstance(response.get("results"), list):
            raise InputError("expansion record for seed %r has no results" % (seed,))
        request_log.append(
            {
                "seed": seed,
                "status": "ok",
                "query_id": response.get("query_id"),
                "result_count": len(response["results"]),
            }
        )
        for rank, item in enumerate(response["results"]):
            asset_id = _asset_id_of(item)
            existing = by_id.get(asset_id)
            if existing is None:
                by_id[asset_id] = {
                    "asset_id": asset_id,
                    "found_by": [seed],
                    "best_rank": rank,
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "score": item.get("score"),
                    "file": item.get("file"),
                    "thumb": item.get("thumb"),
                    "rights": item.get("rights"),
                }
                order.append(asset_id)
            else:
                if seed not in existing["found_by"]:
                    existing["found_by"].append(seed)
                if rank < existing["best_rank"]:
                    existing["best_rank"] = rank
    shortlist = [by_id[asset_id] for asset_id in order]
    return request_log, shortlist


def _idempotency_key(asset_id: str, k: int) -> str:
    raw = ("similar-expand:v1:%s:%d" % (asset_id, k)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def live_lookup(base_url, api_key, seed, k, timeout):
    """Perform one ``/v1/similar`` request. Returns a result dict, never retries."""
    url = base_url.rstrip("/") + "/v1/similar"
    body = json.dumps({"asset_id": seed, "k": k}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "Idempotency-Key": _idempotency_key(seed, k),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return {"status": "ok", "http_status": response.status,
                    "response": strict_json(payload)}
    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:500]
        except Exception:  # pragma: no cover - defensive
            detail = ""
        return {"status": "error", "http_status": exc.code,
                "retry_after": retry_after, "error": detail}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"status": "error", "http_status": None, "error": str(exc)}


def _abort_reason(http_status):
    if http_status == 402:
        return "credits_exhausted"
    if http_status == 403:
        return "paid_feature"
    if http_status == 429:
        return "rate_limited"
    if http_status is not None and 500 <= http_status < 600:
        return "provider_unavailable"
    return None


def _upgrade_url(detail):
    """Return upgrade_url (or buy_credits_url) from a 402/403 error body, if any."""
    try:
        body = json.loads(detail or "")
    except ValueError:
        return None
    inner = body.get("detail") if isinstance(body, dict) else None
    if not isinstance(inner, dict):
        return None
    return inner.get("upgrade_url") or inner.get("buy_credits_url")


def run_live(plan, base_url, api_key, k, timeout):
    """Execute the planned lookups sequentially with abort controls."""
    records = []
    requests_out = []
    aborted = None
    for seed in plan["seeds"]:
        if aborted:
            requests_out.append({"seed": seed, "status": "skipped", "reason": aborted})
            continue
        outcome = live_lookup(base_url, api_key, seed, k, timeout)
        entry = {
            "seed": seed,
            "status": outcome["status"],
            "http_status": outcome.get("http_status"),
        }
        if outcome["status"] == "ok":
            response = outcome["response"]
            entry["query_id"] = response.get("query_id")
            entry["result_count"] = len(response.get("results", []))
            if response.get("degraded"):
                entry["degraded"] = response["degraded"]
            records.append({"seed": seed, "response": response})
        else:
            entry["error"] = outcome.get("error")
            if outcome.get("retry_after"):
                entry["retry_after"] = outcome["retry_after"]
            upgrade_url = _upgrade_url(outcome.get("error"))
            if upgrade_url:
                entry["upgrade_url"] = upgrade_url
            reason = _abort_reason(outcome.get("http_status"))
            if reason:
                aborted = reason
        requests_out.append(entry)
    request_log, shortlist = merge_expansions(records)
    # Re-key the merge log by request entries, preserving seed-level detail.
    return requests_out, shortlist, aborted


def build_report(mode, base_url, k, plan, requests_out, shortlist,
                 aborted=None, notes=None):
    return {
        "schema": SCHEMA,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "mode": mode,
        "base_url": base_url,
        "k": k,
        "credits_per_request": credits_per_request(k),
        "seeds": plan["seeds"],
        "seeds_available": plan["seeds_available"],
        "seeds_skipped": plan["seeds_skipped"],
        "planned_requests": plan["planned_requests"],
        "planned_credits": plan["planned_credits"],
        "budget_credits": plan["budget_credits"],
        "blocked": plan["blocked"],
        "aborted": aborted,
        "requests": requests_out,
        "shortlist_count": len(shortlist),
        "shortlist": shortlist,
        "notes": notes or [],
    }


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Plan, perform or merge bounded /v1/similar expansion.")
    parser.add_argument("--seed", action="append", default=[],
                        help="Seed asset_id (repeatable).")
    parser.add_argument("--seeds-from", action="append", default=[], metavar="FILE",
                        help="Saved /v1/search or /v1/similar response to take seeds from.")
    parser.add_argument("--expansion", action="append", default=[], metavar="FILE",
                        help='Offline record {"seed":..., "response":...} to merge (repeatable).')
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-seeds", type=int, default=5)
    parser.add_argument("--budget-credits", type=int, default=None,
                        help="Maximum credits the plan may reserve (1 credit per 10 results, min 1 per call).")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--live", action="store_true",
                        help="Actually send requests. Requires LIGHTDRIFT_API_KEY.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--report", default=None, help="Write the report JSON to this path.")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    seeds = []
    seed_sources = {}
    for seed in args.seed:
        if seed not in seeds:
            seeds.append(seed)
            seed_sources.setdefault(seed, "explicit")
    for path in args.seeds_from:
        response = load_json(path)
        for asset_id in extract_seed_asset_ids(response, path):
            if asset_id not in seeds:
                seeds.append(asset_id)
                seed_sources.setdefault(asset_id, "seeds-from:%s" % os.path.basename(path))

    # Offline merge mode: no seeds, no network, no key.
    if args.expansion:
        records = [load_json(path) for path in args.expansion]
        request_log, shortlist = merge_expansions(records)
        plan = {
            "seeds": [rec["seed"] for rec in records],
            "seeds_available": len(records),
            "seeds_skipped": 0,
            "planned_requests": 0,
            "planned_credits": 0,
            "budget_credits": None,
            "blocked": False,
        }
        report = build_report("merge", args.base_url, args.k,
                              plan, request_log, shortlist,
                              notes=["Offline merge: no network, no credits used."])
        _emit(report, args.report)
        return 0

    plan = plan_expansion(seeds, args.k, args.max_seeds, args.budget_credits)
    plan["seed_sources"] = {seed: seed_sources.get(seed, "unknown") for seed in plan["seeds"]}

    if plan["blocked"]:
        report = build_report("plan", args.base_url, args.k,
                              plan, [], [], aborted="budget_exceeded",
                              notes=["Plan exceeds the stated budget; no request was sent."])
        _emit(report, args.report)
        return 1

    if not args.live:
        report = build_report("plan", args.base_url, args.k,
                              plan, [], [],
                              notes=["Dry run. Pass --live and set LIGHTDRIFT_API_KEY to execute."])
        _emit(report, args.report)
        return 0

    api_key = os.environ.get("LIGHTDRIFT_API_KEY")
    if not api_key:
        raise InputError("--live requires LIGHTDRIFT_API_KEY in the environment")

    requests_out, shortlist, aborted = run_live(plan, args.base_url, api_key,
                                                args.k, args.timeout)
    report = build_report("live", args.base_url, args.k,
                          plan, requests_out, shortlist, aborted=aborted,
                          notes=["No request was retried. 404 seeds were skipped; "
                                 "402/403/429/5xx aborted the remainder."])
    _emit(report, args.report)
    return 0


def _emit(report, path):
    text = json.dumps(report, indent=2, sort_keys=False)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as exc:
        sys.stderr.write("error: %s\n" % (exc,))
        raise SystemExit(2)
