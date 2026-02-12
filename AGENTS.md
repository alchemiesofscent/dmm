# Repository Guidelines

## Project Structure

- `scripts/`: Python 3 (stdlib-only) pipeline scripts that generate canonical datasets.
- `data/`: canonical CSVs (`entries.csv`, `alignments.csv`, `entities.csv`, etc.) and derived QA outputs (`master_*.csv`, `semantic_alignment_flags.csv`, `data/alignments/*`).
- `data/vnext/`: vNext canonical artifacts during greenfielding (citations + IIIF registries + validation outputs). Keep new Phase 1+ artifacts here until explicitly promoted.
- `src/`: source TEI/XML editions (large files); not fully ingested by the pipeline yet.
- `revised_ed/`: working TSV exports/edits used during alignment experiments (treat as scratch unless wired into the pipeline).

## Current Planning Docs (authoritative)

- Execution plan: `plan.md`
- Living checklist: `planning/wbs.md`
- Decision log: `planning/decisions.md`
- Phase 1 agent handoff (implementation + verification): `planning/phase1_agent_handoff.md`
- Specs:
  - citations normalization: `docs/citations.md`
  - IIIF auto-linking: `docs/iiif_autolinking.md`
  - validation: `docs/validation.md`

## Build, Test, and Development Commands

Run from repo root:

```bash
python3 scripts/build_master_concordance.py --xlsx "Materia Medica.xlsx" --out-dir data
python3 scripts/assign_master_ids.py --in data/master_concordance.csv --out-dir data
python3 scripts/build_alignment_beck_berendes.py --xlsx "Materia Medica.xlsx" --out-dir data/alignments
python3 scripts/import_csv.py   # destructive: rebuilds data/dmm.db
python3 scripts/export_csv.py [table_name]
```

## Coding Style & Naming Conventions

- Python: keep scripts dependency-light (stdlib preferred), deterministic (stable sorting), and runnable from repo root.
- Data files: UTF-8, tab-separated for `*.tsv`, comma-separated for canonical `data/*.csv`.
- Column naming: prefer `edition_field` patterns (e.g., `gunther_chapter`, `barbaro_page`) and keep header order stable once published.
- Early alignment work is **standoff-first**: do not edit `src/*.xml` for segmentation/alignments until the standoff mappings and IDs are stable.

## Phase 1 Guardrails

- Deterministic outputs are mandatory (stable headers, stable sorting).
- Phase 1 writes only under `data/vnext/` unless explicitly approved.
- Phase 1 build/validate scripts must not require network access (use cached manifests on disk).
- Do not edit `src/*.xml` during Phase 1.
- Treat `docs/*.md` specs and `planning/decisions.md` as authoritative.

## Testing Guidelines

- No formal test suite. For changes to scripts, sanity-check by running the relevant pipeline step(s) and verifying row counts/diffs of the affected outputs in `data/` (or `revised_ed/` if applicable).
- For Phase 1 vNext work, the "tests" are the validation outputs in `data/vnext/` (especially `validation_report.md` and `needs_review_*.csv`), run by a separate verification agent.

## Commit & Pull Request Guidelines

- Commits: short, imperative subjects (e.g., "Build master concordance..."), focused to one change.
- PRs: describe the data impact (which files changed and why), include before/after row counts for regenerated tables, and call out any destructive steps (e.g., `scripts/import_csv.py` rebuilding `data/dmm.db`).
