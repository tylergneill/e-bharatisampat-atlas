"""Does having a PDF twin explain the bibliographic-apparatus gap?

endpoint-populations.md: 0/335 read_chapter books have a publish year, vs
1070/1952 readbook3. Two explanations were on the table --
(a) the site genuinely lacks those fields for these books, or
(b) the old template hides them from the scraper.
A third now appears: these are books with no printed edition behind them.
"""
import json
import re
from collections import Counter
from pathlib import Path

# The repo root, two levels up from notes/samples/ -- derived rather than
# hardcoded so this runs on any checkout.
REPO = str(Path(__file__).resolve().parent.parent.parent)
cat = [json.loads(l) for l in open("catalogue.jsonl", encoding="utf-8")]
pdf_ids = {r["id"] for r in cat if r["collection"] == "pdf"}
pdf_by_id = {r["id"]: r for r in cat if r["collection"] == "pdf"}

snap = [json.loads(l) for l in open(f"{REPO}/data/inventory.jsonl", encoding="utf-8")]
for r in snap:
    u = r.get("source_url") or ""
    m = re.search(r"bookid=([A-Za-z0-9+/=]+)", u)
    r["_id"] = m.group(1) if m else None
    r["_ep"] = "read_chapter" if "read_chapter" in u else "readbook3"
    r["_pdf"] = r["_id"] in pdf_ids

FIELDS = ["publish year", "publisher", "pages", "printer", "editor", "translator",
          "books contributor"]


def meta(r, f):
    v = (r.get("metadata") or {}).get(f)
    return bool(v and str(v).strip())


print("Field presence, split by endpoint AND by whether a PDF twin exists:\n")
groups = {
    ("read_chapter", False): [r for r in snap if r["_ep"] == "read_chapter" and not r["_pdf"]],
    ("read_chapter", True): [r for r in snap if r["_ep"] == "read_chapter" and r["_pdf"]],
    ("readbook3", False): [r for r in snap if r["_ep"] == "readbook3" and not r["_pdf"]],
    ("readbook3", True): [r for r in snap if r["_ep"] == "readbook3" and r["_pdf"]],
}
labels = [k[0][:9] + ("/pdf" if k[1] else "/no") for k in groups]
hdr = f"{'field':<20}" + "".join(f"{lab:>16}" for lab in labels)
print(hdr)
print(f"{'':<20}" + "".join(f"{f'n={len(v)}':>16}" for v in groups.values()))
print("-" * len(hdr))
for f in FIELDS:
    row = f"{f:<20}"
    for k, v in groups.items():
        n = sum(meta(r, f) for r in v)
        row += f"{f'{n} ({n/len(v):.0%})' if v else '-':>16}"
    print(row)

print("\n=== the key comparison ===")
print("readbook3 books WITHOUT a pdf twin vs read_chapter books without one:")
for f in ["publish year", "publisher", "pages"]:
    a = groups[("readbook3", False)]
    b = groups[("read_chapter", False)]
    na, nb = sum(meta(r, f) for r in a), sum(meta(r, f) for r in b)
    print(f"  {f:<16} readbook3-no-pdf {na}/{len(a)} ({na/len(a):.0%})   "
          f"read_chapter-no-pdf {nb}/{len(b)} ({nb/len(b):.0%})")
