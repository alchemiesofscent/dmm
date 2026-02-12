# Phase 1 handoff: citations + IIIF (implementation + test)

Last updated: 2026-02-10

This document is written to be handed to “agents”:
- **Agent A (Implementer)**: implements Phase 1 pipeline and produces artifacts under `data/vnext/`.
- **Agent B (Verifier)**: runs the pipeline, checks determinism/coverage, and validates outputs without changing code.

Authoritative specs to follow:
- Citations schema + normalization: `docs/citations.md`
- IIIF registries + auto-linking: `docs/iiif_autolinking.md`
- Validation expectations: `docs/validation.md`
- Repo structure rules: `docs/repo_structure.md`

## Scope (Phase 1)

Produce a canonical citation layer from `revised_ed/*.tsv` and ensure that for **non-TEI editions**, every tracked citation can be opened via IIIF (manifest-backed preferred; provisional allowed but must be flagged).

Phase 1 is **citation-level**. Do not attempt segment-level IIIF mapping yet.

### Which editions are “non-TEI” for Phase 1?

Operational rule (until refined):
- If `data/editions.csv.tei_file` is empty for an `edition_id`, treat it as **non-TEI** and require IIIF navigability for its citations.

Initial non-TEI editions that already have citation-like TSV sources in `revised_ed/`:
- `barbaro`
- `desmoulins`
- `lusitanus`
- `ruellius`
- `wechel`

Notes:
- Some TEI-backed editions may still benefit from IIIF (facsimile navigation), but Phase 1 *requires* IIIF coverage only for non-TEI editions in scope.

## Deliverables (files in `data/vnext/`)

Required:
- `citations.csv`
- `iiif_manifests.csv` (already stubbed; fill in as manifests are identified)
- `iiif_source_rules.csv`
- `citation_iiif_map.csv`
- `validation_report.md`

Review queues (as needed):
- `needs_review_missing_manifest.csv`
- `needs_review_missing_iiif.csv`
- `needs_review_ambiguous_iiif.csv`
- `needs_review_bad_rows.csv` (parse errors, missing required fields)

## Agent A — Implementation plan (do this)

### A1) Implement citation normalization

Create a script (proposed name):
- `scripts/vnext_build_citations.py`

Inputs:
- `revised_ed/*.tsv`

Output:
- `data/vnext/citations.csv`

Requirements:
- Handle heterogeneous inputs documented in `docs/citations.md`:
  - `revised_ed/beck.tsv` header is space-delimited (normalize headers).
  - `revised_ed/wellmann.tsv` has no header row (treat first row as data).
- Deterministic output:
  - stable row ordering within `(edition_id, book_num?, chapter_num?, page_label?, citation_ref?)`
  - stable header order per `docs/citations.md`
- Preserve provenance:
  - populate `source_file` and `source_row`
  - store unmapped fields in `extra_json` (or implement an equivalent lossless strategy, but document it)

### A2) Implement IIIF registry + auto-linking (citation-level)

Create scripts (proposed names; can be combined if preferred):
- `scripts/vnext_build_iiif_registries.py` (optional; may be mostly manual for now)
- `scripts/vnext_build_citation_iiif_map.py`

Inputs:
- `data/vnext/citations.csv`
- `data/vnext/iiif_manifests.csv`
- `data/vnext/iiif_source_rules.csv`
- optional: `src/sources.xml`, `src/dmm-defs.xml` (as hints only)

Outputs:
- `data/vnext/citation_iiif_map.csv`
- `data/vnext/needs_review_missing_manifest.csv` (editions lacking manifests but expected to have them)
- `data/vnext/needs_review_missing_iiif.csv` (citations with no IIIF target)

Rules:
- If `iiif_manifests.csv.status=manifest_backed`, `manifest_url` must be non-empty.
- If `status=provisional`, `why_provisional` must be non-empty; linking may fall back to `target_url` patterns.

Implementation note:
- `data/vnext/iiif_manifests.csv` is already initialized with provisional rows for the non-TEI editions above. Agent A should upgrade rows to `manifest_backed` as manifest URLs are identified.

Auto-linking strategy (minimum viable):
- Prefer manifest-backed mapping when a manifest is available:
  - store `canvas_id` (and optionally `canvas_label`)
  - avoid relying on numeric ordering unless explicitly recorded as `canvas_index` with a declared base
- If provisional:
  - allow a stable `target_url` that opens the citation in a viewer or image endpoint
  - but emit a flag so it remains visible as technical debt

Manifest retrieval note:
- If the execution environment cannot fetch manifests over the network, treat manifest acquisition as an external/manual step and support reading cached manifest JSON from disk (e.g., `data/vnext/iiif/manifests/<edition_id>.json`).

### A3) Implement Phase 1 validation

Create a script (proposed name):
- `scripts/vnext_validate_phase1.py`

Inputs:
- `data/vnext/citations.csv`
- `data/vnext/iiif_manifests.csv`
- `data/vnext/citation_iiif_map.csv`

Outputs:
- `data/vnext/validation_report.md`
- `data/vnext/needs_review_missing_iiif.csv`
- `data/vnext/needs_review_missing_manifest.csv`

Validation checks (minimum):
- Required columns exist in each file.
- `(edition_id, citation_ref)` uniqueness in `citation_iiif_map.csv`.
- Coverage:
  - for each edition that is non-TEI for the tracked scope: 100% of citations have an IIIF target (manifest-backed preferred; provisional allowed but listed)
- Status correctness:
  - `manifest_backed` rows have `manifest_url`
  - `provisional` rows have `why_provisional`

### A4) Update docs only if needed

If implementation reveals missing clarity in specs:
- update the spec files in `docs/` (small, surgical changes)
- record any policy change in `planning/decisions.md`

## Agent B — Verification plan (do this, no code changes)

### B1) Rebuild Phase 1 outputs from scratch

Run (exact commands depend on Agent A’s script names; example):
- `python3 scripts/vnext_build_citations.py --out data/vnext`
- `python3 scripts/vnext_build_citation_iiif_map.py --in data/vnext --out data/vnext`
- `python3 scripts/vnext_validate_phase1.py --in data/vnext --out data/vnext`

### B2) Determinism check

- Run the same commands twice.
- Confirm the generated CSVs are byte-identical or at least stable in row order and values.

### B3) Coverage check

- Read `data/vnext/validation_report.md` and confirm:
  - which editions are `manifest_backed` vs `provisional`
  - % citation coverage per edition
- Spot-check a few `target_url` or `canvas_id` values for plausibility (no requirement to open them in a browser inside this environment).

### B4) Review queues

- Ensure `needs_review_missing_iiif.csv` is empty for any edition we consider “required coverage” in the current scope.
- Ensure provisional editions are explicitly listed with reasons.

## Acceptance criteria (Phase 1 “done”)

- `data/vnext/citations.csv` exists and is deterministic.
- `data/vnext/iiif_manifests.csv` is populated with correct statuses (manifest-backed where known; otherwise provisional with reasons).
- For each non-TEI edition in scope:
  - every citation has an IIIF target in `data/vnext/citation_iiif_map.csv`
  - missing manifests/targets are surfaced via `needs_review_*` outputs, not hidden.
