"""Stage 2a: snapshot bodies -> data/snapshot_text_sizes.jsonl.

Measures each book three ways -- raw bytes, cleaned content bytes, and the
byte length of that content transliterated DEV->IAST. All three are pure
functions of the book file, and the snapshot is static, so this runs once per
snapshot and `snapshot_build_tree` just reads the result.

The DEV->IAST pass is the slow part (~1.5 min on 8 cores against ~1.6G of
Devanagari); the point of caching is that a normal build pays none of it, and
never reads the snapshot at all.

`snapshot_build_tree` trusts the cache as-is; whatever updates the snapshot is
what reruns this.

Run: python -m pipeline.count_snapshot_sizes
"""

import argparse
import json
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from pipeline.config import INVENTORY_PATH, SNAPSHOT_SIZES_PATH, snapshot_root

STAT_KEYS = ("raw_bytes", "content_bytes", "transliterated_bytes")

FRONTMATTER_RE = re.compile(r"\A\+\+\+\s*\n.*?\n\+\+\+", re.S)
# One file in 2287 carries these OCR control markers; cheap to strip everywhere.
CONTROL_JUNK_RE = re.compile(r"\?R\?\d\?\d")
# Snapshot bodies open with a "[[<title>\tSource: [EB](url)]]" header and wrap
# the text in \[ ... \]; none of that is the text itself.
SOURCE_HEADER_RE = re.compile(r"\A\s*\[\[.*?\]\]", re.S)
MARKDOWN_NOISE_RE = re.compile(r"\\\[|\\\]|\*\*|^\s*[-—_]{3,}\s*$", re.M)

_transliterator = None


def _get_transliterator():
    """skrutable is slow to import, so each pool worker builds one lazily."""
    global _transliterator
    if _transliterator is None:
        from skrutable.transliteration import Transliterator
        _transliterator = Transliterator(from_scheme="DEV", to_scheme="IAST")
    return _transliterator


def clean_body(text: str) -> str:
    body = FRONTMATTER_RE.sub("", text)
    body = SOURCE_HEADER_RE.sub("", body)
    body = CONTROL_JUNK_RE.sub("", body)
    body = MARKDOWN_NOISE_RE.sub("", body)
    return body.strip()


def measure(args: tuple[str, str]) -> tuple[str, dict]:
    """Worker: read one book and return its three byte figures."""
    book_id, path = args
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    raw = FRONTMATTER_RE.sub("", text)
    content = clean_body(text)

    stats = {
        "raw_bytes": len(raw.encode("utf-8")),
        "content_bytes": len(content.encode("utf-8")),
        "transliterated_bytes": 0,
    }
    if content:
        iast = _get_transliterator().transliterate(content)
        stats["transliterated_bytes"] = len(iast.encode("utf-8"))
    return book_id, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    parser.add_argument("--out", type=Path, default=SNAPSHOT_SIZES_PATH)
    parser.add_argument("--snapshot", help="override the snapshot directory")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()

    if not args.inventory.exists():
        raise SystemExit(f"missing {args.inventory}; run `make parse` first.")

    records = [json.loads(line) for line in args.inventory.open(encoding="utf-8")]
    root_dir = snapshot_root(args.snapshot)
    jobs = [(r["book_id"], str(root_dir / r["path"])) for r in records]

    print(f"measuring {len(jobs)} books with DEV->IAST...")

    sizes: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for done, (book_id, stats) in enumerate(
                pool.map(measure, jobs, chunksize=16), start=1):
            sizes[book_id] = stats
            if done % 250 == 0:
                print(f"  {done}/{len(jobs)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for book_id, stats in sizes.items():
            handle.write(json.dumps({"book_id": book_id, **stats}) + "\n")

    totals = {k: sum(s[k] for s in sizes.values()) for k in STAT_KEYS}
    print(f"\nbooks:        {len(sizes)}")
    for key in STAT_KEYS:
        print(f"{key + ':':14}{totals[key]:,}")
    if totals["transliterated_bytes"]:
        ratio = totals["content_bytes"] / totals["transliterated_bytes"]
        print(f"deva:iast     {ratio:.3f}x  (sibling observes ~1.975x)")
    print(f"wrote:        {args.out}")


if __name__ == "__main__":
    main()
