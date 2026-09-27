"""Offline Lightdrift rate-limit pacing validator and scheduler.

No network, credentials, credit spend, or request execution. It validates a
proposed request schedule against minute, daily and concurrency limits, or
builds a deterministic earliest-start schedule for the same limits.
"""
import argparse
import json
import sys
from pathlib import Path

PLANS = {
    'promo': {'rpm': 30, 'rpd': 1000, 'concurrency': 2},
    'starter': {'rpm': 60, 'rpd': 5000, 'concurrency': 4},
    'growth': {'rpm': 300, 'rpd': 25000, 'concurrency': 10},
    'scale': {'rpm': 1000, 'rpd': 100000, 'concurrency': 25},
}
PLAN_NAMES = {name: name.capitalize() for name in PLANS}
MINUTE_SECONDS = 60
DAY_SECONDS = 86400
MAX_REQUESTS = 2000
MAX_HORIZON_SECONDS = 366 * DAY_SECONDS
LIMITATION = (
    'Minute and daily limits are fixed windows in the product; this tool checks '
    'conservative sliding windows, so a schedule it passes is safe but a schedule '
    'it flags may still pass against the real fixed windows. Durations are caller '
    'estimates, not observed service times. This tool does not reserve credit, send '
    'requests, or implement retries.'
)


class InputError(ValueError):
    pass


def positive_int(value, name, maximum=None):
    if type(value) is not int or value < 1:
        raise InputError(f'{name} must be an integer of at least 1')
    if maximum is not None and value > maximum:
        raise InputError(f'{name} must be at most {maximum}')
    return value


def nonnegative_int(value, name):
    if type(value) is not int or value < 0:
        raise InputError(f'{name} must be an integer of at least 0')
    return value


def resolve_limits(data):
    limits = {}
    basis = 'explicit limits'
    plan = data.get('plan')
    if plan is not None:
        if not isinstance(plan, str) or plan.strip().lower() not in PLANS:
            raise InputError('plan must be one of Promo, Starter, Growth, Scale')
        limits = dict(PLANS[plan.strip().lower()])
        basis = f'plan {PLAN_NAMES[plan.strip().lower()]}'
    supplied = data.get('limits', {})
    if not isinstance(supplied, dict):
        raise InputError('limits must be an object')
    for key in ('rpm', 'rpd', 'concurrency'):
        if key in supplied:
            limits[key] = positive_int(supplied[key], f'limits.{key}', 10_000_000)
    for key in ('rpm', 'rpd', 'concurrency'):
        if key not in limits:
            raise InputError(f'missing limit: provide limits.{key} or a plan')
    if limits['concurrency'] > 500:
        raise InputError('limits.concurrency must be at most 500')
    return limits, basis


def load(path):
    try:
        raw = path.read_text()
    except OSError as exc:
        raise InputError(f'cannot read {path}: {exc}')
    if len(raw.encode()) > 5_000_000:
        raise InputError('input file is larger than 5 MB')
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputError(f'invalid JSON: {exc}')
    if not isinstance(data, dict):
        raise InputError('top-level JSON must be an object')
    return data


def resolve_requests(data, default_duration):
    requests = data.get('requests')
    if not isinstance(requests, list) or not requests:
        raise InputError('requests must be a non-empty array')
    if len(requests) > MAX_REQUESTS:
        raise InputError(f'requests is capped at {MAX_REQUESTS} entries')
    seen = set()
    parsed = []
    for index, entry in enumerate(requests):
        if not isinstance(entry, dict):
            raise InputError(f'requests[{index}] must be an object')
        ident = entry.get('id')
        if not isinstance(ident, str) or not ident.strip():
            raise InputError(f'requests[{index}].id must be a non-empty string')
        if ident in seen:
            raise InputError(f'duplicate request id: {ident}')
        seen.add(ident)
        duration = entry.get('duration_seconds', default_duration)
        duration = nonnegative_int(duration, f'requests[{index}].duration_seconds')
        parsed.append({'id': ident, 'duration_seconds': duration, 'entry': entry})
    return parsed


def window_max(starts, width):
    best = 0
    left = 0
    for right in range(len(starts)):
        while starts[right] - starts[left] >= width:
            left += 1
        best = max(best, right - left + 1)
    return best


def max_overlap(intervals):
    best = 0
    for index, (start, end) in enumerate(intervals):
        if end <= start:
            continue
        best = max(best, sum(1 for a, b in intervals if a <= start < b))
    return best


def validate(data, limits, parsed, basis):
    intervals = []
    for req in parsed:
        at = req['entry'].get('at_second')
        at = nonnegative_int(at, f"requests[{req['id']}].at_second")
        intervals.append((at, at + req['duration_seconds']))
    order = sorted(range(len(parsed)), key=lambda i: intervals[i][0])
    starts = [intervals[i][0] for i in order]
    minute_max = window_max(starts, MINUTE_SECONDS)
    day_max = window_max(starts, DAY_SECONDS)
    concurrency_max = max_overlap(sorted(intervals))
    violations = []
    if minute_max > limits['rpm']:
        violations.append({
            'kind': 'rpm',
            'detail': f'{minute_max} requests fall inside one 60-second window; limit is {limits["rpm"]}',
        })
    if day_max > limits['rpd']:
        violations.append({
            'kind': 'rpd',
            'detail': f'{day_max} requests fall inside one 24-hour window; limit is {limits["rpd"]}',
        })
    if concurrency_max > limits['concurrency']:
        violations.append({
            'kind': 'concurrency',
            'detail': f'{concurrency_max} searches overlap at once; limit is {limits["concurrency"]}',
        })
    report = {
        'tool': 'pace_plan',
        'mode': 'validate',
        'status': 'invalid' if violations else 'valid',
        'limits': limits,
        'limits_basis': basis,
        'total_requests': len(parsed),
        'observed': {
            'max_per_minute': minute_max,
            'max_per_day': day_max,
            'max_concurrent': concurrency_max,
        },
        'violations': violations,
        'limitations': [LIMITATION],
    }
    return report, (1 if violations else 0)


def overlaps(candidate, interval):
    start, end = candidate
    a, b = interval
    return a < end and start < b if end > start else False


def earliest_start(base, duration, intervals, concurrency):
    if duration <= 0 or concurrency < 1:
        return base
    start = base
    for _ in range(len(intervals) + 2):
        if max_overlap(intervals + [(start, start + duration)]) <= concurrency:
            return start
        candidates = []
        for a, b in intervals:
            if overlaps((start, start + duration), (a, b)):
                for point in (a, b):
                    if point > start:
                        candidates.append(point)
        if not candidates:
            return None
        nxt = min(candidates)
        if nxt <= start:
            return None
        start = nxt
    return None


def schedule(data, limits, parsed, basis):
    scheduled = []
    starts = []
    for req in parsed:
        duration = req['duration_seconds']
        base = 0
        if len(starts) >= limits['rpm']:
            base = max(base, starts[len(starts) - limits['rpm']] + MINUTE_SECONDS)
        if len(starts) >= limits['rpd']:
            base = max(base, starts[len(starts) - limits['rpd']] + DAY_SECONDS)
        start = earliest_start(base, duration, scheduled, limits['concurrency'])
        if start is None or start > MAX_HORIZON_SECONDS:
            return {
                'tool': 'pace_plan',
                'mode': 'schedule',
                'status': 'infeasible',
                'limits': limits,
                'limits_basis': basis,
                'total_requests': len(parsed),
                'scheduled_requests': len(scheduled),
                'reason': 'no start time within the 366-day horizon satisfies the configured limits',
                'limitations': [LIMITATION],
            }, 1
        scheduled.append((start, start + duration))
        starts.append(start)
        req['start'] = start
    rows = []
    for req in parsed:
        rows.append({
            'id': req['id'],
            'start_second': req['start'],
            'end_second': req['start'] + req['duration_seconds'],
        })
    all_intervals = [(r['start_second'], r['end_second']) for r in rows]
    flat_starts = sorted(r['start_second'] for r in rows)
    warnings = []
    if len(parsed) > limits['rpd']:
        warnings.append('request count exceeds the daily limit, so the schedule spans multiple days')
    if any(r['duration_seconds'] == 0 for r in parsed):
        warnings.append('zero-duration requests never overlap, so concurrency is not bounded for them')
    if max(flat_starts, default=0) >= DAY_SECONDS:
        warnings.append('one or more requests start on a later day')
    report = {
        'tool': 'pace_plan',
        'mode': 'schedule',
        'status': 'scheduled',
        'limits': limits,
        'limits_basis': basis,
        'total_requests': len(parsed),
        'makespan_seconds': max((end for _, end in all_intervals), default=0),
        'observed': {
            'max_per_minute': window_max(flat_starts, MINUTE_SECONDS),
            'max_per_day': window_max(flat_starts, DAY_SECONDS),
            'max_concurrent': max_overlap(all_intervals),
        },
        'schedule': rows,
        'warnings': warnings,
        'limitations': [LIMITATION],
    }
    return report, 0


def render_text(report):
    lines = [f"pace_plan {report['mode']}: {report['status']}"]
    lines.append(f"limits {report['limits']} ({report['limits_basis']})")
    if report['mode'] == 'validate':
        obs = report['observed']
        lines.append(f"observed per-minute={obs['max_per_minute']} per-day={obs['max_per_day']} concurrent={obs['max_concurrent']}")
        for violation in report['violations']:
            lines.append(f"- {violation['kind']}: {violation['detail']}")
    elif report['status'] == 'scheduled':
        for row in report['schedule']:
            lines.append(f"- {row['id']}: start={row['start_second']}s end={row['end_second']}s")
        lines.append(f"makespan={report['makespan_seconds']}s")
    else:
        lines.append(report.get('reason', 'infeasible'))
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate or build a rate-limit pacing schedule offline.')
    parser.add_argument('--mode', choices=['validate', 'schedule'], default='validate')
    parser.add_argument('--format', choices=['json', 'text'], default='json')
    parser.add_argument('file', type=Path)
    args = parser.parse_args(argv)
    try:
        data = load(args.file)
        limits, basis = resolve_limits(data)
        default_duration = nonnegative_int(data.get('duration_seconds', 0), 'duration_seconds')
        parsed = resolve_requests(data, default_duration)
        if args.mode == 'schedule':
            report, code = schedule(data, limits, parsed, basis)
        else:
            report, code = validate(data, limits, parsed, basis)
    except InputError as exc:
        report = {'tool': 'pace_plan', 'status': 'error', 'error': str(exc)}
        code = 2
    if args.format == 'json':
        print(json.dumps(report, indent=2, sort_keys=False))
    else:
        if report.get('status') == 'error':
            print(f"pace_plan error: {report['error']}")
        else:
            print(render_text(report))
    return code


if __name__ == '__main__':
    sys.exit(main())
