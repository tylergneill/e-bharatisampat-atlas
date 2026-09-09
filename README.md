# e-bharatisampat-atlas

A browsable atlas over the **E-bhāratīsampat** corpus
([ebharatisampat.in](https://ebharatisampat.in)); one of the
[`Sāgarasaṅgama`](https://github.com/tylergneill/sagara-sangama) Atlases.

Indexes metadata and structure; hosts no text of its own. Every book links back
to ebharatisampat.in for the content itself.

Served at https://tylergneill.github.io/e-bharatisampat-atlas.

Its [about page](https://tylergneill.github.io/e-bharatisampat-atlas/about.html)
is the user-facing documentation — what the corpus is, how categories and
authors relate, and where the data is uneven. `CLAUDE.md` has the architecture
and data shape, and `notes/` the working backlog and the evidence behind it.
The rest of this file covers only how to build it.

# how it works

A `pipeline/` emits `docs/data/tree.json`; a single-page frontend in `docs/`
browses it. The catalogue is fetched one metadata page per work into a
gitignored cache of raw responses, so re-deriving a field never needs the
network twice.

`build` emits a flat work list plus each axis's keys, not a nested tree:
category and author are independent (many works carry no author at all), so the
browser does the grouping rather than the builder materializing four copies of
the corpus. See `pipeline/shape.py`.

## acquisition (not in this repo)

Everything that crosses the network lives in `rivulet`, a private package that
is not public and not obtainable. **A checkout without it cannot acquire
anything, and that is deliberate** — there is no meaningful way to obtain this
corpus without the acquisition code. These targets exit 2 ("machinery not
installed") with an explanation rather than half-running:

- `make clearance` — one-time setup the other networked targets depend on.
- `make fetch-metadata` — one metadata page per catalogue id → raw HTML in
  `data/metadata_cache/`. ~11k requests, so ~6h at one per 2s. Ctrl-C stops
  cleanly and a rerun resumes; nothing is fetched twice.
- `make fetch-text` — one reader fetch per text-bearing work →
  `data/fulltext_cache/` plus byte counts. Costs one request *per chunk*, so
  budget by requests rather than books (`MAX_REQUESTS=`, `MAX_CHUNKS=`). The
  cached text is a local working artifact and **never ships to `docs/`**.
- `make check-source-links` — asks whether the category and author links the
  frontend builds still point at what we claim. ~15 requests.

## building and serving

If `data/` is already populated, the rest of the pipeline runs offline and the
atlas builds normally:

- `make catalogue LISTINGS=<dir>` — saved listing HTML →
  `data/catalogue.jsonl`, the site's own catalogue of every distinct work. Does
  no fetching; point it at pages saved by hand.
- `make parse-metadata` — the raw cache → `docs/data/metadata.json`, one object
  per work. Safe against a partial fetch, and prints field coverage, which is
  the tripwire for the site changing its markup.
- `make count-sizes` — the fulltext cache → `data/text_sizes.jsonl`, in
  raw/content/IAST bytes. The fetcher already measures each book as it
  finishes; this rebuilds without refetching.
- `make build` — `metadata.json` → `docs/data/tree.json`
- `make changelog` — each work's addition date, decoded from the thumbnail
  filename's epoch → `docs/data/changelog.json`, bucketed by month. Needs
  `parse-metadata` to have run, since that is where the interpolation happens.
- `make serve` — serve `docs/` on :8002 (`serve-fulltext` adds the local text
  at `/text/<serial>`, localhost only)
- `make audit` / `make audit-update-about` — re-derives the figures published on
  the about page and rewrites only its own marked region. Part of it walks the
  live site; pass `ARGS=--offline-skip-gap` for our side only.

Figures are measured from the current build and move when the catalogue does;
re-derive them rather than quoting them.

# parallel snapshot track

A second, parallel track builds from a third-party snapshot of the corpus (the
`ebhAratI-sampat` directory of the `sanskrit/raw_etexts` repo — not ours, not
committed here, never written to), via `make parse`, `count-snapshot-sizes`,
`snapshot-tree` and `serve-snapshot`. It once carried the byte sizes our own
scrape lacked; it no longer does, so it survives only as a cross-check and is
deletable. It covers a fifth of the catalogue and has known defects, documented
in `notes/snapshot-defects.md`. Both tracks emit the same shape, and which one
the frontend gets is a serve-time flag, not a build-time one.

# license

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.en),
matching `Sāgarasaṅgama`. Applies to this atlas's own code and derived metadata;
the texts themselves belong to ebharatisampat.in and its contributors.
