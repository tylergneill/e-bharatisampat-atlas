# Adjusting to the rebuilt site (EBS "VERSION 4.0.0")

**Status: 2026-11-06, pipeline refreshed, front end not yet.** The site facts
are in `../site-structure.md`. This file is the work list; delete it when every
item is done. The live site carries an under-construction banner (PR #4);
`adjust-for-new-site` removes it, so merge that branch only once the
user-visible items below are fixed.

## Done 2026-11-06

- [x] `make walk-shelves` (rivulet `walk_shelves`) and a new `parse_listings`
  that reads the JSON walk: 153 requests, ~5.5 min.
- [x] `fetch_metadata` reads the new page layout, reshaping it into the old
  `<h5>` rows, so `parse_metadata` was not ported. It also needed a stale
  clearance call fixing and `ebook_pdf` matched without `.php`.
- [x] Fetched the 147 new works, and refetched the 49 that gained text and the
  7 that gained a PDF (203 requests). `parse_metadata` now drops works on no
  shelf (serial 8997).
- [x] About "Scraping Metadata" and "Two Overlapping Collections" rewritten;
  `make build` and an offline audit refreshed every intro figure.

## Broken now (user-visible)

- [x] **Text and PDF links rebuilt** in `docs/app.js` (`readerId`) and
  Sāgarasaṅgama's `docs/search.js` (`ebReaderId`, from a new `s` serial field
  in its index), as `readbook3?bookid=`, `read_chapter?bookid=` and
  `ebook_pdf?bookid=` with the encoded serial and no `bookname`.
  `pipeline/parse_metadata.py::reader_url` still builds the old forms; it is
  unused, cited only in comments.
- [x] **Browse links rebuilt as inclusion filters** (`browseLinks` in
  `docs/app.js`): categories, sub-categories and authors each get one link per
  shelf that holds their works ("browse txt" / "browse AI" / "browse PDF"),
  with `search txt+pdf` last for categories and authors. Checked against the
  live site 2026-11-09 (āyurveda 107 / 80 / 314, कालिदासः 48 / 6 / 106-107).

## About page, next in order

- [x] **"Hidden Searchable Texts" replaced by "AI-converted Books"** (moved up
  under "Two Overlapping Collections"), and the audit's hidden-books finding
  retired with it. That finding was the audit's only live request, so the
  audit is now entirely offline: no clearance, no `--offline-skip-gap`.
- [x] **About copy for browsing** ("Search vs. Browse", "Emphasis on
  Searchable Text", "Browsing by Categories and Authors") rewritten for the
  three shelves and inclusion filters; the āyurveda 107-vs-32 example and its
  audit stats are gone.
- [x] **"Structured vs. Unstructured Texts"** rewritten for the new readers
  (whole text on one page, both downloads login-gated, "Read Chapter"), and
  "Multiple Editions of One Work" moved up after "AI-converted Books", its
  counts refreshed (32 / 28). "Calculating Size Information" still cites deep
  pagination as why the scrape took weeks: true of the walk we ran, but not of
  a refetch now.
- [x] **The "overcounted by E-Books" bullet's link** (`audit.PDF_BROWSE_URL`)
  now points at the unfiltered `/pdf` shelf instead of `pdf.php?cat=All`. Its 7 works (2715, 2972, 3170, 3613, 3819, 3856, 4059) are still
  shelved as E-Books with no PDF on their page.

## Pipeline

- [ ] **`__content_version__`** (`build_tree.stamp_version`) reads only the
  fulltext journal, so it still says 2026-09-09 though metadata was fetched
  2026-11-06. It is also published as `all_stats.sourced` ("data last
  sourced"). Take the newer of the two journals.
- [ ] **rivulet `check_source_links`**: it asserts on `<select name="type">`
  (gone; it is a hidden input now), and `check_browse_not_inverted` tests the
  old complement logic. Both need rewriting.
- [ ] **rivulet `fetch_fulltext`**: **the route itself can change.** One
  `readbook3` GET holds the whole book (site-structure.md), so a full refetch
  would be ~5,600 requests (~3h at 2s) instead of the 412,045 the chunk walk
  cost, with no dead-run termination heuristics and no repeated chunks. Also: `READER_URL` (the unproofread-banner probe)
  is the dead `readbook3.php` form. `correct_ocr`, or which shelf a work is on,
  replaces the banner probe outright. `get_unicode.php` itself still works,
  byte-identical. The 49 works that gained text, plus the 147 new ones, have
  no byte sizes until this runs.

## New opportunities

- [x] **Publish the proofread axis from the shelves** rather than the banner
  heuristic: `parse_metadata` joins `ai_converted` from the "AI-converted
  books" shelf, shown as an "AI" badge in the Atlas and "AI-converted" in
  Sāgarasaṅgama's search. The site-structure.md caution that the flag is
  batch structure, not a per-book judgement, still applies. (Not yet a
  browsing filter or a total.)
- [ ] **`title_eg`** (English or romanized title) is a new field. It could
  feed search.
- [x] **Sub-category and author links**: done with the browse-link rebuild.
