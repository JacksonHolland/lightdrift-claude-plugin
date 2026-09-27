"""Offline tests for rights_compat. No network calls, no real product data."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import rights_compat as rc

HERE = Path(__file__).resolve().parent
RESPONSE = HERE / "fixtures" / "search-response.json"
USE_COMMERCIAL = HERE / "fixtures" / "use-commercial-derivatives.json"
USE_EDITORIAL = HERE / "fixtures" / "use-editorial.json"


def run_main(*argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rc.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


def write_tmp(obj, suffix=".json"):
    handle = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    json.dump(obj, handle)
    handle.close()
    return Path(handle.name)


class UseProfileTests(unittest.TestCase):
    def test_loads_all_required_keys(self):
        use = rc.load_use_profile(USE_COMMERCIAL)
        self.assertEqual(set(use), set(rc._USE_KEYS))

    def test_missing_key_is_invalid(self):
        path = write_tmp({"commercial": True})
        with self.assertRaises(rc.InputError):
            rc.load_use_profile(path)

    def test_non_boolean_is_invalid(self):
        path = write_tmp({**{k: False for k in rc._USE_KEYS}, "commercial": "yes"})
        with self.assertRaises(rc.InputError):
            rc.load_use_profile(path)

    def test_non_object_is_invalid(self):
        path = write_tmp(["commercial"])
        with self.assertRaises(rc.InputError):
            rc.load_use_profile(path)


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.use = rc.load_use_profile(USE_COMMERCIAL)
        data = json.loads(RESPONSE.read_text(encoding="utf-8"))
        self.by_id = {
            a["asset_id"]: a
            for a in rc._extract_assets(data)
        }

    def decide(self, asset_id, use=None):
        return rc.evaluate_asset(self.by_id[asset_id], use or self.use)

    def test_cc0_commercial_is_ok(self):
        d = self.decide("fixture-cc0-0001")
        self.assertEqual(d["status"], rc.STATUS_OK)
        self.assertEqual(d["reason_codes"], [])

    def test_ccby_with_attribution(self):
        d = self.decide("fixture-ccby-0002")
        self.assertEqual(d["status"], rc.STATUS_ATTRIBUTION)
        self.assertTrue(d["attribution"])

    def test_noncommercial_blocks_commercial_use(self):
        d = self.decide("fixture-ccbync-0003")
        self.assertEqual(d["status"], rc.STATUS_BLOCKED)
        self.assertIn("license_declares_noncommercial", d["reason_codes"])

    def test_noderivatives_blocks_derivative_use(self):
        d = self.decide("fixture-ccbynd-0004")
        self.assertEqual(d["status"], rc.STATUS_BLOCKED)
        self.assertIn("license_forbids_derivatives", d["reason_codes"])

    def test_share_alike_requires_review_when_not_accepted(self):
        d = self.decide("fixture-ccbysa-0005")
        self.assertEqual(d["status"], rc.STATUS_REVIEW)
        self.assertIn("share_alike_obligation", d["reason_codes"])

    def test_share_alike_ok_when_accepted(self):
        use = rc.load_use_profile(USE_EDITORIAL)
        d = self.decide("fixture-ccbysa-0005", use)
        self.assertEqual(d["status"], rc.STATUS_ATTRIBUTION)

    def test_null_flags_are_unknown_not_permission(self):
        d = self.decide("fixture-unknown-flags-0006")
        self.assertEqual(d["status"], rc.STATUS_REVIEW)
        self.assertIn("commercial_permission_unknown", d["reason_codes"])
        self.assertIn("derivative_permission_unknown", d["reason_codes"])

    def test_required_attribution_missing_is_review(self):
        d = self.decide("fixture-missing-attribution-0007")
        self.assertEqual(d["status"], rc.STATUS_REVIEW)
        self.assertIn("attribution_required_but_missing", d["reason_codes"])

    def test_missing_rights_object_is_review(self):
        d = self.decide("fixture-no-rights-0008")
        self.assertEqual(d["status"], rc.STATUS_REVIEW)
        self.assertEqual(d["reason_codes"], ["rights_missing"])

    def test_missing_license_is_review(self):
        d = self.decide("fixture-no-license-0009")
        self.assertEqual(d["status"], rc.STATUS_REVIEW)
        self.assertIn("license_unknown", d["reason_codes"])

    def test_editorial_profile_permits_noncommercial(self):
        use = rc.load_use_profile(USE_EDITORIAL)
        self.assertNotEqual(
            self.decide("fixture-ccbync-0003", use)["status"], rc.STATUS_BLOCKED
        )


class ExtractTests(unittest.TestCase):
    def test_normalized_assets_envelope(self):
        assets = rc._extract_assets({"assets": [{"asset_id": "a", "rights": None}]})
        self.assertEqual([a["asset_id"] for a in assets], ["a"])

    def test_plain_list_envelope(self):
        assets = rc._extract_assets([{"asset_id": "a"}])
        self.assertEqual(len(assets), 1)

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(rc.InputError):
            rc._extract_assets({"results": [{"asset_id": "a"}, {"asset_id": "a"}]})

    def test_missing_id_rejected(self):
        with self.assertRaises(rc.InputError):
            rc._extract_assets({"results": [{"source": "x"}]})

    def test_empty_rejected(self):
        with self.assertRaises(rc.InputError):
            rc._extract_assets({"results": []})

    def test_non_object_rejected(self):
        with self.assertRaises(rc.InputError):
            rc._extract_assets({"results": ["nope"]})


class ReportTests(unittest.TestCase):
    def test_report_shape_and_determinism(self):
        data = json.loads(RESPONSE.read_text(encoding="utf-8"))
        use = rc.load_use_profile(USE_COMMERCIAL)
        first = rc.build_report(data, use)
        second = rc.build_report(data, use)
        self.assertEqual(first, second)
        self.assertEqual(first["rights_clearance"], "not_evaluated")
        self.assertEqual(
            first["summary"]["assets"],
            first["summary"]["ok"]
            + first["summary"]["ok_with_attribution"]
            + first["summary"]["review"]
            + first["summary"]["blocked"],
        )
        self.assertEqual(len(first["decisions"]), first["summary"]["assets"])

    def test_credits_only_include_clean_attribution_assets(self):
        data = json.loads(RESPONSE.read_text(encoding="utf-8"))
        report = rc.build_report(data, rc.load_use_profile(USE_COMMERCIAL))
        self.assertEqual(len(report["credit_lines"]), 1)
        self.assertIn("fixture-ccby-0002", report["credit_lines"][0])

    def test_markdown_render_has_key_sections(self):
        data = json.loads(RESPONSE.read_text(encoding="utf-8"))
        md = rc.render_markdown(rc.build_report(data, rc.load_use_profile(USE_COMMERCIAL)))
        for needle in ("# Image rights compatibility report", "## Summary", "## Credit block", "not_evaluated"):
            self.assertIn(needle, md)


class CliTests(unittest.TestCase):
    def test_json_run_exits_one_on_review_or_blocked(self):
        code, out, err = run_main(RESPONSE, USE_COMMERCIAL)
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        report = json.loads(out)
        self.assertGreater(report["summary"]["review"] + report["summary"]["blocked"], 0)

    def test_markdown_run(self):
        code, out, _ = run_main(RESPONSE, USE_COMMERCIAL, "--format", "markdown")
        self.assertEqual(code, 1)
        self.assertIn("# Image rights compatibility report", out)

    def test_output_file(self):
        target = Path(tempfile.mkdtemp()) / "report.json"
        code, out, _ = run_main(RESPONSE, USE_COMMERCIAL, "--output", target)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn('"rights_clearance"', target.read_text(encoding="utf-8"))

    def test_malformed_response_exits_two(self):
        bad = Path(tempfile.mkdtemp()) / "bad.json"
        bad.write_text("{ not json", encoding="utf-8")
        code, _, err = run_main(bad, USE_COMMERCIAL)
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)

    def test_missing_file_exits_two(self):
        code, _, err = run_main(HERE / "does-not-exist.json", USE_COMMERCIAL)
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)


if __name__ == "__main__":
    unittest.main()
