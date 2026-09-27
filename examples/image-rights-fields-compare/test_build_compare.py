#!/usr/bin/env python3
"""Tests for compare_rights.py. Standard library only; no network."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

import compare_rights as cr

HERE = os.path.dirname(os.path.abspath(__file__))


def minimal_dataset():
    return {
        "dimensions": [
            {"id": "license_identifier", "label": "License identifier per result"},
            {"id": "provenance_url", "label": "Provenance / source landing URL"},
        ],
        "providers": [
            {
                "id": "alpha",
                "name": "Alpha",
                "fields": {
                    "license_identifier": {
                        "exposed": True,
                        "field": "license",
                        "source_url": "https://example.test/alpha",
                        "capture": "sources/alpha.html",
                        "quote": "license - the license",
                    },
                    "provenance_url": {
                        "exposed": False,
                        "field": None,
                        "source_url": "https://example.test/alpha",
                        "capture": "sources/alpha.html",
                        "quote": "page - the page",
                        "basis": "no provenance field",
                    },
                },
                "primary_sources": [{"url": "https://example.test/alpha", "capture": "sources/alpha.html"}],
            },
            {
                "id": "beta",
                "name": "Beta",
                "fields": {
                    "license_identifier": {
                        "exposed": False,
                        "field": None,
                        "source_url": "https://example.test/beta",
                        "capture": "sources/beta.html",
                        "quote": "id - identifier only",
                        "basis": "no license field",
                    },
                    "provenance_url": {
                        "exposed": True,
                        "field": "pageURL",
                        "source_url": "https://example.test/beta",
                        "capture": "sources/beta.html",
                        "quote": "pageURL - source page",
                    },
                },
                "primary_sources": [{"url": "https://example.test/beta", "capture": "sources/beta.html"}],
            },
        ],
    }


class LoadTests(unittest.TestCase):
    def test_default_dataset_loads_and_validates(self):
        data = cr.load_dataset(cr.DEFAULT_DATASET)
        cr.validate_dataset(data)
        self.assertGreaterEqual(len(data["providers"]), 4)
        self.assertEqual(len(data["dimensions"]), 9)

    def test_missing_file_raises(self):
        with self.assertRaises(cr.DatasetError):
            cr.load_dataset(os.path.join(HERE, "does-not-exist.json"))

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{not json")
            with self.assertRaises(cr.DatasetError):
                cr.load_dataset(path)


class ValidateTests(unittest.TestCase):
    def test_minimal_is_valid(self):
        cr.validate_dataset(minimal_dataset())

    def test_missing_dimensions_rejected(self):
        data = minimal_dataset()
        data["dimensions"] = []
        with self.assertRaises(cr.DatasetError):
            cr.validate_dataset(data)

    def test_missing_providers_rejected(self):
        data = minimal_dataset()
        data["providers"] = []
        with self.assertRaises(cr.DatasetError):
            cr.validate_dataset(data)

    def test_provider_missing_dimension_rejected(self):
        data = minimal_dataset()
        del data["providers"][0]["fields"]["provenance_url"]
        with self.assertRaises(cr.DatasetError):
            cr.validate_dataset(data)

    def test_duplicate_dimension_rejected(self):
        data = minimal_dataset()
        data["dimensions"].append(dict(data["dimensions"][0]))
        with self.assertRaises(cr.DatasetError):
            cr.validate_dataset(data)

    def test_duplicate_provider_rejected(self):
        data = minimal_dataset()
        data["providers"].append(dict(data["providers"][0]))
        with self.assertRaises(cr.DatasetError):
            cr.validate_dataset(data)

    def test_exposed_without_field_rejected(self):
        data = minimal_dataset()
        data["providers"][0]["fields"]["license_identifier"]["field"] = None
        with self.assertRaises(cr.DatasetError):
            cr.validate_dataset(data)

    def test_non_boolean_exposed_rejected(self):
        data = minimal_dataset()
        data["providers"][0]["fields"]["license_identifier"]["exposed"] = "yes"
        with self.assertRaises(cr.DatasetError):
            cr.validate_dataset(data)

    def test_claim_not_object_rejected(self):
        data = minimal_dataset()
        data["providers"][0]["fields"]["license_identifier"] = "license"
        with self.assertRaises(cr.DatasetError):
            cr.validate_dataset(data)


class SourceGapTests(unittest.TestCase):
    def test_valid_sources_have_no_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sources"))
            for name in ("alpha.html", "beta.html"):
                with open(os.path.join(tmp, "sources", name), "w", encoding="utf-8") as handle:
                    handle.write("x")
            self.assertEqual(cr.source_gaps(minimal_dataset(), tmp), [])

    def test_missing_capture_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sources"))
            problems = cr.source_gaps(minimal_dataset(), tmp)
            self.assertTrue(any("capture not found" in p for p in problems))

    def test_missing_quote_is_reported(self):
        data = minimal_dataset()
        del data["providers"][0]["fields"]["license_identifier"]["quote"]
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sources"))
            for name in ("alpha.html", "beta.html"):
                with open(os.path.join(tmp, "sources", name), "w", encoding="utf-8") as handle:
                    handle.write("x")
            problems = cr.source_gaps(data, tmp)
            self.assertTrue(any("missing verbatim quote" in p for p in problems))

    def test_missing_source_url_is_reported(self):
        data = minimal_dataset()
        del data["providers"][1]["fields"]["provenance_url"]["source_url"]
        problems = cr.source_gaps(data, HERE)
        self.assertTrue(any("missing source_url" in p for p in problems))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.data = cr.load_dataset(cr.DEFAULT_DATASET)

    def test_markdown_contains_providers_and_dimensions(self):
        out = cr.render_markdown(self.data)
        for provider in self.data["providers"]:
            self.assertIn(provider["name"], out)
        for dim in self.data["dimensions"]:
            self.assertIn(dim["label"], out)
        self.assertIn("rights.commercial", out)
        self.assertIn("foreign_landing_url", out)
        self.assertIn("not exposed", out)

    def test_html_escapes_field_values(self):
        data = minimal_dataset()
        data["providers"][0]["fields"]["license_identifier"]["field"] = "<script>alert(1)</script>"
        out = cr.render_html(data)
        self.assertNotIn("<script>alert(1)</script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_html_flags_absent_cells(self):
        out = cr.render_html(minimal_dataset())
        self.assertIn("not exposed", out)
        self.assertIn("alpha", out.lower())

    def test_json_round_trips(self):
        out = cr.render_json(self.data)
        self.assertEqual(json.loads(out)["providers"][0]["id"], "lightdrift")

    def test_matrix_lists_every_dimension(self):
        out = cr.render_matrix(self.data)
        for dim in self.data["dimensions"]:
            self.assertIn(dim["label"], out)

    def test_render_is_deterministic(self):
        self.assertEqual(cr.render_markdown(self.data), cr.render_markdown(self.data))

    def test_all_formats_nonempty(self):
        for name, renderer in cr.RENDERERS.items():
            self.assertTrue(renderer(self.data).strip(), name)


class CliTests(unittest.TestCase):
    def _write_dataset(self, tmp, data):
        os.makedirs(os.path.join(tmp, "sources"))
        for name in ("alpha.html", "beta.html"):
            with open(os.path.join(tmp, "sources", name), "w", encoding="utf-8") as handle:
                handle.write("x")
        path = os.path.join(tmp, "providers.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def test_cli_valid_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_dataset(tmp, minimal_dataset())
            self.assertEqual(cr.main(["--dataset", path, "--format", "matrix"]), 0)

    def test_cli_require_sources_missing_capture_returns_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = minimal_dataset()
            path = self._write_dataset(tmp, data)
            os.remove(os.path.join(tmp, "sources", "beta.html"))
            self.assertEqual(cr.main(["--dataset", path, "--require-sources"]), 1)

    def test_cli_invalid_dataset_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[1, 2, 3]")
            self.assertEqual(cr.main(["--dataset", path]), 2)

    def test_cli_writes_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_dataset(tmp, minimal_dataset())
            out = os.path.join(tmp, "out.md")
            self.assertEqual(cr.main(["--dataset", path, "--output", out]), 0)
            with open(out, encoding="utf-8") as handle:
                self.assertIn("# Image API rights fields", handle.read())


if __name__ == "__main__":
    unittest.main()
