# Data validation (authoritative)

This document defines the validation checks we expect around Phase 1+ so that the dataset remains navigable and auditable even when TEI transcription is incomplete.

## Outputs

Recommended outputs (names can change, but keep the concept):
- `data/vnext/validation_report.md` — human-readable summary (counts + top issues)
- `data/vnext/needs_review_missing_iiif.csv` — citations/segments lacking required IIIF
- `data/vnext/needs_review_missing_manifest.csv` — editions that should have manifests but are still provisional
- `data/vnext/needs_review_ambiguous_iiif.csv` — citations with multiple plausible IIIF targets
- `data/vnext/needs_review_missing_tei_anchor.csv` — segments expected to have TEI anchors but missing
- `data/vnext/needs_review_non_1_to_1.csv` — segment↔unit mapping not yet 1:1 (expected during refinement)

## Checks (minimum viable)

### 1) Schema checks

- Required columns present for canonical files.
- Controlled vocab fields only use allowed values (where defined).

### 2) ID checks

- `unit_id` uniqueness; no reuse of deprecated IDs.
- `segment_id` uniqueness per `edition_id`.

### 3) Navigability checks (TEI vs IIIF)

For each segment (or citation, depending on the stage), ensure it is navigable by at least one mechanism:
- TEI: has a valid TEI anchor (`segment_tei_anchor`)
- OR IIIF: has a valid IIIF mapping (`citation_iiif_map` / `segment_iiif_map`)

Edition-level:
- if an edition uses IIIF mappings, it should have a manifest (`iiif_manifests`) when findable; otherwise it must be explicitly marked `provisional` with a reason.

### 4) Coverage checks

- For each edition, count citations present vs expected scope.
- For non-TEI editions: % citations with IIIF coverage (target: 100% for the tracked scope).

## Where this lives in the workflow

- Phase 1: validate citation normalization + IIIF coverage for non-TEI editions.
- Phase 2+: validate segment↔unit mapping state and TEI/IIIF navigability at segment granularity.
