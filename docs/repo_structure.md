# Repo structure (authoritative)

This document describes the intended structure of the repository and the rules for keeping it orderly.

## Principles

- **Archive, don’t delete**: superseded plans, experiments, and one-off outputs go under `archive/YYYY-MM-DD/`.
- **Separate living vs stable docs**:
  - `planning/` is frequently updated.
  - `docs/` changes less frequently and defines conventions.
- **Deterministic pipeline**: scripts should produce the same outputs given the same inputs (stable sorting, stable headers).
- **Keep canonical outputs in one place**: canonical CSVs and derived exports live under `data/`.

## Directories

### `planning/` (living)

- Work tracking and iteration control:
  - plan: `plan.md`
  - checklist: `planning/wbs.md`
  - decisions: `planning/decisions.md`

### `docs/` (specs)

- Conventions and definitions:
  - IDs and stability: `docs/ids.md`
  - Data model: `docs/data_model.md`
  - TEI standoff mapping: `docs/standoff_mapping.md`

### `archive/` (immutable snapshots)

- Dated snapshots of superseded docs/experiments.
- Do not edit in place.

### `revised_ed/` (working inputs)

- Working TSV exports/edits used during alignment experiments.
- Treat as a source for normalization, not as a final canonical schema.

### `src/` (TEI/XML sources)

- Source TEI/XML editions (large files).
- Early workflow uses **standoff mapping** rather than editing TEI directly.

### `scripts/` (pipeline scripts)

- Python 3, stdlib-only where possible.
- Runnable from repo root.

### `data/` (canonical outputs)

Current canonical outputs already exist here (e.g., `entries.csv`, `alignments.csv`, `master_*` exports, `dmm.db`).

During greenfielding:
- avoid silently overwriting canonical files; prefer new outputs with explicit names/paths, then promote intentionally.
- when promoting, record the decision and update the WBS.

### `data/vnext/` (transition area; canonical for vNext)

- New Phase 1+ canonical artifacts live here while we greenfield:
  - `citations.csv`
  - `iiif_manifests.csv`
  - `iiif_source_rules.csv`
  - `citation_iiif_map.csv`
  - validation + `needs_review_*.csv` outputs
