# similar-expand demo (synthetic fixtures)

Run: `python3 similar_expand.py --expansion fixtures/similar-a.json --expansion fixtures/similar-b.json`

| Field | Value |
| --- | --- |
| mode | merge (offline) |
| seeds merged | 2 (`isorepublic:17191`, `stocksnap:BAVURMUHRD`) |
| shortlist size | 4 unique assets |
| search credit spent | $0 (no network) |

## Merged shortlist

| asset_id | found by | source | license | attribution required |
| --- | --- | --- | --- | --- |
| stocksnap:BAVURMUHRD | isorepublic:17191 | stocksnap | cc0 | no |
| flickr:51141533761 | isorepublic:17191, stocksnap:BAVURMUHRD | flickr | cc-by-sa | yes |
| isorepublic:17191 | stocksnap:BAVURMUHRD | isorepublic | cc0 | no |
| yfcc:9715466326 | stocksnap:BAVURMUHRD | yfcc | cc-by | yes |

`flickr:51141533761` was returned for both seeds, so it carries two entries in
`found_by` and appears once in the shortlist. This is the identity-de-duplication
that keeps an expanded moodboard from re-listing the same photo.

All values above are copied from the synthetic fixtures. They are not observed
customer searches.
