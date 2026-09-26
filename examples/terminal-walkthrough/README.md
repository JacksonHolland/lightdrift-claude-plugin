# From an image brief to an inspectable search request

A terminal walkthrough for developers adding recurring image retrieval to a presentation builder or travel planner. Run the existing examples, inspect the requests, then choose whether to execute them with your own Lightdrift account. Python 3.10+ and Git are sufficient; no pip packages are needed.

## 1. Reproduce the dry-run

From a terminal:

```sh
git clone https://github.com/JacksonHolland/lightdrift-claude-plugin.git
cd lightdrift-claude-plugin
git checkout f113f60
python3 examples/presentation-image-search/search_slides.py --dry-run \
  "Wind turbines in open countryside, wide composition" \
  "Engineers inspecting solar panels" \
  "City skyline at dawn with space for a headline"
python3 examples/itinerary-image-search/search_itinerary.py --dry-run
```

The checkout pins the existing example code used for this capture. These commands print three JSON lines each and make **no search requests**. They need no API key. Each run generates a new `client_session`, so that value will differ from this recording.

Here is the actual first presentation line captured on September 26, 2026:

```json
{"slide": 1, "method": "POST", "url": "https://api.lightdrift.ai/v1/search", "body": {"query": "Wind turbines in open countryside, wide composition", "k": 5, "filters": {"commercial": true, "orientation": "landscape"}, "client_session": "9ffe1754-2366-46fb-b6c0-eaf9dd06b73d", "experiment": "lig103_presentation_search_v1"}}
```

Read the complete, unedited captures: [presentation requests](presentation-dry-run.jsonl) and [itinerary requests](itinerary-dry-run.jsonl). These are request previews, not image results or evidence of live search success. No product search or source-media download was used to produce this demo.

Look for `POST /v1/search`, one brief per request, `k: 5`, and the commercial/landscape filters. The session groups the three requests. The example-specific experiment values remain unchanged. The preview does not prove that five suitable candidates exist, that a location matches, or that an image is cleared for your use.

## 2. Make the explicit transition to live execution

[Create your Lightdrift account and API key](https://lightdrift.ai/sign-up?utm_source=github&utm_medium=demo&utm_campaign=lig122_terminal_demo_v1&utm_content=walkthrough). Check your account entitlement and [current pricing](https://api.lightdrift.ai/v1/pricing) before continuing. On September 26, 2026 the pricing endpoint returned $0.005 per search ($5 per 1,000). Three successful searches would cost $0.015 at that rate; running both examples would make up to six searches. The dry-run establishes no free-search entitlement.

Supply your own `LIGHTDRIFT_API_KEY` through your backend environment or secret manager. For an interactive **Bash** session, this prompt keeps the value out of shell history and terminal echo:

```bash
read -r -s -p 'Lightdrift API key: ' LIGHTDRIFT_API_KEY
printf '\n'
export LIGHTDRIFT_API_KEY
```

Choose one workflow. Removing `--dry-run` is the step that sends authenticated, potentially billable requests:

```sh
# Presentation: up to three sequential real searches.
python3 examples/presentation-image-search/search_slides.py \
  "Wind turbines in open countryside, wide composition" \
  "Engineers inspecting solar panels" \
  "City skyline at dawn with space for a headline" > presentation-candidates.jsonl

# Alternative itinerary workflow: up to three sequential real searches.
python3 examples/itinerary-image-search/search_itinerary.py > itinerary-candidates.jsonl
```

Run only the command you intend to pay for. Afterward, `unset LIGHTDRIFT_API_KEY` removes the variable from this shell. Keep credentials out of source control, browser code and logs. MCP OAuth is separate from these API scripts.

Each successful live call writes one JSON line containing `slide`/`topic` or `stop`/`query`, plus the full `response`. That response contains the real results and rights metadata; this walkthrough supplies no simulated results. The scripts stop on errors without retrying. Earlier successful lines remain if a later call fails. Check usage after an uncertain timeout before rerunning, because earlier searches can be charged again.

## 3. Review a candidate before using it

Inspect empty results and any degraded response metadata. Check the candidate's source page, subject/location, license declaration and attribution requirements. Keep required credits and source references with the chosen asset. The scripts return candidates; they do not select, download or place an image for you.

Continue with the existing [presentation workflow guide](https://docs.lightdrift.ai/guides/presentation-image-search) or [itinerary workflow guide](https://docs.lightdrift.ai/guides/itinerary-images), and the [rights guidance](https://docs.lightdrift.ai/guides/rights). Detailed script behavior remains in the [presentation README](../presentation-image-search) and [itinerary README](../itinerary-image-search).

Demo version 1.0.0; experiment `lig122_terminal_demo_v1`. The signup CTA identifies demo referrals; API requests retain the original example experiments. Evaluate tagged visits, first successful search, buyer-confirmed useful selection, repeat use and paid usage separately. This publication does not establish audience reach or customer outcomes. No third-party media is included.
