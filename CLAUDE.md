# e-bharatisampat-atlas

A browsable atlas over the **ebhAratI-sampat** corpus (ebharatisampat.in), one
of the `sagara-sangama` atlases. A `pipeline/` emits `docs/data/tree.json`; a
single-page frontend in `docs/` browses it.

This repo **publishes no text of its own.** It indexes metadata and structure
and links out to ebharatisampat.in. It does *cache* text locally -- 4.0 GB
across 5539 files under the gitignored `data/fulltext_cache/` -- but that is a
working artifact for measuring byte sizes, and none of it ships to `docs/`.

**Fulltext ACQUISITION is not in this repo.** It moved to the private
`rivulet` package; see "Fulltext lives in rivulet" below.

## `notes/` — structure, research, and tasks in flight

**The shape is the same in all five repos:**

    notes/*.md        non-trivial notes on structure -- why it is built this
                      way, what will bite you. NOT a record of how a decision
                      was reached or what the state of play was on some date.
    notes/<topic>/    folders of research material: samples, one-off analysis
                      scripts, measurements kept so a figure can be re-derived
                      rather than re-guessed. Each carries its own README.
    notes/scratch/    tasks in flight -- plans, scoped designs, measurements
                      under way, and the backlog itself.

**The lifecycle.** A new task is written into `scratch/`. When it finishes, any
insight worth keeping is **promoted** into a top-level note (or into a code
comment beside the thing it explains) and **the scratch file is deleted**.
Nothing is kept because it was expensive to write.

Keep top-level notes short. A long one usually means a task's history was never
cut out of it.

### When asked what's left

On "what do the notes say we need to work on" (or any variant — "what's next",
"what's still open"), **read the notes and answer from them.** Don't guess from
code or git history.

1. `notes/scratch/todo.md` is the spine — every open `- [ ]` item. Start there.
2. Everything else under `scratch/` is a task in flight; check its status line,
   and check it against the code before acting on it.
3. Top-level notes are **reference, not backlog** — they explain the thing, they
   do not list work.
4. Report the open items with enough context to choose, and lead with anything
   marked blocking. (The access decision that used to gate phase 2 was
   settled 2026-08-11 — proceed politely, terms at the top of
   `scratch/todo.md`.)

### Chipping away

- **Check the box** (`- [ ]` → `- [x]`) when an item is done, and say so plainly.
  If part of it is still open, check it anyway and note the remainder — either
  inline or as its own item. Don't leave a finished item unchecked because a
  loose end survives it.
- **Delete a whole note file once everything it covers is resolved** — that is
  the intended end state, not an unusual step. `snapshot-defects.md` disappears
  when phase 2 replaces the snapshot; a note disappears once the
  fetcher exists and works. **Exception: files marked reference at the top**
  (`site-structure.md`) are durable and stay.
- **Record what the site teaches you in `site-structure.md`**, separately from
  what the snapshot suggests. The snapshot is one scraper's rendering of the
  site, covering ~21% of the catalogue — provisional by construction. Keep the
  two straight: site-sourced claims are usable, snapshot-derived ones are
  hypotheses to test.
- **Prune sections the same way.** A resolved §-section comes out of the file
  rather than accumulating "(done)" markers.
- **Add what you learn.** New defect, new constraint, new open question → it goes
  in the relevant note as a new item, with the detail needed to act on it later.
  Findings that close a question can be recorded as closed so nobody re-opens
  them (see `snapshot-defects.md` "Checked and cleared").
- **Editing freely is expected.** Correct notes in place when something is
  disproven. No preserved wording, no changelog ceremony.

### Two cautions

- **Don't cite a notes figure as fact — re-derive it.** Many are measurements of
  a third-party snapshot that changes under us. `snapshot-defects.md` §2 is the
  standing example: a pull moved the empty-book count 13 → 12 and falsified the
  named example the section's explanation rested on. When a claim survives
  verification, record which upstream pull it was checked against.
- **Don't promote note prose into README or UI copy** without re-checking it.
  Provisional-but-useful is the right register for a backlog; user-facing text
  needs a higher bar.

**`notes/samples/` is evidence, not backlog.** It holds retrieved source material
(e.g. the serial-1618 text backing the `snapshot-defects.md` case). It is not
deleted when tasks close.

## The data underneath is borrowed

**Mostly historical as of 2026-08-12** — the atlas is now built from our own
metadata scrape (`docs/data/metadata.json`, 11066 works). The snapshot supplies
exactly one thing the scrape does not: **measured byte sizes**.

That snapshot is a **third-party checkout** at
`raw_etexts/mixed/ebhAratI-sampat/` — not ours, not committed here, never
written to. Location resolves via `pipeline/config.snapshot_root()`,
overridable with the `EBS_SNAPSHOT` env var or `--snapshot`.

It is incomplete (2287 books, 21% of the catalogue; ~44% of `urls.md` never
materialized) and has known defects. Tier 3 has replaced its byte sizes with our
own, so the whole snapshot track can be deleted rather than reconfigured.

## Commands

| Command | Does |
|---|---|
| `make parse-metadata` | tier-2 cache → `docs/data/metadata.json` (11066 works, no network) |
| `make clearance` | **NETWORKED. NEEDS `rivulet`** (exits 2 without it). Establishes session clearance → `data/clearance.json`. Run first; the other three need it |
| `make fetch-metadata` | **NETWORKED. NEEDS `rivulet`** (exits 2 without it). One `readSearch.php` per distinct work → `data/metadata_cache/` |
| `make fetch-text` | **NETWORKED. NEEDS `rivulet`** (exits 2 without it). readers → `data/fulltext_cache/` + sizes. Pass `MAX_REQUESTS=`; `MAX_CHUNKS=` is a resumable checkpoint |
| `make check-source-links` | **NETWORKED. NEEDS `rivulet`** (exits 2 without it, which is *inconclusive*, not failure). Have the shipped source links drifted? |
| `make count-sizes` | fulltext cache → `data/text_sizes.jsonl` (no network) |
| `make build` | `metadata.json` → `docs/data/tree.json` — **all 11066 works, no byte sizes** |
| `make parse` | snapshot → `data/snapshot_inventory.jsonl` (one record per book, no network) |
| `make count-snapshot-sizes` | snapshot → `data/snapshot_text_sizes.jsonl`, raw/content/IAST bytes per book (~1.5 min) |
| `make snapshot-tree` | inventory + sizes → `docs/data/snapshot_tree.json` — **2287 books, with sizes** |
| `make changelog` | `metadata.json` addition dates → `docs/data/changelog.json` (needs `parse-metadata`) |
| `make serve` | serve `docs/` on :8002 |
| `make serve-snapshot` | same, but serving the snapshot tree at the frontend's `tree.json` URL |

**Two parallel build tracks, never combined.** `build` is the real one. The
snapshot track survived only because it once carried the byte sizes our scrape
lacked — no longer true since tier 3 completed, so it is now a cross-check
rather than a dependency, and is deletable. Both emit the same shape
(`pipeline/shape.py`), so the frontend reads either — and **which one it gets is
a serve-time flag**, not a build-time one.

`snapshot-tree` requires both `parse` and `count-snapshot-sizes` to have run first, and errors
telling you which is missing. Byte counts are a pure function of the static
snapshot, so `count-snapshot-sizes` measures them once and `snapshot-tree` just reads them —
that split is why it never touches the 1.6G of source text. **It trusts the
cache and cannot tell it is stale**, so whatever updates the snapshot is what
reruns `count-snapshot-sizes`.

## What to carry between machines

`data/` is gitignored, so moving work to another machine means copying it by
hand. Only four things are expensive; everything else rebuilds locally in
seconds to minutes.

**Carry these** — they cost network requests to recreate:

    data/metadata_cache/            11066 requests, ~11h
    data/fulltext_cache/            the whole tier-3 walk
    data/metadata_fetch_log.jsonl   id -> serial map; tier-2 resume state
    data/text_fetch_log.jsonl       chunks_written; tier-3 resume state

**The two journals are not optional extras.** They are resume state, not logs:
`text_fetch_log.jsonl` records how many chunks each cached `.txt` holds, and the
files carry no chunk markers, so without it a resumed run would append from
chunk 0 onto a file that already has 20. Copy them with the caches they describe.

**Leave these** — they are pure functions of the above plus the snapshot:

    data/catalogue.jsonl            make catalogue LISTINGS=...
    data/snapshot_inventory.jsonl   make parse
    data/snapshot_text_sizes.jsonl  make count-snapshot-sizes  (~1.5 min)
    data/text_sizes.jsonl           make count-sizes           (no network)

## Everything networked lives in rivulet (since 2026-09-03)

**No acquisition of any kind is here.** Clearance, the metadata tier, the
fulltext walk and `check_source_links` all moved to `rivulet`, a *private*
package, because this atlas is public and the acquisition is the sensitive
part: the site is access-controlled, and **the atlas does not need the text** — it publishes byte sizes, and those are a pure
function of whatever cache is already on disk.

What stayed public: `parse_metadata`, `count_sizes`, `build_tree`, `shape`,
`text_measure`, and the audit — every check in it but the one networked prober.

**This widened from an earlier, narrower split.** Until 2026-09-03 only the
fulltext walk was private, and clearance was **duplicated** — a copy in rivulet
and `pipeline/clearance.py` here, because `fetch_metadata`,
`check_source_links` and `audit` all needed it locally. Those callers have now
moved too, so the duplication has no reason left and the Atlas copy is gone.
Likewise the two byte-identical page readers in `check_source_links` and
`audit`, which folded into `rivulet/verify/ebharatisampat/reader.py` — that
file's own comment had been waiting for "a third caller", and the move was it.

**The command surface did not change.** `pipeline/clearance.py`,
`fetch_metadata.py` and `check_source_links.py` still exist as thin runners
over `pipeline/fetch.py`, so every `make` target works as before.

### Where things land

    data/fulltext_cache/   what the site served
    data/text_extract/     clean plain text derived from it

The same two directories every Atlas uses. **`text_extract/` does not exist
here yet**: rivulet's `fetch_fulltext` strips markup and cuts page furniture as
it fetches, so `fulltext_cache/` already holds extracted text rather than raw
responses. Splitting those apart — a fetcher that keeps what was served, a
`text_extractor` that derives clean text from it — is the intended next step,
and it is the same argument `count_sizes` already makes about byte counts:
changing the rules should not cost 5557 refetches.

`pipeline/text_measure.py` holds the pure measuring functions
(`devanagari_chars`, `strip_furniture`, `to_iast`, `load_progress`) that
`count_sizes` needs and the departed fetcher also used. rivulet imports them
back from here. **rivulet may import from this Atlas; this Atlas may never
require rivulet *to build from a cache it already has*.** The import direction
is still one-way; what changed on 2026-09-03 is that acquisition now genuinely
does require the package — accepted deliberately, since there is no meaningful
way to obtain a gated corpus without the acquisition code.

### Three modes

1. **Without rivulet** — everything but fetching runs. Sizes come from an
   existing `text_sizes.jsonl`, or are recomputed from any cache present, or
   are absent. Nothing is deleted. Every networked target — `make clearance`,
   `fetch-metadata`, `fetch-text`, `check-source-links` — **exits 2**
   ("machinery not installed"), distinct from 1 = failure, and
   `run_ladder.sh` propagates that so `|| break` still works. `make audit`
   still runs every offline check; its one networked probe reports
   *inconclusive*, which is what it already did for lapsed clearance.
2. **With rivulet** (`pip install -e ../../rivulet`) — cache refreshed, sizes
   full and current.
3. **`--fulltext` serve mode** (`make serve-fulltext`) — does *not* require
   rivulet. It only toggles links to text already on disk. **Localhost only,
   never published.**

   Three things make that true, and all three are load-bearing:

   - the text lives **outside `docs/`**, under the gitignored `data/`, so no
     build step and no deploy can pick it up — GitHub Pages serves `docs/`
     alone
   - the flag **binds 127.0.0.1**, not all interfaces
   - the frontend **probes** `/text/` at startup and reads `X-Fulltext-Mode`;
     without the flag no badge renders at all. Verified: same 2038 work rows,
     1327 `txt` badges with the flag and **0** without it.

   Requests are resolved through a prebuilt `serial -> file` index, never by
   joining a path, so `/text/../../etc/passwd` finds no key and 404s. The
   server also pins its root to `docs/` rather than inheriting the caller's
   cwd — run from the repo root the old behaviour served the whole repo,
   `data/clearance.json` included.

   Sāgarasaṅgama shows the same badge in its unified search, reached
   cross-origin; `/text/` sends `Access-Control-Allow-Origin` only in fulltext
   mode and only to a localhost/private-network origin.

`tree.json` carries a `has_text` boolean per work, set from cache presence, so
Sāgarasaṅgama renders text links without reading this repo's `data/`. It is
derived from the **cache**, not from `sizes`: a work can be measured on a
machine whose text is elsewhere, and linking to that is the dead link the flag
exists to prevent. The flag is **omitted entirely** when there is no cache dir
— "could not tell" and "no text" are different claims.

### `text_sizes.jsonl` must never be deleted

It is the concentrated distillate of a 4.0 GB cache and expensive to
reproduce. `count_sizes` **refuses to overwrite a non-empty one with a run that
measured zero bytes** and exits non-zero. Note the test is measured *bytes*,
not row count: a cacheless run still emits explicit zero rows for books whose
fetch legitimately returned nothing, so a row count would not catch it.

## Sizes are derived, never fetched twice

Two stages, one per corpus, deliberately symmetrical:

    count_snapshot_sizes.py   the raw_etexts snapshot -> snapshot_text_sizes.jsonl
    count_sizes.py            our fulltext_cache      -> text_sizes.jsonl

rivulet's fetcher also measures each book as it completes it, but that is a
convenience, not the source of truth. Sizes are a pure function of the cached
text, so `make count-sizes` rebuilds them offline — which is what keeps a change
to how bytes are counted from costing 5557 refetches.

`count_sizes` measures **complete books only**. A book stopped at the chunk
ceiling has real text on disk but has not ended, and publishing its bytes would
read as a finished measurement — the failure that once recorded serial 304 as a
complete 54,498-character book when it was truncated. Use `--include-partial` to
measure them anyway; they are flagged `partial: true`.

## The atlas has two browsing axes, not a tree

`tree.json` is a **flat `works` array plus `axes` holding ids into it** — not a
nested tree, despite the filename. Category and author are independent peers,
each optionally grouped by the other, and the browser groups at render time.

This is load-bearing, not stylistic: nesting author under category scatters an
author across the tree (Kālidāsa's 110 works sit under 7 domains, and
multi-domain authors hold 32.5% of all authored works) and leaves nowhere for
the 3888 works with no author. The shape is documented in `pipeline/shape.py`.

## Before scraping anything

**Authorized — tiers 1–3, the whole acquisition plan.** Tier 2 was authorized
2026-08-11 (`pipeline/fetch_metadata.py` / `make fetch-metadata`, one
`readSearch.php` page per catalogue id) and has run to completion. **Tier 3, the
full-content pass for byte sizes, was authorized 2026-08-13**, lives in rivulet,
and completed its ladder 2026-08-28. Re-run either without asking again.

**A refresh can only diff on id membership.** EBS supplies no versioning at all
— no ETag, no modified date, no revision number — so a book whose text or
metadata was corrected upstream keeps its id and is **indistinguishable from a
stale cache entry**. Additions and removals are detectable; in-place edits are
not. The cache is therefore authoritative until we deliberately decide it is
not, and "update" means refetching blind rather than syncing. The tier-1
membership check costs ~15 requests, so run it freely; the tier-2 refetch is the
rare, expensive one. The per-entry fetch timestamp is the only staleness handle
that exists — an age, not a version.

Two rate terms, kept because **the code enforces them** — change the code and
this text together, never one alone:

- **one request per 2s minimum**, start-to-start, single-threaded.
  rivulet's fetcher hard-exits below a 1s `--delay`; responses take ~1.0s, so a
  shorter gap would overlap them.
- **back off 30/120/300s on 429/5xx and give up** rather than hammering
  (`BACKOFF` in rivulet's fetcher and in `fetch_metadata.py`).

### The site requires session clearance (2026-08-14)

`ebharatisampat.in` requires per-session clearance before it will serve
content. How that clearance is obtained lives in `rivulet` and is not
documented here.

Consequences for anything that fetches here:

- **Clearance is session-scoped**, so it is established once and reused; the
  fetchers themselves stay plain HTTP.
- **Detect an unserved response in every reply.** `strip_markup()` would
  happily render a placeholder as "text" and record a book complete at a few
  hundred bytes.
- **A lapse mid-run is routine, not a failure.** Clearance expires roughly
  hourly and the fetcher re-earns it in place and carries on. Only
  `MAX_CLEARANCE_RETRIES` **consecutive** failures to re-earn end the run, and
  that path **exits non-zero**.

## The ladder must not step over an unfinished rung

The fetcher is driven by `./run_ladder.sh`, which walks a list of chunk
ceilings and **breaks on a non-zero exit**. Climbing gets the shallow books
done early instead of spending a night on one 900-chunk mahābhāṣya, and the
journal makes each rung resumable — a book stopped at 150 restarts at 151.

That only works if the exit code distinguishes "this rung is done" from "this
rung was cut short". Until 2026-08-19 it did not, in two compounding ways:

- `MAX_CLEARANCE_RETRIES` was a budget **per run** rather than per consecutive
  failure, so the 4th lapse ended a rung even though all three re-earns had
  **succeeded**. Clearance lapses roughly hourly, so this quietly capped every
  rung at ~4 hours regardless of its queue.
- every give-up path was a bare `return`, so the process exited **0** and
  `|| break` never fired.

Four rungs ran overnight and **431 books were still parked at cursor 50**,
passed over each time. If open books sit below the current ceiling, the ladder
skipped them — check with a cursor histogram over incomplete books before
assuming a rung completed. Do not reintroduce a per-run cap on lapses.

## Phase 1 is deliberately crude

The pattern is: rough acquisition → browsable interface → complete redo. Phase 2
will throw this pipeline away, so **don't invest in hardening it.** Fix what's
wrong, don't build infrastructure around it.

**One exception, already taken:** the sequestration into `rivulet` was a
publishing decision, not a hardening one. Phase 2 inherits the boundary even
though it throws the pipeline away.
