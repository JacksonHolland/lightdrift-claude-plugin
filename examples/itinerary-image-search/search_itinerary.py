#!/usr/bin/env python3
"""Search candidate stock images for three stops on an illustrative San Diego itinerary (Python 3.10+)."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

ENDPOINT = "https://api.lightdrift.ai/v1/search"
EXPERIMENT = "lig_itinerary_example_v1"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the API key to another endpoint.


def payload(topic, session):
    return {
        "query": topic,
        "k": 5,
        "filters": {"commercial": True, "orientation": "landscape"},
        "client_session": session,
        "experiment": EXPERIMENT,
    }


def main(argv=None, opener=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print request bodies; no network or key needed")
    args = parser.parse_args(argv)
    topics = [
        "Old Point Loma Lighthouse, Cabrillo National Monument, San Diego, exterior",
        "Balboa Park, San Diego, walking through gardens",
        "La Jolla Shores, San Diego, kayaking near the coast",
    ]
    key = os.environ.get("LIGHTDRIFT_API_KEY", "").strip()
    if not args.dry_run and not key:
        parser.error("Set LIGHTDRIFT_API_KEY in your environment")
    session = str(uuid.uuid4())
    opener = opener or urllib.request.build_opener(NoRedirect())
    for stop, topic in enumerate(topics, 1):
        body = payload(topic, session)
        if args.dry_run:
            print(json.dumps({"stop": stop, "method": "POST", "url": ENDPOINT, "body": body}))
            continue
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(body).encode(), method="POST",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
        )
        try:
            with opener.open(req, timeout=60) as response:
                data = json.load(response)
            if not isinstance(data, dict) or not isinstance(data.get("results"), list) or not isinstance(data.get("query_id"), str):
                raise ValueError("Unexpected response envelope")
        except urllib.error.HTTPError as exc:
            print(f"Stop {stop}: HTTP {exc.code}; stopped without retry. Check account balance, limits and API docs.", file=sys.stderr)
            return 1
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            print(f"Stop {stop}: transport or response error; outcome may be unknown. Check usage before rerunning; no automatic retry.", file=sys.stderr)
            return 1
        # Preserve the API envelope, including rights, query_id and any degraded flag.
        print(json.dumps({"stop": stop, "query": topic, "response": data}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
