#!/usr/bin/env python3
"""
Extract per-edition tables from Materia Medica.xlsx into normalized CSVs.

Outputs (default: data/editions/):
  - berendes.csv
  - desmoulins.csv
  - laguna.csv
  - wechel.csv
  - ruel.csv
  - lusitanus.csv
  - barbaro.csv
  - gunther.csv
  - matthiolo.csv
  - wellmann.csv
  - beck_index.csv
  - moulins.csv (raw Desmoulins list)

This is deliberately “edition-native”: it does not attempt cross-edition alignment.
"""

from __future__ import annotations

import argparse
import csv
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable
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


def _normalize(value: str) -> str:
    v = str(value).strip()
    if v.upper() == "#N/A":
        return ""
    # trim float-ish integers like "17.0" -> "17"
    if v.endswith(".0") and v.replace(".", "", 1).isdigit():
        return v[:-2]
    return v


class XlsxReader:
    def __init__(self, path: Path):
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self._shared_strings = self._load_shared_strings()
        self._sheet_targets = self._load_sheet_targets()

    def close(self) -> None:
        self._zip.close()

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

    def iter_rows(self, sheet: str) -> Iterable[tuple[int, dict[int, str]]]:
        target = self._sheet_targets[sheet]
        root = ET.fromstring(self._zip.read("xl/" + target.lstrip("/")))

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

            value = _normalize(value)
            if value == "":
                continue
            rows[row][col] = value

        for r in sorted(rows.keys()):
            yield r, rows[r]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def extract(xlsx_path: Path, out_dir: Path) -> None:
    reader = XlsxReader(xlsx_path)
    try:
        # berendes (no header; 3 columns)
        ber: list[dict[str, str]] = []
        for row_idx, cells in reader.iter_rows("berendes"):
            ber.append(
                {
                    "edition": "berendes",
                    "edition_entry_id": f"row{row_idx}",
                    "berendes_teitok_id": _normalize(cells.get(1, "")),
                    "berendes_chapter": _normalize(cells.get(2, "")),
                    "berendes_term": _normalize(cells.get(3, "")),
                }
            )
        _write_csv(
            out_dir / "berendes.csv",
            ["edition", "edition_entry_id", "berendes_teitok_id", "berendes_chapter", "berendes_term"],
            ber,
        )

        # moulins (has header)
        moul: list[dict[str, str]] = []
        # Read header row explicitly from iter_rows
        raw_rows = list(reader.iter_rows("moulins"))
        header = {col: val for col, val in raw_rows[0][1].items()}
        for row_idx, cells in raw_rows[1:]:
            moul.append(
                {
                    "edition": "desmoulins",
                    "edition_entry_id": f"row{row_idx}",
                    "desmoulins_page": _normalize(cells.get(1, "")),
                    "desmoulins_term": _normalize(cells.get(2, "")),
                    "desmoulins_chapter": _normalize(cells.get(3, "")),
                }
            )
        _write_csv(
            out_dir / "desmoulins.csv",
            ["edition", "edition_entry_id", "desmoulins_page", "desmoulins_chapter", "desmoulins_term"],
            moul,
        )
        _write_csv(
            out_dir / "moulins.csv",
            ["edition", "edition_entry_id", "desmoulins_page", "desmoulins_chapter", "desmoulins_term"],
            moul,
        )

        # laguna (has header row)
        lag: list[dict[str, str]] = []
        raw_rows = list(reader.iter_rows("laguna"))
        # skip header
        for row_idx, cells in raw_rows[1:]:
            lag.append(
                {
                    "edition": "laguna",
                    "edition_entry_id": f"row{row_idx}",
                    "laguna_scan_id": _normalize(cells.get(1, "")),
                    "laguna_book": _normalize(cells.get(2, "")),
                    "laguna_page": _normalize(cells.get(3, "")),
                    "laguna_chapter": _normalize(cells.get(4, "")),
                    "laguna_title": _normalize(cells.get(5, "")),
                }
            )
        _write_csv(
            out_dir / "laguna.csv",
            [
                "edition",
                "edition_entry_id",
                "laguna_scan_id",
                "laguna_book",
                "laguna_page",
                "laguna_chapter",
                "laguna_title",
            ],
            lag,
        )

        # wechel (has header row)
        wec: list[dict[str, str]] = []
        raw_rows = list(reader.iter_rows("wechel"))
        for row_idx, cells in raw_rows[1:]:
            wec.append(
                {
                    "edition": "wechel",
                    "edition_entry_id": f"row{row_idx}",
                    "wechel_scan_id": _normalize(cells.get(1, "")),
                    "wechel_book": _normalize(cells.get(2, "")),
                    "wechel_page": _normalize(cells.get(3, "")),
                    "wechel_title": _normalize(cells.get(4, "")),
                    "wechel_chapter": _normalize(cells.get(5, "")),
                }
            )
        _write_csv(
            out_dir / "wechel.csv",
            [
                "edition",
                "edition_entry_id",
                "wechel_scan_id",
                "wechel_book",
                "wechel_page",
                "wechel_chapter",
                "wechel_title",
            ],
            wec,
        )

        # ruel (no header; 6 columns)
        ruel: list[dict[str, str]] = []
        for row_idx, cells in reader.iter_rows("ruel"):
            ruel.append(
                {
                    "edition": "ruel",
                    "edition_entry_id": f"row{row_idx}",
                    "ruel_page_scan": _normalize(cells.get(1, "")),
                    "ruel_book": _normalize(cells.get(2, "")),
                    "ruel_unknown_val": _normalize(cells.get(3, "")),
                    "ruel_chapter": _normalize(cells.get(4, "")),
                    "ruel_title_latin": _normalize(cells.get(5, "")),
                    "ruel_folio": _normalize(cells.get(6, "")),
                }
            )
        _write_csv(
            out_dir / "ruel.csv",
            [
                "edition",
                "edition_entry_id",
                "ruel_page_scan",
                "ruel_book",
                "ruel_unknown_val",
                "ruel_chapter",
                "ruel_title_latin",
                "ruel_folio",
            ],
            ruel,
        )

        # lusitanus (no header; usually 3 columns: page, title, note)
        lus: list[dict[str, str]] = []
        for row_idx, cells in reader.iter_rows("lusitanus"):
            lus.append(
                {
                    "edition": "lusitanus",
                    "edition_entry_id": f"row{row_idx}",
                    "lusitanus_page": _normalize(cells.get(1, "")),
                    "lusitanus_title": _normalize(cells.get(2, "")),
                    "lusitanus_note": _normalize(cells.get(3, "")),
                }
            )
        _write_csv(
            out_dir / "lusitanus.csv",
            ["edition", "edition_entry_id", "lusitanus_page", "lusitanus_title", "lusitanus_note"],
            lus,
        )

        # barbaro (no header; 4 columns)
        bar: list[dict[str, str]] = []
        for row_idx, cells in reader.iter_rows("barbaro"):
            bar.append(
                {
                    "edition": "barbaro",
                    "edition_entry_id": f"row{row_idx}",
                    "barbaro_page": _normalize(cells.get(1, "")),
                    "barbaro_chapter": _normalize(cells.get(2, "")),
                    "barbaro_term": _normalize(cells.get(3, "")),
                    "barbaro_book": _normalize(cells.get(4, "")),
                }
            )
        _write_csv(
            out_dir / "barbaro.csv",
            ["edition", "edition_entry_id", "barbaro_page", "barbaro_book", "barbaro_chapter", "barbaro_term"],
            bar,
        )

        # gunther (no header; 4 columns)
        gun: list[dict[str, str]] = []
        for row_idx, cells in reader.iter_rows("gunther"):
            gun.append(
                {
                    "edition": "gunther",
                    "edition_entry_id": f"row{row_idx}",
                    "gunther_chapter": _normalize(cells.get(1, "")),
                    "gunther_division": _normalize(cells.get(2, "")),
                    "gunther_term": _normalize(cells.get(3, "")),
                    "gunther_description": _normalize(cells.get(4, "")),
                }
            )
        _write_csv(
            out_dir / "gunther.csv",
            [
                "edition",
                "edition_entry_id",
                "gunther_chapter",
                "gunther_division",
                "gunther_term",
                "gunther_description",
            ],
            gun,
        )

        # matthiolo (no header; 4 columns in early rows, but later may extend)
        mat: list[dict[str, str]] = []
        for row_idx, cells in reader.iter_rows("matthiolo"):
            mat.append(
                {
                    "edition": "matthiolo",
                    "edition_entry_id": f"row{row_idx}",
                    "matthiolo_book": _normalize(cells.get(1, "")),
                    "matthiolo_chapter": _normalize(cells.get(2, "")),
                    "matthiolo_greek": _normalize(cells.get(3, "")),
                    "matthiolo_latin": _normalize(cells.get(4, "")),
                }
            )
        _write_csv(
            out_dir / "matthiolo.csv",
            [
                "edition",
                "edition_entry_id",
                "matthiolo_book",
                "matthiolo_chapter",
                "matthiolo_greek",
                "matthiolo_latin",
            ],
            mat,
        )

        # wellmann (no header; 4 columns)
        wel: list[dict[str, str]] = []
        for row_idx, cells in reader.iter_rows("wellmann"):
            wel.append(
                {
                    "edition": "wellmann",
                    "edition_entry_id": f"row{row_idx}",
                    "wellmann_id": _normalize(cells.get(1, "")),
                    "wellmann_book": _normalize(cells.get(2, "")),
                    "wellmann_chapter": _normalize(cells.get(3, "")),
                    "wellmann_greek_text": _normalize(cells.get(4, "")),
                }
            )
        _write_csv(
            out_dir / "wellmann.csv",
            [
                "edition",
                "edition_entry_id",
                "wellmann_id",
                "wellmann_book",
                "wellmann_chapter",
                "wellmann_greek_text",
            ],
            wel,
        )

        # beck-index (no header; 3 columns)
        beck: list[dict[str, str]] = []
        for row_idx, cells in reader.iter_rows("beck-index"):
            beck.append(
                {
                    "edition": "beck",
                    "edition_entry_id": f"row{row_idx}",
                    "dmm_id": _normalize(cells.get(1, "")),
                    "greek_lemma": _normalize(cells.get(2, "")),
                    "latin_lemma": _normalize(cells.get(3, "")),
                }
            )
        _write_csv(
            out_dir / "beck_index.csv",
            ["edition", "edition_entry_id", "dmm_id", "greek_lemma", "latin_lemma"],
            beck,
        )

    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract per-edition CSVs from Materia Medica.xlsx")
    parser.add_argument("--xlsx", default="Materia Medica.xlsx", help="Input .xlsx path")
    parser.add_argument("--out-dir", default="data/editions", help="Output directory")
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    out_dir = Path(args.out_dir)
    if not xlsx_path.exists():
        raise SystemExit(f"Input not found: {xlsx_path}")

    extract(xlsx_path, out_dir)
    print(f"Wrote edition CSVs to {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

