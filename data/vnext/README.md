# `data/vnext/`

This folder holds **vNext canonical artifacts** while the repo is being greenfielded.

It exists to avoid clobbering the current canonical outputs in `data/` (e.g., `entries.csv`, `alignments.csv`, `dmm.db`, `master_*` exports) until we intentionally promote the new pipeline.

Expected Phase 1+ artifacts:
- `citations.csv` — normalized citation layer derived from `revised_ed/*.tsv`
- `iiif_manifests.csv` — per-edition IIIF manifest registry (`manifest_backed` vs `provisional`)
- `iiif_source_rules.csv` — per-edition rules for auto-linking citations to IIIF targets
- `citation_iiif_map.csv` — citation→IIIF canvas/page targets (Phase 1)
- `validation_report.md` and `needs_review_*.csv` — validation outputs

