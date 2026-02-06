# Aligner workflow (DMM)

This repo’s “aligner” workflow is a small, reproducible pipeline that turns the working spreadsheet (`Materia Medica.xlsx`) into:

- a **master register** (long/audit table),
- a **master concordance** (wide/QC table),
- stable per-row IDs (`MMK…`), plus a small **semantic QA flags** file, and
- a **rich Beck ↔ Berendes alignment export** (explicit edges + inferred spans).

All scripts are designed to be dependency-light: `.xlsx` files are read as a ZIP of SpreadsheetML XML (no pandas/openpyxl required).

## Inputs and “source of truth”

- `Materia Medica.xlsx` is the primary editable source for the alignment work.
- Many scripts treat the **Berendes chaptering** (`berendes` sheet) as the canonical axis for `chapter_key` and use it to avoid Excel numeric-format collisions (e.g. `1.10` becoming `1.1`).

## Recommended run order

From repo root:

1) Build master tables from the spreadsheet:

```bash
python3 scripts/build_master_concordance.py --xlsx "Materia Medica.xlsx" --out-dir data
```

2) Assign stable master IDs and compute semantic QA flags:

```bash
python3 scripts/assign_master_ids.py --in data/master_concordance.csv --out-dir data
```

3) Build Beck ↔ Berendes alignment exports (explicit and span-inferred):

```bash
python3 scripts/build_alignment_beck_berendes.py --xlsx "Materia Medica.xlsx" --out-dir data/alignments
```

4) (Optional) Compare a manually curated “rough” TSV against generated output:

```bash
python3 scripts/compare_beck_berendes_rough.py --out-dir data/alignments
```

## Outputs (what files mean)

### `data/master_register.csv` (long/audit)

Produced by: `scripts/build_master_concordance.py`

One row per **(edition × chapter_key)** occurrence, with traceability back to the spreadsheet:

- `chapter_key` / `chapter_key_raw` / `chapter_key_source`
- `edition`, plus edition-specific metadata (`book`, `chapter`, `page`, `scan_id`, `folio`, `division`, `term`, `title`, `greek`, `latin`, `greek_text`)
- `source_sheet`, `source_row` (where it came from in the `.xlsx`)

This file is useful when you need to answer “where did this value come from?” or debug missing/misaligned rows.

### `data/master_concordance.csv` (wide/QC)

Produced by: `scripts/build_master_concordance.py`

One row per `chapter_key` with wide columns per edition/source (Berendes, Desmoulins, Laguna, Wechel, Ruel, Lusitanus, Barbaro, Matthiolo, Gunther, Wellmann, Beck).

The `data/master_qa.md` file is generated alongside it and summarizes coverage per edition and known caveats (notably: the `all` sheet is intentionally ignored because of Excel numeric-format collisions).

### `data/master_concordance_mm.csv` + `data/master_key_index.csv`

Produced by: `scripts/assign_master_ids.py`

- `master_concordance_mm.csv` = `master_concordance.csv` plus a stable, sequential `mm_id` column (default prefix `MMK`, starting at `MMK001`).
- `master_key_index.csv` is a compact lookup: `mm_id`, `chapter_key`, `berendes_term`, `beck_greek_lemma`, `beck_latin_lemma`.

`mm_id` stability: it is stable **as long as** the sorted sequence of `chapter_key` rows doesn’t change. If you insert/remove/renumber chapters, `mm_id` assignments will shift.

### `data/semantic_alignment_flags.csv` (semantic QA)

Produced by: `scripts/assign_master_ids.py`

This is a **review list**, not an alignment table. Each row is a `chapter_key` that fails a simple string-similarity check:

- `ratio_beck_wellmann`: similarity between `beck_greek_lemma` and `wellmann_greek_lemma`
- `ratio_beck_matthiolo`: similarity between `beck_greek_lemma` and `matthiolo_greek`

Default flagging rule: emit a row if either ratio is below `--flag-threshold` (default `0.80`).

Implementation details (important for interpreting the ratios):

- Text normalization: NFKD diacritic stripping, `casefold()`, and removal of common punctuation/whitespace.
- Similarity metric: `difflib.SequenceMatcher(...).ratio()`
- If either side is empty after normalization, the ratio is treated as `1.0` (i.e., “can’t compare” is not flagged).

In practice, most flags tend to come from the Beck vs Matthiolo comparison because Matthiolo often uses different headwords for the same chapter.

## Beck ↔ Berendes alignment exports

Produced by: `scripts/build_alignment_beck_berendes.py` into `data/alignments/`

### `data/alignments/beck_berendes_edges.csv` (explicit edges)

One row per mapping row from the `beck+berendes` sheet, enriched with context from other sheets when possible.

Key columns:

- `beck_dmm_id`, `beck_greek_lemma`, `beck_latin_lemma`
- `berendes_teitok_id` (the stable Berendes ID; preferred join key)
- `berendes_chapter_raw` (may be composite like `3.29;3.30`)
- `berendes_chapter_keys` (expanded)
- `cardinality` + degrees (`beck_degree`, `berendes_degree`) for quick 1→N / N→1 spotting
- contextual columns (Desmoulins/Laguna/Wechel/Matthiolo/Ruel/Lusitanus/Barbaro/Gunther/Wellmann)

Important: this file may contain “continuation rows” where `beck_dmm_id` is blank (an Excel-style sparse table). If your downstream checks expect every row to be self-contained, prefer the span export below.

### `data/alignments/beck_berendes_groups.csv` (per-Beck aggregation)

One row per `beck_dmm_id`, aggregating its mapped Berendes targets and a few context fields. Useful as a quick “how many Berendes chapters does this Beck DMM span?” view.

### `data/alignments/beck_berendes_span_edges.csv` (inferred spans)

This is a **dense, one-row-per-Berendes-entry** view derived from the explicit anchors in `beck+berendes`:

- Choose the earliest Berendes anchor position for each `beck_dmm_id`
- Span forward through the ordered Berendes list until the next Beck anchor
- Emit one row for every Berendes entry in the span with:
  - `span_anchor_teitok_id`, `span_anchor_chapter`
  - `span_offset` (0-based position within the span)

This dense export is intended for QA/review and for downstream logic that cannot handle missing Beck IDs on continuation rows.

### QA + samples

The script also writes:

- `data/alignments/beck_berendes_qa.md` (counts, 1→N stats, notes)
- `data/alignments/beck_berendes_sample50.txt` (deterministic random sample)
- `data/alignments/beck_berendes_span_qa.md`
- `data/alignments/beck_berendes_span_sample50.txt`

## Rough TSV comparison (optional)

Produced by: `scripts/compare_beck_berendes_rough.py`

Treats `data/alignments/beck_berendes_rough.tsv` as a curated list of `(beck_dmm_id → berendes_teitok_id)` pairs and compares it to:

- explicit edges (`beck_berendes_edges.csv`), and
- inferred spans (`beck_berendes_span_edges.csv`).

Outputs:

- `data/alignments/beck_berendes_rough_compare.md`
- `data/alignments/beck_berendes_rough_compare_pairs.csv`

The report includes heuristic “reasons” for mismatches (e.g., blank Berendes targets in the sheet, DMM reuse, missing anchors causing span inference differences).

## Edition-native extraction (optional)

`scripts/extract_editions_from_xlsx.py` extracts per-edition CSVs to `data/editions/` (e.g., `berendes.csv`, `laguna.csv`, `wechel.csv`, `wellmann.csv`, `beck_index.csv`, …). This is **not** the alignment graph; it’s a convenient normalized dump of the spreadsheet’s per-edition sheets.

## SQLite import/export (canonical graph)

These scripts operate on the canonical “graph” CSVs in `data/` (`entries.csv`, `alignments.csv`, `entities.csv`, …), not on the master concordance outputs.

- `scripts/import_csv.py`
  - Creates/recreates `data/dmm.db` from `data/*.csv`.
  - **Destructive:** it deletes the existing `data/dmm.db` first.
  - Note: it does **not** implement `--help`/arg parsing; running it will execute immediately.

- `scripts/export_csv.py`
  - Exports tables from `data/dmm.db` back to `data/*.csv` for roundtrip editing.

## Legacy XML migration (optional)

`scripts/migrate_db.py` converts the legacy `dioscmatmad_db.xml` into normalized CSVs (`entries.csv`, `alignments.csv`, `entities.csv`, `identifications.csv`, plus templates for manuscripts/witnesses). It aligns “entries from the same XML `<item>`” as `equivalent` by default.

## Practical notes / common pitfalls

- CSV parsing: several exported fields contain commas inside quotes; avoid tools that split on `,` without CSV awareness.
- Excel sparse tables: if you see “missing IDs” in a CSV, first check whether the source sheet intentionally uses blank cells for repeated values. Prefer the dense exports (`*_span_edges.csv`) for QA tooling.
- `chapter_key_raw` vs `chapter_key`: composite keys (`3.29;3.30`) are preserved in `*_raw` columns and expanded to multiple rows via `chapter_key`.

