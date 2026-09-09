#!/usr/bin/env python3
"""Local dev server for docs/, gzip-compressing responses and setting
Cache-Control so repeated reloads during iteration (and testing over an
ngrok tunnel on a mobile data plan) don't re-transfer the full uncompressed
tree.json/changelog.json on every load. python -m http.server does neither.

Also picks WHICH tree the frontend gets. The two builders are parallel tracks
that always write their own file -- `make build` -> tree.json (all 11066 works,
no byte sizes) and `make snapshot-tree` -> snapshot_tree.json (2287 books, with
sizes). `--snapshot` serves the latter in place of the former, so the frontend
never knows which it asked for: it fetches tree.json and reads the `source`
field in the payload to label what it got.

## `--fulltext` is localhost-only, and deliberately not publishable

`--fulltext` exposes the cached corpus text at `/text/<serial>`, so the
frontend can offer a "txt" link beside the existing PDF and site-text badges.

**That text is never published.** It lives outside `docs/` -- under the
gitignored `data/` -- so no build step and no deploy can pick it up, and
GitHub Pages serves `docs/` alone. Only this dev server can reach it, and only
when explicitly asked. The flag binds to 127.0.0.1 rather than all interfaces
for the same reason: a corpus that is fine to read locally is not a corpus
this repo has any right to redistribute.

Serial -> filename comes from the fetch journal, because filenames embed a
transliterated title (`120 - karmmapradIpaH.txt`) and cannot be reconstructed
from an id. The frontend therefore asks for `/text/120` and never needs to
know what the file is called.
"""
import argparse
import gzip
import re
import json
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

PORT = 8002
CACHE_MAX_AGE = 60  # seconds; short, so edits during iteration aren't stale for long
COMPRESSIBLE_SUFFIXES = {".json", ".js", ".html", ".css", ".svg"}

# What the frontend always asks for -> what it gets under --snapshot.
TREE_REQUEST = "/data/tree.json"
SNAPSHOT_TREE = "data/snapshot_tree.json"

# Where the corpus text lives, relative to the repo root (NOT docs/).
# `text_extract/` is the standard location every Atlas uses; EBS has not been
# split into fetch/extract yet, so its cache is the fallback -- see
# rivulet/extract/ebharatisampat/__init__.py.
TEXT_DIRS = ("data/text_extract", "data/fulltext_cache")
TEXT_PREFIX = "/text/"
JOURNAL = "data/text_fetch_log.jsonl"


def load_text_index(root: Path) -> dict[str, Path]:
    """serial -> the file holding its text, for whichever dir exists.

    The journal is the only reliable link: it records the filename each serial
    was written to, and those names embed a transliterated title that nothing
    downstream can reconstruct. Later lines win, matching `load_progress`.
    """
    journal = root / JOURNAL
    if not journal.exists():
        return {}
    names: dict[str, str] = {}
    for line in journal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue  # torn final line from a hard kill
        if entry.get("file") and entry.get("serial") is not None:
            names[str(entry["serial"])] = entry["file"]

    index: dict[str, Path] = {}
    for serial, name in names.items():
        for directory in TEXT_DIRS:
            candidate = root / directory / name
            if candidate.is_file():
                index[serial] = candidate
                break
    return index



# "Local" means this machine or this LAN, matching docs/local-links.js:
# browsing from a phone at 192.168.1.x is a normal way to work here.
_LOCAL_ORIGIN_RE = re.compile(
    r"^https?://(localhost|127\.\d+\.\d+\.\d+|\[::1\]|"
    r"10\.[\d.]+|192\.168\.[\d.]+|172\.(1[6-9]|2\d|3[01])\.[\d.]+)"
    r"(:\d+)?$"
)


def _is_local_origin(origin: str) -> bool:
    return bool(origin) and bool(_LOCAL_ORIGIN_RE.match(origin))


class CachingGzipHandler(SimpleHTTPRequestHandler):
    serve_snapshot = False
    fulltext = False
    text_index: dict[str, Path] = {}

    def end_headers(self):
        self.send_header("Cache-Control", f"max-age={CACHE_MAX_AGE}")
        super().end_headers()

    def do_GET(self):
        route = self.path.split("?")[0]
        if route.startswith(TEXT_PREFIX):
            self._serve_text(route[len(TEXT_PREFIX):])
            return

        if self.serve_snapshot and route == TREE_REQUEST:
            substitute = Path(self.directory) / SNAPSHOT_TREE
            if not substitute.is_file():
                self.send_error(404, "snapshot tree not built; run `make snapshot-tree`")
                return
            self._serve_gzipped(str(substitute))
            return

        path = self.translate_path(self.path)
        accepts_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
        if accepts_gzip and Path(path).suffix in COMPRESSIBLE_SUFFIXES and Path(path).is_file():
            self._serve_gzipped(path)
        else:
            super().do_GET()

    def do_HEAD(self):
        # The frontend probes `/text/` to learn whether this server offers the
        # corpus at all. Answered with a header rather than by the shape of a
        # 404, so the page never has to guess from a status code that a plain
        # static host could also produce.
        if self.path.split("?")[0].startswith(TEXT_PREFIX):
            self.send_response(404)
            self.send_header("X-Fulltext-Mode", "on" if self.fulltext else "off")
        # Sagarasangama runs on another port, so its probe and its `txt`
        # links are cross-origin. Allowed narrowly: only the /text/ route,
        # only in fulltext mode, and only for a localhost/private-network
        # origin -- the same "local means this machine or this LAN" rule
        # local-links.js uses. Nothing here widens what the PUBLISHED site
        # can reach, because the published site has no /text/ route at all.
        origin = self.headers.get("Origin", "")
        if self.fulltext and _is_local_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Expose-Headers", "X-Fulltext-Mode")

            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_HEAD()

    def _serve_text(self, serial):
        """`/text/<serial>` -> the cached text, as UTF-8 plain text.

        404s rather than erroring when fulltext mode is off, so a stale page
        left open from a `--fulltext` session degrades to a dead badge instead
        of a traceback.

        The serial is looked up in a prebuilt index, never joined onto a path,
        so a crafted `/text/../../etc/passwd` finds no key and gets a 404. That
        is the whole traversal defence: no user-supplied string ever reaches
        the filesystem.
        """
        path = self.text_index.get(unquote(serial).strip("/"))
        if path is None:
            self.send_error(404, "no text for that serial")
            return
        raw = path.read_bytes()
        body = gzip.compress(raw) if "gzip" in self.headers.get("Accept-Encoding", "") else raw
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        # Sagarasangama runs on another port, so its probe and its `txt`
        # links are cross-origin. Allowed narrowly: only the /text/ route,
        # only in fulltext mode, and only for a localhost/private-network
        # origin -- the same "local means this machine or this LAN" rule
        # local-links.js uses. Nothing here widens what the PUBLISHED site
        # can reach, because the published site has no /text/ route at all.
        origin = self.headers.get("Origin", "")
        if self.fulltext and _is_local_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Expose-Headers", "X-Fulltext-Mode")

        if body is not raw:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_gzipped(self, path):
        raw = Path(path).read_bytes()
        # The substitution path calls this directly, so honour Accept-Encoding
        # here rather than assuming the caller checked.
        if "gzip" not in self.headers.get("Accept-Encoding", ""):
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        compressed = gzip.compress(raw)
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(compressed)))
        self.end_headers()
        self.wfile.write(compressed)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("port", nargs="?", type=int, default=PORT)
    parser.add_argument(
        "--snapshot", action="store_true",
        help="serve the snapshot tree (2287 books, with byte sizes) in place of "
             "the full one (11066 works, no sizes)",
    )
    parser.add_argument(
        "--fulltext", action="store_true",
        help="serve the cached corpus text at /text/<serial>, so the frontend "
             "shows a `txt` link. LOCALHOST ONLY -- the text lives outside "
             "docs/ and is never published",
    )
    args = parser.parse_args()

    CachingGzipHandler.serve_snapshot = args.snapshot
    which = "snapshot_tree.json (2287 books, with sizes)" if args.snapshot \
        else "tree.json (11066 works)"

    root = Path(__file__).resolve().parent
    CachingGzipHandler.fulltext = args.fulltext
    if args.fulltext:
        CachingGzipHandler.text_index = load_text_index(root)

    # Pin the served directory to docs/ rather than inheriting the caller's
    # cwd. `make serve` does `cd docs` first, so this changes nothing there --
    # but run from the repo root the old behaviour exposed the WHOLE repo,
    # `data/clearance.json` (live session credentials) included. Serving is now
    # correct regardless of where the process was started, which is the only
    # version of this that is safe to combine with --fulltext.
    handler = partial(CachingGzipHandler, directory=str(root / "docs"))

    # Bound to loopback in fulltext mode. Everything else this server does is
    # already-published material, but the corpus text is not ours to hand out,
    # so it is not reachable from another machine even by accident.
    host = "127.0.0.1" if args.fulltext else ""
    server = HTTPServer((host, args.port), handler)
    print(f"Serving docs/ on http://localhost:{args.port} "
          f"(gzip + Cache-Control: max-age={CACHE_MAX_AGE})")
    print(f"  tree: {which}")
    if args.fulltext:
        count = len(CachingGzipHandler.text_index)
        print(f"  fulltext: {count} works at /text/<serial> "
              f"-- LOCALHOST ONLY, never published")
        if not count:
            print("            (none found -- is data/fulltext_cache present?)")
    server.serve_forever()


if __name__ == "__main__":
    main()
