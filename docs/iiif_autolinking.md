# IIIF manifest auto-linking (design)

Goal: make IIIF ingestion low-touch by deriving most navigation links from per-edition configuration + citation metadata.

This is a *design/spec* document. Implement scripts only after this is agreed.

## What “complete” means (Phase 1)

- We track IIIF at the **citation level first**.
- For each non-TEI edition in scope, every `citation_ref` must have a navigable IIIF target:
  - at minimum: a **canvas/page** target (region `xywh` optional)
- Segment-level IIIF mapping is deferred until Phase 2/3 where it is actually needed.

### Manifests vs provisional linking

- Prefer and require IIIF Presentation **manifests** whenever they can be identified for an edition.
- If a manifest cannot yet be found for an edition, allow **provisional** citation-level linking (e.g., page URLs or Image API patterns) but:
  - mark it explicitly as provisional, and
  - emit validation output so it stays on the “to fix” list.

## Inputs we expect to have

From `revised_ed/*.tsv` (varies by edition):
- some form of `scan_id`, `*_iiif`, page number, or external URL

From `src/` registries (optional but preferred):
- `src/sources.xml` as a source catalogue (where manifest/base URLs can be recorded)
- `src/dmm-defs.xml` link templates (may provide legacy URL patterns)

## Canonical registries (proposed)

### 1) `iiif_manifests` (what to open)

File:
- `data/vnext/iiif_manifests.csv`

Meaning:
- One row per edition providing a IIIF Presentation manifest URL (when available).

Concrete columns (Phase 1 proposal):
- `edition_id` (required)
- `manifest_url` (required when `status=manifest_backed`)
- `status` (required): `manifest_backed` | `provisional`
- `why_provisional` (required when `status=provisional`)
- `label` (optional)
- `homepage_url` (optional)
- `license` (optional)
- `notes` (optional)

### 2) `iiif_source_rules` (how to derive)

File:
- `data/vnext/iiif_source_rules.csv`

Purpose:
- Defines how to turn citation metadata into an IIIF target with minimal manual per-citation editing.

Suggested columns:
- `edition_id`
- `iiif_kind`: `presentation` | `image`
- `manifest_url` (if `presentation`)
- `image_base_url` (if `image`)
- `citation_key_field`: which normalized citation field is used as the lookup key (e.g., `scan_id`, `page`, `iiif_key`)
- `target_rule`: a short rule identifier (e.g., `canvas_index`, `canvas_id_template`, `image_api_template`)
- `notes`

## Auto-linking procedure (high level)

1) Normalize citations into a canonical `citations` table/file (Phase 1 output).
2) For each edition:
   - load its `iiif_source_rules`
   - attempt to derive an IIIF target for each `citation_ref`
3) Write:
   - `data/vnext/citation_iiif_map.csv` for successful derivations
   - `data/vnext/needs_review_missing_iiif.csv` for failures (include the raw citation metadata that prevented linking)

## Validation checks (Phase 1)

- Editions that are IIIF-backed must have a manifest/base URL in the registry.
- For each IIIF-backed edition in scope: `% citations with IIIF target == 100%` (or the agreed threshold during bootstrap, but record the gap explicitly).
- Detect duplicate/conflicting IIIF targets for the same `(edition_id, citation_ref)`.

Additional:
- For any edition marked `provisional`, emit a summary row in the validation report stating:
  - how linking is currently achieved (rule),
  - what is missing (manifest URL),
  - and what evidence/lead is needed to find it.

## `citation_iiif_map` (concrete schema; Phase 1 proposal)

File:
- `data/vnext/citation_iiif_map.csv`

Key:
- `(edition_id, citation_ref)` must be unique (and should match a row in canonical `citations`).

Columns:
- `edition_id` (required)
- `citation_ref` (required; matches `citations.citation_ref`)
- `manifest_url` (preferred; may be empty only when edition is provisional)
- `canvas_id` (preferred; IIIF canvas URI when known)
- `canvas_label` (optional; e.g., `020r`, `2v`, `p. 17`)
- `canvas_index` (optional; 0-based or 1-based — must be specified if used)
- `target_url` (optional fallback viewer URL if `canvas_id` unavailable)
- `status` (required): `manifest_backed` | `provisional`
- `notes` (optional)

Rationale:
- `canvas_id` is the most stable long-term pointer when a manifest exists.
- `canvas_index` can be used temporarily for auto-linking if the manifest ordering is stable and recorded.
