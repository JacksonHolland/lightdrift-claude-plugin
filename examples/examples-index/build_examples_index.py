#!/usr/bin/env python3
"""Build a discoverability index for runnable image-search examples.

The Lightdrift docs publish a guide per runnable example, and each guide links
back to the example source. Nothing currently links *from* a single reference
page to every example, so some published examples are reachable only if a
reader already knows their name. This offline utility scans an examples tree
and a guides tree, and emits:

  * an MDX reference page that links every example (and its guide, when one
    exists), giving the documentation an internal-link hub and a citable index;
  * a JSON coverage report listing examples that have no guide, so the gap is
    visible instead of silent.

It reads local files only. It never calls Lightdrift, fetches a URL, or spends
search credits.

Exit codes
    0   every example is referenced from at least one guide (or --no-strict)
    1   at least one example has no guide and --strict is set
    2   usage/input error (missing directory, unreadable README, ...)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_REPO_URL = (
    "https://github.com/JacksonHolland/lightdrift-claude-plugin/tree/main/examples"
)

_TITLE_RE = re.compile(r"^#\s+(.*\S)\s*$")


class InputError(Exception):
    """Raised for a usage/input problem (exit code 2)."""


def _first_sentence(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return match.group(1) if match else text


def read_title_and_blurb(readme: Path) -> tuple[str, str]:
    try:
        raw = readme.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - defensive
        raise InputError(f"cannot read {readme}: {exc}") from exc

    lines = raw.splitlines()
    title = ""
    body: list[str] = []
    seen_title = False
    for line in lines:
        stripped = line.strip()
        if not seen_title:
            m = _TITLE_RE.match(stripped)
            if m:
                title = m.group(1)
                seen_title = True
            continue
        if not stripped:
            if body:
                break
            continue
        if stripped.startswith(("#", "```", "|", ">")):
            break
        body.append(stripped)
    if not title:
        raise InputError(f"{readme} has no level-1 heading")
    return title, _first_sentence(" ".join(body))


def find_run_command(example_dir: Path) -> str:
    scripts = sorted(
        p.name
        for p in example_dir.glob("*.py")
        if not p.name.startswith("test_")
        and p.name != "__init__.py"
    )
    if not scripts:
        return ""
    return f"python3 {scripts[0]}"


def discover_examples(examples_dir: Path) -> list[dict]:
    if not examples_dir.is_dir():
        raise InputError(f"examples directory not found: {examples_dir}")
    found: list[dict] = []
    for child in sorted(examples_dir.iterdir()):
        readme = child / "README.md"
        if not child.is_dir() or not readme.is_file():
            continue
        title, blurb = read_title_and_blurb(readme)
        found.append(
            {
                "key": child.name,
                "title": title,
                "blurb": blurb,
                "run": find_run_command(child),
            }
        )
    if not found:
        raise InputError(f"no examples with a README.md under {examples_dir}")
    return found


def read_guide_coverage(guides_dir: Path) -> list[dict]:
    if not guides_dir.is_dir():
        raise InputError(f"guides directory not found: {guides_dir}")
    guides: list[dict] = []
    for path in sorted(guides_dir.glob("*.mdx")):
        if path.is_file():
            guides.append(
                {"key": path.stem, "text": path.read_text(encoding="utf-8")}
            )
    return guides


def _guide_for(key: str, guides: list[dict]) -> str | None:
    for guide in guides:
        if guide["key"] == key:
            return guide["key"]
    pattern = re.compile(
        r"(?:/|^)examples/" + re.escape(key) + r"(?![\w-])"
    )
    matches = [g["key"] for g in guides if pattern.search(g["text"])]
    return matches[0] if matches else None


def build_index(
    examples_dir: Path, guides_dir: Path, repo_url: str
) -> tuple[str, dict]:
    examples = discover_examples(examples_dir)
    guides = read_guide_coverage(guides_dir)

    rows: list[str] = []
    missing: list[str] = []
    for ex in examples:
        guide = _guide_for(ex["key"], guides)
        if guide is None:
            missing.append(ex["key"])
        link = f"[{ex['title']}]({repo_url}/{ex['key']})"
        guide_cell = f"[guide](/guides/{guide})" if guide else "—"
        blurb = ex["blurb"] or "Runnable offline Python utility."
        rows.append(f"| {link} | {blurb} | {guide_cell} |")

    mdx = "\n".join(
        [
            "---",
            'title: "Runnable image-search examples and recipes"',
            'description: "Index of runnable, offline Python examples for Lightdrift image search, each linked to its guide and source code."',
            "---",
            "",
            "Every example below is a runnable, offline Python 3.10+ utility. "
            f"Source: [example repository]({repo_url}).",
            "",
            "| Example | What it produces | Guide |",
            "| --- | --- | --- |",
            *rows,
            "",
        ]
    )

    report = {
        "examples_dir": str(examples_dir),
        "guides_dir": str(guides_dir),
        "examples_total": len(examples),
        "guides_total": len(guides),
        "examples_with_guide": len(examples) - len(missing),
        "examples_without_guide": missing,
        "examples": [
            {
                "key": ex["key"],
                "title": ex["title"],
                "run": ex["run"],
                "guide": _guide_for(ex["key"], guides),
            }
            for ex in examples
        ],
    }
    return mdx, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--examples-dir", required=True, type=Path)
    parser.add_argument("--guides-dir", required=True, type=Path)
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--output", type=Path, help="write MDX here (default stdout)")
    parser.add_argument("--report", type=Path, help="write JSON coverage report here")
    parser.add_argument("--strict", action="store_true", help="exit 1 on any missing guide")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        mdx, report = build_index(args.examples_dir, args.guides_dir, args.repo_url)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.write_text(mdx, encoding="utf-8")
    elif not args.quiet:
        sys.stdout.write(mdx)

    if args.report:
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if not args.quiet:
        print(
            f"{report['examples_total']} examples, "
            f"{report['examples_with_guide']} with a guide, "
            f"{len(report['examples_without_guide'])} without: "
            f"{', '.join(report['examples_without_guide']) or 'none'}",
            file=sys.stderr,
        )

    if args.strict and report["examples_without_guide"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
