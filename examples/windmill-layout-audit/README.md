# Audit saved image responses in a Windmill Python script

Use one dependency-free script to check whether candidate dimensions can fill a page, CMS or presentation slot. It accepts a saved search response, CSS width/height and device pixel ratio (DPR), and returns a JSON audit with the complete response and asset metadata preserved. No API requests, downloads, secrets, paid calls or image processing occur.

## Run in Windmill

1. Create a **Python** script and paste the complete contents of [`layout_audit.py`](layout_audit.py). It is self-contained; no repository imports or resources are needed.
2. The typed entrypoint is `main(response: dict, width: float, height: float, dpr: float = 1.0) -> dict`. Enter the saved response object in `response`, the slot size in `width` and `height`, and optionally `dpr`.
3. For a reproducible preview, use the values in [`fixture-arguments.json`](fixture-arguments.json). The fixture is explicitly synthetic, with placeholder URLs, not a real search or quality benchmark.
4. Run a preview and inspect the returned JSON. A subsequent flow step can consume `candidates`; preserve `original_response` with your review record. Publishing a script in your own workspace is separate from submission to the Hub.

Windmill's [Python quickstart](https://www.windmill.dev/docs/getting_started/scripts_quickstart/python) documents `main` as the entrypoint, annotations as input-schema/UI hints and return values as JSON. These conventions were checked September 26, 2026. This package was tested locally in Python; no hosted Windmill execution or Hub acceptance is claimed.

## Run the same entrypoint locally

From this directory, with Python 3.10 or newer:

```bash
python3 -m unittest -v
python3 - <<'PY'
import json
from pathlib import Path
from layout_audit import main
args = json.loads(Path('fixture-arguments.json').read_text())
print(json.dumps(main(**args), indent=2, allow_nan=False))
PY
```

The parity test expects the adjacent `../layout-fit` directory in this repository. The script itself requires only its single file. Its geometry and audit functions are vendored from [the original layout-fit utility](../layout-fit) at commit `fc056d6c7317bb1ad8c6b557e7ad44c0acd64821` so users can paste it directly into a script editor. The additional entrypoint checks JSON serialization and detaches output metadata from the caller's object.

## Inputs and results

`response` must be an object containing a `results` array of objects. Pass the saved search response itself, not a JSON string or a surrounding workflow record. Empty results are accepted. The script preserves input order and duplicates; it never chooses a winner. It retains all fields, including query metadata, `relaxed`, `degraded`, source URLs, rights and future fields.

Target dimensions and DPR must be positive finite numbers; booleans, strings, zero and negative values raise `ValueError`. Missing or invalid source dimensions produce `unknown_dimensions`. Non-JSON metadata or arithmetic outside representable numeric ranges fails rather than producing an invalid JSON report.

For the synthetic fixture at 960 × 540 CSS pixels, DPR 2:

| Candidate | Retained area | Upscaling required |
| --- | --- | --- |
| 1920 × 1080 | 100% | No |
| 1000 × 1000 | 56.25% | Yes |
| Unknown dimensions | Unknown | Unknown |

Each candidate contains its input index, unchanged asset data, geometry and `needs_visual_and_rights_review`. The geometry assumes a centered, aspect-ratio-preserving cover crop. DPR changes required resolution, not crop fraction. See the [original formula and limitations](../layout-fit/README.md#what-the-calculation-means).

It trusts declared dimensions; it cannot inspect pixels, subjects, focal points or sharpness. Source-declared rights are retained, not approved. Review the actual image, source conditions and required credit before use. See [Lightdrift rights answers](https://docs.lightdrift.ai/guides/rights). Saved responses may contain private query metadata or asset URLs: remove sensitive information before sharing a run or public demo.

## Reuse and distribution

A useful flow is: saved candidate response → this audit → visual/rights review → CMS or deck selection. Use the same report for several slot sizes without repeating a search. This package adds a Windmill-native entrypoint to the existing utility; it does not add another search API integration.

Windmill's [Hub sharing guide](https://www.windmill.dev/docs/misc/share_on_hub) accepts Python scripts and describes a review step for availability through Hub-synced instances. Proposed submission title: **Audit saved image dimensions for a layout slot**. Proposed description: **Offline center-crop and upscaling audit for a saved image-search response. Preserves full source and rights metadata. No credentials or network requests. Geometry is not visual or rights approval.**

Hub account access, submission, approval and any resulting citation must be verified separately. This source release is not a Hub listing or endorsement.
