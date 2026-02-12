# Phase 1 Execution Plan (Citations + IIIF)

Last updated: 2026-02-12

Purpose: define exactly what Phase 1 will build, how it will be tested, how progress will be tracked, and what "done" means. This is a planning document only; no Phase 1 pipeline code is implemented here.

**Scope**

Phase 1A -- Citations normalization
Normalize `revised_ed/*.tsv` into a canonical citation layer. Output: `data/vnext/citations.csv`. Requirements: deterministic row order, stable headers, provenance fields (`source_file`, `source_row`), lossless carry-through (`extra_json` or equivalent).

Phase 1B -- IIIF mapping (citation-level)
Maintain IIIF registries and auto-linking rules for citation-level navigation. Output registries: `data/vnext/iiif_manifests.csv`, `data/vnext/iiif_source_rules.csv`. Output mapping: `data/vnext/citation_iiif_map.csv`. Requirement: non-TEI editions in scope must have 100% citation-level IIIF targets, with manifest-backed links preferred.

Phase 1C -- Validation
Validate schema + navigability + coverage. Output: `data/vnext/validation_report.md` plus `needs_review_*` queues.

Non-scope (Phase 1)
- Segment-level IIIF mapping.
- TEI edits or TEI-embedded anchors (`src/*.xml` must remain untouched).
- Any non-deterministic or network-dependent build steps.

**Editions in scope (Phase 1)**

Non-TEI editions requiring IIIF coverage (per `planning/phase1_agent_handoff.md` rule):
- `barbaro`
- `desmoulins`
- `lusitanus`
- `ruellius`
- `wechel`

TEI-backed editions with citation TSVs (citations normalization only):
- `berendes`
- `gunther`
- `laguna`
- `matthioli`
- `wellmann`

**Milestones and outputs**

Milestone M1 -- Citations normalization. Outputs (all under `data/vnext/`):
- `citations.csv`

Milestone M2 -- IIIF registries + auto-linking. Outputs (all under `data/vnext/`):
- `iiif_manifests.csv`
- `iiif_source_rules.csv`
- `citation_iiif_map.csv`
- `needs_review_missing_manifest.csv`
- `needs_review_missing_iiif.csv`
- `needs_review_ambiguous_iiif.csv`
- `needs_review_bad_rows.csv`

Milestone M3 -- Validation. Outputs (all under `data/vnext/`):
- `validation_report.md`
- `needs_review_missing_manifest.csv`
- `needs_review_missing_iiif.csv`
- `needs_review_ambiguous_iiif.csv`
- `needs_review_bad_rows.csv`

**Current status (from `planning/wbs.md`)**

- [x] Phase 0 specs written (citations, IIIF, validation, data model, IDs, repo structure).
- [x] Canonical `citations` schema defined.
- [x] IIIF manifest registry and citation->IIIF mapping formats defined.
- [x] `data/vnext/iiif_manifests.csv` initialized with provisional rows.
- [ ] Upgrade provisional editions to `manifest_backed` as manifests are found.
- [x] Define/implement validation checks + `needs_review_*` outputs.
- [x] Implement Phase 1 scripts (build citations, build IIIF map, validate).
- [x] Run Phase 1 verification pass (determinism + coverage).

Run record:
- Phase 1 run completed on 2026-02-12; see `planning/phase1_run_2026-02-12.md`.
- All five non-TEI editions reached 100% citation-level IIIF coverage with provisional status.

**Implementation outline (no code)**

Planned scripts and responsibilities (names may be adjusted but intent must remain):
- `scripts/vnext_build_citations.py`: input `revised_ed/*.tsv`. Output `data/vnext/citations.csv`.
- `scripts/vnext_build_citation_iiif_map.py`: inputs `data/vnext/citations.csv`, `data/vnext/iiif_manifests.csv`, `data/vnext/iiif_source_rules.csv`. Outputs `data/vnext/citation_iiif_map.csv`, `needs_review_missing_manifest.csv`, `needs_review_missing_iiif.csv`, `needs_review_ambiguous_iiif.csv`, `needs_review_bad_rows.csv`.
- `scripts/vnext_validate_phase1.py`: inputs `data/vnext/citations.csv`, `data/vnext/iiif_manifests.csv`, `data/vnext/citation_iiif_map.csv`. Outputs `data/vnext/validation_report.md` and refreshed `needs_review_*` queues.

**Determinism requirements**

- Stable headers and field order for all CSV outputs.
- Stable row ordering based on deterministic sort keys.
- `citations.csv` sort key: `(edition_id, book_num, book_label, chapter_num, chapter_label, page_label, citation_ref, source_row)` with `None`/empty values sorted consistently.
- `citation_iiif_map.csv` sort key: `(edition_id, citation_ref)`.
- No reliance on network access during build or validation.
- Any manifest data needed for auto-linking must come from cached JSON on disk.

**Test strategy (Phase 1)**

Unit tests
- TSV dialect handling: normal header, space-delimited header (`revised_ed/beck.tsv`), no-header (`revised_ed/wellmann.tsv`).
- Roman numeral parsing for `chapter_label`, including acceptance of `IIII` when present.
- `page_label` parsing and sort-key behavior (numeric vs folio `r/v`, with a deterministic fallback).
- `citation_ref` construction and per-edition uniqueness checks.

Golden fixtures
- Minimal sample inputs under `tests/fixtures/revised_ed/`.
- Expected outputs under `tests/fixtures/expected/vnext/`.

Integration tests
- End-to-end build of citations + IIIF mapping using fixtures.
- Determinism test: run build twice and compare output hashes for each `data/vnext/*.csv` and `validation_report.md`.

Validation tests
- Confirm each `needs_review_*` queue is produced when expected.
- Enforce 100% IIIF coverage for non-TEI in-scope editions, unless explicitly in bootstrap mode (see decision register).

**Acceptance criteria / Definition of Done (Phase 1)**

- `data/vnext/citations.csv` is produced with stable headers and deterministic row ordering.
- `data/vnext/iiif_manifests.csv` is populated with correct statuses; manifest-backed rows include `manifest_url`, provisional rows include `why_provisional`.
- `data/vnext/iiif_source_rules.csv` exists and is sufficient to derive citation-level IIIF targets for in-scope non-TEI editions.
- `data/vnext/citation_iiif_map.csv` includes a unique row for every `(edition_id, citation_ref)` in scope.
- For each non-TEI edition in scope, IIIF coverage is 100% (manifest-backed preferred; provisional allowed but flagged).
- Validation outputs are generated deterministically and surface any gaps via `needs_review_*` queues.
- No Phase 1 step requires network access; manifests are read from cached JSON when needed.

**Risks / unknowns**

- Meaning of edition-specific `*_iiif` keys in `revised_ed/*.tsv` (especially `barbaro_iiif`, `lusitanus_iiif`).
- Manifest discovery for non-TEI editions and long-term stability of their IIIF identifiers.
- Edition ID alignment for `ruel.tsv` (expected `ruellius`) and `moulins.tsv` (expected `desmoulins`).
- `citation_ref` uniqueness when source files lack explicit identifiers.
- Page label ordering across mixed numeric and folio formats.

**Decision register (must resolve now)**

1. CSV vs TSV for vNext outputs. Recommendation: use RFC4180 CSV for all Phase 1 `data/vnext/*` outputs. Rationale: existing stubs and specs already reference `.csv`; uniformity reduces drift. Status: **Decided**. See `planning/decisions.md` (2026-02-11).
2. Strict vs bootstrap mode for IIIF coverage. Recommendation: strict for non-TEI in-scope editions, with provisional manifests allowed but **no missing citation targets**; gaps go to `needs_review_missing_iiif.csv` and fail validation. Rationale: Phase 1's primary deliverable is navigability for image-only editions. Status: **Decided** (strict coverage enforced in validation for the 2026-02-12 run).
3. `citation_ref` construction + collision policy. Recommendation: derive a deterministic `citation_ref` from the most specific available printed reference; on collision, append a stable suffix (e.g., `-r{source_row}`) and emit `needs_review_bad_rows.csv`. Rationale: collisions must be visible and stable without breaking determinism. Status: **Decided** (see `planning/decisions.md`, 2026-02-11).
4. Manifest cache layout on disk. Recommendation: `data/vnext/iiif/manifests/<edition_id>.json` with a sidecar checksum file if needed. Rationale: keeps cached assets local, deterministic, and edition-addressable without network access. Status: **Pending**.
5. `iiif_key` semantics per edition. Recommendation: treat `iiif_key` as an opaque string and interpret it only via `iiif_source_rules.csv`. Rationale: avoids accidental numeric assumptions and makes rule changes explicit. Status: **Implemented in Phase 1 run; formal decision pending**.
6. `page_label` sort key fallback. Recommendation: parse numeric and folio forms when possible; otherwise preserve deterministic lexical ordering with a documented fallback. Rationale: consistent ordering is required for deterministic outputs even when parsing fails. Status: **Implemented in Phase 1 run; formal decision pending**.
