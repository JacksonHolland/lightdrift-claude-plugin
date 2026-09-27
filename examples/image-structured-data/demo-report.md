# Demo report: structured-data emitter over a synthetic saved search

Input: `fixtures/search-response.json` (synthetic fixtures; no licensed image files, no live search).

Query id: `q_synthetic_fixture_not_a_real_search` — results: 2

| asset_id | name | absolute file | w×h | license used | attribution required | credit |
| --- | --- | --- | --- | --- | --- | --- |
| govflickr:8412901414 | Sea otter floating on its back | True | 1024×768 | https://creativecommons.org/publicdomain/mark/1.0/ | False | US Fish and Wildlife Service — https://www.flickr.com/photos/usfws/8412901414 |
| wikimedia:Example-Lighthouse.jpg | Coastal lighthouse at dusk | True | 800×600 | omitted (identifier) | True | Example Photographer — https://commons.wikimedia.org/wiki/File:Example-Lighthouse.jpg |

## Warnings

- wikimedia:Example-Lighthouse.jpg: rights.license is an identifier, not a URL; 'license' is omitted from JSON-LD

> contentUrl is a Lightdrift tracked URL that redirects (302) to a short-lived signed link; confirm your publishing pipeline follows redirects or replace it with a stable URL you control.

`rights_not_evaluated: true` — this tool copies declared metadata; it does not clear rights.
