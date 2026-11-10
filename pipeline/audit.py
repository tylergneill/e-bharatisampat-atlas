"""Audit stage: what the source collection gets wrong, published for a reader.

Part of the point of an atlas is that an independent index is the only place a
source's own mistakes become visible. This finds them, describes them
specifically enough to act on, and regenerates a section of `docs/about.html`
between the AUDIT markers.

Modelled on `../sanskrit-wikisource-atlas/pipeline/audit.py` -- the conventions
are lifted deliberately so the two projects stay legible to each other; none of
its checks transfer, being MediaWiki-specific.

## Standing rules

**It never mutates anything.** Not the source, not `metadata.json`, not
`tree.json`. An audit finding is a thing for a human to look at, never an
auto-correction. The only file it writes is its own region of `about.html`.

**Every published number is re-derived by the run that publishes it.** The
failure this repo keeps hitting is a measured figure going stale in prose (see
CLAUDE.md, "Don't cite a notes figure as fact"), and an audit page is the worst
place for that because it looks authoritative. Hence the date stamp on every
run, and hence no baked-in constants to compare against.

**No exact count is ever asserted.** The site's own totals wobble by tens
between requests (`notes/site-structure.md` §2: 4192 / 4061 / 4212 for one URL
within days, 151 of swing in minutes). Figures are compared within a run,
reported with the date they were taken, and described by magnitude.

## The checks

1. **Works the "E-Books" shelf lists without a PDF.** Membership comes from
   `catalogue.jsonl` (the latest shelf walk), the PDF flag from each work's own
   metadata page.
2. **Works whose text is empty at the source**, from the fulltext byte counts.

Plus one observation, kept out of the findings because nothing is wrong:
works whose text holds almost no Devanagari.

**Retired 2026-11-09: works with text that "Unicode Books" omitted.** Until the
site's November 2026 rebuild, ~1,365 works with text and a PDF were shelved
only under "E-Books". The rebuild gave them their own shelf, "AI-converted
books", so the omission is no longer a defect; About's "AI-converted Books"
section describes them instead. That finding was the only one needing a live
request (the shelf's headline total), so the audit is now offline.

Further checks have candidates waiting in the notes -- author-name variants
splitting one person, filing inconsistency. Each needs to *re-derive* its
finding rather than restate a stored number. Listed in `notes/scratch/todo.md`
under the audit-pipeline item.

## Inputs

All local, so every run is free: `docs/data/metadata.json`, `catalogue.jsonl`,
`text_sizes.jsonl`, `tree.json` and the dump-analysis cache. A figure whose
input is missing on this checkout keeps its published value rather than being
blanked (see OPTIONAL_STATS).

    make audit                 # report only
    make audit-update-about    # and rewrite the About page
"""

import argparse
import collections
import datetime
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

from pipeline.config import (CATALOGUE_PATH, DOCS_DIR,
                            METADATA_PATH, TEXT_LOG_PATH, TEXT_SIZES_PATH)
from pipeline.upload_dates import interpolate_additions

SITE_ROOT = "https://www.ebharatisampat.in"

# Hand-checked verdicts on works the audit can measure as empty but cannot
# EXPLAIN. Committed, reviewable in a diff, and written only by a person --
# see the file's own _README for the rules that keep it from going stale.
MANUAL_VERDICTS_PATH = Path(__file__).resolve().parent.parent / "notes" / "manual_verdicts.json"

# Below this many extracted bytes, a work with NO Devanagari holds no text.
#
# The Devanagari test comes first and this threshold only breaks the tie,
# because length alone cannot tell a truncated book from a short one. The
# corpus holds complete works of a single verse -- ekaslokiramayanam at 573
# bytes, gayatrimantrah at 255, and eight more hand-checked on 2026-09-07 --
# so a byte cut applied to them files finished texts as empty. Devanagari
# present means text, at any length.
#
# What is left for the threshold to judge is works with no Devanagari at all,
# where two cases must be told apart and the corpus leaves a wide gap.
#
# A reader that finds no book still returns a page, and what extracts from it
# is site chrome -- visitor counter, footer nav, contact block -- at 505 bytes,
# identical across the 14 works it happens to (2495 and its group). Front
# matter truncated by too short a patience lands lower still, 19 to 229 bytes.
# The smallest real text in the corpus is 3011. Nothing at all sits between
# 505 and 3011, so any threshold in that gap partitions the same way, and 1000
# takes it with a 2x margin below and 3x above.
#
# The cost of being wrong high is calling a real book empty; the cost of being
# wrong low is publishing "this item has text" over a footer. Both are visible
# on the About page, which is why the number sits here with its evidence
# rather than inline at the comparison.
MIN_TEXT_BYTES = 1000

# A work is "no Devanagari" below this share of its content, not only at zero.
#
# Exactly-zero was too brittle. Eight English monographs carry one or two
# incidental Devanagari characters -- a single glyph in 297 KB of `Antiquity of
# Hindoo Medicine`, eleven in 934 KB of `The Ancient Geography of India` -- and
# an exact test dropped every one of them out of the finding they plainly
# belong to, leaving them reported nowhere at all.
#
# The corpus separates cleanly, so the value is read off a gap rather than
# chosen: the highest share among works with no Devanagari body is 0.0082
# (serial 8785, an English history quoting the odd mantra), and the lowest
# above it is 0.0106 (serial 8702, a genuine Sanskrit text). 0.01 sits in
# between with nothing near it.
#
# Devanagari is counted in characters and content in bytes, so the share
# multiplies by 3 -- Devanagari is three bytes per character in UTF-8, and
# comparing the two without it would understate every book threefold.
NO_DEVANAGARI_SHARE = 0.01

ABOUT_HTML_PATH = DOCS_DIR / "about.html"

# Intro figures read from files a checkout may not have. When the file is
# missing, `update_intro_stats` leaves the published number alone rather than
# blanking what it did not measure.
OPTIONAL_STATS = frozenset({
    # From `make dump-analysis`; absent unless that cache has been built.
    "dump_files", "dump_compared", "dump_coverage_pct", "post_dump_stamped", "post_dump_new",
    "post_dump_new_pct", "post_dump_reuploads", "reup_within2", "unch_within2",
    # From `catalogue.jsonl`; absent on a checkout that never walked the shelves.
    "unicode_shelf", "unicode_shelf_pdf", "ai_shelf",
    # From `text_sizes.jsonl`; absent on a checkout without measured text.
    "markup_pct", "iast_reduction_pct", "raw_total_gb", "iast_total_gb",
})

# Cached output of pipeline/dump_analysis.py -- minutes of git archaeology over
# a third-party checkout, so not recomputed per audit run.
DUMP_STATS_PATH = DOCS_DIR.parent / "data" / "dump_stats.json"
AUDIT_START_MARKER = "<!-- AUDIT:START -- generated by `python -m pipeline.audit --update-about`; do not hand-edit between these markers -->"
AUDIT_END_MARKER = "<!-- AUDIT:END -->"

# The listing the overshoot finding is measured against, unfiltered, so a
# reader can check it by hand in one click.
PDF_BROWSE_URL = SITE_ROOT + "/pdf"


# --- inputs -----------------------------------------------------------------


def load_works(path=METADATA_PATH):
    if not path.exists():
        raise SystemExit(f"no metadata at {path} -- run `make parse-metadata`")
    return json.loads(path.read_text())


def load_pdf_shelf(path=CATALOGUE_PATH):
    """Which ids the "E-Books" shelf held, from the latest shelf walk.

    Membership, not a count, so the finding can name each work. None when
    there is no capture, which costs the finding but nothing else.
    """
    if not path.exists():
        return None
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("collection") == "pdf":
                ids.add(row["id"])
    return ids or None


def load_empty_texts(path=TEXT_SIZES_PATH):
    """Ids whose fetched text is empty -- no content at all.

    Measured, not assumed: under `MIN_TEXT_BYTES` of extracted content, which
    is where the site's own chrome lands when the reader finds no book. See
    that constant for why the cut is where it is.

    The test used to be `devanagari_chars == 0`, which conflated two different
    things: a work the reader served nothing for, and a work whose text is
    real but not in Devanagari. The site never promised Devanagari -- or even
    Sanskrit -- so the second is not a defect at all. It is now reported
    separately by `load_no_devanagari`, and the two are disjoint by
    construction.

    Returns an empty set when nothing has been measured yet, which correctly
    marks nothing rather than marking everything.
    """
    return _text_size_ids(path)[1]


def load_no_devanagari(path=TEXT_SIZES_PATH):
    """Ids that carry real text containing no Devanagari.

    Not a defect and not an absence -- a fact about the copy the site holds.
    Filing these under "the source has no text" stated something false about
    books that are fine.

    Hand-checked 2026-09-07, all 21 of them, and they are not one thing:

      pre-IAST or OCR-corrupted IAST   8   Cowell's Buddhacarita, Bernhard's
                                           Udanavarga, two Rgvedas, the
                                           Taittiriya-samhita, Canakyaniti
      pre-Unicode font encoding        3   Balaram (Saduktikarnamrtam,
                                           Brahmasphutasiddhanta) and one
                                           mojibake (Taittiriyopanisadbhasya)
      English or German                9   monographs and translations
      OCR noise only                   1   Tarkasangraha (nilakanthisahitah)

    They stay in one bucket deliberately. The split is a reading of each book,
    not something the measurement can see, so sub-buckets here would be a hand
    list pretending to be a finding -- and the one claim this category makes
    ("no Devanagari") is true of every member regardless of which kind it is.
    The distinction that would matter is recoverability, and all but the last
    are recoverable by a decoding or transliteration pass.

    The test is `NO_DEVANAGARI_SHARE`, not zero: eight English monographs carry
    a stray Devanagari character or two, and an exact-zero test stranded every
    one of them outside both findings.

    Disjoint from `load_empty_texts` by construction: this requires at least
    `MIN_TEXT_BYTES` of content, that one requires less. A work is in exactly
    one, so the About page's counts cannot double-report.
    """
    return _text_size_ids(path)[2]


def _text_size_ids(path=TEXT_SIZES_PATH, log_path=TEXT_LOG_PATH):
    """(every id measured, the empty ones, the ones with no Devanagari).

    All three matter: the middle set is the defect, the last is a fact about
    the copy rather than a defect, and the first is the only thing that says
    how much of the corpus either finding actually covers.

    The last two are disjoint. Under `MIN_TEXT_BYTES` of content is empty; at
    or above it with no Devanagari is text in another script. A work cannot be
    both, so the About page's two counts never double-report the same book.

    A later row wins. `text_sizes.jsonl` is appended to rather than rewritten,
    so a refetched work has several rows and only the last is its current
    measurement -- reading them as a set would let a stale row outvote the
    fetch that replaced it.

    Two sources, because neither alone is complete. `text_sizes.jsonl` holds
    the per-work measurements, but `count_sizes` rebuilds it from the cached
    TEXT, so a work whose fetch returned nothing has no cache file and no row
    -- and those are the emptiest works in the corpus. The journal is the only
    record that they were fetched at all, so a completed fetch of 0 bytes is
    read from there and counts as both measured and empty.
    """
    measured, empty, no_deva = set(), set(), set()
    if path.exists():
        latest = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            latest[row.get("id")] = row
        for work_id, row in latest.items():
            measured.add(work_id)
            content = row.get("content_bytes") or 0
            deva = row.get("devanagari_chars") or 0
            # Devanagari is 3 bytes per character in UTF-8; without the factor
            # the share would read a third of its true value.
            share = (deva * 3 / content) if content else 0.0
            if share >= NO_DEVANAGARI_SHARE:
                continue          # a Devanagari text, however short
            elif content < MIN_TEXT_BYTES:
                empty.add(work_id)
            else:
                no_deva.add(work_id)

    # Completed fetches that produced no text at all. Keyed by serial in the
    # journal, so the id comes off the row itself. Later rows win: a work
    # refetched into content must not stay on this list.
    if log_path.exists():
        zero = {}
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            work_id = row.get("id")
            if not work_id or not row.get("complete"):
                continue
            # A flag-only pass re-journals a book without refetching it and
            # reports 0 bytes for that pass; it is not a measurement of the
            # text, so it must not mark a populated book empty.
            if row.get("ending") == "flag-only":
                continue
            zero[work_id] = row.get("bytes") == 0
        for work_id, is_zero in zero.items():
            if work_id in measured:
                continue          # the sizes file already spoke for this one
            if is_zero:
                measured.add(work_id)
                empty.add(work_id)
    return measured, empty, no_deva


def load_manual_verdicts(path=MANUAL_VERDICTS_PATH):
    """Hand-checked verdicts, keyed by serial.

    The audit measures whether a work has text. It cannot measure WHY it does
    not: a 200 with no text container is indistinguishable from a login wall,
    and a machine-generated PDF behind a reader that denies text is invisible
    to any amount of fetching. Those were settled by opening the pages, and
    this is where that judgment is recorded so the published finding can say
    "confirmed to have no text" separately from "we cannot reach it".

    Absent file -> no verdicts, and every empty work reports unexplained. That
    is the honest degradation: a missing curation file must never look like a
    clean bill of health.
    """
    if not path.exists():
        return {}, {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    verdicts = {str(k): v for k, v in (data.get("verdicts") or {}).items()}
    return verdicts, (data.get("labels") or {})


def apply_manual_verdicts(finding, verdicts, labels):
    """Partition an empty-text finding by hand-checked verdict.

    Two guards, both hard errors rather than warnings, because a stale
    hand-written claim on a published page is the exact failure this repo
    keeps having:

    **A verdict may only narrow a measurement.** One naming a work the audit
    did not flag as empty is either a typo or a verdict outliving the thing it
    described -- and silently ignoring it would let the file drift out of any
    relationship with the corpus.

    **A verdict may not survive being contradicted.** If a later fetch gets
    text for a work marked `no_text`, publishing that verdict would state the
    opposite of what the corpus holds. The run fails and names the serial, so
    the fix is to re-check the work rather than to discover the page was wrong
    months later.

    **The corollary is a gap, and it is deliberate.** A defect with no
    measurement to narrow cannot be recorded here at all -- a book that
    announces chapters in its TOC and delivers none has Devanagari, so it is
    neither empty nor no-Devanagari, and no finding exists for a verdict to
    attach to. Serial 6876 is the standing example. Widening the rule to admit
    it would give up the one property that keeps this file honest, so the gap
    stays until such books are measured rather than asserted.
    """
    empty = finding["empty"]
    empty_serials = {str(_serial_num(w)) for w in empty}

    # Both guards are this one comparison. A work that has GAINED text since it
    # was judged is no longer in `empty`, so a verdict for it lands here too --
    # the contradiction and the typo are indistinguishable from the outside,
    # and both want the same response: a person re-checks the work.
    unknown = sorted(set(verdicts) - empty_serials, key=int)
    if unknown:
        raise SystemExit(
            f"{MANUAL_VERDICTS_PATH.name} has verdicts for works the audit does "
            f"not report as empty: {', '.join(unknown)}\n"
            f"  Either the work now HAS text -- in which case the verdict is "
            f"stale and must go -- or the serial is wrong. A verdict may only "
            f"narrow a measurement, never assert one.")

    groups = collections.defaultdict(list)
    for work in empty:
        entry = verdicts.get(str(_serial_num(work)))
        groups[entry["verdict"] if entry else None].append(work)

    finding["verdicts"] = {
        # `None` is the unexplained remainder -- works measured empty that
        # nobody has looked at. It is a real bucket and must keep its own name.
        (key or "unexplained"): works for key, works in groups.items()
    }
    finding["labels"] = dict(labels)
    finding["explained"] = sum(len(w) for k, w in groups.items() if k)
    return finding


def _serial_num(work):
    """The bare serial, as a string key into the verdicts file."""
    return work.get("serial")


def find_empty_texts(works, path=TEXT_SIZES_PATH):
    """Text-bearing works whose fetched text is empty, and those not in Devanagari.

    Reported as its own finding rather than only as inline flags on the other
    two: an entry that opens onto no text is a defect in its own right, and the
    under/overcount lists between them mention only a fraction of these.

    `no_devanagari` rides along as a separate list because it is not the same
    claim. An empty work is a defect -- the entry promises text and none
    arrives. A work in romanized Sanskrit, English, or a pre-Unicode font
    encoding has exactly the text the site holds, and saying otherwise would
    publish a false statement about a book that is fine.

    A text-bearing work that has not been fetched counts as non-empty, not as
    unknown: the audit reports what it has measured. `unmeasured` rides along
    so the stderr report can say how many works a rerun would newly cover.
    """
    measured, empty_ids, no_deva_ids = _text_size_ids(path)
    with_text = text_bearing(works)
    empty = [w for w in with_text if w.get("id") in empty_ids]
    empty.sort(key=_serial)
    no_devanagari = [w for w in with_text if w.get("id") in no_deva_ids]
    no_devanagari.sort(key=_serial)
    return {
        "empty": empty,
        "no_devanagari": no_devanagari,
        "measured": len([w for w in with_text if w.get("id") in measured]),
        "unmeasured": len([w for w in with_text if w.get("id") not in measured]),
        "text_bearing": len(with_text),
    }


def capture_date(path=CATALOGUE_PATH):
    """When the listing capture was taken -- the mtime, since the file itself
    carries no timestamp. Published beside the listing so a reader knows it is
    a snapshot rather than this run's measurement."""
    stamp = datetime.date.fromtimestamp(path.stat().st_mtime)
    return stamp.isoformat()


def text_bearing(works):
    """Works whose metadata page carries a working text reader.

    `text` holds the reader kind (`readbook3` or `read_chapter`) or is absent.
    """
    return [w for w in works if w.get("text")]


# The metadata fields whose coverage the Metadata Pages table publishes, in the
# order the table lists them.
#
# Bibliographic only -- what the source SAYS ABOUT the work. Deliberately not
# `text`/`pdf`, which are the reader endpoint and the PDF's presence:
# `parse_metadata` treats those as STRUCTURAL rather than FIELDS, and they
# describe what content sits behind an entry, not what the work is. Also not
# `uploaded`/`added`/`added_synthetic`, which this Atlas derives from the
# thumbnail rather than reading from any published row.
#
# `id` and `serial` are on every record (100%) and are stated in the prose.
COVERAGE_FIELDS = [
    "title", "domain", "language", "sub_domain", "pages", "publish_year",
    "author", "printer", "publisher", "editor", "books_contributor",
    "primary_commentator", "commentary_name", "translator", "second_editor",
    "secondary_commentator", "tertiary_commentator",
]

# Domains whose author coverage the Metadata Pages prose quotes, as the two
# ends of the range. Named here so the figures move with the data rather than
# being retyped: an anonymous-transmission genre against an authored one.
AUTHOR_PCT_DOMAINS = {
    "author_pct_upanisads": "उपनिषदः",
    "author_pct_sahitya": "साहित्यम्",
}

def field_coverage(works):
    """Per-field counts and percentages for the Metadata Pages table.

    Emitted as `data-stat` values like every other published figure, so a
    metadata rebuild that shifts coverage updates the table instead of leaving
    a stale one behind. A field that vanishes from the corpus still publishes,
    as 0 -- the table's rows are fixed, and a silently missing row would be the
    same stale-number failure in a different shape.
    """
    stats = {}
    for field in COVERAGE_FIELDS:
        n = sum(1 for w in works if w.get(field))
        stats[f"cov_{field}"] = n
        stats[f"covpct_{field}"] = round(n / len(works) * 100, 1)
    # Author coverage, overall and for the two domains the prose contrasts.
    # Whole percentages: `_fmt` gives ints no decimal, and these are quoted as
    # round numbers in the sentence around them.
    stats["author_pct"] = round(sum(1 for w in works if w.get("author"))
                                / len(works) * 100)
    for key, domain in AUTHOR_PCT_DOMAINS.items():
        in_domain = [w for w in works if w.get("domain") == domain]
        stats[key] = (round(sum(1 for w in in_domain if w.get("author"))
                            / len(in_domain) * 100) if in_domain else 0)

    # NOTE: the count of unrecognized labels (works carrying `extra`) is
    # deliberately not published. It was a stat for a sentence the About page
    # no longer runs, and `update_intro_stats` treats an untagged stat as an
    # error rather than a skip -- so an unused figure here breaks every run.
    return stats


def intro_stats(works):
    """The figures the hand-written Practical Intro quotes, re-derived.

    These are the Venn's six numbers plus the two reader-kind counts. They were
    hand-typed until 2026-08-21 and had no way to notice a metadata rebuild
    moving them -- the same failure mode the audit region exists to prevent, so
    they are now published by the run that measures them.
    """
    text = sum(1 for w in works if w.get("text"))
    pdf = sum(1 for w in works if w.get("pdf"))
    both = sum(1 for w in works if w.get("text") and w.get("pdf"))
    kinds = collections.Counter(w["text"] for w in works if w.get("text"))
    stats = {
        "total": len(works),
        "text": text,
        "pdf": pdf,
        "both": both,
        "text_only": text - both,
        "pdf_only": pdf - both,
        "read_chapter": kinds.get("read_chapter", 0),
        "readbook3": kinds.get("readbook3", 0),
    }

    # Language: what share of the collection carries no Sanskrit at all. The
    # field is free text and inconsistent ("English" appears four ways), so
    # match on the Devanagari and roman names rather than on exact values.
    langs = [(w.get("language") or "") for w in works]
    non_skt = sum(1 for l in langs
                  if l.strip() and "संस्कृत" not in l and "sanskrit" not in l.lower())
    # Published as a whole number: the free-text matching above is too coarse
    # to justify a tenth of a percent, and an int is what keeps _fmt from
    # printing a decimal at all (round(x, 0) would still render "3.0").
    stats["non_sanskrit_pct"] = round(non_skt / len(works) * 100)

    # Serial vs upload date: the correlation the chronology argument rests on.
    stats["serial_upload_rho"] = round(_spearman_serial_upload(works), 3)

    # Records whose stamp ran so far past their serial neighborhood that
    # `parse_metadata` interpolated an addition date instead, and the count
    # deviating as far the other way -- the control that makes the first
    # number mean something. Re-derived through the same function that does
    # the interpolating, on a throwaway copy, so the published figures cannot
    # drift from the rule that produced the dates. `records` is already
    # written; this must not mutate it.
    late, early = interpolate_additions([dict(w) for w in works])
    stats["synthetic_dates"] = late
    stats["stamps_early"] = early

    stats.update(_dump_stats(works))
    stats.update(field_coverage(works))
    stats.update(shelf_stats(works))
    stats.update(size_ratio_stats())
    return stats


def size_ratio_stats(path=TEXT_SIZES_PATH):
    """The two shares "Calculating Size Information" quotes, from the sizes.

    `markup_pct`: how much of the pages as delivered is discarded to get the
    text (the site's page code, then the books' own furniture).
    `iast_reduction_pct`: how much further transliterating to IAST shrinks
    what is left. Both are byte-weighted over every measured book,
    a later row winning, as `count_sizes` appends. Missing sizes file means
    the tags keep their published values (see OPTIONAL_STATS).
    """
    if not path.exists():
        return {}
    latest = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["serial"]] = row
    rows = [r for r in latest.values() if r.get("raw_bytes") and r.get("content_bytes")]
    raw = sum(r["raw_bytes"] for r in rows)
    content = sum(r["content_bytes"] for r in rows)
    iast = sum(r.get("transliterated_bytes") or 0 for r in rows)
    if not raw or not content:
        return {}
    return {
        "markup_pct": round((1 - content / raw) * 100),
        "iast_reduction_pct": round((1 - iast / content) * 100),
        # The two ends of that chain, in decimal GB as the Atlas counts bytes.
        "raw_total_gb": round(raw / 1e9, 1),
        "iast_total_gb": round(iast / 1e9, 1),
    }


def shelf_stats(works, path=CATALOGUE_PATH):
    """Shelf sizes for the intro, from the latest shelf walk.

    "With a PDF" means on the E-Books shelf AND a PDF on the work's own page,
    the same `pdf` flag the Venn counts, so the two figures sum to its "both".
    Shelf membership alone overcounts: a few works are shelved as E-Books with
    no PDF on their page. Missing catalogue means the tags keep their
    published values (see OPTIONAL_STATS).
    """
    if not path.exists():
        return {}
    has_pdf = {w["serial"] for w in works if w.get("pdf")}
    shelves = collections.defaultdict(set)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            shelves[row["collection"]].add(row["serial"])
    return {
        "unicode_shelf": len(shelves["unicode"]),
        "unicode_shelf_pdf": len(shelves["unicode"] & shelves["pdf"] & has_pdf),
        "ai_shelf": len(shelves["ai"]),
    }


# Serial bands for the "Understanding Serials" table. Fixed 500-wide rows on
# round boundaries -- unlike `notes/serial-bands.md`, which uses measured era
# edges. The structure survives the coarser cut, and round numbers are what a
# reader can check against a serial they are holding.
SERIAL_BAND_WIDTH = 500


def serial_band_rows(works):
    """Rows for the serial table: one per 500 serials, low to high.

    Returns a list of dicts rather than stats keys. Reaches the page through
    `changelog.json` and the "By Serial Number" chart, which grows a bar per
    500 new serials on its own -- a new band must not require hand-adding
    anything. (Until 2026-08-27 this also rendered an HTML table between
    BANDS:* markers; the table was merged into the chart and that path is gone.)

    Bands are 1-indexed to match the site's own numbering: 1-500, 501-1000.
    Every column is a plain count, so the three format columns subtract across
    the row and nothing depends on a ratio's base. The band's subject mix used
    to ride here as a "drawn from" cell; it is the "Which Subjects, When" line
    chart's job now, on a real time axis.
    """
    bands = {}
    for work in works:
        if work.get("serial"):
            # 1-indexed bands: serial 1-500, 501-1000, ... Serials are the
            # site's own labels and start at 1, so a band boundary at a round
            # multiple is what a reader checking a serial expects. `key` is the
            # band's LOW serial, not a floor-division bucket.
            serial = int(work["serial"])
            key = (serial - 1) // SERIAL_BAND_WIDTH * SERIAL_BAND_WIDTH + 1
            bands.setdefault(key, []).append(work)

    rows = []
    for key in sorted(bands):
        band = bands[key]
        texts = [w for w in band if w.get("text")]
        kinds = collections.Counter(w["text"] for w in texts)
        # When the band was being filled, as a month. Two choices here, both
        # forced by the requirement that this column increase down the table:
        #
        # `added` rather than `uploaded` -- the interpolated date, which
        # `parse_metadata` substitutes for the 207 stamps that run past their
        # serial neighborhood. The page's own chronology section concludes
        # those are noise, and on the raw field one of them drags the first
        # band to Nov 2023 for works added in early 2021.
        #
        # The MEDIAN rather than a high quantile -- bands overlap slightly in
        # real time, so even on `added` a p75/p90/max ends up non-monotonic in
        # two places. The median is monotonic across all 26 bands, and it is
        # the honest summary of a band whose members do not share one date.
        stamps = sorted(w["added"][:7] for w in band if w.get("added"))
        end = (stamps[min(len(stamps) - 1, round((len(stamps) - 1) * 0.50))]
               if stamps else "")

        rows.append({
            "lo": key,
            "hi": key + SERIAL_BAND_WIDTH - 1,
            "end": end,
            "works": len(band),
            "text": len(texts),
            # Chapter-divided texts (`read_chapter`). `readbook3`, the other
            # reader, is not published: it is this column's exact complement
            # against `text`, so it carried nothing a subtraction does not.
            "structured": kinds.get("read_chapter", 0),
            # PDF-only is the complement the growth chart shows by year; here it
            # is what the band offers when it offers no searchable text. A count
            # rather than a share, so it sits beside `works` and `text` and the
            # three read as one subtraction across the row.
            "pdf_only": sum(1 for w in band
                            if w.get("pdf") and not w.get("text")),
        })
    return rows


def _spearman_serial_upload(works):
    """Spearman rho between serial number and thumbnail upload date.

    Both are ordinal proxies for time and neither is a documented field; that
    they agree this closely is what licenses reading either as chronology.
    """
    pairs = [(w["serial"], w["uploaded"]) for w in works
             if w.get("serial") and w.get("uploaded")]
    if len(pairs) < 2:
        return float("nan")

    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx = ranks([p[0] for p in pairs])
    ry = ranks([p[1] for p in pairs])
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = sum((a - mx) ** 2 for a in rx) ** 0.5
    sy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (sx * sy) if sx and sy else float("nan")


def _dump_stats(works):
    """Figures from the 2025 fulltext dump comparison.

    Read from `data/dump_stats.json`, written by `make dump-analysis` -- the
    comparison walks a third-party git checkout and takes minutes, so it is
    cached rather than recomputed on every audit run. Absent cache means the
    tags keep their published values (see OPTIONAL_STATS).
    """
    if not DUMP_STATS_PATH.exists():
        return {}
    cached = json.loads(DUMP_STATS_PATH.read_text())
    total = len(works)
    cached["dump_coverage_pct"] = round(cached["dump_files"] / total * 100, 1)
    cached["post_dump_new_pct"] = round(
        cached["post_dump_new"] / cached["post_dump_stamped"] * 100, 1)
    return cached


def _serial(work):
    """Sort key: the source's own accession number, ascending.

    Every work in the catalogue carries an int serial, but the fallback keeps a
    missing one from raising and parks it at the end rather than at the front,
    where it would look like the lowest-numbered item.
    """
    serial = work.get("serial")
    return (serial is None, serial if serial is not None else 0)


def find_pdf_overshoot(works, pdf_listed_ids=None):
    """Works the "E-Books" shelf lists whose own page offers no PDF.

    Over-inclusion: the shelf promises a PDF and the work has none. Verified
    at the source 2026-08-20: these open and render text, and have no PDF, so
    the error is the listing's, not our metadata's. None when there is no
    shelf capture to check against.
    """
    if not pdf_listed_ids:
        return {"pdf_listed": None, "pdf_without_pdf": None}
    without = [w for w in works
               if w.get("id") in pdf_listed_ids and not w.get("pdf")]
    without.sort(key=_serial)
    return {"pdf_listed": len(pdf_listed_ids), "pdf_without_pdf": without}


# --- report -----------------------------------------------------------------


def print_report(finding, captured):
    print('\n1. works the "E-Books" shelf lists without a PDF\n')
    if finding["pdf_without_pdf"] is None:
        print("  no shelf capture -- run `make walk-shelves` and `make catalogue`")
        return
    print(f"  {len(finding['pdf_without_pdf'])} of {finding['pdf_listed']} shelved "
          f"(shelf walk of {captured})")


# --- HTML -------------------------------------------------------------------
#
# Construction lifted from the wikisource audit's `_bullet` / `_sub_bullet` /
# `_findings_list` / `update_about_html`, so a reader who knows one page's
# markup knows the other's.


def _esc(s):
    return html.escape(str(s))


def _sa(s):
    """Devanagari gets the site's own font treatment, same as hand-written
    About prose does with `<span class="sa-cap">` -- titles and category names,
    which `docs/translit-static.js` title-cases when the scheme is IAST."""
    return f'<span class="sa-cap">{_esc(s)}</span>'


def _work_link(work):
    """Every example links to the work's metadata page, built exactly as
    `docs/app.js` metadataUrl does.

    The metadata page, not a reader: it is the one page that describes the work
    itself rather than a single format of it, and these findings are ABOUT how a
    work is catalogued -- what it is listed as, and what it turns out to have. A
    reader link would answer a question nobody asked here, and for the E-Books
    finding it would be actively wrong, since the defect is precisely that the
    promised format is missing.

    One endpoint for every work, so the link no longer depends on which reader a
    work happens to use.
    """
    href = SITE_ROOT + "/readSearch.php?id=" + urllib.parse.quote(work.get("id", ""))
    title = _sa(work.get("title", "?"))
    return ('<a href="' + html.escape(href) + '" target="_blank" '
            'rel="noopener">' + title + "</a>")


def _preamble(text_html):
    """One line between a finding's summary and its items.

    The only prose a finding carries. It exists to point at the listing the
    finding is about -- the reader can open that view and see the absence for
    themselves -- and must stay a single sentence; anything longer is the
    restated context the findings deliberately dropped.
    """
    return f'          <p style="margin-left: 1.6em;">{text_html}</p>'


def _entry_html(work, empty=frozenset()):
    """One item link, flagged when the fetched text holds no Devanagari.

    No page count. These findings are about how a work is CATALOGUED -- listed
    or not listed, promising a format it has or has not -- and a size says
    nothing about that. It also read as a quality signal it was never measuring.

    The empty flag does belong: a listing entry pointing at a page with no text
    is a different and worse defect than one merely mis-shelved, and it is what
    separates a duplicate entry from the copy that actually carries the work.
    """
    serial = work.get("serial")
    prefix = f"({serial}) " if serial is not None else ""
    link = f"{prefix}{_work_link(work)}"
    if work.get("id") in empty:
        return f"{link} — <strong>empty</strong> (no text at the source)"
    return link


def _findings_list(items):
    """`items` are already-escaped HTML fragments -- this only wraps them in
    <li>/<ul> and must not re-escape. Indented past its own <summary>'s
    triangle, which the global `.content ul` reset does not clear."""
    lis = "\n".join(f"            <li>{item}</li>" for item in items)
    return f'          <ul style="margin-left: 1.6em;">\n{lis}\n          </ul>'


def _summary_text(description, label):
    """The summary's own content, wrapped in one span.

    `.audit-summary` is `display: flex` (for the triangle), which makes every
    child a flex item -- and flex DISCARDS the whitespace between items. A
    description ending in an element, as ours do when a category name is
    wrapped in `<span class="sa-cap">`, would otherwise render as
    "darsanani(678 works)" with the space silently eaten. Wikisource never hit
    this because its summaries are plain text. One wrapper span makes the whole
    label a single flex item, and the space inside it survives.
    """
    return f"<span>{description} ({label})</span>"


def _bullet(description, count, inner_html, unit=None):
    """One finding row. `unit` spells out what the number counts, for cases
    where a bare figure would mislead. A zero-count check still renders, as
    "none found" with an invisible spacer where the triangle would be."""
    if count == 0:
        # Same one-flex-item wrapper as _summary_text, for the same reason.
        return (f'          <li class="audit-item"><div class="audit-summary '
                f'audit-summary-empty"><span>{description}: none found</span></div></li>')
    label = unit if unit is not None else str(count)
    return (
        f'          <li class="audit-item"><details>\n'
        f'            <summary class="audit-summary">{_summary_text(description, label)}</summary>\n'
        f"{inner_html}\n"
        f"          </details></li>"
    )


def _sub_bullet(description, count, inner_html, unit=None):
    """Same construction one level in, for grouping a flat list into
    collapsible sub-groups. Reuses .audit-item/.audit-summary so the triangle
    and spacing match the top-level findings exactly."""
    label = unit if unit is not None else str(count)
    return (
        f'<li class="audit-item"><details>\n'
        f'<summary class="audit-summary">{_summary_text(description, label)}</summary>\n'
        f"{inner_html}\n"
        f"</details></li>"
    )


def _group_ul(items):
    """A nested list of audit bullets -- same wrapper the wikisource audit uses
    between a <summary> and its child findings."""
    return ('          <ul style="margin-left: 1.6em; list-style: none; padding-left: 0;">\n'
            + "\n".join(f"            {item}" for item in items)
            + "\n          </ul>")


def render_pdf_overshoot(finding, empty=frozenset()):
    """The PDF listing's converse defect, as its own finding.

    A different error (over-inclusion, not omission), in a different listing,
    measured against a different field -- so it stands beside the omission
    finding rather than trailing it as a closing paragraph.

    One line of prose, same as its sibling, pointing at the listing it is
    about. Renders as "none found" when the check comes back clean, which is
    the informative outcome and must still be published; `_bullet` handles that.
    """
    works = finding["pdf_without_pdf"]
    if works is None:
        return ""  # no shelf capture: unmeasured, not "none found"
    description = ("Text-only items <strong>overcounted</strong> by “E-Books” "
                   "(PDF) browsing")
    if not works:
        return _bullet(description, 0, "")

    inner = "\n".join([
        _preamble(f'I.e., these should be found '
                  f'<a href="{html.escape(PDF_BROWSE_URL)}" target="_blank" '
                  f'rel="noopener">here</a> only if they have a PDF, but none of them do.'),
        _findings_list([_entry_html(w, empty) for w in works]),
    ])

    return _bullet(
        description, len(works), inner,
        unit=f"{len(works)} of {finding['pdf_listed']} listed",
    )


def render_empty_texts(finding, empty=frozenset()):
    """Empty texts as their own finding: a summary, a pointer, then the works.

    A work not yet fetched is treated as non-empty rather than unknown -- the
    audit reports what it has measured, and a rerun after the next fetch pass
    picks up any that turn out empty. `unmeasured` rides along in the finding
    for the stderr report, which is where "a rerun would change this" belongs.
    """
    works = finding["empty"]
    description = "<strong>Empty</strong> text items"
    if not works:
        return _bullet(description, 0, "")

    groups = finding.get("verdicts") or {"unexplained": works}
    labels = finding.get("labels") or {}

    # Hand-checked groups first, in the labels file's own order so the page
    # does not reshuffle when a count changes; the unexplained remainder last,
    # because it is the only group that is still a question.
    order = [k for k in labels if k in groups] + (
        ["unexplained"] if "unexplained" in groups else [])

    preamble = _preamble(
        "These items are supposed to have text but don't. They are still "
        "displayed in the Atlas if they contain a PDF. Where a group below "
        "says what was found, that is a hand check of the individual works, "
        "not a measurement — the audit can see that an item is empty, but not "
        "why.")

    items = []
    for key in order:
        members = groups[key]
        if not members:
            continue
        heading = labels.get(key, "not yet checked")
        items.append(_sub_bullet(html.escape(heading), len(members),
                                 _findings_list([_entry_html(w)
                                                 for w in members])))
    return _bullet(description, len(works),
                   preamble + "\n" + _group_ul(items),
                   unit=f"{len(works)} items")


def render_no_devanagari(finding):
    """Works whose text is real but carries no Devanagari.

    Deliberately not filed with the empty items. These books have exactly the
    text the site holds; what they lack is a script, and the site never
    promised one. Three kinds turn up, and the page says so rather than
    implying a single cause: editions printed in romanized Sanskrit, works
    written in English or German about Sanskrit subjects, and books stored in
    a pre-Unicode font encoding whose bytes are Devanagari in everything but
    codepoint.

    Only the third is a defect, and it is one this Atlas could fix by decoding
    rather than one ebharatisampat.in should. So this is reported as an
    observation, not an "opportunity for correction" -- no call to action.
    """
    works = finding.get("no_devanagari") or []
    description = "Items with <strong>non-Devanāgarī</strong> text"
    if not works:
        return _bullet(description, 0, "")

    preamble = _preamble(
        "These items carry text that is not in Devanāgarī — which makes "
        "them fundamentally different than the rest of the e-texts, which are "
        "exclusively in Devanāgarī. Some are Sanskrit in transliteration, "
        "some in a pre-Unicode font encoding such as Balaram, and some are "
        "works in English or German.")

    return _bullet(description, len(works),
                   preamble + "\n" + _findings_list(
                       [_entry_html(w) for w in works]),
                   unit=f"{len(works)} items")


def render_audit_html(findings, empty=frozenset()):
    """The whole generated region: one <h3>, a lead-in, and the findings list.

    Same shape as the wikisource sibling's "Opportunities for Correction" --
    a single anchorable heading over a flat list of findings, each stating its
    own numbers and opening onto its own items.

    No dates anywhere in the published region; the run's stderr report carries
    them, which is where they answer a question someone is actually asking.
    """
    bullets = [b for b in (
        render_pdf_overshoot(findings["pdf_overshoot"], empty),
        render_empty_texts(findings["empty_texts"], empty),
    ) if b]

    # Kept out of the list above, which is headed "problems that should be
    # fixed on ebharatisampat.in". A book printed in roman script is not a
    # problem and there is nothing for the site to fix, so filing it there
    # would ask for a correction to something that is already correct.
    observations = [render_no_devanagari(findings["empty_texts"])]

    return (
        f'        <h3 id="opportunities-for-correction">Opportunities for Correction</h3>\n'
        f"        <p>\n"
        f"          The Atlas codebase also includes an audit pipeline for\n"
        f"          detecting and concisely indicating problems that should be fixed on "
        f"ebharatisampat.in.\n"
        f"        </p>\n"
        f'        <ul style="list-style: none; padding-left: 0;">\n'
        + "\n".join(bullets)
        + "\n        </ul>\n"
        f'        <h3 id="observations">Observations</h3>\n'
        f"        <p>\n"
        f"          Facts about the collection rather than faults in it: things a\n"
        f"          reader should know before drawing a conclusion from the counts.\n"
        f"        </p>\n"
        f'        <ul style="list-style: none; padding-left: 0;">\n'
        + "\n".join(observations)
        + "\n        </ul>"
    )


def update_about_html(new_html, path=ABOUT_HTML_PATH):
    """Replace the block between the AUDIT markers -- a targeted string splice,
    not an HTML parse, so the rest of the file and the markers are untouched."""
    text = path.read_text(encoding="utf-8")
    try:
        start = text.index(AUDIT_START_MARKER) + len(AUDIT_START_MARKER)
        end = text.index(AUDIT_END_MARKER)
    except ValueError as err:
        raise SystemExit(
            f"{path} has no AUDIT:START/AUDIT:END markers -- add the Data Quality "
            f"section before running with --update-about"
        ) from err
    path.write_text(text[:start] + "\n" + new_html + "\n        " + text[end:],
                    encoding="utf-8")


def _month_year(iso):
    """"2026-08" -> "Aug 2026", matching the page's own `monthYear()`.

    Sliced rather than parsed, for the reason that function gives: an ISO date
    read as UTC midnight can print the previous month locally.
    """
    if not iso or len(iso) < 7:
        return "—"
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    try:
        return f"{months[int(iso[5:7]) - 1]} {iso[:4]}"
    except (ValueError, IndexError):
        return "—"


def _count_cell(n):
    """A count. Zero is dimmed so the column's one populated stretch -- the
    structured-text era -- stands out against the twenty bands without any."""
    cls = "sb-num sb-zero" if n == 0 else "sb-num"
    return f'<td class="{cls}">{n:,}</td>'


def _fmt(value):
    """Integers get thousands separators; rates keep one decimal.

    Percentages and correlations are floats and must not be comma-grouped or
    rounded to int here -- a coverage rate of 85.0% would publish as "85" and
    rho 0.972 as "1". A stat that genuinely wants a whole number says so by
    being an int at the computation site (see `non_sanskrit_pct`), rather than
    by loosening this.
    """
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:.3f}" if abs(value) < 1 else f"{value:,.1f}"


def update_intro_stats(stats, path=ABOUT_HTML_PATH):
    """Rewrite each `data-stat="..."` figure in the hand-written intro.

    Per-element substitution rather than a marker region: these numbers sit
    inside authored sentences and the Venn's SVG, so there is no contiguous
    block to splice. The tag is the contract -- prose around it can be
    rewritten freely, and only the digits between the tagged element's own
    `>`/`<` are replaced.

    A tag naming a stat we do not compute, or a stat with no tag, is an error
    rather than a skip: silently leaving a stale figure on the page is exactly
    the failure this replaces.

    The one exception is an OPTIONAL_STATS key whose input file is missing on
    this checkout, where the number is genuinely unmeasured. Those are left as
    they stand, since the alternative is republishing the page with the figure
    blanked out.
    """
    text = path.read_text(encoding="utf-8")
    seen = set()

    def sub(match):
        key = match.group("key")
        if key not in stats:
            if key in OPTIONAL_STATS:
                return match.group(0)  # input missing -- leave the measured value
            raise SystemExit(
                f'{path} tags data-stat="{key}", which the audit does not compute'
            )
        seen.add(key)
        return f"{match.group('open')}{_fmt(stats[key])}{match.group('close')}"

    pattern = re.compile(
        r'(?P<open><(?P<tag>span|text)\b[^>]*\bdata-stat="(?P<key>[^"]+)"[^>]*>)'
        r"[^<]*"
        r"(?P<close></(?P=tag)>)"
    )
    updated = pattern.sub(sub, text)

    missing = sorted(set(stats) - seen)
    if missing:
        raise SystemExit(
            f"{path} has no data-stat tag for: {', '.join(missing)} -- "
            f"tag the figure in the prose or drop it from intro_stats()"
        )
    path.write_text(updated, encoding="utf-8")
    return len(seen)  # distinct stats published, not tag sites -- `both` has two


# --- entry point ------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH,
                        help="our parsed catalogue (docs/data/metadata.json)")
    parser.add_argument("--catalogue", type=Path, default=CATALOGUE_PATH,
                        help="the latest shelf walk, for naming the works")
    parser.add_argument("--update-about", action="store_true",
                        help="rewrite the generated region of docs/about.html")
    args = parser.parse_args()

    works = load_works(args.metadata)
    date = datetime.date.today().isoformat()
    print(f"auditing {len(works)} works from {args.metadata} ({date})", file=sys.stderr)

    pdf_listed_ids = load_pdf_shelf(args.catalogue)
    captured = capture_date(args.catalogue) if pdf_listed_ids else None

    findings = {
        "pdf_overshoot": find_pdf_overshoot(works, pdf_listed_ids),
        # Measured first, then narrowed by hand-checked verdicts. The
        # partition never changes WHICH works are reported -- only how the
        # page groups them.
        "empty_texts": apply_manual_verdicts(
            find_empty_texts(works), *load_manual_verdicts()),
    }

    print_report(findings["pdf_overshoot"], captured)

    empty = findings["empty_texts"]
    print(f"\n2. items whose text is empty at the source\n", file=sys.stderr)
    print(f"  empty: {len(empty['empty'])} of {empty['measured']} fetched",
          file=sys.stderr)
    if empty["unmeasured"]:
        # Not a caveat on the published figure -- unfetched counts as non-empty
        # there -- but the one number that says a rerun would find more.
        print(f"  {empty['unmeasured']} text-bearing works not yet fetched; "
              f"rerun after the next `make fetch-text` to cover them",
              file=sys.stderr)

    if args.update_about:
        update_about_html(render_audit_html(findings, load_empty_texts()))
        print(f"\nwrote the audit region of {ABOUT_HTML_PATH}")
        tagged = update_intro_stats(intro_stats(works))
        print(f"refreshed {tagged} intro figures in the same file")
    else:
        print("\n(report only -- pass --update-about to publish this to the About page)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
