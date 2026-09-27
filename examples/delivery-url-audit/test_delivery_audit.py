import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from delivery_audit import audit, inspect_url, main

URL = 'https://media.example/asset/123?query_id=demo&size=large'
def item(**changes):
    return dict(asset_id='synthetic-123', returned_url=URL, exported_url=URL, **{}) | changes

class DeliveryAuditTests(unittest.TestCase):
    def test_unchanged(self):
        self.assertEqual(audit({'items':[item()]})['passed_items'], 1)
    def test_query_removed(self):
        self.assertIn('delivery_url_changed', audit({'items':[item(exported_url=URL.split('?')[0])]})['rows'][0]['findings'])
    def test_changed_query_order_needs_review(self):
        self.assertEqual(audit({'items':[item(exported_url='https://media.example/asset/123?size=large&query_id=demo')]})['review_items'], 1)
    def test_signed_url_detected(self):
        for key in ['X-Amz-Signature', 'X-Goog-Expires', '%73ignature', 'token', 'Expires']:
            self.assertIn('possible_signed_or_temporary_url', inspect_url('https://media.example/a?'+key+'=SYNTHETIC_SECRET'))
    def test_arbitrary_query_is_not_declared_signed(self):
        self.assertEqual(inspect_url(URL), [])
    def test_https_required(self):
        for u in ['http://media.example/a', '/a', '//media.example/a', 'data:image/png;test', 'javascript:alert(1)']:
            self.assertIn('https_absolute_required', inspect_url(u))
    def test_credentials(self):
        self.assertIn('embedded_credentials', inspect_url('https://name:secret@media.example/a'))
    def test_fragment(self):
        self.assertIn('fragment_present', inspect_url(URL+'#preview'))
    def test_malformed(self):
        for u in ['https://[broken/a', 'https://example.test:bad/a', 'https://example.test:99999/a', 'https://example.test/a\nb', 'https://example.test/a%zz', 'https://example.test\\evil/a']:
            self.assertIn('malformed_url', inspect_url(u))
    def test_missing(self):
        for u in [None, '', 1, [], {}]:
            self.assertEqual(inspect_url(u), ['missing_url'])
    def test_no_raw_input_in_report(self):
        text = json.dumps(audit({'items':[item(asset_id='SYNTHETIC_SECRET', returned_url='https://user:SYNTHETIC_SECRET@example.test/SYNTHETIC_SECRET?token=SYNTHETIC_SECRET')]}))
        self.assertNotIn('SYNTHETIC_SECRET', text)
        self.assertNotIn('example.test', text)
    def test_repeated_asset(self):
        r = audit({'items':[item(),item()]})
        self.assertIn('repeated_asset_id', r['rows'][1]['findings'])
    def test_invalid_item_does_not_drop_valid_rows(self):
        r = audit({'items':[None, item(), item(asset_id=None)]})
        self.assertEqual((r['items_checked'],r['passed_items'],r['review_items']),(3,1,2))
    def test_document_shape(self):
        for doc in [[], {}, {'items':[]}, {'items':{}}, {'items':[item()],'extra':1}, {'items':[None]*10001}]:
            with self.assertRaises(ValueError): audit(doc)
    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'manifest.json'
            for data,code in [(json.dumps({'items':[item()]}),0),(json.dumps({'items':[item(exported_url='/a')]}),1),('{"secret":"SYNTHETIC_SECRET"',2)]:
                p.write_text(data)
                out=io.StringIO()
                with contextlib.redirect_stdout(out): self.assertEqual(main([str(p)]),code)
                self.assertNotIn('SYNTHETIC_SECRET',out.getvalue())
                json.loads(out.getvalue())
    def test_cli_missing_file_redacts_path(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out): self.assertEqual(main(['/SYNTHETIC_SECRET/absent.json']),2)
        self.assertNotIn('SYNTHETIC_SECRET',out.getvalue())
    def test_extra_fields(self):
        self.assertIn('unexpected_or_missing_fields', audit({'items':[item(extra=True)]})['rows'][0]['findings'])

if __name__ == '__main__': unittest.main()
