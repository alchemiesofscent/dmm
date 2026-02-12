#!/usr/bin/env python3
"""Build data/vnext/citations.csv from revised_ed/*.tsv.

Deterministic, stdlib-only.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


CITATIONS_HEADER = [
    "edition_id",
    "citation_ref",
    "source_file",
    "source_row",
    "book_label",
    "book_num",
    "chapter_label",
    "chapter_num",
    "page_label",
    "scan_id",
    "iiif_key",
    "headword",
    "headword_greek",
    "headword_latin",
    "headword_english",
    "notes",
    "extra_json",
]


ROMAN_RE = re.compile(r"\b[IVXLCDM]+\b", re.IGNORECASE)


@dataclass
class SourceConfig:
    edition_id: str
    header_mode: str  # normal | space_header | no_header
    headers: Optional[List[str]]
    column_map: Dict[str, str]
    citation_ref_source: Optional[str] = None
    skip: bool = False


SOURCE_CONFIGS: Dict[str, SourceConfig] = {
    "barbaro.tsv": SourceConfig(
        edition_id="barbaro",
        header_mode="normal",
        headers=None,
        column_map={
            "barbaro_iiif": "iiif_key",
            "barbaro_page": "page_label",
            "barbaro_term": "headword",
            "barbaro_chapter": "chapter_label",
        },
    ),
    "beck.tsv": SourceConfig(
        edition_id="beck",
        header_mode="space_header",
        headers=None,
        column_map={
            "beck_id": "citation_ref",
            "beck_greek_name": "headword_greek",
            "beck_english_name": "headword_english",
        },
        citation_ref_source="beck_id",
    ),
    "berendes.tsv": SourceConfig(
        edition_id="berendes",
        header_mode="normal",
        headers=None,
        column_map={
            "berendes_book.chapter": "citation_ref",
            "berendes_name": "headword",
        },
        citation_ref_source="berendes_book.chapter",
    ),
    "editions_table.tsv": SourceConfig(
        edition_id="editions_table",
        header_mode="normal",
        headers=None,
        column_map={},
        skip=True,
    ),
    "gunther.tsv": SourceConfig(
        edition_id="gunther",
        header_mode="normal",
        headers=None,
        column_map={
            "book": "book_num",
            "chapter": "chapter_num",
            "chapter_title": "headword",
            "chapter_description": "notes",
        },
    ),
    "laguna.tsv": SourceConfig(
        edition_id="laguna",
        header_mode="normal",
        headers=None,
        column_map={
            "laguna_scan_id": "scan_id",
            "laguna_book": "book_label",
            "laguna_page": "page_label",
            "laguna_chapter": "chapter_label",
            "laguna_title": "headword",
            "laguna_iiif": "iiif_key",
        },
    ),
    "lusitanus.tsv": SourceConfig(
        edition_id="lusitanus",
        header_mode="normal",
        headers=None,
        column_map={
            "lusitanus_iiif": "iiif_key",
            "lusitanus_entry": "headword",
            "lusitanus_chapter": "chapter_label",
        },
    ),
    "matthioli.tsv": SourceConfig(
        edition_id="matthioli",
        header_mode="normal",
        headers=None,
        column_map={
            "mattioli_chapter": "chapter_label",
            "mattioli_book": "book_num",
            "mattioli_greek": "headword_greek",
            "mattioli_latin": "headword_latin",
        },
    ),
    "moulins.tsv": SourceConfig(
        edition_id="desmoulins",
        header_mode="normal",
        headers=None,
        column_map={
            "desmoulins_page": "page_label",
            "desmoulins_term": "headword",
            "desmoulins_book": "book_num",
            "desmoulins_chapter": "chapter_label",
        },
    ),
    "ruel.tsv": SourceConfig(
        edition_id="ruellius",
        header_mode="normal",
        headers=None,
        column_map={
            "ruel_web": "extra_json",
            "ruel_book": "book_label",
            "ruel_page": "page_label",
            "ruel_chapter": "chapter_label",
            "ruel_entry": "headword",
        },
    ),
    "wechel.tsv": SourceConfig(
        edition_id="wechel",
        header_mode="normal",
        headers=None,
        column_map={
            "wechel_scan_id": "scan_id",
            "wechel_book": "book_label",
            "wechel_page": "page_label",
            "wechel_title": "headword",
            "wechel_chapter": "chapter_label",
        },
    ),
    "wellmann.tsv": SourceConfig(
        edition_id="wellmann",
        header_mode="no_header",
        headers=["book_num", "chapter_num", "headword_greek"],
        column_map={
            "book_num": "book_num",
            "chapter_num": "chapter_num",
            "headword_greek": "headword_greek",
        },
    ),
}


def normalize_ref_component(value: str) -> str:
    cleaned = re.sub(r"\s+", "_", value.strip())
    cleaned = cleaned.replace("|", "/")
    return cleaned


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if v.isdigit():
        try:
            return int(v)
        except ValueError:
            return None
    return None


def parse_roman(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    v = value.strip().upper()
    if not v:
        return None
    # Strip common prefixes like "CAP." or "CHAP."
    v = re.sub(r"^(CAP\.?|CHAP\.?|CAPIT\.?|CAPITUL\.?|LIB\.?|LIBER)\s+", "", v)
    match = ROMAN_RE.search(v)
    if not match:
        return None
    roman = match.group(0)
    if roman == "IIII":
        return 4
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(roman):
        val = values.get(ch)
        if val is None:
            return None
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total


def page_label_sort_key(label: Optional[str]) -> Tuple[int, int, int, str]:
    if not label:
        return (2, 0, 0, "")
    v = label.strip().lower()
    if v.isdigit():
        return (0, int(v), 0, v)
    m = re.match(r"^(\d+)([rv])$", v)
    if m:
        num = int(m.group(1))
        side = 0 if m.group(2) == "r" else 1
        return (1, num, side, v)
    return (2, 0, 0, v)


def build_citation_ref(row: Dict[str, Optional[str]], source_row: int) -> str:
    if row.get("citation_ref"):
        return row["citation_ref"] or ""
    components: List[str] = []
    book_num = row.get("book_num")
    book_label = row.get("book_label")
    chapter_num = row.get("chapter_num")
    chapter_label = row.get("chapter_label")
    page_label = row.get("page_label")
    scan_id = row.get("scan_id")
    iiif_key = row.get("iiif_key")
    headword = row.get("headword")

    if book_num:
        components.append(f"b{normalize_ref_component(str(book_num))}")
    elif book_label:
        components.append(f"b{normalize_ref_component(book_label)}")

    if chapter_num:
        components.append(f"c{normalize_ref_component(str(chapter_num))}")
    elif chapter_label:
        components.append(f"c{normalize_ref_component(chapter_label)}")

    if page_label:
        components.append(f"p{normalize_ref_component(page_label)}")
    if scan_id:
        components.append(f"s{normalize_ref_component(scan_id)}")
    if iiif_key:
        components.append(f"i{normalize_ref_component(iiif_key)}")
    if not components and headword:
        components.append(f"h{normalize_ref_component(headword)}")
    if not components:
        components.append(f"row{source_row}")
    return "|".join(components)


def read_tsv_rows(path: Path, config: SourceConfig) -> Iterable[Tuple[Dict[str, str], int]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        if config.header_mode == "space_header":
            header_line = f.readline()
            if not header_line:
                return
            headers = header_line.strip().split()
            reader = csv.reader(f, delimiter="\t")
            row_num = 1
            for row in reader:
                row_num += 1
                if not row:
                    continue
                data = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                yield data, row_num
            return

        if config.header_mode == "no_header":
            headers = config.headers or []
            reader = csv.reader(f, delimiter="\t")
            row_num = 0
            for row in reader:
                row_num += 1
                if not row:
                    continue
                data = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                yield data, row_num
            return

        # normal header
        reader = csv.DictReader(f, delimiter="\t")
        row_num = 1
        for row in reader:
            row_num += 1
            if not row:
                continue
            yield row, row_num


def normalize_row(
    raw_row: Dict[str, str],
    source_row: int,
    source_file: str,
    config: SourceConfig,
) -> Dict[str, Optional[str]]:
    row: Dict[str, Optional[str]] = {k: None for k in CITATIONS_HEADER}
    row["edition_id"] = config.edition_id
    row["source_file"] = source_file
    row["source_row"] = str(source_row)

    extra: Dict[str, str] = {}

    for src_key, value in raw_row.items():
        if value is None:
            continue
        value = value.strip()
        if src_key in config.column_map:
            target = config.column_map[src_key]
            if target == "extra_json":
                if value:
                    extra[src_key] = value
                continue
            if target in ("book_num", "chapter_num"):
                num = parse_int(value)
                row[target] = str(num) if num is not None else value or None
            else:
                row[target] = value or None
        else:
            if value:
                extra[src_key] = value

    # Derive book/chapter numbers from labels when possible
    if not row.get("book_num") and row.get("book_label"):
        parsed = parse_int(row.get("book_label"))
        if parsed is None:
            parsed = parse_roman(row.get("book_label"))
        if parsed is not None:
            row["book_num"] = str(parsed)
    if not row.get("chapter_num") and row.get("chapter_label"):
        parsed = parse_int(row.get("chapter_label"))
        if parsed is None:
            parsed = parse_roman(row.get("chapter_label"))
        if parsed is not None:
            row["chapter_num"] = str(parsed)

    # Special parsing for berendes citation_ref (book.chapter)
    if config.citation_ref_source == "berendes_book.chapter":
        ref = row.get("citation_ref") or ""
        if ref:
            parts = ref.split(".")
            if len(parts) == 2:
                book = parse_int(parts[0])
                chapter = parse_int(parts[1])
                if book is not None:
                    row["book_num"] = str(book)
                if chapter is not None:
                    row["chapter_num"] = str(chapter)

    # Build citation_ref if missing
    row["citation_ref"] = build_citation_ref(row, source_row)

    if extra:
        row["extra_json"] = json.dumps(extra, sort_keys=True, separators=(",", ":"))

    return row


def resolve_citation_ref_collisions(rows: List[Dict[str, Optional[str]]]) -> None:
    by_key: Dict[Tuple[str, str], List[Dict[str, Optional[str]]]] = {}
    for row in rows:
        edition_id = row.get("edition_id") or ""
        citation_ref = row.get("citation_ref") or ""
        by_key.setdefault((edition_id, citation_ref), []).append(row)

    for (edition_id, base_ref), group in by_key.items():
        if len(group) <= 1:
            continue
        for row in group:
            source_row = row.get("source_row") or ""
            resolved = f"{base_ref}-r{source_row}"
            row["citation_ref"] = resolved
            extra = {}
            if row.get("extra_json"):
                try:
                    extra = json.loads(row["extra_json"])
                except json.JSONDecodeError:
                    extra = {"_extra_json_parse_error": row["extra_json"]}
            extra["citation_ref_collision"] = {"base": base_ref, "resolved": resolved}
            row["extra_json"] = json.dumps(extra, sort_keys=True, separators=(",", ":"))


def sort_key(row: Dict[str, Optional[str]]) -> Tuple:
    def none_last(value: Optional[str]) -> Tuple[int, str]:
        if value is None or value == "":
            return (1, "")
        return (0, value)

    def none_last_num(value: Optional[str]) -> Tuple[int, int]:
        if value is None or value == "":
            return (1, 0)
        try:
            return (0, int(value))
        except ValueError:
            return (0, 0)

    return (
        row.get("edition_id") or "",
        none_last_num(row.get("book_num")),
        none_last(row.get("book_label")),
        none_last_num(row.get("chapter_num")),
        none_last(row.get("chapter_label")),
        page_label_sort_key(row.get("page_label")),
        row.get("citation_ref") or "",
        int(row.get("source_row") or 0),
    )


def write_csv(path: Path, rows: List[Dict[str, Optional[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(CITATIONS_HEADER)
        for row in rows:
            writer.writerow([
                row.get("edition_id") or "",
                row.get("citation_ref") or "",
                row.get("source_file") or "",
                row.get("source_row") or "",
                row.get("book_label") or "",
                row.get("book_num") or "",
                row.get("chapter_label") or "",
                row.get("chapter_num") or "",
                row.get("page_label") or "",
                row.get("scan_id") or "",
                row.get("iiif_key") or "",
                row.get("headword") or "",
                row.get("headword_greek") or "",
                row.get("headword_latin") or "",
                row.get("headword_english") or "",
                row.get("notes") or "",
                row.get("extra_json") or "",
            ])


def build_citations(revised_ed_dir: Path) -> List[Dict[str, Optional[str]]]:
    rows: List[Dict[str, Optional[str]]] = []
    for path in sorted(revised_ed_dir.glob("*.tsv")):
        config = SOURCE_CONFIGS.get(path.name)
        if config is None:
            config = SourceConfig(
                edition_id=path.stem,
                header_mode="normal",
                headers=None,
                column_map={},
            )
        if config.skip:
            continue
        source_file = f"revised_ed/{path.name}"
        for raw_row, row_num in read_tsv_rows(path, config):
            row = normalize_row(raw_row, row_num, source_file, config)
            rows.append(row)

    resolve_citation_ref_collisions(rows)
    rows.sort(key=sort_key)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/vnext/citations.csv from revised_ed/*.tsv")
    parser.add_argument("--revised-ed-dir", default="revised_ed", help="Input directory for revised_ed TSVs")
    parser.add_argument("--out-dir", default="data/vnext", help="Output directory")
    args = parser.parse_args()

    revised_ed_dir = Path(args.revised_ed_dir)
    out_dir = Path(args.out_dir)

    rows = build_citations(revised_ed_dir)
    write_csv(out_dir / "citations.csv", rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
