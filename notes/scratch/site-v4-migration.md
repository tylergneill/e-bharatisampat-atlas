# Adjusting to the rebuilt site (EBS "VERSION 4.0.0")

**Status: surveyed 2026-11-06; nothing fixed yet.** The site facts are in
`../site-structure.md`. This file is the work list; delete it when every item
is done.

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
- [ ] **About page copy** depends on the old defects: the exclusion-list URL at
  `about.html:448`, the "missing from the listing" list at `:477-498`, and the
  ~24% shortfall. Those works are on `ai_books` now. Recheck before rewording;
  see CLAUDE.md on promoting note prose into UI copy.

## Broken now (pipeline)

- [ ] **`parse_metadata.py` parses `{}` from a new metadata page.** `ROW_RE`
  expects `<h5>LABEL: value</h5>`. The current cache is old-format and still
  parses, so this only bites on a refetch. If the refetch goes through the JSON
  listings (below), this parser may not need porting at all.
- [ ] **rivulet `check_source_links`**: it asserts on `<select name="type">`
  (gone; it is a hidden input now), and `check_browse_not_inverted` tests the
  old complement logic. Both need rewriting.
- [ ] **rivulet `fetch_fulltext`**: `READER_URL` (the unproofread-banner probe)
  is the dead `readbook3.php` form. `correct_ocr`, or which shelf a work is on,
  replaces the banner probe outright. `get_unicode.php` itself still works,
  byte-identical.
- [ ] **Clearance may be unnecessary now.** curl with no cookie worked on every
  endpoint on 2026-11-06. Watch whether that holds across days before removing
  anything.

## New opportunities

- [ ] **Metadata in about 150 requests instead of 11h.** The three JSON
  listings give serial, category, sub-category, author, publisher, contributor,
  language, thumbnail and pdfurl. They lack publish year, pages, printer,
  editor, commentators, translator and the reader kind (readbook3 vs
  read_chapter), so tier 2 is still needed for those — but only for the new or
  changed works.
- [ ] **147 new works and 49 works that gained text** since the August scrape;
  7 known works gained a PDF; serial 8997 is gone. This supersedes the counts in
  todo.md's "Rerun the metadata fetch" and "Supplement the full-text fetch"
  items.
- [ ] **Publish the proofread axis from `correct_ocr`** rather than the banner
  heuristic. It is per-shelf and site-sourced; the site-structure.md caution
  that the flag is batch structure, not a per-book judgement, still applies.
- [ ] **`title_eg`** (English or romanized title) is a new field. It could
  feed search.
