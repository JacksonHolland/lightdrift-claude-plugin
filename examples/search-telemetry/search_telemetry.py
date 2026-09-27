#!/usr/bin/env python3
"""Summarize saved Lightdrift search responses offline.

Reads one or more saved /v1/search (or /v1/similar) response envelopes and
reports observed latency, timing phases, rerank/pool ratios, result counts,
degraded/relaxed counts and envelope value distributions. Standard library
only; makes no network requests, needs no key and spends no credits.
"""
import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

MODES = ('auto', 'none', 'text')
RESULT_FIELDS = ('asset_id', 'title', 'width', 'height')


def load_objects(path, errors):
    """Return the list of response objects found in one file or directory."""
    objects = []
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.suffix.lower() == '.json')
        if not files:
            errors.append(f'{path}: no .json files found')
            return objects
        for child in files:
            objects.extend(load_objects(child, errors))
        return objects
    try:
        raw = path.read_text(encoding='utf-8')
    except OSError as exc:
        errors.append(f'{path}: {exc}')
        return objects
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        errors.append(f'{path}: invalid JSON ({exc.msg})')
        return objects
    if isinstance(data, list):
        for index, item in enumerate(data):
            if isinstance(item, dict):
                objects.append((str(path), index, item))
            else:
                errors.append(f'{path}[{index}]: not an object')
    elif isinstance(data, dict):
        objects.append((str(path), 0, data))
    else:
        errors.append(f'{path}: top level is not an object or array')
    return objects


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _summary(values):
    if not values:
        return {'count': 0}
    ordered = sorted(values)
    return {
        'count': len(values),
        'min': min(values),
        'max': max(values),
        'mean': round(statistics.fmean(values), 3),
        'median': round(statistics.median(values), 3),
    }


def _looks_like_response(obj):
    return isinstance(obj, dict) and (
        'results' in obj or 'query_id' in obj or 'timing_ms' in obj or 'pool_size' in obj)


def build_report(objects):
    responses = [(source, index, obj) for source, index, obj in objects if _looks_like_response(obj)]
    skipped = len(objects) - len(responses)

    latency = []
    timing = {'embed': [], 'retrieve': [], 'rerank': []}
    pool = []
    reranked = []
    result_counts = []
    mode_counts = Counter()
    ranking_counts = Counter()
    query_type_counts = Counter()
    backend_counts = Counter()
    degraded = 0
    relaxed_counter = Counter()
    relaxed_responses = 0
    missing = Counter()
    field_presence = Counter()
    total_assets = 0
    results_with_id = 0
    results_with_dimensions = 0

    for _source, _index, obj in responses:
        if 'latency_ms' in obj:
            if _finite(obj['latency_ms']):
                latency.append(obj['latency_ms'])
            else:
                missing['latency_non_numeric'] += 1
        else:
            missing['latency_ms'] += 1

        timing_obj = obj.get('timing_ms')
        if isinstance(timing_obj, dict):
            for phase in timing:
                value = timing_obj.get(phase)
                if _finite(value):
                    timing[phase].append(value)
                elif phase in timing_obj:
                    missing[f'timing_{phase}_non_numeric'] += 1
        else:
            missing['timing_ms'] += 1

        if 'pool_size' in obj:
            if _finite(obj['pool_size']):
                pool.append(obj['pool_size'])
            else:
                missing['pool_size_non_numeric'] += 1
        else:
            missing['pool_size'] += 1

        if 'reranked' in obj:
            if _finite(obj['reranked']):
                reranked.append(obj['reranked'])
            else:
                missing['reranked_non_numeric'] += 1
        else:
            missing['reranked'] += 1

        results = obj.get('results')
        if isinstance(results, list):
            result_counts.append(len(results))
            for item in results:
                total_assets += 1
                if isinstance(item, dict):
                    if item.get('asset_id'):
                        results_with_id += 1
                    if _finite(item.get('width')) and _finite(item.get('height')):
                        results_with_dimensions += 1
        else:
            missing['results'] += 1

        if 'mode' in obj:
            mode_counts[str(obj['mode'])] += 1
        else:
            missing['mode'] += 1

        if 'ranking' in obj:
            ranking_counts[str(obj['ranking'])] += 1
        else:
            missing['ranking'] += 1

        if 'query_type' in obj:
            query_type_counts[str(obj['query_type'])] += 1
        else:
            missing['query_type'] += 1

        if 'backend' in obj:
            backend_counts[str(obj['backend'])] += 1
        else:
            missing['backend'] += 1

        if obj.get('degraded'):
            degraded += 1

        relaxed = obj.get('relaxed')
        if isinstance(relaxed, list) and relaxed:
            relaxed_responses += 1
            for name in relaxed:
                relaxed_counter[str(name)] += 1

        for field in ('query_id', 'degraded', 'relaxed'):
            if field in obj:
                field_presence[field] += 1

    ratios = [round(r / p, 3) for r, p in zip(reranked, pool) if p and r <= p]

    return {
        'responses': len(responses),
        'skipped_non_response_objects': skipped,
        'result_count': _summary(result_counts),
        'results_total': total_assets,
        'results_with_asset_id': results_with_id,
        'results_with_dimensions': results_with_dimensions,
        'latency_ms': _summary(latency),
        'timing_ms': {phase: _summary(values) for phase, values in timing.items()},
        'pool_size': _summary(pool),
        'reranked': _summary(reranked),
        'reranked_over_pool_ratio': _summary(ratios),
        'degraded_responses': degraded,
        'relaxed_responses': relaxed_responses,
        'relaxed_filters': dict(sorted(relaxed_counter.items())),
        'mode': dict(sorted(mode_counts.items())),
        'ranking': dict(sorted(ranking_counts.items())),
        'query_type': dict(sorted(query_type_counts.items())),
        'backend': dict(sorted(backend_counts.items())),
        'field_presence': dict(sorted(field_presence.items())),
        'missing_or_non_numeric': dict(sorted(missing.items())),
        'notice': ('Offline summary of saved response envelopes. Counts describe only the '
                   'inputs given, not service performance, relevance or a benchmark.'),
    }


def render_text(report):
    lines = [
        f"responses: {report['responses']} (skipped non-response objects: {report['skipped_non_response_objects']})",
        f"results per response: {report['result_count'].get('count', 0)} present, "
        f"min {report['result_count'].get('min')} max {report['result_count'].get('max')} "
        f"mean {report['result_count'].get('mean')}",
        f"latency_ms: {report['latency_ms'].get('count', 0)} present, "
        f"min {report['latency_ms'].get('min')} max {report['latency_ms'].get('max')} "
        f"median {report['latency_ms'].get('median')}",
        f"degraded responses: {report['degraded_responses']}",
        f"relaxed responses: {report['relaxed_responses']}",
        f"modes: {report['mode']}",
        f"rankings: {report['ranking']}",
        f"query types: {report['query_type']}",
        f"notice: {report['notice']}",
    ]
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path,
                        help='saved response JSON files, or directories containing them')
    parser.add_argument('--format', choices=('json', 'text'), default='json')
    parser.add_argument('--output', type=Path, default=None,
                        help='write the report here instead of stdout')
    args = parser.parse_args(argv)

    errors = []
    objects = []
    for path in args.inputs:
        if not path.exists():
            errors.append(f'{path}: not found')
            continue
        objects.extend(load_objects(path, errors))
    if errors:
        for message in errors:
            print(f'search-telemetry: {message}', file=sys.stderr)
        return 2

    report = build_report(objects)
    text = (json.dumps(report, indent=2, sort_keys=False, allow_nan=False) + '\n'
            if args.format == 'json' else render_text(report))
    if args.output is not None:
        args.output.write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
