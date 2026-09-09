"""The one place this repo mentions `rivulet`, and it never requires it.

The tier-3 fulltext walk moved to a private package. This Atlas is public and
**runs to completion without it**: `make parse-metadata`, `make build`, and
`make count-sizes` are all unaffected, because sizes are a pure function of
whatever cache is already on disk.

    fulltext cache  ->  text_sizes.jsonl  ->  tree.json

Each stage falls back to the one before. With rivulet, the cache is refreshed
and the sizes are current; without it, `count_sizes` measures whatever is
present, and `build_tree` uses an existing `text_sizes.jsonl` or builds an
unsized tree. Nothing is deleted and nothing errors.

Exit codes, so a `make` target can be told apart from a failure:

    0   it worked
    1   it ran and failed
    2   the machinery is not installed

2 is not an error to be fixed on this machine. It means "this checkout cannot
fetch fulltext, and that is a supported configuration" -- which is what keeps
`run_ladder.sh`'s `|| break` meaningful: a missing package stops the ladder
just as a cut-short rung does, and neither is confused with success.
"""

import sys

EXIT_NOT_INSTALLED = 2

_MISSING = """\
fulltext machinery not installed.

The tier-3 walk lives in the private `rivulet` package, which is not present in
this environment. Everything else in this repo runs without it:

    make parse-metadata     unaffected
    make count-sizes        measures whatever cache is on disk
    make build              uses an existing text_sizes.jsonl, or builds unsized

Nothing has been deleted and `data/text_sizes.jsonl` is untouched.

To enable it:  pip install -e ../../rivulet
"""


def load_fetcher():
    """Return rivulet's EBS fetcher `main`, or exit 2 if it is absent.

    Imported at the point of use, so that importing this module -- which is
    cheap and unconditional -- never depends on rivulet being installed.
    """
    try:
        from rivulet.extract.ebharatisampat.fetch_fulltext import main
    except ImportError:
        print(_MISSING, file=sys.stderr)
        raise SystemExit(EXIT_NOT_INSTALLED)
    return main


def available() -> bool:
    """Whether fulltext acquisition is possible here. Asks, rather than exits."""
    try:
        import rivulet  # noqa: F401
    except ImportError:
        return False
    return True


if __name__ == "__main__":
    load_fetcher()()
