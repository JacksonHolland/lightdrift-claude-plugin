# Export a saved search response as an editorial shortlist

A saved Lightdrift search response is nested JSON, which does not paste into a
spreadsheet cleanly. Editorial and production teams often review candidates in
a table before publishing. This Python 3.10+ standard-library utility reads a
saved `/v1/search` or `/v1/similar` response and writes a flat shortlist:

- a **CSV** with one row per result and rights fields flattened into columns;
- a **JSON** shortlist that keeps the complete `rights` object per result.

It preserves source declarations, keeps unknown/future rights fields, and flags
rows that still need human review. It never calls Lightdrift, downloads an
image or spends search credits.

## Run a reproducible example

```bash
python3 shortlist_export.py fixtures/partial.json --output demo-shortlist
```

This writes `demo-shortlist.csv` and `demo-shortlist.json` and reports
`2 rows, 2 needing review`. The fixtures are synthetic.

## Columns

`row_index`, `asset_id`, `score`, `title`, `source`, `ai_generated`, `width`,
`height`, `file_url`, `thumb_url`, then flattened rights columns
(`rights_license`, `rights_license_verbatim`, `rights_commercial`,
`rights_attribution_required`, `rights_derivatives`, `rights_share_alike`,
`rights_attribution`, `rights_provenance_url`, `rights_basis`), and
`review_status`.

## Review status

| Status | Meaning |
| --- | --- |
| `ready_for_editorial_review` | `license` present and, if `attribution_required`, an `attribution` value is present |
| `needs_attribution_review` | `attribution_required` is true but `attribution` is empty |
| `needs_rights_review` | no `rights` object, or no `license` |

`ready_for_editorial_review` means the source declared the needed fields; it is
not a permission certificate. Review the supplied conditions before publishing.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | export written |
| 1 | `--strict` set and at least one row needs rights review |
| 2 | input error (unreadable file, invalid JSON, no `results` array) |

## Distinction from sibling examples

| Example | Focus |
| --- | --- |
| `search-to-feed` | republish results as RSS/JSON Feed |
| `image-structured-data` | emit schema.org structured data |
| `rights-compat` | check rights against a specific intended use, build credits |
| `attribution-roundtrip` | detect metadata lost during a CMS export |
| `delivery-url-audit` | detect a changed delivery URL |
| **this utility** | flatten a saved response into a review spreadsheet |

## Files

- `shortlist_export.py` — the utility.
- `test_shortlist_export.py` — 14 standard-library tests.
- `fixtures/` — synthetic clean, partial, empty and invalid responses.
- `demo-shortlist.csv`, `demo-shortlist.json` — generated from `fixtures/partial.json`.
- `sources/manifest.json` — captured docs inputs with SHA-256.
