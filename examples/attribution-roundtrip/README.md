# Check image attribution survives a CMS export

A migration can preserve an image URL while silently dropping its creator credit, original source, or a nested rights field. This offline utility compares the metadata selected by an editor against a separately generated CMS export. Use it before a migration release or in a content build. It needs Python 3.10+ and the standard library; it makes no network calls and needs no API key.

This is one metadata-preservation tool. It is not a license validator, an image downloader, or a benchmark of Lightdrift search quality. All included images are represented by synthetic metadata, not licensed image files.

## Run the reproducible example

From this directory:

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 attribution_check.py fixtures/selected.json fixtures/export-preserved.json
python3 attribution_check.py fixtures/selected.json fixtures/export-lossy.json
```

The preserved export exits 0. The deliberately lossy export exits 1 and identifies two changes: `/attribution` and `/rights/review`. Invalid input exits 2. A CI step can run the same command against real normalized files; do not suppress nonzero exit codes. No dependency installation or paid search is necessary.

## Establish an independent baseline

Save the selected-image manifest **before** the migration or CMS transformation. Keep it in your reviewed content source or retained build artifacts. Generate the export from the destination separately. Generating both inputs from the destination can hide exactly the loss you want to detect.

Both files use an explicit local interchange schema, not a Lightdrift API response schema:

```json
{
  "schema_version": 1,
  "assets": [
    {
      "asset_id": "stable-selected-asset-id",
      "source": "original source value or null",
      "provenance_url": "original provenance URL or null",
      "attribution": "original attribution text or null",
      "rights": {"preserve": "the complete original rights object here"}
    }
  ]
}
```

The object above illustrates the envelope only; it does not define rights properties or assert a license. All four metadata fields must be present in the baseline. Preserve `null` when the original metadata was unknown. An empty or null baseline value appears in `baseline_unknowns` even when the export matches. Metadata equality is not rights clearance: every report returns `rights_clearance: "not_evaluated"`.

Choose exactly the selected assets, rather than every search candidate. The export should describe the same selected scope. Missing and unexpected IDs are reported; duplicate IDs are rejected. Asset ordering does not matter. Array ordering within metadata does matter. CMS fields outside the four compared metadata fields are ignored. The complete nested `rights` value is compared, including new or removed fields. Source and attribution text are exact comparisons: even an apparently harmless rewrite should be reviewed. Numbers and booleans are distinct.

## Connect an existing review queue

The [Sanity review example](https://docs.lightdrift.ai/guides/sanity-image-review-queue) retains `assetId`, `source`, `provenance`, `attribution`, `rightsJson`, and the original `candidateJson`. At publication time, map the **editor-selected** candidates as follows:

| Interchange field | Baseline | Destination export |
| --- | --- | --- |
| `asset_id` | original selected result `asset_id` | persisted `assetId` |
| `source` | original selected result `source`, or explicit null | persisted `source` |
| `provenance_url` | original rights `provenance_url`, or explicit null | persisted `provenance` |
| `attribution` | original rights `attribution`, or explicit null | persisted `attribution` |
| `rights` | complete original `rights`, or explicit null | decoded `rightsJson` |

The existing queue turns absent text metadata into an empty string. This checker intentionally flags a null-to-empty transformation; either fix preservation at the boundary or document and review a normalization policy applied independently to both inputs. Do not silently erase differences just to get a passing check. A CMS export missing one of these fields must omit it so the checker reports the loss; do not refill it from the baseline. Parse `rightsJson` as JSON instead of comparing its serialized whitespace. Select approved assets using your real editor workflow; this tool never approves a pending candidate.

For other CMSs, write a small adapter to the same envelope. Version that adapter alongside your content export and retain a fixture where metadata is intentionally removed. A passing check is useful only for the fields your adapter actually exports.

## Interpret failures and repair at the source

- `missing_asset`: the destination export omitted a selected image. Check selection filters and stable IDs.
- `unexpected_asset`: an image exists outside the baseline selection. Review replacements before expanding the baseline.
- `missing_field`: the export adapter or CMS omitted metadata entirely.
- `changed_field`: the value, type, nested structure, or array order changed. Paths use JSON Pointer escaping (`~0` for `~`, `~1` for `/`).

Fix the destination schema or export mapping, rerun, and retain the report with the release evidence. Do not replace the baseline with the lossy export. Keep rights review separate: consult the original source and the [rights guide](https://docs.lightdrift.ai/guides/rights) before use. This utility cannot assess revocations, model/property releases, attribution placement in rendered pages, missing information already absent in the baseline, or whether an image file matches the selected ID.

Input limits are 5 MB per file and 10,000 assets. Empty baselines, duplicate JSON keys, non-finite JSON numbers and malformed files fail rather than returning success. Reports include asset IDs and changed field paths, not old/new metadata values. Keep IDs and rights metadata in appropriately protected build artifacts. The program only reads local inputs and prints JSON.

## Add image discovery upstream

For the search step, use the [API introduction](https://docs.lightdrift.ai/api-reference/introduction) or a [human review workflow](https://docs.lightdrift.ai/guides/agent-image-review), then save the selected records before exporting them. [Create a Lightdrift account](https://lightdrift.ai) to connect your own image-search workflow. This checker remains usable with offline records and other image sources.
