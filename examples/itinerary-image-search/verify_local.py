"""Offline transport checks; synthetic responses are not product observations."""
import contextlib
import io
import json
import os
from pathlib import Path
import urllib.error
from unittest.mock import patch
import search_itinerary

class FakeTransport:
    def __init__(self, fail_at=None, status=429):
        self.status = status
        self.calls = []
        self.fail_at = fail_at
    def open(self, request, timeout):
        self.calls.append(request)
        if len(self.calls) == self.fail_at:
            raise urllib.error.HTTPError(request.full_url, self.status, "fixture", {}, None)
        return io.StringIO(json.dumps({"query_id": "synthetic-test-only", "results": [{"rights": {"basis": "synthetic fixture"}}], "degraded": "synthetic fixture"}))

def run(fake):
    out, err = io.StringIO(), io.StringIO()
    with patch.dict(os.environ, {"LIGHTDRIFT_API_KEY": "offline-fixture"}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = search_itinerary.main([], opener=fake)
    return code, [json.loads(x) for x in out.getvalue().splitlines()], err.getvalue()

ok = FakeTransport()
code, lines, err = run(ok)
assert code == 0 and len(lines) == len(ok.calls) == 3 and not err
assert all(x["response"]["results"][0]["rights"]["basis"] == "synthetic fixture" for x in lines)
assert all(x["response"]["degraded"] == "synthetic fixture" for x in lines)
bodies = [json.loads(r.data) for r in ok.calls]
assert len({b["client_session"] for b in bodies}) == 1
for r in ok.calls:
    assert r.full_url == search_itinerary.ENDPOINT and r.method == "POST"
    assert r.get_header("X-api-key") == "offline-fixture"
fail = FakeTransport(fail_at=2)
code, lines, err = run(fail)
assert code == 1 and len(fail.calls) == 2 and len(lines) == 1 and "429" in err
assert "offline-fixture" not in err
for status in [401, 402, 403, 429]:
    stopped = FakeTransport(fail_at=1, status=status)
    code, lines, err = run(stopped)
    assert code == 1 and len(stopped.calls) == 1 and not lines and str(status) in err
with patch.dict(os.environ, {"LIGHTDRIFT_API_KEY": ""}), contextlib.redirect_stdout(io.StringIO()) as output:
    unused = FakeTransport()
    assert search_itinerary.main(["--dry-run"], opener=unused) == 0
    assert len(output.getvalue().splitlines()) == 3 and not unused.calls
assert search_itinerary.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.org') is None
schema = json.load(open(Path(__file__).with_name('openapi.json')))
props = schema['components']['schemas']['SearchReq']['properties']
assert set(bodies[0]) <= set(props)
assert set(bodies[0]['filters']) <= set(schema['components']['schemas']['Filters']['properties'])
assert props['k']['minimum'] <= bodies[0]['k'] <= props['k']['maximum']
print('PASS: three sequential authenticated requests, documented request fields, shared session, preserved response/rights/degraded, 429 stop without retry; offline synthetic transport only.')
