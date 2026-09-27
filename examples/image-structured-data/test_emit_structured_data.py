import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import emit_structured_data as esd

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(HERE, "fixtures", "search-response.json")
INCOMPLETE = os.path.join(HERE, "fixtures", "search-response-incomplete.json")


def one_result(**overrides):
    base = {
        "asset_id": "src:1",
        "title": "A title",
        "source": "src",
        "width": 100,
        "height": 50,
        "file": "https://cdn.example.org/a.jpg",
        "thumb": "https://cdn.example.org/a-thumb.jpg",
        "rights": {
            "license": "https://example.org/license",
            "attribution": "Someone",
            "provenance_url": "https://example.org/source-page",
        },
    }
    base.update(overrides)
    return base


class LoadResponseTests(unittest.TestCase):
    def test_loads_full_fixture(self):
        data = esd.load_response(FULL)
        self.assertEqual(len(data["results"]), 2)

    def test_invalid_json_raises(self):
        path = os.path.join(HERE, "fixtures", "_invalid.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        try:
            with self.assertRaises(ValueError):
                esd.load_response(path)
        finally:
            os.remove(path)

    def test_missing_results_raises(self):
        path = os.path.join(HERE, "fixtures", "_noresults.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"query_id": "x"}, handle)
        try:
            with self.assertRaises(ValueError):
                esd.load_response(path)
        finally:
            os.remove(path)

    def test_non_object_result_raises(self):
        path = os.path.join(HERE, "fixtures", "_badresult.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"results": ["not-an-object"]}, handle)
        try:
            with self.assertRaises(ValueError):
                esd.load_response(path)
        finally:
            os.remove(path)


class DescribeTests(unittest.TestCase):
    def test_maps_known_fields(self):
        d = esd.describe_result(one_result(), "q1")
        self.assertEqual(d["asset_id"], "src:1")
        self.assertEqual(d["name"], "A title")
        self.assertEqual(d["width"], 100)
        self.assertEqual(d["height"], 50)
        self.assertEqual(d["provenance_url"], "https://example.org/source-page")
        self.assertEqual(d["license_url"], "https://example.org/license")

    def test_null_title_is_warned_not_invented(self):
        d = esd.describe_result(one_result(title=None))
        self.assertIsNone(d["name"])
        self.assertTrue(any("no title" in w for w in d["warnings"]))

    def test_blank_title_treated_as_missing(self):
        d = esd.describe_result(one_result(title="   "))
        self.assertIsNone(d["name"])

    def test_relative_file_url_not_used(self):
        d = esd.describe_result(one_result(file="/v1/asset/x"))
        self.assertIsNone(d["content_url"])
        self.assertEqual(d["content_url_raw"], "/v1/asset/x")
        self.assertTrue(any("not an absolute URL" in w for w in d["warnings"]))

    def test_non_string_width_ignored(self):
        d = esd.describe_result(one_result(width="100"))
        self.assertIsNone(d["width"])

    def test_bool_width_ignored(self):
        d = esd.describe_result(one_result(width=True))
        self.assertIsNone(d["width"])

    def test_license_identifier_not_mapped_to_url(self):
        d = esd.describe_result(one_result(rights={"license": "cc0"}))
        self.assertEqual(d["license_id"], "cc0")
        self.assertIsNone(d["license_url"])
        self.assertTrue(any("identifier, not a URL" in w for w in d["warnings"]))

    def test_attribution_required_without_text_warns(self):
        d = esd.describe_result(one_result(rights={"attribution_required": True}))
        self.assertTrue(any("attribution_required is true" in w for w in d["warnings"]))

    def test_missing_rights_warns_unknown(self):
        d = esd.describe_result(one_result(rights=None))
        self.assertFalse(d["rights_present"])
        self.assertTrue(any("no rights object" in w for w in d["warnings"]))

    def test_missing_dimensions_warn(self):
        d = esd.describe_result(one_result(width=None, height=None))
        self.assertTrue(any("missing width and/or height" in w for w in d["warnings"]))

    def test_missing_asset_id_warns(self):
        d = esd.describe_result(one_result(asset_id=None))
        self.assertIsNone(d["asset_id"])
        self.assertTrue(any("missing asset_id" in w for w in d["warnings"]))


class ImageObjectTests(unittest.TestCase):
    def test_minimal_object(self):
        obj = esd.build_image_object(esd.describe_result(one_result()))
        self.assertEqual(obj["@type"], "ImageObject")
        self.assertEqual(obj["identifier"], "src:1")
        self.assertEqual(obj["contentUrl"], "https://cdn.example.org/a.jpg")
        self.assertEqual(obj["creditText"], "Someone")
        self.assertEqual(obj["isBasedOn"], "https://example.org/source-page")
        self.assertEqual(obj["license"], "https://example.org/license")

    def test_unknown_fields_omitted_not_faked(self):
        obj = esd.build_image_object(esd.describe_result(one_result(title=None, rights={"license": "cc0"})))
        self.assertNotIn("name", obj)
        self.assertNotIn("license", obj)
        self.assertNotIn("creator", obj)
        self.assertNotIn("creditText", obj)

    def test_width_height_are_integers(self):
        obj = esd.build_image_object(esd.describe_result(one_result()))
        self.assertIsInstance(obj["width"], int)
        self.assertIsInstance(obj["height"], int)

    def test_graph_single_result_is_plain_image_object(self):
        response = {"query_id": "q", "results": [one_result()]}
        doc = esd.build_graph(response)
        self.assertEqual(doc["@context"], esd.SCHEMA_CONTEXT)
        self.assertEqual(doc["@type"], "ImageObject")
        self.assertNotIn("@graph", doc)

    def test_graph_many_results_uses_graph(self):
        response = {"query_id": "q", "results": [one_result(asset_id="a"), one_result(asset_id="b")]}
        doc = esd.build_graph(response)
        self.assertEqual(len(doc["@graph"]), 2)
        self.assertNotIn("@type", doc)


class OpenGraphTests(unittest.TestCase):
    def test_og_tags_for_absolute_url(self):
        tags = esd.build_opengraph(esd.describe_result(one_result()))
        self.assertEqual(tags["og:image"], "https://cdn.example.org/a.jpg")
        self.assertEqual(tags["og:image:width"], "100")
        self.assertEqual(tags["og:image:height"], "50")
        self.assertEqual(tags["og:image:alt"], "A title")

    def test_og_omits_relative_url(self):
        tags = esd.build_opengraph(esd.describe_result(one_result(file="/x")))
        self.assertNotIn("og:image", tags)
        self.assertEqual(tags["og:image:alt"], "A title")

    def test_og_omits_alt_when_no_title(self):
        tags = esd.build_opengraph(esd.describe_result(one_result(title=None)))
        self.assertNotIn("og:image:alt", tags)

    def test_html_escapes_quotes_and_ampersands(self):
        tags = esd.build_opengraph(esd.describe_result(one_result(title='Fish & "chips"')))
        html = esd.render_opengraph_html(tags)
        self.assertIn("&amp;", html)
        self.assertIn("&quot;", html)
        self.assertNotIn('"Fish & "chips""', html)


class CreditTests(unittest.TestCase):
    def test_credit_joins_attribution_and_provenance(self):
        credit = esd.build_credit(esd.describe_result(one_result()))
        self.assertEqual(credit, "Someone — https://example.org/source-page")

    def test_credit_empty_when_nothing_declared(self):
        credit = esd.build_credit(esd.describe_result(one_result(title=None, rights=None)))
        self.assertEqual(credit, "")

    def test_only_provenance(self):
        credit = esd.build_credit(esd.describe_result(one_result(rights={"provenance_url": "https://e.org/p"})))
        self.assertEqual(credit, "https://e.org/p")


class ReportTests(unittest.TestCase):
    def test_report_marks_rights_unevaluated(self):
        report = esd.build_report(esd.load_response(FULL), FULL)
        self.assertTrue(report["rights_not_evaluated"])
        self.assertEqual(report["result_count"], 2)

    def test_report_collects_warnings_from_incomplete_fixture(self):
        report = esd.build_report(esd.load_response(INCOMPLETE), INCOMPLETE)
        self.assertTrue(any("no title" in w for w in report["warnings"]))
        self.assertTrue(any("no rights object" in w for w in report["warnings"]))

    def test_completeness_gate(self):
        complete = esd.describe_result(one_result())
        incomplete = esd.describe_result(one_result(title=None))
        self.assertTrue(esd.is_complete(complete))
        self.assertFalse(esd.is_complete(incomplete))


def _run_cli(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return esd.main(argv)


class CliTests(unittest.TestCase):
    def test_jsonld_format_single(self):
        out = esd._format_output("jsonld", esd.load_response(FULL), [esd.describe_result(r) for r in esd.load_response(FULL)["results"]], False)
        doc = json.loads(out)
        self.assertEqual(doc["@context"], esd.SCHEMA_CONTEXT)
        self.assertIn("@graph", doc)

    def test_cli_incomplete_returns_one(self):
        self.assertEqual(_run_cli([INCOMPLETE, "--format", "report", "--require-complete"]), 1)

    def test_cli_full_returns_zero(self):
        self.assertEqual(_run_cli([FULL, "--format", "report", "--require-complete"]), 0)

    def test_cli_invalid_returns_two(self):
        self.assertEqual(_run_cli([os.path.join(HERE, "does-not-exist.json")]), 2)

    def test_cli_unknown_format_exits_two(self):
        with self.assertRaises(SystemExit) as ctx:
            _run_cli([FULL, "--format", "nope"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
