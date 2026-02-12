#!/usr/bin/env python3
"""Build data/vnext/citation_iiif_map.csv and needs_review queues.

Deterministic, stdlib-only, no network access.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


CITATION_IIIF_HEADER = [
    "edition_id",
    "citation_ref",
    "manifest_url",
    "canvas_id",
    "canvas_label",
    "canvas_index",
    "target_url",
    "status",
    "notes",
]

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

NON_TEI_IN_SCOPE = ["barbaro", "desmoulins", "lusitanus", "ruellius", "wechel"]


@dataclass
class ManifestInfo:
    edition_id: str
    manifest_url: str
    status: str
    why_provisional: str


@dataclass
class IiifRule:
    edition_id: str
    iiif_kind: str
    manifest_url: str
    image_base_url: str
    citation_key_field: str
    target_rule: str
    target_template: str
    canvas_index_base: Optional[int]
    notes: str


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


def load_manifest(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_canvas_ids(manifest: Dict) -> List[str]:
    if not manifest:
        return []
    if "items" in manifest and isinstance(manifest["items"], list):
        canvases = manifest["items"]
        ids = []
        for c in canvases:
            if isinstance(c, dict) and "id" in c:
                ids.append(c["id"])
        return ids
    if "sequences" in manifest:
        sequences = manifest.get("sequences") or []
        if sequences:
            canvases = sequences[0].get("canvases") or []
            ids = []
            for c in canvases:
                if isinstance(c, dict):
                    cid = c.get("@id") or c.get("id")
                    if cid:
                        ids.append(cid)
            return ids
    return []


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if v.isdigit():
        return int(v)
    return None


def load_manifests(manifest_csv: Path) -> Dict[str, ManifestInfo]:
    rows = read_csv(manifest_csv)
    out: Dict[str, ManifestInfo] = {}
    for row in rows:
        edition_id = row.get("edition_id", "")
        out[edition_id] = ManifestInfo(
            edition_id=edition_id,
            manifest_url=row.get("manifest_url", ""),
            status=row.get("status", ""),
            why_provisional=row.get("why_provisional", ""),
        )
    return out


def load_rules(rules_csv: Path) -> Dict[str, IiifRule]:
    rows = read_csv(rules_csv)
    out: Dict[str, IiifRule] = {}
    for row in rows:
        edition_id = row.get("edition_id", "")
        base = row.get("canvas_index_base", "")
        base_int = int(base) if base.isdigit() else None
        out[edition_id] = IiifRule(
            edition_id=edition_id,
            iiif_kind=row.get("iiif_kind", ""),
            manifest_url=row.get("manifest_url", ""),
            image_base_url=row.get("image_base_url", ""),
            citation_key_field=row.get("citation_key_field", ""),
            target_rule=row.get("target_rule", ""),
            target_template=row.get("target_template", ""),
            canvas_index_base=base_int,
            notes=row.get("notes", ""),
        )
    return out


def parse_extra_json(citation: Dict[str, str]) -> Dict[str, str]:
    raw = citation.get("extra_json", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        return {"_extra_json_parse_error": raw}
    return {}


def get_citation_value(citation: Dict[str, str], field: str, extra: Dict[str, str]) -> str:
    if field.startswith("extra_json."):
        key = field.split(".", 1)[1]
        return extra.get(key, "")
    return citation.get(field, "")


TEITOK_PATTERN = re.compile(r"\{\{(\d+)%(-?\d+)%([A-Za-z0-9_.]+)\}\}")


def render_template(template: str, citation: Dict[str, str], extra: Dict[str, str], context: Dict[str, str]) -> str:
    def replace(match: re.Match) -> str:
        width = int(match.group(1))
        offset = int(match.group(2))
        field = match.group(3)
        value = get_citation_value(citation, field, extra)
        if value is None or value == "":
            raise ValueError(f"missing_field:{field}")
        if not str(value).isdigit():
            raise ValueError(f"non_numeric_field:{field}")
        num = int(value) + offset
        if width <= 0:
            return str(num)
        return str(num).zfill(width)

    rendered = TEITOK_PATTERN.sub(replace, template)
    return rendered.format(**context)


def build_target(
    citation: Dict[str, str],
    rule: IiifRule,
    manifest_info: ManifestInfo,
    manifest: Optional[Dict],
) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    status = manifest_info.status or "provisional"
    manifest_url = manifest_info.manifest_url or rule.manifest_url

    citation_key_field = rule.citation_key_field
    extra = parse_extra_json(citation)
    citation_key_value = get_citation_value(citation, citation_key_field, extra) if citation_key_field else ""
    if citation_key_field and not citation_key_value:
        return None, "missing_citation_key_field"

    if rule.target_rule == "canvas_index":
        idx_value = parse_int(citation_key_value)
        if idx_value is None:
            return None, "missing_or_non_numeric_index"
        base = rule.canvas_index_base if rule.canvas_index_base is not None else 0
        canvas_index = idx_value - base
        if canvas_index < 0:
            return None, "negative_canvas_index"
        canvas_id = ""
        if manifest:
            canvases = extract_canvas_ids(manifest)
            if canvas_index >= len(canvases):
                return None, "canvas_index_out_of_range"
            canvas_id = canvases[canvas_index]
        return {
            "edition_id": citation["edition_id"],
            "citation_ref": citation["citation_ref"],
            "manifest_url": manifest_url,
            "canvas_id": canvas_id,
            "canvas_label": citation.get("page_label", ""),
            "canvas_index": str(canvas_index),
            "target_url": "",
            "status": status,
            "notes": "",
        }, None

    if rule.target_rule in ("canvas_id_template", "image_api_template", "target_url_template"):
        template = rule.target_template
        if not template:
            return None, "missing_target_template"
        context = dict(citation)
        context["citation_key_value"] = citation_key_value
        context["citation_key_field"] = citation_key_field
        try:
            rendered = render_template(template, citation, extra, context)
        except (KeyError, ValueError):
            return None, "template_missing_fields"
        if rule.target_rule == "canvas_id_template":
            return {
                "edition_id": citation["edition_id"],
                "citation_ref": citation["citation_ref"],
                "manifest_url": manifest_url,
                "canvas_id": rendered,
                "canvas_label": citation.get("page_label", ""),
                "canvas_index": "",
                "target_url": "",
                "status": status,
                "notes": "",
            }, None
        # image_api_template or target_url_template
        return {
            "edition_id": citation["edition_id"],
            "citation_ref": citation["citation_ref"],
            "manifest_url": manifest_url,
            "canvas_id": "",
            "canvas_label": "",
            "canvas_index": "",
            "target_url": rendered,
            "status": status,
            "notes": "",
        }, None

    return None, "unsupported_target_rule"


def build_maps(
    citations_csv: Path,
    manifests_csv: Path,
    rules_csv: Path,
    manifest_dir: Path,
    out_dir: Path,
) -> None:
    citations = read_csv(citations_csv)
    manifests = load_manifests(manifests_csv)
    rules = load_rules(rules_csv) if rules_csv.exists() else {}

    map_rows: List[Dict[str, str]] = []
    missing_iiif: List[Dict[str, str]] = []
    ambiguous: List[Dict[str, str]] = []
    bad_rows: List[Dict[str, str]] = []

    for citation in citations:
        edition_id = citation.get("edition_id", "")
        citation_ref = citation.get("citation_ref", "")
        rule = rules.get(edition_id)
        if rule is None:
            if edition_id in NON_TEI_IN_SCOPE:
                missing_iiif.append({
                    "edition_id": edition_id,
                    "citation_ref": citation_ref,
                    "reason": "missing_iiif_rule",
                    "citation_key_field": "",
                    "citation_key_value": "",
                    "source_file": citation.get("source_file", ""),
                    "source_row": citation.get("source_row", ""),
                })
            continue

        manifest_info = manifests.get(edition_id, ManifestInfo(edition_id, "", "provisional", ""))
        manifest_path = manifest_dir / f"{edition_id}.json"
        manifest = load_manifest(manifest_path)

        target, err = build_target(citation, rule, manifest_info, manifest)
        if err:
            missing_iiif.append({
                "edition_id": edition_id,
                "citation_ref": citation_ref,
                "reason": err,
                "citation_key_field": rule.citation_key_field,
                "citation_key_value": citation.get(rule.citation_key_field, ""),
                "source_file": citation.get("source_file", ""),
                "source_row": citation.get("source_row", ""),
            })
            continue
        if target is None:
            bad_rows.append({
                "edition_id": edition_id,
                "citation_ref": citation_ref,
                "reason": "no_target_produced",
                "source_file": citation.get("source_file", ""),
                "source_row": citation.get("source_row", ""),
            })
            continue
        map_rows.append(target)

    # detect ambiguous duplicates
    seen: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for row in map_rows:
        key = (row["edition_id"], row["citation_ref"])
        seen.setdefault(key, []).append(row)

    final_rows: List[Dict[str, str]] = []
    for key, items in seen.items():
        if len(items) == 1:
            final_rows.append(items[0])
            continue
        targets = ";".join(sorted({i.get("canvas_id", "") or i.get("target_url", "") for i in items}))
        ambiguous.append({
            "edition_id": key[0],
            "citation_ref": key[1],
            "reason": "multiple_targets",
            "targets": targets,
        })

    final_rows.sort(key=lambda r: (r.get("edition_id", ""), r.get("citation_ref", "")))

    write_csv(out_dir / "citation_iiif_map.csv", CITATION_IIIF_HEADER, final_rows)

    # needs_review_missing_manifest: all provisional manifests
    missing_manifest: List[Dict[str, str]] = []
    for edition_id, info in manifests.items():
        if info.status == "provisional":
            missing_manifest.append({
                "edition_id": edition_id,
                "reason": info.why_provisional,
                "manifest_url": info.manifest_url,
                "status": info.status,
            })

    missing_manifest.sort(key=lambda r: r.get("edition_id", ""))
    missing_iiif.sort(key=lambda r: (r.get("edition_id", ""), r.get("citation_ref", "")))
    ambiguous.sort(key=lambda r: (r.get("edition_id", ""), r.get("citation_ref", "")))
    bad_rows.sort(key=lambda r: (r.get("edition_id", ""), r.get("citation_ref", "")))

    write_csv(out_dir / "needs_review_missing_manifest.csv", MISSING_MANIFEST_HEADER, missing_manifest)
    write_csv(out_dir / "needs_review_missing_iiif.csv", MISSING_IIIF_HEADER, missing_iiif)
    write_csv(out_dir / "needs_review_ambiguous_iiif.csv", AMBIGUOUS_HEADER, ambiguous)
    write_csv(out_dir / "needs_review_bad_rows.csv", BAD_ROWS_HEADER, bad_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build citation_iiif_map.csv and needs_review queues")
    parser.add_argument("--in-dir", default="data/vnext", help="Input directory for vnext artifacts")
    parser.add_argument("--out-dir", default="data/vnext", help="Output directory")
    parser.add_argument(
        "--manifest-dir",
        default="data/vnext/iiif/manifests",
        help="Directory for cached IIIF manifests",
    )
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    manifest_dir = Path(args.manifest_dir)

    build_maps(
        citations_csv=in_dir / "citations.csv",
        manifests_csv=in_dir / "iiif_manifests.csv",
        rules_csv=in_dir / "iiif_source_rules.csv",
        manifest_dir=manifest_dir,
        out_dir=out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
