# Audit image layout fit before building the page

A dependency-free Python 3 utility for developers building image selection into CMS, presentation and template workflows. Feed it a saved Lightdrift `/v1/search` or `/v1/similar` response and a target slot. It writes an HTML review table and a JSON audit with the entire original response preserved. It performs no network requests, searches, downloads, image transformations or publication.

## Run a reproducible example

From this directory:

```bash
python3 -m unittest -v
python3 layout_fit.py fixture-response.json --width 960 --height 540 --dpr 2 --output demo
```

Open `demo/report.html` in a browser or inspect `demo/report.json`. The output directory must be new; existing directories are never overwritten. The fixture is synthetic and visibly labelled. Its dimensions exercise arithmetic; it contains no real recommendations, images or rights declarations.

| Synthetic source dimensions | Slot / DPR | Area retained | Upscaling |
| --- | --- | --- | --- |
| 1920 × 1080 | 960 × 540 / 2 | 100% | No |
| 1000 × 1000 | 960 × 540 / 2 | 56.25% | Yes |
| Unknown | 960 × 540 / 2 | Unknown | Unknown |

These are calculated geometry results, not measured search quality or a performance benchmark.

## Use your own saved response

Save the complete JSON response from your existing search workflow as `response.json`. The input must have a top-level `results` array. A presentation/itinerary JSONL record or n8n output wraps the response: extract that record's `response` object first. The utility deliberately rejects arbitrary wrappers instead of guessing which nested candidate list you intended.

```bash
python3 layout_fit.py response.json --width 1200 --height 628 --dpr 1 --output hero-review
```

Keep API keys out of response files and public artifacts. Saved responses can include query-related metadata and image URLs; review before sharing. This utility never asks for a key and the HTML does not load remote images, fonts or scripts. Returned text is HTML-escaped. Missing or invalid source dimensions are reported as unknown, without removing the asset or its rights metadata. Malformed envelopes and invalid target dimensions exit with status 2; an empty results array produces an empty report.

## What the calculation means

For source width `W`, source height `H`, CSS slot `Tw × Th`, and device pixel ratio `D`:

```text
scale = max(Tw × D / W, Th × D / H)
visible source width = Tw × D / scale
visible source height = Th × D / scale
retained area = visible source width × visible source height / (W × H)
```

This is the geometry of filling the slot while preserving aspect ratio. The crop rectangle assumes a centered crop. Moving the focal point changes which pixels remain; it does not change the retained-area fraction. A scale above 1 means the declared source dimensions cannot fill the requested pixel dimensions without enlargement. DPR changes the resolution requirement, not the fraction cropped. Display values are rounded; the enlargement flag uses the unrounded scale.

No universal crop threshold is imposed. A skyline might tolerate a large crop; a portrait can lose the subject with a small crop. The tool cannot see subject placement, optical sharpness, compression, actual file dimensions, or whether the declared dimensions are stale. It trusts the response dimensions and does not download files to validate them. It does not select a winner or reorder the input.

## Review and preserve the evidence

Use the numeric report to identify candidates needing closer visual inspection. Then inspect the image and its source declaration, composition, text placement and suitability for the actual use. The JSON keeps `query_id`, all original response fields, every result and the complete `rights` object, including unknown/future fields. Each candidate remains `needs_visual_and_rights_review`.

Lightdrift's rights metadata reports source declarations. Crop suitability does not establish permission to crop, publish, use commercially, or use a person's likeness. Review the supplied conditions and carry required attribution into the final page or exported document. The HTML is a review aid; it is not a finished credit block or permission certificate. See [Rights answers](https://docs.lightdrift.ai/guides/rights) and the [response contract](https://docs.lightdrift.ai/api-reference/introduction).

## Connect it to a real workflow

Use the [presentation example](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/presentation-image-search) or [itinerary example](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/itinerary-image-search) to obtain candidate responses. Those searches have their own account and usage requirements. Re-running this local report adds no API calls.

[Try Lightdrift with one real layout brief](https://lightdrift.ai/?utm_source=github&utm_medium=example&utm_campaign=layout_fit_v1&utm_content=readme). Save the response, audit your intended dimensions, and record whether an image survives both visual and rights review. A geometrically fitting image is not an activation or paid-account outcome by itself.

For a self-contained typed Python entrypoint that returns this JSON audit inside a workflow, use the [Windmill layout-audit script](../windmill-layout-audit).
