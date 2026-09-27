# Demo report: validating saved search responses

The validator is offline. Three fixture commands:

```bash
python3 validate_search_response.py fixtures/search-response.json --report demo-report.json --quiet
python3 validate_search_response.py fixtures/search-response-warnings.json --report demo-report-warnings.json --quiet
python3 validate_search_response.py fixtures/search-response-errors.json --report demo-report-errors.json --quiet
```

| fixture | status | errors | warnings | exit |
| --- | --- | --- | --- | --- |
| `search-response.json` | valid | 0 | 0 | 0 |
| `search-response-warnings.json` | warnings | 0 | 10 | 0 (1 with `--strict`) |
| `search-response-errors.json` | invalid | 6 | 0 | 1 |

The clean response names its `query_id`, fills every documented per-result field, uses absolute `file`/`thumb` URLs and positive dimensions, and declares each rights field, so it validates without a warning. The warnings response omits `query_id` and several per-result and rights fields, points `file` at a relative path, reports `width: 0`, uses `attribution_required: true` with no attribution, and repeats an `asset_id`; every one of those is reported as a warning with its JSON path. The errors response sets `query_type: "video"`, puts a string in `width` and `score`, gives a non-boolean value in `commercial`, sends a number in `relaxed`, and includes a non-object result; each is a schema error.

Validating the clean fixture against a freshly captured `sources/lightdrift-openapi.json` also exits `0`, exercising the `--schema` extraction path. Fixtures are synthetic and no API request was sent.
