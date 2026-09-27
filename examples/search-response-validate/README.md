# Validate a saved Lightdrift search response against the published schema

A pipeline that stores `/v1/search` responses before rendering pages, feeds or galleries should catch a drifted or malformed response before it reaches a template. This Python 3.10+ standard-library utility validates a saved response against a schema snapshot extracted from the published Lightdrift OpenAPI document. It is offline: no key, no network, no search credit.

It reports two severities. **Errors** are values that contradict the schema's declared type, enum or numeric range. **Warnings** are schema-valid values that miss a documented expectation — a missing `query_id` or per-result field, a relative `file` URL, a duplicate `asset_id`, a non-positive dimension, or `attribution_required` with no `attribution`. It never invents a field, a license value or a benchmark.

## Run a reproducible example

From this directory:

```bash
python3 validate_search_response.py fixtures/search-response.json --report report.json
python3 validate_search_response.py fixtures/search-response-warnings.json
python3 validate_search_response.py fixtures/search-response-errors.json
python3 validate_search_response.py fixtures/search-response.json \
  --schema sources/lightdrift-openapi.json --strict
python3 -m unittest -v
```

The clean fixture is `valid` and exits `0` (`demo-report.json`). The warnings fixture reports ten documented-expectation gaps and exits `0` (or `1` with `--strict`), recorded in `demo-report-warnings.json`. The errors fixture reports type and enum violations and exits `1` (`demo-report-errors.json`). All fixtures are synthetic; they are not observed customer searches.

Exit codes are `0` for a clean response, `1` for schema errors (or any warning under `--strict`), and `2` for an unreadable or malformed response or schema. Findings and the summary go to standard error, so the tool can sit in a shell pipeline. Add `--report review.json` to save the full JSON report.

## Options

| Option | Effect |
| --- | --- |
| `--schema PATH` | Validate against a fresh `openapi.json` (the `SearchResponse` schema is extracted) or a standalone schema. Default: the bundled snapshot |
| `--report PATH` | Write the JSON report: status, counts, and every error/warning with its JSON path |
| `--strict` | Exit `1` when any warning is present |
| `--quiet` | Suppress the human-readable findings and summary on standard error |

## What it checks

**Schema (against the extracted `SearchResponse`/`Result`/`Rights` schema):**

- **types** — `query_id`, `mode`, `ranking`, `backend` and `query_type` are strings; `latency_ms`, `pool_size`, `reranked` and `width`/`height` are integers; `score` is a number or null; `ai_generated` and the rights permission flags are booleans; `results` and `relaxed` are arrays.
- **enums** — `query_type` must be `text`, `image` or `image_text`.
- **numeric bounds** — any keyword present in the schema (`minimum`/`maximum`) is enforced.
- **unknown fields** — a field not in the documented schema is reported as a warning, so an additive API change is visible without failing the build.

**Documented expectations (warnings):**

- the response carries a `query_id`, and `results` is not empty;
- each result carries the documented `asset_id`, `title`, `source`, `width`, `height`, `file` and `rights`;
- each `rights` object carries `license`, `attribution` and `provenance_url`;
- `file`/`thumb` are absolute `http(s)` URLs and `width`/`height` are positive;
- no `asset_id` repeats within the response;
- `attribution_required: true` is accompanied by a non-empty `attribution`.

## Why validate against the OpenAPI schema

The OpenAPI document is the published contract for the response shape. Extracting the response schema from it keeps the check close to the source of truth, and `--schema sources/lightdrift-openapi.json` lets a CI job pull a fresh copy instead of trusting a snapshot. Because the schema marks no property as required, absence is a warning: a response can be shaped correctly and still be missing a field a downstream template needs, and that distinction is what makes the report actionable. The validator interprets a deliberate subset of JSON Schema (`type`, `enum`, `anyOf`, `items`, `minimum`, `maximum`, `properties`); it is not a general-purpose validator.

## Limits

The check is structural, not semantic: it cannot tell whether a license identifier is valid, whether attribution is accurate, or whether a use is permitted. It does not fetch URLs, download images, or contact Lightdrift, and it does not mutate the response. A response from a newer API that adds fields will pass with unknown-field warnings; pin the bundled snapshot or pass `--schema` when you need strict version matching. Rights remain a human decision — see the [rights guide](/guides/rights) and the `rights-compat` example.

## Files

- `validate_search_response.py` — the utility
- `test_validate_search_response.py` — 36 unit tests
- `schema/search-response.schema.json` — the bundled schema snapshot extracted from the OpenAPI document
- `fixtures/` — four synthetic responses (clean, warnings, errors, empty)
- `demo-report.json`, `demo-report-warnings.json`, `demo-report-errors.json`, `demo-report.md` — recorded runs
- `sources/manifest.json` — primary references, HTTP status, SHA-256
