"""Offline delivery URL export audit. Python 3.10+, standard library only."""
import argparse
import json
import re
import sys
from urllib.parse import parse_qsl, urlsplit

SIGNED_KEYS = frozenset({'signature', 'sig', 'token', 'expires', 'x-amz-signature',
    'x-amz-credential', 'x-amz-expires', 'x-goog-signature', 'x-goog-expires',
    'policy', 'key-pair-id'})


def inspect_url(value):
    """Return only fixed diagnostic codes; never include URL contents."""
    if not isinstance(value, str) or not value:
        return ['missing_url']
    if re.search(r'[\x00-\x20\x7f\\]', value) or re.search(r'%(?![0-9a-fA-F]{2})', value):
        return ['malformed_url']
    try:
        parts = urlsplit(value)
        port = parts.port
        if parts.scheme.lower() != 'https' or not parts.hostname:
            return ['https_absolute_required']
        # This is a syntax check, not DNS resolution or a fetching safety check.
        if '%' in parts.hostname or any(c in parts.hostname for c in '<>"{}|^`'):
            return ['malformed_url']
        flags = []
        if parts.username is not None or parts.password is not None:
            flags.append('embedded_credentials')
        if parts.fragment:
            flags.append('fragment_present')
        keys = {k.lower() for k, _ in parse_qsl(parts.query, keep_blank_values=True)}
        if keys & SIGNED_KEYS:
            flags.append('possible_signed_or_temporary_url')
        return flags
    except ValueError:
        return ['malformed_url']


def audit(document):
    if not isinstance(document, dict) or set(document) != {'items'} or not isinstance(document['items'], list):
        raise ValueError('expected an object with one items array')
    rows = document['items']
    if not rows:
        raise ValueError('items must not be empty')
    if len(rows) > 10000:
        raise ValueError('at most 10000 items per batch')
    reports = []
    seen = set()
    for i, row in enumerate(rows):
        flags = []
        if not isinstance(row, dict):
            reports.append({'row': i, 'status': 'review', 'findings': ['invalid_item']})
            continue
        if set(row) != {'asset_id', 'returned_url', 'exported_url'}:
            flags.append('unexpected_or_missing_fields')
        asset = row.get('asset_id')
        if not isinstance(asset, str) or not asset.strip():
            flags.append('missing_asset_id')
        elif asset in seen:
            flags.append('repeated_asset_id')
        else:
            seen.add(asset)
        for field in ('returned_url', 'exported_url'):
            flags.extend(field + ':' + code for code in inspect_url(row.get(field)))
        before, after = row.get('returned_url'), row.get('exported_url')
        if isinstance(before, str) and isinstance(after, str) and before != after:
            flags.append('delivery_url_changed')
        reports.append({'row': i, 'status': 'review' if flags else 'pass', 'findings': flags})
    review = sum(r['status'] == 'review' for r in reports)
    return {'schema_version': 1, 'items_checked': len(rows), 'review_items': review,
            'passed_items': len(rows) - review, 'network_requests': 0, 'rows': reports}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', help='local JSON manifest; no URLs fetched')
    args = parser.parse_args(argv)
    try:
        with open(args.manifest, encoding='utf-8') as source:
            data = json.load(source)
        report = audit(data)
    except (OSError, ValueError, UnicodeError, RecursionError):
        # Do not print exception text: it could expose a URL, value or local path.
        print(json.dumps({'error': 'invalid_manifest', 'network_requests': 0}))
        return 2
    print(json.dumps(report, indent=2))
    return 1 if report['review_items'] else 0


if __name__ == '__main__':
    sys.exit(main())
