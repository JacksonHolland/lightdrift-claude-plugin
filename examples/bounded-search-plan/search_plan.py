"""Offline text-search plan validator. No transport, credentials, or execution."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

RESULTS_PER_CREDIT = 10  # 1 credit per 10 results, rounded up, minimum 1 per search.
PRICING_VERSION = '2026-09-28'
BOOL_FILTERS = {'commercial', 'attribution_required', 'derivatives', 'monochrome', 'ai_generated'}
LIST_FILTERS = {'license_id', 'source', 'colors', 'format'}
INT_FILTERS = {'min_width', 'min_height', 'year_min', 'year_max'}
FILTERS = BOOL_FILTERS | LIST_FILTERS | INT_FILTERS | {'orientation', 'nsfw_max'}


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in {low}..{high}')
    return value


def credits_for(k):
    # Credits are reserved from the requested k: ceil(k / 10), minimum 1.
    return max(1, -(-k // RESULTS_PER_CREDIT))


def request(row):
    if not isinstance(row, dict) or set(row) - {'query', 'k', 'filters'}:
        raise ValueError('request supports only query, k and filters')
    q = row.get('query')
    if not isinstance(q, str) or not q.strip() or len(q) > 1000:
        raise ValueError('query must be a nonblank string of at most 1000 characters')
    k = integer(row.get('k', 10), 1, 100, 'k')
    f = row.get('filters', {})
    if not isinstance(f, dict) or set(f) - FILTERS:
        raise ValueError('unknown filter or filters is not an object')
    for key, value in f.items():
        if value is None:
            continue  # Explicit null is preserved, never merged with omission.
        if key in BOOL_FILTERS and type(value) is not bool:
            raise ValueError(f'{key} must be boolean or null')
        if key in LIST_FILTERS and (not isinstance(value, list) or not value or
                                    any(not isinstance(x, str) or not x.strip() for x in value)):
            raise ValueError(f'{key} must be a nonempty string array or null')
        if key in INT_FILTERS:
            integer(value, 0, 2_147_483_647, key)
        if key == 'orientation' and (not isinstance(value, str) or value not in {'landscape', 'portrait', 'square'}):
            raise ValueError('planner supports landscape, portrait or square orientation')
        if key == 'nsfw_max' and (type(value) not in (int, float) or not 0 <= value <= 1):
            raise ValueError('nsfw_max must be finite and between 0 and 1')
    if f.get('year_min') is not None and f.get('year_max') is not None and f['year_min'] > f['year_max']:
        raise ValueError('year_min exceeds year_max')
    # Deliberately preserve text, array order, nulls and absent filter defaults.
    return {'query': q, 'k': k, 'filters': copy.deepcopy(f)}


def build_plan(data):
    if not isinstance(data, dict) or set(data) != {'requests', 'budget_credits', 'max_requests', 'attempts_per_request'}:
        raise ValueError('plan requires exactly requests, budget_credits, max_requests, attempts_per_request')
    rows = data['requests']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise ValueError('requests must contain 1..10000 entries (local planner limit)')
    budget = integer(data['budget_credits'], 0, 10_000_000, 'budget_credits')
    cap = integer(data['max_requests'], 0, 100000, 'max_requests')
    attempts = integer(data['attempts_per_request'], 1, 10, 'attempts_per_request')
    errors, unique, positions, duplicates = [], [], {}, []
    for index, row in enumerate(rows):
        try:
            normalized = request(row)
        except ValueError as exc:
            errors.append({'index': index, 'error': str(exc)})
            continue
        key = json.dumps(normalized, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
        if key in positions:
            duplicates.append({'index': index, 'duplicate_of': positions[key]})
        else:
            positions[key] = index
            unique.append({'first_index': index, 'request_sha256': hashlib.sha256(key.encode()).hexdigest(), 'body': normalized})
    ceiling = len(unique) * attempts
    base = sum(credits_for(row['body']['k']) for row in unique)
    cost = base * attempts
    reasons = []
    if errors:
        reasons.append('invalid_requests')
    if ceiling > cap:
        reasons.append('request_cap_exceeded')
    if cost > budget:
        reasons.append('budget_exceeded')
    allowed = not reasons
    return {'status': 'within_plan_limits' if allowed else 'blocked', 'block_reasons': reasons,
            'input_count': len(rows), 'valid_unique_count': len(unique), 'duplicates': duplicates,
            'invalid': errors, 'attempts_per_request': attempts,
            'valid_subset_request_ceiling': ceiling, 'max_requests': cap,
            'budget_credits': budget, 'valid_subset_estimate_credits': cost,
            'base_estimate_credits': base,
            'credit_rule': {'results_per_credit': RESULTS_PER_CREDIT, 'minimum_per_search': 1,
                            'version': PRICING_VERSION, 'source': 'https://api.lightdrift.ai/v1/pricing'},
            'executable_request_count': len(unique) if allowed else 0,
            'requests': unique if allowed else [],
            'note': 'Offline estimate only. Every allowed attempt is budgeted at its full reserved credits (from requested k); invalid rows block the entire plan. No calls executed or credits reserved.'}


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate JSON object key')
        out[key] = value
    return out


def load(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError('input exceeds local 5 MB limit')
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON number')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    args = parser.parse_args()
    try:
        report = build_plan(load(args.plan))
    except (ValueError, OSError, UnicodeError, RecursionError):
        print(json.dumps({'status': 'invalid_input', 'error': 'Malformed plan; check schema, types, bounds and JSON keys.'}))
        return 2
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report['status'] == 'within_plan_limits' else 1


if __name__ == '__main__':
    raise SystemExit(main())
