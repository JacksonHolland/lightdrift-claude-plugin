import io
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import search_to_feed as s2f

FIXTURES = Path(__file__).parent / 'fixtures'


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = s2f.main(argv)
    return code, out.getvalue(), err.getvalue()


def write(payload):
    handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
    json.dump(payload, handle)
    handle.close()
    return handle.name


def sample_result(**overrides):
    result = {
        'asset_id': 's:1',
        'title': 'A subject',
        'width': 100,
        'height': 50,
        'file': 'https://api.lightdrift.ai/v1/asset/q/x.jpg',
        'thumb': 'https://api.lightdrift.ai/v1/asset/q/x.jpg?v=thumb',
        'rights': {'license': 'https://example.org/l', 'attribution': 'A Person',
                   'attribution_required': True, 'provenance_url': 'https://example.org/page'},
    }
    result.update(overrides)
    return result


class LoadTests(unittest.TestCase):
    def test_missing_file_is_error(self):
        with self.assertRaises(OSError):
            s2f.load_response('/nonexistent/response.json')

    def test_invalid_json_is_error(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        handle.write('{bad')
        handle.close()
        with self.assertRaises(ValueError):
            s2f.load_response(handle.name)

    def test_top_level_must_be_object(self):
        with self.assertRaises(ValueError):
            s2f.load_response(write([1, 2]))

    def test_results_must_be_array(self):
        with self.assertRaises(ValueError):
            s2f.load_response(write({'results': {}}))

    def test_result_must_be_object(self):
        with self.assertRaises(ValueError):
            s2f.load_response(write({'results': ['x']}))


class DescribeTests(unittest.TestCase):
    def test_asset_id_wins_as_item_id(self):
        item = s2f.describe_item(sample_result(), 0, 'q1')
        self.assertEqual(item['id'], 's:1')

    def test_query_rank_fallback_id(self):
        item = s2f.describe_item(sample_result(asset_id=''), 2, 'q1')
        self.assertEqual(item['id'], 'q1#3')
        self.assertTrue(any('no asset_id' in w for w in item['warnings']))

    def test_position_fallback_id(self):
        item = s2f.describe_item(sample_result(asset_id=None), 0, None)
        self.assertEqual(item['id'], 'result-1')

    def test_provenance_preferred_for_url(self):
        item = s2f.describe_item(sample_result(), 0, 'q1')
        self.assertEqual(item['url'], 'https://example.org/page')

    def test_tracked_url_used_when_no_provenance(self):
        rights = {'license': 'https://example.org/l'}
        item = s2f.describe_item(sample_result(rights=rights), 0, 'q1')
        self.assertEqual(item['url'], 'https://api.lightdrift.ai/v1/asset/q/x.jpg')
        self.assertTrue(any('tracked URL' in w for w in item['warnings']))

    def test_relative_file_is_omitted(self):
        item = s2f.describe_item(sample_result(file='/v1/asset/x.jpg'), 0, 'q1')
        self.assertIsNone(item['image'])
        self.assertTrue(any('not an absolute URL' in w for w in item['warnings']))

    def test_mime_inferred_from_suffix(self):
        item = s2f.describe_item(sample_result(file='https://example.org/a/photo.JPG?x=1'), 0, 'q1')
        self.assertEqual(item['mime_type'], 'image/jpeg')

    def test_mime_omitted_for_extensionless_tracked_url(self):
        rights = {'provenance_url': 'https://example.org/page'}
        item = s2f.describe_item(sample_result(file='https://api.lightdrift.ai/v1/asset/q/govflickr:1', rights=rights), 0, 'q1')
        self.assertIsNone(item['mime_type'])

    def test_non_string_license_warns(self):
        item = s2f.describe_item(sample_result(rights={'license': 42}), 0, 'q1')
        self.assertTrue(any('license is not a string' in w for w in item['warnings']))

    def test_attribution_required_without_text_warns(self):
        rights = {'attribution_required': True}
        item = s2f.describe_item(sample_result(rights=rights), 0, 'q1')
        self.assertTrue(any('no attribution text' in w for w in item['warnings']))

    def test_missing_dimensions_warn(self):
        item = s2f.describe_item(sample_result(width=None, height=None), 0, 'q1')
        self.assertTrue(any('intrinsic size' in w for w in item['warnings']))

    def test_extension_omits_unknown_fields(self):
        item = s2f.describe_item(sample_result(rights={}), 0, 'q1')
        self.assertNotIn('license', item['extension'])
        self.assertNotIn('attribution', item['extension'])
        self.assertEqual(item['extension']['rank'], 1)


class JsonFeedTests(unittest.TestCase):
    def meta(self, **overrides):
        base = {'title': 'T', 'home_url': 'https://example.org/', 'feed_url': 'https://example.org/feed.json', 'description': 'D'}
        base.update(overrides)
        return base

    def test_document_shape(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        feed, warnings = s2f.build_jsonfeed(response, self.meta())
        self.assertEqual(feed['version'], s2f.JSONFEED_VERSION)
        self.assertEqual(feed['title'], 'T')
        self.assertEqual(len(feed['items']), 2)
        self.assertEqual(feed['home_page_url'], 'https://example.org/')
        self.assertEqual(feed['feed_url'], 'https://example.org/feed.json')
        self.assertEqual(warnings, [])

    def test_item_fields(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        feed, _ = s2f.build_jsonfeed(response, self.meta())
        first = feed['items'][0]
        self.assertEqual(first['id'], 'govflickr:8412901414')
        self.assertEqual(first['url'], 'https://www.flickr.com/photos/usfws/8412901414')
        self.assertEqual(first['title'], 'Sea otter floating on its back')
        self.assertIn('image', first)
        self.assertEqual(first['attachments'][0]['url'], first['image'])

    def test_extension_carries_rights(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        feed, _ = s2f.build_jsonfeed(response, self.meta())
        ext = feed['items'][1]['_lightdrift']
        self.assertEqual(ext['license'], 'cc-by-sa-4.0')
        self.assertTrue(ext['share_alike'])

    def test_no_creation_date_is_invented(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        feed, _ = s2f.build_jsonfeed(response, self.meta())
        for item in feed['items']:
            self.assertNotIn('date_published', item)

    def test_empty_results_warns(self):
        response = s2f.load_response(str(FIXTURES / 'search-response-empty.json'))
        feed, warnings = s2f.build_jsonfeed(response, self.meta())
        self.assertEqual(feed['items'], [])
        self.assertTrue(any('no results' in w for w in warnings))

    def test_missing_home_url_warns(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        _, warnings = s2f.build_jsonfeed(response, self.meta(home_url=None))
        self.assertTrue(any('home_page_url' in w for w in warnings))


class RssTests(unittest.TestCase):
    def meta(self):
        return {'title': 'T', 'home_url': 'https://example.org/', 'feed_url': None, 'description': 'D'}

    def test_rss_is_well_formed(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        rss, _ = s2f.build_rss(response, self.meta())
        parsed = ET.fromstring(ET.tostring(rss, encoding='unicode'))
        self.assertEqual(parsed.tag, 'rss')
        self.assertEqual(parsed.get('version'), '2.0')

    def test_channel_fields(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        rss, _ = s2f.build_rss(response, self.meta())
        channel = rss.find('channel')
        self.assertEqual(channel.findtext('title'), 'T')
        self.assertEqual(channel.findtext('link'), 'https://example.org/')

    def test_item_guid_and_media(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        rss, _ = s2f.build_rss(response, self.meta())
        item = rss.find('channel/item')
        guid = item.find('guid')
        self.assertEqual(guid.get('isPermaLink'), 'false')
        self.assertEqual(guid.text, 'govflickr:8412901414')
        content = item.find(f'{{{s2f.MEDIA_NS}}}content')
        self.assertEqual(content.get('width'), '1024')
        self.assertEqual(content.get('height'), '768')

    def test_thumbnail_added_when_distinct(self):
        response = s2f.load_response(str(FIXTURES / 'search-response.json'))
        rss, _ = s2f.build_rss(response, self.meta())
        item = rss.find('channel/item')
        self.assertIsNotNone(item.find(f'{{{s2f.MEDIA_NS}}}thumbnail'))


class MainTests(unittest.TestCase):
    def complete_args(self, extra):
        return [str(FIXTURES / 'search-response.json'), '--home-url', 'https://example.org/'] + extra

    def test_jsonfeed_exit_zero(self):
        code, out, _ = run(self.complete_args(['--pretty']))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['version'], s2f.JSONFEED_VERSION)

    def test_rss_exit_zero(self):
        code, out, _ = run(self.complete_args(['--format', 'rss']))
        self.assertEqual(code, 0)
        ET.fromstring(out)

    def test_valid_batch_has_no_warnings(self):
        code, _, err = run(self.complete_args(['--feed-url', 'https://example.org/feed.json', '--description', 'D']))
        self.assertEqual(code, 0)
        self.assertEqual(err, '')

    def test_require_complete_fails_on_warning(self):
        code, _, _ = run([str(FIXTURES / 'search-response-minimal.json'), '--require-complete'])
        self.assertEqual(code, 1)

    def test_missing_response_exit_two(self):
        code, out, _ = run(['/nonexistent/response.json'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)['status'], 'error')

    def test_report_written(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        handle.close()
        code, _, _ = run([str(FIXTURES / 'search-response-minimal.json'), '--report', handle.name])
        self.assertEqual(code, 0)
        report = json.load(open(handle.name))
        self.assertEqual(report['items'], 1)
        self.assertTrue(report['warnings'])

    def test_escaping_survives_both_formats(self):
        path = write({'query_id': 'q', 'results': [sample_result(title='A <b>& "quoted"')]})
        _, json_out, _ = run([path, '--home-url', 'https://example.org/'])
        self.assertEqual(json.loads(json_out)['items'][0]['title'], 'A <b>& "quoted"')
        _, rss_out, _ = run([path, '--format', 'rss', '--home-url', 'https://example.org/'])
        parsed = ET.fromstring(rss_out)
        self.assertEqual(parsed.find('channel/item').findtext('title'), 'A <b>& "quoted"')


if __name__ == '__main__':
    unittest.main()
