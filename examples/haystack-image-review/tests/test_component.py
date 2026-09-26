import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
from haystack import Pipeline
from lightdrift_haystack import LightdriftImageReview, NoRedirect, search, ENDPOINT

FIXTURE = json.loads((Path(__file__).parents[1] / 'fixtures/candidates.json').read_text())

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.component = LightdriftImageReview()
        self.fixture = copy.deepcopy(FIXTURE)

    def run_fixture(self, fixture=None, count=5):
        return self.component.run('coast', count, fixture if fixture is not None else self.fixture)

    def test_real_pipeline_and_no_network(self):
        p = Pipeline()
        p.add_component('images', self.component)
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden')):
            r = p.run({'images': {'visual_brief': 'coast', 'fixture': self.fixture}})['images']
        self.assertEqual(r['query_id'], self.fixture['query_id'])
        self.assertEqual(r['response'], self.fixture)
        row = r['review_queue'][0]
        self.assertEqual(row['rights'], self.fixture['results'][0]['rights'])
        self.assertEqual(row['provenance_url'], row['rights']['provenance_url'])
        self.assertEqual(row['review_state'], 'pending_human_review')
        self.assertTrue(row['synthetic'])
        row['rights']['future_field']['preserve'] = False
        self.assertTrue(self.fixture['results'][0]['rights']['future_field']['preserve'])

    def test_empty(self):
        self.fixture['results'] = []
        self.assertEqual(self.run_fixture()['status'], 'empty')

    def test_degraded_preserved(self):
        self.fixture['degraded'] = 'fallback'
        r = self.run_fixture()
        self.assertEqual(r['status'], 'degraded')
        self.assertEqual(r['response']['degraded'], 'fallback')

    def test_missing_rights_not_approved(self):
        del self.fixture['results'][0]['rights']
        row = self.run_fixture()['review_queue'][0]
        self.assertIsNone(row['rights'])
        self.assertEqual(row['warnings'], ['missing_or_invalid_rights'])

    def test_missing_provenance(self):
        del self.fixture['results'][0]['rights']['provenance_url']
        self.assertEqual(self.run_fixture()['review_queue'][0]['warnings'], ['missing_provenance'])

    def test_bound_output_without_losing_envelope(self):
        self.fixture['results'] *= 3
        r = self.run_fixture(count=1)
        self.assertEqual(len(r['review_queue']), 1)
        self.assertEqual(len(r['response']['results']), 3)

    def test_invalid_inputs(self):
        for count in [0,21,True,1.5,'2']:
            with self.subTest(count=count), self.assertRaises(ValueError): self.run_fixture(count=count)
        for brief in ['', ' ', 'x'*1001, None]:
            with self.subTest(brief=str(brief)[:10]), self.assertRaises(ValueError): self.component.run(brief, fixture=self.fixture)

    def test_malformed_responses(self):
        for f in [{},dict(FIXTURE,query_id=None),dict(FIXTURE,results={}),dict(FIXTURE,results=[{}])]:
            with self.subTest(f=f), self.assertRaises(ValueError): self.run_fixture(f)

    def test_offline_default_and_no_ambiguous_mode(self):
        with patch('lightdrift_haystack.search') as s:
            with self.assertRaises(ValueError): self.component.run('coast')
            with self.assertRaises(ValueError): LightdriftImageReview(live=True).run('coast',fixture=self.fixture)
            s.assert_not_called()

    def test_live_payload_mock_only(self):
        with patch('lightdrift_haystack.search', return_value=self.fixture) as s:
            r=LightdriftImageReview(live=True).run(' coast ',2)
        self.assertEqual(s.call_args.args[0], {'query':'coast','k':2,'filters':{'commercial':True},'experiment':'haystack_image_review_v1'})
        self.assertFalse(r['review_queue'][0]['synthetic'])

    def test_http_transport_mock_only(self):
        opener=MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value=json.dumps(FIXTURE).encode()
        with patch.dict('os.environ',{'LIGHTDRIFT_API_KEY':'test-secret'}), patch('urllib.request.build_opener',return_value=opener):
            self.assertEqual(search({'query':'coast','k':2}),FIXTURE)
        req=opener.open.call_args.args[0]
        self.assertEqual(req.full_url, ENDPOINT)
        self.assertEqual(req.get_header('X-api-key'),'test-secret')
        self.assertEqual(opener.open.call_count,1)

    def test_errors_no_retry_no_secret(self):
        errors=[urllib.error.HTTPError(ENDPOINT,429,'test-secret',{},None),urllib.error.URLError('test-secret'),TimeoutError('test-secret'),ValueError('test-secret')]
        for error in errors:
            opener=MagicMock(); opener.open.side_effect=error
            with patch.dict('os.environ',{'LIGHTDRIFT_API_KEY':'test-secret'}), patch('urllib.request.build_opener',return_value=opener):
                with self.assertRaises(RuntimeError) as caught: search({})
            self.assertNotIn('test-secret',str(caught.exception))
            self.assertEqual(opener.open.call_count,1)

    def test_missing_key(self):
        with patch.dict('os.environ',{},clear=True), self.assertRaises(ValueError): search({})

    def test_redirect_denied(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid'))

if __name__ == '__main__': unittest.main()
