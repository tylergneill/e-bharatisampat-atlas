# Do the texts change upstream? — settled on 2577 books

**Question.** Our scrape and Vishvas Vasuki's dump captured the same books years
apart. If the texts differ, is EBS *editing* its corpus over time, or are the two
scrapers just extracting differently? And does the `uploaded` timestamp — the
one chronology signal EBS gives — mark a *revision* when it runs ahead of serial
order?

**Answer: extraction, not change; and the timestamp marks an addition, not a
revision.** Measured 2026-08-21 by `pipeline/dump_analysis.py`
(`make dump-analysis`). Re-run 2026-08-31 with the walk complete; the
conclusion did not move.

## The three findings

**1. A post-dump timestamp almost always means a NEW item.** Of the 3318 items
stamped after 2025-02-28, **3276 (98.7%) did not exist in the dump at all**.
Only 42 were present in 2025 and later restamped. So the dominant meaning of
`uploaded` is date-of-addition, exactly as the About page's chronology assumes.

**2. Those 42 re-uploads show no corresponding text change.** Across the 2626
books held at both ends, the restamped ones are statistically indistinguishable
from the rest (re-run 2026-08-31, after the tier-3 walk completed):

                    n      within ±2%
    restamped      42         66.7%
    unchanged    2584         70.4%

The original measurement at n=2577 gave a permutation test on |ratio-1| of
p = 0.65.

**There is no effect.** The restamped group deviates *slightly less*, if
anything. A timestamp that disagrees with serial order is a re-registration of
the record, not a revision of the text.

**3. The residual ±2% is extraction difference, and at least part of it has a
name.** It is present in both groups equally, which is what rules out editorial
change as its cause — but "noise" was too kind. Serial 5852's entire delta is
**our fetcher dropping EBS's critical apparatus**, which lives in `title=`
tooltips that `strip_markup()` deletes along with the tag
(the anchor-`title=` capture in rivulet's fetcher). That loss is systematic, so it sits inside
the ±2% band rather than showing up as an outlier — a reminder that a book
matching on size is not thereby a book we captured correctly.

## Three traps this had to avoid, all of which bit first

**The dump is a live repo, not a snapshot.** 124 commits from 2025-01-31 to
2026-07-10. It is *effectively* frozen — 2737 text files by 2025-02, none added
since — but later commits still rewrite files: 762 non-`_index` text files
differ in bytes between Feb 2025 and HEAD, median 441 lines changed.

**Those diffs are formatting, not re-scraping** — checked by eye, four
examples spanning the range:

    lines    serial  what changed
        3      2795  frontmatter: comma -> hyphen in `books contributor`
       20      3827  anusvāra -> homorganic nasal (सांघिकं -> साङ्घिकं)
      929      5852  whitespace / line re-wrapping, +282 bytes
  737,268      3498  orthographic normalization again; the 739,295 -> 24,077
                     line collapse is incidental reflow, -5% bytes

Serial is stable at both ends in every case, and **orthographic normalization
is the recurring pattern** — the two largest diffs are both that, with the line
churn a side effect of reflowing rather than the change itself. Line count is a
bad proxy for how much moved.

So pinning to commit `6de660bf5` is cheap insurance rather than a correction of
anything — but pin anyway: it costs nothing, removes the question, and the
normalization *does* move Devanagari counts slightly, which is part of the
residual spread below. Note this is the dump's own editorial layer, not EBS's:
whether Vishvas normalized or the site did is untested.

**Filenames are not identities.** The upstream scraper reuses them across
records: **48 of 756 path-joins pair two different books** (`kathAsaritsAgaraH.md`
is serial 9213 at HEAD, 432 at baseline; `gaNakArikA.md` 10119 vs 4015). Join on
the `"serial no."` each file declares. Path-joining produced a spurious n=4
"100% of restamped books changed" result that inverted on correction.

**Incomplete books read as upstream deletions.** A book stopped at the tier-3
chunk ceiling has real text but has not ended. Serial 10045 showed ratio 0.503
purely from our own truncation. Filter on `complete` in `text_fetch_log.jsonl`.

## Still open

- **The apparatus defect** — see `scratch/todo.md` — means every ratio
  here is measured against text we know to be short. It does not disturb the
  finding — the loss is systematic and hits both groups — but re-run the
  comparison after that fix, since it moves the whole band, not one book.
- **What EBS actually changes on re-upload** is not diffed here — this shows
  the *quantity* of text is stable, not its content. But with no size effect at
  n=42 vs 2584, whatever a re-upload does, it is not adding or removing
  material, and a content study was judged not worth doing.

## Related

- `site-structure.md` — the upload-date convention and the proofread axis
- `snapshot-defects.md` — defects in the snapshot text itself
