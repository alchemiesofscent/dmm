# Data model (vNext, TSV-first)

This describes the *intended* canonical model as we greenfield around `revised_ed/*.tsv` and standoff TEI mappings.

It is allowed to coexist with current `data/*.csv` outputs while we transition.

During the transition, vNext canonical artifacts live under `data/vnext/` to avoid clobbering existing `data/*.csv`.

## Core tables/files (proposed)

### `editions`

Purpose:
- Reference metadata for each edition/translation/commentary.

Minimum columns:
- `edition_id`, `name`, `language`, `type`

### `citations` (edition-local printed structure)

Purpose:
- Normalized, queryable “where is it in the printed book?” layer.

Minimum columns (proposal):
- `edition_id`
- `citation_ref` (edition-local printed ref label; join key within edition)
- `source_file`, `source_row` (provenance)

Recommended additional columns:
- `book_label`, `book_num`
- `chapter_label`, `chapter_num`
- `page_label`
- `scan_id`, `iiif_key`
- `headword` and/or language-specific headword columns
- `notes`
- `extra_json` (optional lossless carry-through)

Authoritative Phase 1 schema + normalization rules live in `docs/citations.md`.

### `segments` (edition-local alignment units)

Purpose:
- The edition-local units we align (sub-chapter granularity).

Minimum columns:
- `edition_id`
- `segment_id`
- `citation_ref` (which printed unit it belongs to)
- `seq_in_citation` (ordering)
- `label` (optional human label)

### `units` (global work units)

Purpose:
- Stable global alignment atoms keyed by `unit_id`.

Minimum columns:
- `unit_id`
- `anchor_edition_id` (for ordering)
- `anchor_citation_ref`
- `anchor_seq` (sequence within anchor citation)
- `status` (`draft` | `frozen`)

### `segment_unit_map`

Purpose:
- The gold mapping between edition-local segments and global work units.

Minimum columns:
- `segment_id`
- `unit_id`
- `status` (`draft` | `reviewed` | `frozen`)
- `notes`

### `segment_tei_anchor` (standoff TEI attachment)

Purpose:
- Map `segment_id` to TEI anchors (per edition).

Minimum columns:
- `edition_id`, `tei_file`, `segment_id`, `anchor_type`, `anchor_value`, `notes`

## IIIF attachment layer (for image-only editions)

### `iiif_manifests`

Purpose:
- Registry of IIIF manifests per edition.

Minimum columns:
- `edition_id`
- `status` (`manifest_backed` | `provisional`)
- `manifest_url` (required when `status=manifest_backed`)
- `why_provisional` (required when `status=provisional`)

### `iiif_source_rules` (recommended; for auto-linking)

Purpose:
- Per-edition configuration that enables deterministic, low-touch generation of IIIF links from citation metadata (scan IDs, page numbers, or `*_iiif` keys).

Minimum columns (proposal):
- `edition_id`
- `iiif_kind` (`presentation` | `image` | `other`)
- `manifest_url` (if `presentation`)
- `image_base_url` (if `image`)
- `notes`

### `citation_iiif_map` (or `segment_iiif_map`)

Purpose:
- Ensure every citation (and optionally every segment) is navigable even without TEI transcription.

Minimum columns (citation-level):
- `edition_id`
- `citation_ref`
- `manifest_url` (or `manifest_id`)
- `canvas_id`
- `xywh` (optional)
- `notes`

## Optional concept layer

### `topics` + `unit_topic_map`

Use only if needed:
- `topic_id` groups multiple `unit_id` values under a concept (many-to-many).

## Relationship summary

- `citations` are edition-local references.
- `segments` subdivide citations to the alignment granularity.
- `units` are global and citation-stable once frozen.
- `segment_unit_map` links edition-local text to global units.
- `segment_tei_anchor` links segments back to TEI without editing TEI early.
- `iiif_manifests` + `citation_iiif_map` provide navigability for image-only sources.
