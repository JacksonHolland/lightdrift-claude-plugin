import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import validate_search_response as vsr

FIXTURES = Path(__file__).parent / 'fixtures'
OPENAPI = Path('/data/workspaces/content-distribution/lightdrift-docs/openapi.json')


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = vsr.main(argv)
    return code, out.getvalue(), err.getvalue()


def write(payload):
    handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
    json.dump(payload, handle)
    handle.close()
    return handle.name


class LoadTests(unittest.TestCase):
    def test_missing_file_is_error(self):
        with self.assertRaises(vsr.InputError):
            vsr.load_json('/nonexistent.json')

    def test_invalid_json_is_error(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        handle.write('{bad')
        handle.close()
        with self.assertRaises(vsr.InputError):
            vsr.load_json(handle.name)


class ExtractSchemaTests(unittest.TestCase):
    def test_openapi_document(self):
        schema = vsr.extract_schema(json.load(open(OPENAPI)))
        self.assertEqual(schema['properties']['query_type']['enum'], ['text', 'image', 'image_text'])
        self.assertIn('Result', schema['$defs'])

    def test_schema_with_defs_passthrough(self):
        doc = {'$defs': {'Result': {'type': 'object'}}, 'properties': {'results': {'type': 'array'}}}
        self.assertIs(vsr.extract_schema(doc), doc)

    def test_bare_properties(self):
        doc = {'properties': {'query_id': {'type': 'string'}}}
        self.assertIs(vsr.extract_schema(doc), doc)

    def test_rejects_non_dict(self):
        with self.assertRaises(vsr.InputError):
            vsr.extract_schema(['nope'])

    def test_rejects_unrelated_document(self):
        with self.assertRaises(vsr.InputError):
            vsr.extract_schema({'openapi': '3.0.0'})


class TypeTests(unittest.TestCase):
    def schema(self):
        return json.load(open(Path(__file__).parent / 'schema' / 'search-response.schema.json'))

    def errors(self, value, prop):
        errs, warns = [], []
        vsr.validate_node(value, self.schema()['properties'][prop], self.schema(), '$', errs, warns)
        return errs

    def test_latency_integer(self):
        self.assertEqual(self.errors(120, 'latency_ms'), [])

    def test_latency_string_fails(self):
        self.assertTrue(self.errors('fast', 'latency_ms'))

    def test_boolean_is_not_integer(self):
        self.assertTrue(self.errors(True, 'latency_ms'))

    def test_results_must_be_array(self):
        self.assertTrue(self.errors({'a': 1}, 'results'))

    def test_query_type_enum(self):
        self.assertTrue(self.errors('video', 'query_type'))
        self.assertEqual(self.errors('image_text', 'query_type'), [])

    def test_relaxed_items_are_strings(self):
        self.assertTrue(self.errors([1000], 'relaxed'))

    def test_degraded_is_string(self):
        self.assertEqual(self.errors('reranker unavailable', 'degraded'), [])

    def test_nested_result_type_error(self):
        schema = self.schema()
        result = {'asset_id': 'x', 'width': 'wide'}
        errs, warns = [], []
        vsr.validate_node(result, schema['$defs']['Result'], schema, '$', errs, warns)
        self.assertTrue(any(e['path'] == '$.width' for e in errs))

    def test_rights_boolean_type(self):
        schema = self.schema()
        errs, warns = [], []
        vsr.validate_node({'commercial': 'yes'}, schema['$defs']['Rights'], schema, '$', errs, warns)
        self.assertTrue(errs)

    def test_anyof_null_union(self):
        schema = {'anyOf': [{'type': 'integer'}, {'type': 'null'}]}
        for value in (5, None):
            errs, _ = [], []
            vsr.validate_node(value, schema, schema, '$', errs, [])
            self.assertEqual(errs, [])
        errs = []
        vsr.validate_node('x', schema, schema, '$', errs, [])
        self.assertTrue(errs)

    def test_minimum_and_maximum(self):
        schema = {'type': 'integer', 'minimum': 1, 'maximum': 100}
        errs = []
        vsr.validate_node(0, schema, schema, '$', errs, [])
        self.assertTrue(errs)
        errs = []
        vsr.validate_node(101, schema, schema, '$', errs, [])
        self.assertTrue(errs)

    def test_unknown_field_warns(self):
        schema = self.schema()
        errs, warns = [], []
        vsr.validate_node({'query_id': 'q', 'surprise': 1}, schema, schema, '$', errs, warns)
        self.assertEqual(errs, [])
        self.assertTrue(any('surprise' in w['path'] for w in warns))


class SemanticTests(unittest.TestCase):
    def warnings_for(self, response):
        warns = []
        vsr.semantic_checks(response, warns)
        return warns

    def test_missing_query_id(self):
        self.assertTrue(any(w['path'] == 'query_id' for w in self.warnings_for({'results': []})))

    def test_empty_results(self):
        warns = self.warnings_for({'query_id': 'q', 'results': []})
        self.assertTrue(any(w['path'] == 'results' for w in warns))

    def test_duplicate_asset_id(self):
        response = {'query_id': 'q', 'results': [{'asset_id': 'a'}, {'asset_id': 'a'}]}
        self.assertTrue(any('duplicate' in w['message'] for w in self.warnings_for(response)))

    def test_relative_url_warns(self):
        response = {'query_id': 'q', 'results': [{'asset_id': 'a', 'file': '/x.jpg'}]}
        self.assertTrue(any(w['path'].endswith('file') for w in self.warnings_for(response)))

    def test_nonpositive_dimension_warns(self):
        response = {'query_id': 'q', 'results': [{'asset_id': 'a', 'width': 0, 'height': 5}]}
        self.assertTrue(any('positive' in w['message'] for w in self.warnings_for(response)))

    def test_attribution_required_without_text(self):
        response = {'query_id': 'q', 'results': [{'asset_id': 'a', 'rights': {'attribution_required': True}}]}
        self.assertTrue(any('attribution_required' in w['message'] for w in self.warnings_for(response)))

    def test_clean_response_has_no_semantic_warnings(self):
        response = json.load(open(FIXTURES / 'search-response.json'))
        self.assertEqual(self.warnings_for(response), [])


class ValidateTests(unittest.TestCase):
    def load(self, name):
        return json.load(open(FIXTURES / name))

    def schema(self):
        return json.load(open(Path(__file__).parent / 'schema' / 'search-response.schema.json'))

    def test_clean_is_valid(self):
        report = vsr.validate(self.load('search-response.json'), self.schema())
        self.assertEqual(report['status'], 'valid')
        self.assertEqual(report['error_count'], 0)
        self.assertEqual(report['warning_count'], 0)

    def test_empty_is_warnings(self):
        report = vsr.validate(self.load('search-response-empty.json'), self.schema())
        self.assertEqual(report['status'], 'warnings')

    def test_errors_fixture_is_invalid(self):
        report = vsr.validate(self.load('search-response-errors.json'), self.schema())
        self.assertEqual(report['status'], 'invalid')
        self.assertGreaterEqual(report['error_count'], 4)


class MainTests(unittest.TestCase):
    def test_clean_exit_zero(self):
        code, out, err = run([str(FIXTURES / 'search-response.json')])
        self.assertEqual(code, 0)
        self.assertEqual(out, '')
        self.assertIn('valid', err)

    def test_errors_exit_one(self):
        code, _, _ = run([str(FIXTURES / 'search-response-errors.json'), '--quiet'])
        self.assertEqual(code, 1)

    def test_warnings_exit_zero_by_default(self):
        code, _, _ = run([str(FIXTURES / 'search-response-warnings.json'), '--quiet'])
        self.assertEqual(code, 0)

    def test_strict_warnings_exit_one(self):
        code, _, _ = run([str(FIXTURES / 'search-response-warnings.json'), '--strict', '--quiet'])
        self.assertEqual(code, 1)

    def test_missing_response_exit_two(self):
        code, out, _ = run(['/nonexistent/response.json'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)['status'], 'error')

    def test_report_written(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        handle.close()
        run([str(FIXTURES / 'search-response-warnings.json'), '--report', handle.name, '--quiet'])
        report = json.load(open(handle.name))
        self.assertEqual(report['status'], 'warnings')
        self.assertTrue(report['warnings'])

    def test_openapi_schema_override(self):
        code, _, _ = run([str(FIXTURES / 'search-response.json'), '--schema', str(OPENAPI), '--quiet'])
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
