# Citations (Phase 1) — schema + normalization rules

Phase 1 goal: normalize `revised_ed/*.tsv` into a single, consistent **citation layer** that answers:
- “Where is it in the printed edition?” (book/chapter/page/folio labels)
- “How do we open it?” (TEI anchor if available; otherwise IIIF navigation)

This is **edition-local** structure. Cross-edition equivalence is handled later via `unit_id`.

## 1) Input reality: `revised_ed/*.tsv` is heterogeneous

Observed issues that Phase 1 must accommodate:
- Different headings per file (edition-specific prefixes, inconsistent semantics).
- Mixed delimiters:
  - `revised_ed/beck.tsv` uses **spaces** between headers (not tabs).
  - `revised_ed/wellmann.tsv` has **no header row** (first row is data).
- Some files look like citation lists (book/chapter/page/title), others look like headword indices (e.g., `beck_id` + names).

Implication:
- Phase 1 defines a **canonical citations schema** and a **normalization mapping** from each source TSV into it.
- “Index-like” files can be carried through as provenance, but citation-level IIIF coverage will be evaluated only where citations are actually present.

## 2) Canonical file: `citations` (proposed)

Canonical location (Phase 1 decision):
- `data/vnext/citations.csv` (pipeline-derived; replaces any need for `staging/` intermediates)

### 2.1 Required columns

- `edition_id`
- `citation_ref` — edition-local reference label used as the join key within the edition (string)
- `source_file` — e.g., `revised_ed/wechel.tsv`
- `source_row` — 1-based row number in the source file

### 2.2 Strongly recommended columns (navigability + ordering)

- `book_label` — e.g., `Liber primus`, `Libro primero` (string)
- `book_num` — integer when parseable
- `chapter_label` — e.g., `Cap. I`, `Chap. II`, `Textus primi enarratio prima` (string)
- `chapter_num` — integer when parseable
- `page_label` — e.g., `1r`, `2v`, `17`, `020r` (string)
- `scan_id` — edition-specific scan identifier when present (string)
- `iiif_key` — raw key that helps derive an IIIF target (string; may be numeric)
- `headword` — short title/term/headword as printed (string)
- `headword_greek` / `headword_latin` / `headword_english` — only when explicitly present in the source
- `notes`

### 2.3 Provenance / lossless carry-through

To avoid losing edition-specific fields during normalization, include one of:
- `extra_json` — JSON object of unmapped source columns (stringified JSON), OR
- a parallel `citations_extra` file keyed by `(edition_id, citation_ref, source_row)`

Choose one and document it; default recommendation is `extra_json` for simplicity.

## 3) Parsing/normalization rules (minimum)

### 3.1 TSV/CSV hygiene

- Canonical normalized files must be:
  - UTF-8
  - tab-separated (TSV) or RFC4180 CSV (pick one; keep consistent per output)
  - a single header row
  - stable column order
- Source quirks get normalized rather than propagated:
  - space-delimited headers → split into proper columns
  - missing headers → assign explicit headers and record the decision

### 3.2 Roman numeral parsing (chapters)

When `chapter_label` is in roman numerals (e.g., `I`, `IIII`, `V`) or prefixed forms (`Cap I`, `Cap. II`, `Chap. III`):
- store the original in `chapter_label`
- derive `chapter_num` when unambiguous

### 3.3 Book parsing

When `book_label` is parseable to a numeric book:
- store original in `book_label`
- derive `book_num`

Do not invent book numbers if the source does not support it.

## 4) Source-to-canonical mapping inventory (current)

This table is the Phase 1 starting point; update it as sources change.

### Citation-like sources

- `revised_ed/berendes.tsv`
  - `citation_ref`: `berendes_book.chapter`
  - `headword`: `berendes_name`
- `revised_ed/gunther.tsv`
  - `book_num`: `book`
  - `chapter_num`: `chapter`
  - `headword`: `chapter_title`
  - `notes/extra`: `chapter_description`
- `revised_ed/laguna.tsv`
  - `scan_id`: `laguna_scan_id`
  - `book_label`: `laguna_book`
  - `page_label`: `laguna_page`
  - `chapter_label`: `laguna_chapter`
  - `headword`: `laguna_title`
  - `iiif_key`: `laguna_iiif` (may be empty)
- `revised_ed/wechel.tsv`
  - `scan_id`: `wechel_scan_id`
  - `book_label`: `wechel_book`
  - `page_label`: `wechel_page`
  - `chapter_label`: `wechel_chapter`
  - `headword`: `wechel_title`
- `revised_ed/ruel.tsv`
  - `book_label`: `ruel_book`
  - `page_label`: `ruel_page`
  - `chapter_label`: `ruel_chapter`
  - `headword`: `ruel_entry`
  - `extra_json`: include `ruel_web`
- `revised_ed/moulins.tsv` (Desmoulins)
  - `book_num`: `desmoulins_book`
  - `page_label`: `desmoulins_page`
  - `chapter_label`: `desmoulins_chapter`
  - `headword`: `desmoulins_term`
- `revised_ed/matthioli.tsv`
  - `book_num`: `mattioli_book`
  - `chapter_label`: `mattioli_chapter` (roman)
  - `headword_greek`: `mattioli_greek`
  - `headword_latin`: `mattioli_latin`
- `revised_ed/barbaro.tsv`
  - `page_label`: `barbaro_page`
  - `chapter_label`: `barbaro_chapter` (roman)
  - `headword`: `barbaro_term`
  - `iiif_key`: `barbaro_iiif` (meaning to confirm; keep raw)
- `revised_ed/lusitanus.tsv`
  - `chapter_label`: `lusitanus_chapter`
  - `headword`: `lusitanus_entry`
  - `iiif_key`: `lusitanus_iiif` (meaning to confirm; keep raw)
- `revised_ed/wellmann.tsv`
  - **no header**; current columns appear to be:
    - `book_num`, `chapter_num`, `headword_greek` (confirm and formalize)

### Index-like / metadata sources (not sufficient for citation+IIIF by themselves)

- `revised_ed/beck.tsv`
  - space-delimited header; contains `beck_id` plus names
  - treat as a headword index unless/until citations/pages are added
- `revised_ed/editions_table.tsv`
  - bibliographic/scan registry material; useful for IIIF manifest discovery but not a citation list

## 5) Phase 1 deliverables this enables

- A canonical citations table for downstream segmentation and IIIF mapping.
- A clear list of:
  - which editions are citation-covered,
  - which are missing citations or pages,
  - which are missing IIIF manifests/canvas targets (see `docs/validation.md`).
