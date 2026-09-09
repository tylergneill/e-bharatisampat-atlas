"""Establish session clearance for the site, and save it.

**The implementation lives in `rivulet`**, which is private; this module is a
runner so that `python -m pipeline.clearance` and the Makefile target that
wraps it keep working. See `pipeline/fetch.py` for the boundary and for what
this repo can still do without the package installed.
"""

from pipeline.fetch import clearance_main

if __name__ == "__main__":
    clearance_main()()
