"""Pure text measurement: no network, no site knowledge, no I/O but the journal.

Extracted from `fetch_text.py` so that measuring the cache does not depend on
the code that fills it. `count_sizes.py` needs exactly four things from the
fetcher -- `devanagari_chars`, `strip_furniture`, `to_iast`, `load_progress` --
and none of them touch the network. Leaving them in the fetcher meant that
re-deriving sizes from a cache already on disk imported a module whose job is
to cross the network.

That split is a **publishing boundary**: fulltext acquisition moves to the
private `rivulet` package, while everything that reads a cache already present
stays here and public. These functions stay because they only ever read text.
`rivulet` imports them back from this module -- rivulet may depend on an Atlas,
an Atlas may never require rivulet.

Everything here is a pure function of its input except `load_progress`, which
reads the fetch journal. The journal is resume state rather than a log, and
parsing it is the same "read what is already on disk" operation.
"""

import json
import re
from pathlib import Path

from pipeline.config import FULLTEXT_CACHE_DIR

DEVANAGARI = ("ऀ", "ॿ")

# Anything that makes a filename awkward in a shell or on another filesystem.
UNSAFE_RE = re.compile(r'[/\\:*?"<>|\x00-\x1f]')

_transliterator = None
_hk_transliterator = None


def to_hk(text: str) -> str:
    """Devanagari -> Harvard-Kyoto for filenames: plain ASCII, no diacritics to
    break shell completion, no normalization traps. Mirrors fetch_metadata's
    helper so the two caches file the same book under the same name."""
    global _hk_transliterator
    if not any(DEVANAGARI[0] <= ch <= DEVANAGARI[1] for ch in text):
        return text
    if _hk_transliterator is None:
        from skrutable.transliteration import Transliterator
        _hk_transliterator = Transliterator()
    return _hk_transliterator.transliterate(text, from_scheme="DEV", to_scheme="HK")


def cache_path(serial: int, title: str | None) -> Path:
    """`data/fulltext_cache/6385 - manusmRtiH.txt`.

    Deliberately the same shape as `metadata_cache/`'s names, so one book's two
    cached artifacts sit under the same label and a known serial is findable in
    either directory by the same string."""
    if not title:
        return FULLTEXT_CACHE_DIR / f"{serial}.txt"
    name = UNSAFE_RE.sub("", to_hk(title)).strip()[:150].rstrip()
    return FULLTEXT_CACHE_DIR / (f"{serial} - {name}.txt" if name
                                 else f"{serial}.txt")


def to_iast(text: str) -> str:
    """Devanagari -> IAST, for the transliterated byte count. Mirrors
    count_snapshot_sizes so both trees' figures mean the same thing."""
    global _transliterator
    if not text.strip():
        return ""
    if _transliterator is None:
        from skrutable.transliteration import Transliterator
        _transliterator = Transliterator()
    return _transliterator.transliterate(text, from_scheme="DEV", to_scheme="IAST")


def devanagari_chars(text: str) -> int:
    return sum(1 for ch in text if DEVANAGARI[0] <= ch <= DEVANAGARI[1])


# The site's own page chrome, appended to some reader responses: a visitor
# counter, the footer nav, and the copyright line. Tag stripping leaves it in
# the extracted text, where it is indistinguishable from content by size alone.
#
# Measured over the whole cache (2026-08-22): present in 660 of 5046 files, and
# in every one of them it is the SAME 504-character block, always a suffix,
# always beginning at this marker. So it is stripped by its known shape rather
# than guessed at.
#
# Deliberately NOT a positive test for Devanagari. Keeping only Devanagari-
# bearing lines would also delete legitimate roman-script content -- serial
# 2367 is the entire Rigveda in romanized transliteration, 1.4 MB with zero
# Devanagari, and a positive filter reduces it to nothing.
FURNITURE_MARKER = "Number Of Visitors"


def strip_furniture(text: str) -> str:
    """`text` with the site's trailing page chrome removed.

    Cuts at the marker only when it appears in the last part of the text, where
    the chrome lives. A book that happens to quote the phrase mid-body keeps
    everything, since truncating a text at a coincidental match would lose real
    content -- the failure this is meant to prevent, in the opposite direction.
    """
    index = text.rfind(FURNITURE_MARKER)
    if index == -1:
        return text
    # The block runs to the end of the response, so anything before the marker
    # is content and anything after is chrome. Only treat it as chrome when
    # what follows is about the right size for it.
    if len(text) - index > 4000:
        return text
    return text[:index].rstrip()


def load_progress(path: Path) -> dict[int, dict]:
    """serial -> {chunks_written, complete} from the fetch journal.

    **The journal is the master record of how much of each book is on disk.**
    The cached `.txt` holds the text with no chunk markers -- a deliberate
    choice, so the files stay clean and readable -- which means the file itself
    cannot say where the next chunk should start. This does.

    That makes the journal load-bearing rather than informational: lose it and
    a resumed run would append from chunk 0 onto a file that already holds
    chunks 0-20, duplicating text. Two things guard against that:

      - it is append-only, one line per pass, flushed as it goes
      - `chunks_written` is only ever advanced *after* the text is on disk,
        so a crash between the two leaves the log behind the file rather than
        ahead of it -- and a run that re-fetches an already-written chunk
        wastes a request but cannot corrupt the file, because the duplicate
        chunk is caught by the `piece in chunks` test on the next pass.

    Later lines win: each pass rewrites the serial's state.
    """
    if not path.exists():
        return {}
    progress: dict[int, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn final line from a hard kill
            serial = record.get("serial")
            if serial is None or "chunks_written" not in record:
                continue
            # Where to resume. Falls back to the chunk count for lines
            # written before the cursor was journalled: those predate the
            # dead-chunk fix, and the count is the only estimate they carry
            # -- too low, so a resume refetches rather than skipping, which
            # is the safe direction to be wrong in.
            cursor = record.get("next_my_id", record["chunks_written"])
            # The cursor only ever moves FORWARD, even though later lines win
            # for everything else. A pass that walked no rows still journals a
            # cursor, and a run at a lower --max-chunks journals the lower
            # ceiling -- so plain last-line-wins let `CHUNKS=12` then `CHUNKS=5`
            # rewind a book from 12 to 5 and re-walk rows already on disk. 53
            # serials did exactly that. Deep books are the ones affected, since
            # they are the ones a lowered ceiling can fall behind.
            previous = progress.get(serial, {}).get("next_my_id", 0)
            # The unproofread flag STICKS once any pass has recorded it. Later
            # lines win for everything else, but only the pass that actually
            # checked writes a value -- every subsequent pass omits the key --
            # so plain last-line-wins would erase it and re-check the book on
            # every run, which is exactly the idempotence this is for.
            #
            # `is not None`, not truthiness: False is a real answer meaning
            # "checked, proofread", and must not read as "never checked".
            flag = record.get("unproofread")
            if flag is None:
                flag = progress.get(serial, {}).get("unproofread")
            # Consecutive failures that left the cursor exactly where it was.
            # A book whose front matter is dead fails at the same row forever:
            # it never advances, never completes, so it re-enters the queue on
            # every rung and costs a request per pass indefinitely. Serial 2736
            # did this 48 times across five days. Any pass that moves the
            # cursor -- or succeeds -- resets the count, so a book failing on a
            # transient network error is unaffected.
            stuck = progress.get(serial, {}).get("stuck", 0)
            if record.get("error") and cursor <= previous:
                stuck += 1
            elif record.get("ok"):
                stuck = 0
            progress[serial] = {
                "chunks_written": record["chunks_written"],
                "next_my_id": max(cursor, previous),
                "complete": bool(record.get("complete")),
                "unproofread": flag,
                "stuck": stuck,
            }
    return progress
