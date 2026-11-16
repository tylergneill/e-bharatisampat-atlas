"""Walked shelves -> data/catalogue.jsonl (one record per shelf row, no network).

Reads the raw JSON pages `make walk-shelves` saved under
`data/shelves_cache/<date>/`, by default the latest complete walk (the one with
a `manifest.json`). Three shelves:

    pdf       "E-Books"
    unicode   "Unicode Books"        (proofread text)
    ai        "AI-converted books"   (unproofread text)

A work appears once per shelf it is on, so the rows outnumber the works. Join
on `serial` or `id`; see notes/site-structure.md.

Each JSON record carries the serial (as `id`) and the listed fields. The base64
id, which the metadata pages are keyed on, is only in the response's
`table_html`, where each row's link pairs it with the serial:

    <a href="readunicode?id=NDIxODAzNzU3OTgxOTcwMQ==" ...> 11242 </a>

So the two are joined on serial, not on row order.

Run: python -m pipeline.parse_listings              # latest complete walk
     python -m pipeline.parse_listings --walk DIR   # a specific one
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from pipeline.config import CATALOGUE_PATH, SHELVES_CACHE_DIR

SHELVES = ("pdf", "unicode", "ai")
ROW_LINK_RE = re.compile(r'href="read\w+\?id=([A-Za-z0-9+/=]+)"[^>]*>\s*(\d+)\s*</a>')
THUMB_DIR = "img/thumbnailsimages/"


def latest_walk(root: Path) -> Path:
    walks = sorted(p for p in root.glob("*") if (p / "manifest.json").exists())
    if not walks:
        raise SystemExit(f"no complete walk under {root} -- run `make walk-shelves`")
    return walks[-1]


def record(book: dict, base64_id: str, shelf: str) -> dict:
    """One shelf row, in this pipeline's vocabulary. Empty strings -> absent."""
    fields = {
        "serial": int(book["id"]),
        "id": base64_id,
        "collection": shelf,
        "title": book.get("devanagari_title"),
        "title_eg": book.get("title_eg"),
        "category": book.get("cat_eg"),
        "sub_category": book.get("sub_cat"),
        "author": book.get("author_eg"),
        "publisher": book.get("publisher_eg"),
        "contributor": book.get("contributor"),
        "language": book.get("language"),
        # Same shape the old HTML listings gave, which upload_dates.decode reads.
        "thumbnail": THUMB_DIR + book["thumbimg"] if book.get("thumbimg") else None,
        "pdf_file": book.get("pdfurl"),
        "correct_ocr": book.get("correct_ocr"),
    }
    return {k: v.strip() if isinstance(v, str) else v
            for k, v in fields.items() if v not in (None, "")}


def parse_shelf(walk: Path, shelf: str) -> list[dict]:
    pages = sorted((walk / shelf).glob("*.json"))
    if not pages:
        raise SystemExit(f"{walk / shelf}: no pages")
    rows = []
    for page in pages:
        data = json.loads(page.read_text(encoding="utf-8"))
        ids = {int(serial): token for token, serial
               in ROW_LINK_RE.findall(data["table_html"])}
        for book in data["books"]:
            serial = int(book["id"])
            if serial not in ids:
                raise SystemExit(
                    f"{page}: serial {serial} has no link in table_html -- "
                    f"the listing markup has probably changed")
            rows.append(record(book, ids[serial], shelf))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--walk", type=Path,
                    help="a walk directory (default: the latest complete one)")
    ap.add_argument("--out", type=Path, default=CATALOGUE_PATH)
    args = ap.parse_args()

    walk = args.walk or latest_walk(SHELVES_CACHE_DIR)
    manifest = json.loads((walk / "manifest.json").read_text())
    print(f"reading {walk}")

    records, by_shelf = [], {}
    for shelf in SHELVES:
        rows = parse_shelf(walk, shelf)
        expected = manifest["shelves"][shelf]["total"]
        if len(rows) != expected:
            raise SystemExit(f"{shelf}: parsed {len(rows)}, manifest says {expected}")
        records.extend(rows)
        by_shelf[shelf] = {r["serial"] for r in rows}

    # One serial, one id, whichever shelf it was read from.
    id_of = {}
    for r in records:
        if id_of.setdefault(r["serial"], r["id"]) != r["id"]:
            raise SystemExit(f"serial {r['serial']} has two ids on different shelves")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    text = by_shelf["unicode"] | by_shelf["ai"]
    pdf = by_shelf["pdf"]
    print(f"wrote {args.out}: {len(records)} rows")
    for shelf in SHELVES:
        print(f"  {shelf:16} {len(by_shelf[shelf]):6d}")
    print(f"  distinct works   {len(text | pdf):6d}")
    print(f"    text only      {len(text - pdf):6d}")
    print(f"    both           {len(text & pdf):6d}")
    print(f"    pdf only       {len(pdf - text):6d}")
    if overlap := by_shelf["unicode"] & by_shelf["ai"]:
        print(f"  !! on both text shelves: {len(overlap)}")
    missing_thumb = sum(1 for r in records if "thumbnail" not in r)
    if missing_thumb:
        print(f"  rows without a thumbnail: {missing_thumb}")
    print(f"  categories       {len(Counter(r.get('category') for r in records)):6d}")


if __name__ == "__main__":
    main()
