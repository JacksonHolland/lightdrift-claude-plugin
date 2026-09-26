import copy
import importlib.util
import json
from pathlib import Path
import unittest
from layout_audit import main

ROOT = Path(__file__).parent

class Tests(unittest.TestCase):
    def test_valid_and_unknown_fixture(self):
        args = json.loads((ROOT / 'fixture-arguments.json').read_text())
        before = copy.deepcopy(args)
        report = main(**args)
        wide, square, unknown = [x['layout'] for x in report['candidates']]
        self.assertEqual(wide['retained_area_percent'], 100)
        self.assertFalse(wide['upscale_required'])
        self.assertEqual(square['retained_area_percent'], 56.25)
        self.assertTrue(square['upscale_required'])
        self.assertEqual(unknown, {'status': 'unknown_dimensions'})
        self.assertEqual(report['original_response'], args['response'])
        self.assertEqual(args, before)
        json.dumps(report, allow_nan=False)

    def test_preserves_unknown_metadata_and_order(self):
        response = {'degraded': True, 'relaxed': ['orientation'], 'future': {'v': [1]},
                    'results': [{'asset_id': 'fixture:duplicate', 'rights': {'future': None}},
                                {'asset_id': 'fixture:duplicate', 'credit': 'synthetic'}]}
        report = main(response, 100, 100)
        self.assertEqual(report['original_response'], response)
        self.assertEqual([c['asset'] for c in report['candidates']], response['results'])
        self.assertEqual([c['input_index'] for c in report['candidates']], [0, 1])
        report['original_response']['future']['v'].append(2)
        self.assertEqual(response['future']['v'], [1])

    def test_invalid_targets(self):
        for field in ('width', 'height', 'dpr'):
            for value in (0, -1, None, True, '100', float('nan'), float('inf')):
                args = dict(response={'results': []}, width=100, height=100, dpr=1)
                args[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    main(**args)

    def test_unknown_source_dimensions(self):
        for value in (None, 0, -2, True, '100'):
            report = main({'results': [{'width': value, 'height': 100}]}, 100, 100)
            self.assertEqual(report['candidates'][0]['layout']['status'], 'unknown_dimensions')

    def test_bad_envelopes(self):
        for response in ([], {}, {'results': None}, {'results': [None]}):
            with self.assertRaises(ValueError):
                main(response, 100, 100)

    def test_empty_and_default_dpr(self):
        report = main({'results': []}, 100, 100)
        self.assertEqual(report['candidates'], [])
        self.assertEqual(report['target']['device_pixel_ratio'], 1)

    def test_vendored_parity(self):
        spec = importlib.util.spec_from_file_location('original', ROOT.parent / 'layout-fit/layout_fit.py')
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        args = json.loads((ROOT / 'fixture-arguments.json').read_text())
        for dpr in (1, 2, 3):
            args['dpr'] = dpr
            self.assertEqual(main(**args), original.audit(**args))

    def test_unrepresentable_geometry_fails_closed(self):
        with self.assertRaises(ValueError):
            main({'results': [{'width': 100, 'height': 100}]}, 1e308, 100, 1e308)

if __name__ == '__main__':
    unittest.main()
