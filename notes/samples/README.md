# Samples

Retrieved by hand, kept as evidence rather than as corpus data. This atlas
publishes no text of its own; nothing here feeds the pipeline.

## `1618_siddhasiddhantasangraha.txt`

Balabhadra, *Siddhasiddhāntasaṅgraha* — Sarasvati Bhavana Texts No. 13,
Government Sanskrit Library, Benares, 1925. Serial `Ebharati-1618`.

795 lines, 42217 chars, 28309 of them Devanagari. Title page through back
matter, clean verse with intact daṇḍas and numbering.

Kept because this book is **absent from the upstream snapshot** while its id sits
in `urls.md` — the worked example that shows the 1780-entry gap is upstream
script failure rather than missing content. See `../snapshot-defects.md`.

Extracted from `POST get_unicode.php` (`b_id=1618&my_id=0`) by stripping tags
and unescaping entities; see `../scraping-findings.md` for the mechanism.

## `catalogue-2026-08-10.jsonl.gz`

**Both collections enumerated in full**, 2026-08-10 — 13620 rows (4192 Unicode
+ 9428 PDF), one JSON object per listing row:

```
{"sno", "title", "category", "author", "publisher",
 "id", "id_decoded", "endpoint", "thumbnail", "collection"}
```

Produced by **`pipeline/parse_listings.py`** (`make catalogue LISTINGS=<dir>`),
which is the maintained parser — this file is a dated snapshot of its output.

Retrieved as 15 requests: `unicodetype.php` and `pdf.php` with
`cat=All&sub_cat=&author=&publisher=&contributor=&language=&sort=&limit=1000`
and `&page=1..5` / `&page=1..10`. Rows come from each page's table view; the
grid view's `readunicode.php` / `readpdf.php` links supply `id` in the same
document order.

This is the evidence behind the overlap finding in `../site-structure.md`
(2554 records in both collections, 11066 distinct works). Kept because
re-deriving it means 15 more requests against the site.

**Caveats.** `sno` is a per-page row counter, not a serial — it restarts at 1
each page, and the listings expose no `Ebharati-NNNN` anywhere. `id_decoded` is
the base64-decoded opaque id, a 15–16 digit number with no established relation
to the serial. Rows are the site's raw strings, unnormalized.

`extract-catalogue.py` is the parser that produced it, kept so the shape can be
re-derived if the listing markup changes. It reads saved listing HTML from the
working directory; it does no fetching.

## `serial-bands.py`

The serial-axis band analysis behind `../serial-bands.md` — dates, formats
and text sizes per band, plus the serial gap map and the serial/`uploaded`
agreement rate. Reads `docs/data/metadata.json`, `data/text_sizes.jsonl` and
`data/text_open_books.jsonl`; **fetches nothing**.

    python notes/samples/serial-bands.py            # the report table
    python notes/samples/serial-bands.py --gaps     # gaps + occupancy
    python notes/samples/serial-bands.py --edges    # fine-grained era edges
    python notes/samples/serial-bands.py --rho      # serial/uploaded agreement
    python notes/samples/serial-bands.py --coverage # done vs open per band

Unlike the other files here this is a *script kept for rerunning*, not a
frozen artifact: every figure it prints moves as the tier-3 ladder closes
open books. Regenerate the table in `../serial-bands.md` from `--report`
rather than editing it by hand.

**Band edges are deliberately not round numbers** — they follow the format
transitions `--edges` finds (PDF drops at 2450, returns at 4550) and the
186-serial hole at 4370-4557. Rounding them to decades hides the finding.
