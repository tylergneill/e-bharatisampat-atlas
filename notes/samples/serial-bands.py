"""Serial-band analysis: dates, formats, and text sizes across the serial axis.

Written 2026-08-22. Produces the table in `../serial-bands.md` — do not edit
that table by hand; rerun this and paste.

Reads three local files, fetches nothing:

    docs/data/metadata.json     serial, uploaded, publish_year, text, pdf
    data/text_sizes.jsonl       devanagari_chars for COMPLETED books only
    data/text_open_books.jsonl  the still-open books, excluded from sizes

Run from the atlas root:

    python notes/samples/serial-bands.py            # the report table
    python notes/samples/serial-bands.py --gaps     # serial gaps + occupancy
    python notes/samples/serial-bands.py --edges    # fine-grained era edges
    python notes/samples/serial-bands.py --rho      # serial/uploaded agreement

Band edges are NOT round numbers. They follow the format transitions found by
--edges (PDF drops at 2450, returns at 4550) and the 186-serial hole at
4370-4557. Changing them to decade boundaries hides the finding.
"""

import argparse
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Era boundaries, from --edges. See the module docstring before changing.
ERAS = [
    (120, 499), (500, 999), (1000, 1499), (1500, 1999), (2000, 2449),
    (2450, 2999), (3000, 3499), (3500, 3999), (4000, 4449), (4550, 4999),
    (5000, 5499), (5500, 5999), (6000, 6999), (7000, 7999), (8000, 8999),
    (9000, 9999), (10000, 10499), (10500, 11499), (11500, 12499),
    (12500, 12879),
]


def load():
    meta = json.loads((ROOT / "docs/data/metadata.json").read_text())
    sizes = {}
    with open(ROOT / "data/text_sizes.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            sizes[r["serial"]] = r
    openb = set()
    with open(ROOT / "data/text_open_books.jsonl") as fh:
        for line in fh:
            openb.add(json.loads(line).get("serial"))
    return meta, sizes, openb


def publish_year(m):
    """Bibliographic year, or None. Never conflate with `uploaded`."""
    y = str(m.get("publish_year") or "").strip()
    return int(y) if y.isdigit() and 1400 <= int(y) <= 2026 else None


def qi(values, p):
    """Index-based quantile. Works on date strings, unlike arithmetic ones."""
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, int(round((len(v) - 1) * p)))]


def report(meta, sizes, _openb):
    def k(v):
        return "—" if v is None else (f"{v/1000:.0f}k" if v >= 1000 else str(v))

    print("| serials | works | uploaded (p5 → **median** → p95) | text % | PDF % "
          "| reader | publish yr (med / n) | median chars | p90 chars | measured |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for lo, hi in ERAS:
        b = [m for m in meta if lo <= m["serial"] <= hi]
        if not b:
            continue
        ups = [m["uploaded"] for m in b if m.get("uploaded")]
        pys = [publish_year(m) for m in b if publish_year(m)]
        txt = [m for m in b if m.get("text")]
        rchap = sum(1 for m in txt if m["text"] == "read_chapter")
        pdf = sum(1 for m in b if m.get("pdf"))
        ms = [sizes[m["serial"]] for m in b if m["serial"] in sizes]
        dev = [r["devanagari_chars"] for r in ms]

        pct_text = round(100 * len(txt) / len(b))
        reader = "—" if pct_text == 0 else (
            "read_chapter" if rchap > len(b) * 0.4
            else "mixed" if rchap else "readbook3")
        print(f"| {lo}-{hi} | {len(b)} | {qi(ups,.05)} → **{qi(ups,.50)}** → "
              f"{qi(ups,.95)} | {pct_text}% | {round(100*pdf/len(b))}% | {reader} "
              f"| {int(st.median(pys)) if pys else '—'} / {len(pys)} "
              f"| {k(int(st.median(dev)) if dev else None)} "
              f"| {k(int(qi(dev,.90)) if dev else None)} | {len(ms)} |")


def gaps(meta, _sizes, _openb):
    uniq = sorted({m["serial"] for m in meta})
    print(f"works {len(meta)}  distinct serials {len(uniq)}  "
          f"range {uniq[0]}..{uniq[-1]}")
    holes = [(a, b, b - a - 1) for a, b in zip(uniq, uniq[1:]) if b - a > 1]
    print(f"unused serial slots: {sum(h[2] for h in holes)}\n")
    print("largest gaps:")
    for a, b, n in sorted(holes, key=lambda t: -t[2])[:12]:
        print(f"  {a:6d} -> {b:6d}   {n:5d} missing")
    print("\nper-500 occupancy:")
    from collections import Counter
    buck = Counter(s // 500 * 500 for s in uniq)
    for key in sorted(buck):
        print(f"  {key:6d}-{key+499:6d}  {buck[key]:5d}")


def edges(meta, _sizes, _openb):
    """Fine-grained walk. This is what located the 2450 / 4550 boundaries."""
    by = {m["serial"]: m for m in meta}
    ser = sorted(by)
    for lo, hi, step in [(2300, 2700, 50), (4300, 4800, 50),
                         (4900, 5200, 50), (120, 700, 100)]:
        print(f"\n--- {lo}-{hi} by {step} ---")
        print(f"{'range':>13} {'n':>4} {'up_med':>10} {'%text':>6} {'%pdf':>6} {'rchap':>5}")
        for s in range(lo, hi, step):
            b = [by[x] for x in ser if s <= x < s + step]
            if not b:
                continue
            ups = [m["uploaded"] for m in b if m.get("uploaded")]
            t = sum(1 for m in b if m.get("text"))
            p = sum(1 for m in b if m.get("pdf"))
            rc = sum(1 for m in b if m.get("text") == "read_chapter")
            print(f"{s:6d}-{s+step-1:6d} {len(b):4d} {qi(ups,.50) or '-':>10} "
                  f"{100*t/len(b):6.1f} {100*p/len(b):6.1f} {rc:5d}")


def rho(meta, _sizes, _openb):
    """Serial/uploaded agreement — the open item in `../scratch/todo.md`."""
    pairs = [(m["serial"], m["uploaded"]) for m in meta if m.get("uploaded")]
    n = len(pairs)
    srank = {s: i for i, (s, _) in enumerate(sorted(pairs, key=lambda t: t[0]))}
    urank = {s: i for i, (s, _) in enumerate(sorted(pairs, key=lambda t: (t[1], t[0])))}
    d2 = sum((srank[s] - urank[s]) ** 2 for s, _ in pairs)
    print(f"Spearman rho(serial, uploaded) = {1 - 6*d2/(n*(n*n-1)):.4f}  n={n}")
    seq = [u for _, u in sorted(pairs)]
    inv = sum(1 for a, b in zip(seq, seq[1:]) if b < a)
    print(f"adjacent-serial date inversions: {inv}/{len(seq)-1} "
          f"({100*inv/(len(seq)-1):.1f}%)")


def coverage(meta, sizes, openb):
    """Per-band completion, to tell 'not text-bearing' from 'not yet fetched'."""
    tb = {m["serial"] for m in meta if m.get("text")}
    print(f"text-bearing {len(tb)}  measured {len(sizes)}  open {len(openb)}\n")
    print(f"{'band':>13} {'tb':>5} {'done':>5} {'open':>5} {'%done':>6}")
    for lo, hi in ERAS:
        band = [s for s in tb if lo <= s <= hi]
        if not band:
            continue
        d = sum(1 for s in band if s in sizes)
        o = sum(1 for s in band if s in openb)
        print(f"{lo:5d}-{hi:5d} {len(band):5d} {d:5d} {o:5d} "
              f"{100*d/len(band):6.1f}")


MODES = {"report": report, "gaps": gaps, "edges": edges, "rho": rho,
         "coverage": coverage}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for name in MODES:
        ap.add_argument(f"--{name}", action="store_true")
    args = ap.parse_args()
    chosen = [n for n in MODES if getattr(args, n)] or ["report"]
    for i, name in enumerate(chosen):
        if i:
            print()
        MODES[name](*load())
