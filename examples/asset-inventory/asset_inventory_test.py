import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import asset_inventory as ai  # noqa: E402

VALID = HERE / 'fixtures' / 'valid'
MALFORMED = HERE / 'fixtures' / 'malformed.json'


def load(paths):
    errors = []
    objects = []
    for path in paths:
        objects.extend(ai.load_objects(path, errors))
    assert not errors, errors
    return objects


class ClassificationTests(unittest.TestCase):
    def test_search_and_asset_are_distinguished(self):
        self.assertEqual(ai.classify({'results': []}), 'search')
        self.assertEqual(ai.classify({'query_id': 'q'}), 'search')
        self.assertEqual(ai.classify({'asset_id': 'x'}), 'asset')
        self.assertEqual(ai.classify({'unrelated': 1}), 'other')


class LoadTests(unittest.TestCase):
    def test_directory_loads_every_json(self):
        objects = load([VALID])
        self.assertEqual(len(objects), 4)

    def test_malformed_reports_error_not_crash(self):
        errors = []
        ai.load_objects(MALFORMED, errors)
        self.assertTrue(errors)
        self.assertIn('invalid JSON', errors[0])

    def test_missing_path_reports_error(self):
        errors = []
        ai.load_objects(Path('/nonexistent/nope.json'), errors)
        self.assertTrue(errors)


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = ai.build_inventory(load([VALID]))

    def test_counts(self):
        self.assertEqual(self.report['search_responses'], 2)
        self.assertEqual(self.report['asset_responses'], 2)
        self.assertEqual(self.report['distinct_assets_seen'], 4)
        self.assertEqual(self.report['assets_with_asset_response'], 2)

    def test_unresolved_ids(self):
        self.assertEqual(self.report['unresolved_asset_ids'], ['fixture:a2', 'fixture:a4'])

    def test_duplicate_detection(self):
        self.assertEqual(self.report['duplicate_assets_across_responses'], {'fixture:a3': 2})

    def test_field_conflict_width_and_rights(self):
        conflicts = self.report['field_conflicts']['fixture:a1']
        self.assertEqual(conflicts['width'], {'search': 1920, 'asset': 1900})
        self.assertEqual(conflicts['rights.commercial'], {'search': False, 'asset': True})

    def test_rights_attribution_conflict(self):
        conflicts = self.report['field_conflicts']['fixture:a3']
        self.assertEqual(conflicts['rights.attribution_required'], {'search': False, 'asset': True})

    def test_request_plan_shape_and_order(self):
        plan = self.report['request_plan']
        self.assertEqual([p['asset_id'] for p in plan], ['fixture:a2', 'fixture:a4'])
        self.assertTrue(all(p['url'].endswith(p['asset_id']) for p in plan))

    def test_inventory_flags_presence(self):
        inv = self.report['inventory']
        self.assertTrue(inv['fixture:a1']['has_asset_response'])
        self.assertFalse(inv['fixture:a2']['has_asset_response'])
        self.assertEqual(inv['fixture:a3']['in_search_responses'], 2)


class CliTests(unittest.TestCase):
    def run_main(self, argv):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ai.main(argv)
        return code, buf.getvalue()

    def test_json_output_is_valid(self):
        code, out = self.run_main([str(VALID)])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload['distinct_assets_seen'], 4)

    def test_plan_only_is_a_list(self):
        code, out = self.run_main([str(VALID), '--plan-only'])
        self.assertEqual(code, 0)
        self.assertIsInstance(json.loads(out), list)

    def test_text_format_summarises(self):
        code, out = self.run_main([str(VALID), '--format', 'text'])
        self.assertEqual(code, 0)
        self.assertIn('missing asset responses: 2', out)

    def test_malformed_input_exits_two(self):
        code, _ = self.run_main([str(MALFORMED)])
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
