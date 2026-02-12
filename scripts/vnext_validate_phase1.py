#!/usr/bin/env python3
"""Validate Phase 1 outputs (citations + IIIF coverage)."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


NON_TEI_IN_SCOPE = ["barbaro", "desmoulins", "lusitanus", "ruellius", "wechel"]

MISSING_IIIF_HEADER = [
    "edition_id",
    "citation_ref",
    "reason",
    "citation_key_field",
    "citation_key_value",
    "source_file",
    "source_row",
]

MISSING_MANIFEST_HEADER = [
    "edition_id",
    "reason",
    "manifest_url",
    "status",
]

AMBIGUOUS_HEADER = [
    "edition_id",
    "citation_ref",
    "reason",
    "targets",
]

BAD_ROWS_HEADER = [
    "edition_id",
    "citation_ref",
    "reason",
    "source_file",
    "source_row",
]


CITATIONS_REQUIRED = {
    "edition_id",
    "citation_ref",
    "source_file",
    "source_row",
}

CITATION_IIIF_REQUIRED = {
    "edition_id",
    "citation_ref",
    "status",
}

IIIF_MANIFEST_REQUIRED = {
    "edition_id",
    "status",
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def write_csv(path: Path, header: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([row.get(h, "") for h in header])


def validate(
    citations_csv: Path,
    manifests_csv: Path,
    iiif_map_csv: Path,
    out_dir: Path,
) -> None:
    citations = read_csv(citations_csv)
    manifests = read_csv(manifests_csv)
    iiif_map = read_csv(iiif_map_csv)

    bad_rows: List[Dict[str, str]] = []
    missing_iiif: List[Dict[str, str]] = []
    missing_manifest: List[Dict[str, str]] = []
    ambiguous: List[Dict[str, str]] = []

    # Required columns checks
    if citations:
        missing_cols = CITATIONS_REQUIRED - set(citations[0].keys())
        if missing_cols:
            bad_rows.append({
                "edition_id": "",
                "citation_ref": "",
                "reason": f"citations_missing_columns:{','.join(sorted(missing_cols))}",
                "source_file": "",
                "source_row": "",
            })
    if iiif_map:
        missing_cols = CITATION_IIIF_REQUIRED - set(iiif_map[0].keys())
        if missing_cols:
            bad_rows.append({
                "edition_id": "",
                "citation_ref": "",
                "reason": f"iiif_map_missing_columns:{','.join(sorted(missing_cols))}",
                "source_file": "",
                "source_row": "",
            })
    if manifests:
        missing_cols = IIIF_MANIFEST_REQUIRED - set(manifests[0].keys())
        if missing_cols:
            bad_rows.append({
                "edition_id": "",
                "citation_ref": "",
                "reason": f"iiif_manifests_missing_columns:{','.join(sorted(missing_cols))}",
                "source_file": "",
                "source_row": "",
            })

    # Build lookup sets
    citations_by_edition: Dict[str, List[Dict[str, str]]] = {}
    for row in citations:
        citations_by_edition.setdefault(row.get("edition_id", ""), []).append(row)

    iiif_keys: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for row in iiif_map:
        key = (row.get("edition_id", ""), row.get("citation_ref", ""))
        iiif_keys.setdefault(key, []).append(row)

    citation_keys: Set[Tuple[str, str]] = set(
        (row.get("edition_id", ""), row.get("citation_ref", "")) for row in citations
    )

    # Ambiguous detection
    for key, rows in iiif_keys.items():
        if len(rows) > 1:
            targets = ";".join(sorted({r.get("canvas_id", "") or r.get("target_url", "") for r in rows}))
            ambiguous.append({
                "edition_id": key[0],
                "citation_ref": key[1],
                "reason": "multiple_targets",
                "targets": targets,
            })

    # Missing IIIF for non-TEI editions in scope (only if citations present)
    for edition_id in NON_TEI_IN_SCOPE:
        edition_citations = citations_by_edition.get(edition_id, [])
        if not edition_citations:
            continue
        for row in edition_citations:
            key = (edition_id, row.get("citation_ref", ""))
            if key not in iiif_keys:
                missing_iiif.append({
                    "edition_id": edition_id,
                    "citation_ref": row.get("citation_ref", ""),
                    "reason": "missing_iiif_target",
                    "citation_key_field": "",
                    "citation_key_value": "",
                    "source_file": row.get("source_file", ""),
                    "source_row": row.get("source_row", ""),
                })

    # Missing manifest for provisional editions
    for row in manifests:
        if row.get("status") == "provisional":
            missing_manifest.append({
                "edition_id": row.get("edition_id", ""),
                "reason": row.get("why_provisional", ""),
                "manifest_url": row.get("manifest_url", ""),
                "status": row.get("status", ""),
            })
        if row.get("status") == "manifest_backed" and not row.get("manifest_url"):
            bad_rows.append({
                "edition_id": row.get("edition_id", ""),
                "citation_ref": "",
                "reason": "manifest_backed_missing_manifest_url",
                "source_file": "iiif_manifests.csv",
                "source_row": "",
            })
        if row.get("status") == "provisional" and not row.get("why_provisional"):
            bad_rows.append({
                "edition_id": row.get("edition_id", ""),
                "citation_ref": "",
                "reason": "provisional_missing_why_provisional",
                "source_file": "iiif_manifests.csv",
                "source_row": "",
            })

    # Check iiif_map rows against citations + status correctness
    for row in iiif_map:
        key = (row.get("edition_id", ""), row.get("citation_ref", ""))
        if key not in citation_keys:
            bad_rows.append({
                "edition_id": row.get("edition_id", ""),
                "citation_ref": row.get("citation_ref", ""),
                "reason": "iiif_map_missing_citation",
                "source_file": "citation_iiif_map.csv",
                "source_row": "",
            })
        if row.get("status") == "manifest_backed" and not row.get("manifest_url"):
            bad_rows.append({
                "edition_id": row.get("edition_id", ""),
                "citation_ref": row.get("citation_ref", ""),
                "reason": "iiif_map_manifest_backed_missing_manifest_url",
                "source_file": "citation_iiif_map.csv",
                "source_row": "",
            })

    missing_iiif.sort(key=lambda r: (r.get("edition_id", ""), r.get("citation_ref", "")))
    missing_manifest.sort(key=lambda r: r.get("edition_id", ""))
    ambiguous.sort(key=lambda r: (r.get("edition_id", ""), r.get("citation_ref", "")))
    bad_rows.sort(key=lambda r: (r.get("edition_id", ""), r.get("citation_ref", "")))

    write_csv(out_dir / "needs_review_missing_iiif.csv", MISSING_IIIF_HEADER, missing_iiif)
    write_csv(out_dir / "needs_review_missing_manifest.csv", MISSING_MANIFEST_HEADER, missing_manifest)
    write_csv(out_dir / "needs_review_ambiguous_iiif.csv", AMBIGUOUS_HEADER, ambiguous)
    write_csv(out_dir / "needs_review_bad_rows.csv", BAD_ROWS_HEADER, bad_rows)

    # Validation report
    report_lines: List[str] = []
    report_lines.append("# Phase 1 Validation Report")
    report_lines.append("")
    report_lines.append("Inputs:")
    report_lines.append(f"- citations.csv: {len(citations)} rows")
    report_lines.append(f"- citation_iiif_map.csv: {len(iiif_map)} rows")
    report_lines.append(f"- iiif_manifests.csv: {len(manifests)} rows")
    report_lines.append("")
    report_lines.append("Coverage (non-TEI editions in scope):")
    for edition_id in NON_TEI_IN_SCOPE:
        edition_citations = citations_by_edition.get(edition_id, [])
        if not edition_citations:
            continue
        total = len(edition_citations)
        mapped = sum(1 for row in edition_citations if (edition_id, row.get("citation_ref", "")) in iiif_keys)
        pct = 0 if total == 0 else int(round(mapped * 100 / total))
        status = next((m.get("status", "") for m in manifests if m.get("edition_id") == edition_id), "")
        report_lines.append(f"- {edition_id}: {mapped}/{total} ({pct}%) status={status}")
    report_lines.append("")
    report_lines.append("Provisional manifests:")
    if missing_manifest:
        for row in missing_manifest:
            report_lines.append(f"- {row.get('edition_id')}: {row.get('reason')}")
    else:
        report_lines.append("- none")
    report_lines.append("")
    report_lines.append("Needs review counts:")
    report_lines.append(f"- needs_review_missing_manifest.csv: {len(missing_manifest)}")
    report_lines.append(f"- needs_review_missing_iiif.csv: {len(missing_iiif)}")
    report_lines.append(f"- needs_review_ambiguous_iiif.csv: {len(ambiguous)}")
    report_lines.append(f"- needs_review_bad_rows.csv: {len(bad_rows)}")

    (out_dir / "validation_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 1 outputs")
    parser.add_argument("--in-dir", default="data/vnext", help="Input directory for vnext artifacts")
    parser.add_argument("--out-dir", default="data/vnext", help="Output directory")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)

    validate(
        citations_csv=in_dir / "citations.csv",
        manifests_csv=in_dir / "iiif_manifests.csv",
        iiif_map_csv=in_dir / "citation_iiif_map.csv",
        out_dir=out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
