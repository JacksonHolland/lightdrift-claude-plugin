# Image-workflow pilot — acceptance record

- Pilot: `image-workflow-pilot-v1`
- Overall verdict: **incomplete**
- Checked: 4 / 7 (pass 4, fail 0, unchecked 3)
- Generated from: `fixtures`

| # | Requirement | Status | Detail |
| --- | --- | --- | --- |
| A1 | the twenty briefs used are the buyer-confirmed list | pass | 20 confirmed briefs match requests |
| A2 | one searchable request per brief is produced | pass | exactly 20 requests |
| A3 | candidates + provenance returned for every brief that returned results | pass | 20 briefs have candidate records (0 with result_count 0) |
| A4 | every candidate row carries its rights fields and a review_status | pass | 20 rows carry rights + review_status |
| A5 | usable candidate found for >= 16 of 20 briefs (buyer-recorded) | unchecked | usable_briefs not supplied by buyer; requires buyer's acceptance sheet |
| A6 | required credit/source info survives to the review step (buyer-recorded) | unchecked | attribution_survives not supplied by buyer; requires buyer's acceptance sheet |
| A7 | the buyer can run the handoff on their own briefs (buyer-recorded) | unchecked | handoff_run not supplied by buyer; requires buyer's acceptance sheet |

`unchecked` criteria are buyer-recorded (A5-A7). This file does not
infer a buyer decision; supply a buyer answers file to complete them.
