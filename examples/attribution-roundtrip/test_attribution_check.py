import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from attribution_check import compare, load, differences

BASE = {'schema_version': 1, 'assets': [{'asset_id': 'fixture-lighthouse',
        'source': 'synthetic', 'provenance_url': 'https://example.invalid/image',
        'attribution': 'Synthetic creator — not a real image',
        'rights': {'license': {'name': 'fixture only'}, 'commercial': False,
                   'review': {'required': True}, 'tags': ['one', 'two']}}]}


class PreservationTests(unittest.TestCase):
    def test_exact(self):
        report = compare(BASE, copy.deepcopy(BASE))
        self.assertTrue(report['metadata_preserved'])
        self.assertEqual(report['rights_clearance'], 'not_evaluated')

    def test_cms_extra_fields_allowed(self):
        other = copy.deepcopy(BASE); other['assets'][0]['cms_id'] = 'local-1'
        self.assertTrue(compare(BASE, other)['metadata_preserved'])

    def test_lost_nested_rights(self):
        other = copy.deepcopy(BASE); del other['assets'][0]['rights']['review']
        self.assertEqual(compare(BASE, other)['issues'][0]['path'], '/rights/review')

    def test_attribution_changed(self):
        other = copy.deepcopy(BASE); other['assets'][0]['attribution'] = ''
        self.assertFalse(compare(BASE, other)['metadata_preserved'])

    def test_false_not_zero(self):
        other = copy.deepcopy(BASE); other['assets'][0]['rights']['commercial'] = 0
        self.assertFalse(compare(BASE, other)['metadata_preserved'])

    def test_missing_field_not_null(self):
        before = copy.deepcopy(BASE); before['assets'][0]['attribution'] = None
        after = copy.deepcopy(before); del after['assets'][0]['attribution']
        self.assertEqual(compare(before, after)['issues'][0]['kind'], 'missing_field')

    def test_preserved_unknown_is_not_clearance(self):
        before = copy.deepcopy(BASE); before['assets'][0]['rights'] = None
        report = compare(before, before)
        self.assertTrue(report['metadata_preserved'])
        self.assertIn('rights', report['baseline_unknowns'][0]['fields'])

    def test_missing_unexpected(self):
        other = copy.deepcopy(BASE); other['assets'][0]['asset_id'] = 'untracked'
        self.assertEqual([r['kind'] for r in compare(BASE, other)['issues']], ['missing_asset', 'unexpected_asset'])

    def test_duplicate_asset_rejected(self):
        other = copy.deepcopy(BASE); other['assets'] *= 2
        with self.assertRaises(ValueError): compare(BASE, other)

    def test_empty_baseline_rejected(self):
        with self.assertRaises(ValueError): compare({'schema_version': 1, 'assets': []}, BASE)

    def test_incomplete_baseline_rejected(self):
        before = copy.deepcopy(BASE); del before['assets'][0]['source']
        with self.assertRaises(ValueError): compare(before, BASE)

    def test_invalid_version_rejected(self):
        other = copy.deepcopy(BASE); other['schema_version'] = True
        with self.assertRaises(ValueError): compare(BASE, other)

    def test_array_order_preserved(self):
        other = copy.deepcopy(BASE); other['assets'][0]['rights']['tags'].reverse()
        self.assertFalse(compare(BASE, other)['metadata_preserved'])

    def test_asset_order_irrelevant(self):
        before = copy.deepcopy(BASE); second = copy.deepcopy(before['assets'][0]); second['asset_id'] = 'second'
        before['assets'].append(second); after = copy.deepcopy(before); after['assets'].reverse()
        self.assertTrue(compare(before, after)['metadata_preserved'])

    def test_json_pointer_escape(self):
        self.assertEqual(differences({'a/b~c': 1}, {}, '/rights'), ['/rights/a~1b~0c'])

    def test_ambiguous_json_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.json'
            for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
                path.write_text(raw)
                with self.assertRaises(ValueError): load(path)

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'large.json'; path.write_bytes(b' ' * 5_000_001)
            with self.assertRaises(ValueError): load(path)

    def test_cli_exit_codes_and_no_values_in_report(self):
        with tempfile.TemporaryDirectory() as folder:
            baseline = Path(folder) / 'base.json'; exported = Path(folder) / 'export.json'
            baseline.write_text(json.dumps(BASE)); exported.write_text(json.dumps(BASE))
            script = str(Path(__file__).with_name('attribution_check.py'))
            def run(): return subprocess.run([sys.executable, script, str(baseline), str(exported)], capture_output=True, text=True)
            self.assertEqual(run().returncode, 0)
            other = copy.deepcopy(BASE); other['assets'][0]['attribution'] = 'private-value'
            exported.write_text(json.dumps(other)); result = run()
            self.assertEqual(result.returncode, 1); self.assertNotIn('private-value', result.stdout)
            exported.write_text('not json'); self.assertEqual(run().returncode, 2)


if __name__ == '__main__': unittest.main()
