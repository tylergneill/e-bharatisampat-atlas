"""Stage 2c: data/metadata_cache/*.html -> docs/data/metadata.json (no network).

Reads the tier-2 cache -- one reshaped `readSearch.php` page per distinct work,
written by `fetch_metadata` -- and emits a JSON array, one object per work.

The cache stores markup rather than fields on purpose, so this stage is cheap to
rerun: getting an extraction wrong costs a reparse of local files, never a
second scrape. Run it against a partial fetch freely.

Output goes to `docs/data/`, tracked and published, because the frontend reads
it -- unlike the gitignored `data/` artifacts this stage reads.

**This file is shaped for the atlas, not as an archive of the page.** Anything
derivable is dropped, because it ships to every visitor:

- reader URLs and the `SOURCE` url -- rebuilt by `reader_url` / `source_url`
  from the id, whose shapes were verified across all 11066 records
- each reader's `bookid` (always the record's own id) and label (constant per
  format), and `readbook3`'s `pageno` (one constant corpus-wide)
- `pdf`'s endpoint (always `ebook/index`), so `pdf` is a bare boolean
- the thumbnail filename -- only its embedded upload date is kept
- the source cache filename

The cache remains the archive; re-derive from it, not from this file.

Each cached file is a flat list of `<h5>LABEL&nbsp;:&nbsp;VALUE</h5>` rows. 22
labels occur across the corpus; only TITLE / DOMAIN / SERIAL NO. appear on all
11066, and an absent row is itself the signal -- see notes/site-structure.md.

Run: python -m pipeline.parse_metadata
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

from pipeline.config import METADATA_CACHE_DIR, METADATA_PATH
from pipeline.upload_dates import decode as decode_upload
from pipeline.upload_dates import interpolate_additions

# One row. The label runs to the first colon that is not part of the value;
# labels are upper-case ASCII plus space, dot and hyphen ("SERIAL NO.",
# "SUB-DOMAIN"), which no value starts with.
ROW_RE = re.compile(
    r"<h5>([A-Z][A-Z .\-]*?)\s*(?:&nbsp;|\s)*:(?:&nbsp;|\s)*(.*?)</h5>",
    re.S,
)
# TEXT / PDF / SOURCE rows carry an anchor; the endpoint name precedes it.
ANCHOR_RE = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
SERIAL_RE = re.compile(r"Ebharati-(\d+)")
BOOKID_RE = re.compile(r"[?&]bookid=([^&\"]+)")
ID_RE = re.compile(r"[?&]id=([^&\"]+)")

SITE_ROOT = "https://www.ebharatisampat.in"
# Identical across every `readbook3` link in the corpus; see `reader_url`.
READBOOK3_PAGENO = "MjI0MjQyNjk5NTk="

# Label -> output key. Keys are snake_case; the site's own wording is preserved
# in meaning, not in punctuation. Order here is the order fields appear in the
# output record, which is roughly the site's own row order.
FIELDS = {
    "TITLE": "title",
    "AUTHOR": "author",
    "PUBLISHER": "publisher",
    "PUBLISH YEAR": "publish_year",
    "DOMAIN": "domain",
    "SUB-DOMAIN": "sub_domain",
    "PAGES": "pages",
    "LANGUAGE": "language",
    "EDITOR": "editor",
    "SECOND EDITOR": "second_editor",
    "TRANSLATOR": "translator",
    "PRIMARY COMMENTATOR": "primary_commentator",
    "SECONDARY COMMENTATOR": "secondary_commentator",
    "TERTIARY COMMENTATOR": "tertiary_commentator",
    "COMMENTARY NAME": "commentary_name",
    "PRINTER": "printer",
    "BOOKS CONTRIBUTOR": "books_contributor",
}
# Handled specially rather than copied through.
STRUCTURAL = {"SERIAL NO.", "THUMBNAIL", "TEXT", "PDF", "SOURCE"}


def clean(value: str) -> str:
    """Row value -> plain text: drop markup, unescape entities, collapse space."""
    text = html.unescape(TAG_RE.sub(" ", value))
    # Non-breaking spaces survive unescaping as U+00A0; the site uses them as
    # padding, so they are whitespace here.
    return " ".join(text.replace(" ", " ").split())


def parse_rows(page: str) -> list[tuple[str, str]]:
    """Every `<h5>` row as (label, raw value), in document order."""
    return [(m.group(1).strip(), m.group(2)) for m in ROW_RE.finditer(page)]


def parse_reader(value: str) -> str | None:
    """A TEXT/PDF row -> just its endpoint name.

    Everything else in the row is derivable and so is dropped (verified across
    all 11066 records): the anchor's `bookid` always equals the record's own
    `id`, the label is constant per format ("Read Unicode" / "Read E-Book"),
    and `readbook3` links all carry one identical `pageno`. `reader_url` below
    rebuilds the href from `id` + endpoint.

    The endpoint is what survives because it is the only bit carrying
    information: `read_chapter` means the site paginates the work by chapter
    (so a table of contents exists), `readbook3` means one flat text. On the
    PDF side it is always `ebook/index`, which is why `pdf` is stored as a
    plain boolean instead.
    """
    anchor = ANCHOR_RE.search(value)
    if not anchor:
        return None
    return clean(value.split("<a")[0]) or None


def reader_url(book_id: str, endpoint: str) -> str:
    """Rebuild a reader link from the id and endpoint name.

    The inverse of what `parse_reader` drops. Kept here rather than in the
    frontend so the URL shapes live with the code that verified them.
    """
    if endpoint == "readbook3":
        # One constant `pageno` across all 4891 readbook3 links -- it is the
        # site's "start at the beginning" token, not a per-book value.
        return (f"{SITE_ROOT}/readbook3.php?bookid={book_id}"
                f"&pageno={READBOOK3_PAGENO}")
    if endpoint == "read_chapter":
        return f"{SITE_ROOT}/read_chapter.php?bookid={book_id}"
    if endpoint == "ebook/index":
        return f"{SITE_ROOT}/ebook/index.php?bookid={book_id}"
    raise ValueError(f"unknown reader endpoint: {endpoint}")


def source_url(book_id: str) -> str:
    """The metadata page a record came from."""
    return f"{SITE_ROOT}/readSearch.php?id={book_id}"


def parse_file(path: Path) -> dict:
    """One cached page -> one record. Missing rows are simply absent keys."""
    page = path.read_text(encoding="utf-8")
    rows = parse_rows(page)

    record: dict = {}
    extra: dict = {}

    for label, raw in rows:
        if label in STRUCTURAL:
            continue
        value = clean(raw)
        if not value:
            continue
        if key := FIELDS.get(label):
            record[key] = value
        else:
            # A label the corpus census did not turn up. Kept rather than
            # dropped, so a site-side addition surfaces instead of vanishing.
            extra[label] = value

    by_label = {label: raw for label, raw in rows}

    # Identity. The base64 id is the catalogue-wide join key and lives only in
    # the SOURCE row; the serial is the human-facing number. The SOURCE url
    # itself is not stored -- `source_url(id)` rebuilds it.
    if source := by_label.get("SOURCE"):
        if found := ID_RE.search(html.unescape(source)):
            record["id"] = found.group(1)
    if serial := by_label.get("SERIAL NO."):
        if found := SERIAL_RE.search(clean(serial)):
            record["serial"] = int(found.group(1))

    # The thumbnail filename's only use here is the upload date -- the site's
    # only signal about the digital record rather than the printed book. The
    # filename itself is dropped (the atlas links out rather than rendering
    # covers); it stays in the cache should that change. Both naming
    # conventions and the exact-10-digit rule live in `upload_dates`; do not
    # re-derive them here (its docstring explains what that costs).
    if thumb := by_label.get("THUMBNAIL"):
        name = html.unescape(TAG_RE.sub("", thumb)).replace(" ", " ").strip()
        when, _ = decode_upload(name)
        if when:
            record["uploaded"] = when.date().isoformat()

    # Readers. `text` holds the endpoint name because it varies and carries the
    # TOC flag; `pdf` is a bare true because its endpoint never varies. Absence
    # means that format does not exist for the work -- every work has at least
    # one, and 50% have only the PDF.
    if raw := by_label.get("TEXT"):
        if endpoint := parse_reader(raw):
            record["text"] = endpoint
    if raw := by_label.get("PDF"):
        if parse_reader(raw):
            record["pdf"] = True

    if extra:
        record["extra"] = extra
    return record


def key_order(record: dict) -> dict:
    """Identity first, then bibliography, then readers -- stable across records."""
    lead = ["id", "serial", "title"]
    tail = ["uploaded", "added", "added_synthetic", "text", "pdf", "extra"]
    middle = [k for k in record if k not in lead and k not in tail]
    return {k: record[k] for k in [*lead, *middle, *tail] if k in record}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, default=METADATA_CACHE_DIR)
    parser.add_argument("--out", type=Path, default=METADATA_PATH)
    args = parser.parse_args()

    if not args.cache.is_dir():
        print(
            f"metadata cache not found: {args.cache}\n"
            f"Run `make fetch-metadata` first -- this stage only reads what "
            f"that wrote, and costs no requests.",
            file=sys.stderr,
        )
        return 1

    paths = sorted(args.cache.glob("*.html"))
    if not paths:
        print(f"no cached pages in {args.cache}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    duplicates = 0
    no_id = 0
    field_counts: dict[str, int] = {}
    unknown_labels: dict[str, int] = {}

    records = []
    for path in paths:
        record = key_order(parse_file(path))

        book_id = record.get("id")
        if not book_id:
            no_id += 1
        elif book_id in seen_ids:
            duplicates += 1
        else:
            seen_ids.add(book_id)

        for key in record:
            field_counts[key] = field_counts.get(key, 0) + 1
        for label in record.get("extra", {}):
            unknown_labels[label] = unknown_labels.get(label, 0) + 1

        records.append(record)

    # `uploaded` is the measured stamp; `added` is when the item actually
    # arrived. They differ only where a stamp runs far past its serial
    # neighborhood -- a later touch to the record, not an arrival -- and
    # publishing that as an arrival date is what put old books in recent months.
    synthetic, early = interpolate_additions(records)

    # A JSON array, not JSONL: the only consumer is a browser doing one
    # `fetch().json()`, which cannot stream lines. Compact separators for the
    # same reason `build_tree` uses them -- this file ships to visitors.
    with args.out.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")

    print(f"cache:   {args.cache}")
    print(f"out:     {args.out}")
    print(f"records: {len(paths)}  ({len(seen_ids)} distinct ids)")
    print(f"added:   {synthetic} synthetic (stamp >1y past its serial neighborhood; "
          f"{early} the same distance behind)")
    if no_id:
        print(f"WARNING: {no_id} records carry no id")
    if duplicates:
        print(f"WARNING: {duplicates} records repeat an id already seen")
    if unknown_labels:
        print(f"unrecognized labels (kept under `extra`): {unknown_labels}")

    size = args.out.stat().st_size
    print(f"size:    {size / 1048576:.1f}M")

    print("\nfield coverage:")
    for key, count in sorted(field_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {count:6d}  {100 * count / len(paths):5.1f}%  {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
