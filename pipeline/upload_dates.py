"""Decode the upload timestamp embedded in a thumbnail filename.

This is the **only** temporal signal on EBS that describes the digital record
rather than the printed book. Keep it strictly distinct from `publish year`,
which is bibliographic (1916, 1939) and answers a different question.

Two naming conventions, both encoding a Unix epoch:

    ebharati-<epoch><name>.jpg    ebharati-1685597534Kadambari 1-06-2023.jpg
    <epoch>.jpg                   1732774427.jpg

**Match exactly 10 digits.** A greedy `\\d{9,11}` swallows the first digit of a
title that begins with one (`ebharati-1697441963५३३०.jpg`) and silently shifts
the date. That bug, plus dismissing the bare form as unusable, is what produced
the old 47%-coverage reading and inverted the growth story -- see
`notes/site-structure.md`.

Coverage against `data/catalogue.jsonl` (13620 rows): 13582 dated (99.7%), 38
hand-named (`raghuvirakosha.jpg`, `sdk_ebs.jpg`), range 2021-01-01 to
2026-08-10.

**This is an inference from a filename convention, not a documented field**, and
the site already changed that convention once, mid-2023, without announcing it.
Re-verify on each pull, and read a sudden coverage drop as a naming change
rather than as a stalled site.
"""

import re
from datetime import datetime, timezone

# Exactly 10 digits, anchored. Anything longer belongs to the title.
PREFIXED_RE = re.compile(r"^ebharati-(\d{10})")
BARE_RE = re.compile(r"^(\d{10})\.(?:jpg|jpeg|png|gif|webp)$", re.IGNORECASE)

# The site launched in 2017; an "epoch" outside this window is a coincidence,
# not a date. The upper bound is deliberately loose so a future pull does not
# start silently discarding its newest rows.
EPOCH_MIN = int(datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp())
EPOCH_MAX = int(datetime(2035, 1, 1, tzinfo=timezone.utc).timestamp())


def decode(thumbnail: str | None) -> tuple[datetime | None, str]:
    """`img/thumbnailsimages/1732774427.jpg` -> (datetime, "bare").

    Returns (None, reason) when no timestamp can be read: "hand-named" for the
    38 rows with a descriptive filename, "none" when there is no thumbnail at
    all, "out-of-range" when 10 digits decode to an implausible date.
    """
    if not thumbnail:
        return None, "none"

    name = thumbnail.rsplit("/", 1)[-1]

    match = PREFIXED_RE.match(name)
    kind = "prefixed"
    if not match:
        match = BARE_RE.match(name)
        kind = "bare"
    if not match:
        return None, "hand-named"

    epoch = int(match.group(1))
    if not (EPOCH_MIN <= epoch <= EPOCH_MAX):
        return None, "out-of-range"

    return datetime.fromtimestamp(epoch, tz=timezone.utc), kind


# How far ahead of its serial neighborhood a stamp must sit before we stop
# reading it as the date the item arrived. Neighboring serials are usually
# uploaded days or weeks apart, so a year is far outside the normal spread --
# and the population is insensitive to the exact figure (`notes/serial-bands.md`
# measures 210 suspects at >=1y against 115 at >=2y, the same shape either way).
LATE_STAMP_DAYS = 365

# Serials either side to draw the neighborhood from. A *local* baseline, not a
# global one: serial tracks time, so a work's neighbors say when that stretch
# of the catalogue was built, and the same 2023 stamp is anomalous among
# 2021-era serials but unremarkable among 2023-era ones.
NEIGHBORHOOD = 100


def interpolate_additions(records: list[dict]) -> tuple[int, int]:
    """Give every record an `added` date, synthetic where the stamp is late.

    `uploaded` is the measured thumbnail timestamp and is never modified. For
    the minority of records whose stamp runs more than LATE_STAMP_DAYS past
    their serial neighborhood's median, that stamp records some later touch to
    the record -- not the date the item arrived -- so `added` instead carries
    the neighborhood median, and `added_synthetic` marks it as an estimate.

    Without this the growth graphs place a few hundred old items in recent
    months, which is the one thing this axis exists to get right.

    Returns (late, early): how many records got a synthetic date, and how many
    deviate as far in the *opposite* direction. The second number is the
    control, and it is what makes the first meaningful -- a stamp that drifted
    both ways would be noise, while one that only ever jumps forward looks like
    a file rewritten after the fact. Measured 207 late against 0 early on
    2026-08-21, so the asymmetry is total at this threshold.
    """
    dated = sorted((r for r in records if r.get("serial") and r.get("uploaded")),
                   key=lambda r: r["serial"])
    if not dated:
        return 0, 0

    ordinals = [datetime.fromisoformat(r["uploaded"]).toordinal() for r in dated]

    late = early = 0
    for i, record in enumerate(dated):
        lo = max(0, i - NEIGHBORHOOD)
        hi = min(len(dated), i + NEIGHBORHOOD + 1)
        # The record's own stamp must not vote on the baseline it is judged by.
        window = sorted(ordinals[lo:i] + ordinals[i + 1:hi])
        if not window:
            continue
        median = window[len(window) // 2]
        drift = ordinals[i] - median
        if drift > LATE_STAMP_DAYS:
            record["added"] = datetime.fromordinal(median).date().isoformat()
            record["added_synthetic"] = True
            late += 1
        else:
            record["added"] = record["uploaded"]
            if drift < -LATE_STAMP_DAYS:
                # Not corrected: a stamp EARLIER than its neighbors is a
                # different phenomenon, and nothing here knows what it means.
                early += 1
    return late, early


def coverage(rows: list[dict], key: str = "thumbnail") -> dict:
    """Summarize decodability over catalogue rows -- run this on every pull.

    A drop in `pct` is the tripwire for the convention changing again.
    """
    counts = {"prefixed": 0, "bare": 0, "hand-named": 0, "none": 0,
              "out-of-range": 0}
    dated = []
    for row in rows:
        when, kind = decode(row.get(key))
        counts[kind] += 1
        if when:
            dated.append(when)

    total = len(rows) or 1
    return {
        "total": len(rows),
        "dated": len(dated),
        "pct": len(dated) / total * 100.0,
        "kinds": counts,
        "min": min(dated).date().isoformat() if dated else None,
        "max": max(dated).date().isoformat() if dated else None,
    }
