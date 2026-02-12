# TEI standoff mapping (authoritative)

Goal: connect edition-local segments to TEI locations **without** editing the TEI during early refinement.

## What gets mapped

At minimum we need:
- `segment_id` → TEI anchor (where the segment lives in that edition’s TEI)
- `segment_id` → `unit_id` (which global work unit it corresponds to)

## Recommended mapping files (proposal)

### 1) Segment → TEI anchor

File (example path):
- `data/vnext/segment_tei_anchor.csv` (or `.tsv` if preferred)

Columns (minimum):
- `edition_id`
- `tei_file` (repo-relative path under `src/` when applicable)
- `segment_id`
- `anchor_type` (`xml_id` | `xpath` | `range` | `other`)
- `anchor_value` (e.g., `div-13` / `seg-2` / an XPath)
- `notes`

Rules:
- Prefer `xml:id` anchors whenever possible.
- If XPath is used, keep it robust (avoid brittle positional selectors).

### 2) Segment → unit mapping (alignment)

File (example path):
- `data/vnext/segment_unit_map.csv`

Columns (minimum):
- `segment_id`
- `unit_id`
- `status` (`draft` | `reviewed` | `frozen`)
- `confidence` (optional; if used, define allowed values)
- `notes`
- `source` (optional provenance: who/where/when)

Cardinality:
- During refinement, allow 1:N and N:1 (and record a QC flag).
- Target state is 1:1 at segment granularity where possible.

## Why standoff first

- Segment boundaries and alignments change early; changing standoff tables is cheaper than rewriting TEI across multiple editions.
- Once stable, we can optionally embed `@corresp`/IDs into TEI as a later, deliberate step.

## IIIF navigation mapping (for non-TEI / poor OCR editions)

Many editions are image-only (or effectively image-only due to OCR quality). For those, IIIF mappings are part of the *minimum viable navigability* layer.

### 3) Edition → IIIF manifest registry

File (example path):
- `data/vnext/iiif_manifests.csv`

Columns (minimum):
- `edition_id`
- `manifest_url`
- `status` (`manifest_backed` | `provisional`)
- `why_provisional` (required when `status=provisional`)
- `label` (optional)
- `notes` (optional)

Validation rule:
- For any edition that lacks TEI transcription for a scope, a manifest should be provided when findable; otherwise mark as `provisional` and track until resolved.

### 4) Citation/segment → IIIF target

File (example path):
- `data/vnext/citation_iiif_map.csv` (citation-level) and/or `data/vnext/segment_iiif_map.csv` (segment-level)

Columns (minimum; citation-level):
- `edition_id`
- `citation_ref`
- `manifest_url` (or a `manifest_id` if you normalize)
- `canvas_id` (or page identifier)
- `xywh` (optional; for region targeting)
- `notes`

Rule of thumb:
- Start with citation-level mapping (page/canvas). Move to segment-level (canvas + region) only when needed.

## IIIF auto-linking procedure (design requirement)

To reduce manual work, design the ingestion so that many IIIF links can be derived automatically from per-edition source configuration plus citation metadata.

Suggested approach:
- Maintain a per-edition IIIF source registry (manifest URL or Image API base) plus rules for interpreting any `*_iiif` / `scan_id` / page fields found in `revised_ed/*.tsv`.
- Generate `citation_iiif_map.csv` deterministically when possible; emit `needs_review_missing_iiif.csv` when not.

See `docs/iiif_autolinking.md` for the specification to write down before implementing any scripts.
