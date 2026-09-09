"""Every networked entry point this Atlas has, and none of them live here.

Acquisition and the networked checks moved to the private `rivulet` package on
2026-09-03. This module is the one place this repo names it, and it never
requires it.

## What this repo can still do alone

Everything that reads a cache already on disk -- which is most of the pipeline:

    make parse-metadata   parse-listings   count-sizes   build
    make changelog        audit (offline)  serve         shape

What needs rivulet is anything that crosses the network:

    make clearance            establish session clearance
    make fetch-metadata       one readSearch.php per work
    make fetch-text           the fulltext scrape (already private)
    make check-source-links   have the shipped source links drifted?

**A checkout without rivulet cannot acquire anything.** That is accepted and
deliberate: there is no meaningful way to obtain this corpus without the
acquisition code, and the site is gated besides. If `data/` is already
populated, every offline target works and the atlas builds normally.

## Inconclusive, not failed

The networked checks here already distinguish "the links drifted" (exit 1) from
"the site could not be asked" (exit 2). A missing rivulet is the second kind:
it says nothing about whether anything drifted, so it must never be reported as
a failure.

    0   it worked
    1   it ran and failed
    2   the machinery is not installed, or the site could not be asked
"""

import sys

EXIT_NOT_INSTALLED = 2

_MISSING = """\
acquisition machinery not installed.

Fetching and the networked checks live in the private `rivulet` package, which
is not present in this environment. Everything that reads the existing cache
still runs: `make parse-metadata`, `make build`, `make count-sizes`,
`make audit` and `make serve` are unaffected.

To enable it:  pip install -e ../../rivulet
"""


def _load(dotted: str, name: str):
    """Import `name` from a rivulet module, or exit 2 if the package is absent.

    Imported at the point of use rather than at module load, so that merely
    importing this shim never depends on rivulet being installed.
    """
    try:
        module = __import__(dotted, fromlist=[name])
    except ImportError:
        print(_MISSING, file=sys.stderr)
        raise SystemExit(EXIT_NOT_INSTALLED)
    return getattr(module, name)


def clearance_main():
    # The EBS-specific CLI, not the site-agnostic library beside it: the
    # library takes site_root and the profile dir as parameters, and this is
    # what fills them in from the Atlas's config.
    return _load("rivulet.extract.ebharatisampat.clearance_cli", "main")


def fetch_metadata_main():
    return _load("rivulet.extract.ebharatisampat.fetch_metadata", "main")


def fetch_text_main():
    return _load("rivulet.extract.ebharatisampat.fetch_fulltext", "main")


def check_source_links_main():
    return _load("rivulet.verify.ebharatisampat.check_source_links", "main")


def reader():
    """The shared networked page-reader, for `audit.py`'s own probing.

    Returns the module, so the caller gets `fetch`, `load_clearance` and
    `Inconclusive` together -- they are used as a set.
    """
    try:
        from rivulet.verify.ebharatisampat import reader as module
    except ImportError:
        print(_MISSING, file=sys.stderr)
        raise SystemExit(EXIT_NOT_INSTALLED)
    return module


def available() -> bool:
    """Whether networked work is possible here. Asks, rather than exits."""
    try:
        import rivulet  # noqa: F401
    except ImportError:
        return False
    return True
