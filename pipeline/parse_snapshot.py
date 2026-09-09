"""Stage 1: snapshot -> data/snapshot_inventory.jsonl (one record per book, no network).

Reads the ebhAratI-sampat snapshot's per-book markdown files and extracts their
TOML-ish frontmatter into normalized records.

Deliberately keys the hierarchy off frontmatter (`domain` / `sub-domain` /
`author`) rather than off directory layout. Those fields are 100% populated
across all 2287 books and are what our own scrape would yield too, whereas the
on-disk nesting encodes the upstream author's filing decisions -- which this
project does not intend to inherit. The on-disk path is recorded anyway, purely
so the two can be compared (see --report).

Run: python -m pipeline.parse_snapshot
"""

import argparse
import base64
import json
import re
from collections import Counter
from pathlib import Path

from pipeline.config import INVENTORY_PATH, snapshot_root
from pipeline.languages import is_sanskrit
from pipeline.languages import parse as parse_languages
from pipeline.languages import unknown_tokens as unknown_language_tokens

# Frontmatter is delimited by +++ lines. Keys are bare (title, domain) or
# double-quoted when they contain spaces/periods ("books contributor",
# "serial no.", "publish year") -- so a naive split on "=" mis-parses them.
FRONTMATTER_RE = re.compile(r"\A\+\+\+\s*\n(.*?)\n\+\+\+", re.S)
KEY_VALUE_RE = re.compile(r'^\s*(?:"([^"]+)"|([^"=\s][^=]*?))\s*=\s*"(.*)"\s*$')

# The six fields present on every content file; anything missing one is a
# parse failure worth surfacing rather than silently dropping.
REQUIRED_FIELDS = ("title", "domain", "sub-domain", "language", "serial no.", "source_url")

SERIAL_RE = re.compile(r"Ebharati-(\d+)")
BOOKID_RE = re.compile(r"[?&]bookid=([A-Za-z0-9+/=]+)")
ENDPOINT_RE = re.compile(r"\.in/([A-Za-z_0-9]+)\.php")

# 335 of the 2287 titles (all of them from the read_chapter.php code path) come
# through as: Download Text\n\t\t\t\t<actual title>, with the escapes literal.
TITLE_PREFIX_RE = re.compile(r"^\s*Download Text\s*")


def clean_title(raw: str) -> str:
    """Strip the 'Download Text' prefix and collapse literal escape sequences."""
    text = raw.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
    text = TITLE_PREFIX_RE.sub("", text)
    return " ".join(text.split()).strip()


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        kv = KEY_VALUE_RE.match(line)
        if kv:
            key = (kv.group(1) or kv.group(2)).strip()
            fields[key] = kv.group(3)
    return fields


def decode_bookid(encoded: str) -> str | None:
    """The site's ids are base64 over a numeric string, sometimes unpadded."""
    try:
        raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
    except Exception:
        return None
    value = raw.decode("utf-8", "replace").strip()
    return value if value.isdigit() else None


def body_after_frontmatter(text: str) -> str:
    match = FRONTMATTER_RE.match(text)
    return text[match.end():] if match else text


def build_record(path: Path, root: Path) -> tuple[dict | None, str | None]:
    """Return (record, error). Exactly one is non-None."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fields = parse_frontmatter(text)
    if not fields:
        return None, "no frontmatter"

    missing = [f for f in REQUIRED_FIELDS if f not in fields]
    if missing:
        return None, f"missing {', '.join(missing)}"

    source_url = fields["source_url"]
    encoded = BOOKID_RE.search(source_url)
    if not encoded:
        return None, "no bookid in source_url"

    endpoint = ENDPOINT_RE.search(source_url)
    serial = SERIAL_RE.search(fields["serial no."])
    rel = path.relative_to(root)

    record = {
        "book_id": decode_bookid(encoded.group(1)),
        "book_id_encoded": encoded.group(1),
        "serial": int(serial.group(1)) if serial else None,
        "serial_raw": fields["serial no."],
        "title": clean_title(fields["title"]),
        "domain": fields["domain"],
        "sub_domain": fields["sub-domain"],
        "author": fields.get("author"),
        "language": fields["language"],
        "source_url": source_url,
        "endpoint": endpoint.group(1) if endpoint else None,
        "path": str(rel),
        "path_depth": len(rel.parts),
        "body_bytes": len(body_after_frontmatter(text).encode("utf-8")),
        # Everything else the snapshot happens to carry, kept verbatim so the
        # tree can expose it as facets later without a reparse.
        "metadata": {
            k: v for k, v in fields.items()
            if k not in REQUIRED_FIELDS and k != "author"
        },
    }
    return record, None


def iter_content_files(root: Path):
    """Book files only: _index.md are directory labels, urls.md is the inventory."""
    for path in sorted(root.rglob("*.md")):
        if path.name in ("_index.md", "urls.md"):
            continue
        yield path


def load_urls_md(root: Path) -> set[str]:
    """Decoded ids from urls.md -- the upstream script's apparent input list."""
    path = root / "urls.md"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    ids = set()
    for encoded in re.findall(r"[?&]id=([A-Za-z0-9+/=]+)", text):
        decoded = decode_bookid(encoded)
        if decoded:
            ids.add(decoded)
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", help="override the snapshot directory")
    parser.add_argument("--out", type=Path, default=INVENTORY_PATH)
    parser.add_argument(
        "--report", action="store_true",
        help="also cross-check against urls.md and the on-disk layout",
    )
    args = parser.parse_args()

    root = snapshot_root(args.snapshot)
    if not root.is_dir():
        raise SystemExit(f"snapshot not found: {root}\nSet EBS_SNAPSHOT or pass --snapshot.")

    records, errors = [], []
    for path in iter_content_files(root):
        record, error = build_record(path, root)
        if record:
            records.append(record)
        else:
            errors.append((path.relative_to(root), error))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"snapshot:  {root}")
    print(f"books:     {len(records)}")
    print(f"errors:    {len(errors)}")
    for rel, error in errors[:10]:
        print(f"  {rel}: {error}")
    print(f"wrote:     {args.out}")

    if args.report:
        report(records, root)


def report(records: list[dict], root: Path) -> None:
    print("\n--- cross-checks ---")

    ids = {r["book_id"] for r in records if r["book_id"]}
    print(f"decoded book ids:      {len(ids)} unique / {len(records)} books")

    url_ids = load_urls_md(root)
    if url_ids:
        print(f"urls.md ids:           {len(url_ids)}")
        print(f"  books also in urls:  {len(ids & url_ids)}")
        print(f"  books NOT in urls:   {len(ids - url_ids)}")
        print(f"  urls not materialized: {len(url_ids - ids)}")

    serials = [r["serial"] for r in records if r["serial"] is not None]
    print(f"serials parsed:        {len(serials)} "
          f"(unique {len(set(serials))}, range {min(serials)}-{max(serials)})")

    # Language is free text -- one language has several spellings, and
    # multi-language values vary in word order (pipeline/languages.py). Report
    # the normalized picture, and loudly flag any token no rule recognizes:
    # an unseen spelling would otherwise just quietly shrink a total.
    langs = Counter()
    for r in records:
        for lang in parse_languages(r["language"]):
            langs[lang] += 1
    n_skt = sum(1 for r in records if is_sanskrit(r["language"]))
    print(f"languages (normalized): {len(langs)} distinct, "
          f"{len({r['language'] for r in records})} raw strings")
    print(f"  contains Sanskrit:   {n_skt} / {len(records)}")
    print("  top:                 " + ", ".join(
        f"{k}={v}" for k, v in langs.most_common(6)))
    unknown = Counter()
    for r in records:
        for tok in unknown_language_tokens(r["language"]):
            unknown[tok] += 1
    if unknown:
        print("  UNRECOGNIZED TOKENS: " + ", ".join(
            f"{t!r}x{n}" for t, n in unknown.most_common()))
        print("    -> add these to pipeline/languages.py TOKENS")

    print("endpoints:             " + ", ".join(
        f"{k}={v}" for k, v in Counter(r["endpoint"] for r in records).most_common()))
    print("path depths:           " + ", ".join(
        f"{k}={v}" for k, v in sorted(Counter(r["path_depth"] for r in records).items())))

    # The depth-3 rule: books with no author sit directly under sub-domain.
    by_depth_author = Counter(
        (r["path_depth"], bool(r["author"])) for r in records)
    print("depth x has_author:    " + ", ".join(
        f"d{d}/{'auth' if a else 'noauth'}={n}"
        for (d, a), n in sorted(by_depth_author.items())))

    # Does the frontmatter-derived hierarchy agree with the on-disk one? A
    # systematic divergence would mean the upstream filing encodes something
    # the metadata doesn't.
    mismatched = [
        r for r in records
        if r["author"] and r["path_depth"] >= 4
        and r["author"] != Path(r["path"]).parts[2]
    ]
    print(f"author != path part:   {len(mismatched)} "
          f"(expected: transliterated dir names never match Devanagari)")

    titles = Counter(r["title"] for r in records)
    dupes = sum(1 for v in titles.values() if v > 1)
    print(f"titles:                {len(titles)} unique, {dupes} duplicated "
          f"-> node ids must key on book_id, not title")


if __name__ == "__main__":
    main()
