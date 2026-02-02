#!/usr/bin/env python3
"""
Assign stable master IDs to each concordance row (chapter_key) and emit semantic QA flags.

Inputs:
  - data/master_concordance.csv (or --in)

Outputs (default to data/):
  - master_concordance_mm.csv     (adds mm_id)
  - master_key_index.csv          (mm_id -> minimal identifying fields)
  - semantic_alignment_flags.csv  (rows with low Greek-lemma similarity)
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


def chapter_sort_key(chapter_key: str) -> tuple:
    # chapter_key like "3.29" or "4.162" or "1.4.5"
    parts = chapter_key.strip().split(".")
    out: list[tuple[int, object]] = []
    for p in parts:
        if p.isdigit():
            out.append((0, int(p)))
        else:
            out.append((1, p))
    return tuple(out)


_RE_PUNCT = re.compile(r"[\s·.;,()\\[\\]{}\\-_/\\\\]+")


def strip_diacritics(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)
    )


def norm_token(s: str) -> str:
    s = strip_diacritics(s)
    s = s.casefold()
    s = _RE_PUNCT.sub("", s)
    return s


def ratio(a: str, b: str) -> float:
    na = norm_token(a or "")
    nb = norm_token(b or "")
    if not na or not nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def main() -> int:
    parser = argparse.ArgumentParser(description="Assign master IDs and emit semantic QA flags")
    parser.add_argument("--in", dest="in_path", default="data/master_concordance.csv")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--prefix", default="MMK")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--flag-threshold", type=float, default=0.80)
    args = parser.parse_args()

    in_path = Path(args.in_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with in_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rows = [r for r in rows if (r.get("chapter_key") or "").strip()]
    rows.sort(key=lambda r: chapter_sort_key(r["chapter_key"]))

    width = len(str(args.start + len(rows) + 10))

    out_rows: list[dict[str, str]] = []
    index_rows: list[dict[str, str]] = []
    flags: list[dict[str, str]] = []

    for i, r in enumerate(rows, start=args.start):
        mm_id = f"{args.prefix}{i:0{width}d}"
        r2 = dict(r)
        r2["mm_id"] = mm_id
        out_rows.append(r2)

        index_rows.append(
            {
                "mm_id": mm_id,
                "chapter_key": r.get("chapter_key", ""),
                "berendes_term": r.get("berendes_term", ""),
                "beck_greek_lemma": r.get("beck_greek_lemma", ""),
                "beck_latin_lemma": r.get("beck_latin_lemma", ""),
            }
        )

        r_bw = ratio(r.get("beck_greek_lemma", ""), r.get("wellmann_greek_lemma", ""))
        r_bm = ratio(r.get("beck_greek_lemma", ""), r.get("matthiolo_greek", ""))
        if r_bw < args.flag_threshold or r_bm < args.flag_threshold:
            flags.append(
                {
                    "mm_id": mm_id,
                    "chapter_key": r.get("chapter_key", ""),
                    "berendes_term": r.get("berendes_term", ""),
                    "beck_greek_lemma": r.get("beck_greek_lemma", ""),
                    "wellmann_greek_lemma": r.get("wellmann_greek_lemma", ""),
                    "matthiolo_greek": r.get("matthiolo_greek", ""),
                    "ratio_beck_wellmann": f"{r_bw:.3f}",
                    "ratio_beck_matthiolo": f"{r_bm:.3f}",
                }
            )

    concordance_out = out_dir / "master_concordance_mm.csv"
    with concordance_out.open("w", newline="", encoding="utf-8") as f:
        base_fields = list(rows[0].keys()) if rows else ["chapter_key"]
        fieldnames = ["mm_id"] + [fn for fn in base_fields if fn != "mm_id"]
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    index_out = out_dir / "master_key_index.csv"
    with index_out.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["mm_id", "chapter_key", "berendes_term", "beck_greek_lemma", "beck_latin_lemma"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(index_rows)

    flags_out = out_dir / "semantic_alignment_flags.csv"
    with flags_out.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "mm_id",
            "chapter_key",
            "berendes_term",
            "beck_greek_lemma",
            "wellmann_greek_lemma",
            "matthiolo_greek",
            "ratio_beck_wellmann",
            "ratio_beck_matthiolo",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(flags)

    print(f"Wrote: {concordance_out}")
    print(f"Wrote: {index_out}")
    print(f"Wrote: {flags_out} ({len(flags)} flagged rows; threshold={args.flag_threshold})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

