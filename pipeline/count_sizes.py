"""Stage 3b: data/fulltext_cache/ -> data/text_sizes.jsonl. No network.

The site-derived twin of `count_snapshot_sizes.py`, which does the same job for
the third-party snapshot. Both measure a book three ways and write one record
per book; they differ only in where the text comes from:

    count_snapshot_sizes.py   raw_etexts snapshot  -> snapshot_text_sizes.jsonl
    count_sizes.py            our fulltext_cache   -> text_sizes.jsonl

**Why this exists separately from the fetcher.** `fetch_text.py` measures each
book as it completes it, which is convenient but makes the sizes a side effect
of network work. That is wrong in two ways: it means a change to how bytes are
counted would need 5557 refetches, and it means `text_sizes.jsonl` cannot be
rebuilt on a machine that has the cache but has not run the fetcher. Sizes are
a pure function of the cached text, so deriving them is local, repeatable, and
costs nothing.

That split is the same one the snapshot side already uses, and the same reason
tier 2 stores raw HTML rather than parsed fields: keep what the site served,
derive numbers from it locally, and never pay the network twice.

**Only complete books are measured.** `text_fetch_log.jsonl` records how many
chunks each cached file holds and whether the book ended; a book stopped at the
chunk ceiling has real text on disk but is not finished, and publishing its
bytes would read as a complete measurement. Those are skipped and reported.

Run: python -m pipeline.count_sizes
     python -m pipeline.count_sizes --include-partial   # measure them anyway
"""

import argparse
import json
from pathlib import Path

from pipeline.config import (FULLTEXT_CACHE_DIR, METADATA_PATH, TEXT_LOG_PATH,
                             TEXT_SIZES_PATH)
from pipeline.progress import LiveCounter
from pipeline.text_measure import (devanagari_chars, load_progress,
                                   strip_furniture, to_iast)

STAT_KEYS = ("raw_bytes", "content_bytes", "transliterated_bytes")

# Journal field -> sizes field, for figures this stage cannot derive from
# cached text and so must carry forward verbatim. The journal calls the
# response size `bytes`; the sizes file has always called it `raw_bytes`.
#
# `raw_bytes` measures the response AS DELIVERED, markup included, which only
# the fetcher ever sees -- the cache holds extracted text, so no offline rerun
# can reproduce it. `unproofread` is a property of the book, recorded by the
# pass that checked.
#
# `toc`/`divisions`/`measured_at` are NOT here: they were written by an older
# fetcher into the sizes file and never appear in the journal, so there is
# nothing to carry them from. See notes/scratch/todo.md.
JOURNAL_CARRIED = {"bytes": "raw_bytes", "unproofread": "unproofread"}


def measure(text: str) -> dict:
    """The three byte counts, matching count_snapshot_sizes so the two trees'
    figures mean the same thing.

    `raw_bytes` is absent here on purpose: it describes the response as
    delivered, markup included, which only the fetcher ever sees. The cache
    holds extracted text, so this stage reports the two counts that are
    genuinely functions of it and leaves raw_bytes to the fetch journal.
    """
    deva = devanagari_chars(text)
    content_bytes = len(text.encode("utf-8"))
    return {
        "content_bytes": content_bytes,
        # This is the figure the Atlas displays, so the site's own page
        # chrome is stripped before measuring -- see `strip_furniture`. A book
        # with no Devanagari has nothing to transliterate; some readers serve
        # roman-script records or whole romanized editions (serials 584, 2367,
        # 5630), and those keep their content size.
        "transliterated_bytes": (len(to_iast(strip_furniture(text)).encode("utf-8"))
                                 if deva else content_bytes),
        "devanagari_chars": deva,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", type=Path, default=FULLTEXT_CACHE_DIR)
    parser.add_argument("--log", type=Path, default=TEXT_LOG_PATH)
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH)
    parser.add_argument("--out", type=Path, default=TEXT_SIZES_PATH)
    parser.add_argument("--serials", type=str,
                        help="measure only these serials (comma-separated) and "
                             "MERGE them into the existing sizes file, leaving "
                             "every other row untouched. For the handful of "
                             "books a repair run just fetched: a full pass is "
                             "~25 min of transliteration to re-derive rows "
                             "that have not changed.")
    parser.add_argument("--include-partial", action="store_true",
                        help="also measure books that stopped at the chunk "
                             "ceiling; their bytes are a lower bound, not a "
                             "measurement, and are flagged `partial: true`")
    args = parser.parse_args()

    if not args.cache.is_dir():
        raise SystemExit(
            f"no cache at {args.cache}; run `make fetch-text` first -- this "
            f"stage only re-derives sizes from text already fetched."
        )

    progress = load_progress(args.log)
    if not progress:
        raise SystemExit(
            f"no fetch journal at {args.log}. It records which books are "
            f"complete, so without it there is no way to tell a finished book "
            f"from one stopped at the chunk ceiling."
        )

    # serial -> id/reader, so the output carries the same keys the fetcher wrote
    by_serial = {}
    if args.metadata.exists():
        for record in json.loads(args.metadata.read_text(encoding="utf-8")):
            if record.get("serial"):
                by_serial[record["serial"]] = record

    # The journal names the file for each serial, which is the only reliable
    # link: filenames embed a transliterated title and cannot be reconstructed.
    #
    # The rest of each journal row is kept too. Several fields are recorded by
    # the FETCH and are not recoverable from cached text -- `raw_bytes` is the
    # response as delivered, and `toc`/`divisions` come from the reader's own
    # chapter markup, which the cache does not preserve. Rebuilding the sizes
    # file without them silently discarded a measurement nothing offline can
    # reproduce; see JOURNAL_CARRIED.
    #
    # Later lines win, matching `load_progress`. A `flag-only` pass carries no
    # measurement of its own -- it re-journals a book without refetching, with
    # `bytes: 0` -- so its blanks must not overwrite the real pass's figures.
    files, journal = {}, {}
    for line in args.log.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        serial = entry.get("serial")
        if serial is None:
            continue
        if entry.get("file"):
            files[serial] = entry["file"]
        if entry.get("ending") == "flag-only":
            # Keep only the flag it exists to record.
            if "unproofread" in entry:
                journal.setdefault(serial, {})["unproofread"] = entry["unproofread"]
            continue
        carried = {dest: entry[src] for src, dest in JOURNAL_CARRIED.items()
                   if entry.get(src) is not None}
        journal.setdefault(serial, {}).update(carried)

    # This stage walks a multi-GB cache one book at a time and the largest
    # books take seconds each to transliterate, so a silent run is
    # indistinguishable from a wedged one for minutes at a stretch -- which is
    # exactly the report that prompted this. One pinned line carries the count,
    # rate and ETA, plus the book being measured RIGHT NOW: a stall leaves the
    # culprit's name on screen, and the ETA says whether it is a stall at all.
    #
    # The total counts only what will actually be measured, so the bar ends
    # where it says it will; incomplete books are skipped before the counter
    # ever sees them.
    serials = sorted(progress)
    if args.serials:
        wanted = {int(s) for s in args.serials.replace(",", " ").split()}
        unknown = wanted - set(serials)
        if unknown:
            raise SystemExit(
                f"not in the fetch journal: "
                f"{', '.join(str(s) for s in sorted(unknown))}\n"
                f"  Only a fetched book can be measured.")
        serials = [s for s in serials if s in wanted]
    measurable = sum(1 for s in serials
                     if progress[s]["complete"] or args.include_partial)
    counter = LiveCounter("measuring DEV->IAST", total=measurable)

    rows, skipped, missing, empty_fetch = [], 0, 0, 0
    for serial in serials:
        state = progress[serial]
        if not state["complete"] and not args.include_partial:
            skipped += 1
            continue
        name = files.get(serial)
        path = args.cache / name if name else None
        if not path or not path.exists():
            missing += 1
            # A completed fetch that returned nothing writes no cache file, so
            # there is no text to measure -- but the absence IS the
            # measurement, and it is the strongest empty signal in the corpus.
            # Dropping the row lost 17 works from the sizes file and with them
            # the audit's "Empty text items" finding; they are emitted here as
            # explicit zeroes instead. Anything else missing from disk (a
            # deleted cache file, say) is genuinely unmeasured and still
            # skipped.
            carried = journal.get(serial, {})
            # A completed fetch that wrote no chunks returned nothing at all,
            # so there is no cache file to measure -- and the absence IS the
            # measurement, the strongest empty signal in the corpus. Keyed on
            # `chunks_written`, not on bytes: a book can journal 0 bytes on a
            # later no-op pass while holding real text from an earlier one.
            if state["chunks_written"] == 0:
                record = by_serial.get(serial, {})
                rows.append({
                    "serial": serial,
                    "id": record.get("id"),
                    "reader": record.get("text"),
                    "raw_bytes": 0,
                    "content_bytes": 0,
                    "transliterated_bytes": 0,
                    "devanagari_chars": 0,
                    "chunks": state["chunks_written"],
                    **{k: v for k, v in carried.items() if k != "raw_bytes"},
                    "file": name,
                })
                missing -= 1
                empty_fetch += 1
            continue

        # Repainted BEFORE the work, not after: a book that never finishes is
        # the one whose name is needed, and a line painted on completion is
        # the one line a hang never reaches.
        counter.update(name)

        record = by_serial.get(serial, {})
        carried = journal.get(serial, {})
        row = {
            "serial": serial,
            "id": record.get("id"),
            "reader": record.get("text"),
            # `raw_bytes` first so it keeps its place ahead of the counts this
            # stage derives, matching the order the fetcher writes.
            **({"raw_bytes": carried["raw_bytes"]}
               if "raw_bytes" in carried else {}),
            **measure(path.read_text(encoding="utf-8")),
            "chunks": state["chunks_written"],
            **{k: v for k, v in carried.items() if k != "raw_bytes"},
            "file": name,
        }
        if not state["complete"]:
            row["partial"] = True
        rows.append(row)

    counter.close()

    # **Never replace good sizes with nothing.** This file is the concentrated
    # distillate of a multi-GB cache -- the one artifact that survives when the
    # cache does not, and what `build_tree` falls back to. The write below is a
    # truncate-and-rewrite, so a run that measured nothing (an absent or empty
    # cache on a machine that still has the sizes) would silently erase it.
    #
    # **The test is measured BYTES, not row count.** An empty cache does not
    # produce an empty `rows`: every journalled book is missing from disk, and
    # the ones whose fetch legitimately returned nothing still emit explicit
    # zero rows (see `empty_fetch` above). So a cacheless run writes a short
    # file of all-zero measurements -- non-empty, entirely worthless, and
    # indistinguishable from real output by length alone. Summing the content
    # bytes is what tells "measured nothing" from "measured something".
    #
    # Measuring nothing is not an error in itself -- it is the expected result
    # without a cache -- so this refuses the WRITE rather than the run, and
    # exits non-zero so a `make` chain stops rather than continuing on data it
    # thinks it just refreshed.
    # A targeted run measures a handful of books, so the whole-file guard below
    # would see three rows where the file holds thousands and refuse -- rightly,
    # for a full pass. Merging first makes the two cases identical: `rows`
    # becomes the complete corpus either way, and the guard keeps its meaning.
    if args.serials:
        touched = {r["serial"] for r in rows}
        kept = []
        if args.out.exists():
            for line in args.out.open(encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if existing.get("serial") not in touched:
                    kept.append(existing)
        before = len(kept) + len(touched)
        rows = sorted(kept + rows, key=lambda r: r.get("serial") or 0)
        print(f"  merged {len(touched)} re-measured "
              f"{'row' if len(touched) == 1 else 'rows'} into "
              f"{len(kept):,} kept -> {len(rows):,} total")
        # A merge that LOSES rows means the existing file could not be read
        # back -- the one way this path can quietly destroy work the full pass
        # cannot. Cheap to check, and the alternative is discovering it when
        # the tree comes up short.
        if len(rows) < before:
            raise SystemExit(
                f"merge produced {len(rows):,} rows from {before:,}; "
                f"refusing to write a shorter sizes file.")

    measured_bytes = sum(r["content_bytes"] for r in rows)
    if not measured_bytes and args.out.exists() and args.out.stat().st_size > 0:
        raise SystemExit(
            f"measured 0 bytes of text across {len(rows)} rows, but "
            f"{args.out} already holds {args.out.stat().st_size:,} bytes -- "
            f"refusing to overwrite it with nothing.\n"
            f"This is what an absent or empty fulltext cache looks like on a "
            f"machine that still has the sizes ({missing:,} journalled books "
            f"were not on disk). The sizes are expensive to reproduce and the "
            f"cache is not here to reproduce them from, so the existing file "
            f"is left untouched.\n"
            f"If you really do mean to discard them, delete the file first."
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8")

    total_content = sum(r["content_bytes"] for r in rows)
    total_iast = sum(r["transliterated_bytes"] for r in rows)
    no_deva = sum(1 for r in rows if not r["devanagari_chars"])
    print(f"measured:     {len(rows)} books")
    if skipped:
        print(f"skipped:      {skipped} incomplete "
              f"(stopped at the chunk ceiling; --include-partial to measure)")
    if empty_fetch:
        print(f"empty fetch:  {empty_fetch} returned 0 bytes "
              f"(no cache file; recorded as measured zeroes)")
    if missing:
        print(f"missing:      {missing} journalled but not on disk")
    if no_deva:
        print(f"no Devanagari:{no_deva}  (the reader served no Sanskrit text)")
    print(f"content:      {total_content:,} bytes")
    print(f"IAST:         {total_iast:,} bytes")
    if total_content:
        print(f"deva:iast     {total_content / total_iast:.3f}x")
    print(f"wrote:        {args.out}")


if __name__ == "__main__":
    main()
