"""Tier 2: one readSearch.php per distinct work.

**The implementation lives in `rivulet`**, which is private; this module is a
runner so that `python -m pipeline.fetch_metadata` and the Makefile target that
wraps it keep working. See `pipeline/fetch.py` for the boundary and for what
this repo can still do without the package installed.
"""

from pipeline.fetch import fetch_metadata_main

if __name__ == "__main__":
    fetch_metadata_main()()
