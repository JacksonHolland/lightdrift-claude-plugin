# Demo report: a saved search response as JSON Feed 1.1 and RSS 2.0

The converter is offline. Two commands over the synthetic two-result fixture:

```bash
python3 search_to_feed.py fixtures/search-response.json --pretty \
  --title "Standing query: coastal wildlife" \
  --home-url https://docs.lightdrift.ai/guides/search \
  --feed-url https://example.com/coastal-wildlife.json \
  --description "New images matching a standing image query"
python3 search_to_feed.py fixtures/search-response.json --format rss \
  --title "Standing query: coastal wildlife" \
  --home-url https://docs.lightdrift.ai/guides/search
```

The JSON Feed output is `demo-report.json`; the RSS output is `demo-feed.xml`. Each item receives a stable id, the source `provenance_url` as its link, the image as an attachment, and a `_lightdrift` extension carrying the rank, size, license and credit that the response declared.

| item id | link | image attachment | declared license |
| --- | --- | --- | --- |
| govflickr:8412901414 | https://www.flickr.com/photos/usfws/8412901414 | yes | https://creativecommons.org/publicdomain/mark/1.0/ |
| wikimedia:Example-Lighthouse.jpg | https://commons.wikimedia.org/wiki/File:Example-Lighthouse.jpg | yes | cc-by-sa-4.0 |

No date, byte length, creator or license is invented: the first item's Public Domain Mark license URL and the second item's bare `cc-by-sa-4.0` identifier are copied verbatim, and the tracked image URL is kept as the attachment rather than presented as a stable public file. Fixtures are synthetic and no API request was sent.
