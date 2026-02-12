# Decision log

This is a lightweight log of decisions that affect data/ID stability, repo structure, and workflow.

## 2026-02-10 -- Standoff-first TEI

Decision:
- Use standoff mappings for TEI anchoring until segmentation stabilizes; avoid editing `src/*.xml` during early alignment work.

Why:
- Segmentation will likely change (split/merge). Standoff mappings can change without creating churn across multiple TEI files.

Implications:
- We must define a robust selector strategy for TEI anchors (prefer TEI `xml:id`; allow fallbacks).

## 2026-02-10 -- Global work units use opaque stable IDs

Decision:
- Use citation-stable global work-unit IDs like `DMMU000001` as the canonical identifier for cross-edition retrieval.

Why:
- Encoding book/chapter/section into the ID tends to force renumbering during refinement, which breaks citation stability.

Implications:
- Maintain separate anchor metadata for human readability (e.g., anchor edition + book/chapter + sequence), but do not embed it in `unit_id`.

## 2026-02-10 -- Hybrid model (segments <-> units, optional topics)

Decision:
- Keep edition-local `segment_id` and map them to global `unit_id`. Add `topic_id` only if/when concept-level grouping is needed beyond passage alignment.

Why:
- Separates text-boundary identity (segment) from cross-edition equivalence (unit) and from concept grouping (topic).

## 2026-02-10 -- IIIF is required for non-TEI navigability

Decision:
- For any edition/scope where TEI transcription is missing or unreliable, treat **IIIF navigation links** as required data.

Why:
- Many editions are image-only at this stage; we still need a complete "open in facsimile" path for every citation/segment we track.

Implications:
- Phase 1 includes an IIIF manifest registry + citation/segment->canvas mapping, with validation and `needs_review` outputs.

## 2026-02-10 -- IIIF manifests required when available; otherwise provisional

Decision:
- Require IIIF Presentation **manifests** for any edition where we can identify them.
- If an edition cannot (yet) be tied to a manifest, treat it as **provisional** and track the gap explicitly until resolved.

Why:
- Manifests provide stable canvas identity and better long-term interoperability than ad-hoc image links.

Implications:
- Validation should distinguish "manifest-backed" coverage (preferred / target state).
- Validation should distinguish "provisional" coverage (allowed temporarily; must be flagged).

## 2026-02-11 -- Phase 1 vNext outputs use CSV (RFC4180)

Decision:
- Phase 1 canonical outputs under `data/vnext/` are **CSV** (RFC4180) with stable headers and stable row ordering.

Why:
- Existing Phase 1 stubs are already `.csv` (e.g., `data/vnext/iiif_manifests.csv`), and multiple specs reference `.csv` filenames.
- Keeping a single format avoids mixing CSV/TSV during greenfielding and reduces accidental format drift.

Implications:
- Phase 1 scripts must emit CSV with deterministic column order and quoting rules.
- A future switch to TSV must be recorded as a new decision and applied consistently across vNext outputs.

## 2026-02-11 -- citation_ref collision policy (Phase 1)

Decision:
- If two or more rows within the same edition produce the same base `citation_ref`, append a stable suffix `-r{source_row}` to all colliding rows.
- Record the collision in `extra_json` for each affected row (include the base and resolved values).

Why:
- Collisions must be visible without breaking determinism or silently dropping rows.

Implications:
- Phase 1 citation normalization must do a collision pass before writing `citations.csv`.
