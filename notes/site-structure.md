# site structure

What we have learned about **ebharatisampat.in from the site itself** — its
endpoints, its identifiers, and which of its behaviours will mislead a reader
of its own pages. Add to it; prune only what is disproven.

**Corpus figures are not here.** `make audit` re-derives them and writes
them into `about.html`. Text-acquisition mechanics are not here either: they
live with the fetcher, in rivulet's `extract/ebharatisampat/fetch_fulltext.py`.

## The site was rebuilt in autumn 2026 ("VERSION 4.0.0")

Seen 2026-11-06. Routes are extensionless now (`unicodetype`, `readunicode`,
`readbook3`), though the `.php` forms of the listing, metadata and search pages
still answer 200. **Plain curl needs no clearance cookie** on any endpoint
tried that day: the headers show nginx + `PHPSESSID`, no BitNinja.

## Endpoints

| endpoint | serves |
|---|---|
| `readSearch.php?id=` / `readunicode?id=` | the metadata page — the tier-2 route |
| `readbook3?bookid=X&bookname=Y` | the flat-text reader, **whole book inline** in one page |
| `read_chapter?bookid=X` | the chaptered reader |
| `ebook_pdf.php?bookid=X` | the PDF reader, present only when a scan exists |
| `get_unicode.php` (POST `b_id`,`my_id`) | the old AJAX text endpoint — **still live**, byte-identical (serial 2503: 803,232 B, as journalled 2026-08-15) |
| `filter_books_unicode.php`, `filter_books_ai.php`, `filter_books.php` | POST, JSON: the three listings (below) |

**The pre-rebuild reader URLs are dead.** `readbook3.php?bookid=<id>&pageno=…`
and `read_chapter.php?bookid=<id>` return an empty shell that JS-redirects to
the listing; `ebook/index.php?bookid=<id>` is a 404.

**The new reader `bookid` encodes the SERIAL, not the base64 id**, and
`bookname` the Devanagari title. Each is wrapped five times: decode base64,
then four rounds of reverse-the-string-and-decode-base64. So links are
buildable from data we already hold. **`bookname` is optional**: without it
both readers serve the whole book (2503: 415,733 B against 415,753 with it,
checked 2026-11-09) and only the browser-tab title goes blank.

**`readunicode.php`, `readpdf.php` and `readSearch.php` are one endpoint.**
The first two are redundant aliases; all three return the same metadata page.
The page's `<h5>LABEL: value</h5>` rows became
`<div class="book-meta-item"><span class="label">…</span><span class="value">…</span>`;
the title moved to `<h1 class="book-title">`, and TEXT/PDF are now the
`book-actions` buttons. The field set is unchanged.

The download buttons are **login-gated** (`login.php`) on both readers:
`readbook3` offers PDF / Word / Text, `read_chapter` Text only (its PDF and
Word links are commented out). Metadata-page buttons read "Read Unicode",
"Read Chapter" (singular now) and "Read E-Book". Checked 2026-11-09.

**One `readbook3` GET now holds the whole book**, where `get_unicode.php`
needs one request per chunk. Checked 2026-11-09 against the cache by
Devanagari word multiset, after rivulet's `strip_markup` (which lifts the
`title=` glosses -- skip that and a sacūrṇika book looks ~1% short): 1618
(1 chunk), 2503 (1) and 640 (318) are **identical**; 6779 (1864 chunks, the
deepest; 9.3 MB, 3.1 s) has 651 words more than the cache and 1 fewer; 304
(51) has ~900 fewer, nearly all repeats the chunk walk wrote twice. The page's
own scripts only call highlights / reading-history APIs; nothing loads text
on scroll. The journal records 412,045 requests for the whole tier-3 walk; one
GET per book would be ~5,600.

**The TOC is the one difference left between the readers**: `read_chapter`'s
"Note Book" sidebar (hidden by default) has a "Title" tab listing chapters;
`readbook3`'s has only Notes / Highlights.

**The reader endpoint is a TOC flag, not a content class.** `read_chapter`
means the book has a navigable chapter list, `readbook3` a single flat text.
Median body sizes are within 1.5% of each other, so **entries in both groups
are whole works** — the name invites the opposite reading. The flag is on the
metadata page's button href, so tier 2 captures it without a reader fetch.

**Reading is anonymous.** Only the site's own Download buttons are login-gated. Every route the pipeline uses works logged out.

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
- **`SERIAL NO.` is 1:1 with `id`** and spans all the shelves. Before the
  rebuild it appeared only on book pages; **the JSON listings now carry it as
  `id`** (checked: 11242 ↔ `NDIxODAzNzU3OTgxOTcwMQ==`). The listings do not
  carry the base64 id, except inside their HTML fragments' `readunicode?id=`
  hrefs.

The snapshot's `book_id_encoded` is exactly the listing's opaque `id`, which is
what lets the snapshot be joined to the live catalogue.

## Three shelves, not one

Since the rebuild: `unicodetype` (proofread text), `ai_books` ("AI-converted
books", unproofread text) and `pdf` (scans). Each pages through a POST JSON
endpoint (`limit`, `offset`, `sort`, and `cat[]`-style facets), **capped at 100
records per request**. The whole site takes about 150 requests at roughly 6 s
each. Each record carries the **serial** (as `id`), `thumbimg`, `pdfurl`,
category, sub-category, author, publisher, contributor, language, an English
`title_eg`, and on the text shelves `correct_ocr`.

Full dump 2026-11-06:

| shelf | works | `correct_ocr` |
|---|---|---|
| unicode | 4242 | all `1` |
| ai | 1364 | all `0` |
| pdf | 9574 | absent |

- unicode ∩ ai = 0; union 5606. **Every one of our 5557 text works is on one
  of the two text shelves**; 49 shelf works have text we lack.
- AI shelf ≈ our journalled `unproofread=True` (1314 of 1316).
- Union of all three = 11212: our 11066 minus 1 (serial 8997, gone) plus 147
  new since the August scrape. 7 known works gained a PDF.

The PDF and text shelves overlap heavily — a work can be on both. None of
them is the catalogue: the union is.

**Language is free text**, not a controlled field, and most of the catalogue is
Sanskrit — but the exact share is a live figure on the About page, not a
constant to quote from here.

## The listings are unreliable — and this is why the atlas exists

The site cannot give a consistent account of its own holdings. Four independent
defects, all verified:

**1. The Unicode listing hides books that have text — explained by the
rebuild.** Well over a thousand works had a Unicode reader but were not on
`unicodetype.php`. They were the unproofread ones, now shelved separately as
`ai_books` (see "Three shelves"). "Has text" is still the union of two
shelves, never the Unicode one alone.

**2. The same URL returns different totals minutes apart.** Readings of 4061,
4192 and 4212 came from one clearance session on the same day. Within a single
session the number is stable; across sessions it is not. Probed for eight days
and abandoned unexplained — the mechanism was not worth further chase, and the
probe apparatus was deleted 2026-08-28. Membership does genuinely churn a
little (single-digit adds and removals over days), but that is a different and
much smaller phenomenon than a 151-swing in minutes. **Any site-sourced total
needs a date attached.**

**3. Facets were EXCLUSION lists — fixed by the rebuild.** Before it, the filter
parameters named values to leave *out*. Now they are **inclusion** lists
(2026-11-06): `cat[]=वेदः` gives 46; `sub_cat[]=आयुर्वेदः` gives 107, matching
its facet count, where the old complement trick gave 32; `author[]=कालिदासः`
gives 48; `cat[]=All` is harmless. The page keeps its state in
`?q=<urlsafe-base64(JSON {cat:[…], sort})>`. Legacy `?cat=a,b` and `?cat[]=a`
are still parsed, but as **inclusion**, so any complement URL built for the old
bug now shows the opposite of its intent. The JS skips updating the URL once
it passes 1800 characters.

`search.php` still honours `type` (कालिदासः: author 125, book 2) and links to
`readSearch?id=`. Its `<select name="type">` is gone, replaced by a hidden
`<input name="type">`.

**4. The PDF listing overshoots slightly** — it lists a handful of works whose
scan does not resolve. Discovered by accident through a *text* discrepancy;
nothing we run would otherwise have caught it, and the PDFs themselves have
never been fetched. So "has a PDF" means the metadata page shows a link,
nothing more.

## The proofread axis is real but not a census

Since the rebuild the site states it outright: unproofread texts are shelved
as "AI-converted books" (`correct_ocr` 0 in the shelf JSON), proofread ones as
"Unicode Books" (`correct_ocr` 1). Before that it showed only as a banner in
the `readbook3` reader HTML ("This text is machine converted"), invisible to
the listings and the metadata. rivulet's `fetch_fulltext` still probes that
banner and journals it as `unproofread`; the two agree on 1,314 of 1,316
books (checked 2026-11-06).

Two cautions, unchanged by the rebuild:

- **Do not report the corpus-wide ratio on its own.** It is **batch structure,
  not per-book judgement**: the flag tracks when a book was ingested, not how
  carefully it was read.
- **"Proofread" is not evidence of finished proofreading.** The site runs a
  two-stage *Proofread → Review* workflow tracked to a page offset inside each
  book, and leaks per-book progress notes into the served text. Every such
  note found so far sat on a book journalled `unproofread=False` while stating
  it was incomplete. Neither `False` nor a place on "Unicode Books" means more
  than "not flagged as machine-converted".

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

Since the rebuild its statistics block matches the listings (9,574 e-books,
4,242 Unicode, 2026-11-06). Its prose still claims "6,800 books" and "4,500+
searchable texts", and elsewhere "4,598 digitized texts" — still a third set of
numbers.

## Open

- **Are `read_chapter` divisions extractable?** The TOC flag is free from tier
  2; whether the divisions *within* a book can be pulled out is untested.
- **Serial uniqueness is snapshot-derived** and possibly circular — if the
  upstream scraper deduplicated on serial, our check would look exactly like
  this. Test against overlap works the snapshot never captured.
- **Is `readunicodetype.php?id=` an alias for `readunicode.php`?** Assumed, not
  verified.
