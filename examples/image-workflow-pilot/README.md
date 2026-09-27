# Check the acceptance record for an image-workflow pilot

A fixed-scope image-workflow pilot delivers a runner and a twenty-brief run on
real material, then has to be accepted against published criteria. This Python
3.10+ standard-library utility reads the run artifacts a pilot produces and
reports each criterion (A1–A7) as `pass`, `fail` or `unchecked`, emitting one
machine-readable acceptance record plus an optional Markdown summary.

It makes **no network call, needs no API key and spends no search credit**. It
never infers a buyer decision: A1–A4 are checked from the artifacts, while A5–A7
are **buyer-recorded** and stay `unchecked` (overall verdict `incomplete`) until
a buyer-answers file supplies them.

## Run a reproducible example

```bash
python3 pilot_acceptance.py \
  --briefs fixtures/briefs-20.json \
  --requests fixtures/requests.jsonl \
  --candidates fixtures/candidates.jsonl \
  --shortlist fixtures/shortlist.json \
  --record acceptance-record.json \
  --markdown acceptance-record.md
```

Against the bundled real `pilot-v1` sample fixtures (no buyer answers) this
exits `3` with A1–A4 passing and A5–A7 unchecked. Supplying the clearly-labeled
synthetic `fixtures/buyer-answers.synthetic.json` demonstrates the accepted
path (`acceptance-record.accepted-demo.json`).

## Criteria

| # | Requirement | Checked from |
| --- | --- | --- |
| A1 | the twenty briefs used are the buyer-confirmed list | run artifacts |
| A2 | one searchable request per brief is produced | run artifacts |
| A3 | candidates + provenance returned for every brief that returned results | run artifacts |
| A4 | every candidate row carries its rights fields and a `review_status` | run artifacts |
| A5 | usable candidate found for >= 16 of 20 briefs | buyer answers |
| A6 | required credit/source info survives to the review step | buyer answers |
| A7 | the buyer can run the handoff on their own briefs | buyer answers |

Buyer answers shape:

```json
{"usable_briefs": 17, "attribution_survives": true, "handoff_run": true}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | all seven criteria pass |
| 1 | at least one checked criterion fails |
| 2 | malformed or unreadable input / schema error |
| 3 | no failure, but one or more buyer-recorded criteria are unchecked |

## Fixtures

`fixtures/` are the real artifacts from `revenue/pilot-v1/sample-output/`
(synthetic fixture data; not live searches, not rights declarations).
`fixtures/buyer-answers.synthetic.json` is a clearly-labeled synthetic demo, not
a buyer decision.

## Tests

```bash
python3 -m unittest -v test_pilot_acceptance
```

17 standard-library tests cover both verdicts, every structural failure,
buyer-recorded criteria and all four exit codes.

## Distinction from sibling examples

| Example | Focus |
| --- | --- |
| `response-to-shortlist` | flatten a saved response into a review table |
| `bounded-search-plan` | validate and price a batch offline before execution |
| `delivery-url-audit` | detect a changed image-delivery URL |
| **this utility** | check a pilot's acceptance record against published criteria |

## Files

- `pilot_acceptance.py` — the checker.
- `test_pilot_acceptance.py` — 17 standard-library tests.
- `fixtures/` — briefs, request log, candidate log, shortlist and a synthetic buyer-answers demo.
- `acceptance-record.json`, `acceptance-record.md` — generated from `fixtures/` (incomplete).
- `acceptance-record.accepted-demo.json` — generated with the synthetic buyer answers.
- `test-evidence.txt` — recorded test and fixture runs.
- `sources/manifest.json` — captured inputs with SHA-256.

This is a documentation utility for the `image-workflow-pilot-v1` pilot; see the
[image-workflow integration pilot guide](https://docs.lightdrift.ai/guides/image-workflow-integration-pilot).
