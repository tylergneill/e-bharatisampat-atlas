"""Does the snapshot's coverage gap correlate with when records were added?

If missing books cluster AFTER the upstream scrape, the gap is staleness.
If they are spread evenly across upload dates, it is scraper failure.
"""
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

# The repo root, two levels up from notes/samples/ -- derived rather than
# hardcoded so this runs on any checkout.
REPO = str(Path(__file__).resolve().parent.parent.parent)
cat = [json.loads(l) for l in open("catalogue.jsonl", encoding="utf-8")]
snap_ids = {json.loads(l)["book_id_encoded"]
            for l in open(f"{REPO}/data/inventory.jsonl", encoding="utf-8")}

TS = re.compile(r"ebharati-(\d{10})")


def ts(rec):
    m = TS.match((rec.get("thumbnail") or "").split("/")[-1])
    return int(m.group(1)) if m else None


# The snapshot only ever covered the Unicode collection, so restrict to it --
# comparing against PDF-only books would just re-measure that fact.
uni = [r for r in cat if r["collection"] == "unicode"]
have = [r for r in uni if r["id"] in snap_ids]
miss = [r for r in uni if r["id"] not in snap_ids]
print(f"Unicode collection: {len(uni)}   in snapshot: {len(have)}   missing: {len(miss)}")

hs = [ts(r) for r in have if ts(r)]
ms = [ts(r) for r in miss if ts(r)]
print(f"  with timestamp:  have {len(hs)}/{len(have)} ({len(hs)/len(have):.0%})   "
      f"missing {len(ms)}/{len(miss)} ({len(ms)/len(miss):.0%})")


def year(x):
    return dt.datetime.utcfromtimestamp(x).year


print("\n           in snapshot        missing      % missing")
yrs = sorted(set(map(year, hs + ms)))
ch, cm = Counter(map(year, hs)), Counter(map(year, ms))
for y in yrs:
    h, m = ch.get(y, 0), cm.get(y, 0)
    pct = f"{m/(h+m):.0%}" if h + m else "-"
    print(f"  {y}   {h:8d}   {m:12d}   {pct:>10}")

if hs and ms:
    print(f"\n  median upload date, in snapshot: "
          f"{dt.datetime.utcfromtimestamp(sorted(hs)[len(hs)//2]).date()}")
    print(f"  median upload date, missing:     "
          f"{dt.datetime.utcfromtimestamp(sorted(ms)[len(ms)//2]).date()}")
    print(f"  latest in snapshot:              "
          f"{dt.datetime.utcfromtimestamp(max(hs)).date()}")
    print(f"  missing records added AFTER that: "
          f"{sum(1 for x in ms if x > max(hs))} of {len(ms)}")
