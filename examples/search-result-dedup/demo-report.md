# Demo report: dedup_assets.py

Synthetic fixtures, no live search, no network.

Command:

```sh
python3 dedup_assets.py fixtures/search-response.json fixtures/second-response.json
```

Result: 12 assets across 2 saved responses, 3 duplicate clusters, 7 assets in clusters, 5 ungrouped, 1 asset with no identity signal.

| Cluster | Confidence | Members | Shared key(s) |
| --- | --- | --- | --- |
| 1 | `asset_id` | `fixture:mirror-a` (env 1), `fixture:mirror-b` (env 1), `fixture:mirror-a` (env 2) | `asset_id=fixture:mirror-a`; `source_external_id=examplesource:IMG-204`; `canonical_url=https://cdn.example.org/photo/CLIFF-01.jpg` |
| 2 | `source_external_id` | `fixture:ext-a`, `fixture:ext-b` | `source_external_id=examplesource:ID-7788` |
| 3 | `canonical_url` | `fixture:rights-url`, `fixture:rights-url-two` | `canonical_url=https://rights.example.org/assets/AA-1` |

What the fixture demonstrates:

- `mirror-a` and `mirror-b` differ in the host case and carry tracking/fragment noise (`utm_source`, `utm_medium`, `#top`), yet canonicalize to the same URL. A third occurrence of the same `asset_id` in the second response joins the cluster.
- `ext-a` and `ext-b` have different URLs but the same source-native id, so they cluster on `source_external_id`.
- `rights-url` and `rights-url-two` expose no top-level URL; the source URL lives under `rights.provenance_url`, is still found, and clusters after tracking removal.
- `fixture:case-diff` has a different path case (`cliff-01.jpg`) and stays separate: path case is preserved.
- `fixture:thumb-a` and `fixture:thumb-b` share a placeholder `thumbnail_url` but are **not** clustered, because thumbnail URLs are excluded identity signals.
- `fixture:no-signal` appears in `assets_without_identity_signal`.

Exit codes: normal run `0`; `--exit-nonzero-on-duplicates` returns `1`; malformed input returns `2`. `test-evidence.txt` records 26 passing tests.
