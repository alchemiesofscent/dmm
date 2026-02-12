# DMM Plan (current)

Last updated: 2026-02-10

This is the current, living plan for greenfielding the repo **with archiving**. Superseded planning docs are preserved in `archive/2026-02-10/`.

## 1) Objective

Build a stable, reproducible data model and workflow for aligning multiple editions/translations of *Dioscorides, De Materia Medica* at **sub-chapter segment** granularity, while supporting:
- citation-stable global IDs,
- edition-local TEI anchoring,
- IIIF-based navigation for image-only sources,
- deterministic derived exports (wide/QC tables, alignment views),
- and long-term maintainability of repo structure and documentation.

## 2) Core decisions (locked for this iteration)

- **Standoff-first TEI**: do not edit `src/*.xml` until segmentation stabilizes; store mappings in separate files.
- **Hybrid identifiers**:
  - `segment_id` = edition-local textual segment (anchored to an edition’s TEI via `xml:id` / pointer).
  - `unit_id` = global *work unit* ID (`DMMU000001`, citation-stable).
  - optional `topic_id` = concept/substance grouping across units (many-to-many).

## 3) Definitions (what we mean)

- **Citation**: edition-local printed structure (book/chapter/etc.) used for human reference.
- **Segment**: the smallest edition-local chunk we will align 1:1 where possible (sub-chapter granularity).
- **Work unit** (`unit_id`): the smallest cross-edition chunk intended to represent “the same textual unit” across witnesses; the global alignment atom.
- **Alignment**: mapping between edition-local segments and global work units; during refinement it may be 1:N / N:1, but the goal is 1:1 at segment granularity.

## 4) Repo structure (target)

- `planning/` — living plan/WBS/decision log.
- `docs/` — stable-ish specs (IDs, schemas, standoff mapping conventions, repo structure).
- `archive/` — immutable snapshots of superseded docs/experiments.
- `revised_ed/` — current TSV exports/edits (treated as working inputs until normalized).
- `data/` — canonical derived outputs (CSV/DB) produced by scripts.

See `docs/repo_structure.md` for the authoritative “what goes where” rules (to be written).

## 5) Execution phases (high level)

### Phase 0 — Evaluate & reset planning (docs-only)

Deliverables:
- `planning/decisions.md` with the decisions above recorded + any new ones.
- `planning/wbs.md` as the living checklist that we update every session.
- `docs/` specs drafted (IDs, data model, standoff mapping format).

Exit criteria:
- We agree on terminology and the minimum canonical tables/files.
- We agree on `unit_id` stability rules (including split/merge handling).

### Phase 1 — Normalize `revised_ed/*.tsv` into a canonical citation layer

Deliverables (draft names):
- a single canonical `citations` table/file with per-edition printed refs + provenance
- normalization rules for inconsistent headings across TSVs
- **validation checks + reports** for coverage and navigability (TEI vs IIIF)
- citation-level IIIF mapping (`citation_ref → IIIF target`) for non-TEI editions (segment-level comes later)
- an IIIF manifest auto-linking procedure (spec-first; then implement)

Exit criteria:
- every edition has a consistent, queryable citation reference system.
- for editions/chapters without TEI transcription, we have **complete IIIF manifest + page/canvas coverage** (so every citation/segment can be opened in images).

Implementation note:
- During transition, Phase 1 artifacts are written to `data/vnext/` (see `docs/repo_structure.md`).

### Phase 2 — Define segments and start standoff mappings

Deliverables:
- an edition-local `segments` table/file (initially derived from citations; later TEI-anchored)
- a `segment_unit_map` linking segments → `unit_id` (goal: converge to 1:1)

Exit criteria:
- for the “core” editions, we can fetch all aligned witnesses for any `unit_id`.

### Phase 3 — TEI anchoring (still standoff; inline later only if desired)

Deliverables:
- standoff pointers from `segment_id` → TEI `xml:id` / XPath / other robust selectors
- validation checks (missing anchors, duplicates, out-of-order anchors)

Exit criteria:
- segments are navigable back to the TEI sources with stable pointers.

### Phase 4 — QC outputs and stability freeze

Deliverables:
- wide/QC tables keyed by `unit_id`
- a process for freezing `unit_id` assignments (citation stability)

Exit criteria:
- `unit_id` is considered citation-stable for the frozen scope/version.

## 6) Where to track work

- Work checklist: `planning/wbs.md`
- Decision log: `planning/decisions.md`
- Clarifying Q/A: `plan_questions.md`
