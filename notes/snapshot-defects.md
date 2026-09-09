# What's wrong with the upstream snapshot

All figures re-verified 2026-08-10 (18:30, after pulling upstream `0977e07c2`)
against `raw_etexts/mixed/ebhAratI-sampat/` (2287 book files, 1364 `_index.md`,
1 `urls.md`). Reproduce with `make parse` (prints the cross-checks) or
`python -m pipeline.parse_snapshot --report`.

Everything below holds against that pull **except §2, which the pull changed** —
the empty-book set is not stable upstream. Structural counts (§1, §3–§6) were
unaffected.

This is the evidence base for redoing acquisition rather than cleaning up what's
here.

## 1. 44% of the catalogue was never materialized

`urls.md` is a **flat list of 4067 bare URLs** — no titles, no paths, no
hierarchy — using endpoint `readunicode.php?id=`. Content files instead record
`readbook3.php?bookid=` (1952) or `read_chapter.php?bookid=` (335). The base64
payloads decode into the same numeric id space.

- **All 2287 on-disk bookids appear in `urls.md`.**
- **1780 `urls.md` ids have no file on disk.**

So `urls.md` looks like the input list to the author's external script, and the
tree its output — with 44% silently dropped. `urls.md` therefore does *not*
describe the directory's structure, but it is a usable inventory of what
*should* exist.

**One member was examined end to end** (serial 1618, the
Siddhasiddhāntasaṅgraha): it is absent from the snapshot, its id is in
`urls.md`, and the live site serves the full text. So the gap is upstream
script failure, not missing content — the sample text is kept in
`samples/1618_siddhasiddhantasangraha.txt`.

## 3. Two code paths, one with mangled titles

All **335** `read_chapter.php` books carry titles of the form
`Download Text\n\t\t\t\t<actual title>` (escapes literal in the TOML). All 1952
`readbook3.php` ones are clean. The scraper grabbed a button label along with
the title on one path only. `parse_snapshot.clean_title` strips it.

## 4. Filing conflates author with commentator

86 books have **no `author` field** yet sit in an author-named directory
upstream; **71 of those have a `primary commentator`** instead. The upstream
script evidently filed by commentator when author was absent — two distinct
roles collapsed into one directory level.

This repo builds hierarchy from **frontmatter, not paths**, so those 86 land
directly under their sub-domain, which is what the metadata actually says.

**The "file by commentator instead" idea does not scale — settled 2026-08-12.**
It rescues 71 of 86 here, but corpus-wide (11066 works) only **16.7%** of the
3888 authorless works have a `primary commentator`, and **57.4% have neither
commentator nor editor**. No metadata field fills the gap. The atlas's answer
is instead structural: author is an independent axis rather than a level
beneath category, and authorless works are a real `unknown` bucket on it. See
`site-structure.md`.

## 5. One garbled category label

`charitAni_-_biography/_index.md` has title `चरितानि - बिओग्रफ्य्` — "Biography"
transliterated into Devanagari as if it were Sanskrit. The frontmatter `domain`
value (`चरितानि - Biography`) is correct, which is why the builder uses
frontmatter rather than `_index.md` titles.

## 6. OCR junk — minor, not systematic

`?R?0?1`-style control markers appear in **exactly 1 file of 2287**, and never
in live responses from the site. Stripped defensively in
`count_snapshot_sizes.clean_body`.
Not a pipeline-shaping concern.

## What is actually reliable

The per-book frontmatter. Every book carries `title`, `domain`, `sub-domain`,
`language`, `serial no.` and `source_url` with **zero exceptions**; the
bibliographic fields (author, publisher, editor, commentators, …) are optional
and often absent.

**Titles are not unique** — 1885 distinct across 2287 books, and 652 books share
a title with at least one other. Key nodes on the book id, never the title.
