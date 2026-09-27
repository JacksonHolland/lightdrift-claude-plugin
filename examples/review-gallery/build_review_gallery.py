#!/usr/bin/env python3
"""Build a self-contained HTML review gallery from a saved Lightdrift response.

Turns a saved ``/v1/search`` (or ``/v1/similar``) response body into a single
HTML page that a person can open offline to review candidates: one figure per
result with its thumbnail, declared credits and provenance link, plus missing-
metadata markers. Offline, standard library only, no network, no key.

The page embeds no external stylesheet, script, font or image tracker, and it
copies only source-declared values. It never invents a caption, creator,
license or source page. Rights are not evaluated here; review them separately.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from typing import Any
from urllib.parse import urlparse

STYLE = """\
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0 auto; max-width: 72rem; padding: 1.5rem; font: 16px/1.5 system-ui, sans-serif; }
header { border-bottom: 1px solid currentColor; padding-bottom: 1rem; margin-bottom: 1.5rem; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
.subtitle { opacity: .8; margin: 0 0 .5rem; }
.meta { font-size: .85rem; opacity: .7; margin: 0; }
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr)); gap: 1.25rem; }
figure { margin: 0; border: 1px solid color-mix(in srgb, currentColor 25%, transparent); border-radius: .5rem; overflow: hidden; }
figure img { display: block; width: 100%; height: auto; background: color-mix(in srgb, currentColor 10%, transparent); }
figcaption { padding: .75rem; font-size: .9rem; }
.caption { font-weight: 600; display: block; margin-bottom: .5rem; }
.credit { margin: .5rem 0 0; }
dl { display: grid; grid-template-columns: auto 1fr; gap: .15rem .5rem; margin: 0; font-size: .85rem; }
dt { opacity: .7; }
dd { margin: 0; overflow-wrap: anywhere; }
.missing { color: #b3261e; font-weight: 600; }
footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid currentColor; font-size: .85rem; opacity: .8; }
"""


class InputError(ValueError):
    pass


def load_response(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: not valid JSON ({exc.msg})") from exc
    if not isinstance(data, dict):
        raise InputError(f"{path}: top level must be a JSON object")
    results = data.get("results")
    if not isinstance(results, list):
        raise InputError(f"{path}: 'results' must be an array")
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise InputError(f"{path}: results[{index}] must be an object")
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


def describe(result: dict[str, Any], index: int, query_id: str | None) -> dict[str, Any]:
    rights = result.get("rights")
    rights = rights if isinstance(rights, dict) else {}
    missing: list[str] = []

    asset_id = _text(result.get("asset_id"))
    if asset_id:
        anchor = asset_id
    elif query_id:
        anchor = f"{query_id}#{index + 1}"
        missing.append("asset_id")
    else:
        anchor = f"result-{index + 1}"
        missing.append("asset_id")

    title = _text(result.get("title"))
    if not title:
        missing.append("title")

    thumb = result.get("thumb")
    image_url = thumb if _is_absolute_url(thumb) else None
    if image_url is None:
        file_url = result.get("file")
        image_url = file_url if _is_absolute_url(file_url) else None
    if image_url is None:
        missing.append("image")

    provenance_url = rights.get("provenance_url")
    provenance_url = provenance_url if _is_absolute_url(provenance_url) else None
    if provenance_url is None:
        missing.append("provenance_url")

    license_value = _text(rights.get("license"))
    license_verbatim = _text(rights.get("license_verbatim"))
    if not license_value and not license_verbatim:
        missing.append("license")

    attribution = _text(rights.get("attribution"))
    if not attribution:
        missing.append("attribution")

    width = _int_or_none(result.get("width"))
    height = _int_or_none(result.get("height"))
    if width is None or height is None:
        missing.append("dimensions")

    return {
        "anchor": anchor,
        "rank": index + 1,
        "title": title,
        "image_url": image_url,
        "provenance_url": provenance_url,
        "license": license_value,
        "license_verbatim": license_verbatim,
        "attribution": attribution,
        "attribution_required": rights.get("attribution_required") if isinstance(rights.get("attribution_required"), bool) else None,
        "source": _text(result.get("source")),
        "width": width,
        "height": height,
        "score": result.get("score") if isinstance(result.get("score"), (int, float)) and not isinstance(result.get("score"), bool) else None,
        "missing": missing,
    }


def _credit_line(item: dict[str, Any]) -> str:
    parts = [item["attribution"], item["license_verbatim"] or item["license"]]
    return " / ".join(part for part in parts if part)


def render(response: dict[str, Any], meta: dict[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    query_id = _text(response.get("query_id"))
    results = response["results"]
    items = [describe(result, index, query_id) for index, result in enumerate(results)]
    warnings: list[str] = []
    if not results:
        warnings.append("the response contains no results: the gallery is empty")
    for item in items:
        for field in item["missing"]:
            warnings.append(f"{item['anchor']}: missing {field}")

    title = html.escape(meta["title"])
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{title}</title>",
        f"<style>{STYLE}</style>",
        "</head>",
        "<body>",
        "<header>",
        f"<h1>{title}</h1>",
    ]
    if meta.get("subtitle"):
        parts.append(f'<p class="subtitle">{html.escape(meta["subtitle"])}</p>')
    meta_bits = [f"{len(items)} result(s)"]
    if query_id:
        meta_bits.append(f"query_id {query_id}")
    if meta.get("generated_at"):
        meta_bits.append(f"built {meta['generated_at']}")
    parts.append(f'<p class="meta">{html.escape(" | ".join(meta_bits))}</p>')
    parts.append("</header>")
    parts.append('<main class="gallery">')
    for item in items:
        parts.append(f'<figure id="{html.escape(item["anchor"], quote=True)}">')
        if item["image_url"]:
            alt = item["title"] or ""
            attrs = [f'src="{html.escape(item["image_url"], quote=True)}"', f'alt="{html.escape(alt, quote=True)}"', 'loading="lazy"', 'decoding="async"']
            if item["width"] is not None:
                attrs.append(f'width="{item["width"]}"')
            if item["height"] is not None:
                attrs.append(f'height="{item["height"]}"')
            parts.append(f'<img {" ".join(attrs)}>')
        else:
            parts.append('<div class="missing">image URL missing or not absolute</div>')
        parts.append("<figcaption>")
        if item["title"]:
            parts.append(f'<span class="caption">{html.escape(item["title"])}</span>')
        else:
            parts.append('<span class="caption missing">untitled</span>')
        rows = [("Rank", str(item["rank"]))]
        if item["source"]:
            rows.append(("Source", item["source"]))
        if item["width"] is not None and item["height"] is not None:
            rows.append(("Size", f'{item["width"]}x{item["height"]}'))
        if item["score"] is not None:
            rows.append(("Score", str(item["score"])))
        rows.append(("License", item["license_verbatim"] or item["license"] or "unknown"))
        rows.append(("Attribution", item["attribution"] or "none declared"))
        parts.append("<dl>")
        for label, value in rows:
            css = ' class="missing"' if value in ("unknown", "none declared") else ""
            parts.append(f"<dt>{html.escape(label)}</dt><dd{css}>{html.escape(value)}</dd>")
        parts.append("</dl>")
        if item["provenance_url"]:
            parts.append(f'<p class="credit">Source: <a href="{html.escape(item["provenance_url"], quote=True)}">{html.escape(item["provenance_url"])}</a></p>')
        else:
            parts.append('<p class="credit missing">source page not declared</p>')
        credit = _credit_line(item)
        if credit:
            parts.append(f'<p class="credit">Credit: {html.escape(credit)}</p>')
        parts.append("</figcaption>")
        parts.append("</figure>")
    parts.append("</main>")
    parts.append("<footer><p>Review page generated offline from a saved search response. Rights are not evaluated and no item is cleared for publication. Verify each license and credit with the source before use.</p></footer>")
    parts.append("</body>")
    parts.append("</html>")
    report = {
        "result_count": len(items),
        "assets": [{"anchor": item["anchor"], "missing": item["missing"]} for item in items],
        "warnings": warnings,
    }
    return "\n".join(parts) + "\n", warnings, report


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a saved Lightdrift search response as a self-contained HTML review gallery.")
    parser.add_argument("response", help="path to a saved search response JSON file")
    parser.add_argument("--title", default="Image review gallery")
    parser.add_argument("--subtitle")
    parser.add_argument("--generated-at", help="optional build label to show in the header; omitted by default")
    parser.add_argument("--output", help="write HTML to this path instead of standard output")
    parser.add_argument("--report", help="write a JSON review report with per-asset missing fields")
    parser.add_argument("--require-complete", action="store_true", help="exit 1 if any asset is missing metadata")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        response = load_response(args.response)
    except InputError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2
    meta = {"title": args.title, "subtitle": args.subtitle, "generated_at": args.generated_at}
    document, warnings, report = render(response, meta)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(document)
    else:
        sys.stdout.write(document)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 1 if (warnings and args.require_complete) else 0


if __name__ == "__main__":
    sys.exit(main())
