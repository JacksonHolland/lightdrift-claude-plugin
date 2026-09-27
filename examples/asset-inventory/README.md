# asset-inventory

Reconcile saved Lightdrift search and `/v1/asset/{asset_id}` responses into one
offline inventory of image assets. Standard library only. No network, no API key,
no credits.

## Why

A search response tells you what an asset *looks like right now in the ranking
payload*; `/v1/asset/{asset_id}` tells you the canonical metadata and file links.
When you collect many saved responses you end up with the same asset appearing
more than once, some assets with no canonical metadata saved yet, and occasional
disagreements between the two views (width, format, `rights.commercial`, ...).
This tool turns that pile into:

- a merged **inventory** keyed by `asset_id`,
- the list of **unresolved** asset ids that still need one `GET /v1/asset/{id}`,
- a ready-to-run **request plan** for exactly those ids,
- **duplicate** assets seen across responses,
- **field conflicts** between search-declared and asset-declared values.

This is not a duplicate-identity resolver. For grouping images that arrive under
different `asset_id` values (canonical source URL / external id matching), use the
`search-result-dedup` example. This tool is about *metadata completeness*: which
assets still need canonical metadata, and where the two views disagree.

## Usage

```bash
python3 asset_inventory.py SAVED.json [MORE.json ...] [--format json|text] [--output report.json]
python3 asset_inventory.py SAVED_DIR --plan-only
```

Arguments accept either individual saved response files or a directory (scanned
recursively for `*.json`). Each file may contain one JSON object or an array of
objects. Response kind is inferred: an object with `results` or `query_id` is a
search response; an object with `asset_id` and no `results` is an asset response;
anything else is skipped and counted.

Exit codes: `0` success, `2` one or more inputs were missing or malformed (each
is reported on stderr; no partial report is written).

## Output shape

```json
{
  "search_responses": 2,
  "asset_responses": 2,
  "skipped_other_objects": 0,
  "distinct_assets_seen": 4,
  "assets_with_asset_response": 2,
  "assets_missing_asset_response": 2,
  "duplicate_assets_across_responses": {"fixture:a3": 2},
  "field_conflicts": {
    "fixture:a1": {"width": {"search": 1920, "asset": 1900}}
  },
  "unresolved_asset_ids": ["fixture:a2", "fixture:a4"],
  "request_plan": [
    {"asset_id": "fixture:a2", "method": "GET", "url": "https://api.lightdrift.ai/v1/asset/fixture:a2"}
  ],
  "inventory": {"fixture:a1": {"in_search_responses": 1, "has_asset_response": true,
    "search_declared": {}, "asset_declared": {}, "sources": []}},
  "notice": "..."
}
```

Conflicts compare only fields *both* sides declare (`title`, `source`, `width`,
`height`, `format`, `file`, `thumb`, and the right-layer fields `license`,
`license_verbatim`, `commercial`, `attribution_required`, `derivatives`,
`share_alike`, `attribution`, `provenance_url`, `basis`). A conflict is a textual
difference, not proof that either side is wrong: search ranking payloads may
carry truncated fields, and rights are "as-declared by source; verify for
critical use". Resolve against the live `/v1/asset/{id}` response before
publishing.

## Tests

```bash
python3 asset_inventory_test.py
```

15 tests cover classification, directory loading, malformed-input handling,
counts, unresolved ids, duplicates, exact width/rights conflicts, the request
plan shape, inventory flags, and all CLI output modes. Fixtures under
`fixtures/valid/` are synthetic (`fixture:*` ids) and `fixtures/malformed.json`
is intentionally unparseable.
