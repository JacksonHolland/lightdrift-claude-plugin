#!/usr/bin/env python3
"""Tests for shortlist_export.py (standard library only)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shortlist_export as s  # noqa: E402

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


class ParseTests(unittest.TestCase):
    def test_loads_results(self):
        data = s.load_results(FIX / "clean.json")
        self.assertEqual(data["query_id"], "q_clean")
        self.assertEqual(len(data["results"]), 1)

    def test_missing_results_raises(self):
        with self.assertRaises(s.InputError):
            s.load_results(FIX / "bad.json")

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(s.InputError):
                s.load_results(p)


class ReviewStatusTests(unittest.TestCase):
    def test_ready_when_license_and_attribution_present(self):
        self.assertEqual(s.review_status({"license": "CC BY", "attribution_required": True, "attribution": "A"}), s._REVIEW_READY)

    def test_attribution_missing(self):
        self.assertEqual(s.review_status({"license": "CC BY", "attribution_required": True, "attribution": None}), s._REVIEW_ATTRIBUTION)

    def test_rights_missing(self):
        self.assertEqual(s.review_status({}), s._REVIEW_RIGHTS)
        self.assertEqual(s.review_status(None), s._REVIEW_RIGHTS)
        self.assertEqual(s.review_status({"commercial": True}), s._REVIEW_RIGHTS)


class BuildTests(unittest.TestCase):
    def test_clean_csv_has_header_and_row(self):
        csv_text, rows = s.build_shortlist(s.load_results(FIX / "clean.json"))
        header = csv_text.splitlines()[0]
        self.assertEqual(header.split(",")[:3], ["row_index", "asset_id", "score"])
        self.assertIn("ready_for_editorial_review", csv_text)
        self.assertEqual(len(rows), 1)

    def test_partial_flags_and_preserves_unknown_rights_field(self):
        _, rows = s.build_shortlist(s.load_results(FIX / "partial.json"))
        statuses = [r["review_status"] for r in rows]
        self.assertEqual(statuses, ["needs_rights_review", "needs_attribution_review"])
        self.assertEqual(rows[0]["rights"]["future_field"], "keep-me")

    def test_empty_results(self):
        csv_text, rows = s.build_shortlist(s.load_results(FIX / "empty.json"))
        self.assertEqual(len(rows), 0)
        self.assertEqual(len(csv_text.splitlines()), 1)

    def test_bool_cells_lowercase(self):
        csv_text, _ = s.build_shortlist(s.load_results(FIX / "clean.json"))
        self.assertIn("true", csv_text)
        self.assertNotIn("True", csv_text)


class CliTests(unittest.TestCase):
    def _run(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = s.main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()

    def test_exit_zero_clean(self):
        code, out, _ = self._run(FIX / "clean.json", "--quiet")
        self.assertEqual(code, 0)
        self.assertIn("asset_id", out)

    def test_strict_exit_one(self):
        code, _, _ = self._run(FIX / "partial.json", "--strict", "--quiet")
        self.assertEqual(code, 1)

    def test_exit_two_bad_input(self):
        code, _, err = self._run(FIX / "bad.json", "--quiet")
        self.assertEqual(code, 2)
        self.assertIn("results", err)

    def test_writes_both_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "shortlist"
            code, _, _ = self._run(FIX / "clean.json", "--output", base, "--quiet")
            self.assertEqual(code, 0)
            self.assertTrue(base.with_suffix(".csv").is_file())
            payload = json.loads(base.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(payload["query_id"], "q_clean")
            self.assertEqual(payload["results"][0]["asset_id"], "a1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
