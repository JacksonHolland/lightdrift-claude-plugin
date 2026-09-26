# Candidate images for a three-stop travel itinerary

For developers maintaining a travel planner with recurring location-image retrieval. This Python 3.10+ standard-library example sends three sequential `POST /v1/search` requests for one illustrative San Diego itinerary: Old Point Loma Lighthouse, a garden walk in Balboa Park, and kayaking near La Jolla Shores. These are sample location/activity briefs, not verified travel recommendations or claims that matching images are available.

## Install and run

Clone this public repository and enter the example directory (or download `search_itinerary.py` alone). No pip packages are required:

```sh
git clone https://github.com/JacksonHolland/lightdrift-claude-plugin.git
cd lightdrift-claude-plugin/examples/itinerary-image-search
python3 search_itinerary.py --dry-run
```

Dry-run prints exactly three request bodies without a key or network calls. Edit the three briefs in the script for your own itinerary.

[Create a Lightdrift account and API key](https://lightdrift.ai/sign-up?utm_source=github&utm_medium=example&utm_campaign=lig_itinerary_example_v1&utm_content=readme). Supply `LIGHTDRIFT_API_KEY` through your backend environment or secret manager. Keep it out of source control, browser code and published logs. After checking your account entitlement and [current pricing](https://api.lightdrift.ai/v1/pricing), run:

```sh
python3 search_itinerary.py > itinerary-candidates.jsonl
```

Live execution consumes your search entitlement: up to three requests, one per stop. There is no batch call or automatic retry. Validation of this example used no live product searches and establishes no free-search entitlement.

## Output and failure handling

Each successful search prints one JSON line with wrapper fields `stop` (1–3), `query`, and `response`. The complete API response is retained, including `query_id`, `results`, result `rights`, and any `degraded` or `relaxed` metadata. An empty `results` list remains empty. Earlier successful lines remain if a later request fails.

```python
import json

with open("itinerary-candidates.jsonl") as stream:
    for line in stream:
        stop = json.loads(line)
        response = stop["response"]
        print(stop["stop"], response["query_id"])
        print("Review status:", response.get("degraded"), response.get("relaxed"))
        for candidate in response["results"]:
            print(candidate.get("title"), candidate.get("rights"))
```

Requests ask for five landscape candidates using the documented commercial-permission filter. Other API defaults apply. Filters narrow results; they do not clear a final use. The script stops immediately with a nonzero exit on any HTTP error (including authentication, account/balance and quota errors), transport failure or unexpected response envelope. It does not print keys or raw provider errors. API redirects are refused to avoid forwarding the key. After an uncertain timeout, check account usage before running again; rerunning the itinerary repeats earlier successful searches too.

## Review before placing an image

- Open the source page and verify the actual landmark, activity and location. A query, title or ranking score does not prove geographic identity. Do not imply a stock image depicts a booked hotel or supplier property without verification.
- Inspect dimensions and crop suitability, empty results and any degraded/relaxed metadata. Leave the image unset if no candidate passes review.
- Read the full `rights` object and source declaration, including `license`, `license_verbatim`, `commercial`, `derivatives`, `share_alike`, `attribution_required`, `attribution`, `provenance_url` and `basis`. Unknown or null information is unresolved. Check applicable conditions and other rights involving people, logos or artworks.
- Keep source/license references and required credits with the selected image through itinerary rendering and export. Render returned text as text, not trusted HTML. This script returns candidates for review; it does not select, download or publish source media.

See the [live itinerary guide](https://docs.lightdrift.ai/guides/itinerary-images) and [rights guidance](https://docs.lightdrift.ai/guides/rights). No third-party media is bundled; no geographic accuracy or rights guarantee is made.

## Verification and measurement

Run `python3 verify_local.py` for offline synthetic transport checks. Each successful scenario has three sequential requests; failure scenarios stop within three. Checks cover current documented request fields, shared session, response/rights/degraded preservation, account/quota stops, dry-run and redirect refusal. The bundled [OpenAPI](https://api.lightdrift.ai/openapi.json) was fetched September 26, 2026. See the [response reference](https://docs.lightdrift.ai/api-reference/introduction).

Content version 1.0.0; experiment/cohort `lig_itinerary_example_v1` appears in requests and the signup CTA. A random `client_session` groups each run. Hypothesis: the guide-to-example path helps qualified travel-planner developers try a recurring workflow. Measure guide referrals, first searches, buyer-confirmed useful selections, repeat use and paid usage separately when observed. Publication, a view or a synthetic test is not activation, measured demand or a paid customer result. Those outcomes are currently unknown.
