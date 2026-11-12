.PHONY: serve-fulltext parse count-snapshot-sizes \
        clearance walk-shelves catalogue fetch-metadata parse-metadata fetch-text count-sizes \
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
#   walk-shelves -----> data/shelves_cache/<date>/   raw JSON, three shelves
#   catalogue --------> data/catalogue.jsonl      one row per item per shelf
#   fetch-metadata ---> data/metadata_cache/*.html   raw, one file per work
#   parse-metadata ---> docs/data/metadata.json   serial, sub-cat, language, ...
#
# Fetching here was an explicit decision, not an assumption; keep the rate
# polite.

# The three shelves (E-Books, Unicode Books, AI-converted books) -> raw JSON
# pages under data/shelves_cache/<date>/, plus a manifest when complete.
# *** THIS HITS THE NETWORK. *** ~150 requests, 5–15 min. NEEDS `rivulet`
# (exits 2 without it). Rerun the same day to resume an interrupted walk.
#   make walk-shelves
walk-shelves:
	python -m pipeline.walk_shelves $(ARGS)

# The latest complete shelf walk -> data/catalogue.jsonl, one row per item per
# shelf, with serial and base64 id. No network.
#   make catalogue
#   make catalogue ARGS="--walk data/shelves_cache/2026-11-06"
catalogue:
	python -m pipeline.parse_listings $(ARGS)

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
# One request per book since the site rebuild (the whole book is one page);
# the raw page is kept gzipped in data/raw_cache/.
#
#   make fetch-text MAX_REQUESTS=0                      # plan only, fetches nothing
#   make fetch-text MAX_REQUESTS=500                    # a bounded run
#   make fetch-text                                     # everything not yet refetched
#   make fetch-text ARGS="--reextract"                  # raw_cache -> text + sizes, offline
#
# A book whose raw page is already in data/raw_cache/ is never fetched again.
# For a fresh full refetch, move data/raw_cache/ aside first. A page the site
# truncates is completed in the same run from the old get_unicode.php endpoint.
#   make fetch-text MAX_REQUESTS=50 DELAY=3 ARGS="--reader read_chapter"
#
# Ctrl-C stops cleanly (exit 0) and a rerun resumes.
fetch-text:
	python -m pipeline.fulltext \
	  $(if $(MAX_REQUESTS),--max-requests $(MAX_REQUESTS)) \
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

# Are the links in docs/app.js still pointing at what we claim? They are built
# from our own data, so a change upstream does not error -- it quietly changes
# what the reader is shown. This asks the site, for a sample of each kind:
# text and PDF readers open the right book, the three shelves still read `?q=`
# and filter by inclusion, and search still honours `type=` and states a total.
#
# *** HITS THE NETWORK. *** ~50 requests at one per 2s. No clearance needed
# since the rebuild (sent if data/clearance.json exists). Exit 0 fine, 1
# drifted, 2 inconclusive (network error / the browser check came back) -- 2 is
# deliberately not a failure, since being unable to ask says nothing about the
# links. What each check means: the docstring of rivulet's check_source_links.
#   make check-source-links
#   make check-source-links ARGS="--readers 10 --authors 10"
check-source-links:
	python -m pipeline.check_source_links $(ARGS)

# What the source collection gets wrong, published to the About page.
#
# Never mutates anything: it reads, reports, and rewrites only its own region of
# docs/about.html between the AUDIT markers. A finding is for a human to look
# at, never an auto-correction.
#
# No network: reads metadata.json, catalogue.jsonl and the size files, and
# re-derives every number it publishes. A figure whose input file is missing on
# this checkout keeps its published value rather than being blanked.
#   make audit                # report only
#   make audit-update-about   # ...and publish it
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
