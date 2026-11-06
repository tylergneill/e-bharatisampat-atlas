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

- [ ] **Text and PDF links in `docs/app.js` are dead.** `textUrl` and `pdfUrl`
  build `readbook3.php?bookid=<id>&pageno=…`, `read_chapter.php?bookid=<id>` and
  `ebook/index.php?bookid=<id>`. The new forms take the *encoded serial* (and
  `bookname` = encoded title for readbook3); the encoding is in
  site-structure.md. Test whether `bookname` can be omitted before shipping it.
  `metadataUrl` (`readSearch.php?id=`) still works. The same goes for
  `pipeline/parse_metadata.py::reader_url`.
- [ ] **The same dead links are in Sāgarasaṅgama** — `sagara-sangama/docs/search.js:204-215`.
- [ ] **The category "browse" link is inverted.** `listingComplementUrl` names
  the other 32 categories; facets are now inclusion lists, so the link shows
  everything *except* the chosen category. Build
  `unicodetype?q=<b64 {"cat":[x]}>` instead. **Unicode shelf only**: the AI
  shelf (`ai_books?q=…`) holds the other ~24% of texts, so either give two links
  or say so in the tooltip.
- [ ] **Sub-category and author browse links are now possible.** The long
  comment block explaining why they are withheld (the sub_cat complement
  failing, the 451 KB author URL) is obsolete. Rewrite or delete it.

## About page, next in order

- [ ] **"Hidden Searchable Texts" → about "AI-converted books".** The 1,364
  works the old Unicode listing omitted are now their own shelf. Rewrite the
  section, and with it `audit.py`'s `find_hidden_books` /
  `load_listing_capture`, which still count only `collection == "unicode"` as
  the text listing and so report every AI-converted book as missing.
- [ ] **Other copy relying on the old defects**: the exclusion-list URL near
  `about.html:448` and the ~24% shortfall. Recheck before rewording; see
  CLAUDE.md on promoting note prose into UI copy.

## Before the next full (online) audit run

`make audit-update-about` without `--offline-skip-gap` rewrites the
"Opportunities for Correction" region. Do not run it until these are fixed:

- [ ] The hidden-books fix above, or it republishes 1,364 works as omitted.
- [ ] **The online walk itself** (~33 requests) reads totals from the old
  `.php` listing pages. They still answer, but check them against the rebuilt
  site.
- [ ] **The "overcounted by E-Books" bullet**: its "of 9428 listed" is the
  August total (now 9,574), and its link `pdf.php?cat=All` may show nothing now
  that facets are inclusion lists. The 7 works it names (2715, 2972, 3170, 3613,
  3819, 3856, 4059) are still shelved as E-Books with no PDF on their page.

## Pipeline

- [ ] **`__content_version__`** (`build_tree.stamp_version`) reads only the
  fulltext journal, so it still says 2026-09-09 though metadata was fetched
  2026-11-06. It is also published as `all_stats.sourced` ("data last
  sourced"). Take the newer of the two journals.
- [ ] **rivulet `check_source_links`**: it asserts on `<select name="type">`
  (gone; it is a hidden input now), and `check_browse_not_inverted` tests the
  old complement logic. Both need rewriting.
- [ ] **rivulet `fetch_fulltext`**: `READER_URL` (the unproofread-banner probe)
  is the dead `readbook3.php` form. `correct_ocr`, or which shelf a work is on,
  replaces the banner probe outright. `get_unicode.php` itself still works,
  byte-identical. The 49 works that gained text, plus the 147 new ones, have
  no byte sizes until this runs.

## New opportunities

- [ ] **Publish the proofread axis from `correct_ocr`** rather than the banner
  heuristic. It is per-shelf and site-sourced; the site-structure.md caution
  that the flag is batch structure, not a per-book judgement, still applies.
- [ ] **`title_eg`** (English or romanized title) is a new field. It could
  feed search.
- [ ] **Sub-category and author links** (above) are the big one: facets as
  inclusion lists make every axis of the Atlas linkable on the site.
