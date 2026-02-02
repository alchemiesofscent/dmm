#!/usr/bin/env python3
"""
Build a master register (long) and a master concordance (wide) from Materia Medica.xlsx.

Outputs (default to data/):
  - master_register.csv
  - master_concordance.csv
  - master_qa.md

This script avoids third-party dependencies by reading .xlsx as ZIP + SpreadsheetML XML.
"""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


NS_MAIN = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col_to_int(col: str) -> int:
    n = 0
    for c in col:
        n = n * 26 + (ord(c) - 64)
    return n


def _split_ref(cell_ref: str) -> tuple[int, int]:
    col = "".join([c for c in cell_ref if c.isalpha()])
    row = int("".join([c for c in cell_ref if c.isdigit()]))
    return _col_to_int(col), row


def _is_empty(value: str) -> bool:
    v = value.strip()
    return v == "" or v.upper() == "#N/A"


_RE_FLOAT_INT = re.compile(r"^\d+\.0+$")
_RE_WS = re.compile(r"\s+")


def normalize_scalar(value: str) -> str:
    v = value.strip()
    if v.upper() == "#N/A":
        return ""
    v = _RE_WS.sub(" ", v)
    if _RE_FLOAT_INT.match(v):
        return v.split(".", 1)[0]
    return v


def expand_chapter_key(raw: str) -> list[str]:
    v = normalize_scalar(raw)
    if _is_empty(v):
        return []
    parts = [p.strip() for p in v.split(";") if p.strip()]
    return parts if len(parts) > 1 else [v]


def _looks_like_header(row: list[str]) -> bool:
    joined = "|".join([c.lower() for c in row if c])
    return any(token in joined for token in ("dmm_id", "chapter", "scan", "teitok_id", "term"))


@dataclass(frozen=True)
class SheetRef:
    name: str
    target: str


class XlsxReader:
    def __init__(self, path: Path):
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self._shared_strings = self._load_shared_strings()
        self._sheets = self._load_sheets()

    def close(self) -> None:
        self._zip.close()

    def sheets(self) -> list[str]:
        return [s.name for s in self._sheets]

    def sheet_exists(self, name: str) -> bool:
        return any(s.name == name for s in self._sheets)

    def _load_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self._zip.namelist():
            return []
        root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        shared: list[str] = []
        for si in root.findall("m:si", NS_MAIN):
            texts = [(t.text or "") for t in si.findall(".//m:t", NS_MAIN)]
            shared.append("".join(texts))
        return shared

    def _load_sheets(self) -> list[SheetRef]:
        wb = ET.fromstring(self._zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(f"{REL_NS}Relationship")
        }

        sheets: list[SheetRef] = []
        for sh in wb.findall("m:sheets/m:sheet", NS_MAIN):
            name = sh.attrib["name"]
            rid = sh.attrib.get(R_ID)
            target = rid_to_target.get(rid, "")
            sheets.append(SheetRef(name=name, target=target))
        return sheets

    def _sheet_target(self, name: str) -> str:
        for s in self._sheets:
            if s.name == name:
                return s.target
        raise KeyError(f"Sheet not found: {name}")

    def iter_rows(self, name: str) -> Iterable[tuple[int, dict[int, str]]]:
        """
        Yield (row_index, {col_index: value}) for rows that contain at least one non-empty cell.
        col_index is 1-based.
        """
        target = self._sheet_target(name)
        xml_path = "xl/" + target.lstrip("/")
        root = ET.fromstring(self._zip.read(xml_path))

        rows: dict[int, dict[int, str]] = defaultdict(dict)
        for c in root.findall(".//m:sheetData/m:row/m:c", NS_MAIN):
            ref = c.attrib.get("r")
            if not ref:
                continue
            col, row = _split_ref(ref)

            value = ""
            cell_type = c.attrib.get("t")
            if cell_type == "inlineStr":
                t = c.find(".//m:t", NS_MAIN)
                value = t.text if t is not None and t.text is not None else ""
            else:
                v = c.find("m:v", NS_MAIN)
                if v is None or v.text is None:
                    continue
                if cell_type == "s":
                    try:
                        value = self._shared_strings[int(v.text)]
                    except Exception:
                        value = v.text
                else:
                    value = v.text

            value = normalize_scalar(str(value))
            if _is_empty(value):
                continue
            rows[row][col] = value

        for r in sorted(rows.keys()):
            yield r, rows[r]

    def read_table(self, name: str, *, header: bool | None) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
        """
        Return (headers, records) where records is a list of (row_index, {header: value}).

        If header is None, a header row is guessed.
        """
        raw_rows = list(self.iter_rows(name))
        if not raw_rows:
            return [], []

        # Determine max column used in first row to build a header candidate.
        first_row_idx, first_cells = raw_rows[0]
        max_col = max(first_cells.keys(), default=0)
        header_row = [first_cells.get(i, "") for i in range(1, max_col + 1)]

        has_header = _looks_like_header(header_row) if header is None else header
        if has_header:
            headers = [normalize_scalar(h) for h in header_row]
            data_rows = raw_rows[1:]
        else:
            headers = []
            data_rows = raw_rows

        records: list[tuple[int, dict[str, str]]] = []
        if has_header:
            for row_idx, cells in data_rows:
                rec: dict[str, str] = {}
                for col_idx, value in cells.items():
                    if col_idx <= len(headers):
                        key = headers[col_idx - 1]
                        if key:
                            rec[key] = value
                if rec:
                    records.append((row_idx, rec))
            return headers, records

        # No header: use column numbers as keys ("1", "2", ...)
        for row_idx, cells in data_rows:
            rec = {str(col_idx): value for col_idx, value in cells.items()}
            if rec:
                records.append((row_idx, rec))
        return headers, records


def _csv_write(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _unique_join(values: Iterable[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        nv = normalize_scalar(v)
        if _is_empty(nv):
            continue
        if nv not in seen:
            seen.add(nv)
            out.append(nv)
    return "; ".join(out)


def build_master(xlsx_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    reader = XlsxReader(xlsx_path)
    try:
        required = [
            "berendes",
            "berendes + moulins",
            "NEW moulins laguna",
            "NEW moulins wechel",
            "NEW moulins matthiolus",
            "berendes + ruel",
            "berendes + lusitanus",
            "berendes + barbaro",
            "gunther beck combined",
            "wellmann beck combined",
            "beck+berendes",
        ]
        missing = [s for s in required if not reader.sheet_exists(s)]
        if missing:
            raise RuntimeError(f"Missing expected sheets: {', '.join(missing)}")

        # Base: berendes (no header).
        _, ber_raw = reader.read_table("berendes", header=False)
        berendes_by_teitok: dict[str, dict[str, str]] = {}
        teitoks_by_chapter: dict[str, list[str]] = defaultdict(list)
        for row_idx, rec in ber_raw:
            teitok = normalize_scalar(rec.get("1", ""))
            chapter = normalize_scalar(rec.get("2", ""))
            term = normalize_scalar(rec.get("3", ""))
            if _is_empty(teitok) and _is_empty(chapter) and _is_empty(term):
                continue
            if teitok:
                berendes_by_teitok[teitok] = {
                    "berendes_teitok_id": teitok,
                    "berendes_chapter": chapter,
                    "berendes_term": term,
                }
            if chapter and teitok:
                teitoks_by_chapter[chapter].append(teitok)

        # Mapping: beck+berendes (header).
        _, beck_map_raw = reader.read_table("beck+berendes", header=None)
        dmm_to_berendes: dict[str, dict[str, str]] = {}
        for row_idx, rec in beck_map_raw:
            dmm = normalize_scalar(rec.get("dmm_id", ""))
            if _is_empty(dmm):
                continue
            teitok = normalize_scalar(rec.get("berendes_teitok_id", ""))
            canonical = berendes_by_teitok.get(teitok, {})
            canonical_chapter = normalize_scalar(canonical.get("berendes_chapter", ""))
            canonical_term = normalize_scalar(canonical.get("berendes_term", ""))
            dmm_to_berendes[dmm] = {
                "dmm_id": dmm,
                "beck_greek_lemma": normalize_scalar(rec.get("beck_greek_lemma", "")),
                "beck_latin_lemma": normalize_scalar(rec.get("beck_latin_lemma", "")),
                "berendes_teitok_id": teitok,
                # Prefer canonical berendes chapter/term from the berendes base sheet; this
                # avoids Excel numeric-format collisions in join sheets (e.g., 1.10 -> 1.1).
                "berendes_chapter": canonical_chapter or normalize_scalar(rec.get("berendes_chapter", "")),
                "berendes_term": canonical_term or normalize_scalar(rec.get("berendes_term", "")),
            }

        register: list[dict[str, str]] = []

        def add_record(
            *,
            chapter_key: str,
            chapter_key_raw: str,
            chapter_key_source: str,
            berendes_teitok_id: str,
            dmm_id: str,
            source_id: str,
            edition: str,
            book: str = "",
            chapter: str = "",
            page: str = "",
            scan_id: str = "",
            folio: str = "",
            division: str = "",
            term: str = "",
            title: str = "",
            greek: str = "",
            latin: str = "",
            greek_text: str = "",
            notes: str = "",
            source_sheet: str = "",
            source_row: str = "",
        ) -> None:
            register.append(
                {
                    "chapter_key": chapter_key,
                    "chapter_key_raw": chapter_key_raw,
                    "chapter_key_source": chapter_key_source,
                    "berendes_teitok_id": berendes_teitok_id,
                    "dmm_id": dmm_id,
                    "source_id": source_id,
                    "edition": edition,
                    "book": book,
                    "chapter": chapter,
                    "page": page,
                    "scan_id": scan_id,
                    "folio": folio,
                    "division": division,
                    "term": term,
                    "title": title,
                    "greek": greek,
                    "latin": latin,
                    "greek_text": greek_text,
                    "notes": notes,
                    "source_sheet": source_sheet,
                    "source_row": source_row,
                }
            )

        # Edition: berendes (canonical list)
        for row_idx, rec in ber_raw:
            teitok = normalize_scalar(rec.get("1", ""))
            chapter_raw = normalize_scalar(rec.get("2", ""))
            term = normalize_scalar(rec.get("3", ""))
            keys = expand_chapter_key(chapter_raw)
            if not keys:
                continue
            for k in keys:
                add_record(
                    chapter_key=k,
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id="",
                    source_id="",
                    edition="berendes",
                    chapter=k,
                    term=term,
                    source_sheet="berendes",
                    source_row=str(row_idx),
                )

        # Edition: desmoulins (from berendes + moulins)
        _, bm = reader.read_table("berendes + moulins", header=None)
        for row_idx, rec in bm:
            teitok = normalize_scalar(rec.get("berendes_teitok_id", ""))
            chapter_raw = normalize_scalar(rec.get("berendes_chapter", ""))
            des_page = normalize_scalar(rec.get("desmoulins_page", ""))
            des_term = normalize_scalar(rec.get("desmoulins_term", ""))
            des_chapter = normalize_scalar(rec.get("desmoulins_chapter", ""))
            keys = expand_chapter_key(chapter_raw)
            if not keys:
                continue
            for k in keys:
                add_record(
                    chapter_key=k,
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id="",
                    source_id="",
                    edition="desmoulins",
                    chapter=des_chapter,
                    page=des_page,
                    term=des_term,
                    source_sheet="berendes + moulins",
                    source_row=str(row_idx),
                )

        # Edition: matthiolo (from NEW moulins matthiolus; aligns via berendes_id)
        _, nmat = reader.read_table("NEW moulins matthiolus", header=None)
        for row_idx, rec in nmat:
            source_id = normalize_scalar(rec.get("dmm_id", ""))
            chapter_raw = normalize_scalar(rec.get("berendes_id", ""))
            ber_greek = normalize_scalar(rec.get("berendes_greek", ""))
            book = normalize_scalar(rec.get("mattioli_book", ""))
            chap_roman = normalize_scalar(rec.get("mattioli_chapter_roman", ""))
            chap_decimal = normalize_scalar(rec.get("mattioli_chapter_decimal", ""))
            greek = normalize_scalar(rec.get("mattioli_greek", ""))
            latin = normalize_scalar(rec.get("mattioli_latin", ""))
            keys = expand_chapter_key(chapter_raw)
            if not keys:
                continue
            for k in keys:
                teitok_guess = ""
                teitok_list = teitoks_by_chapter.get(k, [])
                if len(teitok_list) == 1:
                    teitok_guess = teitok_list[0]
                add_record(
                    chapter_key=k,
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="berendes_id",
                    berendes_teitok_id=teitok_guess,
                    dmm_id="",
                    source_id=source_id,
                    edition="matthiolo",
                    book=book,
                    chapter=chap_decimal,
                    division=chap_roman,
                    term="",  # keep term in greek/latin fields; ber_greek is captured as greek when needed elsewhere
                    greek=greek or ber_greek,
                    latin=latin,
                    source_sheet="NEW moulins matthiolus",
                    source_row=str(row_idx),
                )

        # Edition: laguna (from NEW moulins laguna)
        _, nlag = reader.read_table("NEW moulins laguna", header=None)
        for row_idx, rec in nlag:
            source_id = normalize_scalar(rec.get("dmm_id", ""))
            dmm = source_id if source_id.startswith("DMM") else ""
            ber_raw_key = normalize_scalar(rec.get("berendes_id", ""))
            ber_greek = normalize_scalar(rec.get("berendes_greek", ""))
            scan_id = normalize_scalar(rec.get("laguna_scan_id", ""))
            book = normalize_scalar(rec.get("laguna_book", ""))
            page = normalize_scalar(rec.get("laguna_page", ""))
            chap = normalize_scalar(rec.get("laguna_chapter", ""))
            title = normalize_scalar(rec.get("laguna_title", ""))
            keys = expand_chapter_key(ber_raw_key)
            if not keys and (dmm or source_id):
                # unalignable row; keep in register anyway
                add_record(
                    chapter_key="",
                    chapter_key_raw=ber_raw_key,
                    chapter_key_source="berendes_id",
                    berendes_teitok_id="",
                    dmm_id=dmm,
                    source_id=source_id if not dmm else "",
                    edition="laguna",
                    book=book,
                    chapter=chap,
                    page=page,
                    scan_id=scan_id,
                    title=title,
                    greek=ber_greek,
                    notes="missing chapter_key",
                    source_sheet="NEW moulins laguna",
                    source_row=str(row_idx),
                )
                continue
            for k in keys:
                teitok_guess = ""
                teitok_list = teitoks_by_chapter.get(k, [])
                if len(teitok_list) == 1:
                    teitok_guess = teitok_list[0]
                add_record(
                    chapter_key=k,
                    chapter_key_raw=ber_raw_key,
                    chapter_key_source="berendes_id",
                    berendes_teitok_id=teitok_guess,
                    dmm_id=dmm,
                    source_id=source_id if not dmm else "",
                    edition="laguna",
                    book=book,
                    chapter=chap,
                    page=page,
                    scan_id=scan_id,
                    title=title,
                    greek=ber_greek,
                    source_sheet="NEW moulins laguna",
                    source_row=str(row_idx),
                )

        # Edition: wechel (from NEW moulins wechel)
        _, nwec = reader.read_table("NEW moulins wechel", header=None)
        for row_idx, rec in nwec:
            source_id = normalize_scalar(rec.get("dmm_id", ""))
            dmm = source_id if source_id.startswith("DMM") else ""
            ber_raw_key = normalize_scalar(rec.get("berendes_id", ""))
            ber_greek = normalize_scalar(rec.get("berendes_greek", ""))
            scan_id = normalize_scalar(rec.get("wechel_scan_id", ""))
            book = normalize_scalar(rec.get("wechel_book", ""))
            page = normalize_scalar(rec.get("wechel_page", ""))
            title = normalize_scalar(rec.get("wechel_title", ""))
            chap = normalize_scalar(rec.get("wechel_chapter", ""))
            keys = expand_chapter_key(ber_raw_key)
            if not keys and (dmm or source_id):
                add_record(
                    chapter_key="",
                    chapter_key_raw=ber_raw_key,
                    chapter_key_source="berendes_id",
                    berendes_teitok_id="",
                    dmm_id=dmm,
                    source_id=source_id if not dmm else "",
                    edition="wechel",
                    book=book,
                    chapter=chap,
                    page=page,
                    scan_id=scan_id,
                    title=title,
                    greek=ber_greek,
                    notes="missing chapter_key",
                    source_sheet="NEW moulins wechel",
                    source_row=str(row_idx),
                )
                continue
            for k in keys:
                teitok_guess = ""
                teitok_list = teitoks_by_chapter.get(k, [])
                if len(teitok_list) == 1:
                    teitok_guess = teitok_list[0]
                add_record(
                    chapter_key=k,
                    chapter_key_raw=ber_raw_key,
                    chapter_key_source="berendes_id",
                    berendes_teitok_id=teitok_guess,
                    dmm_id=dmm,
                    source_id=source_id if not dmm else "",
                    edition="wechel",
                    book=book,
                    chapter=chap,
                    page=page,
                    scan_id=scan_id,
                    title=title,
                    greek=ber_greek,
                    source_sheet="NEW moulins wechel",
                    source_row=str(row_idx),
                )

        # Edition: ruel (from berendes + ruel)
        _, bruel = reader.read_table("berendes + ruel", header=None)
        for row_idx, rec in bruel:
            teitok = normalize_scalar(rec.get("berendes_teitok_id", ""))
            chapter_raw = normalize_scalar(rec.get("berendes_chapter", ""))
            page_scan = normalize_scalar(rec.get("ruel_page_scan", ""))
            book = normalize_scalar(rec.get("ruel_book", ""))
            chap = normalize_scalar(rec.get("ruel_chapter", ""))
            title_lat = normalize_scalar(rec.get("ruel_title_latin", ""))
            folio = normalize_scalar(rec.get("ruel_folio", ""))
            title_ver = normalize_scalar(rec.get("ruel_title_vernacular", ""))
            keys = expand_chapter_key(chapter_raw)
            if not keys:
                continue
            for k in keys:
                add_record(
                    chapter_key=k,
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id="",
                    source_id="",
                    edition="ruel",
                    book=book,
                    chapter=chap,
                    page=page_scan,
                    folio=folio,
                    title=title_lat,
                    term=title_ver,
                    source_sheet="berendes + ruel",
                    source_row=str(row_idx),
                )

        # Edition: lusitanus (from berendes + lusitanus)
        _, blus = reader.read_table("berendes + lusitanus", header=None)
        for row_idx, rec in blus:
            teitok = normalize_scalar(rec.get("berendes_teitok_id", ""))
            chapter_raw = normalize_scalar(rec.get("berendes_chapter", ""))
            page = normalize_scalar(rec.get("lusitanus_page", ""))
            title = normalize_scalar(rec.get("lusitanus_title", ""))
            chap = normalize_scalar(rec.get("lusitanus_chapter", ""))
            keys = expand_chapter_key(chapter_raw)
            if not keys:
                continue
            for k in keys:
                add_record(
                    chapter_key=k,
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id="",
                    source_id="",
                    edition="lusitanus",
                    chapter=chap,
                    page=page,
                    title=title,
                    source_sheet="berendes + lusitanus",
                    source_row=str(row_idx),
                )

        # Edition: barbaro (from berendes + barbaro)
        _, bbar = reader.read_table("berendes + barbaro", header=None)
        for row_idx, rec in bbar:
            teitok = normalize_scalar(rec.get("berendes_teitok_id", ""))
            chapter_raw = normalize_scalar(rec.get("berendes_chapter", ""))
            page = normalize_scalar(rec.get("barbaro_page", ""))
            chap = normalize_scalar(rec.get("barbaro_chapter", ""))
            term = normalize_scalar(rec.get("barbaro_term", ""))
            book = normalize_scalar(rec.get("barbaro_book", ""))
            keys = expand_chapter_key(chapter_raw)
            if not keys:
                continue
            for k in keys:
                add_record(
                    chapter_key=k,
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id="",
                    source_id="",
                    edition="barbaro",
                    book=book,
                    chapter=chap,
                    page=page,
                    term=term,
                    source_sheet="berendes + barbaro",
                    source_row=str(row_idx),
                )

        # Edition: gunther (from gunther beck combined)
        _, gcb = reader.read_table("gunther beck combined", header=None)
        for row_idx, rec in gcb:
            dmm = normalize_scalar(rec.get("dmm_id", ""))
            teitok = normalize_scalar(rec.get("berendes_teitok_id", ""))
            chapter_raw = normalize_scalar(rec.get("berendes_chapter", ""))
            gun_ch = normalize_scalar(rec.get("gunther_chapter", ""))
            gun_div = normalize_scalar(rec.get("gunther_division", ""))
            gun_term = normalize_scalar(rec.get("gunther_term", ""))
            keys = expand_chapter_key(chapter_raw)
            if not keys and dmm:
                # Try mapping through dmm_id
                mapped = dmm_to_berendes.get(dmm, {})
                chapter_raw = normalize_scalar(mapped.get("berendes_chapter", ""))
                keys = expand_chapter_key(chapter_raw)
                if mapped.get("berendes_teitok_id") and _is_empty(teitok):
                    teitok = normalize_scalar(mapped.get("berendes_teitok_id", ""))
            if not keys:
                add_record(
                    chapter_key="",
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id=dmm,
                    source_id="",
                    edition="gunther",
                    chapter=gun_ch,
                    division=gun_div,
                    term=gun_term,
                    notes="missing chapter_key",
                    source_sheet="gunther beck combined",
                    source_row=str(row_idx),
                )
                continue
            for k in keys:
                add_record(
                    chapter_key=k,
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id=dmm,
                    source_id="",
                    edition="gunther",
                    chapter=gun_ch,
                    division=gun_div,
                    term=gun_term,
                    source_sheet="gunther beck combined",
                    source_row=str(row_idx),
                )

        # Edition: wellmann (from wellmann beck combined via dmm_id -> berendes chapter)
        _, wbc = reader.read_table("wellmann beck combined", header=None)
        for row_idx, rec in wbc:
            dmm = normalize_scalar(rec.get("dmm_id", ""))
            lemma = normalize_scalar(rec.get("term_greek_lemma", ""))
            w_id = normalize_scalar(rec.get("wellmann_id", ""))
            w_book = normalize_scalar(rec.get("wellmann_book", ""))
            w_ch = normalize_scalar(rec.get("wellmann_chapter", ""))
            w_txt = normalize_scalar(rec.get("wellmann_greek_text", ""))
            mapped = dmm_to_berendes.get(dmm, {})
            chapter_raw = normalize_scalar(mapped.get("berendes_chapter", ""))
            teitok = normalize_scalar(mapped.get("berendes_teitok_id", ""))
            keys = expand_chapter_key(chapter_raw)
            if not keys:
                add_record(
                    chapter_key="",
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="dmm_id->berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id=dmm,
                    source_id="",
                    edition="wellmann",
                    book=w_book,
                    chapter=w_ch,
                    term=w_id,
                    greek=lemma,
                    greek_text=w_txt,
                    notes="missing chapter_key",
                    source_sheet="wellmann beck combined",
                    source_row=str(row_idx),
                )
                continue
            for k in keys:
                add_record(
                    chapter_key=k,
                    chapter_key_raw=chapter_raw,
                    chapter_key_source="dmm_id->berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id=dmm,
                    source_id="",
                    edition="wellmann",
                    book=w_book,
                    chapter=w_ch,
                    term=w_id,
                    greek=lemma,
                    greek_text=w_txt,
                    source_sheet="wellmann beck combined",
                    source_row=str(row_idx),
                )

        # Edition: beck (from beck+berendes; already has berendes_chapter)
        for row_idx, rec in beck_map_raw:
            dmm = normalize_scalar(rec.get("dmm_id", ""))
            teitok = normalize_scalar(rec.get("berendes_teitok_id", ""))
            canonical = berendes_by_teitok.get(teitok, {})
            bchap = normalize_scalar(canonical.get("berendes_chapter", "")) or normalize_scalar(
                rec.get("berendes_chapter", "")
            )
            greek = normalize_scalar(rec.get("beck_greek_lemma", ""))
            latin = normalize_scalar(rec.get("beck_latin_lemma", ""))
            keys = expand_chapter_key(bchap)
            if not keys:
                add_record(
                    chapter_key="",
                    chapter_key_raw=bchap,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id=dmm,
                    source_id="",
                    edition="beck",
                    greek=greek,
                    latin=latin,
                    notes="missing chapter_key",
                    source_sheet="beck+berendes",
                    source_row=str(row_idx),
                )
                continue
            for k in keys:
                add_record(
                    chapter_key=k,
                    chapter_key_raw=bchap,
                    chapter_key_source="berendes_chapter",
                    berendes_teitok_id=teitok,
                    dmm_id=dmm,
                    source_id="",
                    edition="beck",
                    greek=greek,
                    latin=latin,
                    source_sheet="beck+berendes",
                    source_row=str(row_idx),
                )

        # Build master concordance (wide), keyed by chapter_key.
        by_chapter: dict[str, list[dict[str, str]]] = defaultdict(list)
        for r in register:
            key = r.get("chapter_key", "")
            if key:
                by_chapter[key].append(r)

        def first_nonempty(vals: Iterable[str]) -> str:
            for v in vals:
                nv = normalize_scalar(v)
                if not _is_empty(nv):
                    return nv
            return ""

        concordance: list[dict[str, str]] = []
        for chapter_key in sorted(by_chapter.keys(), key=lambda s: (len(s), s)):
            rows = by_chapter[chapter_key]
            ber_terms = [r["term"] for r in rows if r["edition"] == "berendes"]
            ber_teitok = [r["berendes_teitok_id"] for r in rows if r["edition"] == "berendes"]
            dmm_ids = [r["dmm_id"] for r in rows if r.get("dmm_id")]
            source_ids = [r["source_id"] for r in rows if r.get("source_id")]

            def ed(edition: str, field: str) -> list[str]:
                return [r.get(field, "") for r in rows if r.get("edition") == edition]

            concordance.append(
                {
                    "chapter_key": chapter_key,
                    "berendes_teitok_id": _unique_join(ber_teitok),
                    "berendes_term": first_nonempty(ber_terms),
                    "dmm_id": _unique_join(dmm_ids),
                    "source_id": _unique_join(source_ids),
                    "desmoulins_page": _unique_join(ed("desmoulins", "page")),
                    "desmoulins_chapter": _unique_join(ed("desmoulins", "chapter")),
                    "desmoulins_term": _unique_join(ed("desmoulins", "term")),
                    "laguna_page": _unique_join(ed("laguna", "page")),
                    "laguna_chapter": _unique_join(ed("laguna", "chapter")),
                    "laguna_title": _unique_join(ed("laguna", "title")),
                    "laguna_scan_id": _unique_join(ed("laguna", "scan_id")),
                    "laguna_book": _unique_join(ed("laguna", "book")),
                    "wechel_page": _unique_join(ed("wechel", "page")),
                    "wechel_chapter": _unique_join(ed("wechel", "chapter")),
                    "wechel_title": _unique_join(ed("wechel", "title")),
                    "wechel_scan_id": _unique_join(ed("wechel", "scan_id")),
                    "wechel_book": _unique_join(ed("wechel", "book")),
                    "ruel_page_scan": _unique_join(ed("ruel", "page")),
                    "ruel_folio": _unique_join(ed("ruel", "folio")),
                    "ruel_chapter": _unique_join(ed("ruel", "chapter")),
                    "ruel_title_latin": _unique_join(ed("ruel", "title")),
                    "ruel_title_vernacular": _unique_join(ed("ruel", "term")),
                    "ruel_book": _unique_join(ed("ruel", "book")),
                    "lusitanus_page": _unique_join(ed("lusitanus", "page")),
                    "lusitanus_chapter": _unique_join(ed("lusitanus", "chapter")),
                    "lusitanus_title": _unique_join(ed("lusitanus", "title")),
                    "barbaro_page": _unique_join(ed("barbaro", "page")),
                    "barbaro_chapter": _unique_join(ed("barbaro", "chapter")),
                    "barbaro_term": _unique_join(ed("barbaro", "term")),
                    "barbaro_book": _unique_join(ed("barbaro", "book")),
                    "matthiolo_book": _unique_join(ed("matthiolo", "book")),
                    "matthiolo_chapter": _unique_join(ed("matthiolo", "chapter")),
                    "matthiolo_greek": _unique_join(ed("matthiolo", "greek")),
                    "matthiolo_latin": _unique_join(ed("matthiolo", "latin")),
                    "gunther_chapter": _unique_join(ed("gunther", "chapter")),
                    "gunther_division": _unique_join(ed("gunther", "division")),
                    "gunther_term": _unique_join(ed("gunther", "term")),
                    "wellmann_id": _unique_join(ed("wellmann", "term")),
                    "wellmann_book": _unique_join(ed("wellmann", "book")),
                    "wellmann_chapter": _unique_join(ed("wellmann", "chapter")),
                    "wellmann_greek_lemma": _unique_join(ed("wellmann", "greek")),
                    "beck_greek_lemma": _unique_join(ed("beck", "greek")),
                    "beck_latin_lemma": _unique_join(ed("beck", "latin")),
                }
            )

        # QA report (counts + unalignables)
        edition_counts: dict[str, int] = defaultdict(int)
        missing_key_counts: dict[str, int] = defaultdict(int)
        for r in register:
            edition = r.get("edition", "")
            if edition:
                edition_counts[edition] += 1
                if _is_empty(r.get("chapter_key", "")):
                    missing_key_counts[edition] += 1

        qa_lines = []
        qa_lines.append(f"# Master build QA\n")
        qa_lines.append(f"- Source: `{xlsx_path.name}`")
        qa_lines.append(f"- Register rows: {len(register)}")
        qa_lines.append(f"- Concordance rows (chapter_key): {len(concordance)}\n")
        qa_lines.append("## Rows by edition")
        for ed_name in sorted(edition_counts.keys()):
            miss = missing_key_counts.get(ed_name, 0)
            qa_lines.append(f"- {ed_name}: {edition_counts[ed_name]} rows (missing chapter_key: {miss})")
        qa_lines.append("\n## Notes")
        qa_lines.append(
            "- `chapter_key_raw` preserves composite keys (e.g. `3.29;3.30`) while `chapter_key` is expanded."
        )
        qa_lines.append(
            "- `all` sheet is intentionally not used because it contains Excel numeric-format collisions (e.g., `1.10` -> `1.1`)."
        )

        return register, concordance, "\n".join(qa_lines) + "\n"
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build master register + concordance from Materia Medica.xlsx"
    )
    parser.add_argument(
        "--xlsx",
        default="Materia Medica.xlsx",
        help="Input .xlsx (default: Materia Medica.xlsx)",
    )
    parser.add_argument(
        "--out-dir",
        default="data",
        help="Output directory (default: data/)",
    )
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    out_dir = Path(args.out_dir)
    if not xlsx_path.exists():
        raise SystemExit(f"Input not found: {xlsx_path}")

    register, concordance, qa_md = build_master(xlsx_path)

    register_fields = [
        "chapter_key",
        "chapter_key_raw",
        "chapter_key_source",
        "berendes_teitok_id",
        "dmm_id",
        "source_id",
        "edition",
        "book",
        "chapter",
        "page",
        "scan_id",
        "folio",
        "division",
        "term",
        "title",
        "greek",
        "latin",
        "greek_text",
        "notes",
        "source_sheet",
        "source_row",
    ]

    concordance_fields = list(concordance[0].keys()) if concordance else ["chapter_key"]

    _csv_write(out_dir / "master_register.csv", register, register_fields)
    _csv_write(out_dir / "master_concordance.csv", concordance, concordance_fields)
    (out_dir / "master_qa.md").write_text(qa_md, encoding="utf-8")

    print(f"Wrote {len(register)} rows: {out_dir / 'master_register.csv'}")
    print(f"Wrote {len(concordance)} rows: {out_dir / 'master_concordance.csv'}")
    print(f"Wrote QA: {out_dir / 'master_qa.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
