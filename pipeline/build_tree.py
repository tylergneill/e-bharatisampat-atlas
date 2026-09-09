"""docs/data/metadata.json -> docs/data/tree.json. All 11066 works.

Byte sizes come from data/text_sizes.jsonl, written by `pipeline.count_sizes`
over the fulltext cache, and are attached to whichever works the fetch has
reached. The cache is optional and normally partial: the fetch is incremental,
so `sized` in the emitted stats says how many of the 11066 carry figures, and
the byte totals sum over exactly those. They rise as the fetch continues.

The companion `build_snapshot_tree` emits the same shape from the third-party
snapshot into `docs/data/snapshot_tree.json` -- 2287 books (21%) sized from
borrowed text. The two files are alternatives the frontend picks between,
never combined: same shape, different corpus. It goes away once this builder's
own coverage passes it.

(The snapshot's books are a strict subset -- all 2287 of its serials appear
among the 11066 -- but the two sources encode the book id differently, snapshot
decoded vs metadata base64. `serial` is the stable key if anything ever needs
to cross them.)

**The output is flat.** A list of works plus the two axes' keys -- not a nested
tree. Grouping happens in the browser, because the same works are presented
four ways (category flat, category grouped by author, author flat, author
grouped by category) and materializing four trees would be the same data under
four orderings.

The two axes are peers, neither nested inside the other:

  category  domain -> sub_domain -> works, optionally grouped by author
  author    author -> works,                optionally grouped by category

Both groupings default off; the frontend owns that toggle. Nesting author under
category -- what this builder used to do -- scatters an author across the tree
(Kalidasa's 110 works land in 7 separate domains, and authors spanning >1
domain hold 32.5% of all authored works) and has nowhere at all to put the 3888
works with no author.

Authorless works are real members of the author axis under UNKNOWN_AUTHOR, not
omitted.

Run: python -m pipeline.build_tree
"""

import argparse
import datetime
import json
from pathlib import Path

from pipeline.config import (FULLTEXT_CACHE_DIR, METADATA_PATH, TEXT_LOG_PATH,
                             TEXT_SIZES_PATH, TREE_PATH, VERSION_PATH)
from pipeline.audit import load_empty_texts
from pipeline.shape import OPTIONAL_FIELDS, SIZE_KEYS, build_axes, report, write
from pipeline.languages import parse as parse_languages


def load_sizes(path: Path) -> tuple[dict[str, dict], set[str]]:
    """(work id -> byte figures, ids whose text is empty) from the size cache.

    Keyed on `id`, the base64 form metadata.json uses -- unlike the snapshot's
    cache, whose ids are decoded and need `serial` to cross. Both keys in fact
    join cleanly here, but `id` is what this builder already carries.

    The second return value is what `pipeline.audit` reports as "Empty text
    items", and it is taken FROM that module rather than recomputed here. The
    two must agree about which works have no text -- the audit publishes the
    finding, this builder acts on it by suppressing the reader endpoint -- and
    when the rule lived in both places they drifted apart the moment one was
    corrected: on 2026-09-07 the audit stopped calling a work empty for holding
    no Devanagari, and this file went on suppressing 63 works when the audit
    reported 28. The 35 in between were books with real text in romanized
    Sanskrit, English, or a pre-Unicode font encoding, whose text links this
    builder was hiding.
    """
    sizes = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        # A later row supersedes an earlier one: text_sizes.jsonl is appended
        # to, so a refetched work has several and only the last is current.
        sizes[row["id"]] = {k: row[k] for k in SIZE_KEYS if k in row}

    # The empty set is the audit's, including its reading of the journal for
    # works whose fetch returned nothing and so have no size row at all.
    empty = load_empty_texts(path)
    return sizes, empty


def load_has_text(cache: Path, log_path: Path = TEXT_LOG_PATH) -> set[int] | None:
    """Serials whose plain text is on disk right now, or None if unknowable.

    **Presence, not measurement.** The journal names the cache file for each
    serial -- filenames embed a transliterated title and cannot be
    reconstructed -- so this reads the journal for names and then asks the
    filesystem which of them are actually here.

    None means "no cache directory": the flag is then omitted from every work
    rather than published as False everywhere, because those are different
    claims. False for a specific work says the text is absent; a missing flag
    says this build could not tell. A public checkout with no `data/` is the
    latter, and must not be read as an authoritative "no text exists".
    """
    if not cache.is_dir() or not log_path.exists():
        return None
    present = set()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue  # torn final line from a hard kill
        name, serial = entry.get("file"), entry.get("serial")
        if name and serial is not None and (cache / name).exists():
            present.add(serial)
    return present


def work_from_metadata(record: dict, sizes: dict[str, dict],
                       empty: set[str] = frozenset(),
                       has_text: set[int] | None = None) -> dict:
    """One metadata.json record -> one work.

    `text` keeps the reader endpoint name rather than a boolean, because
    `read_chapter` means the site paginates the work by chapter -- i.e. a table
    of contents exists -- while `readbook3` means one flat text.

    `sizes` is attached for whatever the fetcher has measured so far, and is
    absent on the rest. The fetch is incremental, so a partial cache is the
    normal state, not an error: `shape.build_axes` records how many works came
    out sized, and the byte totals are honest sums over exactly those.

    A work in `empty` is published WITHOUT its text: no reader endpoint, no
    byte figures. The Atlas must not offer a text link that opens onto nothing,
    and it must not count such a work as text-bearing -- so the suppression
    happens here, where the work is built, and every axis, total and badge
    downstream follows from it rather than each having to know the rule.

    Their byte figures are dropped along with the endpoint, because those are
    what make an empty text look real: one of these measures 3 KB, all of it
    page furniture. The entry itself stays -- it is a real catalogued work, and
    most carry a perfectly good PDF -- it simply stops claiming a text.
    """
    work = {
        "id": record["id"],
        "serial": record["serial"],
        "title": record["title"],
        "domain": record["domain"],
        "sub_domain": record.get("sub_domain"),
        "author": record.get("author"),
        "language": record.get("language"),
        "languages": sorted(parse_languages(record.get("language") or "")),
        "text": None if record["id"] in empty else record.get("text"),
        "pdf": bool(record.get("pdf")),
        "uploaded": record.get("uploaded"),
        # When the item actually arrived. Equal to `uploaded` except for the
        # ~200 records whose stamp runs far past their serial neighborhood,
        # where it is interpolated from that neighborhood instead -- graph
        # this, not `uploaded`, or those land in the wrong month.
        "added": record.get("added"),
    }
    if record.get("added_synthetic"):
        work["added_synthetic"] = True
    for key in OPTIONAL_FIELDS:
        if record.get(key):
            work[key] = record[key]
    if record["id"] not in empty:
        if measured := sizes.get(record["id"]):
            work["sizes"] = measured
        # Whether a plain-text file for this work exists on THIS machine.
        #
        # Published so that Sagarasangama can render a text link without
        # reading any Atlas's `data/` -- CONTRACT.md holds unchanged, and the
        # consumer needs one boolean rather than a second directory to stat.
        #
        # Derived from cache presence, not from `sizes`: a work can be measured
        # (its bytes recorded in a `text_sizes.jsonl` carried between machines)
        # while its text is not here, and offering a link to that is exactly
        # the dead link this flag exists to prevent. False is the honest answer
        # on a checkout without the cache, and the default everywhere.
        if has_text is not None and record["serial"] in has_text:
            work["has_text"] = True
    return work


def stamp_version(log_path: Path, version_path: Path, tree_path: Path) -> str | None:
    """Write when the corpus was fetched into docs/VERSION.

    `__content_version__` is the date the newest book in the corpus was
    fetched, read from the fetch journal -- the scrape records its own date, so
    nothing here needs maintaining by hand. It sat at "2026-07-08" while the
    newest fetch was 2026-08-17, because it was hand-maintained: nothing writes
    to a file only humans update, and a stale date is plausible enough to skim
    past.

    `__data_version__` is today: when the pipeline last ran.

    Only stamped for the real track. `build_snapshot_tree` writes its own file
    and must never relabel the site's currency with the borrowed snapshot's.
    """
    if tree_path != TREE_PATH or not log_path.exists():
        return None
    newest = ""
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            fetched = json.loads(line).get("fetched_at") or ""
            if fetched > newest:
                newest = fetched
    if not newest:
        return None
    content = newest[:10]

    fields = {}
    if version_path.exists():
        for line in version_path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                fields[key.strip()] = value.strip().strip("\"'")
    fields["__data_version__"] = datetime.date.today().isoformat()
    fields["__content_version__"] = content
    fields.setdefault("__code_version__", "0.1.0")

    version_path.write_text("".join(
        f'{k} = "{v}"\n' for k, v in (
            ("__code_version__", fields["__code_version__"]),
            ("__data_version__", fields["__data_version__"]),
            ("__content_version__", fields["__content_version__"]))),
        encoding="utf-8")
    return content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH)
    parser.add_argument("--sizes", type=Path, default=TEXT_SIZES_PATH)
    parser.add_argument("--out", type=Path, default=TREE_PATH)
    parser.add_argument("--cache", type=Path, default=FULLTEXT_CACHE_DIR,
                        help="fulltext cache, read ONLY to set each work's "
                             "`has_text` flag from what is actually on disk. "
                             "Absent is fine: the flag is then omitted.")
    parser.add_argument("--log", type=Path, default=TEXT_LOG_PATH,
                        help="fetch journal the content date is read from")
    args = parser.parse_args()

    if not args.metadata.exists():
        print(f"missing {args.metadata}; run `make parse-metadata` first.")
        return 1

    # Optional, unlike build_snapshot_tree's hard requirement: this builder
    # predates any fetching and has to keep working with nothing measured.
    sizes, empty = load_sizes(args.sizes) if args.sizes.exists() else ({}, set())
    if empty:
        print(f"  suppressing the text of {len(empty)} works measured empty "
              f"(see `python -m pipeline.audit`)")

    # Which works have text on disk HERE. Independent of `sizes`: the sizes
    # travel between machines, the 4 GB of text does not.
    has_text = load_has_text(args.cache, args.log)
    if has_text is not None:
        print(f"  {len(has_text)} works have fulltext on disk")

    records = json.loads(args.metadata.read_text(encoding="utf-8"))
    tree = build_axes([work_from_metadata(r, sizes, empty, has_text)
                       for r in records],
                      "metadata")
    write(tree, args.out)
    report(tree, args.out)
    if stamped := stamp_version(args.log, VERSION_PATH, args.out):
        print(f"  content version: {stamped} (newest fetch)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

