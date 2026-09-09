"""Do the texts differ between our scrape and the upstream snapshot -- and why?

Two captures of the same books, years apart, by two different scrapers. A
difference could be the corpus changing upstream, or it could be the two
scrapers extracting differently. This separates them.

Compares three ways, coarse to fine:

  1. bytes           content_bytes on each side, computed the same way
  2. Devanagari      the script characters only -- immune to markup, whitespace,
                     boilerplate and roman-script apparatus, so a difference
                     here is a difference in the TEXT
  3. shared prefix   how far the two agree before diverging, which separates
                     "same text, different header" from "genuinely edited"

(2) is load-bearing. A byte delta conflates real change with the two scrapers'
different extraction; the Devanagari count does not. (3) is what makes a
divergence interpretable: a prefix of 0 means they disagree from the first
character, which is a boilerplate difference, not an edit.

Reads `data/text_sizes.jsonl` (complete books only -- run `make count-sizes`
first), joins to the snapshot via `snapshot_inventory.jsonl` (serial ->
book_id -> path), and writes per-book detail to
`data/snapshot_vs_scrape.jsonl`, sorted by absolute delta.

Only books present in BOTH are comparable, and the snapshot covers 21% of the
catalogue -- expect to lose a quarter of any sample to that.

Run: python notes/samples/scrape-vs-snapshot.py
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

# The repo root, two levels up from notes/samples/ -- derived rather than
# hardcoded so this runs on any checkout.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
from pipeline.config import snapshot_root  # noqa: E402

DEVA = re.compile(r"[ऀ-ॿ]")


def load(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def deva_only(text):
    """Just the Devanagari, NFC-normalized: the comparable core of a text.

    NFC matters -- the two scrapers need not agree on whether a vowel sign is
    composed or decomposed, and an unnormalized compare would read that as a
    textual difference."""
    return "".join(DEVA.findall(unicodedata.normalize("NFC", text)))


def common_prefix(a, b):
    """Length of the shared opening, by bisection rather than a char loop --
    these are hundreds of thousands of characters."""
    lo, hi = 0, min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def main():
    ours = {r["serial"]: r for r in load(REPO / "data/text_sizes.jsonl")
            if r.get("serial") is not None}
    if not ours:
        raise SystemExit(
            "no completed books in data/text_sizes.jsonl -- run `make fetch-text` "
            "and `make count-sizes` first."
        )
    by_serial = {r["serial"]: r
                 for r in load(REPO / "data/snapshot_inventory.jsonl")
                 if r.get("serial") is not None}
    if not by_serial:
        raise SystemExit(
            "no snapshot inventory -- run `make parse` first (needs the "
            "raw_etexts checkout; see pipeline/config.snapshot_root)."
        )

    snap_root = snapshot_root()
    rows, missing = [], []

    for serial, mine in sorted(ours.items()):
        inv = by_serial.get(serial)
        if not inv:
            missing.append(serial)
            continue
        snap_path = snap_root / inv["path"]
        our_path = REPO / "data/fulltext_cache" / mine["file"]
        if not snap_path.exists() or not our_path.exists():
            missing.append(serial)
            continue

        snap_d = deva_only(snap_path.read_text(encoding="utf-8", errors="replace"))
        our_d = deva_only(our_path.read_text(encoding="utf-8", errors="replace"))

        rows.append({
            "serial": serial,
            "title": inv.get("title") or "",
            "reader": mine.get("reader", "?"),
            "chunks": mine.get("chunks", 0),
            "our_bytes": mine["content_bytes"],
            "snap_bytes": snap_path.stat().st_size,
            "our_deva": len(our_d),
            "snap_deva": len(snap_d),
            "identical": snap_d == our_d,
            "shared_prefix": common_prefix(snap_d, our_d),
            "our_file": mine["file"],
            "snap_path": inv["path"],
        })

    print(f"compared: {len(rows)}   (skipped {len(missing)}: not in snapshot)")
    if not rows:
        return
    print(f"byte-identical in Devanagari: "
          f"{sum(r['identical'] for r in rows)}/{len(rows)}")

    # Grouped by reader, because that is where the systematic split showed up.
    print()
    for reader in sorted({r["reader"] for r in rows}):
        group = [r for r in rows if r["reader"] == reader]
        deltas = [r["our_deva"] - r["snap_deva"] for r in group]
        ratios = [r["our_deva"] / r["snap_deva"] for r in group if r["snap_deva"]]
        print(f"  {reader:>12}: {len(group):>3} books, "
              f"delta {min(deltas):>+8} .. {max(deltas):>+8}, "
              f"ratio {min(ratios):.3f} .. {max(ratios):.3f}")

    print()
    print(f"{'serial':>7} {'reader':>12} {'our deva':>9} {'snap deva':>10} "
          f"{'delta':>9} {'ratio':>6} {'prefix':>8}  title")
    for r in sorted(rows, key=lambda r: r["our_deva"] - r["snap_deva"]):
        delta = r["our_deva"] - r["snap_deva"]
        ratio = (r["our_deva"] / r["snap_deva"]) if r["snap_deva"] else float("inf")
        pct = f"{ratio:5.2f}x" if ratio != float("inf") else "  inf"
        print(f"{r['serial']:>7} {r['reader']:>12} {r['our_deva']:>9} "
              f"{r['snap_deva']:>10} {delta:>+9} {pct} {r['shared_prefix']:>8}"
              f"{'=' if r['identical'] else ' '}  {r['title'][:28]}")

    out = REPO / "data" / "snapshot_vs_scrape.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in sorted(rows, key=lambda r: abs(r["our_deva"] - r["snap_deva"]),
                        reverse=True):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nper-book detail -> {out}")


if __name__ == "__main__":
    main()
