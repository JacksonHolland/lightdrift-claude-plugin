"""Offline response inspection. No network, credentials, dependencies, or writes."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import sys


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('non-finite JSON number: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def index(envelope):
    if not isinstance(envelope, dict) or not isinstance(envelope.get('results'), list):
        raise ValueError('expected an object containing a results array')
    found = {}
    for rank, row in enumerate(envelope['results'], 1):
        if not isinstance(row, dict):
            raise ValueError('each result must be an object')
        key = row.get('asset_id')
        if not isinstance(key, str) or not key.strip():
            raise ValueError('each result needs a nonempty string asset_id')
        if key in found:
            raise ValueError('duplicate asset_id: ' + key)
        found[key] = (rank, row)
    return found


def changes(before, after, exclude=()):
    out = {}
    for key in sorted((before.keys() | after.keys()) - set(exclude)):
        if key not in before or key not in after or before[key] != after[key]:
            out[key] = {'before_present': key in before, 'after_present': key in after,
                        'before': before.get(key), 'after': after.get(key)}
    return out


def compare(before, after):
    old, new = index(before), index(after)
    common = old.keys() & new.keys()
    union = old.keys() | new.keys()
    return {
        'schema_version': 1,
        'counts': {'before': len(old), 'after': len(new), 'shared': len(common)},
        'overlap_jaccard': len(common) / len(union) if union else None,
        'entered': [key for key in new if key not in old],
        'exited': [key for key in old if key not in new],
        'shared': [{'asset_id': key, 'rank_before': old[key][0], 'rank_after': new[key][0],
                    'rank_change': old[key][0] - new[key][0],
                    'field_changes': changes(old[key][1], new[key][1], ('asset_id',))}
                   for key in new if key in old],
        'envelope_changes': changes(before, after, ('results',)),
        'interpretation': 'Positive rank_change means moved toward the first position. '
                          'Rank and overlap are descriptive, not relevance or latency benchmarks.'
    }


def markdown(report):
    """Render input-derived values as inert JSON in HTML preformatted blocks."""
    def block(value):
        return '<pre>' + html.escape(json.dumps(value, indent=2, ensure_ascii=True,
                                               allow_nan=False)) + '</pre>'
    sections = [
        '# Saved search response review',
        'Offline comparison only. Rank changes and overlap do not establish relevance gains. '
        'Review original snapshots and source rights before using an image.',
        '## Input fingerprints', block(report.get('inputs', {})),
        '## Membership', block({key: report[key] for key in
                                ('counts', 'overlap_jaccard', 'entered', 'exited')}),
        '## Shared assets: rank and field changes',
    ]
    sections.extend(block(row) for row in report['shared'])
    if not report['shared']:
        sections.append('No shared assets.')
    sections.extend(['## Envelope changes', block(report['envelope_changes']),
                     'Missing values and explicit nulls remain distinct through the presence flags. '
                     'Unchanged metadata remains in the original snapshots. '
                     'Reports contain input metadata; review before sharing.'])
    return '\n\n'.join(sections) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    args = parser.parse_args()
    try:
        raw = [p.read_bytes() for p in (args.before, args.after)]
        report = compare(*(strict_json(r) for r in raw))
        report['inputs'] = {name: {'sha256': hashlib.sha256(r).hexdigest()}
                            for name, r in zip(('before', 'after'), raw)}
        print(markdown(report) if args.format == 'markdown' else
              json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))
    except (ValueError, OSError) as exc:
        print('search-diff: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
