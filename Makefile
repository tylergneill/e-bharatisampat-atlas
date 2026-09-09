.PHONY: serve-fulltext parse count-snapshot-sizes \
        clearance catalogue fetch-metadata parse-metadata fetch-text count-sizes \
        check-source-links audit audit-update-about dump-analysis \
        build snapshot-tree changelog serve serve-snapshot \
        free-server-port get-server-ip-address

# ============================================================================
# GROUP 1 -- from the third-party snapshot.  TEMPORARY; deleted at phase 2.
# ============================================================================
# These read `raw_etexts/mixed/ebhAratI-sampat`, a separate checkout that is not
# ours and is never written to. It covers ~21% of the catalogue and has known
# defects. Everything here goes away once group 2 supplies the same fields
# independently -- see notes/todo.md.

# Snapshot -> data/snapshot_inventory.jsonl (one record per book, no network).
# Override the snapshot location with EBS_SNAPSHOT=/path or SNAPSHOT=/path.
parse:
	python -m pipeline.parse_snapshot $(if $(SNAPSHOT),--snapshot $(SNAPSHOT)) --report

# Snapshot bodies -> data/snapshot_text_sizes.jsonl, in raw/content/IAST bytes.
# Reads ~1.6G of source text; ~1.5 min on 8 cores. Sizes are a pure function of
# the snapshot, so this only needs rerunning when the snapshot changes.
# Override worker count with e.g. `make count-snapshot-sizes WORKERS=4`.
count-snapshot-sizes:
	python -m pipeline.count_snapshot_sizes $(if $(SNAPSHOT),--snapshot $(SNAPSHOT)) $(if $(WORKERS),--workers $(WORKERS))

# ============================================================================
# GROUP 2 -- from the live site.  The phase-2 pipeline.
# ============================================================================
# Acquisition is ours here: the catalogue listings, then one metadata page per
# distinct work. Fetched bytes land in a gitignored cache holding RAW responses,
# so re-deriving a field never needs the network twice.
#
#   catalogue --------> data/catalogue.jsonl      11066 distinct works
#   fetch-metadata ---> data/metadata_cache/*.html   raw, one file per work
#   parse-metadata ---> docs/data/metadata.json   serial, sub-cat, language, ...
#
# Fetching here was an explicit decision, not an assumption; keep the rate
# polite.

# Saved listing HTML -> data/catalogue.jsonl, the site's own catalogue of all
# 11066 distinct works against the snapshot's 2287. Does NO fetching: point
# LISTINGS at a directory of pages saved by hand (URLs in the module docstring).
#   make catalogue LISTINGS=/path/to/saved/html
catalogue:
	python -m pipeline.parse_listings --listings $(LISTINGS)

# Establish session credentials for the networked targets -> data/clearance.json.
#
# *** RUN THIS BEFORE ANY NETWORKED TARGET. *** Implementation lives in the
# private `rivulet` package; without it this exits 2. Session-lived: when a
# fetcher reports it has lapsed, rerun this.
#   make clearance                  # establish and save
#   make clearance ARGS="--check"   # is the saved session still live?
#   make clearance ARGS="--reset-profile"
clearance:
	python -m pipeline.clearance $(ARGS)

# One readSearch.php page per catalogue id -> data/metadata_cache/, filed as
# `<serial> - <title in HK>.html` e.g. `6385 - manusmRtiH.html`.
# *** THIS HITS THE NETWORK, and needs `make clearance` first. *** ~11066
# requests at one per 2s, so ~6.5h. Ctrl-C whenever: it stops cleanly (exit 0,
# not an error), the cache is durable, and a rerun resumes where it stopped with
# the progress bar picking up at the cached count.
#   make fetch-metadata                     # everything not yet cached
#   make fetch-metadata ARGS="--limit 50"   # a bounded taste
#   make fetch-metadata ARGS="--delay 5"    # gentler still
fetch-metadata:
	python -m pipeline.fetch_metadata $(ARGS)

# The cache's raw HTML -> docs/data/metadata.json: a JSON array, one object
# per distinct work. Reads only the local cache, so it costs no requests and is
# safe to run against a partial fetch -- rerun it freely whenever the
# extraction changes.
#
# Output lands in docs/, tracked and published, because the frontend reads it;
# the cache it reads stays gitignored under data/. Everything derivable from an
# id is dropped rather than shipped -- see the module docstring. Prints field
# coverage, which is the tripwire for the site changing its markup.
#   make parse-metadata
parse-metadata:
	python -m pipeline.parse_metadata $(ARGS)

# One reader fetch per text-bearing work -> data/fulltext_cache/ (the text) and
# data/text_sizes.jsonl (three byte counts per serial).
#
# *** THIS HITS THE NETWORK, and needs `make clearance` first. ***
# A readbook3 book costs one request PER CHUNK,
# so budget by REQUESTS, not books. Nothing is ever fetched twice: a book
# stopped partway resumes at its next chunk, so CHUNKS=n is a checkpoint, not a
# cap on what you can eventually get.
#
#   make fetch-text MAX_REQUESTS=0                      # plan only, fetches nothing
#   make fetch-text MAX_REQUESTS=500                    # a bounded run
#   make fetch-text MAX_REQUESTS=2000 MAX_CHUNKS=20     # the ~83% cheaply
#   make fetch-text MAX_CHUNKS=100                      # continue the tail
#   make fetch-text                                     # everything, no ceiling
#   make fetch-text MAX_REQUESTS=50 DELAY=3 ARGS="--reader read_chapter"
#
# Ctrl-C stops cleanly (exit 0) and a rerun resumes.
fetch-text:
	python -m pipeline.fulltext \
	  $(if $(MAX_REQUESTS),--max-requests $(MAX_REQUESTS)) \
	  $(if $(MAX_CHUNKS),--max-chunks $(MAX_CHUNKS)) \
	  $(if $(DELAY),--delay $(DELAY)) \
	  $(ARGS)

# The fulltext cache -> data/text_sizes.jsonl. No network, no snapshot.
# The site-derived twin of `count-snapshot-sizes`. The fetcher already measures
# each book as it finishes, but sizes are a pure function of the cached text, so
# this rebuilds them without refetching -- which is what makes text_sizes.jsonl
# cheap to recompute and unnecessary to carry between machines.
#   make count-sizes
count-sizes:
	python -m pipeline.count_sizes $(ARGS)

# Are the category/author links in docs/app.js still pointing at what we claim?
# Those URLs are built from our own strings, so a change upstream does not error
# -- it quietly changes what the reader is shown. This asks the site.
#
# Four checks: `type=` is still honored (a stopped-being-honored `type` turns
# every category link into a title search, silently), values still match,
# search still states a total, and the browse complement has not inverted.
#
# *** HITS THE NETWORK, and needs `make clearance` first. *** ~14 requests at
# one per 2s. Exit 0 fine, 1 drifted, 2 inconclusive (no clearance / the browser
# check came back) -- 2 is deliberately not a failure, since being unable to ask
# says nothing about the links. Background in notes/site-structure.md.
#   make check-source-links
#   make check-source-links ARGS="--categories 33 --authors 20"
check-source-links:
	python -m pipeline.check_source_links $(ARGS)

# What the source collection gets wrong, published to the About page.
#
# Never mutates anything: it reads, reports, and rewrites only its own region of
# docs/about.html between the AUDIT markers. A finding is for a human to look
# at, never an auto-correction.
#
# Offline checks read docs/data/metadata.json and always run. The live walk runs
# too, BY DEFAULT: it needs `make clearance` first and costs ~33 requests at one
# per 2s (~2 min). Without clearance it exits 2 = INCONCLUSIVE, not 1 -- being
# unable to ask the site says nothing about the collection, same convention as
# check-source-links.
#
# Every number is re-derived by the run that publishes it, so a run without the
# walk reports NO gap: the listing's half of the subtraction lives on the site,
# and quoting a remembered figure is the exact failure this guards against.
#
# Hence one mode selector rather than two knobs. --offline-skip-gap skips the
# walk AND the gap: with --update-about it leaves the published audit region
# untouched, since rewriting it gap-less would delete the per-category listing
# figures nothing offline can reproduce. The intro's data-stat figures still
# refresh either way -- those are measured from files on disk.
#   make audit                                    # report, incl. the live walk
#   make audit ARGS=--offline-skip-gap            # our side only, gap left alone
#   make audit-update-about                       # ...and publish it
audit:
	python -m pipeline.audit $(ARGS)

# Tests the chronology argument against Vishvas Vasuki's 2025 fulltext dump:
# does a moved upload timestamp mean a revised text? (It does not -- it marks a
# new acquisition.) Reads the raw_etexts checkout AT its Feb-2025 commit, so it
# needs that checkout present; no network. Minutes of git archaeology, so the
# result is cached in data/dump_stats.json and `audit` just reads it.
dump-analysis:
	python -m pipeline.dump_analysis

audit-update-about:
	python -m pipeline.audit --update-about $(ARGS)

# ============================================================================
# GROUP 3 -- build and serve the site.
# ============================================================================

# Build docs/data/tree.json from docs/data/metadata.json -- the whole
# catalogue, 11066 works against the snapshot's 2287. No byte sizes until the
# full fetcher adds them to the metadata records.
#
# Emits a flat work list plus the two axes' keys, NOT a nested tree: category
# and author are independent, each optionally grouped by the other, and the
# browser does the grouping rather than the builder materializing four copies
# of the corpus. See pipeline/shape.py.
#
# No network, no snapshot, ~1s.
#   make build
build:
	python -m pipeline.build_tree $(ARGS)

# Build docs/data/snapshot_tree.json from the third-party snapshot -- 2287
# books (21% of the catalogue), but WITH measured byte sizes, which is the only
# reason this target still exists. Same shape as `build`, so the frontend can
# read either file; they are alternatives, never combined.
#
# Requires `parse` and `count-snapshot-sizes` to have run, and errors telling you which is
# missing. TRUSTS the size cache and cannot tell that it is stale.
#   make snapshot-tree
snapshot-tree:
	python -m pipeline.build_snapshot_tree $(ARGS)

# Build docs/data/changelog.json from each work's addition date -- decoded from
# the thumbnail filename's epoch, the site's only "when was this added" signal,
# and interpolated from the serial neighbourhood where that stamp runs late.
# Reads docs/data/metadata.json, so `parse-metadata` must have run (that is
# where the interpolation happens), plus the snapshot inventory to show what we
# hold per period. Local only, no network.
#
# Monthly is the published granularity, shared with the sibling atlases so
# sagara-sangama can plot all three on one time axis; the frontend groups
# months into quarters or years at render time. Pass year only for a quick
# local look, never for what ships.
#   make changelog
#   make changelog ARGS="--granularity year"
changelog:
	python -m pipeline.build_changelog $(ARGS)

# Serve docs/ locally on port 8002, gzipping JSON/JS/HTML/CSS.
# Same server, plus the locally cached text at /text/<serial>, so each work
# gets a `txt` badge. LOCALHOST ONLY -- binds 127.0.0.1, and the text lives
# outside docs/ so no deploy can pick it up.
serve-fulltext:
	cd docs && python ../serve_docs.py --fulltext $(ARGS)

serve:
	cd docs && python ../serve_docs.py $(ARGS)

# Same server, but serving the snapshot tree at the frontend's tree.json URL --
# 2287 books (21%) WITH measured byte sizes, instead of all 11066 without them.
# A serve-time choice only: both builders always write their own file, and the
# frontend asks for the same path either way.
#   make serve-snapshot
serve-snapshot:
	cd docs && python ../serve_docs.py --snapshot $(ARGS)

free-server-port:
	kill $$(lsof -ti tcp:8002)

get-server-ip-address:
	ifconfig | grep "inet " | grep -v 127.0.0.1
