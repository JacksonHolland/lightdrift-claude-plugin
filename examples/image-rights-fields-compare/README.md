# Compare image-API rights fields from primary sources

When your pipeline needs to publish an image, the expensive failure is a license
field your search response never returned. This offline package renders an
honest, sourced comparison of what four image APIs actually expose per result,
and it fails its own build if any claim loses its source.

Four providers are compared from their own documentation:

| Provider | Endpoint | Rights fields per result |
| --- | --- | --- |
| Lightdrift | `GET /v1/search` | Full `rights` object: license, license_verbatim, commercial, attribution_required, derivatives, share_alike, attribution, provenance_url, basis |
| Openverse | `GET /v1/images/` | `license`, `license_version`, `license_url`, `attribution`, `foreign_landing_url`, `creator` |
| Wikimedia Commons | `GET …?action=query&prop=imageinfo` | `extmetadata`: License, LicenseShortName, UsageTerms, Artist, Credit, AttributionRequired |
| Pixabay | `GET /api/` | No license, attribution or permission field in the image hit; `pageURL` only |

`not exposed` in the rendered matrix means the provider's own documentation
lists no such field — not that the license forbids the use.

## Reproduce the comparison

Python 3.10+ standard library only. No network, no API key.

```sh
python3 -m unittest -v test_build_compare.py
python3 compare_rights.py --require-sources --format matrix
python3 compare_rights.py --require-sources --format markdown
python3 compare_rights.py --format html --output comparison.html
python3 compare_rights.py --format json --output comparison.json
```

Exit codes: `0` rendered; `1` with `--require-sources` when a claim lacks a
source URL, a verbatim quote, or a retrievable capture file; `2` the dataset is
malformed.

## What the dataset holds

`datasets/providers.json` has one entry per provider and one claim per rights
dimension. Every claim carries:

- `exposed` — whether the provider documents such a field;
- `field` — the exact documented field name (null when not exposed);
- `source_url`, `capture`, `quote` — where the claim came from and the sentence
  it was taken from;
- `basis` — why a `not exposed` cell is still a sourced claim.

`--require-sources` walks every claim and verifies the capture exists on disk.
A cell cannot be added without its evidence.

## Honest edges

- **Response shape, not legal advice.** This compares fields, not fitness for a
  use. A provider exposing `commercial: false` and a provider exposing only a
  license identifier both require the caller to act on the value.
- **Absence of a field is a documented claim.** For Pixabay, the claim is that
  the published image-hit field table lists no license field. It is not a
  statement about the license terms, which are applied site-wide.
- **Wikimedia `extmetadata` is HTML-formatted and optional.** The API description
  says results are HTML formatted, and not every key is populated on every file
  (the sampled public-domain file has no `LicenseUrl`).
- **Two providers were excluded, not guessed.** Unsplash's runtime docs do not
  expose their response field table as retrievable text and the license page
  returned an anti-bot challenge; Pexels documentation returned HTTP 403. Both
  exclusions are recorded in `datasets/providers.json`.
- **Snapshots age.** Source captures and their SHA-256 are in
  `sources/manifest.json`. Re-run the capture before republishing.

## Related examples

- [Emit structured data for images](image-structured-data) — turn a saved
  response into JSON-LD, Open Graph and a credit line.
- [Check attribution survives a CMS export](attribution-roundtrip).
- [Plan rights-compatible credits](rights-compat).
