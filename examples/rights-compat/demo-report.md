# Image rights compatibility report

> `rights_clearance: not_evaluated` — this report is a review aid, not legal clearance.

## Intended use

- commercial: `true`
- derivatives: `true`
- share_alike_ok: `false`
- attribution_in_output: `true`

## Summary

- assets: 9
- ok: 1
- ok_with_attribution: 1
- review: 5
- blocked: 2

## Per-asset decisions

| asset_id | status | license | reason codes |
| --- | --- | --- | --- |
| fixture-cc0-0001 | ok | cc0 | - |
| fixture-ccby-0002 | ok_with_attribution | cc-by | - |
| fixture-ccbync-0003 | blocked | cc-by-nc | license_declares_noncommercial |
| fixture-ccbynd-0004 | blocked | cc-by-nd | license_forbids_derivatives |
| fixture-ccbysa-0005 | review | cc-by-sa | share_alike_obligation |
| fixture-missing-attribution-0007 | review | cc-by | attribution_required_but_missing |
| fixture-no-license-0009 | review | - | license_unknown |
| fixture-no-rights-0008 | review | - | rights_missing |
| fixture-unknown-flags-0006 | review | cc-by | commercial_permission_unknown, derivative_permission_unknown, attribution_requirement_unknown |

## Credit block

- Coastal cliffs at dawn by A. Author via ExampleSource, CC BY 4.0 (https://example.org/assets/fixture-ccby-0002)

## Limitations

- This tool reads source-declared metadata; it does not verify the source or the declaration.
- It does not assess likeness, trademark, property, model or other rights beyond copyright.
- A pass is not legal clearance: rights_clearance remains not_evaluated for every asset.
- It does not check revocations or whether a downloaded file matches the selected asset ID.
- It does not evaluate where the credit is rendered or whether a CMS preserved it.
