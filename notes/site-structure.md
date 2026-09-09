# site structure

What we have learned about **ebharatisampat.in from the site itself** — its
endpoints, its identifiers, and which of its behaviours will mislead a reader
of its own pages. Add to it; prune only what is disproven.

**Corpus figures are not here.** `make audit` measures them live and writes
them into `about.html`. Text-acquisition mechanics are not here either: they
live with the fetcher, in rivulet's `extract/ebharatisampat/fetch_fulltext.py`.

## Endpoints

A book has four views, and the id space is shared across all of them.

| endpoint | serves |
|---|---|
| `readSearch.php?id=` | the metadata page — the tier-2 route |
| `readbook3.php?bookid=` | the flat-text reader (4891 works) |
| `read_chapter.php?bookid=` | the chaptered reader (666 works) |
| `ebook/index.php?bookid=` | the PDF reader, present only when a scan exists |
| `get_unicode.php` (POST `b_id`,`my_id`) | the AJAX text endpoint; mechanics in rivulet |

**`readunicode.php`, `readpdf.php` and `readSearch.php` are one endpoint.**
The first two are redundant aliases; all three return the same metadata page.

**The reader endpoint is a TOC flag, not a content class.** `read_chapter`
means the book has a navigable chapter list, `readbook3` a single flat text.
Median body sizes are within 1.5% of each other, so **entries in both groups
are whole works** — the name invites the opposite reading. The flag is on the
metadata page's button href, so tier 2 captures it without a reader fetch.

**Reading is anonymous.** Only the site's own Download buttons are login-gated,
and only on `readbook3`. Every route the pipeline uses works logged out.

## Identifiers

| id | in listings? | unique? | ties collections? |
|---|---|---|---|
| `sno` | yes | **no** | **no** |
| base64 `id` | yes | yes | **yes** |
| `SERIAL NO.` | **no** | yes | yes |

- **`sno` is a per-page row counter**, 1–1000, recycled every page. It carries
  no identity — never key on it.
- **base64 `id` is the catalogue-wide key.** 11066 distinct ids across 13620
  rows; the ~2554 duplicates *are* the unicode/pdf overlap — the same work as
  text and as scan.
- **`SERIAL NO.` is 1:1 with `id`** and spans both collections, but appears
  **only on book pages**, so it costs one fetch per book. `readSearch.php` with
  a BookId query does the serial → id lookup.

The snapshot's `book_id_encoded` is exactly the listing's opaque `id`, which is
what lets the snapshot be joined to the live catalogue.

## Two collections, not one

`unicodetype.php` (text) and `pdf.php` (scans) are separate shelves, and they
**overlap heavily** — a work can be on both. Neither is the catalogue: the
union is. Both paginate at `limit=1000&page=N` and are cheaply exhaustible in
about 15 requests.

**Language is free text**, not a controlled field, and most of the catalogue is
Sanskrit — but the exact share is a live figure on the About page, not a
constant to quote from here.

## The listings are unreliable — and this is why the atlas exists

The site cannot give a consistent account of its own holdings. Four independent
defects, all verified:

**1. The Unicode listing hides books that have text.** Well over a thousand
works have a Unicode reader but do not appear on `unicodetype.php`. The
listing is a *shelf*, not an index of what has text — so never derive
"how many works have text" from it. Our own metadata says 5557; the listing
says far fewer.

**2. The same URL returns different totals minutes apart.** Readings of 4061,
4192 and 4212 came from one clearance session on the same day. Within a single
session the number is stable; across sessions it is not. Probed for eight days
and abandoned unexplained — the mechanism was not worth further chase, and the
probe apparatus was deleted 2026-08-28. Membership does genuinely churn a
little (single-digit adds and removals over days), but that is a different and
much smaller phenomenon than a 151-swing in minutes. **Any site-sourced total
needs a date attached.**

**3. Every facet parameter is an EXCLUSION list.** The filter parameters name
the values to leave **out**, not the ones to show — a one-word bug repeated in
all six of the site's facet handlers, where a variable named for *checked*
boxes is filled with the unchecked ones. The arithmetic confirms it exactly: a
category's complement plus that category equals the collection total.

Three consequences for anyone building a URL:

- **Never pass `All` in a facet parameter** — it excludes everything.
- **Unknown values are ignored in `cat` but not in `sub_cat`**, so the two do
  not behave alike; the `cat` complement works and the `sub_cat` complement
  does not.
- Prefer `search.php`, which is the sound interface. Where the listings hide
  books, search does not, and its `<select name="type">` names the accepted
  values (`book`, `author`, `pub`, …) in the markup.

**4. The PDF listing overshoots slightly** — it lists a handful of works whose
scan does not resolve. Discovered by accident through a *text* discrepancy;
nothing we run would otherwise have caught it, and the PDFs themselves have
never been fetched. So "has a PDF" means the metadata page shows a link,
nothing more.

## The proofread axis is real but not a census

The site labels its whole Unicode collection "Proofread Books", while a
substantial minority of complete `readbook3` books carry an **unproofread
banner in the reader HTML** — invisible to both the listings and the metadata,
which is where an earlier check looked and found nothing.

Two cautions:

- **Do not report the corpus-wide ratio on its own.** It is **batch structure,
  not per-book judgement**: the flag tracks when a book was ingested, not how
  carefully it was read.
- **`unproofread=False` is not evidence of proofreading.** The site runs a
  two-stage *Proofread → Review* workflow tracked to a page offset inside each
  book, and leaks per-book progress notes into the served text. Every such note
  found so far sat on a book journalled `False` while stating it was
  incomplete. `False` means only "the banner sentence did not appear".

## Thumbnail filenames are the only "when was this added" signal

The site publishes no upload date. The thumbnail filename embeds a Unix
timestamp, and `pipeline/upload_dates.py` reads it — an inferred convention, not
a documented field, and **it already changed once mid-2023 without
announcement**. Re-verify on each pull. Serial order corroborates it
(ρ≈0.972); see `serial-bands.md`.

## Filing is inconsistent, and it is the site's inconsistency

- **Authorship and categorization are independent axes** — a work's category
  says nothing about who wrote it, and the two must not be rolled into one
  hierarchy.
- **Filing conflates author with commentator** in places, so an author node can
  collect works someone else wrote.
- **Superseded empty duplicates exist** — a serial can point at a record the
  site has since replaced, leaving the old one served but empty.

## The home page advertises a third set of totals

The front page claims more PDFs and more searchable works than either its own
listings or our metadata. It is a third number, agreeing with neither.
Usefully, its text count exceeding its own Unicode listing corroborates defect
§1 from the site's own side.

## Open

- **Are `read_chapter` divisions extractable?** The TOC flag is free from tier
  2; whether the divisions *within* a book can be pulled out is untested.
- **Serial uniqueness is snapshot-derived** and possibly circular — if the
  upstream scraper deduplicated on serial, our check would look exactly like
  this. Test against overlap works the snapshot never captured.
- **Is `readunicodetype.php?id=` an alias for `readunicode.php`?** Assumed, not
  verified.
