# Demo report: pacing a five-brief burst without exceeding two requests per minute

Command: `python3 pace_plan.py --mode schedule fixtures/schedule-burst.json`

- status: `scheduled`
- limits: `{'rpm': 2, 'rpd': 1000, 'concurrency': 1}` (explicit limits)
- requests: 5
- makespan: 120 seconds
- observed per-minute: 2 (limit 2)

| request | start (s) | end (s) |
| --- | --- | --- |
| b-1 | 0 | 0 |
| b-2 | 0 | 0 |
| b-3 | 60 | 60 |
| b-4 | 60 | 60 |
| b-5 | 120 | 120 |

The first two briefs start together; the next two wait for the next minute window and the fifth waits for the following window. Zero-duration requests never overlap, so the single concurrency slot is not exercised here. The fixtures are synthetic and no API request was sent.
