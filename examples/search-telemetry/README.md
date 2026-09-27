# Summarize saved image-search responses offline

A Python 3.10+ standard-library utility for developers tuning an image-search integration. Point it at one or more saved Lightdrift `/v1/search` (or `/v1/similar`) response envelopes and it writes a summary of what those envelopes actually declare: latency, timing phases, rerank/pool ratios, result counts, degraded and relaxed counts, and the distribution of `mode`, `ranking`, `query_type` and `backend`. It makes no network requests, needs no key and spends no credits.

Use it after a batch of searches to answer practical questions: how often did the reranker run, how many responses came back in retrieval order because reranking was degraded, which filters were relaxed, and how do timings split across embed, retrieve and rerank.

## Run a reproducible example

From this directory:

```sh
python3 -m unittest -v
python3 search_telemetry.py --format text fixtures/responses.json
python3 search_telemetry.py fixtures/responses.json
python3 search_telemetry.py fixtures/single.json --output report.json
```

The three fixtures are synthetic envelopes, visibly labelled, and contain no live results. The first command runs 16 local tests. The second prints a short report; the third prints the full JSON; the fourth writes the JSON to a new file.

Exit codes: `0` report written, `2` an input path was missing or unreadable, or any file was not valid JSON. Inputs fail closed: if any path is unreadable, no report is produced.

## Input contract

Each input is a saved response object, a JSON array of response objects, or a directory whose `*.json` files contain either. Objects without any of `results`, `query_id`, `timing_ms` or `pool_size` are skipped and counted, not silently treated as responses.

```json
{
  "query_id": "your-query-id",
  "mode": "auto",
  "ranking": "text",
  "query_type": "text",
  "backend": "voyage",
  "latency_ms": 120,
  "timing_ms": {"embed": 18, "retrieve": 40, "rerank": 55},
  "pool_size": 100,
  "reranked": 60,
  "relaxed": ["orientation"],
  "results": [{"asset_id": "example", "width": 1920, "height": 1080, "rights": {}}]
}
```

These are the fields documented in the public OpenAPI `SearchResponse` and `Result` schemas. Keep API keys out of saved response files and public artifacts.

## What the report contains

| Section | Meaning |
| --- | --- |
| `responses` | Count of response objects found |
| `skipped_non_response_objects` | Objects that did not look like a response envelope |
| `result_count` / `results_total` | Per-response and total result counts |
| `results_with_asset_id` / `results_with_dimensions` | How many results carry an id, and finite width **and** height |
| `latency_ms` | Count/min/max/mean/median over responses that declare it |
| `timing_ms` | Same summary per phase (`embed`, `retrieve`, `rerank`) |
| `pool_size`, `reranked` | Summaries of retrieval pool and reranked candidate counts |
| `reranked_over_pool_ratio` | Reranked ÷ pool_size for responses with a positive pool |
| `degraded_responses` | Responses whose `degraded` field is set |
| `relaxed_responses` / `relaxed_filters` | Count of responses that relaxed filters, and which filters |
| `mode` / `ranking` / `query_type` / `backend` | Value distributions |
| `missing_or_non_numeric` | Per-field count of absent or non-finite values |

## Honest edges

- **This is a summary of the inputs, not a benchmark.** Counts describe only the saved envelopes you pass in. They are not service performance, relevance, availability or a measured customer experience.
- **Missing fields stay missing.** A response without `latency_ms` is counted as missing, never imputed from other responses. `timing_ms` phases may be absent even when the envelope is otherwise complete.
- **`reranked_over_pool_ratio` is filtered, not interpreted.** It is only computed where `pool_size` is positive and `reranked` does not exceed it. A ratio near 1 does not by itself mean good results.
- **`degraded` is reported, not hidden.** A non-empty `degraded` value means the reranker was unavailable and results are in retrieval order; the utility surfaces the count so a workflow can decide what to do.
- **No scores, images or rights are judged.** The utility does not read relevance scores, fetch images, or evaluate licenses. It is a log summarizer, not a quality evaluator.
- **No network access.** No request, redirect, download or paid search occurs.

## Connect it to a real workflow

Log the raw response envelope your backend already receives, then run the report over the saved files after a batch. Pair it with the [rate-limit pacing guide](/guides/rate-limit-pacing) when a larger pull needs a schedule, and with the [search-response diff example](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/search-response-diff) when a single brief changes. The `pool_size`/`reranked` counts are the inputs to those tools, not substitutes for them.

[Try Lightdrift with one real search brief](https://lightdrift.ai/?utm_source=github&utm_medium=example&utm_campaign=search_telemetry_v1&utm_content=readme). Save the response, summarize a batch, and record what actually happened rather than assuming reranking always ran.

## Evidence

`test-evidence.txt` records 16 passing local tests. `sources/manifest.json` identifies the schema and docs pages inspected, with capture timestamps and SHA-256 hashes. The schema capture establishes the field names read; the tests establish only offline behavior. No live search, download or paid request was performed, and no measured relevance, latency or performance result is claimed.
