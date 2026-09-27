import io
import json
import contextlib
import tempfile
import unittest
from pathlib import Path

import search_telemetry as st

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'fixtures'


def load(path):
    errors = []
    objects = st.load_objects(path, errors)
    assert not errors, errors
    return objects


class LoadTests(unittest.TestCase):
    def test_array_file_yields_three_responses(self):
        objects = load(FIXTURES / 'responses.json')
        self.assertEqual(len(objects), 3)

    def test_single_object_file(self):
        objects = load(FIXTURES / 'single.json')
        self.assertEqual(len(objects), 1)
        self.assertTrue(st._looks_like_response(objects[0][2]))

    def test_malformed_file_reports_error(self):
        errors = []
        objects = st.load_objects(FIXTURES / 'malformed.json', errors)
        self.assertEqual(objects, [])
        self.assertEqual(len(errors), 1)
        self.assertIn('invalid JSON', errors[0])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.report = st.build_report(load(FIXTURES / 'responses.json'))

    def test_counts(self):
        self.assertEqual(self.report['responses'], 3)
        self.assertEqual(self.report['results_total'], 3)
        self.assertEqual(self.report['results_with_asset_id'], 3)
        self.assertEqual(self.report['results_with_dimensions'], 2)

    def test_latency_only_counts_present_values(self):
        self.assertEqual(self.report['latency_ms']['count'], 2)
        self.assertEqual(self.report['missing_or_non_numeric']['latency_ms'], 1)

    def test_degraded_and_relaxed(self):
        self.assertEqual(self.report['degraded_responses'], 1)
        self.assertEqual(self.report['relaxed_responses'], 1)
        self.assertEqual(self.report['relaxed_filters'], {'orientation': 1, 'min_width': 1})

    def test_envelope_distributions(self):
        self.assertEqual(self.report['mode'], {'auto': 2, 'text': 1})
        self.assertEqual(self.report['ranking'], {'multimodal': 1, 'none (degraded)': 1, 'text': 1})
        self.assertEqual(self.report['query_type'], {'image_text': 1, 'text': 2})
        self.assertEqual(self.report['backend'], {'voyage': 3})

    def test_ratio_filtered_to_nonzero_pool(self):
        ratios = self.report['reranked_over_pool_ratio']
        self.assertEqual(ratios['count'], 3)
        self.assertEqual(ratios['min'], 0.0)
        self.assertEqual(ratios['max'], 0.6)

    def test_notice_states_scope(self):
        self.assertIn('not service performance', self.report['notice'])

    def test_empty_input_is_zeroed(self):
        report = st.build_report([])
        self.assertEqual(report['responses'], 0)
        self.assertEqual(report['latency_ms'], {'count': 0})
        self.assertEqual(report['missing_or_non_numeric'], {})


class CliTests(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = st.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_json_stdout(self):
        code, out, _ = self._run(['--format', 'json', str(FIXTURES / 'responses.json')])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload['responses'], 3)

    def test_text_output(self):
        code, out, _ = self._run(['--format', 'text', str(FIXTURES / 'single.json')])
        self.assertEqual(code, 0)
        self.assertIn('responses: 1', out)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'report.json'
            code, out, _ = self._run([str(FIXTURES / 'single.json'), '--output', str(target)])
            self.assertEqual(code, 0)
            self.assertEqual(out, '')
            self.assertEqual(json.loads(target.read_text())['responses'], 1)

    def test_malformed_returns_two(self):
        code, _, err = self._run([str(FIXTURES / 'malformed.json')])
        self.assertEqual(code, 2)
        self.assertIn('invalid JSON', err)

    def test_missing_path_returns_two(self):
        code, _, err = self._run([str(FIXTURES / 'does-not-exist.json')])
        self.assertEqual(code, 2)
        self.assertIn('not found', err)

    def test_mixed_valid_and_invalid_inputs_fail_closed(self):
        code, _, err = self._run([str(FIXTURES / 'single.json'), str(FIXTURES / 'malformed.json')])
        self.assertEqual(code, 2)
        self.assertIn('invalid JSON', err)


if __name__ == '__main__':
    unittest.main()
