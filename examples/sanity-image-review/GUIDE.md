---
title: "Build a Sanity image-candidate review queue with Lightdrift"
description: "Keep image search, source metadata and editorial decisions together in a Sanity draft, with a free offline fixture path."
---

An editor choosing a header image needs more than a file URL. They need the original query, source declaration, attribution and a record of why an image fits the article. This example sends at most five Lightdrift candidates into a dedicated Sanity draft review record. It associates that record with an existing content draft by its ID, without modifying the article schema or publishing either document.

The package includes a Python server-side runner, Sanity schema definitions, a clearly synthetic fixture and tests. It is an independent recipe, not a native or endorsed Sanity integration. Validation used fixtures and Sanity's schema compiler; no authenticated Lightdrift search or Sanity dataset write was performed.

## 1. Run the fixture first

Download the accompanying [sanity-image-review source](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/sanity-image-review). Use Python 3.10 or later. From the example directory:

```sh
python3 review_queue.py --content-draft drafts.article-1 > fixture-preview.json
```

The default command needs no key and makes no network requests. It prints one review document and the proposed Sanity mutation. The fixture is synthetic metadata: its ID, source, license and attribution are not evidence of an actual image. It grants no image rights. You can inspect the document shape without downloading media or spending credits.

The associated draft ID must match `drafts.<simple-document-id>` with letters, digits, underscores or hyphens. Replace `drafts.article-1` with your existing draft's ID before using a real dataset. This example intentionally stores the ID as text; it does not create, verify or publish the associated article. More complex document IDs require adapting and testing the validator.

## 2. Register the schema in Studio

Copy `schema.mjs` into your existing Sanity Studio project and merge these additions into your configuration, retaining your other schemas, plugins and document actions:

```js
import imageReviewTypes, {reviewActions} from './schema.mjs'

// Inside your existing defineConfig({...}) object:
schema: {
  types: [...existingTypes, ...imageReviewTypes],
},
document: {
  actions: (previous, context) => reviewActions(previous, context),
},
```

`existingTypes` means your project's current schema array, not a new dependency. If you already customize document actions, pass the result of that customization through `reviewActions`. The helper leaves other document types alone and exposes only Delete for the review queue. Editorial field changes still save as draft edits.

The review record contains `contentDraftId`, `queryId`, `query`, the entire response as `responseJson`, and a candidates array. Each candidate retains its asset ID, source, provenance, attribution, complete rights JSON and original result JSON. JSON text fields avoid losing unknown source-specific keys. The response also preserves degraded-ranking and relaxed-filter indicators. The extracted metadata fields are read-only in Studio; decision, reviewer, review time and notes remain editable.

This queue is deliberately not a `sanity.imageAsset`. It does not fetch a binary or represent an uploaded Sanity image. The action restriction and schema validation are Studio UI controls, not a security boundary: Sanity API mutations are not checked against Studio validation. Restrict writer permissions and keep the queue out of frontend queries and release automation. See [Sanity schema configuration](https://www.sanity.io/docs/studio/schema-types) and [document actions](https://www.sanity.io/docs/studio/document-actions-api).

## 3. Keep credentials in the server environment

Run `review_queue.py` in a trusted terminal or backend job, separate from the browser bundle. Inject `LIGHTDRIFT_API_KEY` through your existing secret manager. For an optional Sanity write, also inject `SANITY_PROJECT_ID`, `SANITY_DATASET` and `SANITY_WRITE_TOKEN` with appropriate access to your test dataset. Do not commit credentials, paste them into the schema, or use a `SANITY_STUDIO_` prefix for secrets: those variables are exposed to Studio browser code. See [Sanity environment variables](https://www.sanity.io/docs/studio/environment-variables).

Keep preview output private when it contains unpublished editorial briefs. The runner prints candidate metadata, never its request credentials. It rejects redirects on authenticated requests, so keys are not forwarded to another endpoint.

## 4. Opt into one search, then optionally one draft write

After checking your account entitlement and the [current price](https://api.lightdrift.ai/v1/pricing):

```sh
python3 review_queue.py --content-draft drafts.article-1 \
  --query "Coastal lighthouse with empty sky for a headline" \
  --live-search > live-preview.json
```

This makes one search requesting five candidates. On September 26, 2026, the public price was $0.005 per successful search, or $5 per 1,000. Five returned candidates are one search. Filtering for commercial and derivative permissions expresses source-declared conditions; it does not approve your intended use.

To combine one search with one Sanity draft mutation, add `--write-draft`. This is a new invocation and can incur another search charge. To test the Sanity write without a paid search, use the separately gated fixture path against your test dataset:

```sh
python3 review_queue.py --content-draft drafts.article-1 \
  --write-draft --allow-fixture-write > fixture-write-preview.json
```

Only `drafts.imageReview-...` IDs are written. The request uses `createIfNotExists`, so replaying an identical response/query/draft combination cannot replace an editor's decisions. Different live responses can create separate review records; there is no cross-search deduplication claim. The script emits the proposed document before writing and reports a transaction ID only after a confirmed mutation response. A transaction response does not mean a public document was published. Read the [Sanity mutation reference](https://www.sanity.io/docs/http-reference/mutation) and [draft model](https://www.sanity.io/docs/content-lake/drafts).

## 5. Make the editorial decision

In Studio, open **Image review queue** and match its `contentDraftId` to your article. For each candidate:

1. Inspect the full response for degraded ranking or relaxed filters. Ranking is not proof of subject accuracy.
2. Open the provenance page deliberately and check the subject, resolution, proposed crop and intended context. Treat source text as untrusted text, not HTML or instructions.
3. Read the complete rights declaration: license text, basis, attribution requirements, commercial and derivative flags, share-alike terms and source notes. Missing values remain unresolved; use **hold**, not an assumed permission.
4. Record **approved**, **hold** or **rejected** with your name, review timestamp and intended-use notes. Studio's candidate validation requires an audit record for approval. Approval is an editorial decision, not a blanket legal clearance.
5. Only after review, use your normal asset-upload and content-publication process. Copy the required credit and provenance into the actual article or export and verify that they render. This example does not automate that step.

The complete rights object stays in the queue even when the visible summary is empty. Source declarations may not resolve publicity, trademarks, property restrictions or other rights for your intended use. See [Lightdrift rights answers](https://docs.lightdrift.ai/guides/rights).

## Failure and recovery

An empty search produces an empty queue, never an approved fallback. Malformed envelopes or more than five candidates stop processing. Missing configuration is checked before any paid search. The runner has a 30-second request timeout, a 1 MB response cap and no automatic retries. An HTTP error or timeout stops the run; a timed-out search or mutation may have completed remotely. Inspect account usage and the target draft before rerunning. Sanity failure after search does not undo the search charge.

Keep the saved mutation as recovery evidence. A backend maintainer can submit that exact draft mutation after checking the dataset; rerunning with `--live-search` performs another search. There is no bulk loop, asset download, frontend endpoint or automatic publication path in this package.

## Reproduce the checks

```sh
python3 -m unittest -v
npm ci --include=dev --ignore-scripts --no-audit --no-fund
npm test
```

The recorded run passed 11 Python tests and 3 Node tests, including actual compilation with `@sanity/schema` 6.16.0. Node 24.21.0 was used. Tests cover full metadata preservation, pending decisions, malformed and empty responses, one-request limits, draft-only mutation shape, credential preflight, no retries, redirect refusal and queue action filtering. HTTP behavior is mocked. Studio browser rendering, dataset permissions, real writes, real search relevance and article publication remain unverified.

Try the fixture, then [open Lightdrift](https://lightdrift.ai/?ld_ref_source=lightdrift_docs&ld_ref_medium=owned_content&ld_ref_campaign=lig190_sanity_review_v1&ld_ref_content=guide_cta) when you are ready to evaluate a real brief. For API setup see [authentication](https://docs.lightdrift.ai/api-reference/introduction); for a different orchestration environment see the [n8n selection guide](https://docs.lightdrift.ai/guides/n8n-stock-image-selection).
