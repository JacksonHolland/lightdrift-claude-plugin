# Sanity image review queue

Start with [the guide](GUIDE.md). Run `python3 review_queue.py --content-draft drafts.article-1` for the zero-network fixture. Live modes require explicit flags; no image publication is implemented.

Runtime: Python 3.10+ standard library. Schema testing: Node 24 and the pinned package-lock dependency; `npm ci --include=dev --ignore-scripts --no-audit --no-fund`, then `npm test`. Python tests: `python3 -m unittest -v`.

The fixture is synthetic test data, never a ledger event or claimed search result. Do not use its license/attribution as real rights evidence.

## Check metadata after export

After editor selection, use the [attribution round-trip checker](../attribution-roundtrip) to compare an independent original baseline against your CMS export. It detects missing credits and nested rights metadata, including null-to-empty transformations. A passing metadata comparison does not establish rights clearance. To hand the same saved response to a reviewer as a self-contained HTML page of thumbnails with declared credits and missing-metadata markers, render it with the [offline review-gallery builder](../review-gallery).
