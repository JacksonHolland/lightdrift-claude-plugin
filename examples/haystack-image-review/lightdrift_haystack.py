"""Backend-only candidate review component; no downloads or automatic approval."""
import copy
import json
import os
import urllib.error
import urllib.request
from haystack import component

ENDPOINT = 'https://api.lightdrift.ai/v1/search'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def search(body):
    key = os.environ.get('LIGHTDRIFT_API_KEY', '').strip()
    if not key:
        raise ValueError('Set LIGHTDRIFT_API_KEY on the backend')
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), method='POST',
                                 headers={'X-API-Key': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Lightdrift HTTP {exc.code}; no retry. Check usage and limits.') from None
    except (urllib.error.URLError, OSError, ValueError):
        raise RuntimeError('Transport/JSON failure; charge outcome unknown. Check usage before retry.') from None


@component
class LightdriftImageReview:
    """One bounded search or explicit synthetic fixture -> human review queue.

    live=False never calls the network. Fixture records are caller-supplied test data.
    """
    def __init__(self, live: bool = False):
        if type(live) is not bool:
            raise ValueError('live must be a boolean')
        self.live = live

    @component.output_types(review_queue=list[dict], query_id=str, response=dict, status=str)
    def run(self, visual_brief: str, candidate_count: int = 5, fixture: dict | None = None):
        if not isinstance(visual_brief, str) or not 1 <= len(visual_brief.strip()) <= 1000:
            raise ValueError('visual_brief must contain 1–1000 characters')
        if type(candidate_count) is not int or not 1 <= candidate_count <= 20:
            raise ValueError('candidate_count must be an integer from 1 to 20')
        if self.live and fixture is not None:
            raise ValueError('Do not mix live execution and fixtures')
        if not self.live and fixture is None:
            raise ValueError('Offline default requires an explicit synthetic fixture')
        body = {'query': visual_brief.strip(), 'k': candidate_count,
                'filters': {'commercial': True}, 'experiment': 'haystack_image_review_v1'}
        data = search(body) if self.live else copy.deepcopy(fixture)
        if not isinstance(data, dict) or not isinstance(data.get('query_id'), str) or not data['query_id'] or not isinstance(data.get('results'), list):
            raise ValueError('Malformed search response; no review queue emitted')
        queue = []
        # Validate every returned result; never silently approve malformed entries.
        for asset in data['results']:
            if not isinstance(asset, dict) or not isinstance(asset.get('asset_id'), str) or not asset['asset_id']:
                raise ValueError('Malformed asset ID; no review queue emitted')
        for asset in data['results'][:candidate_count]:
            rights = copy.deepcopy(asset.get('rights'))
            warnings = []
            if not isinstance(rights, dict):
                warnings.append('missing_or_invalid_rights')
            elif not rights.get('provenance_url'):
                warnings.append('missing_provenance')
            queue.append({'query_id': data['query_id'], 'asset_id': asset['asset_id'],
                          'source': copy.deepcopy(asset.get('source')),
                          'provenance_url': rights.get('provenance_url') if isinstance(rights, dict) else None,
                          'rights': rights, 'asset': copy.deepcopy(asset),
                          'review_state': 'pending_human_review', 'warnings': warnings,
                          'synthetic': not self.live})
        return {'review_queue': queue, 'query_id': data['query_id'], 'response': copy.deepcopy(data),
                'status': 'degraded' if data.get('degraded') else ('empty' if not queue else 'pending_review')}
