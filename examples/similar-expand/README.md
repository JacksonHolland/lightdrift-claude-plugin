# Expand an image shortlist with similar-image search

A moodboard, deck or article often starts from one or two images that are "right"
and needs more in the same visual direction. Lightdrift's `/v1/similar` endpoint
takes an **indexed** asset ID and returns more like it, excluding the seed. This
Python 3.10+ standard-library utility turns that into a bounded, reproducible
step: it takes seeds from a saved `/v1/search` (or `/v1/similar`) response or the
command line, plans or performs the lookups, and merges every response into one
identity-deduplicated shortlist that keeps each result's source-declared rights.

Two properties keep it safe to hand to a pipeline:

- **The default is a plan.** Nothing is sent and no credit is spent until you
  pass `--live` and set `LIGHTDRIFT_API_KEY`. Run a dry run first.
- **Saved responses merge offline.** `--expansion` merges saved response bodies
  with **no key, no network and no search credit**, so a shortlist is
  reproducible and testable.

## What the utility does

- **Seed selection.** `--seed` adds an asset ID directly; `--seeds-from FILE`
  reads a saved `/v1/search` or `/v1/similar` body and takes its `results[]`
  `asset_id` values in rank order, de-duplicated.
- **Bounded plan.** `--max-seeds` caps how many seeds are used and `--k` sets
  results per seed (1–100). The plan reports `planned_requests`, `planned_cost_usd`
  and `seeds_skipped` before anything runs. `--budget-usd` blocks the plan when
  the worst-case cost would exceed it (integer-microdollar comparison, so
  `0.005 + 0.005` is compared exactly).
- **No ambiguous retries.** In `--live` mode each seed is one request with a
  stable `Idempotency-Key`. A `404` seed (outside the current index) is skipped;
  a `402` (credit), `429` (rate limit) or `5xx` aborts the remainder and is
  recorded rather than retried. Failed searches are not charged, so a skip costs
  nothing.
- **Identity merge.** Results are de-duplicated by `asset_id`; an asset found by
  several seeds accumulates every seed in `found_by` and appears once. The full
  `rights` object travels with each shortlist entry.
- **No key leakage.** The API key is sent only to the configured `--base-url`.
  Returned `file`/`thumb` URLs are recorded, never fetched with the key.

## Reproduce the example

From this directory:

```bash
python3 -m unittest -v test_similar_expand.py

# Offline merge of two synthetic saved responses (no key, no credit):
python3 similar_expand.py --expansion fixtures/similar-a.json \
  --expansion fixtures/similar-b.json --report report.json

# Dry run from a saved search response, with a budget ceiling:
python3 similar_expand.py --seeds-from fixtures/seed-response.json \
  --budget-usd 0.02
```

The offline merge produces a 4-asset shortlist from 2 synthetic responses; the
asset `flickr:51141533761` is returned for both seeds and is listed once with
`found_by: ["isorepublic:17191", "stocksnap:BAVURMUHRD"]`. The dry run plans 2
requests at $0.010000 against a $0.020000 ceiling and exits `0`. All fixtures are
**synthetic**; they are not observed customer searches.

To run it against your own account, set `LIGHTDRIFT_API_KEY` through your
environment's secret controls and add `--live`. Each successful similar call
costs $0.005 ($5 per 1,000) in account credit, checked against the public
`/v1/pricing` endpoint on September 26, 2026; request limits are separate.

## Options

| Option | Effect |
| --- | --- |
| `--seed ID` | Seed asset ID (repeatable). |
| `--seeds-from FILE` | Saved `/v1/search` or `/v1/similar` response to take seeds from (repeatable). |
| `--expansion FILE` | Offline `{"seed": ..., "response": ...}` record to merge (repeatable). Switches to merge mode. |
| `--k N` | Results per seed, 1–100 (default 10). |
| `--max-seeds N` | Cap on seeds used (default 5). |
| `--budget-usd DECIMAL` | Block the plan if the worst-case cost exceeds this. |
| `--price-usd-micros N` | Price per successful call in microdollars (default 5000). |
| `--base-url URL` | API base (default `https://api.lightdrift.ai`). |
| `--live` | Actually send requests; requires `LIGHTDRIFT_API_KEY`. |
| `--report FILE` | Write the report JSON to a file instead of stdout. |

Exit codes: `0` success, `1` plan blocked by budget, `2` malformed local input.

## Read the report

- `mode` is `plan`, `live` or `merge`.
- `requests[]` records each seed's outcome (status, HTTP status, `query_id`,
  `result_count`) and any `Retry-After`. In live mode it never claims more than
  what was observed.
- `shortlist[]` has `asset_id`, `found_by`, `best_rank`, dimensions, `file`,
  `thumb` and the full `rights` object.
- `aborted` names the stop reason (`budget_exceeded`, `insufficient_credit`,
  `rate_limited`, `provider_unavailable`) when the run stopped early.

## What this cannot establish

- Similarity is not identity. A visually related scene is not the same place or
  object, and a similar result does not verify a person's likeness, a logo, a
  building or an artwork.
- The utility does not clear rights, decide whether a use is permitted, or reach
  a payment or license decision. Rights come from the source's declarations;
  check the [rights guide](https://docs.lightdrift.ai/guides/rights) before
  publishing.
- `404` seeds are outside the current index; the endpoint has no legacy fallback.
- A `degraded` response is still a successful billed search with lane-order
  results; the utility records the flag but cannot repair ranking.
- The `--price-usd-micros` default is a documentation snapshot, not a live quote.
  Confirm the current rate at `/v1/pricing` before relying on a cost figure.

## Next step

Read the [search guide](https://docs.lightdrift.ai/guides/search) for the full
`/v1/similar` contract and the [reference-image search guide](https://docs.lightdrift.ai/guides/reference-image-search)
to choose between a new reference image and an existing asset ID. Then
[create a Lightdrift account](https://lightdrift.ai/sign-up?utm_source=github&utm_medium=example&utm_campaign=similar_expand_v1&utm_content=readme)
and follow the [quickstart](https://docs.lightdrift.ai/quickstart). The offline
merge is free; live lookups consume account entitlement.

## Suggested backlink audiences

- Developer-writeup and moodboard/design-tool authors describing visual
  "more like this" workflows on top of a search API.
- MCP and agent-tooling writers who need a concrete, bounded example of using an
  indexed asset as a similarity seed.
- Data-pipeline writers covering deterministic budgets and abort policies for
  paid search calls (plan → budget gate → no ambiguous retry).
- Image/asset management projects discussing shortlist de-duplication across
  multiple seed expansions.

These are hypotheses for the Earned owner to qualify; no destination has been
contacted and no link is claimed. Track pitch, submission, acceptance and live
link separately, including whether a resulting link is nofollow or sponsored.
