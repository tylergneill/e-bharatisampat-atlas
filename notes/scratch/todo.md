# TODO

**The backlog spine.** Every open item lives here; the top-level notes hold the
evidence behind them.

Check items off as they're done, and delete a finished item rather than keeping
it checked — if it left an insight worth having, promote that to a top-level
note or a code comment first. See `../CLAUDE.md`.

## Growth axis (axis 2) — not built

EBS is the only Atlas with two independent time signals: serial number gives
arrival *order*, the img filename timestamp gives last touch. Interpolating
dates from serial order, corrected where the timestamp contradicts it, is
inference and must be labelled as such — not measurement.

- [ ] Build the serial→date interpolation, with the timestamp correction pass.
- [ ] Publish that this Atlas's series is `inferred`, so the parent can caveat
      per-series. (Transport is settled: the contract reads `changelog.json`.)
- [ ] `all_stats` omits `last_changed`, which the fetch journal already knows.
- [ ] When the snapshot track is retired, the changelog's coverage overlay —
      which measures the snapshot's ~45% scraper failure — goes with it.

## De-wikisource the inherited codebase

The project was copied from `../sanskrit-wikisource-atlas`, so anything not
deliberately changed may still be shaped for a MediaWiki dump — namespaces,
transclusions, orphan categories, monthly snapshots — none of which exist here.
Delete rather than keep-just-in-case.

**Re-checked 2026-08-31: the frontend has substantially diverged.** Only
`topbar-height.js` is still byte-identical to the sibling; `styles.css`,
`app.js`, `anchor-details.js` and `translit-static.js` all differ, and no
`wikisource` reference survives in `styles.css` or `index.html`. The two
mentions left in `about.js` and `translit-static.js` are deliberate
cross-references, not leftovers.

- [ ] **`docs/styles.css` is 59K and grew rather than shrank.** The two-axis
      rewrite added to it without pruning. Dead rules for UI that no longer
      renders (shared-category highlighting, `index_items`, subpage lists) are
      the likely bulk, but this now needs measuring rather than assuming.
- [ ] **Non-code leftovers** — `docs/VERSION`, `.gitignore`, `requirements.in`,
      Makefile targets. Small, but the same question each time.

## Phase 1 leftovers (small, safe)

- [ ] **Use `languages` in the frontend.** Both builders emit the normalized set
      per work alongside the raw string; **nothing reads it yet** — the rewrite
      carried the field through without adding a filter. Still the natural first
      facet, and now it would be a third axis or a filter across both existing
      ones, which is a design question rather than a mechanical one.
- [ ] **`.github/workflows` for Pages**, mirroring the sibling's verify-then-
      publish gate, once the content is worth publishing. Note the sibling
      gates on `pipeline/verify_publish.py`; there's no equivalent here yet.
## Research EBS's actual structure, then teach it

**We do not yet have a clear picture of how ebharatisampat.in is organized**,
and the snapshot cannot give us one — it is one scraper's rendering of the site,
covering ~21% of the catalogue, and is for bootstrapping only. Our whole
domain → sub-domain → author tree is inherited from its frontmatter and has
never been checked against the site's own categorization.

Destination: an **About page with a teaching section**, modeled on the sibling's
(`../sanskrit-wikisource-atlas/docs/about.html` — "Practical Intro to Wikisource
Structure", then "Obtaining and Representing…", then data quality). Its register
is worth copying: name the site's own jargon, explain the mechanism concretely,
give a real example.

Order of work: **research → record findings in a note → convert the note into an
About section.** Do not write UI copy straight from provisional notes.

Findings go in **`site-structure.md`** (reference, never deleted), which
already covers the first two items below.

- [ ] **A size-over-time graph for the texts.** Same axis, but bytes rather than
      counts, using the byte figures the tree already carries. Texts only —
      scans have no meaningful size in this sense.
      **No page-count equivalent is wanted**: `pages` is a printed-edition
      field, present on only 1377/2287 (60%) of the snapshot's books and absent
      by construction on contributed digital texts, so it would measure the
      print-provenance population rather than the collection.
## Judgement calls worth revisiting after looking at the UI

- [ ] **Spill the essential metadata into the interface itself**, not just the
      ⓘ link. Started 2026-08-12: a work row now shows **author, publish year,
      and size** (where each exists) plus format badges. Every other field ships
      in the tree and is still ignored — publisher, printer, editor, second
      editor, three commentator slots, commentary name, translator, books
      contributor, pages, language. Which earn a place inline is **to be decided
      gradually while browsing**, not settled up front. Filtering/faceting
      follows once the fields are visible.

## Phase 2 — independent acquisition

- [ ] **Decide whether the apparatus fix forces a refetch.** **Blast radius now
      measured: 10 of 39 random `readbook3` books (26%) carry apparatus**, 1 to
      2566 notes per chunk. So roughly **1,400 of the 5538 cached books** hold
      text fetched by the old code, and their `text_sizes.jsonl` byte counts
      are short by an unmeasured amount — landing on the one thing tier 3
      exists to produce. **It cannot be narrowed from the cache**: the attribute
      is already gone from disk, so there is no way to tell which cached book
      had apparatus without refetching it. Either a full 5538-book refetch, or
      a sampled estimate published as a stated error bar. `make count-sizes`
      alone cannot help — it re-measures the same truncated files.
- [ ] Verify by refetching books that exist in the snapshot and diffing.
      **Now easier than when this was written:** both corpora build to the same
      shape, so `tree.json` and `snapshot_tree.json` can be diffed directly on
      the 2287 overlapping works — join on `serial`, since the two sources
      encode the id differently (snapshot decoded, metadata base64).
- [ ] **Make acquisition rerun `make count-snapshot-sizes`.** Sizes are cached in
      `data/snapshot_text_sizes.jsonl` and `build-snapshot-tree` trusts them blindly,
      so once the corpus stops being static, whatever updates it owns refreshing
      that cache — or the site silently publishes the previous pull's numbers.
      Narrower than it was: only the snapshot track reads that cache now.
- [ ] Once tier 3 lands, drop the `raw_etexts` dependency entirely — delete
      `config.snapshot_root`, `parse_snapshot.py`, `count_snapshot_sizes.py`,
      `build_snapshot_tree.py`, `snapshot_tree.json`, the `--snapshot` serve
      flag, and `snapshot-defects.md`.
      **Also drop `build_changelog`'s coverage overlay** — its `--inventory`
      arg, the `snapshot_ids` set, and the fourth series. Checked 2026-08-19:
      the changelog does **not** need a two-track split the way the tree
      builder did. Its spine is `catalogue.jsonl` (ours); the snapshot enters
      only as a named side-series measuring *the gap between the two corpora*,
      which is meaningless split in half — a snapshot-only changelog would
      compare the snapshot to itself. The `args.inventory.exists()` check is
      already soft, so it degrades to the three real bands on its own.
      Deleting the code layer does **not** touch the `raw_etexts` checkout
      itself — that lives outside this repo. But the re-upload diff study (next
      item) is the one thing still reading it, so confirm that checkout is
      somewhere durable before dropping the last code that knows where it is.

- [ ] **Author strings need deduplication.** 3407 distinct strings, but they are
      not 3407 people: `अप्पय्यदीक्षितः` and `अप्पयदीक्षितः` are one author under
      two spellings, and the author axis shows them as two entries. Normalizing
      whitespace/case/punctuation collapses **zero**, so this needs real
      orthographic matching (anusvāra, gemination, vowel length, honorific
      prefixes) — the same class of problem `languages.py` solved for the 87
      language strings, and probably the same shape of solution.
      2521 of the 3407 are singletons, so the tail is long.
- [ ] **Verify the diacritic-folded search in a browser.** Added 2026-08-12 so
      `kadambari` finds `कादम्बरी` (14 works). The folding logic was verified
      directly, but **the fix was never seen running on the page** — the browser
      session ended before it could be checked.
- [ ] **The work-list cap does not bound a domain.** `WORK_LIST_CAP` applies per
      sub-domain independently, so selecting दर्शनानि renders ~2100 works and
      ~16k DOM nodes (~220ms) despite the cap. Acceptable now; the real fix is
      virtualized rendering, which is a bigger change than it is worth today.
- [ ] **`pdf_count` is structurally 0 in the snapshot tree**, and that is not a
      real zero — the snapshot only ever captured Unicode text, so it knows
      nothing about scans. Marked in `build_snapshot_tree`, but any UI that
      shows a PDF count will under-report on that source. Goes away with the
      snapshot.
- [ ] **`styles.css` grew rather than shrank.** The rewrite added the axis
      switch, group pill, badges and work lists without pruning the wikisource
      rules underneath. Folds into the de-wikisource item above.

## The catalogue has drifted since the 2026-08-14 capture (found 2026-08-22)

The listing membership snapshots under `data/listing_membership/` disagree with
`data/catalogue.jsonl`, and the gap is real movement upstream, not noise:
**4192 Unicode ids captured 08-14, 4214 on 08-21** — 24 added, 2 dropped, net
+22. The two dropped are serials 981 (`केशवीशिक्षा`) and 1502
(`अध्यात्मतरङ्गिणी`); the additions cluster at high serials (9000–10557), which
reads like recent uploads landing in bulk.

- [ ] **Rerun the metadata fetch, then reparse.** The 24 new ids are not in
      `docs/data/metadata.json` at all for the fields that matter — 20 of them
      come back `text=None`, which is our *absence of a record*, not a measured
      "this work has no text". Until they are fetched we cannot say which of
      them are text-bearing, and every total derived from the catalogue is
      quietly stale.
      `make fetch-metadata` then `make parse-metadata`.
      *Hits the network; needs `make clearance` first, one request per 2s.*

- [ ] **Supplement the full-text fetch with the new Unicode-text items.**
      Once the metadata is refreshed, any of the 24 that turn out to carry a
      reader needs its text fetched so `text_sizes.jsonl` covers it — otherwise
      the size axis under-reports the works added since 08-14. Of the 4 that
      already show a reader in current metadata (serials 4633, 8801, 10303,
      10557, all `readbook3`), only 4633 has been fetched — **8801, 10303 and
      10557 are missing from `text_sizes.jsonl`**.
      `make fetch-text` resumes and never refetches, so this is additive:
      a bounded run (`MAX_REQUESTS=…`) is enough to pick up the tail.

- [ ] **Recheck the "error runs one way only" claim** published in the Data
      Quality audit. It says *"every item it does show does have text. Nothing
      is listed that should not be"*, which was true of the 08-14 capture
      (`contradictions == 0`). On the 08-21 membership it is **not** obviously
      true: 20 of the 24 additions have no text record. If the refetch confirms
      they genuinely lack a Unicode reader, the Unicode listing has the same
      over-inclusion defect the E-Books finding reports, and that sentence in
      `render_hidden_books` has to go or be qualified.

**Why this was not visible before:** the audit's gap figure comes from the live
listing total, but the *names* come from `catalogue.jsonl`, which is a
capture with a date on it. The two were never compared against the membership
snapshots, so an 8-day drift sat between them unnoticed. Worth deciding whether
`catalogue.jsonl` should simply be regenerated whenever a membership snapshot
disagrees with it.

## Books stopped shallow by `dead-run`

- [ ] **~20 books are still stopped shallow, and are the same shape as the
      three that were recovered.** Every one stopped at `my_id=4` with 1 chunk
      written, against page counts up to 1017 — front matter, almost certainly,
      not an ending. They were out of scope on 2026-09-04 only because that
      pass took the zero-chunk books; these wrote one chunk and so were not in
      that set.

          491 539 547 576 636 659 1177 1178 1179 1180 1181 1196 1204 1795
          8569 518 516 1061 6876 10441

      Note 1177-1181 are five consecutive volumes of one work, all stopped at
      4, and 539 claims 1017 pages but yielded 308 bytes — the scan's barcode
      slip. Run them the same way:

          SERIALS=491,539,... PATIENCE=15 ./run_ladder.sh 150 300 600 1200

      *Hits the network; needs `make clearance` first.* Re-derive the list
      before running — it is a measurement, and the count moved 45 -> 57 as
      more books were walked.

## The audit classifies 2 works nowhere (2026-09-07, narrowed 2026-09-08)

Every text-bearing work should land in exactly one place: measured empty,
measured as carrying no Devanagari, or fine. Ten did not, and they were
silently absent from the About page rather than wrong on it -- which is worse,
because nothing on the page indicated they exist.

**Eight of the ten are fixed (2026-09-08).** They were English books with one
or two stray Devanagari characters, excluded by an exact `devanagari_chars ==
0` test. `NO_DEVANAGARI_SHARE = 0.01` replaced it, and all eight now appear in
"Items with non-Devanāgarī text" (30 items). The threshold is read off a gap in
the corpus, not chosen: highest share with no Devanagari body is 0.0082, lowest
above it is 0.0106.

    8782   deva=1    297 KB   Antiquity of Hindoo Medicine
    7589   deva=2     81 KB   samskrta-imskripta
    8768   deva=2    385 KB   Indian Cultural Influence in Cambodia
    3475   deva=3    387 KB   samskrtam-vaidyakiya-matrkah
    7701   deva=5    950 KB   Studies on the Ice Age in India
    7668   deva=11   934 KB   The Ancient Geography of India
    9929   deva=12   147 KB   Abhinayadarpanam
    1354   deva=29   457 KB   Nyayabindutika (with English translation)

*(The eight above are now covered; the list is kept as the record of what the
exact-zero test excluded.)*

**Two remain, and they are the standing gap.** 3085 and 2736 below. Both need a
defect *asserted* rather than measured, which is exactly what the verdicts
guard refuses -- so neither is reported anywhere on the About page today.

**3085 is a different failure and needs a different test.** `candrikabinduh`
has 44 Devanagari characters in 644 bytes -- its title plus `prathamah
adhyayah` and `dvitiyah adhyayah` over the site's footer chrome. It announces
two chapters and delivers neither. A proportional test may well pass it (44
chars is not a small fraction of 644 bytes); **what condemns it is the absolute
size.** So the emptiness side needs an absolute floor as well as the
proportional one on the script side. Still unfixed: 3085 clears the 0.01 share
test at ~20% and is counted among the healthy works.

**2736 is the tenth, and structural.** `agnipuranam-alankaradhyayah` is
login-gated: the fetch never completed, so there is no measurement, and
`_text_size_ids` only counts a completed 0-byte fetch as empty. The audit's
docstring says an unfetched work "counts as non-empty, not as unknown", which
is right for a work still queued and wrong for one retired after 5+ failures
with a known, permanent cause.

Note it is NOT established that 2736 has text: `text: read_chapter` in the
metadata is the site's claim, and the login wall stopped us before it could be
tested. That is a third state -- claimed, untestable -- distinct from both
"measured empty" and "has text".

**Why this is deferred rather than fixed now:** both 3085 and 2736 need a place
to be *reported*, and `apply_manual_verdicts` deliberately refuses any verdict
on a work the measurement did not flag ("a verdict may only narrow a
measurement, never assert one"). Giving these a home means either relaxing that
rule -- which is the guard that keeps hand-written claims from rotting -- or
adding a finding sourced from the journal rather than from `text_sizes.jsonl`.
That is a design decision, not a threshold tweak.

## The resume cursor is only as good as the ending that set it (2026-09-07)

`next_my_id` is where the next pass starts. It is written by whatever ended the
previous pass -- and the endings are not equally trustworthy, so neither is the
cursor they leave behind.

    warning     the site's own "no such row". Certain. Cursor is sound.
    ceiling     we stopped it while text was still arriving. Cursor is sound.
    budget      same. Cursor is sound.
    interrupt   same. Cursor is sound.
    error       the request failed; the cursor deliberately does not advance.
    dead-run    a GUESS -- the walk inferring the book ended because chunks
                stopped yielding text. Its own docstring says "strong
                evidence, not proof."

**Only `dead-run` writes a cursor that was never confirmed by the site**, and
that is the one that has repeatedly gone wrong.

### Why a wrong cursor is worse than an ordinary bug

It is silent, self-confirming, and permanent:

1. A `dead-run` parks the cursor somewhere past the real text.
2. The next pass starts THERE, asks for rows that do not exist, and gets
   `warning` -- the certain ending.
3. It concludes the book is finished, marks `complete`, and advances the
   cursor by one.
4. Every later pass inherits a slightly worse starting point.

Nothing errors. The book looks finished. And the escape hatch does not reach
it: `--serials` was built to override the journal's `complete` flag -- because
selecting a book by hand IS disputing its ending -- but **nothing overrides
`next_my_id`**, so the one tool for disputing a bad ending cannot dispute a bad
cursor.

### Two books lost this way, found 2026-09-07

**8569** `anusthanaprakasah` sat at 53 bytes -- its own title -- through two
ladders at patience 50 and 75, while the site plainly served a full book. Its
Aug 15 pass ended `dead-run` at cursor 4; every pass after asked for rows 4,5,
6... and got `warning`. The whole book was at `my_id=0`, permanently behind the
cursor. Clearing its journal rows and cache recovered **543 KB in 3 requests**.

**10441** `brhannighanturatnakarah` is the same, and larger. Cached at 3,391
bytes with the cursor at 5. Probing `get_unicode.php` directly:

    my_id=0    1,535,102 bytes   662,764 Devanagari
    my_id=1       94,377 bytes    46,857 Devanagari
    my_id>=2         139 bytes    WARNING -- genuine end of rows

**The book is two chunks and we hold none of them.** 1.6 MB behind a cursor of
5.

### Patience cannot fix this, and higher patience never will

Both books hit `warning` on their first request of every later pass. A
`warning` stops the walk immediately, before the patience counter is ever
consulted -- so 10441 at patience 200 makes one request, gets `warning` at
cursor 7, and stops, exactly as it did at 50. **Patience and cursor are
independent failures**, and only one of them was fixed today.

### The rule

**Never trust a cursor left by `dead-run`.** Restart those books at `my_id=0`.
Every other ending either heard it from the site or was imposed by us, and its
cursor is a valid resume point.

This subsumes any size- or signature-based heuristic (an earlier attempt here
tried "small content but high cursor", which is guesswork), needs no threshold,
and would have caught both books automatically. The cost is bounded: a
`dead-run` book that really did end re-walks itself once, and a resumed book
already reads its own cached text so a repeated chunk is recognised as dead
rather than appended twice.

**Not implemented.** It belongs at the resume site in rivulet's
`fetch_fulltext.py`.

### What a from-scratch second pass would and would not fix

A full refetch into an empty journal is immune to this by construction -- every
book starts at 0 and inherits no cursor. Worth being precise about why, because
it is *not* due to anything changed on 2026-09-06/07:

- **Patience 3 -> 50** fixes real dead runs mid-book. It would NOT have saved
  8569 or 10441; both were stopped by `warning`, not by impatience.
- **The audit changes** are measurement-side and do not touch fetching.
- **The cursor rule** above is still only a proposal.

So the cursor liability is fully present on the incremental path -- which is
the path normally used. That is the argument for implementing the rule
regardless of whether a second pass ever happens.

And a second pass still cannot see what no fetch can: 2736's login wall, the
text-bearing PDFs with no code path, and the works whose reader genuinely
serves nothing.

## `toc` / `divisions` / `measured_at` lost from text_sizes.jsonl (2026-08-22)

Rebuilding `data/text_sizes.jsonl` with `make count-sizes` dropped three fields
that an older fetcher had written straight into it: **`toc`, `divisions`,
`measured_at`**. They are gone and not recoverable offline — the fetch journal
(`text_fetch_log.jsonl`) never carried them, so there is nothing to re-derive
them from. Only 1 row of 5030 survived in a backup taken after the fact.

`count_sizes` is now lossless for everything the journal DOES hold:
`raw_bytes` (journalled as `bytes` — the name mismatch is why a first attempt
silently carried nulls) and `unproofread` are carried forward, and the 17
works whose fetch returned nothing are emitted as explicit zero rows instead
of being skipped for having no cache file.

**Impact is small but real.** `toc` was `None` on every row, and nothing
downstream reads `divisions` or `measured_at` — `build_tree` ships only
`SIZE_KEYS`. So no published figure changed. But the TOC structure was a real
measurement of the reader's chapter markup.

- [ ] **Decide whether `toc`/`divisions` are worth recovering.** They only come
      back from a refetch, which for `read_chapter` books is one request each
      (the whole book is inline). If they are wanted, the fetcher should also
      journal them, so the next `count-sizes` cannot drop them again — that is
      the actual bug: the sizes file held the only copy of a fetch-derived
      measurement.

## Keep the raw responses — parse locally, forever (2026-08-22)

**The fetcher throws away the source and keeps only its own reading of it.**
`strip_markup()` runs at fetch time, per chunk, and only the extracted text is
written to `data/fulltext_cache/`. The HTML response is never stored. Every
parser bug is therefore permanent until a refetch, and a refetch costs the
whole walk.

This is not hypothetical — it has already cost us twice:

- **The `title=` apparatus.** Tag stripping deleted attributes along with the
  tags, so the critical apparatus EBS publishes in anchor tooltips was silently
  discarded until 2026-08-21. It affects **10 of 39 sampled books**, a quarter
  of the corpus, and the loss was systematic rather than occasional — a book
  missing 6% of its text still passed a 0.999 size-ratio screen. The fix landed
  in the parser, but **every book fetched before it keeps the damage**, because
  the text those anchors carried is not in the cache to re-extract.
- **`toc` / `divisions` / `measured_at`** (see the section above): same shape,
  different field. A fetch-derived measurement lived in exactly one place and
  a rebuild dropped it.

### The economics are lopsided, and we got them backwards

Markup is ~30% of the response, which felt like a reason not to keep it. It is
not, measured against what discarding it costs:

    cache on disk now          3.57 GiB   (5,539 files, text only)
    raw:content ratio          1.44x
    raw archive would be       5.13 GiB   -- 1.56 GiB more than now
    gzipped at ~5x             ~1.03 GiB  -- LESS than the current cache

    chunks walked so far       182,078
    refetch at 1 req/2s        101 hours  = 4.2 days of polite scraping

**1.56 GiB uncompressed — or about 1 GiB gzipped, smaller than what we already
store — against 4.2 days of refetching.** Storage is the cheap resource here by
three orders of magnitude, and it is the only one that buys unlimited retries.

- [ ] **Store the raw response, before the eventual refetch — not after.**
      Whatever refetch we do next is the one chance to capture this cheaply;
      doing it later means paying the 4.2 days twice. Write the response body
      per chunk (gzipped, e.g. `data/raw_cache/<serial>/<chunk>.html.gz`), and
      make `fulltext_cache/` a *derived* artifact rebuilt from it offline.

- [ ] **Make text extraction a local, re-runnable stage.** Once raws exist, the
      parser stops being a one-shot decision made at network time: a
      `make extract-text` reruns over the archive in minutes, and finding a
      parser bug costs a rebuild instead of a walk. This is the same split that
      already works for sizes — `count_sizes` rebuilds `text_sizes.jsonl` from
      the cache offline, which is exactly why a change to how bytes are counted
      does not cost 5,557 refetches (see `../CLAUDE.md`, "Sizes are derived,
      never fetched twice"). Text extraction should have had it from the start.

- [ ] **Keep the raws after the refetch.** The point is not one recovery; it is
      that every future parser question — apparatus, TOC structure, verse
      numbering, whatever is found next — becomes answerable offline. Treat
      `raw_cache/` as carried-between-machines data alongside the journals
      (`../CLAUDE.md`, "What to carry between machines").

**The general rule this is an instance of:** never let the network stage be the
only thing that has seen the source. Fetch, store verbatim, parse separately.
Each of the three bugs above is the same mistake wearing different clothes —
a fetch-time transformation with no way back.

## Measure Sanskrit content directly, not by stripping furniture (2026-08-24)

The size pipeline currently measures a book by **subtraction**: take everything
the reader served, strip the markup and the known chrome, transliterate what is
left. That makes every size figure only as good as the stripping, and the
stripping is known-imperfect — material is being filtered at *fetch* time
rather than locally, which is its own open bug (deliberately not addressed
here). Front matter, publisher boilerplate, and roman apparatus all survive
into `content_bytes` and are counted as if they were text.

**Proposed inversion: measure additively.** Instead of asking "what is left
after removing what we recognize as furniture", ask "what do we positively
recognize as Sanskrit". Walk the text, keep contiguous runs of Devanagari
(`DEVANAGARI = ("ऀ", "ॿ")`, already in `pipeline/text_measure.py`), allow intra-run
punctuation, digits, and whitespace so a daṇḍa or a verse number does not
split a run, then transliterate and count **only those runs**. Front matter
in English, page furniture, and nav text never enter the count, so the metric
stops depending on how well stripping worked.

This is a **new statistic alongside the existing three**, not a replacement —
`raw_bytes`/`content_bytes`/`transliterated_bytes` stay as they are so nothing
already published silently changes meaning. It belongs in `count_sizes.py`'s
`measure()` and its snapshot twin `count_snapshot_sizes.py`, both of which are
pure functions of cached text and cost nothing to rerun (no refetch).

**The one thing that must not be forgotten** — it is already written down at
rivulet's `fetch_fulltext.py` and a naive positive filter walks straight into it:

> Deliberately NOT a positive test for Devanagari. Keeping only Devanagari-
> bearing lines would also delete legitimate roman-script content — serial
> 2367 is the entire Rigveda in romanized transliteration, 1.4 MB with zero
> Devanagari, and a positive filter reduces it to nothing.

**Update 2026-09-07: those 65 have now been read, one by one.** The audit
publishes them as their own finding (`pipeline/audit.py`, `render_empty_texts`), and the
"mix, not one category" warning below was right -- the split is pre-IAST or
OCR-corrupted IAST (8), pre-Unicode font encodings such as Balaram (3),
English or German (9), and one work that is pure OCR noise. The count is 21
rather than 65 because the ladders of 2026-09-06/07 filled in the books that
were empty for want of fetching, not for want of Devanagari.

That strengthens the case for the inversion proposed here: most of these hold
a real text that a decoding or transliteration pass would recover, and a
positively-measured Devanagari statistic would score every one of them near
zero while `content_bytes` still shows the text is there. Both columns are
needed, exactly as the note says.

Measured 2026-08-24 over `text_sizes.jsonl` (4885 books), so the size of the
exposure is known rather than guessed:

- **65 books have zero Devanagari**, 7.2 MB of `content_bytes`.
- **110 books are under 30% Devanagari by bytes**, 28.1 MB — **0.9% of the
  corpus**.
- Those 65 are a **mix, not one category**: serials 2367/2369 (Rgveda),
  2305 (Taittirīya Saṃhitā), 1527 (Nirukta) are real romanized Sanskrit,
  while 8791 (`a-zArThisTri-Aph-Aryan-meDikal-sAyans`) and 8788 (`India
  Through The Ages`) are genuinely English books.

So the new statistic must be reported **as** what it is — Devanagari-script
content — and a romanized book legitimately scores near zero on it. That is
correct behaviour, not a defect, but it means the field cannot be relabelled
"Sanskrit content" without also detecting romanized Sanskrit, which is a
harder problem (IAST diacritics vs. plain-ASCII English) and should not be
bundled into this change. Keep the existing counts so those books remain
visible in some column.

**Why it is worth doing:** the current aggregate hides a wide spread. Markup
and headers are 28.2% of raw bytes corpus-wide, but the **median book only
sheds 11.5%** — the aggregate is carried by a minority of deeply paginated
books whose per-page furniture repeats hundreds of times. A positively
measured statistic would not have that shape, and the two disagreeing is
itself the diagnostic for where stripping is failing.

- [ ] Add the run-based counter to `pipeline/text_measure.py` next to `devanagari_chars`,
      wire a new field through `measure()` in `count_sizes.py` and
      `count_snapshot_sizes.py`, and rerun both (local, no network).
- [ ] Compare the new field against `transliterated_bytes` per book; the books
      where they diverge most are the stripping failures, which feeds the
      fetch-time filtering bug.
- [ ] Only then revisit the About page's "Calculating Size Information"
      section — see the item below.

- [ ] **About page wording, independent of the above.** The step-1
      parenthetical reads "stripping content of markup and headers (30% by
      data volume)", which is ambiguous between "markup is 30% of the raw
      bytes" (true: 28.2%) and "this removes 30% of the content" (wrong
      sense). A reader compounding the two steps lands at ~35% raw→IAST when
      the measured figure is 38% (1.74 GB / 4.56 GB). Suggested minimal fix:
      "(~30% of raw bytes by data volume)". Step 2's "approximately 50% of
      the Devanāgarī byte count" is sound — 53.2% aggregate, 51.4% median.

- [ ] **Stale sanity-check constant.** `count_snapshot_sizes.py:110` prints
      `(sibling observes ~1.975x)` as the expected deva:iast ratio, but the
      current `text_sizes.jsonl` yields **1.880x**. Cosmetic — it prints
      beside the real computed ratio — but misleading to anyone using it as a
      check.
