# Compare two saved image-search responses offline

When you change a search brief or request setting in an image-selection workflow, inspect what changed before replacing a saved shortlist. This Python 3.10+ standard-library utility compares Lightdrift response envelopes by `asset_id`. It reports entrants, exits, rank movement, changed result fields and changed envelope metadata. It makes no network calls and needs no key.

## Reproduce the example

From this directory:

```sh
python3 -m unittest -v
python3 search_diff.py fixtures/before.json fixtures/after.json > diff.json
```

Both input files are **synthetic fixtures**, not captured API results. They contain no actual images or source-license declarations. The report shows:

| Observation | Fixture result |
| --- | --- |
| Entered | `fixture:c` |
| Exited | `fixture:a` |
| Shared | `fixture:b` |
| Shared asset rank | 2 → 1 |
| Shared asset score | 0.6 → null |
| Set overlap (intersection / union) | 1 / 3 |

The positive rank change of 1 means the shared asset moved one position toward the top. The overlap value describes membership only. Neither observation demonstrates improved relevance. A null score is preserved, not converted to zero or treated as an error.

## Share a readable review

For a pull-request attachment or a local Markdown review, use:

```sh
python3 search_diff.py fixtures/before.json fixtures/after.json --format markdown > review.md
```

The Markdown report contains membership, ranks, field changes, envelope changes and input fingerprints. Input-derived values are JSON-encoded and HTML-escaped inside preformatted blocks; they do not become image embeds or source hyperlinks. Use a Markdown viewer supporting HTML preformatted blocks. JSON remains the default for automation. This output is for review, not a quality score or CI gate. The fixture report is synthetic. Review input metadata before sharing.

## Compare your own snapshots

Save two complete JSON response bodies from your existing workflow as `before.json` and `after.json`. Then run:

```sh
python3 search_diff.py before.json after.json > review.json
```

The utility expects one object with a `results` array in each file. If you use the [presentation example](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/presentation-image-search) or [itinerary example](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/itinerary-image-search), select the intended JSONL record and extract its `response` object first. Compare the same slide or stop; do not combine unrelated responses just because the wrappers share a shape.

For example, extract the first record locally:

```python
import json
from pathlib import Path
with open('candidates.jsonl') as stream:
    record = json.loads(next(stream))
Path('before.json').write_text(json.dumps(record['response'], indent=2))
```

Keep the original request body, observation time and complete response beside each snapshot. The response alone may not establish which request settings differed. Input SHA-256 hashes in the report let you associate a comparison with the exact saved bytes; they do not establish when or how the files were obtained.

## Read the report

- `entered` and `exited` follow their respective input result order.
- `shared` follows the after order and records one-based ranks. Rank change is before rank minus after rank.
- `field_changes` compares all result fields other than `asset_id`. Nested objects are reported whole, making changed rights/source structures available for review.
- `before_present` and `after_present` distinguish a missing key from an explicit null.
- `envelope_changes` compares all top-level fields except `results`. Check changes to ranking, mode, backend, relaxed filters or degraded responses before interpreting position changes.
- `overlap_jaccard` is null when both sets are empty. No overlap denominator exists in that case.

Keep the original files: unchanged metadata is not copied into this diff. It is an inspection artifact, not a replacement asset manifest or a source of publishing rights. Review the image, source and [rights answer](https://docs.lightdrift.ai/guides/rights) before use. A change in the response's license or attribution metadata deserves source review; this tool does not determine legal validity.

Malformed envelopes, missing or repeated asset IDs, repeated JSON object keys and non-finite JSON constants fail with exit code 2 and no report on standard output. Successful comparison exits 0 even if differences exist. This is a review utility, not a CI pass/fail policy. The shell redirection shown above can overwrite an existing report; choose a fresh output filename when preserving earlier reviews.

## What this comparison cannot establish

Different briefs, filters, result counts, collection updates or serving conditions can change the returned list. Scores are not calibrated probabilities; some serving paths return null. This tool deliberately does not compute score improvement, significance, search latency averages or a quality winner. Its fixtures verify mechanics only. Large snapshots are loaded into memory; use normal saved search envelopes rather than an unbounded dataset.

This comparison matches results by `asset_id`, so the same underlying image arriving under two different ids appears as one entry leaving and another entering. To group cross-id duplicates by canonical source URL or source-native id before comparing, see the [search-result dedup utility](https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples/search-result-dedup).

Reports may include query-related metadata, image URLs and attribution text from your inputs. Review them before sharing publicly. No remote content is fetched or rendered by the utility.

## Next step

Use the [search guide](https://docs.lightdrift.ai/guides/search) to design one controlled request change, then compare saved responses. If starting a recurring image workflow, [create a Lightdrift account](https://lightdrift.ai/sign-up?utm_source=github&utm_medium=example&utm_campaign=search_response_diff_v1&utm_content=readme) and follow the [quickstart](https://docs.lightdrift.ai/quickstart). New live searches consume your account's entitlement; the offline comparison does not. Consult [current pricing](https://docs.lightdrift.ai/api-reference/current-search-pricing) before collecting new snapshots.
