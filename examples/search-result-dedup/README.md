# Find duplicate images across saved search responses

When several search answers, mirror sources or feed runs are merged into one shortlist, the same underlying image can arrive under two different `asset_id` values. This Python 3.10+ standard-library utility reads one or more saved Lightdrift response bodies and reports likely duplicates using identity signals that already travel with the data: a canonicalized source/provenance URL or a source-native external id. It makes no network calls and needs no key.

## What it does

For every result the tool collects:

- a **canonical source URL** from `provenance_url`, `source_url`, `source_page_url`, `page_url`, `license_url` or `url`, including the same fields nested under `rights`, `source` or `provenance`;
- an **external id** from `source_asset_id`, `external_id`, `provider_id`, `native_id`, `asset_uid` or `source_id`, paired with `source` when present.

URLs are lowercased at the scheme and host, default ports and fragments are dropped, tracking parameters (`utm_*`, `fbclid`, `gclid`, `ref`, ...) are removed, the remaining query is sorted and a trailing slash is stripped. Path case and percent-encoding are preserved because object stores treat them as significant.

Results that share any identity key are grouped into connected clusters. Each cluster reports every shared key and a confidence level:

| Confidence | Meaning |
| --- | --- |
| `asset_id` | The same `asset_id` appears in more than one saved response. Exact same asset. |
| `source_external_id` | Two different `asset_id` values resolve to the same `source` + native id. |
| `canonical_url` | Two different `asset_id` values canonicalize to the same source URL. |

## Reproduce the example

From this directory:

```sh
python3 -m unittest -v test_dedup_assets.py
python3 dedup_assets.py fixtures/search-response.json fixtures/second-response.json > report.json
python3 dedup_assets.py fixtures/search-response.json --exit-nonzero-on-duplicates > /dev/null; echo $?
```

The second command exits `0`; the third exits `1` because the fixture contains duplicates. The fixtures are **synthetic** and contain no real images, licenses or customer data. The fixture run reports 12 assets, 3 clusters and 5 ungrouped results.

## Use it on your own snapshots

Save each complete response body you want to compare as JSON. Each file must be one object with a `results` array.

```sh
python3 dedup_assets.py first.json second.json third.json > report.json
```

Only strong identity signals are used. `thumbnail_url`, `preview_url` and `download_url` are deliberately **excluded**: CDN placeholder thumbnails are frequently shared between unrelated images, so using them would manufacture false duplicate clusters. The report lists the excluded signals so a reviewer can see the boundary. The tool also does not compare pixels or embeddings; two visually identical images with no shared URL or id stay separate, and two different crops served from one source URL are reported as one cluster. Treat a cluster as a prompt to review the source pages, not as a deletion instruction.

## Read the report

- `inputs` records the path and SHA-256 of each file, so a review can be tied to exact saved bytes. It does not establish when the bytes were obtained.
- `counts.assets_without_identity_signal` and the `assets_without_identity_signal` array list results that carried no URL or external id; these can never be deduplicated by identity.
- Each `clusters[]` entry has `cluster_id`, `confidence`, `shared_keys` and `members` with `asset_id`, `source`, `envelope` and `rank`.
- `ungrouped` counts results that stayed in a cluster of one.

Malformed envelopes, missing or empty `asset_id`, repeated `asset_id` inside one envelope, repeated JSON object keys and non-finite JSON constants fail with exit code `2` and no report on standard output. Successful runs exit `0` even when duplicates exist. Add `--exit-nonzero-on-duplicates` to return `1` when clusters are found, for a CI gate.

## What this cannot establish

Canonicalization is heuristic. Distinct images can share a templated source URL, and one image can be served under several unrelated URLs. The tool does not verify that a cluster's source pages are live, that the files are identical, or that any of them is licensed for your use. A match on a canonical URL or external id is evidence of shared identity, not of rights, quality or provenance validity.

Reports may include query-related metadata and source URLs from your inputs. Review them before sharing publicly.

## Next step

Use the [search guide](https://docs.lightdrift.ai/guides/search) to design one controlled request change, and [compare two saved responses](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/search-response-diff) before merging them. Check the [rights guide](https://docs.lightdrift.ai/guides/rights) before publishing any clustered asset, then [create a Lightdrift account](https://lightdrift.ai/sign-up?utm_source=github&utm_medium=example&utm_campaign=search_result_dedup_v1&utm_content=readme) and follow the [quickstart](https://docs.lightdrift.ai/quickstart). The offline utility is free to run; collecting new live responses consumes your account's entitlement. Consult [current pricing](https://docs.lightdrift.ai/api-reference/current-search-pricing) before collecting more snapshots.

## Suggested backlink audiences

- Image-pipeline and static-site maintainers who merge multiple stock sources and would cite a provenance-based dedup gate.
- Open-source DAM and CMS projects discussing canonical asset identity.
- Data-engineering and ETL writers covering entity resolution with cheap deterministic keys before fuzzy matching.
- Anyone documenting multi-source image workflows where the same photo appears under several provider ids.

These are hypotheses for the Earned owner to qualify; no destination has been contacted and no link is claimed. Track pitch, submission, acceptance and live link separately, including whether any resulting link is nofollow or sponsored.
