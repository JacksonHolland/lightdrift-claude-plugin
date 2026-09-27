"""Tests for dedup_assets.py. Standard library only, no network."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dedup_assets as d


def write_json(directory, name, obj):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle)
    return path


class NormalizeUrlTests(unittest.TestCase):
    def test_lowercases_scheme_and_host(self):
        self.assertEqual(
            d.normalize_url("HTTPS://CDN.Example.ORG/Photo.JPG"),
            "https://cdn.example.org/Photo.JPG",
        )

    def test_drops_default_port_and_keeps_other(self):
        self.assertEqual(d.normalize_url("http://x.example:80/a"), "http://x.example/a")
        self.assertEqual(d.normalize_url("https://x.example:443/a"), "https://x.example/a")
        self.assertEqual(d.normalize_url("https://x.example:8443/a"), "https://x.example:8443/a")

    def test_drops_fragment_and_tracking_params(self):
        self.assertEqual(
            d.normalize_url("https://x.example/p?utm_source=n&gclid=1&v=2#frag"),
            "https://x.example/p?v=2",
        )

    def test_sorts_query_and_strips_trailing_slash(self):
        self.assertEqual(
            d.normalize_url("https://x.example/p/?b=2&a=1"),
            "https://x.example/p?a=1&b=2",
        )

    def test_root_slash_preserved(self):
        self.assertEqual(d.normalize_url("https://x.example/"), "https://x.example/")

    def test_rejects_non_http_and_junk(self):
        for value in ["ftp://x.example/a", "not a url", "", "https://", None, 5]:
            self.assertIsNone(d.normalize_url(value))


class StrictJsonTests(unittest.TestCase):
    def test_rejects_duplicate_keys(self):
        with self.assertRaises(ValueError):
            d.strict_json('{"a": 1, "a": 2}')

    def test_rejects_non_finite(self):
        with self.assertRaises(ValueError):
            d.strict_json('{"a": NaN}')

    def test_accepts_plain_object(self):
        self.assertEqual(d.strict_json('{"a": [1, 2]}'), {"a": [1, 2]})


class IdentitySignalTests(unittest.TestCase):
    def test_reads_nested_rights_provenance(self):
        signals = d.identity_signals(
            {"asset_id": "x", "rights": {"provenance_url": "https://a.example/p?utm_source=z"}},
            "x",
        )
        self.assertEqual(signals["canonical_urls"], ["https://a.example/p"])

    def test_collects_top_level_and_nested_urls(self):
        signals = d.identity_signals(
            {
                "url": "https://a.example/p",
                "rights": {"provenance_url": "https://b.example/p"},
            },
            "x",
        )
        self.assertEqual(len(signals["canonical_urls"]), 2)

    def test_numeric_external_id_is_stringified(self):
        signals = d.identity_signals(
            {"asset_id": "x", "source": "S", "external_id": 7788}, "x"
        )
        self.assertEqual(
            signals["source_external_id"], {"source": "S", "value": "7788"}
        )

    def test_thumbnail_only_is_not_an_identity_signal(self):
        signals = d.identity_signals(
            {"asset_id": "x", "thumbnail_url": "https://t.example/p"}, "x"
        )
        self.assertEqual(signals["canonical_urls"], [])
        self.assertIsNone(signals["source_external_id"])


class EnvelopeValidationTests(unittest.TestCase):
    def test_duplicate_asset_id_within_envelope_is_an_error(self):
        errors = []
        d._index_envelope({"results": [{"asset_id": "a"}, {"asset_id": "a"}]}, 1, errors)
        self.assertTrue(any("duplicate asset_id" in message for message in errors))

    def test_missing_asset_id_is_an_error(self):
        errors = []
        d._index_envelope({"results": [{"title": "no id"}]}, 1, errors)
        self.assertTrue(any("asset_id" in message for message in errors))

    def test_non_list_results_is_an_error(self):
        errors = []
        d._index_envelope({"results": {}}, 1, errors)
        self.assertTrue(any("results array" in message for message in errors))


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.first = write_json(cls.tmp, "first.json", json.loads(
            Path(Path(__file__).parent / "fixtures" / "search-response.json").read_text()
        ))
        cls.second = write_json(cls.tmp, "second.json", json.loads(
            Path(Path(__file__).parent / "fixtures" / "second-response.json").read_text()
        ))

    def test_counts(self):
        report = d.build_report([self.first, self.second])
        self.assertEqual(report["counts"]["assets"], 12)
        self.assertEqual(report["counts"]["clusters"], 3)
        self.assertEqual(report["counts"]["assets_in_clusters"], 7)
        self.assertEqual(report["counts"]["ungrouped"], 5)
        self.assertEqual(report["counts"]["assets_without_identity_signal"], 1)
        self.assertEqual(report["errors"], [])

    def test_canonical_url_cluster(self):
        report = d.build_report([self.first])
        url_cluster = [
            c for c in report["clusters"]
            if any(k["type"] == "canonical_url" for k in c["shared_keys"])
        ]
        self.assertTrue(url_cluster)

    def test_external_id_cluster(self):
        report = d.build_report([self.first])
        cluster = next(c for c in report["clusters"] if c["confidence"] == "source_external_id")
        ids = {m["asset_id"] for m in cluster["members"]}
        self.assertEqual(ids, {"fixture:ext-a", "fixture:ext-b"})

    def test_thumbnails_do_not_cluster(self):
        report = d.build_report([self.first])
        for cluster in report["clusters"]:
            ids = {m["asset_id"] for m in cluster["members"]}
            self.assertNotIn("fixture:thumb-a", ids)
            self.assertNotIn("fixture:thumb-b", ids)

    def test_shared_thumbnail_only_report_has_no_clusters(self):
        tmp = tempfile.mkdtemp()
        path = write_json(tmp, "thumbs.json", {
            "results": [
                {"asset_id": "a", "thumbnail_url": "https://t.example/same"},
                {"asset_id": "b", "thumbnail_url": "https://t.example/same"},
            ]
        })
        report = d.build_report([path])
        self.assertEqual(report["clusters"], [])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = write_json(self.tmp, "ok.json", {
            "results": [
                {"asset_id": "a", "provenance_url": "https://x.example/p?utm_source=1"},
                {"asset_id": "b", "provenance_url": "https://x.example/p"},
            ]
        })

    def test_success_exit_zero(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = d.main([self.path])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["counts"]["clusters"], 1)

    def test_optional_nonzero_on_duplicates(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = d.main([self.path, "--exit-nonzero-on-duplicates"])
        self.assertEqual(code, 1)

    def test_invalid_file_exit_two(self):
        err = io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = d.main([os.path.join(self.tmp, "missing.json")])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err.getvalue())

    def test_malformed_json_exit_two(self):
        bad = os.path.join(self.tmp, "bad.json")
        Path(bad).write_text("{not json")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = d.main([bad])
        self.assertEqual(code, 2)

    def test_no_duplicates_reports_zero(self):
        unique = write_json(self.tmp, "unique.json", {
            "results": [{"asset_id": "solo", "provenance_url": "https://solo.example/p"}]
        })
        out = io.StringIO()
        with redirect_stdout(out):
            code = d.main([unique])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["clusters"], [])


if __name__ == "__main__":
    unittest.main()
