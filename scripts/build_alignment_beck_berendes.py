#!/usr/bin/env python3
"""
Build a rich Beck ↔ Berendes alignment export from Materia Medica.xlsx.

Goal: support 1→N mappings (Beck entry spans multiple Berendes chapters) and provide
enough context to review/curate: book/chapter/page/title where available from other sheets.

Outputs (default to data/alignments/):
  - beck_berendes_edges.csv     (one row per Beck->Berendes relation)
  - beck_berendes_groups.csv    (one row per Beck dmm_id, aggregated)
  - beck_berendes_qa.md
  - beck_berendes_sample50.txt  (50 random edge rows, non-repeating; deterministic by seed)
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


NS_MAIN = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

_RE_WS = re.compile(r"\s+")
_RE_FLOAT_INT = re.compile(r"^\d+\.0+$")


def normalize(value: str) -> str:
    v = str(value).strip()
    if v.upper() == "#N/A":
        return ""
    v = _RE_WS.sub(" ", v)
    if _RE_FLOAT_INT.match(v):
        return v.split(".", 1)[0]
    return v


def expand_key(raw: str) -> list[str]:
    v = normalize(raw)
    if not v:
        return []
    parts = [p.strip() for p in v.split(";") if p.strip()]
    return parts if len(parts) > 1 else [v]


def berendes_book_num(chapter_key: str) -> str:
    ck = normalize(chapter_key)
    if not ck:
        return ""
    head = ck.split(".", 1)[0]
    return head if head.isdigit() else ""


def unique_join(values: Iterable[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        nv = normalize(v)
        if not nv:
            continue
        if nv not in seen:
            seen.add(nv)
            out.append(nv)
    return "; ".join(out)


def looks_like_header(row: list[str]) -> bool:
    joined = "|".join([normalize(c).lower() for c in row if c])
    return any(token in joined for token in ("dmm_id", "chapter", "scan", "teitok", "term"))


class XlsxReader:
    def __init__(self, path: Path):
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self._shared_strings = self._load_shared_strings()
        self._sheet_targets = self._load_sheet_targets()

    def close(self) -> None:
        self._zip.close()

    def sheet_exists(self, name: str) -> bool:
        return name in self._sheet_targets

    def _load_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self._zip.namelist():
            return []
        root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        shared: list[str] = []
        for si in root.findall("m:si", NS_MAIN):
            texts = [(t.text or "") for t in si.findall(".//m:t", NS_MAIN)]
            shared.append("".join(texts))
        return shared

    def _load_sheet_targets(self) -> dict[str, str]:
        wb = ET.fromstring(self._zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(f"{REL_NS}Relationship")
        }
        targets: dict[str, str] = {}
        for sh in wb.findall("m:sheets/m:sheet", NS_MAIN):
            targets[sh.attrib["name"]] = rid_to_target.get(sh.attrib.get(R_ID, ""), "")
        return targets

    @staticmethod
    def _col_to_int(col: str) -> int:
        n = 0
        for c in col:
            n = n * 26 + (ord(c) - 64)
        return n

    @classmethod
    def _split_ref(cls, cell_ref: str) -> tuple[int, int]:
        col = "".join([c for c in cell_ref if c.isalpha()])
        row = int("".join([c for c in cell_ref if c.isdigit()]))
        return cls._col_to_int(col), row

    def iter_rows(self, sheet: str) -> Iterable[tuple[int, dict[int, str]]]:
        target = self._sheet_targets[sheet]
        root = ET.fromstring(self._zip.read("xl/" + target.lstrip("/")))

        rows: dict[int, dict[int, str]] = defaultdict(dict)
        for c in root.findall(".//m:sheetData/m:row/m:c", NS_MAIN):
            ref = c.attrib.get("r")
            if not ref:
                continue
            col, row = self._split_ref(ref)

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

            value = normalize(value)
            if not value:
                continue
            rows[row][col] = value

        for r in sorted(rows.keys()):
            yield r, rows[r]

    def read_table(self, sheet: str, *, header: bool | None) -> list[tuple[int, dict[str, str]]]:
        raw_rows = list(self.iter_rows(sheet))
        if not raw_rows:
            return []

        first_row_idx, first_cells = raw_rows[0]
        max_col = max(first_cells.keys(), default=0)
        header_row = [first_cells.get(i, "") for i in range(1, max_col + 1)]
        has_header = looks_like_header(header_row) if header is None else header

        if not has_header:
            out: list[tuple[int, dict[str, str]]] = []
            for row_idx, cells in raw_rows:
                out.append((row_idx, {str(k): v for k, v in cells.items()}))
            return out

        headers = [normalize(h) for h in header_row]
        out2: list[tuple[int, dict[str, str]]] = []
        for row_idx, cells in raw_rows[1:]:
            rec: dict[str, str] = {}
            for col_idx, val in cells.items():
                if col_idx <= len(headers):
                    key = headers[col_idx - 1]
                    if key:
                        rec[key] = normalize(val)
            if rec:
                out2.append((row_idx, rec))
        return out2


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def build(xlsx_path: Path, out_dir: Path, *, seed: str) -> None:
    reader = XlsxReader(xlsx_path)
    try:
        needed = [
            "berendes",
            "beck+berendes",
            "berendes + moulins",
            "NEW moulins laguna",
            "NEW moulins wechel",
            "NEW moulins matthiolus",
            "berendes + ruel",
            "berendes + lusitanus",
            "berendes + barbaro",
            "gunther beck combined",
            "wellmann beck combined",
        ]
        missing = [s for s in needed if not reader.sheet_exists(s)]
        if missing:
            raise SystemExit(f"Missing expected sheets: {', '.join(missing)}")

        # Base Berendes (no header): col 1 teitok id, col 2 chapter, col 3 term.
        ber_raw = reader.read_table("berendes", header=False)
        ber_by_teitok: dict[str, dict[str, str]] = {}
        chapter_to_teitoks: dict[str, list[str]] = defaultdict(list)
        ber_order: list[str] = []
        ber_pos: dict[str, int] = {}
        for row_idx, rec in ber_raw:
            teitok = normalize(rec.get("1", ""))
            ch_raw = normalize(rec.get("2", ""))
            term = normalize(rec.get("3", ""))
            if teitok:
                ber_by_teitok[teitok] = {
                    "berendes_teitok_id": teitok,
                    "berendes_chapter_raw": ch_raw,
                    "berendes_term": term,
                }
                ber_pos[teitok] = len(ber_order)
                ber_order.append(teitok)
            for k in expand_key(ch_raw):
                if teitok:
                    chapter_to_teitoks[k].append(teitok)

        # Indices used for enrichment.
        des_by_teitok: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("berendes + moulins", header=None):
            teitok = normalize(rec.get("berendes_teitok_id", ""))
            if not teitok:
                continue
            des_by_teitok[teitok].append(
                {
                    "desmoulins_page": normalize(rec.get("desmoulins_page", "")),
                    "desmoulins_chapter": normalize(rec.get("desmoulins_chapter", "")),
                    "desmoulins_term": normalize(rec.get("desmoulins_term", "")),
                    "src_row": str(row_idx),
                }
            )

        lag_by_chapter: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("NEW moulins laguna", header=None):
            ch_raw = normalize(rec.get("berendes_id", ""))
            for k in expand_key(ch_raw):
                lag_by_chapter[k].append(
                    {
                        "laguna_book": normalize(rec.get("laguna_book", "")),
                        "laguna_page": normalize(rec.get("laguna_page", "")),
                        "laguna_chapter": normalize(rec.get("laguna_chapter", "")),
                        "laguna_title": normalize(rec.get("laguna_title", "")),
                        "laguna_scan_id": normalize(rec.get("laguna_scan_id", "")),
                        "src_row": str(row_idx),
                    }
                )

        wec_by_chapter: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("NEW moulins wechel", header=None):
            ch_raw = normalize(rec.get("berendes_id", ""))
            for k in expand_key(ch_raw):
                wec_by_chapter[k].append(
                    {
                        "wechel_book": normalize(rec.get("wechel_book", "")),
                        "wechel_page": normalize(rec.get("wechel_page", "")),
                        "wechel_chapter": normalize(rec.get("wechel_chapter", "")),
                        "wechel_title": normalize(rec.get("wechel_title", "")),
                        "wechel_scan_id": normalize(rec.get("wechel_scan_id", "")),
                        "src_row": str(row_idx),
                    }
                )

        mat_by_chapter: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("NEW moulins matthiolus", header=None):
            ch_raw = normalize(rec.get("berendes_id", ""))
            for k in expand_key(ch_raw):
                mat_by_chapter[k].append(
                    {
                        "mattioli_book": normalize(rec.get("mattioli_book", "")),
                        "mattioli_chapter_roman": normalize(rec.get("mattioli_chapter_roman", "")),
                        "mattioli_chapter_decimal": normalize(rec.get("mattioli_chapter_decimal", "")),
                        "mattioli_greek": normalize(rec.get("mattioli_greek", "")),
                        "mattioli_latin": normalize(rec.get("mattioli_latin", "")),
                        "src_row": str(row_idx),
                    }
                )

        ruel_by_teitok: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("berendes + ruel", header=None):
            teitok = normalize(rec.get("berendes_teitok_id", ""))
            if not teitok:
                continue
            ruel_by_teitok[teitok].append(
                {
                    "ruel_book": normalize(rec.get("ruel_book", "")),
                    "ruel_page_scan": normalize(rec.get("ruel_page_scan", "")),
                    "ruel_folio": normalize(rec.get("ruel_folio", "")),
                    "ruel_chapter": normalize(rec.get("ruel_chapter", "")),
                    "ruel_title_latin": normalize(rec.get("ruel_title_latin", "")),
                    "ruel_title_vernacular": normalize(rec.get("ruel_title_vernacular", "")),
                    "src_row": str(row_idx),
                }
            )

        lus_by_teitok: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("berendes + lusitanus", header=None):
            teitok = normalize(rec.get("berendes_teitok_id", ""))
            if not teitok:
                continue
            lus_by_teitok[teitok].append(
                {
                    "lusitanus_page": normalize(rec.get("lusitanus_page", "")),
                    "lusitanus_chapter": normalize(rec.get("lusitanus_chapter", "")),
                    "lusitanus_title": normalize(rec.get("lusitanus_title", "")),
                    "src_row": str(row_idx),
                }
            )

        bar_by_teitok: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("berendes + barbaro", header=None):
            teitok = normalize(rec.get("berendes_teitok_id", ""))
            if not teitok:
                continue
            bar_by_teitok[teitok].append(
                {
                    "barbaro_book": normalize(rec.get("barbaro_book", "")),
                    "barbaro_page": normalize(rec.get("barbaro_page", "")),
                    "barbaro_chapter": normalize(rec.get("barbaro_chapter", "")),
                    "barbaro_term": normalize(rec.get("barbaro_term", "")),
                    "src_row": str(row_idx),
                }
            )

        gun_by_dmm: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("gunther beck combined", header=None):
            dmm = normalize(rec.get("dmm_id", ""))
            if not dmm:
                continue
            gun_by_dmm[dmm].append(
                {
                    "gunther_chapter": normalize(rec.get("gunther_chapter", "")),
                    "gunther_division": normalize(rec.get("gunther_division", "")),
                    "gunther_term": normalize(rec.get("gunther_term", "")),
                    "src_row": str(row_idx),
                }
            )

        well_by_dmm: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_idx, rec in reader.read_table("wellmann beck combined", header=None):
            dmm = normalize(rec.get("dmm_id", ""))
            if not dmm:
                continue
            well_by_dmm[dmm].append(
                {
                    "wellmann_id": normalize(rec.get("wellmann_id", "")),
                    "wellmann_book": normalize(rec.get("wellmann_book", "")),
                    "wellmann_chapter": normalize(rec.get("wellmann_chapter", "")),
                    "term_greek_lemma": normalize(rec.get("term_greek_lemma", "")),
                    "wellmann_greek_text": normalize(rec.get("wellmann_greek_text", "")),
                    "src_row": str(row_idx),
                }
            )

        def enrich_edge(*, dmm: str, beck_gr: str, beck_lat: str, teitok: str, source_row: str) -> dict[str, str]:
            bchap_raw = ""
            bterm = ""
            canonical = ber_by_teitok.get(teitok, {})
            bchap_raw = normalize(canonical.get("berendes_chapter_raw", ""))
            bterm = normalize(canonical.get("berendes_term", ""))
            chapter_keys = expand_key(bchap_raw)

            lag_rows = []
            wec_rows = []
            mat_rows = []
            for ck in chapter_keys:
                lag_rows.extend(lag_by_chapter.get(ck, []))
                wec_rows.extend(wec_by_chapter.get(ck, []))
                mat_rows.extend(mat_by_chapter.get(ck, []))

            return {
                "beck_berendes_row": source_row,
                "beck_dmm_id": dmm,
                "beck_greek_lemma": beck_gr,
                "beck_latin_lemma": beck_lat,
                "berendes_teitok_id": teitok,
                "berendes_chapter_raw": bchap_raw,
                "berendes_book_num": unique_join([berendes_book_num(k) for k in chapter_keys]),
                "berendes_chapter_keys": unique_join(chapter_keys),
                "berendes_term": bterm,
                "desmoulins_page": unique_join([r["desmoulins_page"] for r in des_by_teitok.get(teitok, [])]),
                "desmoulins_chapter": unique_join([r["desmoulins_chapter"] for r in des_by_teitok.get(teitok, [])]),
                "desmoulins_term": unique_join([r["desmoulins_term"] for r in des_by_teitok.get(teitok, [])]),
                "laguna_book": unique_join([r["laguna_book"] for r in lag_rows]),
                "laguna_page": unique_join([r["laguna_page"] for r in lag_rows]),
                "laguna_chapter": unique_join([r["laguna_chapter"] for r in lag_rows]),
                "laguna_title": unique_join([r["laguna_title"] for r in lag_rows]),
                "laguna_scan_id": unique_join([r["laguna_scan_id"] for r in lag_rows]),
                "wechel_book": unique_join([r["wechel_book"] for r in wec_rows]),
                "wechel_page": unique_join([r["wechel_page"] for r in wec_rows]),
                "wechel_chapter": unique_join([r["wechel_chapter"] for r in wec_rows]),
                "wechel_title": unique_join([r["wechel_title"] for r in wec_rows]),
                "wechel_scan_id": unique_join([r["wechel_scan_id"] for r in wec_rows]),
                "mattioli_book": unique_join([r["mattioli_book"] for r in mat_rows]),
                "mattioli_chapter_decimal": unique_join([r["mattioli_chapter_decimal"] for r in mat_rows]),
                "mattioli_chapter_roman": unique_join([r["mattioli_chapter_roman"] for r in mat_rows]),
                "mattioli_greek": unique_join([r["mattioli_greek"] for r in mat_rows]),
                "mattioli_latin": unique_join([r["mattioli_latin"] for r in mat_rows]),
                "ruel_book": unique_join([r["ruel_book"] for r in ruel_by_teitok.get(teitok, [])]),
                "ruel_page_scan": unique_join([r["ruel_page_scan"] for r in ruel_by_teitok.get(teitok, [])]),
                "ruel_folio": unique_join([r["ruel_folio"] for r in ruel_by_teitok.get(teitok, [])]),
                "ruel_chapter": unique_join([r["ruel_chapter"] for r in ruel_by_teitok.get(teitok, [])]),
                "ruel_title_latin": unique_join([r["ruel_title_latin"] for r in ruel_by_teitok.get(teitok, [])]),
                "ruel_title_vernacular": unique_join([r["ruel_title_vernacular"] for r in ruel_by_teitok.get(teitok, [])]),
                "lusitanus_page": unique_join([r["lusitanus_page"] for r in lus_by_teitok.get(teitok, [])]),
                "lusitanus_chapter": unique_join([r["lusitanus_chapter"] for r in lus_by_teitok.get(teitok, [])]),
                "lusitanus_title": unique_join([r["lusitanus_title"] for r in lus_by_teitok.get(teitok, [])]),
                "barbaro_book": unique_join([r["barbaro_book"] for r in bar_by_teitok.get(teitok, [])]),
                "barbaro_page": unique_join([r["barbaro_page"] for r in bar_by_teitok.get(teitok, [])]),
                "barbaro_chapter": unique_join([r["barbaro_chapter"] for r in bar_by_teitok.get(teitok, [])]),
                "barbaro_term": unique_join([r["barbaro_term"] for r in bar_by_teitok.get(teitok, [])]),
                "gunther_chapter": unique_join([r["gunther_chapter"] for r in gun_by_dmm.get(dmm, [])]),
                "gunther_division": unique_join([r["gunther_division"] for r in gun_by_dmm.get(dmm, [])]),
                "gunther_term": unique_join([r["gunther_term"] for r in gun_by_dmm.get(dmm, [])]),
                "wellmann_id": unique_join([r["wellmann_id"] for r in well_by_dmm.get(dmm, [])]),
                "wellmann_book": unique_join([r["wellmann_book"] for r in well_by_dmm.get(dmm, [])]),
                "wellmann_chapter": unique_join([r["wellmann_chapter"] for r in well_by_dmm.get(dmm, [])]),
                "wellmann_greek_lemma": unique_join([r["term_greek_lemma"] for r in well_by_dmm.get(dmm, [])]),
                "wellmann_greek_text": unique_join([r["wellmann_greek_text"] for r in well_by_dmm.get(dmm, [])]),
            }

        # Edges from beck+berendes.
        edges: list[dict[str, str]] = []
        per_dmm: dict[str, list[dict[str, str]]] = defaultdict(list)
        beck_meta: dict[str, dict[str, str]] = {}
        for row_idx, rec in reader.read_table("beck+berendes", header=None):
            dmm = normalize(rec.get("dmm_id", ""))
            beck_gr = normalize(rec.get("beck_greek_lemma", ""))
            beck_lat = normalize(rec.get("beck_latin_lemma", ""))
            teitok = normalize(rec.get("berendes_teitok_id", ""))
            bchap_sheet = normalize(rec.get("berendes_chapter", ""))
            bterm_sheet = normalize(rec.get("berendes_term", ""))

            # fallback term/chapter if teitok is empty (can't enrich without)
            if teitok and teitok in ber_by_teitok:
                record = enrich_edge(
                    dmm=dmm,
                    beck_gr=beck_gr,
                    beck_lat=beck_lat,
                    teitok=teitok,
                    source_row=str(row_idx),
                )
            else:
                record = {
                    "beck_berendes_row": str(row_idx),
                    "beck_dmm_id": dmm,
                    "beck_greek_lemma": beck_gr,
                    "beck_latin_lemma": beck_lat,
                    "berendes_teitok_id": teitok,
                    "berendes_chapter_raw": bchap_sheet,
                    "berendes_book_num": unique_join([berendes_book_num(k) for k in expand_key(bchap_sheet)]),
                    "berendes_chapter_keys": unique_join(expand_key(bchap_sheet)),
                    "berendes_term": bterm_sheet,
                    "desmoulins_page": "",
                    "desmoulins_chapter": "",
                    "desmoulins_term": "",
                    "laguna_book": "",
                    "laguna_page": "",
                    "laguna_chapter": "",
                    "laguna_title": "",
                    "laguna_scan_id": "",
                    "wechel_book": "",
                    "wechel_page": "",
                    "wechel_chapter": "",
                    "wechel_title": "",
                    "wechel_scan_id": "",
                    "mattioli_book": "",
                    "mattioli_chapter_decimal": "",
                    "mattioli_chapter_roman": "",
                    "mattioli_greek": "",
                    "mattioli_latin": "",
                    "ruel_book": "",
                    "ruel_page_scan": "",
                    "ruel_folio": "",
                    "ruel_chapter": "",
                    "ruel_title_latin": "",
                    "ruel_title_vernacular": "",
                    "lusitanus_page": "",
                    "lusitanus_chapter": "",
                    "lusitanus_title": "",
                    "barbaro_book": "",
                    "barbaro_page": "",
                    "barbaro_chapter": "",
                    "barbaro_term": "",
                    "gunther_chapter": "",
                    "gunther_division": "",
                    "gunther_term": "",
                    "wellmann_id": "",
                    "wellmann_book": "",
                    "wellmann_chapter": "",
                    "wellmann_greek_lemma": "",
                    "wellmann_greek_text": "",
                }

            chapter_keys_for_candidates = expand_key(record.get("berendes_chapter_raw", ""))
            if not teitok and chapter_keys_for_candidates:
                candidates = []
                for ck in chapter_keys_for_candidates:
                    candidates.extend(chapter_to_teitoks.get(ck, []))
                record["berendes_teitok_candidates"] = unique_join(candidates)
            else:
                record["berendes_teitok_candidates"] = ""

            edges.append(record)
            if dmm:
                per_dmm[dmm].append(record)
                if dmm not in beck_meta and (beck_gr or beck_lat):
                    beck_meta[dmm] = {"beck_greek_lemma": beck_gr, "beck_latin_lemma": beck_lat}

        dmm_counts = Counter([e["beck_dmm_id"] for e in edges if e["beck_dmm_id"]])
        teitok_counts = Counter([e["berendes_teitok_id"] for e in edges if e["berendes_teitok_id"]])
        for e in edges:
            e["beck_degree"] = str(dmm_counts.get(e["beck_dmm_id"], 0))
            e["berendes_degree"] = str(teitok_counts.get(e["berendes_teitok_id"], 0))
            if e["beck_dmm_id"]:
                deg = dmm_counts[e["beck_dmm_id"]]
                e["cardinality"] = "1->N" if deg > 1 else "1->1"
            else:
                e["cardinality"] = ""

        edge_fields = [
            "beck_berendes_row",
            "beck_dmm_id",
            "beck_greek_lemma",
            "beck_latin_lemma",
            "beck_degree",
            "cardinality",
            "berendes_teitok_id",
            "berendes_teitok_candidates",
            "berendes_degree",
            "berendes_book_num",
            "berendes_chapter_raw",
            "berendes_chapter_keys",
            "berendes_term",
            "desmoulins_page",
            "desmoulins_chapter",
            "desmoulins_term",
            "laguna_book",
            "laguna_page",
            "laguna_chapter",
            "laguna_title",
            "laguna_scan_id",
            "wechel_book",
            "wechel_page",
            "wechel_chapter",
            "wechel_title",
            "wechel_scan_id",
            "mattioli_book",
            "mattioli_chapter_decimal",
            "mattioli_chapter_roman",
            "mattioli_greek",
            "mattioli_latin",
            "ruel_book",
            "ruel_page_scan",
            "ruel_folio",
            "ruel_chapter",
            "ruel_title_latin",
            "ruel_title_vernacular",
            "lusitanus_page",
            "lusitanus_chapter",
            "lusitanus_title",
            "barbaro_book",
            "barbaro_page",
            "barbaro_chapter",
            "barbaro_term",
            "gunther_chapter",
            "gunther_division",
            "gunther_term",
            "wellmann_id",
            "wellmann_book",
            "wellmann_chapter",
            "wellmann_greek_lemma",
            "wellmann_greek_text",
        ]

        write_csv(out_dir / "beck_berendes_edges.csv", edge_fields, edges)

        # Groups view (per Beck dmm_id)
        groups: list[dict[str, str]] = []
        for dmm in sorted(per_dmm.keys()):
            items = per_dmm[dmm]
            groups.append(
                {
                    "beck_dmm_id": dmm,
                    "beck_greek_lemma": items[0].get("beck_greek_lemma", ""),
                    "beck_latin_lemma": items[0].get("beck_latin_lemma", ""),
                    "beck_degree": str(len(items)),
                    "berendes_teitok_ids": unique_join([it["berendes_teitok_id"] for it in items]),
                    "berendes_chapter_keys": unique_join([it["berendes_chapter_keys"] for it in items]),
                    "berendes_terms": unique_join([it["berendes_term"] for it in items]),
                    "desmoulins_pages": unique_join([it["desmoulins_page"] for it in items]),
                    "laguna_pages": unique_join([it["laguna_page"] for it in items]),
                    "wechel_pages": unique_join([it["wechel_page"] for it in items]),
                    "mattioli_chapters": unique_join([it["mattioli_chapter_decimal"] for it in items]),
                }
            )

        write_csv(
            out_dir / "beck_berendes_groups.csv",
            [
                "beck_dmm_id",
                "beck_greek_lemma",
                "beck_latin_lemma",
                "beck_degree",
                "berendes_teitok_ids",
                "berendes_chapter_keys",
                "berendes_terms",
                "desmoulins_pages",
                "laguna_pages",
                "wechel_pages",
                "mattioli_chapters",
            ],
            groups,
        )

        one_to_many = sum(1 for c in dmm_counts.values() if c > 1)
        many_to_one = sum(1 for c in teitok_counts.values() if c > 1)
        qa_lines = [
            "# Beck ↔ Berendes alignment QA",
            f"- Source: `{xlsx_path.name}`",
            f"- Edge rows: {len(edges)} (with beck_dmm_id: {sum(1 for e in edges if e['beck_dmm_id'])})",
            f"- Unique Beck dmm_id: {len(dmm_counts)}",
            f"- Beck 1→N cases (degree>1): {one_to_many}",
            f"- Berendes N→1 cases (degree>1): {many_to_one}",
            "",
            "## Notes",
            "- Uses `berendes_teitok_id` as the Berendes stable id.",
            "- Adds context from Desmoulins/Laguna/Wechel/Mattioli/Ruel/Lusitanus/Barbaro/Gunther/Wellmann where available.",
            "- `berendes_chapter_raw` may be composite (e.g. `3.29;3.30`); `berendes_chapter_keys` is expanded.",
            "- `cardinality` is computed per Beck dmm_id within this alignment sheet only.",
        ]
        (out_dir / "beck_berendes_qa.md").write_text("\n".join(qa_lines) + "\n", encoding="utf-8")

        rng = random.Random(seed)
        sample = rng.sample(edges, 50) if len(edges) >= 50 else list(edges)
        lines = ["Sample: 50 random beck_berendes_edges rows"]
        for i, e in enumerate(sample, start=1):
            lines.append(
                f"{i:02d} {e['beck_dmm_id']} ({e['beck_greek_lemma']}) -> "
                f"{e['berendes_teitok_id']} {e['berendes_chapter_keys']} {e['berendes_term']} | "
                f"des_pg={e['desmoulins_page']} lag_pg={e['laguna_page']} wec_pg={e['wechel_page']} "
                f"mat={e['mattioli_chapter_decimal']}"
            )
        (out_dir / "beck_berendes_sample50.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Span inference: use beck+berendes as anchors and assign contiguous Berendes ranges.
        anchors: dict[str, int] = {}
        for e in edges:
            dmm = e.get("beck_dmm_id", "")
            teitok = e.get("berendes_teitok_id", "")
            if not dmm or not teitok:
                continue
            pos = ber_pos.get(teitok)
            if pos is None:
                continue
            if dmm not in anchors or pos < anchors[dmm]:
                anchors[dmm] = pos

        anchor_list = sorted([(pos, dmm) for dmm, pos in anchors.items()])
        span_edges: list[dict[str, str]] = []
        span_sizes: dict[str, int] = {}
        for idx, (start_pos, dmm) in enumerate(anchor_list):
            end_pos = (anchor_list[idx + 1][0] - 1) if idx + 1 < len(anchor_list) else (len(ber_order) - 1)
            if end_pos < start_pos:
                continue
            span_sizes[dmm] = end_pos - start_pos + 1
            meta = beck_meta.get(dmm, {})
            beck_gr = meta.get("beck_greek_lemma", "")
            beck_lat = meta.get("beck_latin_lemma", "")
            anchor_teitok = ber_order[start_pos]
            anchor_ch = normalize(ber_by_teitok.get(anchor_teitok, {}).get("berendes_chapter_raw", ""))
            for pos in range(start_pos, end_pos + 1):
                teitok = ber_order[pos]
                row = enrich_edge(dmm=dmm, beck_gr=beck_gr, beck_lat=beck_lat, teitok=teitok, source_row="")
                row["span_anchor_teitok_id"] = anchor_teitok
                row["span_anchor_chapter"] = anchor_ch
                row["span_offset"] = str(pos - start_pos)
                span_edges.append(row)

        span_fields = ["span_anchor_teitok_id", "span_anchor_chapter", "span_offset"] + [
            f for f in edge_fields if f not in ("beck_berendes_row",)
        ]
        # ensure no duplicate fieldnames
        seen = set()
        span_fields = [f for f in span_fields if not (f in seen or seen.add(f))]
        write_csv(out_dir / "beck_berendes_span_edges.csv", span_fields, span_edges)

        # Span QA
        size_counts = Counter(span_sizes.values())
        biggest = sorted(span_sizes.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        qa2 = []
        qa2.append("# Beck ↔ Berendes span inference QA")
        qa2.append(f"- Spanned Berendes entries: {len(span_edges)} (should equal {len(ber_order)})")
        qa2.append(f"- Anchors (unique dmm_id with anchor): {len(anchor_list)}")
        qa2.append(f"- Span size distribution (size:count): {', '.join([f'{k}:{v}' for k,v in sorted(size_counts.items())[:12]])}")
        qa2.append("")
        qa2.append("## Largest spans (top 10)")
        for dmm, size in biggest:
            meta = beck_meta.get(dmm, {})
            qa2.append(f"- {dmm} ({meta.get('beck_greek_lemma','')}) size={size}")
        (out_dir / "beck_berendes_span_qa.md").write_text("\n".join(qa2) + "\n", encoding="utf-8")

        # Sample span edges for review
        rng2 = random.Random(f"{seed}:span")
        span_sample = rng2.sample(span_edges, 50) if len(span_edges) >= 50 else list(span_edges)
        lines2 = ["Sample: 50 random beck_berendes_span_edges rows"]
        for i, e in enumerate(span_sample, start=1):
            lines2.append(
                f"{i:02d} {e['beck_dmm_id']} ({e['beck_greek_lemma']}) -> "
                f"{e['berendes_teitok_id']} {e['berendes_chapter_keys']} {e['berendes_term']} | "
                f"offset={e['span_offset']} anchor={e['span_anchor_teitok_id']} {e['span_anchor_chapter']}"
            )
        (out_dir / "beck_berendes_span_sample50.txt").write_text("\n".join(lines2) + "\n", encoding="utf-8")
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Beck↔Berendes alignment export")
    parser.add_argument("--xlsx", default="Materia Medica.xlsx")
    parser.add_argument("--out-dir", default="data/alignments")
    parser.add_argument(
        "--seed",
        default="beck-berendes-sample",
        help="Seed for the random 50-row sample (default: fixed string)",
    )
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    if not xlsx_path.exists():
        raise SystemExit(f"Input not found: {xlsx_path}")

    out_dir = Path(args.out_dir)
    build(xlsx_path, out_dir, seed=args.seed)
    print(f"Wrote: {out_dir / 'beck_berendes_edges.csv'}")
    print(f"Wrote: {out_dir / 'beck_berendes_groups.csv'}")
    print(f"Wrote: {out_dir / 'beck_berendes_qa.md'}")
    print(f"Wrote: {out_dir / 'beck_berendes_sample50.txt'}")
    print(f"Wrote: {out_dir / 'beck_berendes_span_edges.csv'}")
    print(f"Wrote: {out_dir / 'beck_berendes_span_qa.md'}")
    print(f"Wrote: {out_dir / 'beck_berendes_span_sample50.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
