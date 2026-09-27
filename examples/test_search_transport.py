"""Offline HTTP parser regression checks; all wire data and credentials are synthetic."""
import contextlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent
ENVELOPE = {"query_id": "synthetic-only", "results": [{"rights": {"basis": "synthetic-only"}}], "degraded": "synthetic-only"}
BODY = json.dumps(ENVELOPE).encode()
VALID = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(BODY)).encode() + b"\r\n\r\n" + BODY

class WireSocket:
    def __init__(self, wire):
        self.wire = wire
    def makefile(self, mode):
        return io.BytesIO(self.wire)

class WireTransport:
    def __init__(self, wire=VALID, fail_at=2):
        self.wire, self.fail_at, self.calls = wire, fail_at, []
    def open(self, request, timeout):
        self.calls.append(request)
        response = http.client.HTTPResponse(WireSocket(self.wire if len(self.calls) == self.fail_at else VALID))
        response.begin()
        return response

def examples():
    for folder, script, args in [
        ("presentation-image-search", "search_slides", ["Wind turbines", "Solar panels", "City skyline"]),
        ("itinerary-image-search", "search_itinerary", []),
    ]:
        spec = importlib.util.spec_from_file_location(script, ROOT / folder / (script + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield script, module, args

class TransportTests(unittest.TestCase):
    def exercise(self, wire, expected=1, dry_run=False):
        for name, module, args in examples():
            with self.subTest(example=name):
                transport = WireTransport(wire)
                out, err = io.StringIO(), io.StringIO()
                with patch.dict(os.environ, {"LIGHTDRIFT_API_KEY": "synthetic-key-never-print"}), \
                     patch("socket.socket", side_effect=AssertionError("network forbidden")), \
                     contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = module.main(args + (["--dry-run"] if dry_run else []), opener=transport)
                self.assertEqual(code, expected)
                lines = [json.loads(line) for line in out.getvalue().splitlines()]
                self.assertEqual(len(transport.calls), 0 if dry_run else (2 if expected else 3))
                self.assertEqual(len(lines), 1 if expected else 3)
                if not dry_run:
                    self.assertTrue(all(line["response"] == ENVELOPE for line in lines))
                if expected:
                    self.assertIn("Check usage before rerunning", err.getvalue())
                    self.assertIn("no automatic retry", err.getvalue())
                else:
                    self.assertEqual(err.getvalue(), "")
                self.assertNotIn("synthetic-key-never-print", err.getvalue())
                self.assertNotIn("provider-private-marker", err.getvalue())
                self.assertNotIn("Traceback", err.getvalue())

    def test_truncated_content_length(self):
        self.exercise(b"HTTP/1.1 200 OK\r\nContent-Length: 9999\r\n\r\nprovider-private-marker")

    def test_truncated_chunk(self):
        self.exercise(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nFF\r\nprovider-private-marker")

    def test_invalid_status_line(self):
        self.exercise(b"provider-private-marker\r\n\r\n")

    def test_malformed_json(self):
        self.exercise(b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n{")

    def test_complete_response(self):
        self.exercise(VALID, expected=0)

    def test_dry_run(self):
        self.exercise(VALID, expected=0, dry_run=True)

if __name__ == "__main__":
    unittest.main(verbosity=2)
