# Candidate stock images for three presentation slides

For developers building recurring image retrieval into presentation software: send three image briefs to Lightdrift and return candidates for human review. This Python 3.10+ example uses only the standard library. It performs three sequential `POST /v1/search` calls, one per topic; there is no batch endpoint, image generation or slide rendering in this example.

## Try it

[Create a Lightdrift account and API key](https://lightdrift.ai/sign-up?utm_source=github&utm_medium=example&utm_campaign=lig103_presentation_search_v1&utm_content=readme), then save `search_slides.py` from this directory. Keep the key on your backend, outside source control and client-side code. Supply `LIGHTDRIFT_API_KEY` through your environment or secret manager.

Inspect request construction without a key or network calls:

```bash
python3 search_slides.py --dry-run \
  "Wind turbines in open countryside, wide composition" \
  "Engineers inspecting solar panels" \
  "City skyline at dawn with space for a headline"
```

Once your environment contains `LIGHTDRIFT_API_KEY`, run real searches:

```bash
python3 search_slides.py \
  "Wind turbines in open countryside, wide composition" \
  "Engineers inspecting solar panels" \
  "City skyline at dawn with space for a headline" > candidates.jsonl
```

Live execution consumes your account's search entitlement. The public [pricing endpoint](https://api.lightdrift.ai/v1/pricing) returned $0.005/search ($5/1,000) on September 26, 2026: three successful searches would total $0.015 at that rate. Check current pricing and your balance before running. No product searches were made to validate this example.

The requests ask for five landscape candidates whose source-declared licenses permit commercial use. Composition text expresses a preference, not a guarantee. Other API defaults still apply. Fewer or no candidates may be returned; matching a filter is not universal rights clearance.

## Output contract

Standard output is JSON Lines: one line after each successful slide search. `slide` (1–3), `topic` and `response` are this example's wrapper fields. `response` is the unmodified API response; the wrapper does not add candidate fields or manufacture empty results.

The [documented response](https://docs.lightdrift.ai/api-reference/introduction) contains `query_id`, `results`, `backend`, `mode`, `ranking` and `latency_ms`. Each result includes `asset_id`, `score`, `title`, `source`, `width`, `height`, `file`, `thumb` and `rights`. Titles and scores can be null. `score` is not a calibrated probability. A degraded response may carry a `degraded` message; preserving the envelope keeps that visible.

For example, consume the real output without assuming a nonempty result list:

```python
import json

with open("candidates.jsonl") as stream:
    for line in stream:
        slide = json.loads(line)
        response = slide["response"]
        print(slide["slide"], response["query_id"])
        if response.get("degraded"):
            print("Review retrieval status:", response["degraded"])
        for candidate in response["results"]:
            print(candidate["asset_id"], candidate["file"], candidate["rights"])
```

The script stops at the first HTTP, transport or response-shape error and exits nonzero. Earlier successful lines remain in the output file. It never automatically retries: a timeout can leave billing outcome unknown. Inspect account usage before rerunning, since rerunning all three topics can charge for earlier successful searches again. API keys and raw provider error bodies are not printed. API redirects are refused so the credential is not forwarded elsewhere.

## Review before putting an image on a slide

Open each candidate's source page from `rights.provenance_url` and review the source declaration and license conditions. Check `license`, `license_verbatim`, `commercial`, `derivatives`, `share_alike`, `attribution_required`, `attribution` and `basis`. Unknown/null permissions are not affirmative permission. Preserve required credit and source information alongside the chosen asset and in the exported presentation where required. Consider rights beyond copyright, including people, logos and artworks.

Review subject accuracy, composition and suitability with the presentation author. Returning candidates is not selecting or approving them. The example does not fetch any source media or bundle third-party images. When you later fetch a `file` or `thumb` URL, the docs describe a 302 redirect to a signed download link valid for one hour; follow those download redirects without sending your API key to the destination.

## Sources and verification

Contract checked September 26, 2026 against the live [OpenAPI](https://api.lightdrift.ai/openapi.json), [authentication and response docs](https://docs.lightdrift.ai/api-reference/introduction), [quickstart](https://docs.lightdrift.ai/quickstart), and [rights guidance](https://docs.lightdrift.ai/guides/rights), consistent with the canonical product fact audit. Local checks cover request construction, three sequential requests using a fake transport, preservation of response/rights fields, and stop-on-error behavior. Those checks are not proof of live account access, relevance, rights clearance or successful product execution.

Experiment `lig103_presentation_search_v1` is included in each request; a random `client_session` groups the three calls. The signup link uses the same campaign identifier. The hypothesis is that a copyable example reduces integration effort. Measure tagged visits, successful first search, buyer-confirmed useful image selection, repeat workflow use and paid usage separately when observed. A repository view is not activation or payment.

Content version: 1.0.0. Prepared for the `examples/presentation-image-search/` path in the existing Lightdrift plugin repository; publication status is tracked separately from these files.
