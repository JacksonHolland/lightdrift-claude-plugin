# Emit structured data for images from a saved search response

Image search returns candidates; publishing them is a second job. Search engines, social cards and CMS integrations each want a different shape of the same facts: an `<img>` with a stable URL and dimensions, Schema.org `ImageObject` JSON-LD, Open Graph `og:image` tags, and a credit line. Rebuilding that by hand for every image is how captions and credits get dropped.

This Python 3.10+ standard-library utility converts one saved Lightdrift `/v1/search` (or `/v1/similar`) response body into Schema.org `ImageObject` JSON-LD, Open Graph image tags and a plain-text credit line. It makes no network calls, needs no API key, and uses synthetic fixtures.

It copies only the values the response declares. It never invents a license URL, a creator, or a display name, and it marks every gap as a warning rather than filling it. Rights clearance is **not evaluated** — see the [rights guide](https://docs.lightdrift.ai/guides/rights) and the [rights-compat example](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/rights-compat).

## Reproduce the example

From this directory:

```sh
python3 -m unittest -v test_emit_structured_data.py
python3 emit_structured_data.py fixtures/search-response.json --format jsonld --pretty
python3 emit_structured_data.py fixtures/search-response.json --format opengraph
python3 emit_structured_data.py fixtures/search-response.json --format credit
python3 emit_structured_data.py fixtures/search-response.json --format report --pretty
```

Exit codes: `0` emitted; `1` with `--require-complete` when a result lacks `asset_id`, title, an absolute `file` URL, width or height; `2` invalid input. All fixtures are synthetic and assert no license.

## What it maps

| Response field | JSON-LD `ImageObject` | Open Graph |
| --- | --- | --- |
| `asset_id` | `identifier` | — |
| `title` | `name` | `og:image:alt` |
| `file` | `contentUrl` | `og:image`, `og:image:secure_url` |
| `thumb` | `thumbnailUrl` | — |
| `width` / `height` | `width` / `height` | `og:image:width` / `og:image:height` |
| `rights.attribution` | `creditText` | — |
| `rights.provenance_url` | `isBasedOn` | — |
| `rights.license` (URL only) | `license` | — |

Every other declared rights field (`commercial`, `derivatives`, `share_alike`, `attribution_required`, `license_verbatim`, `basis`, and a non-URL `license` identifier) is carried into the review report, not guessed into JSON-LD.

## Honest edges

- **Tracked URLs.** `file` and `thumb` are Lightdrift tracked URLs: a `GET` answers `302` to a signed link valid for one hour. Confirm your pipeline follows redirects, or replace `contentUrl` with a stable URL you control. The report repeats this note.
- **License identifiers are not URLs.** A value like `cc0` or `cc-by-sa-4.0` is an identifier. Schema.org `license` expects a URL, so the field is omitted and warned on rather than fabricated.
- **Null is not empty.** A null `title` or `attribution` stays absent; the emitter does not substitute `""` or a placeholder.
- **One result, one `ImageObject`; many results, an `@graph`.** Choose the image your page actually shows, then emit its object rather than the whole candidate list.

## Use it in a build

```sh
python3 emit_structured_data.py saved-response.json --format jsonld --pretty --require-complete > image.jsonld
python3 emit_structured_data.py saved-response.json --format opengraph >> fragment.html
```

Pipe the JSON-LD into a `<script type="application/ld+json">` block and the tags into `<head>`. Use `--require-complete` in CI so a search response that loses its caption or dimensions fails the build instead of silently shipping an uncaptioned image. The report lists each warning with its `asset_id`, so a reviewer can fix the source data before publication.

Do not suppress a nonzero exit code to force a publish. Missing metadata is useful signal.

## Related examples

- [Compare which rights fields each image API returns](image-rights-fields-compare) before relying on a response shape.
- [Compare two saved responses offline](search-response-diff) to see what changed between two briefs.
- [Republish a saved response as a JSON Feed or RSS feed](search-to-feed) when an aggregator or newsletter consumes the result set.
- [Find the same image under two asset ids](search-result-dedup) before publishing duplicates.
- [Check attribution survives a CMS export](attribution-roundtrip) after the page is live.
- [Plan a bounded search batch](bounded-search-plan) before spending on a large pull.
