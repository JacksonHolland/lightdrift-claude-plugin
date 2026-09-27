"""Offline duplicate detection and canonicalization for saved image-search responses.

Finds results that probably describe the same underlying image under different
``asset_id`` values, using identity signals that travel with the response:
a canonicalized source/provenance URL or a source-native external id.

No network, no credentials, no writes. Python 3.10+, standard library only.

Exit codes
----------
0  Report written to stdout (duplicates or not).
2  Invalid input: unreadable file, malformed envelope, missing/empty asset_id,
   repeated asset_id inside one envelope, repeated JSON keys, non-finite number.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

# Strong identity signals only. Thumbnail/preview/download URLs are deliberately
# excluded: CDN placeholders are frequently shared between unrelated images, so
# using them would manufacture false duplicate clusters.
STRONG_URL_FIELDS = (
    "provenance_url",
    "source_url",
    "source_page_url",
    "page_url",
    "license_url",
    "url",
)
EXTERNAL_ID_FIELDS = (
    "source_asset_id",
    "external_id",
    "provider_id",
    "native_id",
    "asset_uid",
    "source_id",
)
NESTED_OBJECTS = ("rights", "source", "provenance")
TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "ref",
    "referrer",
    "source",
    "campaign",
}
TRACKING_PREFIXES = ("utm_",)
DEFAULT_PORTS = {"http": "80", "https": "443"}


def strict_json(raw):
    """Parse JSON, rejecting duplicate keys and non-finite numbers."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + str(key))
            result[key] = value
        return result

    def constant(value):
        raise ValueError("non-finite JSON number: " + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def normalize_url(raw):
    """Return a conservative canonical form of an http(s) URL, or None.

    Lowercases scheme/host, drops default ports and fragments, removes tracking
    query parameters, sorts the remaining query and strips a trailing slash.
    Path case and percent-encoding are preserved because they can be
    significant for object stores.
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    netloc = host
    port = parts.port
    if port is not None and str(port) != DEFAULT_PORTS[scheme]:
        netloc = "%s:%d" % (host, port)
    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not (key.lower().startswith(TRACKING_PREFIXES) or key.lower() in TRACKING_PARAMS)
    ]
    query = urlencode(sorted(kept))
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, query, ""))


def _first_url(container):
    if not isinstance(container, dict):
        return None
    for field in STRONG_URL_FIELDS:
        value = container.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _first_external_id(container):
    if not isinstance(container, dict):
        return None
    for field in EXTERNAL_ID_FIELDS:
        value = container.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def identity_signals(result, asset_id):
    """Extract canonical URL and external-id signals for one result."""
    urls = []
    top = _first_url(result)
    if top:
        urls.append(top)
    for key in NESTED_OBJECTS:
        nested = result.get(key)
        found = _first_url(nested)
        if found:
            urls.append(found)

    canonical_urls = []
    for candidate in urls:
        canonical = normalize_url(candidate)
        if canonical and canonical not in canonical_urls:
            canonical_urls.append(canonical)

    external = _first_external_id(result)
    source = result.get("source")
    source_name = source.strip() if isinstance(source, str) and source.strip() else None
    external_id = None
    if external:
        external_id = {"source": source_name, "value": external}
    return {
        "asset_id": asset_id,
        "canonical_urls": canonical_urls,
        "source_external_id": external_id,
    }


def _index_envelope(envelope, envelope_index, errors):
    if not isinstance(envelope, dict) or not isinstance(envelope.get("results"), list):
        errors.append("input %d: expected an object containing a results array" % envelope_index)
        return []
    seen = set()
    indexed = []
    for rank, row in enumerate(envelope["results"], 1):
        if not isinstance(row, dict):
            errors.append("input %d rank %d: each result must be an object" % (envelope_index, rank))
            continue
        asset_id = row.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            errors.append("input %d rank %d: missing nonempty string asset_id" % (envelope_index, rank))
            continue
        if asset_id in seen:
            errors.append("input %d: duplicate asset_id %s within one envelope" % (envelope_index, asset_id))
            continue
        seen.add(asset_id)
        signals = identity_signals(row, asset_id)
        indexed.append(
            {
                "asset_id": asset_id,
                "source": row.get("source") if isinstance(row.get("source"), str) else None,
                "envelope": envelope_index,
                "rank": rank,
                "signals": signals,
            }
        )
    return indexed


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def add(self, item):
        self.parent.setdefault(item, item)

    def find(self, item):
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def identity_keys(record):
    """Return the strong identity keys for one indexed record."""
    signals = record["signals"]
    keys = [("asset_id", record["asset_id"])]
    keys.extend(("canonical_url", url) for url in signals["canonical_urls"])
    ext = signals["source_external_id"]
    if ext:
        if ext["source"]:
            keys.append(("source_external_id", "%s:%s" % (ext["source"].lower(), ext["value"])))
        else:
            keys.append(("source_external_id", ext["value"]))
    return keys


def build_clusters(records):
    """Group records that share a strong identity key via connected components."""
    uf = _UnionFind()
    key_records = {}
    for index, record in enumerate(records):
        uf.add(record["asset_id"])
        for key in identity_keys(record):
            key_records.setdefault(key, []).append(index)

    for key, indexes in key_records.items():
        first = records[indexes[0]]["asset_id"]
        for index in indexes[1:]:
            uf.union(first, records[index]["asset_id"])

    components = {}
    for index, record in enumerate(records):
        components.setdefault(uf.find(record["asset_id"]), []).append(index)

    confidence_order = {"asset_id": 0, "source_external_id": 1, "canonical_url": 2}
    clusters = []
    for indexes in components.values():
        if len(indexes) < 2:
            continue
        member_indexes = set(indexes)
        shared_keys = []
        for key, owners in sorted(key_records.items()):
            if len(member_indexes & set(owners)) >= 2:
                shared_keys.append({"type": key[0], "value": key[1]})
        shared_keys.sort(key=lambda k: (confidence_order.get(k["type"], 9), k["value"]))
        confidence = shared_keys[0]["type"] if shared_keys else "unknown"
        clusters.append(
            {
                "confidence": confidence,
                "shared_keys": shared_keys,
                "members": [
                    {
                        "asset_id": records[index]["asset_id"],
                        "source": records[index]["source"],
                        "envelope": records[index]["envelope"],
                        "rank": records[index]["rank"],
                    }
                    for index in sorted(
                        indexes, key=lambda i: (records[i]["envelope"], records[i]["rank"])
                    )
                ],
            }
        )
    clusters.sort(key=lambda c: (-len(c["members"]), c["members"][0]["asset_id"]))
    for number, cluster in enumerate(clusters, 1):
        cluster["cluster_id"] = number
    return clusters, uf


def process(paths):
    errors = []
    inputs = []
    records = []
    for index, path in enumerate(paths, 1):
        try:
            raw = Path(path).read_bytes()
        except OSError as exc:
            errors.append("input %d: cannot read %s (%s)" % (index, path, exc))
            continue
        digest = hashlib.sha256(raw).hexdigest()
        try:
            envelope = strict_json(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            errors.append("input %d: invalid JSON: %s" % (index, exc))
            continue
        records.extend(_index_envelope(envelope, index, errors))
        result_count = len(envelope["results"]) if isinstance(envelope, dict) and isinstance(envelope.get("results"), list) else 0
        inputs.append({"path": str(path), "sha256": digest, "results": result_count})
    return inputs, records, errors


def build_report(paths):
    inputs, records, errors = process(paths)
    clusters, _ = build_clusters(records)
    in_clusters = sum(len(c["members"]) for c in clusters)
    no_signal = [
        r["asset_id"]
        for r in records
        if not r["signals"]["canonical_urls"] and not r["signals"]["source_external_id"]
    ]
    report = {
        "schema_version": 1,
        "generated_by": "dedup_assets.py",
        "inputs": inputs,
        "counts": {
            "inputs": len(inputs),
            "assets": len(records),
            "clusters": len(clusters),
            "assets_in_clusters": in_clusters,
            "ungrouped": len(records) - in_clusters,
            "assets_without_identity_signal": len(no_signal),
        },
        "signals_used": ["source_external_id", "canonical_url"],
        "signals_excluded": [
            "thumbnail_url",
            "preview_url",
            "download_url",
            "similarity/visual comparison",
        ],
        "assets_without_identity_signal": no_signal,
        "clusters": clusters,
        "errors": errors,
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="+", help="saved response JSON file(s) with a results array")
    parser.add_argument(
        "--exit-nonzero-on-duplicates",
        action="store_true",
        help="exit 1 when at least one duplicate cluster is found (for CI)",
    )
    args = parser.parse_args(argv)

    report = build_report(args.inputs)
    if report["errors"]:
        for message in report["errors"]:
            print("error: " + message, file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")
    if args.exit_nonzero_on_duplicates and report["clusters"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
