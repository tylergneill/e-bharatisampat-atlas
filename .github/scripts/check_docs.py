#!/usr/bin/env python3
"""Smoke-test the committed contents of docs/ before a Pages deploy.

docs/ has no build step -- whatever is committed there is what gets served --
so this is the only stage that would notice a truncated or half-written
artifact. It is deliberately shallow: it checks that the files the frontend
fetches exist, parse, and are not empty. It does NOT check that the figures in
them are right; that is what `make audit` is for, and the audit needs the
gitignored data/ that a runner does not have.

Reads only committed files. No network, no data/, no pipeline imports, so it
runs anywhere a bare python3 does.
"""

import json
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"

# The frontend fetches exactly these; a missing one is a broken page rather
# than a degraded one. Anything else under data/ is unreferenced and not
# required here.
REQUIRED_JSON = ("tree.json", "changelog.json")

VERSION_FIELDS = ("__code_version__", "__data_version__", "__content_version__")


def check_json_files(problems):
    for name in REQUIRED_JSON:
        path = DOCS / "data" / name
        if not path.exists():
            problems.append(f"docs/data/{name} is missing")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"docs/data/{name} is not valid JSON: {exc}")
            continue
        if not payload:
            problems.append(f"docs/data/{name} is empty")
            continue
        print(f"  ok   {name} parses ({path.stat().st_size:,} bytes)")


def check_version(problems):
    path = DOCS / "VERSION"
    if not path.exists():
        problems.append("docs/VERSION is missing")
        return
    found = dict(re.findall(r'^(__\w+__)\s*=\s*"([^"]*)"',
                            path.read_text(encoding="utf-8"), re.MULTILINE))
    for field in VERSION_FIELDS:
        if not found.get(field):
            problems.append(f"docs/VERSION is missing {field}")
    for field in ("__data_version__", "__content_version__"):
        value = found.get(field, "")
        if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            problems.append(
                f"docs/VERSION's {field} is {value!r}, expected YYYY-MM-DD")
    if not problems:
        print(f"  ok   VERSION: {' '.join(f'{k}={v}' for k, v in found.items())}")


def check_tree_not_empty(problems):
    """A zero count means a broken build, not a small corpus.

    No threshold beyond that: the corpus grows with every fetch, so a pinned
    figure would either mean nothing or need bumping on every run.

    The atlases do not share a tree schema -- some nest everything under a
    single `root`, others carry a flat `works` list beside named `axes` -- so
    this detects which it has rather than hardcoding one. An unrecognised
    shape is itself a failure: it means the build wrote something neither
    frontend could read.
    """
    path = DOCS / "data" / "tree.json"
    if not path.exists():
        return
    try:
        tree = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return  # already reported

    if "root" in tree:
        root = tree["root"]
        if not root.get("children"):
            problems.append("tree.json root has no children -- empty tree")
        count = root.get("stats", {}).get("text_count")
        if not isinstance(count, int) or count <= 0:
            problems.append(
                f"tree.json root stats.text_count is {count!r}, expected a positive int")
        else:
            print(f"  ok   tree.json: {count:,} texts, {len(root['children'])} branches")

    elif "works" in tree:
        works, axes = tree.get("works"), tree.get("axes") or {}
        if not works:
            problems.append("tree.json has no works -- empty build")
        if not axes:
            problems.append("tree.json has no axes -- nothing to browse by")
        count = (tree.get("all_stats") or {}).get("count")
        if not isinstance(count, int) or count <= 0:
            problems.append(
                f"tree.json all_stats.count is {count!r}, expected a positive int")
        else:
            print(f"  ok   tree.json: {count:,} works, "
                  f"axes: {', '.join(sorted(axes))}")

    else:
        problems.append(
            "tree.json has neither 'root' nor 'works' -- unrecognised schema")


def main():
    problems = []
    check_json_files(problems)
    check_version(problems)
    check_tree_not_empty(problems)

    if problems:
        print("\ndocs/ failed its pre-publish smoke test:", file=sys.stderr)
        for problem in problems:
            print(f"  FAIL {problem}", file=sys.stderr)
        return 1
    print("\ndocs/ looks publishable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
