# Turn a saved Lightdrift search response into an offline HTML review gallery

A person choosing which images to publish often works from a saved `/v1/search` response and a spreadsheet. This Python 3.10+ standard-library utility renders that response as one self-contained HTML page: a figure per result with its thumbnail, declared credit and license, a link to the source page, and a visible marker for any metadata the response did not supply. It is offline: no key, no network, no search credit.

The builder copies only values the response declares. It never invents a caption, creator, license or source page — missing values become `untitled`, `none declared` or `source page not declared`, and are listed in a review report. Rights are not evaluated: the page is a review aid, not a clearance.

## Run a reproducible example

From this directory:

```bash
python3 build_review_gallery.py fixtures/search-response.json \
  --title "Standing query review: coastal wildlife" \
  --subtitle "Offline review page built from a saved search response" \
  --generated-at 2026-09-27 \
  --output gallery.html --report review.json

python3 build_review_gallery.py fixtures/search-response-partial.json --require-complete
python3 -m unittest -v
```

The two-result fixture renders cleanly (`demo-gallery.html`, `demo-report.json`) and exits `0`. The partial fixture reports every omission, marks each on the page, and exits `1` under `--require-complete`. The empty fixture warns that the gallery has no results. All fixtures are synthetic; they are not observed customer searches.

Exit codes are `0` for success, `1` when `--require-complete` is set and any asset (or the response) is missing metadata, and `2` for unreadable or malformed input. Warnings go to standard error, so the HTML on standard output stays clean and pipeable. Add `--report review.json` to save the per-asset omissions.

## Options

| Option | Effect |
| --- | --- |
| `--title` | Page `<title>` and heading (default `Image review gallery`) |
| `--subtitle` | Optional line under the heading |
| `--generated-at` | Optional build label shown in the header; omitted by default |
| `--output` | Write HTML to this path instead of standard output |
| `--report` | Write a JSON report listing each asset's missing fields |
| `--require-complete` | Exit `1` if any asset is missing metadata |

## What each figure carries

For each result in `results[]`:

- **image** — the tracked `thumb` URL when it is absolute, otherwise the `file` URL. Both redirect (`302`) to a short-lived signed link, so the page is for review, not permanent embedding. If neither is absolute, the figure shows an "image URL missing" marker.
- **caption** — the declared `title`, or `untitled` when absent.
- **size and rank** — `width`x`height` and the result position, shown only when the response declares them.
- **license and attribution** — copied verbatim into the caption. A license *identifier* stays an identifier; it is not rewritten into a URL.
- **source page** — the rights `provenance_url` when it is an absolute URL, linked so a reviewer can open it. Otherwise the figure shows `source page not declared`.
- **missing-marker** — each absent field is listed in `--report` and highlighted in the caption.

Nothing is invented. The page embeds no external stylesheet, script, font or image tracker — all CSS is inline, so it opens offline and sends no request when viewed.

## Why a self-contained page

Reviewing candidates should not require an account, a running server or an upload. A single HTML file can be attached to a ticket, committed next to a content draft or opened from disk, and it keeps the per-image credit and provenance beside the thumbnail instead of in a separate column. Because it renders only declared fields, the missing-metadata markers double as a pre-publication checklist.

## Limits

Inputs are read fully into memory, so keep saved responses modest. The tool does not paginate, merge multiple responses, download images, verify that a license is valid, or decide whether a use is permitted. It does not read or write to Lightdrift. Whether an item may be republished is a rights decision — see the [rights guide](/guides/rights) and the `rights-compat` example before publishing.

## Files

- `build_review_gallery.py` — the utility
- `test_build_review_gallery.py` — 33 unit tests
- `fixtures/` — three synthetic response files (clean, partial, empty)
- `demo-gallery.html`, `demo-report.json`, `demo-report-partial.json`, `demo-report.md` — one recorded render
- `sources/manifest.json` — primary references, HTTP status, SHA-256
- `CONTENT-HANDOFF.md` — publication handoff notes
