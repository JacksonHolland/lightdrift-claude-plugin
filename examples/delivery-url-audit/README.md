# Audit image-delivery URLs before a CMS export

A CMS can preserve an image's title and credit while silently changing the URL used to display it. A query-stripping transform can remove delivery context; saving the final URL after a redirect can turn a temporary download address into a long-lived content field. This offline Python utility compares the URL returned at selection time with the URL your export is about to publish.

Use it between selecting an image and publishing a static page, itinerary or slide deck. It produces a small JSON review report suitable for CI. It never calls Lightdrift, fetches an image, follows redirects or spends search credits.

## Reproduce the demonstration

Requires Python 3.10 or newer, with no dependencies. From this directory:

```sh
python3 -m unittest -v
python3 delivery_audit.py fixtures/pass.json
python3 delivery_audit.py fixtures/review.json
```

The first fixture passes with exit code 0. The second returns exit code 1 with four checked items: one passes and three need review. This is a deliberately constructed example, not an observed failure rate or benchmark. All fixture domains and identities are synthetic.

For your own export, write a local UTF-8 JSON manifest:

```json
{
  "items": [
    {
      "asset_id": "your-selected-asset-id",
      "returned_url": "https://media.example/asset/demo?query_id=example",
      "exported_url": "https://media.example/asset/demo?query_id=example"
    }
  ]
}
```

These three fields form this utility's input contract; they are not an API response schema. `returned_url` is the exact selected `thumb` or file URL from your stored response. `exported_url` is the image URL extracted from your final CMS/static export. Keep the originals in your private build input; do not put private URLs in public test fixtures. Compare equivalent representations: decode HTML entities when extracting an HTML attribute, but do not strip or reconstruct query parameters. Use one row per selected asset. Repeated asset IDs trigger review; if your page intentionally repeats an image, resolve that finding in your workflow.

## Read and resolve the report

| Finding | What it means | Next action |
| --- | --- | --- |
| `delivery_url_changed` | The strings differ, including query order and encoding | Compare the private inputs; check whether the exporter changed the address intentionally |
| `possible_signed_or_temporary_url` | A known signature, token or expiry query key appears | Check the source's delivery contract; avoid persisting a final redirect URL as a permanent address |
| `https_absolute_required` | The value is not an absolute HTTPS URL | Restore the selected delivery URL or review your deliberate local-hosting design |
| `embedded_credentials` | The URL contains user information | Remove credentials from publication input and investigate the exporting step |
| `missing_asset_id` | The manifest cannot identify the selected asset | Restore the stored asset identity before publishing |

Additional findings identify empty values, malformed syntax, fragments, unexpected fields and repeated IDs. Rows use zero-based indexes back into your input file. No URL, query value, host, path or asset ID is echoed in the report. Exit 0 means no configured checks found an issue; exit 1 means at least one row needs review; exit 2 means the input could not be read or its document shape was invalid. CI can retain the report without retaining the raw manifest.

The comparison is deliberately exact. Changing the query order may be harmless, but the utility cannot prove that for a provider's signature rules. It flags the difference instead of rewriting the URL. It also leaves `query_id` untouched: the [search guide](https://docs.lightdrift.ai/guides/search) describes delivery URLs carrying query context for download attribution. The [reference-image guide](https://docs.lightdrift.ai/guides/reference-image-search) explains that file URLs can redirect to signed downloads and recommends retaining asset identity and source metadata. Neither this tool nor its fixtures assigns an expiry time to a URL.

## Boundaries and integration

This is an offline export check, not a downloader, URL availability test, security scanner, rights validator or proof of permanent hosting. A clean report does not establish that the URL resolves, returns image bytes, is authorized, is safe to fetch, or will remain usable. Signature-key detection is heuristic; unrecognized keys and path-based signatures can pass. A generic `token` or `expires` key may also cause a false positive. Human review of flagged rows remains part of the workflow. The utility has no DNS, redirect, content-type or image-dimension checks.

Keep asset identity, creator and license/source metadata alongside delivery fields. Use the [rights guide](https://docs.lightdrift.ai/guides/rights) for source review, and the [presentation workflow](https://docs.lightdrift.ai/guides/presentation-image-search) for a selection-to-export example. This utility complements attribution-export checks: those detect lost metadata; this one detects delivery URL changes.

To use actual search results, start with the [Lightdrift quickstart](https://docs.lightdrift.ai/quickstart), select an image, and feed your stored URL plus the exported URL into this audit before publication. Lightdrift remains a stock-image API/MCP; this example does not add a hosting guarantee or change the product's pricing.
