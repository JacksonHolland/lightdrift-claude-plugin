#!/usr/bin/env python3
"""Local tests for pilot_acceptance.py. No network, no paid calls."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pilot_acceptance as pa  # noqa: E402

FIX = HERE / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _loadl(name):
    return [
        json.loads(line)
        for line in (FIX / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write(directory, name, payload):
    path = directory / name
    if name.endswith(".jsonl"):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in payload), encoding="utf-8"
        )
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.briefs = _write(self.dir, "briefs.json", _load("briefs-20.json"))
        self.requests = _write(self.dir, "requests.jsonl", _loadl("requests.jsonl"))
        self.candidates = _write(
            self.dir, "candidates.jsonl", _loadl("candidates.jsonl")
        )
        self.shortlist = _write(self.dir, "shortlist.json", _load("shortlist.json"))

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, buyer=None):
        argv = [
            "--briefs", str(self.briefs),
            "--requests", str(self.requests),
            "--candidates", str(self.candidates),
            "--shortlist", str(self.shortlist),
        ]
        if buyer:
            argv += ["--buyer", str(buyer)]
        return pa.build_record(pa.argparse.Namespace(
            briefs=self.briefs,
            requests=self.requests,
            candidates=self.candidates,
            shortlist=self.shortlist,
            buyer=Path(buyer) if buyer else None,
            expected_count=20,
        ))

    def _status(self, record, ident):
        return next(c["status"] for c in record["criteria"] if c["id"] == ident)

    def test_structural_criteria_pass_on_real_fixtures(self):
        record = self._run()
        for ident in ("A1", "A2", "A3", "A4"):
            self.assertEqual(self._status(record, ident), pa.PASS, ident)

    def test_buyer_criteria_unchecked_without_answers(self):
        record = self._run()
        for ident in ("A5", "A6", "A7"):
            self.assertEqual(self._status(record, ident), pa.UNCHECKED, ident)
        self.assertEqual(record["verdict"], "incomplete")
        self.assertEqual(record["summary"]["checked"], 4)

    def test_accepted_when_buyer_answers_pass(self):
        buyer = _write(self.dir, "buyer.json", {
            "usable_briefs": 17,
            "attribution_survives": True,
            "handoff_run": True,
        })
        record = self._run(buyer=buyer)
        self.assertEqual(record["verdict"], "accepted")
        self.assertEqual(record["summary"]["pass"], 7)

    def test_a5_fails_when_buyer_reports_too_few(self):
        buyer = _write(self.dir, "buyer.json", {
            "usable_briefs": 12,
            "attribution_survives": True,
            "handoff_run": True,
        })
        record = self._run(buyer=buyer)
        self.assertEqual(self._status(record, "A5"), pa.FAIL)
        self.assertEqual(record["verdict"], "not_accepted")

    def test_a1_fails_on_count_mismatch(self):
        briefs = _load("briefs-20.json")
        briefs["briefs"] = briefs["briefs"][:19]
        self.briefs = _write(self.dir, "briefs.json", briefs)
        record = self._run()
        self.assertEqual(self._status(record, "A1"), pa.FAIL)

    def test_a1_fails_on_duplicate_brief_ids(self):
        briefs = _load("briefs-20.json")
        briefs["briefs"][1]["id"] = briefs["briefs"][0]["id"]
        self.briefs = _write(self.dir, "briefs.json", briefs)
        record = self._run()
        self.assertEqual(self._status(record, "A1"), pa.FAIL)

    def test_a2_fails_on_missing_request(self):
        reqs = _loadl("requests.jsonl")[:-1]
        self.requests = _write(self.dir, "requests.jsonl", reqs)
        record = self._run()
        self.assertEqual(self._status(record, "A2"), pa.FAIL)

    def test_a3_fails_when_brief_has_no_candidate_record(self):
        cands = _loadl("candidates.jsonl")[:-1]
        self.candidates = _write(self.dir, "candidates.jsonl", cands)
        record = self._run()
        self.assertEqual(self._status(record, "A3"), pa.FAIL)

    def test_a3_fails_when_result_loses_rights(self):
        cands = _loadl("candidates.jsonl")
        del cands[0]["response"]["results"][0]["rights"]
        self.candidates = _write(self.dir, "candidates.jsonl", cands)
        record = self._run()
        self.assertEqual(self._status(record, "A3"), pa.FAIL)

    def test_a3_accepts_zero_result_briefs(self):
        cands = _loadl("candidates.jsonl")
        cands[0]["response"]["results"] = []
        self.candidates = _write(self.dir, "candidates.jsonl", cands)
        record = self._run()
        self.assertEqual(self._status(record, "A3"), pa.PASS)
        self.assertIn("S01", record["criteria"][2]["evidence"][0]["empty_result_briefs"])

    def test_a4_fails_when_rights_field_absent(self):
        shortlist = _load("shortlist.json")
        del shortlist["results"][0]["rights"]["basis"]
        self.shortlist = _write(self.dir, "shortlist.json", shortlist)
        record = self._run()
        self.assertEqual(self._status(record, "A4"), pa.FAIL)

    def test_a4_fails_on_bad_review_status(self):
        shortlist = _load("shortlist.json")
        shortlist["results"][0]["review_status"] = "looks_fine"
        self.shortlist = _write(self.dir, "shortlist.json", shortlist)
        record = self._run()
        self.assertEqual(self._status(record, "A4"), pa.FAIL)


class ExitCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.base = [
            "--briefs", str(_write(self.dir, "b.json", _load("briefs-20.json"))),
            "--requests", str(_write(self.dir, "r.jsonl", _loadl("requests.jsonl"))),
            "--candidates", str(_write(self.dir, "c.jsonl", _loadl("candidates.jsonl"))),
            "--shortlist", str(_write(self.dir, "s.json", _load("shortlist.json"))),
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_exit_3_incomplete(self):
        self.assertEqual(pa.main(self.base), 3)

    def test_exit_0_accepted(self):
        buyer = _write(self.dir, "buyer.json", {
            "usable_briefs": 20, "attribution_survives": True, "handoff_run": True,
        })
        self.assertEqual(pa.main(self.base + ["--buyer", str(buyer)]), 0)

    def test_exit_1_failure(self):
        self.base[1] = str(_write(self.dir, "bad.json", {"briefs": []}))
        self.assertEqual(pa.main(self.base), 1)

    def test_exit_2_malformed(self):
        bad = self.dir / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        argv = copy.deepcopy(self.base)
        argv[0] = "--briefs"
        argv[1] = str(bad)
        self.assertEqual(pa.main(argv), 2)

    def test_writes_record_and_markdown(self):
        rec = self.dir / "rec.json"
        md = self.dir / "rec.md"
        code = pa.main(self.base + ["--record", str(rec), "--markdown", str(md)])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(rec.read_text())["verdict"], "incomplete")
        self.assertIn("Overall verdict", md.read_text())


if __name__ == "__main__":
    unittest.main()
