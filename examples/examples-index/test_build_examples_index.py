#!/usr/bin/env python3
"""Tests for build_examples_index.py (standard library only)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_examples_index as b  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


class DiscoverTests(unittest.TestCase):
    def test_discovers_examples_and_titles(self):
        found = b.discover_examples(FIXTURES / "examples")
        keys = [e["key"] for e in found]
        self.assertEqual(keys, ["alpha-util", "beta-util"])
        self.assertEqual(found[0]["title"], "Alpha utility")
        self.assertEqual(found[0]["blurb"], "Alpha checks one thing.")
        self.assertEqual(found[0]["run"], "python3 alpha.py")

    def test_run_command_ignores_test_files(self):
        found = {e["key"]: e for e in b.discover_examples(FIXTURES / "examples")}
        self.assertEqual(found["beta-util"]["run"], "python3 beta.py")
        self.assertNotIn("test", found["beta-util"]["run"])

    def test_missing_dir_raises_input_error(self):
        with self.assertRaises(b.InputError):
            b.discover_examples(FIXTURES / "nope")

    def test_readme_without_heading_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "x"
            d.mkdir()
            (d / "README.md").write_text("no heading\n", encoding="utf-8")
            with self.assertRaises(b.InputError):
                b.discover_examples(Path(tmp))


class GuideCoverageTests(unittest.TestCase):
    def test_guide_linked_by_example_path_counts(self):
        mdx, report = b.build_index(
            FIXTURES / "examples", FIXTURES / "guides", "https://repo/examples"
        )
        by_key = {e["key"]: e["guide"] for e in report["examples"]}
        self.assertEqual(by_key["alpha-util"], "alpha-util")
        self.assertIsNone(by_key["beta-util"])

    def test_prose_mention_without_example_link_does_not_count(self):
        _, report = b.build_index(
            FIXTURES / "examples", FIXTURES / "guides", "https://repo/examples"
        )
        self.assertIn("beta-util", report["examples_without_guide"])
        self.assertEqual(report["examples_with_guide"], 1)
        self.assertEqual(report["examples_total"], 2)

    def test_mdx_links_examples_and_existing_guide(self):
        mdx, _ = b.build_index(
            FIXTURES / "examples", FIXTURES / "guides", "https://repo/examples"
        )
        self.assertIn("](https://repo/examples/alpha-util)", mdx)
        self.assertIn("](https://repo/examples/beta-util)", mdx)
        self.assertIn("[guide](/guides/alpha-util)", mdx)
        self.assertIn("| — |", mdx)

    def test_commit_pinned_example_link_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            guides = Path(tmp) / "guides"
            guides.mkdir()
            (guides / "g.mdx").write_text(
                "See https://github.com/x/y/tree/2ba60057785c6ae371df975c086064cb2b260cab/examples/alpha-util here.",
                encoding="utf-8",
            )
            _, report = b.build_index(
                FIXTURES / "examples", guides, "https://repo/examples"
            )
            by_key = {e["key"]: e["guide"] for e in report["examples"]}
            self.assertEqual(by_key["alpha-util"], "g")


class CliTests(unittest.TestCase):
    def _run(self, *args):
        with redirect_stderr(io.StringIO()):
            return b.main([str(a) for a in args])

    def test_exit_zero_when_no_strict(self):
        self.assertEqual(
            self._run(
                "--examples-dir", FIXTURES / "examples",
                "--guides-dir", FIXTURES / "guides",
                "--quiet",
            ),
            0,
        )

    def test_strict_exit_one_when_gap(self):
        self.assertEqual(
            self._run(
                "--examples-dir", FIXTURES / "examples",
                "--guides-dir", FIXTURES / "guides",
                "--strict", "--quiet",
            ),
            1,
        )

    def test_exit_two_on_bad_input(self):
        self.assertEqual(
            self._run(
                "--examples-dir", FIXTURES / "nope",
                "--guides-dir", FIXTURES / "guides",
                "--quiet",
            ),
            2,
        )

    def test_writes_output_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.mdx"
            rep = Path(tmp) / "rep.json"
            code = self._run(
                "--examples-dir", FIXTURES / "examples",
                "--guides-dir", FIXTURES / "guides",
                "--output", out, "--report", rep, "--quiet",
            )
            self.assertEqual(code, 0)
            self.assertIn("alpha-util", out.read_text(encoding="utf-8"))
            data = json.loads(rep.read_text(encoding="utf-8"))
            self.assertEqual(data["examples_total"], 2)
            self.assertEqual(data["examples_without_guide"], ["beta-util"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
