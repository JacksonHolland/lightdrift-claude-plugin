# Pace an image-search batch against Lightdrift rate limits before sending it

An integration that fires many search briefs at once gets `429` responses: either the minute or daily request allowance is exhausted, or too many searches run at the same time. This Python 3.10+ standard-library utility checks a proposed schedule against those limits, or builds a deterministic earliest-start schedule for the same limits, entirely offline. It needs no key, sends no requests, and spends no credit.

It does not decide budget or remove duplicates — the [bounded search planner](/guides/bounded-search-plan) does that. This tool answers the pacing question: given a list of search requests, when may each one start so the minute, daily and concurrency limits stay satisfied?

## Run a reproducible example

From this directory:

```bash
python3 pace_plan.py fixtures/valid-schedule.json
python3 pace_plan.py fixtures/minute-violation.json --format text
python3 pace_plan.py fixtures/concurrency-violation.json
python3 pace_plan.py fixtures/daily-violation.json
python3 pace_plan.py --mode schedule fixtures/schedule-burst.json
python3 pace_plan.py --mode schedule fixtures/schedule-concurrency.json
python3 -m unittest -v
```

`valid-schedule.json` passes with the Starter limits. `minute-violation.json` has 31 requests in one minute against Promo's 30 per minute. `concurrency-violation.json` overlaps three searches against a concurrency limit of two. `daily-violation.json` places six requests in a day against a daily limit of five. `schedule-burst.json` spreads five briefs across three minute windows at two per minute. All fixtures are synthetic; they are not observed customer searches.

Exit codes are `0` for a valid or scheduled run, `1` for an invalid or infeasible run, and `2` for unreadable or malformed input. Output is JSON by default; add `--format text` for a short report.

## Quote the effective limits

A run file names either a plan or explicit limits:

```json
{
  "plan": "Starter",
  "duration_seconds": 5,
  "requests": [
    {"id": "brief-1", "at_second": 0},
    {"id": "brief-2", "at_second": 1},
    {"id": "brief-3", "at_second": 2, "duration_seconds": 10}
  ]
}
```

`plan` is `Promo`, `Starter`, `Growth` or `Scale`. The limits come from the [plans and limits guide](https://docs.lightdrift.ai/guides/plans-and-limits):

| Plan | Total credit purchased | Requests per minute | Requests per day | Concurrent searches |
| --- | --- | --- | --- | --- |
| Promo | Less than $10 | 30 | 1,000 | 2 |
| Starter | $10 or more | 60 | 5,000 | 4 |
| Growth | $100 or more | 300 | 25,000 | 10 |
| Scale | $1,000 or more | 1,000 | 100,000 | 25 |

Use explicit `limits` instead when an API key has custom limits:

```json
{"limits": {"rpm": 120, "rpd": 20000, "concurrency": 8}, "requests": [{"id": "a"}]}
```

`limits` overrides individual fields from `plan`. Limits may not be inferred from headers by this tool; copy the effective values you observed, because a key's custom limits can differ from the plan defaults. The public OpenAPI document bounds `rpm_limit` at 1–100,000, `rpd_limit` at 1–10,000,000 and `concurrency_limit` at 1–500.

`duration_seconds` is the assumed time one search occupies a concurrency slot. It defaults to `0`, which models an instantaneous request that never overlaps another. Set it from measured latency when you want the concurrency check to mean something; it is a caller estimate, never an observed service time.

## Validate mode

Each request needs an `at_second` offset. The tool reports the busiest sliding 60-second window, the busiest sliding 24-hour window and the maximum number of overlapping searches, then lists every violation.

Minute and daily limits are **fixed** windows in the product, but their start boundaries are not published. This tool checks conservative sliding windows, so a schedule it marks valid is safe, while a schedule it flags may still pass against the real fixed windows. When unsure, slow the schedule down. Window comparisons are half-open: a request at second `0` and one at second `60` fall in different minute windows. No existing example turns the plans table into a pacing check.

## Schedule mode

With no `at_second` required, the tool assigns each request the earliest start that keeps all limits satisfied, in the order written:

- requests wait until the previous minute window has fewer than `rpm` starts;
- requests wait a full day once `rpd` starts are already inside the day;
- a new search that would exceed the concurrency limit is delayed to the earliest moment a slot frees, using the supplied durations.

The output is deterministic and re-running it produces byte-identical JSON. A run that cannot fit inside a 366-day horizon is reported `infeasible`. Zero-duration requests never overlap, so concurrency is reported as unexercised for them.

## Limits

Local limits are 2,000 requests, a 5 MB input file and a 366-day scheduling horizon. Input is never executed. This tool does not reserve credit, does not model `Retry-After`, does not implement a retry policy and does not account for credit balance — a paced schedule can still fail with `402` if you have no credit. It does not replace the provider's own counters: the minute and daily counters are tracked per key, OAuth connections share an account counter, and concurrent searches are counted across the account.

## Files

- `pace_plan.py` — the utility
- `test_pace_plan.py` — 35 unit tests
- `fixtures/` — six synthetic run files
- `demo-report.md`, `demo-report.json` — one recorded schedule run
- `sources/manifest.json` — primary references, HTTP status, SHA-256
- `CONTENT-HANDOFF.md` — publication handoff notes
