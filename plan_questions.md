# Planning / Design Questions (Pre-Plan)

Answering these will determine whether we should prefer shared cross-edition IDs, edition-local IDs + alignment tables, or a hybrid.

## Retrieval Goal

- What is the primary unit you want to retrieve across editions?
  - **(a)** “the same entry/content” (concept-level)
  - **(b)** “the same passage” (text-level)
  - **(c)** both

-- Answer: C

## Current Data Reality (`revised_ed/*.tsv`)

- What columns exist today in `revised_ed/*.tsv` (e.g., chapter/page/line/lemma/entry label), and which are stable enough to become identifiers?

-- currently, the files have different headings, and we will need to standardize them and decide on a way to either noramlize or otherwise describe their contents (or we just arbitrarily link chapter and segments, but this would hide our reasons for linking them)

## Expected Editing Dynamics

- Do you expect frequent split/merge events as you refine segmentation (one segment becomes two; two become one)?

-- its possible -- if we have a workflow where we start by linking chapters, and then when we have one to many or many to one links, we need to go in an refine until we have one to one (which should happen as we segment properly)

- How common are partial overlaps (A maps to half of B; or A maps to B+C)? If they’re common, we’ll want many-to-many alignment.

-- fairly common at the chapter level, but it will be one to one at the segment level

- Do you need to represent uncertainty / competing alignments (e.g., two plausible matches), or will there be exactly one “gold” alignment?

-- there should be one alignment since all are the same text in different editions and translations

## Stability & Citation Requirements

- Do you need IDs that are citation-stable for publications (meaning “never change”), or is “can change with versioning” acceptable?

-- yes ultimately citation stable

## TEI Target Granularity

- Is the TEI goal to mark chapters only, or also sub-chapter granularity (paragraphs, recipes, marginalia, glosses)?

-- goal is also to tag subchapter granularity as segments that can be linked one to one

## Semantics vs Text Parallels

- Will you treat “same thing” as semantic equivalence (same remedy concept) even when the wording/order differs a lot, or only when it’s clearly a parallel passage?

-- since they derive from the same text largely unchanged, they should remain similar. the text is composed of units. the units may be pacakged and arranged differently, or written in different langauges (via translation), and some texts may have units that others do not, but within units the text should be largely the same with minimal variants (dioscorides' text is fairly stable, but we should keep track of variants for sure)

---

## Assistant response (2026-02-10)

Based on your answers in `plan_questions.md:1` (goal = both concept + passage; chapter-level overlaps common; segment-level should become 1:1; IDs must become citation-stable; TEI will be segmented below chapter), I’d recommend a hybrid that keeps TEI stable while still giving you “one ID pulls all witnesses”.

**Recommendation (IDs + linking)**
- Keep **edition-local segment IDs** in TEI (`xml:id` per edition), because segmentation will evolve (split/merge) and you don’t want cross-edition IDs embedded in multiple TEIs to become brittle.
- Mint a **global “work unit” ID** (`unit_id`) that represents “the same underlying passage/unit” across editions, and store the gold mapping `edition_segment_id → unit_id` in a table (ideally 1:1 once refined; allow temporary 1:N/N:1 during refinement).
- Separately mint a **concept/topic ID** (`topic_id`) for “unique entries/substances” if you want concept-level retrieval that isn’t identical to passage boundaries; link `unit_id ↔ topic_id` (many-to-many) rather than forcing one to be the other.
- In TEI, reference `unit_id` via attributes like `@corresp` (or standoff markup) rather than making `unit_id` the TEI `xml:id`.

This gives you:
- Simple retrieval: `unit_id` pulls all aligned passages; `topic_id` pulls all units “about iris”.
- Resilience: TEI segment boundaries can change without breaking global IDs; mappings change instead.
- Citation stability: `unit_id` becomes the thing you cite, once locked.

**Key open decision (1 question)**
- Do you want TEI annotation to be **inline edits** in `src/*.xml`, or **standoff annotations** (separate mapping files) until segmentation stabilizes?

## Plan to refactor (no coding yet)

### Phase 0 — Evaluate existing plan(s) and decide vocabulary (1–2 days)
- Review `plan.md:1`, `dmm_prd_wbs.md:1`, `ALIGNER_WORKFLOW.md:1`, `ALIGNMENT_MODEL_PAUSE_NOTE.md:1` against the new greenfield TSV-first reality.
- Decide and document the canonical nouns (recommend): `edition` / `citation` (printed chapter) / `segment` (TEI subchapter unit) / `unit` (global cross-edition work unit) / `topic` (concept) / `entity` (real-world object).
- Decide ID policy: draft vs locked IDs; how split/merge is handled (tombstones + `replaces_unit_id` beats renumbering).

### Phase 1 — Clean repo structure + documentation (with archive-first)
- Create an `archive/` policy: dated snapshot folders for superseded docs and one-off experiments (keep, don’t delete).
- Define “authoritative vs scratch” directories (recommend intent):
  - `planning/` (living plan, WBS, decisions)
  - `docs/` (stable documentation: repo structure, schemas, ID spec, TEI conventions)
  - `data/` (canonical outputs)
  - `staging/` (inputs like `revised_ed/*.tsv` normalized dumps; not canonical)
- Write `docs/repo_structure.md` and `docs/ids.md` so future work stays orderly.

### Phase 2 — Canonical data model for TSV-first workflow
- Standardize `revised_ed/*.tsv` into a single schema for **citations** (edition-local printed structure), without losing provenance (keep raw columns or a `source_*` namespace).
- Define the minimal canonical tables/files you will maintain by hand vs derive:
  - `editions`
  - `citations` (per edition)
  - `segments` (per edition; later TEI-anchored)
  - `units` (global; citation-stable)
  - `segment_unit_map` (alignment; should converge to 1:1)
  - optional `topics`, `unit_topic_map`
  - optional `variants` (later)

### Phase 3 — Workflow: chapter-first, then segment refinement, then TEI anchoring
- Start with chapter-level mappings to seed coverage.
- Iteratively refine any 1:N / N:1 mappings by segmenting until segment-level is 1:1 where possible.
- Only once stable enough, “attach” segments to TEI (inline or standoff, per the open decision).

### Phase 4 — Living WBS + checklist (constantly updated)
- Replace `dmm_prd_wbs.md:1` with a new `planning/wbs.md` that is explicitly a living checklist.
- Add a lightweight update ritual: every work session updates (a) “Last updated”, (b) checked items, (c) next 3 tasks, (d) blockers.

## WBS skeleton (what the checklist should contain)
- Governance: glossary + decision log + ID policy
- Repo hygiene: archive policy + directory structure + “authoritative vs scratch”
- Data normalization: standard citation schema for all `revised_ed/*.tsv`
- Segmentation spec: what a “segment” is; how to split/merge; how to record merges
- Global units: minting + locking + deprecation rules
- Alignment: segment↔unit mapping; QC views (wide tables) + review queues
- TEI integration: anchoring strategy + conventions + validation
- Variants: how you record/locate variants (minimal viable first)
- Releases: version tags for data snapshots; reproducible rebuild instructions

If you answer the inline-vs-standoff TEI question, I can draft the actual `planning/plan.md` + `planning/wbs.md` structure (still without implementing any refactor).


**Key open decision (1 question): RESPONSE**
**standoff annotations** (separate mapping files) until segmentation stabilizes