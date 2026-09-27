#!/usr/bin/env python3
"""Build and reconcile a local image-asset inventory from saved responses.

Reads saved Lightdrift search responses (for asset ids and search-declared
fields) and saved /v1/asset/{asset_id} responses (for canonical metadata), then
reports the merged inventory, unresolved asset ids, cross-response duplicates
and field conflicts. Standard library only; no network, no key, no credits.
"""
import argparse
import json
import sys
from pathlib import Path

SEARCH_FIELDS = ('title', 'source', 'width', 'height', 'format', 'file', 'thumb')
RIGHTS_FIELDS = ('license', 'license_verbatim', 'commercial', 'attribution_required',
                 'derivatives', 'share_alike', 'attribution', 'provenance_url', 'basis')
CATALOG_KEYS = ('query_id', 'results', 'timing_ms', 'pool_size', 'ranking')


def load_objects(path, errors):
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


def classify(obj):
    if not isinstance(obj, dict):
        return 'other'
    if isinstance(obj.get('results'), list) or 'query_id' in obj:
        return 'search'
    if 'asset_id' in obj:
        return 'asset'
    return 'other'


def _declared(asset):
    out = {}
    for field in SEARCH_FIELDS + ('rights',):
        if field in asset:
            out[field] = asset[field]
    return out


def build_inventory(objects):
    searches = []
    catalog = {}
    skipped = 0
    for source, index, obj in objects:
        kind = classify(obj)
        if kind == 'search':
            searches.append((source, index, obj))
        elif kind == 'asset':
            asset_id = obj.get('asset_id')
            if isinstance(asset_id, str) and asset_id:
                entry = catalog.setdefault(asset_id, {'declared': {}, 'sources': []})
                entry['declared'] = _declared(obj)
                entry['sources'].append(f'{source}[{index}]')
            else:
                skipped += 1
        else:
            skipped += 1

    appearances = {}
    for source, index, obj in searches:
        for asset in obj.get('results') or []:
            if not isinstance(asset, dict):
                continue
            asset_id = asset.get('asset_id')
            if not isinstance(asset_id, str) or not asset_id:
                continue
            slot = appearances.setdefault(asset_id, {'declared': {}, 'appearances': 0, 'sources': []})
            slot['appearances'] += 1
            slot['sources'].append(f'{source}[{index}]')
            for key, value in _declared(asset).items():
                slot['declared'].setdefault(key, value)

    unresolved = sorted(set(appearances) - set(catalog))
    duplicates = {aid: info['appearances'] for aid, info in appearances.items()
                  if info['appearances'] > 1}

    conflicts = {}
    for asset_id, info in appearances.items():
        asset = catalog.get(asset_id)
        if not asset:
            continue
        for key, search_value in info['declared'].items():
            catalog_value = asset['declared'].get(key)
            if catalog_value is None or search_value == catalog_value:
                continue
            if key == 'rights' and isinstance(search_value, dict) and isinstance(catalog_value, dict):
                for rkey in RIGHTS_FIELDS:
                    if rkey in search_value and rkey in catalog_value and search_value[rkey] != catalog_value[rkey]:
                        conflicts.setdefault(asset_id, {})[f'rights.{rkey}'] = {
                            'search': search_value[rkey], 'asset': catalog_value[rkey]}
            elif key != 'rights':
                conflicts.setdefault(asset_id, {})[key] = {
                    'search': search_value, 'asset': catalog_value}

    inventory = {}
    for asset_id in sorted(set(appearances) | set(catalog)):
        info = appearances.get(asset_id)
        asset = catalog.get(asset_id)
        inventory[asset_id] = {
            'in_search_responses': info['appearances'] if info else 0,
            'has_asset_response': asset is not None,
            'search_declared': info['declared'] if info else {},
            'asset_declared': asset['declared'] if asset else {},
            'sources': sorted(set((info['sources'] if info else []) + (asset['sources'] if asset else []))),
        }

    plan = [{'asset_id': aid, 'method': 'GET', 'url': f'https://api.lightdrift.ai/v1/asset/{aid}'}
            for aid in unresolved]

    return {
        'search_responses': len(searches),
        'asset_responses': len(catalog),
        'skipped_other_objects': skipped,
        'distinct_assets_seen': len(set(appearances) | set(catalog)),
        'assets_with_asset_response': len(catalog),
        'assets_missing_asset_response': len(unresolved),
        'duplicate_assets_across_responses': duplicates,
        'field_conflicts': conflicts,
        'unresolved_asset_ids': unresolved,
        'request_plan': plan,
        'inventory': inventory,
        'notice': ('Offline reconciliation of saved responses. A conflict is a textual '
                   'difference between declared values, not proof that either source is wrong; '
                   'resolve against the live /v1/asset response before publishing.'),
    }


def render_text(report):
    lines = [
        f"search responses: {report['search_responses']}",
        f"asset responses: {report['asset_responses']}",
        f"distinct assets seen: {report['distinct_assets_seen']}",
        f"missing asset responses: {report['assets_missing_asset_response']}",
        f"duplicate assets across responses: {len(report['duplicate_assets_across_responses'])}",
        f"assets with field conflicts: {len(report['field_conflicts'])}",
        f"notice: {report['notice']}",
    ]
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path,
                        help='saved search/asset response JSON files, or directories containing them')
    parser.add_argument('--format', choices=('json', 'text'), default='json')
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--plan-only', action='store_true',
                        help='emit only the unresolved /v1/asset request plan')
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
            print(f'asset-inventory: {message}', file=sys.stderr)
        return 2

    report = build_inventory(objects)
    if args.plan_only:
        payload = report['request_plan']
    else:
        payload = report
    if args.format == 'text' and not args.plan_only:
        text = render_text(report)
    else:
        text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    if args.output is not None:
        args.output.write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
