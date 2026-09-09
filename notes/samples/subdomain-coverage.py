"""Re-derive the domain / sub-domain coverage figures in site-structure.md.

Reads docs/data/metadata.json only; no network, no snapshot. Run from the repo
root: python notes/samples/subdomain-coverage.py
"""

import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

recs = json.loads((ROOT / "docs/data/metadata.json").read_text())

domains = {r.get("domain") for r in recs}
pairs = {(r.get("domain"), r.get("sub_domain")) for r in recs}
no_domain = [r for r in recs if not r.get("domain")]
no_sub = [r for r in recs if not r.get("sub_domain")]

print(f"works                    {len(recs)}")
print(f"distinct domains         {len(domains)}")
print(f"distinct (dom, sub)      {len(pairs)}")
print(f"missing domain           {len(no_domain)}")
print(f"missing sub-domain       {len(no_sub)}")
print()

# Is a missing sub-domain a hole in a filled domain, or a domain with no
# second level at all? That distinction is the whole finding.
by_domain = collections.Counter(r.get("domain") for r in recs)
undivided = [d for d in domains if all(not r.get("sub_domain")
                                       for r in recs if r.get("domain") == d)]

print(f"domains with NO sub-domain on any work: {len(undivided)}")
for d in undivided:
    print(f"    {d}  ({by_domain[d]} works)")
print()

print("domains holding a work with no sub-domain:")
for dom in sorted({r.get("domain") for r in no_sub}):
    subs = collections.Counter(
        r.get("sub_domain") or "<NONE>"
        for r in recs
        if r.get("domain") == dom
    )
    missing = subs["<NONE>"]
    total = by_domain[dom]
    print(f"    {dom}  {missing}/{total} missing ({missing / total:.1%})")
    for name, n in subs.most_common():
        print(f"        {n:5d}  {name}")
print()

print("the works themselves:")
for r in sorted(no_sub, key=lambda r: int(r.get("serial", 0))):
    print(f"    {r.get('serial')}  {r.get('domain')}  |  {r.get('title')}")
