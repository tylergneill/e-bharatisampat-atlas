"""Stage 2c: work metadata -> docs/data/changelog.json.

Plots the catalogue as it accumulated, using the Unix epoch embedded in each
row's thumbnail filename (`pipeline/upload_dates.py`) -- the only signal on EBS
for *when a record was added to the site*.

**Not `publish year`.** That field is the printed edition's date and is
bibliographic; this is a repository timestamp about the digital record. The two
must never be conflated.

**Plots `added`, not `uploaded`.** `parse_metadata` runs
`upload_dates.interpolate_additions`, which replaces the measured stamp with a
serial-neighborhood estimate on the 207 records whose stamp runs more than a
year past their neighbors -- a later touch to the file, not an arrival. Reading
the raw stamp put items up to five years old in recent months (serial 1127:
stamped 2026-03, actually added 2021-04). Each period therefore also reports
`synthetic`, the count of estimated dates behind its bar, so the interface can
mark them rather than passing an estimate off as a measurement.

Three series per period, because the collections overlap and the format mix is
the interesting part:

    text only  -- Unicode text, no PDF           1645 works
    both       -- the same work in both          3912 works
    pdf only   -- scan only, no searchable text  5509 works

Two measures ride along per period, and they are not interchangeable.
`*_chars` is Devanagari characters, which is what this atlas's own chart reads;
`*_iast_bytes` is `transliterated_bytes`, the script-neutral measure
`all_stats` publishes and the only one a sibling collection can add to its own
-- Devanagari costs ~3 bytes a character, so a Devanagari collection measured
in raw bytes looks larger than a roman one holding the same works.

Works whose fetched text holds no Devanagari **do not count as text-bearing**,
matching `build_tree`, which drops the reader endpoint for exactly those (66
works as of 2026-08-26). Both files reach that verdict through
`build_tree.load_sizes`, so neither can drift from the other.

Counted by **distinct work** (11066). The bands come from each work's own
metadata page (`text` / `pdf`), not from which listing it appeared in: the
listings under-report, filing 1365 works under `pdf` alone whose metadata page
offers both readers (checked against 40 cached pages, 40/40 carrying both).
That is why `both` is 3912 here and not the 2554 a listing-derived count gives.

A fourth series tracks how much of each period the local snapshot actually
holds, which is what makes the ~45% scraper failure visible as a time series
rather than a single number.

**Monthly is the published granularity**, and it is a cross-atlas contract
rather than a local preference: sagara-sangama plots all three collections on
one time axis, and a yearly series there is a straight line between Decembers
laid over its neighbours' real shape. The frontend groups months into quarters
or years at render time, so publishing the finest grain costs nothing and the
reader still chooses. `--granularity year` remains for a quick local look;
what ships is months.

Run: python -m pipeline.build_changelog [--granularity month|year]
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pipeline.audit import SERIAL_BAND_WIDTH, serial_band_rows
from pipeline.build_tree import load_sizes as load_work_sizes
from pipeline.config import (DOCS_DATA_DIR, INVENTORY_PATH, METADATA_PATH,
                            TEXT_SIZES_PATH)

CHANGELOG_PATH = DOCS_DATA_DIR / "changelog.json"

BANDS = ("text_only", "both", "pdf_only")

# The label a work with no `domain` carries in the per-category series. Empty
# string would collide with "absent" once the counts round-trip through JSON.
NO_DOMAIN = "(none)"


def pct(delta: float, base: float) -> float:
    return (delta / base * 100.0) if base else 0.0


def empty_bucket() -> dict:
    return {**{b: 0 for b in BANDS},
            # Devanagari characters, per band, for the chart's `size` measure.
            # Parallel to the counts so both measures stack the same way.
            **{f"chars_{b}": 0 for b in BANDS},
            # IAST bytes, per band. `transliterated_bytes` is the measure the
            # tree publishes and the only one comparable across the sibling
            # atlases -- Devanagari costs ~3 bytes a character, so a character
            # count and a raw byte count each make this collection look like a
            # different size than a roman-script one holding the same works.
            # Carried here so the growth series is in the same unit as
            # `all_stats.transliterated_bytes` rather than needing a ratio
            # assumed downstream.
            **{f"iast_{b}": 0 for b in BANDS},
            "count": 0, "chars": 0, "iast": 0, "measured": 0, "in_snapshot": 0,
            "synthetic": 0}


def load_sizes(path: Path) -> dict[int, dict]:
    """serial -> {chars, iast}, for works whose text has been fetched.

    Completed books only -- `count_sizes` excludes anything stopped at the
    chunk ceiling, and a partial book published as a finished measurement is
    the exact failure that file guards against. Missing file is not an error:
    the size measure then reports zero everywhere and the page says so.

    Both measures come off the same row so they can never drift apart:
    `devanagari_chars` drives this atlas's own chart, `transliterated_bytes`
    is what the tree publishes and what a cross-atlas comparison needs.
    """
    sizes: dict[int, dict] = {}
    if not path.exists():
        return sizes
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if record.get("partial"):
            continue
        serial = record.get("serial")
        chars = record.get("devanagari_chars")
        if serial is None or chars is None:
            continue
        sizes[int(serial)] = {
            "chars": int(chars),
            "iast": int(record.get("transliterated_bytes") or 0),
        }
    return sizes


def band_of(record: dict, empty: set[str] = frozenset()) -> str | None:
    """Which format band a work sits in, from its own metadata page.

    `text` holds the reader endpoint, `pdf` a bare true; absence means the
    format does not exist for the work. Every work has at least one, so None
    means a record that carries neither -- which should not happen.

    A work in `empty` is treated as having no text, exactly as `build_tree`
    treats it: the fetch came back with no Devanagari at all, so the reader
    endpoint opens onto nothing. `build_tree.work_from_metadata` drops the
    endpoint there, which is why `all_stats.text_count` is 5491 and not the
    5557 `metadata.json` claims. Applying the same rule here is what keeps the
    two files describing one collection -- without it this series ended 66
    works above the total the tree publishes, and a reader comparing the chart
    to the table would have found the chart higher for no stated reason. Such
    a work keeps its entry and its PDF; it simply stops counting as text.
    """
    has_text = bool(record.get("text")) and record["id"] not in empty
    has_pdf = bool(record.get("pdf"))
    if has_text and has_pdf:
        return "both"
    if has_text:
        return "text_only"
    return "pdf_only" if has_pdf else None


def date_coverage(records: list[dict]) -> dict:
    """Summarize how many works carry a date, and how many of those are estimates.

    The decodability tripwire itself lives in `upload_dates.coverage` and runs
    in `parse_metadata`, where the thumbnail filenames still exist. By this
    stage they are gone -- only the decoded dates survive -- so what is
    reported here is date presence over *works*, not filename convention over
    listing rows.
    """
    dated = [r["added"] for r in records if r.get("added")]
    synthetic = sum(1 for r in records if r.get("added_synthetic"))
    total = len(records) or 1
    return {
        "total": len(records),
        "dated": len(dated),
        "pct": len(dated) / total * 100.0,
        "synthetic": synthetic,
        "min": min(dated) if dated else None,
        "max": max(dated) if dated else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH)
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    parser.add_argument("--sizes", type=Path, default=TEXT_SIZES_PATH)
    parser.add_argument("--out", type=Path, default=CHANGELOG_PATH)
    parser.add_argument("--granularity", choices=("year", "month"),
                        default="month")
    args = parser.parse_args()

    if not args.metadata.exists():
        raise SystemExit(
            f"missing {args.metadata}; run `make parse-metadata` first.")

    records = json.loads(args.metadata.read_text(encoding="utf-8"))

    cov = date_coverage(records)
    print(f"dated works: {cov['dated']}/{cov['total']} ({cov['pct']:.1f}%)  "
          f"{cov['min']} -> {cov['max']}")
    print(f"  {cov['synthetic']} interpolated from serial neighborhood")
    if cov["pct"] < 95:
        print("  WARNING: coverage below 95% -- suspect a naming change, "
              "not a stalled site.")

    snapshot_ids: set[str] = set()
    if args.inventory.exists():
        for line in args.inventory.open(encoding="utf-8"):
            record = json.loads(line)
            # Join on the base64 id, which both sides carry verbatim.
            # `metadata.json` has no decoded form to match `book_id` against.
            snapshot_ids.add(record.get("book_id_encoded"))

    sizes = load_sizes(args.sizes)
    # The same verdict `build_tree` reaches, from the same loader, so the two
    # cannot disagree about which works have a text worth counting.
    _, empty = load_work_sizes(args.sizes)
    scrapeable_total = sum(1 for r in records
                           if r.get("text") and r["id"] not in empty)
    print(f"measured text: {len(sizes)}/{scrapeable_total} text-bearing works"
          if sizes else
          "no text sizes on disk -- the chart's `size` measure will read zero")

    buckets: dict[str, dict] = defaultdict(empty_bucket)
    # Per-period counts by category, kept beside `buckets` rather than inside
    # them: every field of a bucket is summed into a running `cumulative`
    # total by name, and a nested dict does not add. This one is a plain
    # {period: {domain: count}} of arrivals, and the frontend accumulates it
    # if it wants a cumulative view.
    domain_buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int))
    domain_totals: dict[str, int] = defaultdict(int)
    undated = bandless = 0
    for record in records:
        when = record.get("added")
        if not when:
            undated += 1
            continue
        band = band_of(record, empty)
        if band is None:
            bandless += 1
            continue
        key = when[:4] if args.granularity == "year" else when[:7]
        bucket = buckets[key]
        bucket[band] += 1
        bucket["count"] += 1
        # An empty work's byte figures go with its endpoint: `build_tree`
        # drops both, because 3 KB of page furniture measured as text is what
        # makes an empty record look real.
        measures = sizes.get(record.get("serial")) if band != "pdf_only" else None
        if measures:
            bucket[f"chars_{band}"] += measures["chars"]
            bucket["chars"] += measures["chars"]
            bucket[f"iast_{band}"] += measures["iast"]
            bucket["iast"] += measures["iast"]
            bucket["measured"] += 1
        if record.get("added_synthetic"):
            bucket["synthetic"] += 1
        if record["id"] in snapshot_ids:
            bucket["in_snapshot"] += 1
        domain = record.get("domain") or NO_DOMAIN
        domain_buckets[key][domain] += 1
        domain_totals[domain] += 1

    intervals = []
    cumulative = empty_bucket()
    for index, key in enumerate(sorted(buckets), start=1):
        bucket = buckets[key]
        before = dict(cumulative)
        for field in cumulative:
            cumulative[field] += bucket[field]

        # Coverage is measured against the *Unicode* works only. The snapshot
        # is a text scrape, so a pdf-only work was never in scope and counting
        # it as "missing" would blame the scraper for the site's format mix --
        # which is what dragged the rate to 2% for 2026, a heavily-PDF year.
        held = bucket["in_snapshot"]
        scrapeable = bucket["text_only"] + bucket["both"]
        intervals.append({
            "id": index,
            "period": key,
            "date": f"{key}-12-31T23:59:59Z" if args.granularity == "year"
                    else f"{key}-01T00:00:00Z",
            "added": {b: bucket[b] for b in BANDS},
            "added_count": bucket["count"],
            "cumulative": {b: cumulative[b] for b in BANDS},
            "cumulative_count": cumulative["count"],
            # Works carrying a text, cumulatively -- `text_only` + `both`,
            # which is the definition `all_stats.text_count` uses. Published
            # outright rather than left to be summed downstream, so the one
            # figure a cross-atlas reader wants is stated by the atlas that
            # owns it instead of assembled from bands whose meaning is local.
            "cumulative_text_count": (cumulative["text_only"]
                                      + cumulative["both"]),
            "added_text_count": bucket["text_only"] + bucket["both"],
            # The same two stacks measured in Devanagari characters instead of
            # works, for the chart's `size` toggle. `pdf_only` is structurally
            # zero -- a scan carries no text to measure -- and that is the
            # point of the measure, not a gap in it. `measured` says how many
            # of the period's works contributed, so the interface can mark a
            # period whose text is not yet fetched.
            "added_chars": {b: bucket[f"chars_{b}"] for b in BANDS},
            "added_chars_total": bucket["chars"],
            "cumulative_chars": {b: cumulative[f"chars_{b}"] for b in BANDS},
            "cumulative_chars_total": cumulative["chars"],
            # The same stacks in IAST bytes -- the measure `all_stats`
            # publishes, and the one a sibling atlas can add to its own.
            # `cumulative_iast_bytes_total` is the series that belongs on a
            # cross-collection growth chart; the chars figures above stay for
            # this atlas's own interface, which reads in Devanagari.
            "added_iast_bytes": {b: bucket[f"iast_{b}"] for b in BANDS},
            "added_iast_bytes_total": bucket["iast"],
            "cumulative_iast_bytes": {b: cumulative[f"iast_{b}"]
                                      for b in BANDS},
            "cumulative_iast_bytes_total": cumulative["iast"],
            "measured": bucket["measured"],
            "cumulative_measured": cumulative["measured"],
            # How many of this period's works sit here on an interpolated date
            # rather than a measured one. The interface marks these; without
            # the count it would have to treat every bar as measured.
            "synthetic": bucket["synthetic"],
            "cumulative_synthetic": cumulative["synthetic"],
            # The snapshot's coverage of this period, over Unicode works only
            # -- the scraper-failure series. A flat rate across years is the
            # finding; a slope would instead have meant the scrape was stale.
            "in_snapshot": held,
            "scrapeable": scrapeable,
            "in_snapshot_pct": pct(held, scrapeable),
            "missing": scrapeable - held,
            "cumulative_in_snapshot": cumulative["in_snapshot"],
            # What arrived in this period, by category. Sparse -- a category
            # the period did not touch is absent rather than zero, which at
            # 33 categories over 67 months is most of the grid. Arrivals only:
            # a cumulative view is a running sum of these, and publishing both
            # would double a file the page loads on every visit.
            "added_domains": dict(sorted(domain_buckets[key].items(),
                                         key=lambda kv: -kv[1])),
            "old_count": before["count"],
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "granularity": args.granularity,
        "generated": datetime.now(timezone.utc).replace(
            microsecond=0).isoformat().replace("+00:00", "Z"),
        "coverage": cov,
        "undated_works": undated,
        "total_works": len(records),
        "snapshot_works": len(snapshot_ids),
        # The serial bands, on the time axis. Same rows the About page's
        # serial table publishes, from the same function in `audit` rather
        # than a second copy of the rule -- the band width and the
        # median-`added` end date are decisions that must not drift between
        # the table and the chart that plots it.
        #
        # `unused` is the band's complement against its own width: serial
        # numbers the site issued and never filled. That is the sparseness
        # the chart exists to show, and it is only visible against the width,
        # so it is computed here rather than left to be inferred.
        "serial_bands": [{**row, "unused": SERIAL_BAND_WIDTH - row["works"]}
                         for row in serial_band_rows(records)],
        # Every category, largest first. The frontend names the leading few
        # and folds the tail into "other" -- how many it names is a palette
        # question, so this file publishes the whole ranking and does not
        # choose. Totals are over dated works only, matching the periods.
        "domains": [{"name": name, "count": count} for name, count
                    in sorted(domain_totals.items(), key=lambda kv: -kv[1])],
        "periods": intervals,
    }
    with args.out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))

    print(f"undated works: {undated}")
    if bandless:
        print(f"WARNING: {bandless} works carry neither a text nor a pdf reader")
    print(f"periods: {len(intervals)}")
    for rec in intervals:
        a = rec["added"]
        print(f"  {rec['period']}: +{rec['added_count']:>5} "
              f"(text {a['text_only']:>4}, both {a['both']:>4}, "
              f"pdf {a['pdf_only']:>5})  "
              f"est {rec['synthetic']:>3}  "
              f"snapshot {rec['in_snapshot']:>4}/{rec['scrapeable']:>4} unicode "
              f"= {rec['in_snapshot_pct']:.0f}%")
    print(f"wrote: {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
