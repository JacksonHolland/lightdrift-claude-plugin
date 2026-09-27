# Check saved image rights against an intended use, and build credits

Search results carry a machine-readable `rights` object. The hard part is turning that declaration into a decision your publishing pipeline can act on: can this image be used commercially, may it be modified, does it carry a share-alike obligation, and where does the required credit go?

This offline utility reads a **saved** search response plus an intended-use profile and returns, per asset, one of four statuses:

- `ok` — declared flags are compatible with the intended use.
- `ok_with_attribution` — compatible, and the asset declares an attribution requirement with an attribution string to carry forward.
- `review` — an unknown (`null`) flag, a share-alike obligation you did not accept, missing required attribution, or an unresolved license. A human decides.
- `blocked` — the source declares the requested use is prohibited (non-commercial license with commercial use requested; no-derivatives license with derivative use requested).

It also emits a **credit block** for clean assets that require attribution. It needs only Python 3.10+ and the standard library: no API key, no network calls, no paid search.

This is a review aid, not a license validator. Every report returns `rights_clearance: not_evaluated`. A `null` flag means the source did not say — the tool routes it to `review`, never to `ok`.

## Run the reproducible example

From this directory:

```bash
python3 -m unittest -v test_rights_compat.py
python3 rights_compat.py fixtures/search-response.json fixtures/use-commercial-derivatives.json
python3 rights_compat.py fixtures/search-response.json fixtures/use-commercial-derivatives.json --format markdown
```

The fixture response exits `1` because it deliberately contains one non-commercial asset, one no-derivatives asset, and several unknowns. Changing only the intended-use profile to editorial use makes the non-commercial and no-derivatives assets usable without modification — the same assets, a different decision, because the intended use changed. That is the point: compatibility is a property of the pairing, not of the image alone.

`demo-report.json` and `demo-report.md` are the actual captured output for the commercial profile. `test-evidence.txt` records 29 passing tests.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every asset is `ok` or `ok_with_attribution`. Nothing needs a human. |
| `1` | At least one asset is `review` or `blocked`. Inspect before publishing. |
| `2` | Invalid input (malformed JSON, missing keys, duplicate IDs, unreadable file). |

A CI step can gate on a non-zero exit while still allowing a human to clear `review` items out of band. Do not weaken the check to force exit `0`; fix the input or record the decision separately.

## Inputs

### Search response

Accept a full saved response (the `results` array) or a normalized `assets` array. Each record needs a non-empty string `asset_id`. The `rights` object may be `null`; documented fields read by this tool are:

| Field | Used for |
| --- | --- |
| `license` | Reported in the report; missing triggers `review` |
| `commercial` | Blocks commercial use when `false`; `review` when `null` |
| `derivatives` | Blocks derivative use when `false`; `review` when `null` |
| `share_alike` | `review` when `true`, derivatives are requested, and the profile does not accept share-alike |
| `attribution_required` | `ok_with_attribution` when `true` with a present string; `review` when `true` with no string |
| `attribution` | Emitted verbatim in the credit block |
| `provenance_url` | Appended to the credit line as the source link |

Field semantics come from the [rights guide](https://docs.lightdrift.ai/guides/rights); the live [OpenAPI](https://api.lightdrift.ai/openapi.json) is captured alongside for request/filter context. The tool does not require the Lightdrift response shape — any source that produces the same documented fields works.

### Intended-use profile

```json
{
  "schema_version": 1,
  "commercial": true,
  "derivatives": true,
  "share_alike_ok": false,
  "attribution_in_output": true
}
```

All four keys are required and must be booleans. `commercial` and `derivatives` describe the intended use. `share_alike_ok` records whether the downstream license can accept a share-alike obligation. `attribution_in_output` records whether credits will actually be rendered; if so, an unknown attribution requirement is surfaced for review.

## Read the decisions

- A **declared prohibition** (`commercial: false`, `derivatives: false`) is a block, not a review. Do not override it by assumption.
- An **unknown** flag is not permission. Route it to review.
- A **share-alike** asset is fine only if the profile accepts the obligation; this tool does not propagate the license, it only flags it.
- **Attribution missing** on an asset that requires it is a hold. Do not invent a credit.
- `attribution` strings are emitted verbatim. Render external titles and credits as text, not trusted HTML.

## Connect it to a real workflow

Save the selected search response from an existing example — for instance the [Sanity review queue](https://docs.lightdrift.ai/guides/sanity-image-review-queue) or the [presentation workflow](https://docs.lightdrift.ai/guides/presentation-image-search) — then run this checker in the build step before publication. It is complementary to the [attribution export round-trip checker](/guides/attribution-roundtrip-check): that one detects whether metadata survived a CMS export, while this one turns the retained metadata into a use decision and a credit block. Keep the two steps separate; a preserved credit on a non-commercial asset is still a blocked use.

Once a use is cleared, the next step is to emit the publishing metadata itself: the [image structured-data emitter](image-structured-data) maps the same response fields to Schema.org `ImageObject` JSON-LD, Open Graph image tags and a credit line. It copies this decision's credit string into `creditText` and never fabricates a license URL for an identifier-only license, so run this checker first and treat its warnings as inputs to that emitter.

## Limitations

- Reads source-declared metadata; does not verify the source or the declaration.
- Does not assess likeness, trademark, property, model releases, or other rights beyond copyright.
- A pass is not legal clearance; `rights_clearance` stays `not_evaluated`.
- Does not check revocations or whether a downloaded file matches the selected asset ID.
- Does not evaluate where a credit is rendered, whether a CMS preserved it, or whether a rendered page omits it.

## Citation audiences and useful angles

These are hypotheses, not contacted prospects or endorsements. Route any email through Outreach; do not mass-submit or automate comments.

- **Personal and CC-licensed content publishers** explaining attribution practice: a reproducible example showing that the same asset flips between usable and blocked when the intended use changes.
- **CI and static-site maintainers** adding a provenance gate: a stdlib-only check with deterministic exit codes.
- **Licensing explainers and creator-education writers**: the explicit "unknown is not permission" rule and the share-alike flag as a concrete teaching example.
- **CMS and digital-asset-management practitioners**: pairing this use-decision step with the export-preservation checker in one release checklist.

Track pitch → submission → acceptance → live link separately, with referring domain, destination, anchor/context, rel attributes, referral traffic, activation, paid outcomes and cost. All link and outcome fields are empty/unknown at handoff.

## Verification

Rights field semantics, request fields and filter names were checked against the captured live [rights guide](https://docs.lightdrift.ai/guides/rights) and [OpenAPI](https://api.lightdrift.ai/openapi.json) on September 27, 2026 (`sources/manifest.json`). No authenticated search, no paid call, no live migration, and no customer data were used. The fixtures are synthetic and assert no license.
