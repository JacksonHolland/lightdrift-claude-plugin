# Demo report: a saved search response as an offline review gallery

The builder is offline. One command over the synthetic two-result fixture:

```bash
python3 build_review_gallery.py fixtures/search-response.json \
  --title "Standing query review: coastal wildlife" \
  --subtitle "Offline review page built from a saved search response" \
  --generated-at 2026-09-27 \
  --output demo-gallery.html \
  --report demo-report.json
```

It writes `demo-gallery.html`: one `<figure>` per result with its thumbnail, a caption, declared credits and the source page link. Running it over `fixtures/search-response-partial.json` (`demo-gallery-partial.html`, `demo-report-partial.json`) exits `0` but reports every missing field and marks it on the page.

| rank | anchor | image | declared license | missing |
| --- | --- | --- | --- | --- |
| 1 | govflickr:8412901414 | thumb | Public Domain Mark 1.0 | none |
| 2 | wikimedia:Example-Lighthouse.jpg | thumb | CC BY-SA 4.0 | none |

The incomplete fixture flags `title`, `provenance_url`, `license`, `attribution`, `dimensions` for the first result and adds `asset_id` and `image` for the second, which has only a relative `file` path. Nothing is invented: a missing caption renders as `untitled`, a missing credit as `none declared`, and a missing source page as `source page not declared`. Fixtures are synthetic and no API request was sent.
