import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from search_plan import build_plan, load, request, money, unique_object

ROOT = Path(__file__).parent

def base():
    return {'requests': [{'query': 'solar panels'}], 'budget_usd': '0.005', 'max_requests': 1, 'attempts_per_request': 1}

class PlanTests(unittest.TestCase):
    def test_boundary(self):
        r = build_plan(base())
        self.assertEqual(r['status'], 'within_plan_limits')
        self.assertEqual(r['valid_subset_estimate_usd'], '0.005000')
    def test_duplicates(self):
        r = build_plan(load(ROOT/'fixtures/duplicates.json'))
        self.assertEqual(r['valid_unique_count'], 1)
        self.assertEqual(r['duplicates'], [{'index': 1, 'duplicate_of': 0}])
    def test_filters_changed(self):
        r = build_plan(load(ROOT/'fixtures/changed-filters.json'))
        self.assertEqual(r['valid_unique_count'], 3)
    def test_invalid_fixture(self):
        r = build_plan(load(ROOT/'fixtures/invalid-queries.json'))
        self.assertEqual(len(r['invalid']), 4)
        self.assertEqual(r['requests'], [])
    def test_budget_fixture(self):
        r = build_plan(load(ROOT/'fixtures/budget-overflow.json'))
        self.assertIn('budget_exceeded', r['block_reasons'])
        self.assertEqual(r['valid_subset_request_ceiling'], 4)
        self.assertEqual(r['requests'], [])
    def test_retries_cap(self):
        p = base(); p['attempts_per_request'] = 2; p['budget_usd'] = '1'
        self.assertEqual(build_plan(p)['block_reasons'], ['request_cap_exceeded'])
    def test_retry_price(self):
        p = base(); p.update(attempts_per_request=3, max_requests=3, budget_usd='0.015')
        self.assertEqual(build_plan(p)['valid_subset_estimate_usd'], '0.015000')
    def test_invalid_does_not_partially_execute(self):
        p = base(); p['requests'].append({'query': ''})
        self.assertEqual(build_plan(p)['executable_request_count'], 0)
    def test_exact_text(self):
        p = base(); p.update(budget_usd='1', max_requests=10)
        p['requests'] = [{'query': x} for x in ['cat', 'Cat', ' cat', 'cat ']]
        self.assertEqual(build_plan(p)['valid_unique_count'], 4)
    def test_null_omission_order(self):
        p = base(); p.update(budget_usd='1', max_requests=10)
        p['requests'] = [{'query': 'cat', 'filters': f} for f in [{}, {'commercial': None}, {'source': ['a','b']}, {'source': ['b','a']}]]
        self.assertEqual(build_plan(p)['valid_unique_count'], 4)
    def test_changed_k(self):
        p = base(); p.update(budget_usd='1', max_requests=10)
        p['requests'] += [{'query': 'solar panels', 'k': 5}]
        self.assertEqual(build_plan(p)['valid_unique_count'], 2)
    def test_bad_types(self):
        for row in [{'query':'x','k':True}, {'query':'x','filters':{'commercial':1}}, {'query':'x','filters':{'nsfw_max':float('nan')}}, {'query':'x','filters':{'source':[]}}, {'query':'x','filters':{'unknown':True}}, {'query':'x','image_url':'x'}]:
            with self.subTest(row=row), self.assertRaises(ValueError): request(row)
    def test_filter_bounds(self):
        for f in [{'min_width':-1}, {'year_min':2026,'year_max':2020}, {'orientation':'sideways'}, {'nsfw_max':1.1}]:
            with self.subTest(f=f), self.assertRaises(ValueError): request({'query':'x','filters':f})
    def test_query_bounds(self):
        self.assertEqual(len(request({'query':'x'*1000})['query']),1000)
        with self.assertRaises(ValueError): request({'query':'x'*1001})
    def test_decimal(self):
        self.assertEqual(money('0.000001'), 1)
        for v in ['NaN','1e3','-1','0.0000001',0.005,True]:
            with self.subTest(v=v), self.assertRaises(ValueError): money(v)
    def test_no_mutation(self):
        p=base(); before=copy.deepcopy(p); build_plan(p); self.assertEqual(p,before)
    def test_duplicate_keys(self):
        with self.assertRaises(ValueError): unique_object([('query','a'),('query','b')])
    def test_top_level_bounds(self):
        for key,value in [('attempts_per_request',True),('max_requests',-1),('requests',[]),('attempts_per_request',11)]:
            p=base(); p[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): build_plan(p)
    def test_cli_codes(self):
        for file,code in [('duplicates.json',0),('budget-overflow.json',1),('malformed.json',2)]:
            r=subprocess.run([sys.executable,str(ROOT/'search_plan.py'),str(ROOT/'fixtures'/file)],capture_output=True,text=True)
            self.assertEqual(r.returncode,code,r.stderr)
            self.assertIn('status',json.loads(r.stdout))

if __name__ == '__main__': unittest.main()

class ContainerOrientationRegression(unittest.TestCase):
    def test_container_orientation_is_rejected(self):
        from search_plan import request
        for value in ([], {}):
            with self.assertRaises(ValueError):
                request({'query': 'test', 'filters': {'orientation': value}})
