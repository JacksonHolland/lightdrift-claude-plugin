import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from search_diff import compare, strict_json, markdown

class DiffTests(unittest.TestCase):
    def setUp(self):
        self.a = {'query_id':'fixture-before', 'results':[
            {'asset_id':'fixture:a','score':None,'rights':{'credit':'A'}},
            {'asset_id':'fixture:b','score':0.5}]}
        self.b = {'query_id':'fixture-after', 'results':[
            {'asset_id':'fixture:b','score':None},
            {'asset_id':'fixture:c','score':0.3}]}
    def test_entrants_and_exits(self):
        r=compare(self.a,self.b)
        self.assertEqual(r['entered'],['fixture:c']); self.assertEqual(r['exited'],['fixture:a'])
        self.assertEqual(r['shared'][0]['rank_change'],1)
        self.assertEqual(r['overlap_jaccard'],1/3)
    def test_null_score_and_provenance(self):
        r=compare(self.a,self.b)
        self.assertIsNone(r['shared'][0]['field_changes']['score']['after'])
        self.assertEqual(r['envelope_changes']['query_id']['after'],'fixture-after')
    def test_nested_metadata(self):
        b=copy.deepcopy(self.a); b['results'][0]['rights']['credit']='B'
        self.assertEqual(compare(self.a,b)['shared'][0]['field_changes']['rights']['before'],{'credit':'A'})
    def test_missing_distinct_from_null(self):
        b=copy.deepcopy(self.a); del b['results'][0]['score']
        c=compare(self.a,b)['shared'][0]['field_changes']['score']
        self.assertTrue(c['before_present']); self.assertFalse(c['after_present'])
    def test_duplicates_rejected(self):
        self.a['results'].append(self.a['results'][0])
        with self.assertRaisesRegex(ValueError,'duplicate asset_id'): compare(self.a,self.b)
    def test_invalid_envelopes(self):
        for bad in ([],{}, {'results':{}},{'results':[{}]}, {'results':[{'asset_id':1}]}, {'results':[None]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError): compare(bad,self.b)
    def test_empty(self):
        self.assertIsNone(compare({'results':[]},{'results':[]})['overlap_jaccard'])
    def test_same_and_no_mutation(self):
        snapshot=copy.deepcopy(self.a); r=compare(self.a,self.a)
        self.assertEqual(r['entered'],[]); self.assertEqual(r['envelope_changes'],{})
        self.assertEqual(self.a,snapshot)
    def test_strict_json(self):
        for raw in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
            with self.assertRaises(ValueError): strict_json(raw)
    def test_cli(self):
        root=Path(__file__).parent
        p=subprocess.run([sys.executable,str(root/'search_diff.py'),str(root/'fixtures/before.json'),str(root/'fixtures/after.json')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(len(json.loads(p.stdout)['inputs']['before']['sha256']),64)
    def test_cli_failure(self):
        p=subprocess.run([sys.executable,str(Path(__file__).parent/'search_diff.py'),'missing-file','missing-file'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2); self.assertEqual(p.stdout,'')

    def test_markdown_inert_input(self):
        self.b['results'][0]['rights'] = {'credit': '</pre><script>alert(1)</script>\n```\n![track](https://invalid.test/a)'}
        result = markdown(compare(self.a, self.b))
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertIn('\\n```\\n', result)

    def test_markdown_missing_and_null(self):
        del self.b['results'][0]['score']
        result = markdown(compare(self.a, self.b))
        self.assertIn('&quot;after_present&quot;: false', result)
        self.assertIn('&quot;after&quot;: null', result)

    def test_markdown_empty(self):
        result = markdown(compare({'results': []}, {'results': []}))
        self.assertIn('No shared assets.', result)
        self.assertIn('&quot;overlap_jaccard&quot;: null', result)

    def test_markdown_cli(self):
        root = Path(__file__).parent
        p = subprocess.run([sys.executable, str(root/'search_diff.py'),
                            str(root/'fixtures/before.json'), str(root/'fixtures/after.json'),
                            '--format', 'markdown'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('# Saved search response review', p.stdout)
        self.assertIn('&quot;sha256&quot;', p.stdout)

if __name__=='__main__': unittest.main()
