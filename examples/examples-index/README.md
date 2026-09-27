# Index runnable examples so every published asset is internally reachable

Lightdrift publishes a guide per runnable example, but nothing linked *from* one
reference page to every example. An example that no guide happens to cite is
reachable only if a reader already knows its name, which weakens discovery and
the internal-link graph that supports citation.

This Python 3.10+ standard-library utility scans an examples tree and a guides
tree and emits:

- an MDX reference page that links every example and its guide, giving the docs
  an internal-link hub and a citable index;
- a JSON coverage report that lists examples with no guide, so the gap is
  visible instead of silent.

It reads local files only. It never calls Lightdrift, fetches a URL or spends
search credits.

## Run a reproducible example

```bash
python3 build_examples_index.py \
  --examples-dir /path/to/public-examples/examples \
  --guides-dir /path/to/lightdrift-docs/guides \
  --output examples-index.mdx \
  --report coverage-report.json
```

Against the current published tree this reports:

```text
18 examples, 15 with a guide, 3 without: delivery-url-audit, layout-fit, windmill-layout-audit
```

`delivery-url-audit` and `layout-fit` are utilities produced by this lane, so
their missing guides are a concrete, actionable gap. `--strict` exits non-zero
when any example lacks a guide, which makes the check usable in CI.

## How coverage is decided

An example counts as covered when a guide links its source at
`/examples/<key>` (commit-pinned links count). A bare prose mention of the name
does **not** count, so false positives from unrelated text are avoided.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | every example is referenced from a guide (or `--strict` not set) |
| 1 | `--strict` set and at least one example has no guide |
| 2 | input error (missing directory, README without a heading, ...) |

## Files

- `build_examples_index.py` — the utility.
- `test_build_examples_index.py` — 12 standard-library tests.
- `fixtures/` — synthetic examples and guides trees.
- `examples-index.mdx` — generated output against the live published tree.
- `coverage-report.json` — generated coverage report.
- `sources/manifest.json` — captured input files with SHA-256.
