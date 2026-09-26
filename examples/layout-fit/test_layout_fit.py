import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from layout_fit import audit, geometry, render

class Tests(unittest.TestCase):
    def test_square_into_wide(self):
        g=geometry(1000,1000,1600,900)
        self.assertEqual(g['retained_area_percent'],56.25)
        self.assertEqual(g['cropped_area_percent'],43.75)
        self.assertTrue(g['upscale_required'])
        self.assertEqual(g['center_crop_source_pixels']['y'],218.75)
    def test_ratio_and_dpr(self):
        self.assertFalse(geometry(1920,1080,960,540,2)['upscale_required'])
        self.assertTrue(geometry(1920,1080,960,540,3)['upscale_required'])
        self.assertEqual(geometry(1920,1080,960,540,3)['retained_area_percent'],100)
    def test_portrait(self):
        self.assertEqual(geometry(1200,1800,1200,600)['center_crop_source_pixels'],{'x':0,'y':600,'width':1200,'height':600})
    def test_unknown_dimensions(self):
        for v in (None,0,-1,True,'1024',float('nan'),float('inf')):
            self.assertEqual(geometry(v,100,100,100)['status'],'unknown_dimensions')
    def test_invalid_target(self):
        for v in (0,-1,True,float('nan'),float('inf')):
            with self.assertRaises(ValueError): audit({'results':[]},v,100)
    def test_preservation(self):
        r={'query_id':'synthetic','degraded':'example','future':{'x':1},'results':[{'asset_id':'fixture:1','rights':{'commercial':None,'future':'preserved'}}]}
        before=copy.deepcopy(r); out=audit(r,100,100)
        self.assertEqual(r,before)
        self.assertEqual(out['original_response'],before)
        self.assertEqual(out['candidates'][0]['asset'],r['results'][0])
        self.assertIn('needs_',out['candidates'][0]['review_status'])
    def test_html_escape(self):
        v='<script>alert(1)</script>'
        out=render(audit({'results':[{'asset_id':v,'title':v,'rights':{'attribution':v}}]},100,100))
        self.assertNotIn('<script>',out); self.assertIn('&lt;script&gt;',out)
        self.assertNotIn('<img',out)
    def test_invalid_shape(self):
        for r in ([],{}, {'results':None},{'results':[None]}):
            with self.assertRaises(ValueError): audit(r,100,100)
    def test_order_and_empty(self):
        self.assertEqual(audit({'results':[]},100,100)['candidates'],[])
        rows=audit({'results':[{'asset_id':'a'},{'asset_id':'a'}]},100,100)['candidates']
        self.assertEqual([r['input_index'] for r in rows],[0,1])
    def test_cli_overwrite_guard(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('PAPERCLIP_RUN_SCRATCH_DIR')) as d:
            root=Path(d); source=root/'input.json'; source.write_text('{"results":[]}')
            cmd=[sys.executable,str(Path(__file__).with_name('layout_fit.py')),str(source),'--width','800','--height','600','--output',str(root/'out')]
            r=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads((root/'out/report.json').read_text())['candidates'],[])
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)

if __name__=='__main__': unittest.main()
