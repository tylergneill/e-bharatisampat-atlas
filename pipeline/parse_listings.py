"""Saved listing HTML -> data/catalogue.jsonl (one record per listing row, no network).

Parses ebharatisampat.in's two catalogue listings, `unicodetype.php` (Unicode
text) and `pdf.php` (scanned PDFs). Between them these enumerate the site's
entire holdings in 15 requests at `limit=1000`, which is the cheapest complete
catalogue source we have -- `urls.md`, the upstream scraper's input list, covers
only 4067 Unicode-side URLs.

**This module does no fetching.** It reads listing pages already saved to disk.
Acquisition is a separate decision -- see notes/scratch/todo.md before
automating it. To refresh by hand:

    curl -sL -o uni_page1.html \\
      "https://www.ebharatisampat.in/unicodetype.php?cat=All&sub_cat=&author=\\
&publisher=&contributor=&language=&sort=&limit=1000&page=1"

...for page=1..5 (unicode) and page=1..10 (pdf.php), then point --listings at
the directory. Filenames must contain the collection and a page number, e.g.
`uni_page3.html` / `pdf_page7.html`.

The two collections overlap -- 2554 records appear in both, so the 13620 rows
here describe 11066 distinct works. Join on `id`; see notes/site-structure.md.

Run: python -m pipeline.parse_listings --listings <dir>
"""

import argparse
import base64
import glob
import html
import json
import os
import re
from collections import Counter

from pipeline.config import CATALOGUE_PATH

# The table view carries the bibliographic columns (S.NO / Name / Category /
# Author / Publisher); the grid view below it carries the ids and thumbnails.
# Both list the same books in the same order, so the two are zipped together.
ROW_RE = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.S)
CELL_RE = re.compile(r"<td>(.*?)</td>", re.S)
ID_RE = re.compile(
    r"(readunicode|readpdf|readunicodetype|readpdftype)\.php\?id=([A-Za-z0-9+/=]+)"
)
# Each grid card is one book. Split on the card boundary rather than scanning
# the whole document, so a thumbnail stays bound to its own id.
CARD_RE = re.compile(
    r'<div class="product product__style--3.*?'
    r'(?=<div class="product product__style--3|\Z)',
    re.S,
)
THUMB_RE = re.compile(r'src="([^"]*thumbnailsimages/[^"]+)"')
TOTAL_RE = re.compile(r"of\s+([0-9]+)\s*(?:results)?", re.I)


def _clean(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _decode_id(token: str) -> str | None:
    """The URL id is base64 of a 15-16 digit number. Not the serial number --
    book 5310 encodes as 028062740047905, with no visible relation."""
    try:
        return base64.b64decode(token).decode("utf-8", "replace")
    except Exception:
        return None


def parse_page(doc: str) -> tuple[list[dict], list[tuple[str, str]], dict[str, str]]:
    """One saved listing page -> (table rows, [(endpoint, id)], {id: thumbnail})."""
    rows = []
    for match in ROW_RE.finditer(doc):
        cells = [_clean(c) for c in CELL_RE.findall(match.group(1))]
        # S.NO is a per-page row counter, not a serial number: it restarts at 1
        # on every page, and the listings expose no Ebharati-NNNN at all.
        if len(cells) == 5 and cells[0].isdigit():
            rows.append({
                "sno": int(cells[0]),
                "title": cells[1],
                "category": cells[2],
                "author": cells[3],
                "publisher": cells[4],
            })

    thumbs = {}
    for card in CARD_RE.findall(doc):
        id_match, img_match = ID_RE.search(card), THUMB_RE.search(card)
        if id_match and img_match:
            thumbs.setdefault(id_match.group(2), img_match.group(1))

    # Each id appears twice per card (thumbnail link and title link); keep first.
    ids, seen = [], set()
    for endpoint, token in ID_RE.findall(doc):
        if token not in seen:
            seen.add(token)
            ids.append((endpoint, token))

    return rows, ids, thumbs


def parse_collection(listings_dir: str, pattern: str, label: str) -> list[dict]:
    paths = sorted(
        glob.glob(os.path.join(listings_dir, pattern)),
        key=lambda p: int(re.search(r"(\d+)\.html$", p).group(1)),
    )
    if not paths:
        raise SystemExit(
            f"no {label} listing pages matching {pattern!r} in {listings_dir}\n"
            f"See this module's docstring for how to save them."
        )

    records, all_ids, thumbs, reported = [], [], {}, None
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as fh:
            doc = fh.read()
        rows, ids, page_thumbs = parse_page(doc)
        records.extend(rows)
        all_ids.extend(ids)
        thumbs.update(page_thumbs)
        if reported is None:
            totals = TOTAL_RE.findall(doc)
            reported = int(totals[0]) if totals else None
        print(f"  {os.path.basename(path)}: {len(rows)} rows, {len(ids)} ids, "
              f"{len(page_thumbs)} thumbnails")

    # The table and grid views must agree, or the zip below silently misaligns
    # every field after `id`.
    if len(records) != len(all_ids):
        raise SystemExit(
            f"{label}: {len(records)} table rows but {len(all_ids)} grid ids -- "
            f"the two views disagree, so records cannot be zipped. Listing markup "
            f"has probably changed; re-check the regexes."
        )

    for record, (endpoint, token) in zip(records, all_ids):
        record["id"] = token
        record["id_decoded"] = _decode_id(token)
        record["endpoint"] = endpoint
        record["thumbnail"] = thumbs.get(token)
        record["collection"] = label

    if reported is not None and reported != len(records):
        print(f"  !! {label}: page header reports {reported}, parsed {len(records)}")
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--listings", required=True,
                    help="directory of saved listing HTML (uni_page*.html, pdf_page*.html)")
    ap.add_argument("--out", default=str(CATALOGUE_PATH))
    args = ap.parse_args()

    print("Unicode:")
    unicode_records = parse_collection(args.listings, "uni_page*.html", "unicode")
    print("PDF:")
    pdf_records = parse_collection(args.listings, "pdf_page*.html", "pdf")
    records = unicode_records + pdf_records

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    unicode_ids = {r["id"] for r in unicode_records}
    pdf_ids = {r["id"] for r in pdf_records}
    both = unicode_ids & pdf_ids

    print(f"\nwrote {args.out}: {len(records)} rows")
    print(f"  unicode          {len(unicode_ids):6d}")
    print(f"  pdf              {len(pdf_ids):6d}")
    print(f"  in both formats  {len(both):6d}")
    print(f"  distinct works   {len(unicode_ids | pdf_ids):6d}  "
          f"(not {len(unicode_ids) + len(pdf_ids)} -- the collections overlap)")

    missing_thumb = sum(1 for r in records if not r["thumbnail"])
    if missing_thumb:
        print(f"  rows without a thumbnail: {missing_thumb}")
    categories = Counter(r["category"] for r in records)
    print(f"  categories       {len(categories):6d}")


if __name__ == "__main__":
    main()
