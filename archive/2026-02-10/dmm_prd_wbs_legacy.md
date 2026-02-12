# DMM PRD + WBS
Version: 0.1  
Last updated: 2026-02-02  
Repo scope: This document describes what the DMM repository should *build and produce* from the current sources (`src/*.xml`, `dioscmatmad_db.xml`, spreadsheets) into canonical CSVs + SQLite, plus derived “master units” and a wide alignment check table for human QC.

---

## 1) Product Requirements Document

### 1.1 Summary
DMM is a reproducible data pipeline and SQLite database for aligning multiple editions/translations/commentaries of *Dioscorides, De Materia Medica* into a single normalized alignment graph. It also records scholarly identifications (text → real-world entity) and manuscript witness readings tied to a base Greek edition.

**Core principle:** the database stores *edition-specific textual entries* and relationships between them. A “substance” is not a fixed table; it is derived from the alignment graph.

**New workflow requirement:** generate a **global, edition-agnostic ID system for the finest alignment units** (“master units”) and a **wide alignment check table** so scholars can visually inspect cross-edition alignment.

---

### 1.2 Goals (what the system must do)
1. **Normalize edition content into a common model**  
   Ingest multiple edition sources (TEI/XML; partial or complete) into `entries.csv` with stable `entries.id` values (`edition:ref[:segment]`).

2. **Represent cross-edition correspondences as a graph**  
   Store explicit alignments between entries with types: `equivalent`, `contains`, `part_of`, `related`, plus confidence and notes.

3. **Separate text from reality**  
   Store real-world objects as `entities` and link them via `identifications` (entry → entity) with confidence + notes.

4. **Attach manuscript witness readings to base Greek entries**  
   Store manuscripts and their readings (`witnesses`) linked to critical-edition entries (typically Wellmann).

5. **Derive “master alignment units” at maximum granularity**  
   Automatically compute **master units** (the smallest units implied by segmentation + contains/part_of structure), assign each a deterministic `DMM` ID, and map each master unit to the edition-specific entries that realize it.

6. **Produce a wide QC table for alignment review**  
   Output a “one row per master unit” spreadsheet-friendly table with per-edition columns (ref/term/page/anchors), prioritizing exact equivalences and falling back to nearest containing entries with clear flags.

7. **Be reproducible and auditable**  
   Given the same inputs, the pipeline produces identical outputs. All derived outputs are deterministic and can be regenerated.

---

### 1.3 Non-goals (explicitly out of scope for this build)
- Building a full public web app/UI (beyond optional basic HTML preview/export).
- Automatic botanical entity resolution against external authority APIs.
- Full text search engine beyond SQLite (no Elastic, etc.).
- Automated scholarly “reasoning” (OWL/RDF inference). RDF export may be future work.

---

### 1.4 Users & primary workflows
**User A: Scholar/editor**
- Wants to visually verify that “Iris” lines up across Berendes, Desmoulins, Mattioli, Laguna, Wechel, etc.
- Uses the wide table to spot mismatches, granularity problems, missing entries, and incorrect mappings.
- Adds/fixes alignments and re-runs pipeline.

**User B: Data builder**
- Runs scripts to ingest XML/spreadsheets, validate CSVs, build SQLite.
- Ensures stable IDs, constraints, and deterministic output.

**User C: Research consumer**
- Queries SQLite to find aligned passages, entities identified by a given edition, or witness readings.

---

### 1.5 Inputs (current repo)
- `src/*.xml` — edition XML/TEI (some partial some complete). Examples: `wellman*.xml`, `berendes*.xml`, `beck*.xml`, `matthioli.xml`, etc.
- `dioscmatmad_db.xml` — legacy XML dataset with multi-edition row alignment and botanical fields.
- `Materia Medica.ods` — spreadsheet alignment work / manual equivalence tables (format may vary by worksheet).
- Existing canonical CSVs in `data/*.csv` (may be generated or partially curated).

---

### 1.6 Outputs (authoritative deliverables)
Canonical CSVs (authoritative storage):
- `data/editions.csv`
- `data/entries.csv`
- `data/alignments.csv`
- `data/entities.csv`
- `data/identifications.csv`
- `data/manuscripts.csv`
- `data/witnesses.csv`

SQLite build:
- `data/dmm.db` (built deterministically from the CSVs)

Derived workflow/QC outputs (new requirements):
- `data/master_units.csv`
- `data/master_unit_entries.csv`
- `data/master_alignment_wide.csv` (and/or `.xlsx`)
- `data/master_units_needs_review.csv` (cycles, missing anchors, ambiguous ordering, etc.)

---

### 1.7 Canonical conceptual model (definitions)
- **Entry:** A textual reference in a specific edition at a specific location (chapter and optional segment).
- **Entity:** A real-world object (plant/animal/mineral/preparation), optionally linked to external identifiers.
- **Identification:** A scholarly attribution linking Entry → Entity with confidence and notes.
- **Alignment:** A typed relationship between two entries across editions (`equivalent`, `contains`, `part_of`, `related`) with confidence and notes.
- **Witness:** A manuscript reading for a base Greek entry, with manuscript metadata and optional IIIF pointers.
- **Master Unit:** A *derived* edition-agnostic alignment unit at maximum granularity (leaf nodes implied by contains/part_of plus segmentation).

---

### 1.8 Data model requirements (matches existing schema)

#### editions (static reference)
Must include: `id`, `name`, `language`, `type`, optional `tei_file`, optional `base_url`.

#### entries (textual references)
Required fields:
- `id`: `edition:ref[:segment]`
- `edition_id`: FK to editions
- `ref`: chapter/section string as in that edition (e.g., `1.29`, `1.4.5`)
- `segment`: nullable (e.g. `seg1`)
- `term`: as printed
Optional enrichment fields:
- `term_greek`, `term_latin`, `page`, `div_id`, `seg_id`, `url`, `notes`

#### alignments (graph edges)
- `entry_a`, `entry_b` FKs to entries
- `alignment_type`: `equivalent | contains | part_of | related`
- `confidence`: `certain | probable | uncertain`
- `UNIQUE(entry_a, entry_b)`

#### entities + identifications
Entities are unique objects; identifications are assertions.

#### manuscripts + witnesses
Witness readings link to a base-edition `entry_id` (typically Wellmann).

---

## 2) Functional Requirements

### 2.1 Ingestion: Edition XML/TEI → entries.csv
**Goal:** Parse each `src/*.xml` edition (even if partial) into `entries` rows.

**Required behaviors**
- For each edition, identify the unit(s) of reference: book/chapter (and optionally subchapter/segment).
- If TEI `<div>` or equivalent structure exists, store stable anchors:
  - `div_id` for chapter-level anchoring
  - `seg_id` for segment-level anchoring
- If `<seg>` elements exist, create `entries.segment` values (`seg1`, `seg2`, …) deterministically in document order.
- Preserve Greek polytonic text (UTF-8).

**Partial XML handling**
- If an edition is missing some chapters/terms, still create entries for what exists; missing coverage is expected.
- If the edition structure cannot provide a stable `ref`, create a temporary `ref` derived from XML position and log it to `needs_review` outputs (do not silently invent).

---

### 2.2 Ingestion: legacy dioscmatmad_db.xml → seed entries + alignments + identifications
**Goal:** Use existing legacy XML as a seed dataset.
- Extract edition-specific fields into `entries.csv`.
- Create initial `alignments.csv` by linking entries that co-occur in the same legacy row.
- Extract botanical/identification fields into `identifications.csv` and `entities.csv`.

---

### 2.3 Ingestion: Spreadsheet alignment tables (ODS) → alignments.csv (and/or entries enrichment)
**Goal:** Support importing manual alignment work from `Materia Medica.ods`.

**Required behaviors**
- Read each worksheet as a table; identify known column patterns (e.g., `dmm_id`, `berendes_id`, `desmoulins_id`, `mattioli_chapter_*`, etc.).
- Normalize these worksheet rows into “links” between edition-specific entries.
- Create entries if referenced by the spreadsheet but not yet present in `entries.csv` (optional; controlled by flag).
- Preserve traceability: store `notes` with `source_sheet` + row index + original `dmm_id` when available.

**No external dependencies requirement**
- Prefer parsing `.ods` via standard library:
  - `.ods` is a ZIP; parse `content.xml` using `zipfile` + `xml.etree.ElementTree`.
- Alternatively support a workflow where scholars export worksheets to CSVs and the pipeline ingests those CSVs.

---

### 2.4 Graph correctness & validation
**Required checks**
- Foreign keys resolve (entry IDs exist; manuscript IDs exist).
- Alignment types and confidence values are in allowed enums.
- Detect and report:
  - duplicate entry IDs
  - alignment duplicates / symmetric duplicates (A,B) vs (B,A) if you choose to treat as undirected for `equivalent`
  - cycles in `contains/part_of` relationships

Outputs:
- `data/validation_report.md` (or `.txt`) summarizing all issues.
- `data/*needs_review*.csv` listing rows requiring manual attention.

---

## 3) New Requirement: Master Units + Global DMM IDs

### 3.1 Why master units exist
Editions differ in granularity. To make a wide alignment table that is stable and reviewable, we need a *global row key* that represents the **finest alignment units implied by all editions**.

This global key must not depend on a single edition’s chaptering (e.g., Wellmann is least granular). It must reflect the **most granular breakdown available anywhere**, while still mapping back to each edition.

---

### 3.2 Master Unit derivation algorithm (deterministic)
**Inputs:** `entries.csv`, `alignments.csv`  
**Outputs:** `master_units.csv`, `master_unit_entries.csv`, and review files

#### Step 1 — Build equivalence components
- Treat `equivalent` edges as **undirected**.
- Compute connected components (e.g., Union-Find).
- Each component is an “equivalence bucket”.

#### Step 2 — Build a granularity graph between components
- Convert `contains` / `part_of` edges into directed relationships between components:
  - `contains`: coarse_component → fine_component
  - `part_of`: fine_component → coarse_component
- Collapse multiple edges between same components.

#### Step 3 — Define atomic master units as leaf components
- A component is **atomic** if it has **no outgoing `contains` edges** (i.e., it contains nothing finer).
- Atomic components become **master units**.

#### Step 4 — Select an anchor entry per master unit
To assign ordering and `(book, chapter)`:
- Compute a granularity score per entry:
  - +1 for each dot-part in `ref` (e.g., `1.4.5` has more detail than `1.4`)
  - +1 if `segment` is non-null
- Choose the entry with max score; break ties by configurable edition priority list, then `entry_id` lexicographically.

#### Step 5 — Assign `(book, chapter, section)` deterministically
- Parse `(book, chapter)` from the anchor entry’s `ref` where possible.
- Group all master units by `(book, chapter)`.
- Sort master units within each group by:
  1) anchor ref numeric subparts (e.g., `1.4.5` sorts after `1.4`)
  2) segment order (`seg1`, `seg2`…)
  3) anchor `entry_id`
- Assign `section = 1..n` in sorted order.

#### Step 6 — Construct global IDs
Use the established convention:
- `master_id = "DMM" + book + (chapter padded to 3 digits) + section`
  - Example: book=1, chapter=1, section=1 → `DMM10011`
  - Example: book=1, chapter=2, section=1 → `DMM10021`

#### Step 7 — Produce mapping table
For each master unit, list all member edition-entries:
- `master_unit_entries.csv`: `(master_id, entry_id, relationship_hint)`
  - `relationship_hint` is optional: `equivalent` for direct same-level, or `fallback_contains` if the edition only has a containing/coarser entry.

#### Step 8 — Handle errors / edge cases without stopping the pipeline
- If cycles exist in contains/part_of: write involved components to `master_units_needs_review.csv`, and proceed by breaking cycles deterministically (e.g., ignore lowest-confidence edges).
- If `(book, chapter)` cannot be parsed: assign `(book, chapter) = (0, 0)` and output to needs_review; still assign a stable section ordering inside that bucket.
- If multiple anchors tie and no priority rule resolves: pick smallest `entry_id` and log.

---

## 4) New Requirement: Wide Alignment Check Table

### 4.1 Purpose
A spreadsheet-friendly table for visual QC, with one row per master unit and columns for each edition’s corresponding entry info.

### 4.2 Output format
`data/master_alignment_wide.csv` (and optionally `.xlsx`)

Columns:
- `master_id`, `book`, `chapter`, `section`, `label`
- For each edition `<ed>` in editions.csv:
  - `<ed>_entry_id`
  - `<ed>_ref`
  - `<ed>_segment`
  - `<ed>_term` (or greek/latin variants if known)
  - `<ed>_page`
  - `<ed>_anchor` (prefer `seg_id` else `div_id`)
  - `<ed>_match_type` (`exact`, `fallback_contains`, `missing`)
  - `<ed>_notes`

### 4.3 Filling rules
For each `(master_id, edition)`:
1. Prefer an entry that is directly in the master unit’s equivalence component (“exact”).
2. If none exists, find the nearest containing/coarser entry via `part_of/contains` traversal (“fallback_contains”) and flag it.
3. If neither exists, mark “missing”.

---

## 5) CLI / Script Requirements

### 5.1 Required scripts (existing + new)
Existing (maintain/extend):
- `scripts/migrate_db.py` — legacy XML → CSV
- `scripts/import_csv.py` — CSV → SQLite
- `scripts/export_csv.py` — SQLite → CSV

New scripts (to implement):
- `scripts/ingest_editions_xml.py` — parse `src/*.xml` TEI → `entries.csv` (or additive CSV to merge)
- `scripts/ingest_spreadsheet.py` — parse `Materia Medica.ods` → `alignments.csv` (and optionally entries additions)
- `scripts/derive_master_units.py` — compute master units + IDs + mapping table
- `scripts/build_wide_alignment.py` — generate wide QC CSV/XLSX
- Optional: `scripts/build_all.py` — one command runs full pipeline end-to-end in correct order

### 5.2 Determinism requirements
- Sorting must be explicit (never rely on dict insertion).
- Tie-break rules must be explicit and documented.
- Outputs must be identical for identical inputs.

### 5.3 Dependency constraints
- Target: Python 3.8+
- Prefer standard library (`xml.etree`, `csv`, `sqlite3`, `zipfile`, `re`, `argparse`, `dataclasses`).
- If a non-stdlib dependency is introduced, it must be optional and documented.

---

## 6) Acceptance Criteria (definition of done)
1. Running `build_all.py` (or documented sequence) produces:
   - canonical CSVs
   - SQLite DB
   - master unit outputs
   - wide QC table
2. `import_csv.py` validates foreign keys and uniqueness constraints successfully.
3. Master unit IDs are stable across runs and match the documented format (`DMM{book}{chapter:03}{section}`).
4. Wide QC output includes all editions listed in `editions.csv` (columns present even if sparse).
5. Any problematic cases (cycles, missing refs, ambiguous merges) appear in `*needs_review*` outputs (not silently ignored).

---

## 7) Risks & Mitigations
- **Inconsistent ref formats across editions**  
  Mitigation: centralize ref parsing; treat as strings for storage; compute numeric sort keys separately.
- **Granularity cycles caused by manual data errors**  
  Mitigation: detect cycles; isolate and report; break edges deterministically by confidence.
- **Partial XML coverage**  
  Mitigation: support partial ingestion; missing data is allowed and flagged.
- **Spreadsheet drift (columns change across worksheets)**  
  Mitigation: implement schema detection per sheet + mapping config; log unknown columns.

---

## 8) Appendix: Edition IDs (current standard)
`wellmann`, `sprengel`, `desmoulins`, `matthioli`, `laguna`, `wechel`, `ruellius`, `lusitanus`, `berendes`, `barbaro`, `beck`, `gunther`

---

---

# 2) Work Breakdown Structure (WBS)

## 2.1 Phase 0 — Repository & baseline
1. Add/confirm `README.md` with:
   - pipeline overview
   - how to run each script
   - where outputs land
2. Add `data/` output policy:
   - which files are authoritative inputs vs generated outputs
3. Add `scripts/common.py` utilities:
   - CSV read/write helpers
   - stable sort helpers
   - ref parsing helpers
   - logging/report writing

Deliverable: documented baseline + shared utilities.

---

## 2.2 Phase 1 — Canonical schema + validation hardening
1. Confirm SQLite schema in `import_csv.py` matches `plan.md` (FKs, UNIQUE, enums).
2. Add a `scripts/validate_csvs.py`:
   - checks allowed enums
   - checks required columns exist
   - checks FK references exist in CSV space before SQLite import
   - outputs `data/validation_report.md`

Deliverable: consistent validation step before DB build.

---

## 2.3 Phase 2 — XML ingestion (editions in `src/`)
1. Implement TEI/XML parser:
   - detect chapters/divs
   - extract ref + term(s)
   - extract anchors: div_id, seg_id
   - generate segments from `<seg>` or equivalent markers
2. Implement edition-specific mapping config:
   - per-edition XPath-ish rules or tag conventions
   - ref/label extraction rules
3. Output:
   - either directly append/merge into `data/entries.csv`
   - or write `data/entries_from_src.csv` then merge in a deterministic “compose” step

Deliverable: reproducible `src/*.xml` → entries rows.

---

## 2.4 Phase 3 — Spreadsheet ingestion (ODS)
1. Implement `.ods` reader (stdlib approach):
   - unzip, parse `content.xml`
   - extract table cells per worksheet
2. Implement per-sheet schema recognition:
   - map known columns to edition refs/terms/pages
   - preserve original `dmm_id` and sheet name
3. Convert to alignment edges:
   - create `equivalent` links among entries in the same row/cluster
   - infer `contains/part_of` for explicit one-to-many patterns (e.g., “3.29;3.30”)
4. Output:
   - `data/alignments_from_spreadsheet.csv` (then merge)
   - optional enrichment: fill missing `page` or `term` in entries

Deliverable: spreadsheet → alignments (and optionally entry enrichment) with traceability.

---

## 2.5 Phase 4 — Compose canonical CSVs
1. Implement `scripts/compose_canonical.py` to merge:
   - legacy-derived CSVs
   - src-XML-derived CSVs
   - spreadsheet-derived alignments
2. Resolve duplicates deterministically:
   - same `entries.id` → merge non-null fields, log conflicts
   - same alignment edge → keep highest confidence, concatenate notes, log conflicts
3. Emit:
   - final `data/entries.csv`, `data/alignments.csv`, etc.
   - plus conflict reports in `data/*needs_review*`

Deliverable: single authoritative set of CSVs.

---

## 2.6 Phase 5 — Master unit derivation + global DMM IDs
1. Implement `scripts/derive_master_units.py`:
   - union-find for `equivalent`
   - build component DAG for contains/part_of
   - identify leaf components (atomic)
   - select anchors + parse book/chapter
   - assign section and construct IDs
2. Emit:
   - `data/master_units.csv`
   - `data/master_unit_entries.csv`
   - `data/master_units_needs_review.csv` (cycles/unparsable refs/ambiguous cases)

Deliverable: deterministic global IDs for finest units.

---

## 2.7 Phase 6 — Wide alignment QC output
1. Implement `scripts/build_wide_alignment.py`:
   - pivot `master_unit_entries` + `entries`
   - per-edition selection rules (exact then fallback_contains)
2. Output `data/master_alignment_wide.csv`
3. Optional: output `.xlsx` if a dependency-free writer is acceptable; otherwise CSV-only.

Deliverable: scholar-friendly alignment check table.

---

## 2.8 Phase 7 — SQLite build + derived views
1. Ensure `scripts/import_csv.py` imports all canonical tables.
2. Add optional derived views:
   - `substance_clusters` view via graph traversal (as feasible in SQLite)
   - views for quick edition crosswalks
3. Ensure `scripts/export_csv.py` round-trips cleanly.

Deliverable: stable `data/dmm.db` aligned with CSVs + helpful views.

---

## 2.9 Phase 8 — End-to-end runner + tests
1. Implement `scripts/build_all.py`:
   - ingest legacy XML
   - ingest src XML
   - ingest spreadsheet
   - compose canonical CSVs
   - validate
   - build SQLite
   - derive master units
   - build wide QC table
2. Add minimal unit/integration tests:
   - ref parsing
   - union-find component building
   - deterministic ordering
   - cycle detection

Deliverable: single-command rebuild + regression safety.

---

## 2.10 Phase 9 — Documentation & operating procedures
1. Document:
   - how to add an edition
   - how to add manual alignments
   - how to correct a bad ref shift
   - how to interpret needs_review outputs
2. Document ID conventions:
   - entries.id
   - master_id

Deliverable: maintainable, handoff-ready workflow docs.

---

## 3) Implementation Notes for Codex (copy/paste)
- Keep `entries` and `alignments` as the canonical representation of the text and its correspondences.
- Implement master units as **derived** outputs, not as manual data entry.
- Prioritize determinism and traceable review outputs over “smart” guessing.
- Support partial XML; missing coverage is normal and should appear as “missing” in the wide QC table.

