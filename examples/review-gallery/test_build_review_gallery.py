import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import build_review_gallery as rg

FIXTURES = Path(__file__).parent / 'fixtures'


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = rg.main(argv)
    return code, out.getvalue(), err.getvalue()


def write(payload):
    handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
    json.dump(payload, handle)
    handle.close()
    return handle.name


def complete_result(**overrides):
    result = {
        'asset_id': 's:1',
        'title': 'A subject',
        'width': 100,
        'height': 50,
        'file': 'https://api.lightdrift.ai/v1/asset/q/x.jpg',
        'thumb': 'https://api.lightdrift.ai/v1/asset/q/x.jpg?v=thumb',
        'rights': {'license': 'cc-by-4.0', 'license_verbatim': 'CC BY 4.0',
                   'attribution': 'A Person', 'provenance_url': 'https://example.org/page'},
    }
    result.update(overrides)
    return result


class LoadTests(unittest.TestCase):
    def test_missing_file_is_error(self):
        with self.assertRaises(rg.InputError):
            rg.load_response('/nonexistent/response.json')

    def test_invalid_json_is_error(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        handle.write('{bad')
        handle.close()
        with self.assertRaises(rg.InputError):
            rg.load_response(handle.name)

    def test_top_level_must_be_object(self):
        with self.assertRaises(rg.InputError):
            rg.load_response(write([1]))

    def test_results_must_be_array(self):
        with self.assertRaises(rg.InputError):
            rg.load_response(write({'results': {}}))

    def test_result_must_be_object(self):
        with self.assertRaises(rg.InputError):
            rg.load_response(write({'results': ['x']}))


class DescribeTests(unittest.TestCase):
    def test_complete_result_has_no_missing(self):
        item = rg.describe(complete_result(), 0, 'q1')
        self.assertEqual(item['missing'], [])

    def test_anchor_uses_asset_id(self):
        item = rg.describe(complete_result(), 0, 'q1')
        self.assertEqual(item['anchor'], 's:1')

    def test_anchor_query_fallback(self):
        item = rg.describe(complete_result(asset_id=''), 2, 'q1')
        self.assertEqual(item['anchor'], 'q1#3')
        self.assertIn('asset_id', item['missing'])

    def test_anchor_position_fallback(self):
        item = rg.describe(complete_result(asset_id=None), 0, None)
        self.assertEqual(item['anchor'], 'result-1')

    def test_thumb_preferred_over_file(self):
        item = rg.describe(complete_result(), 0, 'q1')
        self.assertTrue(item['image_url'].endswith('?v=thumb'))

    def test_file_used_when_thumb_missing(self):
        item = rg.describe(complete_result(thumb=None), 0, 'q1')
        self.assertEqual(item['image_url'], 'https://api.lightdrift.ai/v1/asset/q/x.jpg')

    def test_image_missing_when_paths_relative(self):
        item = rg.describe(complete_result(thumb=None, file='/relative.jpg'), 0, 'q1')
        self.assertIsNone(item['image_url'])
        self.assertIn('image', item['missing'])

    def test_missing_title_flagged(self):
        item = rg.describe(complete_result(title='  '), 0, 'q1')
        self.assertIn('title', item['missing'])

    def test_missing_provenance_flagged(self):
        rights = {'license': 'cc-by-4.0', 'attribution': 'A Person'}
        item = rg.describe(complete_result(rights=rights), 0, 'q1')
        self.assertIn('provenance_url', item['missing'])

    def test_attribution_required_without_text_flagged(self):
        rights = {'license': 'cc-by-4.0', 'provenance_url': 'https://example.org/p',
                  'attribution_required': True}
        item = rg.describe(complete_result(rights=rights), 0, 'q1')
        self.assertIn('attribution', item['missing'])

    def test_missing_dimensions_flagged(self):
        item = rg.describe(complete_result(width=None, height=None), 0, 'q1')
        self.assertIn('dimensions', item['missing'])

    def test_license_verbatim_counts_as_license(self):
        rights = {'license_verbatim': 'CC0 1.0', 'attribution': 'A Person',
                  'provenance_url': 'https://example.org/p'}
        item = rg.describe(complete_result(rights=rights), 0, 'q1')
        self.assertNotIn('license', item['missing'])


class RenderTests(unittest.TestCase):
    def meta(self, **overrides):
        base = {'title': 'Review', 'subtitle': None, 'generated_at': None}
        base.update(overrides)
        return base

    def load(self, name):
        return rg.load_response(str(FIXTURES / name))

    def test_document_structure(self):
        document, warnings, report = rg.render(self.load('search-response.json'), self.meta())
        self.assertTrue(document.startswith('<!DOCTYPE html>'))
        self.assertEqual(report['result_count'], 2)
        self.assertEqual(warnings, [])
        self.assertEqual(document.count('<figure'), 2)

    def test_image_attributes(self):
        document, _, _ = rg.render(self.load('search-response.json'), self.meta())
        self.assertIn('loading="lazy"', document)
        self.assertIn('decoding="async"', document)
        self.assertIn('width="1024"', document)
        self.assertIn('height="768"', document)

    def test_no_external_resources(self):
        document, _, _ = rg.render(self.load('search-response.json'), self.meta())
        self.assertNotIn('<script', document)
        self.assertNotIn('<link', document)
        self.assertNotIn('@import', document)

    def test_subtitle_and_generated_at(self):
        document, _, _ = rg.render(self.load('search-response.json'), self.meta(subtitle='Sub', generated_at='2026-09-27'))
        self.assertIn('<p class="subtitle">Sub</p>', document)
        self.assertIn('built 2026-09-27', document)

    def test_generated_at_absent_by_default(self):
        document, _, _ = rg.render(self.load('search-response.json'), self.meta())
        self.assertNotIn('built ', document)

    def test_missing_markers_rendered(self):
        document, warnings, report = rg.render(self.load('search-response-partial.json'), self.meta())
        self.assertIn('class="missing"', document)
        self.assertTrue(warnings)
        self.assertEqual(len(report['assets']), 2)

    def test_empty_results_warns(self):
        document, warnings, report = rg.render(self.load('search-response-empty.json'), self.meta())
        self.assertEqual(report['result_count'], 0)
        self.assertTrue(any('no results' in w for w in warnings))

    def test_credit_line_combines_attribution_and_license(self):
        document, _, _ = rg.render(self.load('search-response.json'), self.meta())
        self.assertIn('Credit: US Fish and Wildlife Service / Public Domain Mark 1.0', document)


class MainTests(unittest.TestCase):
    def test_stdout_exit_zero(self):
        code, out, err = run([str(FIXTURES / 'search-response.json')])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith('<!DOCTYPE html>'))
        self.assertEqual(err, '')

    def test_output_file_written(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.html', delete=False)
        handle.close()
        code, out, _ = run([str(FIXTURES / 'search-response.json'), '--output', handle.name])
        self.assertEqual(code, 0)
        self.assertEqual(out, '')
        self.assertIn('<!DOCTYPE html>', Path(handle.name).read_text())

    def test_report_written(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        handle.close()
        run([str(FIXTURES / 'search-response-partial.json'), '--report', handle.name])
        report = json.load(open(handle.name))
        self.assertEqual(report['result_count'], 2)
        self.assertTrue(report['assets'][0]['missing'])

    def test_require_complete_passes_when_clean(self):
        code, _, _ = run([str(FIXTURES / 'search-response.json'), '--require-complete'])
        self.assertEqual(code, 0)

    def test_require_complete_fails_when_incomplete(self):
        code, _, _ = run([str(FIXTURES / 'search-response-partial.json'), '--require-complete'])
        self.assertEqual(code, 1)

    def test_missing_response_exit_two(self):
        code, out, _ = run(['/nonexistent/response.json'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)['status'], 'error')

    def test_title_is_escaped(self):
        path = write({'query_id': 'q', 'results': [complete_result()]})
        code, out, _ = run([path, '--title', '<script>alert(1)</script>'])
        self.assertEqual(code, 0)
        self.assertNotIn('<script>alert(1)</script>', out)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', out)

    def test_value_is_escaped_in_caption(self):
        path = write({'query_id': 'q', 'results': [complete_result(title='A & B <b>')]})
        _, out, _ = run([path])
        self.assertIn('A &amp; B &lt;b&gt;', out)


if __name__ == '__main__':
    unittest.main()
