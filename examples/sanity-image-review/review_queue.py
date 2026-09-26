#!/usr/bin/env python3
"""Server-side, bounded Lightdrift search to a Sanity draft review queue."""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = 'https://api.lightdrift.ai/v1/search'
API_VERSION = '2025-02-19'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def post(url, body, headers):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {'Content-Type': 'application/json', **headers}, method='POST')
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('Response exceeds 1 MB limit')
    return json.loads(raw)

def draft_id(value):
    if not re.fullmatch(r'drafts\.[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('Use drafts.<simple-document-id>, at most 100 ID characters')
    return value

def make_document(response, content_draft, query, fixture=False):
    draft_id(content_draft)
    if not isinstance(response, dict) or not isinstance(response.get('query_id'), str) or not response['query_id']:
        raise ValueError('Missing query_id')
    results = response.get('results')
    if not isinstance(results, list) or len(results) > 5:
        raise ValueError('Expected zero to five candidates')
    candidates = []
    for i, result in enumerate(results):
        if not isinstance(result, dict) or not isinstance(result.get('asset_id'), str) or not result['asset_id']:
            raise ValueError('Candidate missing asset_id')
        rights = result.get('rights')
        rights = rights if isinstance(rights, dict) else {}
        candidates.append({
            '_key': f'candidate-{i}', '_type': 'imageReviewCandidate',
            'assetId': result['asset_id'], 'source': str(result.get('source') or ''),
            'provenance': str(rights.get('provenance_url') or ''),
            'attribution': str(rights.get('attribution') or ''),
            'rightsJson': json.dumps(result.get('rights'), ensure_ascii=False, sort_keys=True),
            'candidateJson': json.dumps(result, ensure_ascii=False, sort_keys=True),
            'decision': 'pending', 'reviewer': '', 'reviewNotes': '',
        })
    # Full response participates in identity; exact replay cannot overwrite editor decisions.
    raw = json.dumps(response, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256((content_draft + '\n' + raw + '\n' + query).encode()).hexdigest()[:32]
    return {'_id': 'drafts.imageReview-' + digest, '_type': 'imageReview',
            'title': ('FIXTURE: ' if fixture else '') + query, 'contentDraftId': content_draft,
            'queryId': response['query_id'], 'isFixture': fixture, 'query': query,
            'responseJson': raw, 'candidates': candidates}

def mutation(document):
    draft_id(document['_id'])
    if document['_type'] != 'imageReview':
        raise ValueError('Only review queue drafts may be written')
    return {'mutations': [{'createIfNotExists': document}]}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--content-draft', required=True)
    parser.add_argument('--query', default='Coastal lighthouse with space for a headline')
    parser.add_argument('--live-search', action='store_true', help='One paid search, no retries')
    parser.add_argument('--write-draft', action='store_true', help='One Sanity mutation; never publishes')
    parser.add_argument('--allow-fixture-write', action='store_true', help='Permit clearly labelled fixture in your test dataset')
    args = parser.parse_args(argv)
    try:
        draft_id(args.content_draft)
        if not 1 <= len(args.query.strip()) <= 1000:
            raise ValueError('Query must have 1–1000 characters')
        # Validate every requested credential/destination before any paid request.
        key = os.environ.get('LIGHTDRIFT_API_KEY', '')
        if args.live_search and not key:
            raise ValueError('Set LIGHTDRIFT_API_KEY on the server')
        if args.write_draft:
            if not args.live_search and not args.allow_fixture_write:
                raise ValueError('Fixture write requires --allow-fixture-write')
            project = os.environ.get('SANITY_PROJECT_ID', '')
            dataset = os.environ.get('SANITY_DATASET', '')
            token = os.environ.get('SANITY_WRITE_TOKEN', '')
            if not re.fullmatch(r'[a-z0-9]{1,32}', project) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', dataset) or not token:
                raise ValueError('Set valid SANITY_PROJECT_ID, SANITY_DATASET and SANITY_WRITE_TOKEN')
        if args.live_search:
            response = post(ENDPOINT, {'query': args.query.strip(), 'k': 5,
                            'filters': {'commercial': True, 'derivatives': True},
                            'experiment': 'sanity-image-review-v1'}, {'X-API-Key': key})
        else:
            response = json.loads(Path(__file__).with_name('fixture.json').read_text())
        doc = make_document(response, args.content_draft, args.query.strip(), not args.live_search)
        # Flush recovery evidence before the independent CMS write; protect this output locally.
        print(json.dumps({'draft': doc, 'mutation': mutation(doc)}, ensure_ascii=False), flush=True)
        if args.write_draft:
            result = post(f'https://{project}.api.sanity.io/v{API_VERSION}/data/mutate/{dataset}',
                          mutation(doc), {'Authorization': 'Bearer ' + token})
            if not isinstance(result, dict) or not result.get('transactionId'):
                raise ValueError('Mutation outcome unconfirmed; inspect dataset before repeating')
            print(json.dumps({'sanityTransactionId': result['transactionId'], 'draftId': doc['_id']}), file=sys.stderr)
        return 0
    except urllib.error.HTTPError as exc:
        print(f'HTTP {exc.code}; stopped without retry. Check usage/dataset before rerunning.', file=sys.stderr)
    except (ValueError, OSError, TimeoutError):
        print('Validation, transport or response failure; stopped without retry. Check arguments, credentials, usage and dataset privately. A live outcome may be unknown.', file=sys.stderr)
    return 1

if __name__ == '__main__':
    sys.exit(main())
