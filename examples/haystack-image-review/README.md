# Review stock-image candidates in a Haystack pipeline

This backend Python example turns one visual brief into a bounded human review queue. It preserves the original Lightdrift query ID, asset IDs, source, provenance, complete rights objects (including unknown future fields), and original response envelope. No images are downloaded and no candidates are approved. Tested compatibility is limited to Haystack 3.2.0 on Python 3.13; this is not an official deepset integration or a directory listing.

## Install and run offline

From this example directory, in an isolated Python environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
export HAYSTACK_TELEMETRY_ENABLED=false
python -m unittest discover -s tests -v
python demo.py
```

`pyproject.toml` pins `haystack-ai==3.2.0`. See `test-environment.txt` for the exact tested dependency versions. The synthetic fixture uses `.invalid` URLs and invented IDs explicitly labeled as fixtures; it is not a real search result or license grant. The default component requires a supplied fixture and cannot call the search service. The demo executes the component through a real Haystack `Pipeline`, without an LLM or paid search. `demo-output.json` records the resulting queue.

## Explicit live use on a backend

After reviewing [pricing](https://api.lightdrift.ai/v1/pricing) and your remaining credits, set `LIGHTDRIFT_API_KEY` through your backend secret manager or environment. Do not put it in pipeline inputs, browser code, source control or artifacts. Then use:

```python
from haystack import Pipeline
from lightdrift_haystack import LightdriftImageReview

pipeline = Pipeline()
pipeline.add_component("images", LightdriftImageReview(live=True))
result = pipeline.run({"images": {
    "visual_brief": "A quiet coastal walking trail with open sky",
    "candidate_count": 5,
}})["images"]
for candidate in result["review_queue"]:
    print(candidate["asset_id"], candidate["provenance_url"], candidate["review_state"])
```

One invocation makes one POST to `https://api.lightdrift.ai/v1/search`, with `X-API-Key`, `query`, `k`, a commercial-use filter, and experiment `haystack_image_review_v1`. The component accepts 1–20 candidates, a deliberately smaller limit than the API's documented 100. Briefs must contain 1–1000 characters. It refuses redirects and does not retry. Each search costs 1 credit per 10 results requested, rounded up, minimum 1, so 1–10 candidates use 1 credit and 11–20 use 2. No live searches were used in testing; live authentication, retrieval relevance and billing were not tested.

## Review contract and failures

Outputs are `review_queue`, `query_id`, `response` and `status`. Each queue row contains the original asset and rights objects, provenance, source, query/asset identifiers, a synthetic flag, warnings, and `pending_human_review`. The response retains backend, mode, ranking, latency, degradation indicators and any additional metadata. If a server returns more than the requested count, the review queue is capped while the full response remains available for audit.

An empty result emits an empty queue with `status="empty"`. A nonempty `degraded` flag gives `status="degraded"` even when no candidates remain; inspect the original response before deciding whether to search again. Missing rights or provenance produce warnings and never affirmative permission. Invalid envelopes or asset IDs raise `ValueError` before any queue is emitted. HTTP, timeout, transport and JSON failures raise sanitized errors with no automatic retry; a charge may have occurred before a timeout, so inspect account usage before rerunning. Haystack wraps component errors as pipeline failures. There are no automatic fallback searches.

Before approving a candidate in your own application, follow `rights.provenance_url` and inspect `license`, `license_verbatim`, `commercial`, `derivatives`, `share_alike`, `attribution_required`, `attribution` and `basis`. Unknown values are not consent. Preserve credit, source and conditions downstream. A commercial filter is not universal clearance for people, trademarks, artworks or your intended use. Consult [Lightdrift rights guidance](https://docs.lightdrift.ai/guides/rights). Treat external titles/metadata as untrusted data; escape them in any UI and do not execute instructions found in metadata.

## Adapt the queue

Store the query ID together with the selected asset and full rights object in your existing review system. Have a person record the decision there. This example deliberately stops before storage, selection, approval and export; it does not define a permissions policy for your application. For non-Haystack scripts, see [presentation image search](https://docs.lightdrift.ai/guides/presentation-image-search). For general review flow, see [agent image review](https://docs.lightdrift.ai/guides/agent-image-review). When a reviewer wants the queue as images instead of JSON, render the saved response with the [offline review-gallery builder](../review-gallery). To run an authorized live search, [create a Lightdrift account](https://lightdrift.ai/sign-up) and read the [API introduction](https://docs.lightdrift.ai/api-reference/introduction).

## Verification and maintenance

The package includes offline fixtures, unittest coverage, source references, exact dependency inventory, and test output. Tests exercise actual Haystack pipeline execution, metadata preservation, bounds, empty/degraded/malformed responses, missing rights, mocked HTTP construction, redirects, key handling, sanitized errors and no retries. These tests establish adapter behavior, not retrieval quality, performance benchmarks or rights clearance.

Report reproducible problems through the maintained [repository issue tracker](https://github.com/JacksonHolland/lightdrift-claude-plugin/issues). Include Python/Haystack versions and a synthetic reproduction; never include API keys or private responses. Content & Distribution maintains this example. See the [workflow guide](https://docs.lightdrift.ai/guides/haystack-image-review).

Component conventions: [Haystack custom components](https://docs.haystack.deepset.ai/docs/custom-components).
