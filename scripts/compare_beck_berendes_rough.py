#!/usr/bin/env python3
"""
Compare data/alignments/beck_berendes_rough.tsv against generated exports.

Rough TSV is treated as a span-style mapping: (beck_dmm_id -> berendes_teitok_id) pairs.

Inputs (defaults):
  - data/alignments/beck_berendes_rough.tsv
  - data/alignments/beck_berendes_edges.csv
  - data/alignments/beck_berendes_span_edges.csv
  - data/editions/beck_index.csv

Outputs (default to data/alignments/):
  - beck_berendes_rough_compare.md
  - beck_berendes_rough_compare_pairs.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_rough(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="\t")
        for line in r:
            if not line or all(not c.strip() for c in line):
                continue
            while len(line) < 7:
                line.append("")
            if len(line) > 7:
                line = line[:6] + ["\t".join(line[6:])]
            rows.append(
                {
                    "beck_dmm_id": line[0].strip(),
                    "beck_greek_lemma": line[1].strip(),
                    "beck_latin_lemma": line[2].strip(),
                    "berendes_teitok_id": line[3].strip(),
                    "berendes_chapter": line[4].strip(),
                    "berendes_term": line[5].strip(),
                    "berendes_greek": line[6].strip(),
                }
            )
    return rows


def read_csv_dict(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare beck_berendes_rough.tsv to generated alignments")
    parser.add_argument("--rough", default="data/alignments/beck_berendes_rough.tsv")
    parser.add_argument("--edges", default="data/alignments/beck_berendes_edges.csv")
    parser.add_argument("--span", default="data/alignments/beck_berendes_span_edges.csv")
    parser.add_argument("--beck-index", default="data/editions/beck_index.csv")
    parser.add_argument("--out-dir", default="data/alignments")
    args = parser.parse_args()

    rough_path = Path(args.rough)
    edges_path = Path(args.edges)
    span_path = Path(args.span)
    beck_index_path = Path(args.beck_index)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rough_rows = read_rough(rough_path)
    edges_rows = read_csv_dict(edges_path)
    span_rows = read_csv_dict(span_path)

    rough_pairs = {(r["beck_dmm_id"], r["berendes_teitok_id"]) for r in rough_rows if r["beck_dmm_id"] and r["berendes_teitok_id"]}
    edge_pairs = {(r["beck_dmm_id"], r["berendes_teitok_id"]) for r in edges_rows if (r.get("beck_dmm_id") or "").strip() and (r.get("berendes_teitok_id") or "").strip()}
    span_pairs = {(r["beck_dmm_id"], r["berendes_teitok_id"]) for r in span_rows if (r.get("beck_dmm_id") or "").strip() and (r.get("berendes_teitok_id") or "").strip()}

    # Index generated edges (to detect \"blank Berendes\" Beck rows and DMM reuse)
    edges_by_dmm: dict[str, list[dict[str, str]]] = defaultdict(list)
    blank_berendes_dmms: set[str] = set()
    for r in edges_rows:
        dmm = (r.get("beck_dmm_id") or "").strip()
        if not dmm:
            continue
        edges_by_dmm[dmm].append(r)
        if not (r.get("berendes_teitok_id") or "").strip():
            blank_berendes_dmms.add(dmm)

    # DMM reuse in beck_index (same DMM id with multiple lemmas)
    beck_index_lemmas: dict[str, set[tuple[str, str]]] = defaultdict(set)
    if beck_index_path.exists():
        for r in read_csv_dict(beck_index_path):
            d = (r.get("dmm_id") or "").strip()
            if not d:
                continue
            beck_index_lemmas[d].add(((r.get("greek_lemma") or "").strip(), (r.get("latin_lemma") or "").strip()))
    reused_dmm = sorted([d for d, vals in beck_index_lemmas.items() if len(vals) > 1])

    # N→1 in rough: one Berendes teitok mapped to multiple Beck dmm ids
    rough_by_teitok: dict[str, set[str]] = defaultdict(set)
    for r in rough_rows:
        if r["berendes_teitok_id"] and r["beck_dmm_id"]:
            rough_by_teitok[r["berendes_teitok_id"]].add(r["beck_dmm_id"])
    rough_teitok_multi = sorted(
        [(t, sorted(list(dmms))) for t, dmms in rough_by_teitok.items() if len(dmms) > 1],
        key=lambda x: (-len(x[1]), x[0]),
    )

    # Compare rough vs generated span
    only_rough = sorted(list(rough_pairs - span_pairs))
    only_span = sorted(list(span_pairs - rough_pairs))

    def pair_reason(dmm: str, kind: str) -> str:
        if kind == "rough_only":
            if dmm in blank_berendes_dmms:
                return "Beck+Berendes row exists but Berendes target is blank; rough attaches it to a Berendes teitok."
            if len(edges_by_dmm.get(dmm, [])) > 1:
                return "DMM id is reused (same DMM appears multiple times with different lemmas/targets); span anchors by earliest occurrence."
            return "Not present in generated span; likely manually curated/imputed."
        return "Generated span assigns this Berendes entry to this Beck DMM due to missing intermediate anchors."

    # Write diff pairs CSV
    pairs_out = out_dir / "beck_berendes_rough_compare_pairs.csv"
    with pairs_out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["kind", "beck_dmm_id", "berendes_teitok_id", "reason"])
        w.writeheader()
        for dmm, teitok in only_rough:
            w.writerow({"kind": "rough_only", "beck_dmm_id": dmm, "berendes_teitok_id": teitok, "reason": pair_reason(dmm, "rough_only")})
        for dmm, teitok in only_span:
            w.writerow({"kind": "span_only", "beck_dmm_id": dmm, "berendes_teitok_id": teitok, "reason": pair_reason(dmm, "span_only")})

    # Markdown report
    md: list[str] = []
    md.append("# Beck ↔ Berendes rough comparison")
    md.append(f"- Rough rows: {len(rough_rows)} (pairs: {len(rough_pairs)})")
    md.append(f"- Generated edges pairs (explicit): {len(edge_pairs)}")
    md.append(f"- Generated span pairs (inferred): {len(span_pairs)}")
    md.append("")
    md.append("## Pair diffs (rough vs inferred span)")
    md.append(f"- Rough-only pairs: {len(only_rough)}")
    md.append(f"- Span-only pairs: {len(only_span)}")
    md.append("")
    md.append("### Rough-only pairs")
    for dmm, teitok in only_rough:
        md.append(f"- {dmm} -> {teitok} ({pair_reason(dmm, 'rough_only')})")
    md.append("")
    md.append("### Span-only pairs")
    for dmm, teitok in only_span:
        md.append(f"- {dmm} -> {teitok} ({pair_reason(dmm, 'span_only')})")
    md.append("")
    md.append("## Berendes N→1 cases in rough (same teitok mapped to multiple Beck DMM ids)")
    md.append(f"- Count: {len(rough_teitok_multi)}")
    for teitok, dmms in rough_teitok_multi:
        md.append(f"- {teitok}: {', '.join(dmms)}")
    md.append("")
    md.append("## Beck DMM id reuse in beck_index.csv")
    if reused_dmm:
        md.append(f"- Reused DMM ids: {', '.join(reused_dmm)}")
    else:
        md.append("- None detected")

    md_out = out_dir / "beck_berendes_rough_compare.md"
    md_out.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"Wrote: {md_out}")
    print(f"Wrote: {pairs_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

