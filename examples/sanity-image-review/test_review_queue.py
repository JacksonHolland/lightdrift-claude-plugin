import contextlib
import copy
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error
import review_queue as q

FIXTURE = json.loads(Path(__file__).with_name('fixture.json').read_text())
class QueueTests(unittest.TestCase):
    def run_cli(self, args, response=FIXTURE, env=None):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env or {}, clear=True), patch.object(q, 'post', return_value=response) as post, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = q.main(['--content-draft', 'drafts.article-1', *args])
        return result, out.getvalue(), err.getvalue(), post

    def test_default_has_no_network(self):
        rc, out, _, post = self.run_cli([])
        self.assertEqual(rc, 0); post.assert_not_called()
        self.assertTrue(json.loads(out)['draft']['isFixture'])

    def test_full_metadata_and_envelope_preserved(self):
        d = q.make_document(FIXTURE, 'drafts.article-1', 'query')
        self.assertEqual(json.loads(d['responseJson']), FIXTURE)
        c = d['candidates'][0]
        self.assertEqual(json.loads(c['rightsJson']), FIXTURE['results'][0]['rights'])
        self.assertEqual(json.loads(c['candidateJson']), FIXTURE['results'][0])
        self.assertEqual(c['decision'], 'pending')

    def test_missing_rights_remains_pending(self):
        f = copy.deepcopy(FIXTURE); del f['results'][0]['rights']
        c = q.make_document(f, 'drafts.article-1', 'query')['candidates'][0]
        self.assertEqual(c['rightsJson'], 'null'); self.assertEqual(c['decision'], 'pending')

    def test_empty_results_are_valid(self):
        self.assertEqual(q.make_document({'query_id':'empty', 'results':[]}, 'drafts.article-1','q')['candidates'], [])

    def test_malformed_and_over_limit_rejected(self):
        for f in [{}, {'query_id':'x','results':[{}]}, {'query_id':'x','results':FIXTURE['results']*6}]:
            with self.assertRaises(ValueError): q.make_document(f,'drafts.article-1','q')

    def test_draft_only_and_replay_identity(self):
        d = q.make_document(FIXTURE,'drafts.article-1','q')
        self.assertEqual(q.make_document(FIXTURE,'drafts.article-1','q'), d)
        self.assertEqual(list(q.mutation(d)['mutations'][0]), ['createIfNotExists'])
        for bad in ['article-1','drafts../bad','drafts.x?token=bad']:
            with self.assertRaises(ValueError): q.draft_id(bad)
        with self.assertRaises(ValueError): q.mutation({**d,'_id':'published'})

    def test_missing_configuration_prevents_paid_search(self):
        for args in [['--live-search'], ['--live-search','--write-draft'], ['--write-draft']]:
            rc, _, _, post = self.run_cli(args)
            self.assertEqual(rc,1);post.assert_not_called()

    def test_live_search_exactly_once(self):
        rc, _, _, post = self.run_cli(['--live-search'], env={'LIGHTDRIFT_API_KEY':'test-only'})
        self.assertEqual(rc,0); self.assertEqual(post.call_count,1)
        self.assertEqual(post.call_args.args[1]['k'],5)

    def test_fixture_write_requires_opt_in_and_is_draft(self):
        env={'SANITY_PROJECT_ID':'project1','SANITY_DATASET':'test','SANITY_WRITE_TOKEN':'test-only'}
        rc,out,err,post=self.run_cli(['--write-draft','--allow-fixture-write'], {'transactionId':'test-transaction'},env)
        self.assertEqual(rc,0); self.assertEqual(post.call_count,1)
        self.assertTrue(post.call_args.args[1]['mutations'][0]['createIfNotExists']['_id'].startswith('drafts.'))
        self.assertNotIn('test-only',out+err)

    def test_error_has_no_retry_or_secret(self):
        for error in [urllib.error.HTTPError('url',429,'secret',None,None),TimeoutError('secret'),ValueError('secret')]:
            out,err=io.StringIO(),io.StringIO()
            with patch.dict(os.environ,{'LIGHTDRIFT_API_KEY':'secret'},clear=True), patch.object(q,'post',side_effect=error) as post, contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                self.assertEqual(q.main(['--content-draft','drafts.article-1','--live-search']),1)
            self.assertEqual(post.call_count,1);self.assertNotIn('secret',out.getvalue()+err.getvalue())

    def test_redirects_refused(self):
        self.assertIsNone(q.NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid'))

if __name__ == '__main__': unittest.main()
