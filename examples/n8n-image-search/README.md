# Find candidate images for a content brief in n8n

Import a manual workflow that sends one text brief to Lightdrift and returns five candidate images at most for a newsletter, blog, or other content workflow. It uses n8n's built-in HTTP Request node and the existing Lightdrift API. It does not generate images, download media, select an image, or publish content.

## Import and connect your account

1. Download `workflow.json` from this directory (use GitHub's **Download raw file**).
2. In your n8n workflow editor, open the top-right **…** menu, select **Import from File**, and choose that JSON file. Save it. The workflow has only a Manual Trigger; keep it inactive. No schedule or webhook is included.
3. [Create a Lightdrift account](https://lightdrift.ai/sign-up?utm_source=github&utm_medium=example&utm_campaign=lig128_n8n_search_v1&utm_content=readme) and obtain your own API key through your account. Review [current pricing](https://api.lightdrift.ai/v1/pricing) and your available balance before live execution. On September 26, 2026, pricing returned **$0.005 per search ($5 per 1,000)**; one successful request at that rate costs $0.005, regardless of asking for five candidates. Account entitlements and billing rules still apply.
4. Open **Search Lightdrift**. Authentication is **Generic Credential Type**, Generic Auth Type is **Header Auth**. In its credential selector, replace the placeholder with your existing credential or choose **Create New**. Set header **Name** to `X-API-Key` and **Value** to your own Lightdrift API key. Save the credential and select it on the node. The JSON contains only a clearly labelled placeholder credential ID/name; there is no usable credential or secret in it. Keep your key in n8n credentials, not a query, Code node, HTTP body, or exported workflow.
5. Open **Your search settings** (Edit Fields). Enter your own `query`, for example `Coastal lighthouse at sunrise with open space for a newsletter headline`. Keep `allowLiveRequest` as Boolean **false** until ready for the bounded live check below. Use a nonempty brief of at most 1,000 characters. Composition is a request, not a guarantee.

The source query/filter shape follows the existing [presentation example](../presentation-image-search/README.md): `query`, `k: 5`, and `filters: { commercial: true, orientation: "landscape" }`. Other API defaults apply. The request also carries `experiment: "lig128_n8n_search_v1"` to identify this example; it contains no recipient or customer identifier.

## Offline check first — no account or searches

With Node.js installed, run from this directory:

```sh
node verify.mjs
```

This executes the workflow's validation and result-mapping code against **synthetic fixture data**, with no network calls. `fixture-response.json` uses `.invalid` URLs, unknown permissions, and a visibly fictional query ID. It is not a real search, recommendation, rights declaration, or downloadable image. The fixture is not pinned into the importable workflow.

See [VALIDATION.md](VALIDATION.md) for the precise tested versions and compatibility limits. n8n may report the missing credential before running any node until you bind your credential; offline verification does not require that binding.

## Optional live check: one manual request

Only after reviewing your account, pricing, query, and selected credential:

1. In **Your search settings**, set Boolean `allowLiveRequest` to **true**.
2. Click **Execute workflow** exactly once. Run the entire workflow from its Manual Trigger, not the HTTP node directly. The validation node requires exactly one input item. The HTTP node has Execute Once enabled, no pagination, no retry, a 60-second timeout, and redirects off.
3. Open **Review image candidates** and inspect its JSON output. Preserve `query_id` as your receipt and confirm the execution/usage in your own account.
4. Immediately set `allowLiveRequest` back to **false** and save. The flag is an explicit per-execution opt-in convention, **not a self-resetting or account-wide spend cap**. Leaving it true and executing again sends another request. Editing nodes, running a node directly with previous input, or adding triggers changes these bounds.

No live request was made to validate this example. Do not infer working authentication or live search quality from the offline tests. On a non-2xx response, the HTTP node stops the workflow. For 401/403 inspect credentials/access; for balance or rate-limit errors inspect your account and the [API docs](https://docs.lightdrift.ai/api-reference/introduction). No automatic retry is configured. A timeout or interrupted connection can still have consumed search credit: inspect usage before choosing whether to rerun. Avoid sharing execution exports containing keys, headers, or private briefs.

## Review source and license before using a candidate

The final node emits one item even for zero results. It includes `query_id`, `result_count`, a review reminder, and a `candidates` array with `asset_id`, `title`, `score`, `source`, dimensions, `file`, `thumb`, `source_page`, and full `rights`. It also preserves the entire original response in `response`, including `degraded`, backend, ranking, and any future fields. Null scores/titles and missing rights remain unknown. Scores are not calibrated probabilities. Empty results are a valid outcome.

Open the candidate's `source_page` (`rights.provenance_url`) and review the source declaration, `license`, `license_verbatim`, `commercial`, `derivatives`, `share_alike`, `attribution_required`, `attribution`, and `basis`. Unknown/null permission flags are not permission. Carry required attribution into the eventual content. Source-declared commercial permission is not clearance for every use; consider people, logos, and artwork separately. Review subject accuracy and composition with the content author. See [Lightdrift rights guidance](https://docs.lightdrift.ai/guides/rights).

The workflow stops at human review. If you later fetch `file` or `thumb`, the documented asset URL redirects to a signed link valid for one hour. Use a separate download step without the Lightdrift credential; this search node deliberately refuses redirects. Do not send your API key to an image host or source site.

## Limits and rollback

This is a small example, not a bulk content pipeline: no schedules, retries, loops, automatic selection, media downloads, or CMS writes. It requires JavaScript Code nodes enabled and built-in nodes matching the versions in [VALIDATION.md](VALIDATION.md). End-to-end n8n UI import, credential binding, and a real search remain user-side checks; package-level and fixture checks passed. Responses are documented examples rather than a typed OpenAPI success schema, so the final node validates the envelope and preserves fields rather than assuming every result is complete.

To stop, leave `allowLiveRequest` false or remove this workflow. Delete its dedicated n8n credential if no other workflow needs it. Revoke an API key in your Lightdrift account if appropriate. To roll back a repository publication, remove `examples/n8n-image-search/` and its index link. No product deployment, database migration, or billing change is involved.

## Sources

Checked September 26, 2026: [Lightdrift OpenAPI](https://api.lightdrift.ai/openapi.json), [response/auth docs](https://docs.lightdrift.ai/api-reference/introduction), [rights](https://docs.lightdrift.ai/guides/rights), [pricing](https://api.lightdrift.ai/v1/pricing), and the existing presentation example at repository commit `48fd5593a7bcd42beee8cd57fe4ebe982f6b985c`.

Official n8n instructions: [import/export](https://docs.n8n.io/workflows/export-import/), [HTTP Request](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/), [Header Auth](https://docs.n8n.io/integrations/builtin/credentials/httprequest/), and [Code](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.code/). Example version 1.0.0. Publication and subsequent adoption are separate from these compatibility results.
