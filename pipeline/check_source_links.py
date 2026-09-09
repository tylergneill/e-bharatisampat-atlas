"""Are the shipped source links still pointing at what we claim?

**The implementation lives in `rivulet`**, which is private; this module is a
runner so that `python -m pipeline.check_source_links` and the Makefile target that
wraps it keep working. See `pipeline/fetch.py` for the boundary and for what
this repo can still do without the package installed.
"""

from pipeline.fetch import check_source_links_main

if __name__ == "__main__":
    check_source_links_main()()
