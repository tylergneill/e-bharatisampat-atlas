"""snapshot inventory + sizes -> docs/data/snapshot_tree.json. 2287 books.

The alternative to `build_tree`, which covers all 11066 works from the metadata
scrape but has no byte figures. This one covers 21% of the catalogue and does
have them, measured over 1.6G of source text -- that is the whole reason it
survives. Same shape from both (see `pipeline.shape`), so the frontend can read
either file; they are alternatives, never combined.

The snapshot's books are a strict subset -- all 2287 of its serials appear
among the 11066 -- but the two sources encode the book id differently (snapshot
decoded, metadata base64), so `serial` is the stable key if anything ever needs
to cross them.

Byte figures come from data/snapshot_text_sizes.jsonl, written by
`pipeline.count_snapshot_sizes`. This stage never reads the snapshot itself, so it is
fast -- and it TRUSTS that cache and cannot tell it is stale; whatever updates
the snapshot owns rerunning the measurement.

This stage deliberately does NOT stamp `docs/VERSION`. That file names when
*the site's* content was last fetched, and the snapshot is a third-party pull
of unrelated vintage -- letting it write there would relabel our corpus with a
borrowed date. Only `build_tree` stamps.

Deleted along with the rest of the snapshot dependency once acquisition is ours
and byte sizes come from our own fetch.

Run: python -m pipeline.build_snapshot_tree
"""

import argparse
import json
from pathlib import Path

from pipeline.config import (INVENTORY_PATH, SNAPSHOT_SIZES_PATH,
                             SNAPSHOT_TREE_PATH)
from pipeline.shape import OPTIONAL_FIELDS, SIZE_KEYS, build_axes, report, write
from pipeline.languages import parse as parse_languages

# The snapshot's frontmatter spells these with spaces; the metadata parse uses
# underscores. Normalized here so both builders emit one field vocabulary.
FIELD_ALIASES = {
    "publish year": "publish_year",
    "primary commentator": "primary_commentator",
    "secondary commentator": "secondary_commentator",
    "tertiary commentator": "tertiary_commentator",
    "commentary name": "commentary_name",
    "second editor": "second_editor",
    "books contributor": "books_contributor",
}


def load_sizes(path: Path) -> dict[str, dict]:
    """book_id -> byte figures, from the snapshot's size cache."""
    sizes = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sizes[row["book_id"]] = {k: row[k] for k in SIZE_KEYS if k in row}
    return sizes


def work_from_snapshot(record: dict, sizes: dict[str, dict]) -> dict:
    """One snapshot_inventory.jsonl record -> one work, in the shared shape.

    The snapshot has no `pdf` flag and no upload date, and its reader endpoint
    lives inside the source url rather than in a field -- so those are recovered
    where possible and left absent otherwise, never faked.
    """
    meta = {FIELD_ALIASES.get(k, k): v
            for k, v in record.get("metadata", {}).items()}
    endpoint = record.get("endpoint")

    work = {
        "id": record["book_id"],
        "serial": record["serial"],
        "title": record["title"],
        "domain": record["domain"],
        "sub_domain": record.get("sub_domain"),
        # Top-level in the inventory, not under `metadata` -- and absent for the
        # 1006 books whose frontmatter names no author.
        "author": record.get("author") or meta.get("author"),
        "language": record.get("language"),
        "languages": sorted(parse_languages(record.get("language") or "")),
        "text": endpoint,
        # The snapshot only ever captured Unicode text, so it knows nothing
        # about which works have a scan. False, not unknown -- but do not read
        # it as evidence that no PDF exists upstream.
        "pdf": False,
        "uploaded": None,
    }
    for key in OPTIONAL_FIELDS:
        if meta.get(key):
            work[key] = meta[key]

    if measured := sizes.get(record["book_id"]):
        work["sizes"] = measured
        # Some books scraped down to an empty "\[ \]" wrapper -- the upstream
        # script captured the page but not the text. 12 as of pull 0977e07c2,
        # but the set moves between pulls, so do not trust a fixed count (see
        # notes/snapshot-defects.md). Real catalogue entries either way, so they
        # stay in the tree but do not count as having text.
        if not measured.get("content_bytes"):
            work["empty_in_snapshot"] = True
            work["text"] = None
    return work


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    parser.add_argument("--sizes", type=Path, default=SNAPSHOT_SIZES_PATH)
    parser.add_argument("--out", type=Path, default=SNAPSHOT_TREE_PATH)
    args = parser.parse_args()

    if not args.inventory.exists():
        print(f"missing {args.inventory}; run `make parse` first.")
        return 1
    if not args.sizes.exists():
        print(f"missing {args.sizes}; run `make recount` first.")
        return 1

    sizes = load_sizes(args.sizes)
    works = [
        work_from_snapshot(json.loads(line), sizes)
        for line in args.inventory.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tree = build_axes(works, "snapshot")
    write(tree, args.out)
    report(tree, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
