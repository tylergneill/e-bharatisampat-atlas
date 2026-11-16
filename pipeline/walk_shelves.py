"""Tier 1: walk the site's three shelves (E-Books, Unicode Books, AI-converted
books) -> data/shelves_cache/<date>/.

**The implementation lives in `rivulet`**, which is private; this module is a
runner so that `python -m pipeline.walk_shelves` and the Makefile target that
wraps it work. See `pipeline/fetch.py` for the boundary.
"""

from pipeline.fetch import walk_shelves_main

if __name__ == "__main__":
    walk_shelves_main()()
