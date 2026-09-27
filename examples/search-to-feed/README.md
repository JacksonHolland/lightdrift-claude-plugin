# Turn a saved Lightdrift search response into a JSON Feed or RSS feed

A content pipeline, newsletter builder or monitoring job may already hold a saved `/v1/search` response and want to republish the matches as a standard feed. This Python 3.10+ standard-library utility converts that response into a [JSON Feed 1.1](https://www.jsonfeed.org/version/1.1/) document or an [RSS 2.0](https://www.rssboard.org/rss-specification) channel. It is offline: no key, no network, no search credit.

The converter copies only values the response declares. It omits fields it cannot fill and reports each omission; it never invents a publication date, file size, creator or license. The `_lightdrift` extension on each JSON Feed item keeps the rank, dimensions, license and credit the API returned.

## Run a reproducible example

From this directory:

```bash
python3 search_to_feed.py fixtures/search-response.json --pretty \
  --title "Standing query: coastal wildlife" \
  --home-url https://docs.lightdrift.ai/guides/search \
  --feed-url https://example.com/coastal-wildlife.json \
  --description "New images matching a standing image query"

python3 search_to_feed.py fixtures/search-response.json --format rss \
  --title "Standing query: coastal wildlife" \
  --home-url https://docs.lightdrift.ai/guides/search

python3 search_to_feed.py fixtures/search-response-minimal.json --require-complete
python3 -m unittest -v
```

The two-result fixture converts cleanly to both formats (`demo-report.json`, `demo-feed.xml`). The minimal fixture drops its relative `file` URL, missing title and missing dimensions, reports each omission and exits `1` under `--require-complete`. All fixtures are synthetic; they are not observed customer searches.

Exit codes are `0` for success, `1` when `--require-complete` is set and a field had to be omitted, and `2` for unreadable or malformed input. Warnings go to standard error, so the feed on standard output stays clean and pipeable. Add `--report review.json` to save the warnings.

## Feed metadata

The response supplies the items; you supply the feed envelope:

| Option | Effect |
| --- | --- |
| `--title` | Feed or channel title (default `Lightdrift image search results`) |
| `--home-url` | JSON Feed `home_page_url` and the RSS channel `link` |
| `--feed-url` | JSON Feed `feed_url` only |
| `--description` | JSON Feed `description` and the RSS channel `description` |
| `--format` | `jsonfeed` (default) or `rss` |
| `--pretty` | Indent JSON Feed output |
| `--require-complete` | Exit `1` if any field was omitted |
| `--report` | Write a JSON review report of the omissions |

A feed URL is metadata you control; this tool never guesses one. If `--home-url` is absent, the tool warns rather than fabricating a link.

## What each item carries

For each result in `results[]`:

- **id** — the `asset_id` when present. Otherwise `query_id#rank`, and otherwise the result position, with a warning, so an item id is always stable and non-empty.
- **url / link** — the rights `provenance_url` when it is an absolute URL. Otherwise the tracked `file` URL, with a warning, because a tracked URL redirects (`302`) to a short-lived signed link.
- **image / media** — the tracked `file` URL. In JSON Feed it is an `image` plus an `attachments` entry; in RSS it is a `media:content` element with `type`, `width` and `height` where known.
- **attribution and license** — copied verbatim into the `_lightdrift` extension and, for RSS, into the item `description`. A license *identifier* such as `cc-by-sa-4.0` is emitted as-is; it is not rewritten into a URL.

Nothing is invented. RSS `enclosure` is intentionally not used: RSS 2.0 requires a byte length, which the search response does not provide, so [Media RSS](https://www.rssboard.org/media-rss) `media:content` attaches the image without a fabricated size. JSON Feed `attachments` omit `size_in_bytes` for the same reason. No `date_published`/`pubDate` is emitted because the response has no capture time.

## Why a feed

Feeds are consumed by aggregators, newsletter tools, static-site generators and chat integrations that expect a stable, standards-shaped document. Emitting one from a saved response lets a content team route the same result set into those systems without writing a bespoke exporter, and keeps the per-item provenance next to the image. JSON Feed permits extension objects whose keys start with an underscore, which is how `_lightdrift` carries product metadata without breaking consumers.

## Limits

Local limits: a 5 MB input file is not enforced here, but inputs are read fully into memory, so keep saved responses modest. The tool does not paginate, merge multiple responses, fetch URLs, verify that a license is valid, or decide whether a use is permitted. It does not read or write to Lightdrift. Whether an item may be republished is a rights decision — see the [rights guide](/guides/rights) and the `rights-compat` example before publishing.

## Files

- `search_to_feed.py` — the utility
- `test_search_to_feed.py` — 34 unit tests
- `fixtures/` — three synthetic response files
- `demo-report.json`, `demo-feed.xml`, `demo-report.md` — one recorded conversion
- `sources/manifest.json` — primary references, HTTP status, SHA-256
- `CONTENT-HANDOFF.md` — publication handoff notes
