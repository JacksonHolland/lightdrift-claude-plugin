# py: >=3.10
"""Offline Windmill layout audit; no dependencies, credentials, or network calls.

Geometry/audit functions vendored from ../layout-fit/layout_fit.py at
fc056d6c7317bb1ad8c6b557e7ad44c0acd64821. Keep parity tests when updating.
"""
import json
import math


def positive(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def geometry(w, h, tw, th, dpr=1):
    if not all(positive(v) for v in (tw, th, dpr)):
        raise ValueError('target dimensions and DPR must be positive finite numbers')
    if not all(positive(v) for v in (w, h)):
        return {'status': 'unknown_dimensions'}
    scale = max(tw*dpr/w, th*dpr/h)
    cw, ch = tw*dpr/scale, th*dpr/scale
    retained = cw*ch/(w*h)
    return {'status':'geometry_only', 'scale_to_target_pixels':round(scale,6),
            'upscale_required':scale > 1, 'retained_area_percent':round(100*retained,3),
            'cropped_area_percent':round(100*(1-retained),3),
            'center_crop_source_pixels':dict(zip(('x','y','width','height'),
                (round(v,3) for v in ((w-cw)/2,(h-ch)/2,cw,ch))))}


def audit(response, width, height, dpr=1):
    if not isinstance(response,dict) or not isinstance(response.get('results'),list):
        raise ValueError('input must be a search response object with a results array')
    if not all(positive(v) for v in (width,height,dpr)):
        raise ValueError('target dimensions and DPR must be positive finite numbers')
    rows=[]
    for index,asset in enumerate(response['results']):
        if not isinstance(asset,dict):
            raise ValueError(f'results[{index}] must be an object')
        rows.append({'input_index':index,'asset':asset,
                     'layout':geometry(asset.get('width'),asset.get('height'),width,height,dpr),
                     'review_status':'needs_visual_and_rights_review'})
    return {'schema_version':1,
            'target':{'css_width':width,'css_height':height,'device_pixel_ratio':dpr},
            'original_response':response,'candidates':rows,
            'notice':'Geometry is not a quality, focal-point, or rights approval. No network requests were made.'}



def main(response: dict, width: float, height: float, dpr: float = 1.0) -> dict:
    """Audit a saved response for a CSS pixel slot and device pixel ratio."""
    try:
        report = audit(response, width, height, dpr)
        # Match Windmill's JSON return boundary and detach preserved metadata.
        return json.loads(json.dumps(report, ensure_ascii=False, allow_nan=False))
    except (OverflowError, ZeroDivisionError, TypeError) as exc:
        raise ValueError("input must contain JSON data and representable dimensions") from exc
