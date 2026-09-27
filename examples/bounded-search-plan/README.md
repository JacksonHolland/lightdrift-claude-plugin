# Check an image-search batch before spending search credits

A presentation builder or content pipeline may collect the same image brief from several jobs. Before making requests, determine which proposed requests are exact duplicates, whether every row is valid, and how many attempts the job could make. This Python 3.10+ standard-library utility produces that plan offline. It does not need a key, search for images, reserve credits, or execute requests.

## Run a reproducible example

From this directory:

```bash
python3 search_plan.py fixtures/duplicates.json
python3 search_plan.py fixtures/changed-filters.json
python3 search_plan.py fixtures/budget-overflow.json
python3 -m unittest -v
```

The duplicate fixture has two identical requests in different JSON key order. It produces one unique request (k = 10) and a base estimate of 1 credit. The changed-filter fixture produces three unique requests: commercial true, commercial false, and commercial true with a minimum width. Those requests must not collapse into one simply because their query text matches.

The overflow fixture has two unique requests and allows two attempts per request. Its ceiling is four attempts of 1 credit each, estimated at 4 credits. The supplied budget of 3 credits is one credit too small, so the report is blocked and contains no executable request bodies. All fixtures are synthetic; they are not observed customer searches.

## Define your plan

```json
{
  "budget_credits": 6,
  "max_requests": 6,
  "attempts_per_request": 2,
  "requests": [
    {"query": "Wind turbines in open countryside", "k": 5,
     "filters": {"commercial": true, "orientation": "landscape"}},
    {"query": "Engineers inspecting solar panels", "k": 5,
     "filters": {"commercial": true, "min_width": 1600}}
  ]
}
```

`max_requests` caps attempts, including possible retries; it does not cap returned images. `attempts_per_request` includes the first attempt: 1 means no retry allowance. This tool does not implement a retry policy. A future executor must track attempts and stop at the configured limit. Do not blindly retry timeouts: first reconcile their unknown billing outcome.

Budget is a whole number of credits. The planner requires an explicit budget, attempt allowance and request cap. Local limits are 10,000 input rows, a 5 MB JSON file, 100,000 attempts and 1–10 attempts per request. These are utility limits, not account entitlements.

## What counts as a duplicate?

The identity includes the exact query, candidate count `k`, and complete supplied filter object. JSON object key order does not matter. Omitted `k` becomes 10 and omitted `filters` becomes `{}`. Everything else is deliberately conservative:

| Change | Deduplicated? | Reason |
| --- | --- | --- |
| JSON object keys reordered | Yes | Same represented request |
| Same text, different `k` | No | Different candidate request |
| Same text, changed filter | No | Different candidate constraints |
| Query case or whitespace changed | No | No undocumented text-equivalence assumption |
| Explicit filter null versus omitted filter | No | No undocumented default-equivalence assumption |
| Filter array reordered | No | No undocumented set-equivalence assumption |

The output maps duplicates back to their first zero-based input index. Each unique request has a SHA-256 identity for local audit; it is not a provider query ID or idempotency key. Deduplication only removes repeated planned requests within this file. It does not prove cache hits, reuse earlier responses, or guarantee identical future results.

## Validation and failure behavior

The planner handles text queries only, with `query`, `k`, and `filters`. It rejects unsupported fields such as image input, ranking controls and session tags instead of silently dropping them. Query must be nonblank and at most 1,000 characters; `k` is an integer from 1 to 100. It checks documented filter types, then applies narrower local checks: nonempty string arrays, nonnegative integer dimensions/years, ordered year bounds, orientation landscape/portrait/square, and `nsfw_max` from 0 to 1. The OpenAPI does not enumerate every semantic filter value; passing this validator does not establish provider acceptance or source availability.

Exit 0 means within the supplied plan limits. Exit 1 means invalid request rows, budget overflow or request-cap overflow. Exit 2 means malformed plan/schema/JSON or unreadable input. Unknown fields, duplicate JSON keys, boolean integers and nonfinite JSON numbers fail. Any invalid row blocks the whole plan. A blocked report emits no request bodies; `valid_subset_*` figures describe only valid unique rows and are not a total for the invalid batch. Reports can contain brief text when valid, so store them with the same privacy controls as the input.

## Understand the credit estimate

Lightdrift plans include a monthly credit allowance. A search costs 1 credit per 10 results requested, rounded up, minimum 1: k = 1 to 10 is 1 credit, k = 50 is 5 credits, k = 100 is 10 credits (pricing version `2026-09-28`). Credits are reserved from the requested `k` and settled to the results actually returned, so the estimate here is an upper bound. The utility pins this rule and reports it in every output. It does not refresh pricing in the background.

```
credits per request = max(1, ceil(k / 10))
base estimate = sum of credits per unique valid request
attempt ceiling = unique valid requests × attempts per request
ceiling estimate = base estimate × attempts per request
```

For planning, every allowed attempt is counted at its full reserved credits. Failed searches are not charged, so the ceiling is conservative. This is a credit-usage estimate, not an invoice or guarantee of spend. The Free plan caps each search at 10 results and supports text search only. Before any execution, recheck [current pricing](https://api.lightdrift.ai/v1/pricing), your remaining credits and your plan limits. If the credit rule changes, update the constant and rerun tests before relying on the output.

## Connect the plan to a reviewed workflow

A caller can use the JSON report as a CI check, treating any nonzero exit as a stop. This package intentionally contains no executor. A separately authorized backend must enforce the plan's request and retry ceilings and reconcile actual usage from each response's `credits.charged`; it should stop on a 402 `credits_exhausted` response and not retry; an offline report alone cannot enforce spend in another program. After the spend is bounded, pace the batch so the minute, daily and concurrency limits hold with the [offline rate-limit pacing validator](examples/rate-limit-pacing). Use the [presentation image search guide](https://docs.lightdrift.ai/guides/presentation-image-search) for an existing bounded request example. Review candidates with the [agent image review flow](https://docs.lightdrift.ai/guides/agent-image-review), and preserve [source rights and attribution](https://docs.lightdrift.ai/guides/rights). A commercial filter does not grant universal rights clearance.

When ready to integrate, [create a Lightdrift account](https://lightdrift.ai/sign-up?utm_source=github&utm_medium=example&utm_campaign=bounded_search_plan_v1) and follow the [API introduction](https://docs.lightdrift.ai/api-reference/introduction). Keep keys in a backend secret manager. No measured performance, cache savings, search quality or acquisition-economics claim is made by this utility.

## Evidence

`test-evidence.txt` records 22 passing local tests. `sources/manifest.json` identifies the OpenAPI, sitemap, repository tree and the pinned presentation example with capture timestamps and SHA-256 hashes; old pricing text was removed from those snapshots on 2026-09-27. The captures establish the inspected contract and overlap boundary; tests establish only offline behavior. No paid requests or live account writes were performed.
