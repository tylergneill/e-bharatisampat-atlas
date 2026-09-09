"""Does a moved upload timestamp mean the text was revised?

The About page argues that serial number and thumbnail timestamp are both
proxies for chronology. That argument needs an outside check, and there is
exactly one available: Vishvas Vasuki's fulltext dump at
`sanskrit/raw_etexts`, which captured a slice of EBS years before we did.

**The dump is a live repo, not a snapshot.** It is effectively frozen at
2025-02-28 -- 2737 text files by that month, none added since -- but later
commits still rewrite files, and 33% of the books our inventory reads have been
re-scraped upstream since. So this reads the tree AT the February 2025 commit,
never the working tree, or the "before" is contaminated by the "after".

**Identity comes from the serial each file declares, never from its path.**
The upstream scraper reuses filenames across different records: 48 of 756
path-joins pair two different books (`kathAsaritsAgaraH.md` at HEAD is serial
9213, at baseline 432). Joining by path silently compares unrelated texts.

**Only complete books count.** A book stopped at the tier-3 chunk ceiling has
real text on disk but has not ended, and its deficit would read as an upstream
deletion. `text_fetch_log.jsonl` carries the completeness flag.

Emits `data/dump_stats.json` for `pipeline/audit.py` to publish, and
`data/dump_vs_scrape.jsonl` with one row per compared book.
"""

import json
import re
import subprocess
import unicodedata
from pathlib import Path

from pipeline.config import DOCS_DIR, METADATA_PATH, snapshot_root

# Last commit on or before 2025-02-28, when the dump stopped growing.
BASE_COMMIT = "6de660bf5110123951f95619a8316c5017bcfd78"
CUTOFF = "2025-02-28"

DEVA = re.compile(r"[ऀ-ॿ]+")
SERIAL_RE = re.compile(r'"serial no\." = "Ebharati-(\d+)"')

DATA_DIR = DOCS_DIR.parent / "data"
STATS_PATH = DATA_DIR / "dump_stats.json"
ROWS_PATH = DATA_DIR / "dump_vs_scrape.jsonl"
FULLTEXT_DIR = DATA_DIR / "fulltext_cache"
FETCH_LOG = DATA_DIR / "text_fetch_log.jsonl"

# Below this many Devanagari characters a file is a stub or a failed fetch, not
# a text; comparing it measures the failure rather than the corpus.
MIN_CHARS = 500


def _repo_root():
    """The dump's git root -- snapshot_root() points inside it."""
    root = snapshot_root()
    for parent in [root, *root.parents]:
        if (parent / ".git").exists():
            return parent
    raise SystemExit(f"no git repo above {root} -- is the raw_etexts checkout present?")


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def deva_chars(text):
    """Devanagari only, NFC-normalized: the part two scrapers must agree on.

    Byte counts conflate real change with markup and roman apparatus, which is
    exactly the difference between the two capture paths.
    """
    return "".join(DEVA.findall(unicodedata.normalize("NFC", text)))


def index_baseline(repo, prefix):
    """Every text file at the baseline commit, keyed by its declared serial."""
    listing = _git(repo, "ls-tree", "-r", "--name-only", BASE_COMMIT, "--", prefix)
    paths = [p for p in listing.stdout.splitlines()
             if p.endswith(".md") and not p.endswith("_index.md")]
    by_serial = {}
    for path in paths:
        shown = _git(repo, "show", f"{BASE_COMMIT}:{path}")
        if shown.returncode != 0:
            continue
        match = SERIAL_RE.search(shown.stdout[:2000])
        if match:
            by_serial.setdefault(int(match.group(1)), shown.stdout)
    return len(paths), by_serial


def load_completeness():
    """serial -> did the tier-3 walk finish this book? Last entry wins."""
    done = {}
    if FETCH_LOG.exists():
        for line in FETCH_LOG.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("serial") is not None:
                    done[rec["serial"]] = bool(rec.get("complete"))
    return done


def load_cache():
    """serial -> our fetched text file, from the `<serial> - <title>.txt` name."""
    out = {}
    for path in FULLTEXT_DIR.glob("*.txt"):
        head = path.name.split(" - ")[0]
        if head.isdigit():
            out[int(head)] = path
    return out


def main():
    repo = _repo_root()
    prefix = str(snapshot_root().relative_to(repo))
    print(f"reading {repo} at {BASE_COMMIT[:9]} ({CUTOFF})")

    n_files, baseline = index_baseline(repo, prefix)
    print(f"  {n_files} text files, {len(baseline)} with a readable serial")

    works = json.loads(METADATA_PATH.read_text())
    works = works["works"] if isinstance(works, dict) else works
    uploaded = {w["serial"]: w.get("uploaded") for w in works if w.get("serial")}

    # Q1: does a post-dump stamp mark a new item or a revised one?
    stamped_after = [s for s, d in uploaded.items() if d and d > CUTOFF]
    reuploads = [s for s in stamped_after if s in baseline]

    # Q2/Q3: for books held at both ends, did the text move?
    complete = load_completeness()
    cache = load_cache()
    rows = []
    for serial, before in baseline.items():
        path = cache.get(serial)
        if path is None or not complete.get(serial):
            continue
        old = deva_chars(before)
        new = deva_chars(path.read_text(errors="ignore"))
        if len(old) < MIN_CHARS or len(new) < MIN_CHARS:
            continue
        rows.append({
            "serial": serial,
            "uploaded": uploaded.get(serial),
            "base_chars": len(old),
            "now_chars": len(new),
            "ratio": len(new) / len(old),
            "restamped": bool(uploaded.get(serial) and uploaded[serial] > CUTOFF),
        })

    ROWS_PATH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")

    moved = [r for r in rows if r["restamped"]]
    still = [r for r in rows if not r["restamped"]]

    def within2(group):
        if not group:
            return 0.0
        return round(sum(0.98 <= r["ratio"] <= 1.02 for r in group) / len(group) * 100, 1)

    stats = {
        "dump_files": n_files,
        "dump_compared": len(rows),
        "post_dump_stamped": len(stamped_after),
        "post_dump_new": len(stamped_after) - len(reuploads),
        "post_dump_reuploads": len(reuploads),
        "reup_within2": within2(moved),
        "unch_within2": within2(still),
    }
    STATS_PATH.write_text(json.dumps(stats, indent=2) + "\n")

    print(f"\n  stamped after {CUTOFF}: {stats['post_dump_stamped']}"
          f" -- {stats['post_dump_new']} new, {stats['post_dump_reuploads']} re-uploads")
    print(f"  compared (complete, both ends): {len(rows)}")
    print(f"    restamped  n={len(moved):5d}  within +-2%: {stats['reup_within2']}%")
    print(f"    unchanged  n={len(still):5d}  within +-2%: {stats['unch_within2']}%")
    print(f"\nwrote {STATS_PATH} and {ROWS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
