#!/usr/bin/env python3
"""Offline layout geometry audit for a saved Lightdrift search response."""
import argparse
import html
import json
import math
from pathlib import Path


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


def render(report):
    esc=lambda v:html.escape(str(v),quote=True)
    rows=[]
    for row in report['candidates']:
        asset,layout=row['asset'],row['layout']
        cells=[asset.get('asset_id','(missing)'),asset.get('title'),
               layout.get('retained_area_percent','unknown'),layout.get('upscale_required','unknown'),
               json.dumps(asset.get('rights'),ensure_ascii=False)]
        rows.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in cells)+'</tr>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>Image layout fit audit</title><style>body{font:16px system-ui;margin:2rem}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #aaa;padding:.6rem;text-align:left;overflow-wrap:anywhere}</style>'
            '<h1>Image layout fit audit</h1><p>'+esc(report['notice'])+'</p><p>Target: '+esc(report['target'])
            +'</p><table><thead><tr><th>Asset</th><th>Title</th><th>Area retained (%)</th>'
            '<th>Upscale required</th><th>Source-declared rights: review required</th></tr></thead><tbody>'
            +''.join(rows)+'</tbody></table></html>')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('response',type=Path)
    p.add_argument('--width',required=True,type=float,help='slot width in CSS pixels')
    p.add_argument('--height',required=True,type=float,help='slot height in CSS pixels')
    p.add_argument('--dpr',type=float,default=1,help='target device pixel ratio')
    p.add_argument('--output',required=True,type=Path,help='new directory; refuses overwrite')
    a=p.parse_args()
    try:
        report=audit(json.loads(a.response.read_text(encoding='utf-8')),a.width,a.height,a.dpr)
        output=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        page=render(report)
        a.output.mkdir(parents=True,exist_ok=False)
        (a.output/'report.json').write_text(output,encoding='utf-8')
        (a.output/'report.html').write_text(page,encoding='utf-8')
    except (OSError,ValueError) as exc:
        p.exit(2,f'layout-fit: {exc}\n')
    print(f'{len(report["candidates"])} candidates audited; saved to {a.output}')

if __name__=='__main__': main()
