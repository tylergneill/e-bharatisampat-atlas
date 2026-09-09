"""Live pinned-status-line progress for pipeline stages.

Ported from `../sanskrit-wikisource-atlas/pipeline/progress.py`, which states
the case for it: a long silent phase is ambiguous between "working" and
"hung", and the answer is a single carriage-returned status line, repainted
often and truncated to terminal width so it cannot wrap and leave garbage
behind when cleared. Copied rather than imported, following `audit.py` -- an
Atlas stays runnable without its siblings on disk.

Two differences from the sibling, both because this one measures a local
cache serially rather than draining a process pool:

  - the detail it shows is the book being measured RIGHT NOW, not the last
    one completed. A serial loop knows what it is working on, and that is
    precisely the name a hang needs to leave on screen.
  - no `to_iast` helper. The sibling transliterates Devanagari page titles
    for readability; the names here are cache filenames, already Harvard-
    Kyoto ASCII (see text_measure.to_hk).
"""

from __future__ import annotations

import shutil
import sys
import time


class LiveCounter:
    """Pinned single-line progress: count/total with elapsed time, rate,
    percent, and ETA. Call update() as work starts on each item; call close()
    once at the end to leave a final line and move to a fresh line.

    Writes to stderr, leaving stdout as the stage's summary alone -- and a
    redirected stdout keeps the pinned line off the file, where carriage
    returns would be noise. Repainting is suppressed when stderr is not a
    terminal, so a log or CI transcript gets the summary and nothing else.
    """

    def __init__(self, label: str, total: int | None = None,
                 min_interval: float = 0.1, stream=None):
        self.label = label
        self.total = total
        self.count = 0
        self.min_interval = min_interval
        self._stream = stream if stream is not None else sys.stderr
        self._tty = self._stream.isatty()
        self._start = time.time()
        self._last_paint = 0.0
        self._status_len = 0
        self._last_detail = ""

    def _clear(self) -> None:
        if self._status_len:
            self._stream.write("\r" + " " * self._status_len + "\r")

    def _render(self, width: int) -> str:
        elapsed = time.time() - self._start
        rate = self.count / elapsed if elapsed > 0 else 0.0
        parts = [self.label]
        if self.total:
            pct = 100 * self.count / self.total
            parts.append(f"{self.count}/{self.total} ({pct:.0f}%)")
            remaining = self.total - self.count
            eta = remaining / rate if rate > 0 else None
            eta_str = f", ETA {eta:.0f}s" if eta is not None else ""
            parts.append(f"{rate:.1f}/s, {elapsed:.0f}s elapsed{eta_str}")
        else:
            parts.append(f"{self.count} done")
            parts.append(f"{rate:.1f}/s, {elapsed:.0f}s elapsed")
        # The core stats are the load-bearing part of the line and must always
        # survive truncation whole. The detail is nice-to-have -- appended only
        # if it fits in full, dropped entirely otherwise, so a long filename
        # never gets sliced into a dangling "-- " with no text after it.
        core = " -- ".join(parts)
        if self._last_detail:
            with_detail = core + f" -- {self._last_detail}"
            if len(with_detail) <= width:
                return with_detail
        return core

    def update(self, detail: str | None = None, n: int = 1,
               force: bool = False) -> None:
        self.count += n
        if detail is not None:
            self._last_detail = detail
        if not self._tty:
            return
        now = time.time()
        if not force and (now - self._last_paint) < self.min_interval:
            return
        self._last_paint = now
        self._clear()
        width = shutil.get_terminal_size(fallback=(80, 24)).columns
        line = self._render(max(width - 1, 0))
        self._status_len = len(line)
        self._stream.write(line)
        self._stream.flush()

    def close(self) -> None:
        if not self._tty:
            return
        self.update(n=0, force=True)
        self._stream.write("\n")
        self._stream.flush()
