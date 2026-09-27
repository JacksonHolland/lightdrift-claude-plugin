# Lightdrift for Claude

Real images for the things you build. Search Lightdrift by meaning and retrieve hosted image files with natural-language descriptions, content flags, source provenance, and license information.

## Local installation

```sh
claude --plugin-dir /absolute/path/to/lightdrift-claude-plugin
```

Run `/mcp` and authenticate the Lightdrift connection. Use `/lightdrift:find-images` or ask Claude to source images for your project.

## Claude web / desktop connector

In Claude, open Customize → Connectors → Add custom connector. Use `https://lightdrift.ai/mcp`, then sign in to Lightdrift. The custom connector exposes the tools; it does not install this plugin's skill.

## Try it

- Find a landscape photo of a coastal lighthouse at dusk with open sky on the left, then add it to my hero section with its credit.
- Find three real photographs for a presentation about early space exploration. Include source links and required attribution.
- Find a documented photograph of a mola mola for an educational page. Check the subject against the source metadata.

## Tools and costs

| Tool | Function | Cost |
|---|---|---|
| search_images | Semantic image search with filters | 1 credit per 10 results, rounded up, minimum 1. Search by image or image plus text needs a paid plan |
| find_similar_images | Find images similar to an indexed asset | 1 credit per 10 results, rounded up, minimum 1. Paid plans only |
| get_image | Retrieve file URLs and image metadata | Free |

A Lightdrift account is required. Plans come with monthly credits: the Free plan has 500 credits every month for text search with up to 10 results per search; paid plans add search by image, image plus text, find-similar, and up to 100 results per search. Failed searches are not charged. On Free, image and find-similar calls return 403 `paid_feature`; when monthly credits run out, calls return 402 `credits_exhausted`. Both errors include an `upgrade_url`. Plans and limits: https://lightdrift.ai/#pricing. This plugin does not include credits or an Anthropic subscription. The plugin runtime uses browser OAuth and contains no API keys, scripts, hooks, or executable dependencies. The optional API examples below are separate scripts; they are not run by the plugin.

## Runnable workflow examples

Building repeatable presentation or travel image retrieval? Start with the [presentation workflow guide](https://docs.lightdrift.ai/guides/presentation-image-search), then try the [three-slide presentation example](examples/presentation-image-search) or [three-stop itinerary example](examples/itinerary-image-search).

These optional Python 3.10+ standard-library API scripts are separate from MCP plugin installation. From the itinerary example directory, inspect three request bodies without a key or network calls:

```sh
python3 search_itinerary.py --dry-run
```

Follow each example README for setup and exact commands. Live API execution requires `LIGHTDRIFT_API_KEY` in your backend environment or secret manager; the scripts do not use your MCP OAuth session. Live searches consume account entitlement. Validation used dry-run and offline checks, not live product searches. Review candidate accuracy and source/license conditions, and preserve required credits before using an image.

Watch the request-to-execution steps in the [reproducible terminal walkthrough](examples/terminal-walkthrough), including actual dry-run captures and the explicit switch to your own authenticated searches.

For content automation in n8n, import the [manual image-search workflow](examples/n8n-image-search). It uses your own Header Auth credential, an explicit one-request live opt-in, and returns candidates for source/license review. Offline fixture and package checks are included; no live search was used for validation.

For saved candidate responses, run the [offline layout-fit auditor](examples/layout-fit) to inspect crop loss and resolution requirements for a target slot. It includes synthetic fixtures and tests and makes no network requests.

For Sanity editorial workflows, start with the [image review queue](examples/sanity-image-review): a server-side runner, draft-only mutation and Studio schema, with offline fixtures and explicit live opt-ins.

Compare two saved shortlists with the [offline search-response diff](examples/search-response-diff). It reports entrants, exits, rank movement and metadata changes using synthetic fixtures; it makes no network calls and does not measure relevance.

Run a real Haystack pipeline offline with the [Haystack image-review component](examples/haystack-image-review), including bounded review queues, complete rights preservation and synthetic fixtures.

Check that selected credits and source metadata survive a CMS export with the [offline attribution round-trip checker](examples/attribution-roundtrip). It compares independent baseline and export files; passing does not establish rights clearance.

Catch a changed image-delivery URL before publishing with the [offline delivery URL audit](examples/delivery-url-audit). It compares the URL saved at selection time with the exported URL and flags likely signed or temporary addresses; a clean report does not establish URL lifetime or availability.

Decide whether a saved image's source-declared rights fit an intended use and build the required credit with the [offline rights-compatibility planner](examples/rights-compat). It returns `ok`, `ok_with_attribution`, `review` or `blocked` per asset against a saved use profile and emits a credit block; unknown flags route to review, and a pass is a review aid, not legal clearance.

Keep a batch of search briefs inside the minute, daily and concurrency limits with the [offline rate-limit pacing validator](examples/rate-limit-pacing). It validates a proposed schedule or builds a deterministic earliest-start one from the published plan limits, without sending requests or spending credit.

See which rights fields an image API actually returns, from each provider's own documentation, with the [offline image-rights-field comparison](examples/image-rights-fields-compare). It fails its own build unless every license, attribution and provenance claim keeps a source URL, a verbatim quote and a capture file; `not exposed` means the provider's docs list no such field, not that a license forbids the use.

Catch a drifted or malformed saved response before a template consumes it with the [offline search-response validator](examples/search-response-validate). It checks a stored `/v1/search` response against the published OpenAPI response schema and documented field expectations in two severities — errors contradict the schema, warnings are schema-valid gaps a downstream template still needs — and it is structural, not a rights decision.

Review candidates as images instead of JSON with the [offline review-gallery builder](examples/review-gallery). It renders a saved `/v1/search` response as one self-contained HTML page — a figure per result with declared credit, license and source link, plus a visible marker for any missing metadata — and it copies only declared values, inventing no caption, creator, license or source page.

Turn one or two on-brief images into more like them with the [bounded similar-image expansion utility](examples/similar-expand). It reads seeds from a saved response, plans the request count and worst-case cost before spending, then merges the responses into one identity-deduplicated shortlist that keeps each result's source-declared rights; the default is a dry run.

Pull a saved response into a spreadsheet-ready table with the [offline editorial shortlist exporter](examples/response-to-shortlist). It writes a CSV with the rights fields flattened into columns and a JSON shortlist that keeps each result's full rights object, flags rows that still need review, and never calls Lightdrift or spends credit.

Summarize a batch of saved search envelopes with the [offline search telemetry report](examples/search-telemetry). It reads one or more stored `/v1/search` or `/v1/similar` responses and counts what they declare — latency and `timing_ms` phases, `pool_size`/`reranked` ratios, result counts, and `mode`/`ranking`/`query_type`/`backend` distributions, including `degraded` and `relaxed` responses — with no key, network call or credit. The counts describe only the files you pass in, not service performance.

Reconcile saved search and `/v1/asset/{asset_id}` responses into one canonical inventory with the [offline asset-inventory reconciler](examples/asset-inventory). It merges metadata for known asset ids, lists the assets still missing canonical metadata with a ready-to-run `GET /v1/asset/{id}` plan, counts duplicates, and flags field/rights conflicts between the two views; it makes no network call and a conflict is a signal to review, not a verdict.

## Image rights

Licenses belong to the individual images, not this plugin. Preserve required attribution and source links. Lightdrift reports the source's rights declarations; they are not a blanket clearance for every intended use.

## Privacy and support

The server receives the tool arguments Claude sends, such as search queries, filters, and asset IDs, along with authentication needed to associate calls with your account. Successful searches consume your account's credits. The plugin itself has no separate telemetry or local execution hooks.

- Privacy policy: https://lightdrift.ai/privacy
- Terms: https://lightdrift.ai/terms
- Documentation: https://docs.lightdrift.ai/guides/images-mcp
- Support: jackson@lightdrift.ai

## Publication status

This package is being prepared for submission. It is not yet listed or verified by Anthropic.

## Hosted downloads

Hosted Claude environments must permit outbound access to `api.lightdrift.ai` and `26b17c22f73aeeffe81bee6419afe7ad.r2.cloudflarestorage.com`, the current storage host used by the download redirect. Search and metadata tools can work even when the session network policy blocks image downloads. Report that restriction accurately; do not bypass it.

## Multiple installations

A standalone custom connector and this plugin can expose the same three tools. This is expected when both installation methods are used. The skill prefers the plugin connection and avoids duplicate calls; retain the standalone connector if you also use hosted Claude.
