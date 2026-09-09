"""Where the pipeline reads from and writes to.

The snapshot is a *third-party* corpus checked out elsewhere on disk
(`raw_etexts`, not ours). It is read-only input: nothing here writes to it, and
none of it is copied into this repo. Phase 2 replaces the snapshot with our own
scrape, at which point only `snapshot_root()` needs to change.

The default walks up and over to a sibling checkout, which is brittle if
anything moves, so it is overridable via the EBS_SNAPSHOT env var (or --snapshot
on the individual stages). Paths are resolved relative to this file, never to
the current working directory, so the stages behave the same regardless of where
they're invoked from.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# atlases/e-bharatisampat-atlas -> Git/raw_etexts/mixed/ebhAratI-sampat
_DEFAULT_SNAPSHOT = (
    REPO_ROOT.parent.parent.parent / "raw_etexts" / "mixed" / "ebhAratI-sampat"
)

DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"

# Snapshot-derived, and named so: both files describe the third-party snapshot,
# not the site. Phase 2's own acquisition writes alongside them, and the prefix
# keeps which-came-from-where legible once both exist.
INVENTORY_PATH = DATA_DIR / "snapshot_inventory.jsonl"
SNAPSHOT_SIZES_PATH = DATA_DIR / "snapshot_text_sizes.jsonl"

# Site-derived: the site's own catalogue, against the snapshot's partial copy.
CATALOGUE_PATH = DATA_DIR / "catalogue.jsonl"

# The tier-2 metadata cache, keyed on the catalogue's base64 id. Holds raw HTML
# rather than parsed fields, so a number we didn't think to extract never costs
# a second scrape. The log beside it is the fetch journal, not the metadata.
METADATA_CACHE_DIR = DATA_DIR / "metadata_cache"
METADATA_LOG_PATH = DATA_DIR / "metadata_fetch_log.jsonl"

# Tier 3: the readers' full text, plus the byte sizes measured from it. Same
# posture as the tier-2 cache -- gitignored, outside docs/, holding what the
# site served so that re-deriving a number never costs the network twice. The
# atlas still publishes no text; the cache is a working artifact, not output.
FULLTEXT_CACHE_DIR = DATA_DIR / "fulltext_cache"
TEXT_SIZES_PATH = DATA_DIR / "text_sizes.jsonl"
TEXT_LOG_PATH = DATA_DIR / "text_fetch_log.jsonl"
# Books still unfinished at the chunk ceiling -- the deep tail, and the
# candidate list for a manual download. Rewritten on every run.
TEXT_OPEN_PATH = DATA_DIR / "text_open_books.jsonl"
# Parsed metadata lands in docs/, not data/: it is tracked and published, being
# what the frontend reads, unlike the gitignored cache it is derived from.
METADATA_PATH = DOCS_DATA_DIR / "metadata.json"

TREE_PATH = DOCS_DATA_DIR / "tree.json"

# The snapshot track's own output, deliberately a different file: the two
# builders emit the same shape but different corpora, and which one the
# frontend gets is a serve-time flag. Gitignored, unlike `tree.json` -- Pages
# serves ours, while this one is a local cross-check that dies with the
# snapshot track.
SNAPSHOT_TREE_PATH = DOCS_DATA_DIR / "snapshot_tree.json"

# Stamped by `build_tree` from the fetch journal, never by hand -- see
# `stamp_version`. The snapshot builder must not write it.
VERSION_PATH = DOCS_DIR / "VERSION"

# Session clearance and the identity it is bound to live in one record,
# written by `clearance.py` and read by the fetchers. The profile directory
# beside it is session state rather than pipeline data, kept here only so a
# separate one exists.
CLEARANCE_PATH = DATA_DIR / "clearance.json"
CLEARANCE_PROFILE_DIR = DATA_DIR / "clearance_profile"


def snapshot_root(override: str | None = None) -> Path:
    """Resolve the snapshot directory, preferring an explicit override."""
    raw = override or os.environ.get("EBS_SNAPSHOT")
    path = Path(raw).expanduser() if raw else _DEFAULT_SNAPSHOT
    return path.resolve()
