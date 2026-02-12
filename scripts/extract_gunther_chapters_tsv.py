#!/usr/bin/env python3
"""
Extract Gunther chapter metadata from the TEI-ish XML.

Outputs a TSV with:
  book_number, chapter_number, chapter_title, chapter_description

This is designed to be resilient to structural issues where chapter <div>s
are missing, but the chapter heading <p> still exists, e.g.:
  <p><hi rend="bold">104.</hi>CHRUSOKOLLA.<note .../> Malachite</p>

By default it filters headings to titles that look like Gunther term headings
(almost always ALL CAPS). Use --no-title-filter if you prefer a more lenient
scan (at the cost of more false positives).

Usage:
  python3 scripts/extract_gunther_chapters_tsv.py \
    --xml "src/gunther (1).xml" \
    --out /tmp/gunther_chapters.tsv

  # Only chapters present in XML but missing from data/editions/gunther.csv
  python3 scripts/extract_gunther_chapters_tsv.py \
    --xml "src/gunther (1).xml" \
    --missing-from data/editions/gunther.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


CHAPTER_NUM_RE = re.compile(r"^\s*(\d+)\.\s*$")
HAS_ALNUM_RE = re.compile(r"[0-9A-Za-z]")


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


def has_alnum(text: str) -> bool:
    return bool(HAS_ALNUM_RE.search(text))


def is_probable_chapter_title(title: str) -> bool:
    """
    Gunther chapter titles (Greek terms) are overwhelmingly ALL CAPS.
    Use this to filter out numbered lists inside chapter prose.
    """

    title = normalize_ws(title).strip()
    if not title:
        return False

    # Allow spaces and common punctuation in transliteration.
    if re.search(r"[a-z]", title):
        return False

    return bool(re.search(r"[A-Z]", title))


def load_csv_chapter_refs(csv_path: Path) -> set[str]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "gunther_chapter" not in (reader.fieldnames or []):
            raise ValueError(
                f'Expected "gunther_chapter" column in {csv_path}, found {reader.fieldnames}'
            )
        return {row["gunther_chapter"].strip() for row in reader if row.get("gunther_chapter")}


def load_chapter_overrides_tsv(tsv_path: Path) -> dict[tuple[int, int], tuple[str, str]]:
    with tsv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        needed = {"book", "chapter", "chapter_title", "chapter_description"}
        if not reader.fieldnames or not needed.issubset(set(reader.fieldnames)):
            raise ValueError(
                f"Expected TSV columns {sorted(needed)} in {tsv_path}, found {reader.fieldnames}"
            )

        overrides: dict[tuple[int, int], tuple[str, str]] = {}
        for row in reader:
            book_raw = (row.get("book") or "").strip()
            chapter_raw = (row.get("chapter") or "").strip()
            if not book_raw.isdigit() or not chapter_raw.isdigit():
                continue

            key = (int(book_raw), int(chapter_raw))
            title = (row.get("chapter_title") or "").strip()
            desc = (row.get("chapter_description") or "").strip()
            overrides[key] = (title, desc)

        return overrides


def find_chapter_number_hi(p_elem: ET.Element) -> tuple[Optional[int], Optional[ET.Element]]:
    """
    Return (chapter_number, hi_element) if this <p> looks like a chapter heading.

    We key off <hi rend="bold">N.</hi> somewhere near the start of the paragraph.
    Some headings have a leading symbol like '°' before the <hi>, so we don't
    require the <hi> to be the first content node.
    """

    if p_elem.text and has_alnum(p_elem.text):
        return None, None

    for child in list(p_elem):
        # Notes can appear immediately after the title; they shouldn't block detection.
        # Non-textual markers (rare) can also appear before the chapter-number <hi>.
        if child.tag == "hi" and child.attrib.get("rend") == "bold":
            raw = (child.text or "").strip()
            m = CHAPTER_NUM_RE.match(raw)
            if m:
                return int(m.group(1)), child

        # If we hit substantive text before the numeric <hi>, this isn't a heading.
        if has_alnum("".join(child.itertext())):
            return None, None

    return None, None


def text_after_chapter_number(p_elem: ET.Element, number_hi: ET.Element) -> str:
    """
    Extract the text following the chapter number, skipping <note> elements.
    """

    children = list(p_elem)
    try:
        start_idx = children.index(number_hi)
    except ValueError:
        start_idx = -1

    parts: list[str] = []

    # Everything after the chapter-number <hi> starts with its tail.
    if number_hi.tail:
        parts.append(number_hi.tail)

    for child in children[start_idx + 1 :]:
        if child.tag == "note":
            if child.tail:
                parts.append(child.tail)
            continue

        parts.append("".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)

    return normalize_ws("".join(parts))


def split_title_desc(after_text: str) -> tuple[str, str]:
    """
    Split "TITLE. Desc..." into ("TITLE", "Desc...").
    If no '.' is present, treat it as title-only.
    """

    after_text = normalize_ws(after_text).strip()
    if not after_text:
        return "", ""

    if "." not in after_text:
        return after_text, ""

    title, rest = after_text.split(".", 1)
    return title.strip(), rest.strip()


def is_description_paragraph_candidate(p_elem: ET.Element) -> Optional[str]:
    """
    Some chapters have their English gloss as the next <p>, e.g.

      <p><hi rend="bold">88.</hi> STEAR ...</p>
      <p>Mutton Suet, &c.</p>

    Heuristic: accept the next <p> when it's short, non-empty, and not itself
    a chapter heading.
    """

    chapter_num, _ = find_chapter_number_hi(p_elem)
    if chapter_num is not None:
        return None

    text = normalize_ws("".join(p_elem.itertext())).strip()
    if not text:
        return None

    # Avoid accidentally capturing the first prose paragraph of the chapter.
    if len(text) > 120:
        return None

    if not has_alnum(text):
        return None

    return text


@dataclass(frozen=True)
class ChapterRow:
    book: int
    chapter: int
    title: str
    description: str

    @property
    def ref(self) -> str:
        return f"{self.book}.{self.chapter}"


def iter_gunther_chapters(xml_path: Path) -> Iterable[ChapterRow]:
    root = ET.parse(xml_path).getroot()
    parent_map = {child: parent for parent in root.iter() for child in parent}

    for book_div in root.findall('.//div[@type="book"]'):
        book_raw = (book_div.attrib.get("n") or "").strip()
        if not book_raw.isdigit():
            continue
        book = int(book_raw)

        seen_in_book: set[int] = set()
        for p in book_div.iter("p"):
            chapter_num, number_hi = find_chapter_number_hi(p)
            if chapter_num is None or number_hi is None:
                continue

            # Avoid duplicates if the same heading appears multiple times in a book.
            if chapter_num in seen_in_book:
                continue
            seen_in_book.add(chapter_num)

            after = text_after_chapter_number(p, number_hi)
            title, desc = split_title_desc(after)

            if not desc:
                parent = parent_map.get(p)
                if parent is not None:
                    siblings = list(parent)
                    try:
                        idx = siblings.index(p)
                    except ValueError:
                        idx = -1

                    if idx >= 0:
                        for sib in siblings[idx + 1 :]:
                            if sib.tag != "p":
                                # Skip over non-paragraph elements between heading and gloss (rare).
                                continue
                            candidate = is_description_paragraph_candidate(sib)
                            if candidate:
                                desc = candidate
                            break

            yield ChapterRow(
                book=book,
                chapter=chapter_num,
                title=title,
                description=desc,
            )


def write_tsv(rows: Iterable[ChapterRow], out_file) -> None:
    writer = csv.writer(out_file, delimiter="\t", lineterminator="\n")
    writer.writerow(["book", "chapter", "chapter_title", "chapter_description"])
    for row in rows:
        writer.writerow([row.book, row.chapter, row.title, row.description])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Extract Gunther book/chapter/title/description TSV from src/gunther (1).xml"
    )
    parser.add_argument("--xml", type=Path, default=Path('src') / "gunther (1).xml")
    parser.add_argument("--out", type=Path, help="Write TSV to this path (default: stdout)")
    parser.add_argument(
        "--missing-from",
        type=Path,
        help='Only output chapters missing from this CSV (expects "gunther_chapter" column)',
    )
    parser.add_argument(
        "--overrides-tsv",
        type=Path,
        help="TSV of chapter overrides keyed by (book, chapter).",
    )
    parser.add_argument(
        "--no-title-filter",
        action="store_true",
        help="Do not require ALL CAPS chapter titles (more false positives).",
    )
    args = parser.parse_args(argv)

    if not args.xml.exists():
        print(f"XML not found: {args.xml}", file=sys.stderr)
        return 2

    rows = list(iter_gunther_chapters(args.xml))

    if args.overrides_tsv:
        if not args.overrides_tsv.exists():
            print(f"Overrides TSV not found: {args.overrides_tsv}", file=sys.stderr)
            return 2
        overrides = load_chapter_overrides_tsv(args.overrides_tsv)
        applied = 0
        new_rows: list[ChapterRow] = []
        for row in rows:
            key = (row.book, row.chapter)
            if key not in overrides:
                new_rows.append(row)
                continue

            override_title, override_desc = overrides[key]
            new_rows.append(
                ChapterRow(
                    book=row.book,
                    chapter=row.chapter,
                    title=override_title or row.title,
                    description=override_desc or row.description,
                )
            )
            applied += 1

        rows = new_rows
        print(f"Applied {applied} overrides", file=sys.stderr)

    if not args.no_title_filter:
        rows = [row for row in rows if is_probable_chapter_title(row.title)]

    if args.missing_from:
        if not args.missing_from.exists():
            print(f"CSV not found: {args.missing_from}", file=sys.stderr)
            return 2
        existing = load_csv_chapter_refs(args.missing_from)
        rows = [row for row in rows if row.ref not in existing]

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="") as f:
            write_tsv(rows, f)
    else:
        write_tsv(rows, sys.stdout)

    print(f"Wrote {len(rows)} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
