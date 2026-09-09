"""The flat tree shape, shared by both builders.

`build_tree` (metadata, 11066 works) and `build_snapshot_tree` (snapshot, 2287
books with byte sizes) emit alternatives the frontend picks between, so the
shape has to be identical between them -- hence one module rather than a copy
in each. Each builder owns only its source's quirks: how to read a record and
turn it into a work.

The shape is a flat list of works plus the two axes' keys, NOT a nested tree.
Grouping happens in the browser, because the same works are presented four ways
(category flat, category grouped by author, author flat, author grouped by
category) and materializing four trees would be the same data under four
orderings.

The axes are peers, neither nested inside the other:

  category  domain -> sub_domain -> works, optionally grouped by author
  author    author -> works,                optionally grouped by category

Nesting author under category -- what the old builder did -- scatters an author
across the tree (Kalidasa's 110 works land in 7 separate domains, and authors
spanning >1 domain hold 32.5% of all authored works) and has nowhere at all to
put the 3888 works with no author.
"""

import json
from collections import defaultdict
from pathlib import Path

# Works with no author are a third of the catalogue and mostly anonymous by
# convention rather than by lost attribution -- Vedas, Upanisads, Puranas,
# stotras. They get a real bucket on the author axis; hiding them there would
# make the axis silently cover only 65% of the corpus.
UNKNOWN_AUTHOR = "unknown"

# A handful of works carry a domain but no sub-domain upstream (5 of 11066 as of
# the 2026-08-11 scrape: serials 9168, 10358, 10378, 11408, 12203). They still
# need a bucket to sit in, and an empty string renders as a nameless node -- so
# name the absence, the same way UNKNOWN_AUTHOR does on the other axis.
UNCATEGORIZED_SUB = "uncategorized"

# Byte figures, in the order snapshot_text_sizes.jsonl and the old nested tree used.
SIZE_KEYS = ("raw_bytes", "content_bytes", "transliterated_bytes")

# Bibliographic fields, sparse in both sources. Shipped only when a record
# actually has one, so the file does not carry 11066 nulls per field.
OPTIONAL_FIELDS = (
    "publisher", "publish_year", "printer", "editor", "second_editor",
    "primary_commentator", "secondary_commentator", "tertiary_commentator",
    "commentary_name", "translator", "books_contributor", "pages",
)


def summarize(works: list[dict]) -> dict:
    """Counts for a set of works, plus byte totals over whatever has them.

    `sized` is what makes the totals honest: it says how many of `count` the
    byte figures were actually computed over, so a partial total can never be
    read as a complete one. When nothing has sizes the byte keys are absent
    rather than zero -- zero would claim the works are empty.

    The same holds per key. The site-derived cache reports no `raw_bytes` (it
    measures extracted text; only the fetcher sees the response as delivered),
    so that key is omitted rather than summed to a zero that would read as a
    measurement of nothing.
    """
    stats = {
        "count": len(works),
        "text_count": sum(1 for w in works if w.get("text")),
        "pdf_count": sum(1 for w in works if w.get("pdf")),
    }
    sized = [w["sizes"] for w in works if w.get("sizes")]
    stats["sized"] = len(sized)
    if sized:
        for key in SIZE_KEYS:
            if any(key in s for s in sized):
                stats[key] = sum(s.get(key, 0) for s in sized)
    return stats


def build_category_axis(works: list[dict], by_id: dict[str, dict]) -> list[dict]:
    """domain -> sub_domain, each holding the ids of its works.

    Holds ids, not works: the flat list is the single copy of the data and an
    axis is an index into it. That is what keeps the four presentations from
    duplicating the corpus four times.
    """
    domains: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for work in works:
        sub = work.get("sub_domain") or UNCATEGORIZED_SUB
        domains[work["domain"]][sub].append(work["id"])

    out = []
    for domain in sorted(domains):
        # Uncategorized sorts last for the same reason `unknown` does: it is an
        # absence of filing, not a sub-domain competing alphabetically.
        subs = [
            {
                "title": sub,
                "work_ids": domains[domain][sub],
                "stats": summarize([by_id[i] for i in domains[domain][sub]]),
                **({"uncategorized": True} if sub == UNCATEGORIZED_SUB else {}),
            }
            for sub in sorted(domains[domain],
                              key=lambda s: (s == UNCATEGORIZED_SUB, s))
        ]
        ids = [i for s in subs for i in s["work_ids"]]
        out.append({
            "title": domain,
            "children": subs,
            "stats": summarize([by_id[i] for i in ids]),
        })
    return out


def build_author_axis(works: list[dict], by_id: dict[str, dict]) -> list[dict]:
    """author -> the ids of their works, authorless collected under `unknown`.

    Flat by construction: an author is a peer of a domain, not a leaf beneath
    one. This is the axis that makes a scattered author legible -- all 110 of
    Kalidasa's works in one place regardless of the 7 domains they are filed
    under.
    """
    authors: dict[str, list[str]] = defaultdict(list)
    for work in works:
        authors[work.get("author") or UNKNOWN_AUTHOR].append(work["id"])

    out = []
    for author in sorted(authors, key=lambda a: (a == UNKNOWN_AUTHOR, a)):
        ids = authors[author]
        entry = {
            "title": author,
            "work_ids": ids,
            "stats": summarize([by_id[i] for i in ids]),
            # How far this author's works spread across the category tree --
            # the number the old nested build could not show at all.
            "domains": sorted({by_id[i]["domain"] for i in ids}),
        }
        if author == UNKNOWN_AUTHOR:
            entry["unknown"] = True
        out.append(entry)
    return out


def build_axes(works: list[dict], source: str) -> dict:
    """Works -> the full output document, sorted and indexed both ways."""
    works.sort(key=lambda w: w["serial"])
    by_id = {w["id"]: w for w in works}
    return {
        "source": source,
        "works": works,
        "axes": {
            "category": build_category_axis(works, by_id),
            "author": build_author_axis(works, by_id),
        },
        "all_stats": summarize(works),
        "unknown_author": UNKNOWN_AUTHOR,
        "uncategorized_sub": UNCATEGORIZED_SUB,
    }


def write(tree: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(tree, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def report(tree: dict, path: Path) -> None:
    """Print the cross-checks. Same numbers from both builders, so shared."""
    stats = tree["all_stats"]
    cats, auths = tree["axes"]["category"], tree["axes"]["author"]
    scattered = sum(1 for a in auths if len(a["domains"]) > 1)
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f}M) "
          f"from {tree['source']}")
    print(f"  {stats['count']} works, {stats['text_count']} with text, "
          f"{stats['pdf_count']} with pdf")
    print(f"  category axis: {len(cats)} domains, "
          f"{sum(len(c['children']) for c in cats)} sub-domains")
    print(f"  author axis:   {len(auths)} entries "
          f"({scattered} spanning >1 domain)")
    if stats["sized"]:
        print(f"  sizes for {stats['sized']}/{stats['count']} works")
    else:
        print("  no byte sizes in this source")
