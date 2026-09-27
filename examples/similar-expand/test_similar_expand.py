"""Tests for similar_expand.py. Standard library only, no network, no API key."""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import similar_expand as se  # noqa: E402

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"


class StrictJsonTests(unittest.TestCase):
    def test_rejects_duplicate_keys(self):
        with self.assertRaises(se.InputError):
            se.strict_json('{"a": 1, "a": 2}')

    def test_rejects_non_finite(self):
        with self.assertRaises(se.InputError):
            se.strict_json('{"a": Infinity}')

    def test_accepts_normal_json(self):
        self.assertEqual(se.strict_json('{"a": 1}'), {"a": 1})


class SeedExtractionTests(unittest.TestCase):
    def test_dedups_preserving_first_order(self):
        response = se.load_json(str(FIXTURES / "seed-response.json"))
        seeds = se.extract_seed_asset_ids(response, "fixture")
        self.assertEqual(seeds, ["isorepublic:17191", "stocksnap:BAVURMUHRD"])

    def test_rejects_missing_results(self):
        with self.assertRaises(se.InputError):
            se.extract_seed_asset_ids({"query_id": "x"}, "fixture")

    def test_rejects_result_without_asset_id(self):
        with self.assertRaises(se.InputError):
            se.extract_seed_asset_ids({"results": [{"title": "x"}]}, "fixture")


class PlanTests(unittest.TestCase):
    def test_planned_cost_and_skip(self):
        plan = se.plan_expansion(["a", "b", "c"], k=10, max_seeds=2)
        self.assertEqual(plan["seeds"], ["a", "b"])
        self.assertEqual(plan["planned_requests"], 2)
        self.assertEqual(plan["planned_credits"], 2)
        self.assertEqual(plan["seeds_skipped"], 1)
        self.assertFalse(plan["blocked"])

    def test_budget_blocks_plan(self):
        plan = se.plan_expansion(["a", "b"], k=5, max_seeds=5,
                                 budget_credits=1)
        self.assertTrue(plan["blocked"])

    def test_budget_boundary_is_inclusive(self):
        plan = se.plan_expansion(["a", "b"], k=5, max_seeds=5,
                                 budget_credits=2)
        self.assertFalse(plan["blocked"])

    def test_rejects_out_of_range_k(self):
        with self.assertRaises(se.InputError):
            se.plan_expansion(["a"], k=101, max_seeds=5)


class CreditTests(unittest.TestCase):
    def test_credit_rule(self):
        for k, want in [(1, 1), (10, 1), (11, 2), (50, 5), (100, 10)]:
            self.assertEqual(se.credits_per_request(k), want)

    def test_larger_k_costs_more_credits(self):
        plan = se.plan_expansion(["a", "b"], k=25, max_seeds=5)
        self.assertEqual(plan["planned_credits"], 6)

    def test_rejects_negative_budget(self):
        with self.assertRaises(se.InputError):
            se.plan_expansion(["a"], k=10, max_seeds=5, budget_credits=-1)


class MergeTests(unittest.TestCase):
    def test_merge_dedups_and_accumulates_found_by(self):
        a = se.load_json(str(FIXTURES / "similar-a.json"))
        b = se.load_json(str(FIXTURES / "similar-b.json"))
        request_log, shortlist = se.merge_expansions([a, b])
        self.assertEqual(len(request_log), 2)
        ids = [row["asset_id"] for row in shortlist]
        self.assertEqual(
            set(ids),
            {"stocksnap:BAVURMUHRD", "flickr:51141533761",
             "isorepublic:17191", "yfcc:9715466326"},
        )
        self.assertEqual(len(ids), len(set(ids)), "shortlist must be de-duplicated")
        flickr = next(r for r in shortlist if r["asset_id"] == "flickr:51141533761")
        self.assertEqual(flickr["found_by"],
                         ["isorepublic:17191", "stocksnap:BAVURMUHRD"])
        self.assertIn("rights", flickr)

    def test_merge_requires_seed(self):
        with self.assertRaises(se.InputError):
            se.merge_expansions([{"response": {"results": []}}])


class CliTests(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = se.main(argv)
        return code, out.getvalue()

    def test_dry_run_plan_from_saved_response(self):
        code, stdout = self._run(
            ["--seeds-from", str(FIXTURES / "seed-response.json"),
             "--budget-credits", "2"])
        self.assertEqual(code, 0)
        report = json.loads(stdout)
        self.assertEqual(report["mode"], "plan")
        self.assertEqual(report["planned_requests"], 2)
        self.assertEqual(report["planned_credits"], 2)
        self.assertEqual(report["credits_per_request"], 1)
        self.assertFalse(report["blocked"])
        self.assertEqual(report["shortlist_count"], 0)

    def test_budget_exceeded_exits_one_without_requests(self):
        code, stdout = self._run(
            ["--seed", "a", "--seed", "b", "--budget-credits", "1"])
        self.assertEqual(code, 1)
        report = json.loads(stdout)
        self.assertTrue(report["blocked"])
        self.assertEqual(report["aborted"], "budget_exceeded")
        self.assertEqual(report["requests"], [])

    def test_offline_merge_mode(self):
        code, stdout = self._run(
            ["--expansion", str(FIXTURES / "similar-a.json"),
             "--expansion", str(FIXTURES / "similar-b.json")])
        self.assertEqual(code, 0)
        report = json.loads(stdout)
        self.assertEqual(report["mode"], "merge")
        self.assertEqual(report["shortlist_count"], 4)
        self.assertEqual(report["planned_credits"], 0)

    def test_malformed_input_exits_two(self):
        code = None
        try:
            with redirect_stdout(io.StringIO()):
                code = se.main(["--expansion", str(FIXTURES / "malformed.json")])
        except se.InputError:
            code = 2
        self.assertEqual(code, 2)

    def test_live_without_key_is_an_input_error(self):
        saved = os.environ.pop("LIGHTDRIFT_API_KEY", None)
        try:
            with self.assertRaises(se.InputError):
                with redirect_stdout(io.StringIO()):
                    se.main(["--seed", "a", "--live"])
        finally:
            if saved is not None:
                os.environ["LIGHTDRIFT_API_KEY"] = saved


class AbortPolicyTests(unittest.TestCase):
    def test_abort_reasons(self):
        self.assertEqual(se._abort_reason(402), "credits_exhausted")
        self.assertEqual(se._abort_reason(403), "paid_feature")
        self.assertEqual(se._abort_reason(429), "rate_limited")
        self.assertEqual(se._abort_reason(503), "provider_unavailable")
        self.assertIsNone(se._abort_reason(404))
        self.assertIsNone(se._abort_reason(422))

    def test_upgrade_url_is_extracted(self):
        body = json.dumps({"detail": {"error": "paid_feature", "feature": "similar_search",
                                      "upgrade_url": "https://lightdrift.ai/dashboard/billing"}})
        self.assertEqual(se._upgrade_url(body), "https://lightdrift.ai/dashboard/billing")
        self.assertIsNone(se._upgrade_url("not json"))
        self.assertIsNone(se._upgrade_url(json.dumps({"detail": "rate limited"})))

    def test_idempotency_key_is_stable_and_seed_specific(self):
        self.assertEqual(se._idempotency_key("a", 5), se._idempotency_key("a", 5))
        self.assertNotEqual(se._idempotency_key("a", 5), se._idempotency_key("b", 5))
        self.assertNotEqual(se._idempotency_key("a", 5), se._idempotency_key("a", 6))


if __name__ == "__main__":
    unittest.main()
