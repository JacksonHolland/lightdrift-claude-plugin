#!/usr/bin/env python3
"""Convert a saved Lightdrift search response into a JSON Feed or RSS feed.

Turns a saved ``/v1/search`` (or ``/v1/similar``) response body into a JSON
Feed 1.1 document or an RSS 2.0 channel, so a content pipeline, newsletter or
monitor can consume the same result set as a standard feed. Offline, standard
library only, no network, no key, no search credit.

The converter copies only source-declared values. It omits fields it cannot
honestly fill and reports what it omitted; it never invents a creation date,
file size, creator or license. A tracked ``file`` URL is a real Lightdrift URL
that redirects (302) to a short-lived signed link; prefer the source
``provenance_url`` where present.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

JSONFEED_VERSION = "https://jsonfeed.org/version/1.1"
MEDIA_NS = "http://search.yahoo.com/mrss/"
MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".avif": "image/avif",
}


def load_response(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc.msg})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a JSON object")
    results = data.get("results")
    if not isinstance(results, list):
        raise ValueError(f"{path}: 'results' must be an array")
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: results[{index}] must be an object")
    return data


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _is_absolute_url(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _mime_type(url: Any) -> str | None:
    if not isinstance(url, str):
        return None
    path = url.split("?", 1)[0].split("#", 1)[0]
    dot = path.rfind(".")
    if dot == -1:
        return None
    return MIME_BY_SUFFIX.get(path[dot:].lower())


def describe_item(result: dict[str, Any], index: int, query_id: str | None) -> dict[str, Any]:
    rights = result.get("rights")
    rights = rights if isinstance(rights, dict) else {}
    warnings: list[str] = []

    asset_id = _text(result.get("asset_id"))
    if asset_id:
        item_id = asset_id
    elif query_id:
        item_id = f"{query_id}#{index + 1}"
        warnings.append("no asset_id: falling back to query_id and rank for a stable item id")
    else:
        item_id = f"result-{index + 1}"
        warnings.append("no asset_id or query_id: falling back to the result position for a stable item id")

    title = _text(result.get("title"))
    if not title:
        warnings.append("no title: the feed item has no title")

    file_url = result.get("file")
    file_url = file_url if _is_absolute_url(file_url) else None
    if file_url is None:
        warnings.append("file is not an absolute URL: the item has no image attachment")

    provenance_url = rights.get("provenance_url")
    provenance_url = provenance_url if _is_absolute_url(provenance_url) else None
    if rights.get("provenance_url") is not None and provenance_url is None:
        warnings.append("rights.provenance_url is not an absolute URL: it is omitted")

    item_url = provenance_url or file_url
    if item_url is None:
        warnings.append("no absolute provenance or file URL: the feed item has no link")
    elif provenance_url is None:
        warnings.append("no provenance_url: the item link is a Lightdrift tracked URL that redirects")

    license_value = rights.get("license")
    if license_value is not None and not isinstance(license_value, str):
        warnings.append("rights.license is not a string: it is omitted")

    attribution = _text(rights.get("attribution"))
    if rights.get("attribution_required") is True and not attribution:
        warnings.append("attribution_required is true but no attribution text is present")

    width = _int_or_none(result.get("width"))
    height = _int_or_none(result.get("height"))
    if width is None or height is None:
        warnings.append("missing width and/or height: the item carries no intrinsic size")

    extension: dict[str, Any] = {}
    for key, value in (
        ("query_id", query_id),
        ("rank", index + 1),
        ("score", result.get("score") if isinstance(result.get("score"), (int, float)) and not isinstance(result.get("score"), bool) else None),
        ("source", _text(result.get("source"))),
        ("width", width),
        ("height", height),
        ("content_url", file_url),
        ("thumbnail_url", result.get("thumb") if _is_absolute_url(result.get("thumb")) else None),
        ("provenance_url", provenance_url),
        ("license", license_value if isinstance(license_value, str) else None),
        ("license_verbatim", _text(rights.get("license_verbatim"))),
        ("attribution", attribution),
        ("attribution_required", rights.get("attribution_required") if isinstance(rights.get("attribution_required"), bool) else None),
        ("commercial", rights.get("commercial") if isinstance(rights.get("commercial"), bool) else None),
        ("derivatives", rights.get("derivatives") if isinstance(rights.get("derivatives"), bool) else None),
        ("share_alike", rights.get("share_alike") if isinstance(rights.get("share_alike"), bool) else None),
        ("basis", _text(rights.get("basis"))),
    ):
        if value is not None:
            extension[key] = value

    return {
        "id": item_id,
        "title": title,
        "url": item_url,
        "image": file_url,
        "thumbnail_url": result.get("thumb") if _is_absolute_url(result.get("thumb")) else None,
        "mime_type": _mime_type(file_url),
        "extension": extension,
        "warnings": warnings,
    }


def build_jsonfeed(response: dict[str, Any], meta: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    query_id = _text(response.get("query_id"))
    feed: dict[str, Any] = {"version": JSONFEED_VERSION, "title": meta["title"], "items": []}
    warnings: list[str] = []
    if meta.get("home_url"):
        feed["home_page_url"] = meta["home_url"]
    else:
        warnings.append("no home_page_url provided")
    if meta.get("feed_url"):
        feed["feed_url"] = meta["feed_url"]
    if meta.get("description"):
        feed["description"] = meta["description"]
    if not response.get("results"):
        warnings.append("the response contains no results: the feed has no items")
    for index, result in enumerate(response["results"]):
        item = describe_item(result, index, query_id)
        warnings.extend(f"item {item['id']}: {warning}" for warning in item["warnings"])
        entry: dict[str, Any] = {"id": item["id"]}
        if item["url"]:
            entry["url"] = item["url"]
        if item["title"]:
            entry["title"] = item["title"]
        if item["image"]:
            entry["image"] = item["image"]
            attachment: dict[str, Any] = {"url": item["image"]}
            if item["mime_type"]:
                attachment["mime_type"] = item["mime_type"]
            entry["attachments"] = [attachment]
        if item["extension"]:
            entry["_lightdrift"] = item["extension"]
        feed["items"].append(entry)
    return feed, warnings


def build_rss(response: dict[str, Any], meta: dict[str, Any]) -> tuple[ET.Element, list[str]]:
    ET.register_namespace("media", MEDIA_NS)
    query_id = _text(response.get("query_id"))
    warnings: list[str] = []
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = meta["title"]
    if meta.get("home_url"):
        ET.SubElement(channel, "link").text = meta["home_url"]
    else:
        warnings.append("no home_page_url provided: the channel has no link")
    ET.SubElement(channel, "description").text = meta.get("description") or meta["title"]
    if not response.get("results"):
        warnings.append("the response contains no results: the channel has no items")
    for index, result in enumerate(response["results"]):
        item = describe_item(result, index, query_id)
        warnings.extend(f"item {item['id']}: {warning}" for warning in item["warnings"])
        node = ET.SubElement(channel, "item")
        if item["title"]:
            ET.SubElement(node, "title").text = item["title"]
        if item["url"]:
            ET.SubElement(node, "link").text = item["url"]
        ET.SubElement(node, "guid", {"isPermaLink": "false"}).text = item["id"]
        credit = item["extension"].get("attribution")
        license_id = item["extension"].get("license")
        description = " ".join(part for part in (item["title"], credit, license_id) if part)
        if description:
            ET.SubElement(node, "description").text = description
        if item["image"]:
            media: dict[str, str] = {"url": item["image"]}
            if item["mime_type"]:
                media["type"] = item["mime_type"]
            if item["extension"].get("width") is not None:
                media["width"] = str(item["extension"]["width"])
            if item["extension"].get("height") is not None:
                media["height"] = str(item["extension"]["height"])
            ET.SubElement(node, f"{{{MEDIA_NS}}}content", media)
            if item["image"] != item["thumbnail_url"] and item["thumbnail_url"]:
                ET.SubElement(node, f"{{{MEDIA_NS}}}thumbnail", {"url": item["thumbnail_url"]})
    return rss, warnings


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a saved Lightdrift search response into a JSON Feed or RSS feed offline.")
    parser.add_argument("response", help="path to a saved search response JSON file")
    parser.add_argument("--format", choices=["jsonfeed", "rss"], default="jsonfeed")
    parser.add_argument("--title", default="Lightdrift image search results")
    parser.add_argument("--home-url", dest="home_url")
    parser.add_argument("--feed-url", dest="feed_url")
    parser.add_argument("--description")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON Feed output")
    parser.add_argument("--require-complete", action="store_true", help="exit 1 if any field had to be omitted")
    parser.add_argument("--report", help="write a JSON review report with the warnings to this path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        response = load_response(args.response)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2
    meta = {
        "title": args.title,
        "home_url": args.home_url,
        "feed_url": args.feed_url,
        "description": args.description,
    }
    if args.format == "jsonfeed":
        document, warnings = build_jsonfeed(response, meta)
        print(json.dumps(document, indent=2 if args.pretty else None, ensure_ascii=False))
    else:
        rss, warnings = build_rss(response, meta)
        print(ET.tostring(rss, encoding="unicode", xml_declaration=True))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump({"format": args.format, "items": len(response["results"]), "warnings": warnings}, handle, indent=2)
            handle.write("\n")
    if warnings:
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        if args.require_complete:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
