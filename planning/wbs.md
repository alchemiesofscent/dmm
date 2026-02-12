# WBS (living checklist)

Last updated: 2026-02-12

Update ritual (per work session):
1) update the "Last updated" date
2) check off completed tasks
3) add 1-3 "Next session" items at the top
4) record blockers/questions at the bottom

## Next session (top priority)

- [ ] Resolve manifest URLs for non-TEI editions in scope (`barbaro`, `desmoulins`, `lusitanus`, `ruellius`, `wechel`)
- [ ] Confirm `barbaro_iiif` and `lusitanus_iiif` semantics vs biusante image templates
- [ ] Replace placeholder Wechel target_url scheme with a real viewer URL

## Phase 0 -- Planning & specs (docs-only)

- [x] Write `docs/repo_structure.md`
- [x] Write `docs/ids.md` (unit/segment/topic IDs; stability; split/merge/deprecations)
- [x] Write `docs/standoff_mapping.md` (mapping file format + TEI selector rules)
- [x] Write `docs/data_model.md` (canonical tables/files + required columns)
- [x] Write `docs/validation.md` (data validation expectations)
- [x] Write `docs/iiif_autolinking.md` (manifest/canvas auto-linking design)
- [x] Write `docs/citations.md` (Phase 1 citation schema + normalization rules)
- [ ] Decide how we version "frozen" `unit_id` snapshots (tags? dated folders? both?)

## Phase 1 -- Canonical citation layer (from `revised_ed/*.tsv`)

- [x] Inventory all `revised_ed/*.tsv` headings and normalize to a standard schema (documented in `docs/citations.md`)
- [x] Define a canonical `citations` file/table (per-edition printed refs + provenance)
- [x] Decide where normalized intermediate files live (decision: keep vNext artifacts in `data/vnext/`; no `staging/`)
- [x] Define IIIF manifest registry format (per edition) for image-only / poor-OCR sources
- [x] Define citation -> IIIF page/canvas mapping format (start here; segment-level later)
- [x] Design an IIIF manifest auto-linking procedure per source (inputs, rules, failure modes)
- [x] Initialize edition manifest classification (`data/vnext/iiif_manifests.csv`)
- [ ] Define manifest cache layout and load-from-disk policy for IIIF JSON
- [x] Define `citation_ref` collision policy + visibility in `needs_review_bad_rows.csv`
- [ ] Create minimal fixtures under `tests/fixtures/revised_ed/`
- [ ] Create golden expected outputs under `tests/fixtures/expected/vnext/`
- [ ] Implement Phase 1 unit tests (TSV dialects, roman numerals, page labels, `citation_ref` uniqueness)
- [ ] Implement Phase 1 integration tests (end-to-end build)
- [ ] Add determinism test (run build twice, compare hashes)
- [ ] Add validation tests for `needs_review_*` outputs
- [ ] Add test runner / CI wiring (planning-level only)
- [ ] Upgrade provisional editions to `manifest_backed` as manifests are found
- [ ] Resolve IIIF manifest for `barbaro`
- [ ] Resolve IIIF manifest for `desmoulins`
- [ ] Resolve IIIF manifest for `lusitanus`
- [ ] Resolve IIIF manifest for `ruellius`
- [ ] Resolve IIIF manifest for `wechel`
- [x] Define validation checks + `needs_review` outputs for missing/ambiguous IIIF coverage
- [x] Implement Phase 1 scripts (see `planning/phase1_agent_handoff.md`)
- [x] Run Phase 1 verification pass (determinism + coverage)

## Phase 2 -- Segmentation + work-unit mapping

- [ ] Define what counts as a "segment" operationally (split rules, join rules, exceptions)
- [ ] Define `segments` file/table (edition-local segments, ordered)
- [ ] Define `units` file/table (global work units, ordered by anchor)
- [ ] Define `segment_unit_map` (allow 1:N/N:1 during refinement; converge to 1:1)
- [ ] Define QC flags for non-1:1 mappings ("needs segmentation" queue)

## Phase 3 -- TEI anchoring (standoff)

- [ ] Decide required TEI pointers (prefer `xml:id`; define fallback selectors)
- [ ] Define `segment_tei_anchor` mapping (segment -> TEI pointer)
- [ ] Define validation checks (missing anchors, duplicate anchors, non-monotonic order)
- [ ] Include "navigability" checks: each segment has either TEI anchor or IIIF mapping

## Phase 4 -- QC outputs and freeze process

- [ ] Define wide/QC export keyed by `unit_id` (one row per work unit)
- [ ] Define "freeze" criteria for citation-stable `unit_id` assignments
- [ ] Define change policy after freeze (deprecations/tombstones vs renumbering)

## Blockers / open questions

- [ ] Do we need `topic_id` now, or can we defer until after segment<->unit is stable?
- [ ] Which edition serves as the primary ordering anchor for `units` (likely Wellmann, but confirm)?
- [ ] Strict vs bootstrap mode for IIIF coverage in Phase 1 (non-TEI editions)
- [ ] `citation_ref` uniqueness policy for sources without explicit IDs
- [ ] Manifest cache layout on disk for offline Phase 1 builds
- [ ] Edition ID alignment for `revised_ed/ruel.tsv` -> `ruellius` and `revised_ed/moulins.tsv` -> `desmoulins`
- [ ] Meaning of `barbaro_iiif` and `lusitanus_iiif` keys (opaque vs numeric)
