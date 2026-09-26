#!/usr/bin/env python3
"""Compare locally saved selected-image metadata with a normalized CMS export."""
import argparse
import json
import sys
from pathlib import Path

MAX_BYTES = 5_000_000
FIELDS = ('source', 'provenance_url', 'attribution', 'rights')


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate JSON object key')
        out[key] = value
    return out


def reject_constant(value):
    raise ValueError('Non-finite JSON number')


def load(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Input exceeds 5 MB')
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def index(doc, baseline=False):
    if not isinstance(doc, dict) or type(doc.get('schema_version')) is not int or doc['schema_version'] != 1:
        raise ValueError('Expected schema_version 1')
    rows = doc.get('assets')
    if not isinstance(rows, list) or len(rows) > 10000 or (baseline and not rows):
        raise ValueError('Expected assets list, nonempty for baseline, at most 10000')
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Asset must be an object')
        key = row.get('asset_id')
        if not isinstance(key, str) or not key.strip() or len(key) > 500 or key in result:
            raise ValueError('Missing, invalid or duplicate asset_id')
        if baseline and any(field not in row for field in FIELDS):
            raise ValueError('Baseline must explicitly include every metadata field')
        if baseline:
            for field in ('source', 'provenance_url', 'attribution'):
                if row[field] is not None and not isinstance(row[field], str):
                    raise ValueError('Baseline text metadata must be string or null')
            if row['rights'] is not None and not isinstance(row['rights'], dict):
                raise ValueError('Baseline rights must be object or null')
        result[key] = row
    return result


def pointer(key):
    return str(key).replace('~', '~0').replace('/', '~1')


def differences(expected, actual, path):
    # Type checks intentionally distinguish false from 0 and null from absence.
    if type(expected) is not type(actual):
        return [path]
    if isinstance(expected, dict):
        found = []
        for key in sorted(expected.keys() | actual.keys()):
            child = path + '/' + pointer(key)
            if key not in expected or key not in actual:
                found.append(child)
            else:
                found.extend(differences(expected[key], actual[key], child))
        return found
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [path]
        return [item for i, (left, right) in enumerate(zip(expected, actual))
                for item in differences(left, right, path + '/' + str(i))]
    return [] if expected == actual else [path]


def compare(baseline, exported):
    before, after = index(baseline, True), index(exported)
    issues, unknown = [], []
    for key in sorted(before):
        row = before[key]
        empty = [field for field in FIELDS if row[field] in (None, '', {})]
        if empty:
            unknown.append({'asset_id': key, 'fields': empty})
        if key not in after:
            issues.append({'asset_id': key, 'kind': 'missing_asset'})
            continue
        for field in FIELDS:
            if field not in after[key]:
                issues.append({'asset_id': key, 'kind': 'missing_field', 'path': '/' + field})
            else:
                for path in differences(row[field], after[key][field], '/' + field):
                    issues.append({'asset_id': key, 'kind': 'changed_field', 'path': path})
    for key in sorted(after.keys() - before.keys()):
        issues.append({'asset_id': key, 'kind': 'unexpected_asset'})
    return {'schema_version': 1, 'metadata_preserved': not issues,
            'baseline_assets': len(before), 'export_assets': len(after),
            'issues': issues, 'baseline_unknowns': unknown,
            'rights_clearance': 'not_evaluated'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline')
    parser.add_argument('export')
    args = parser.parse_args(argv)
    try:
        report = compare(load(args.baseline), load(args.export))
    except (OSError, ValueError, RecursionError):
        # Do not echo supplied files, metadata, credentials or parser excerpts.
        print(json.dumps({'error': 'Invalid or unreadable input; see README schema and limits.'}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report['metadata_preserved'] else 1


if __name__ == '__main__':
    sys.exit(main())
