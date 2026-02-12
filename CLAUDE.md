# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DMM (Dioscorides Materia Medica) is a reproducible data pipeline that aligns multiple editions, translations, and commentaries of Dioscorides' *De Materia Medica* into a normalized alignment graph stored as canonical CSVs and a SQLite database.

**Core domain distinction:** An *entry* is a textual reference in a specific edition (e.g., "ἶρις" in Wellmann 1.1). An *entity* is a real-world botanical object (e.g., *Iris germanica* L.). An *identification* links them via scholarly attribution. There is no `substances` table — substance identity emerges from the alignment graph.

## Pipeline Commands

All scripts use Python 3.8+ standard library only (no pip dependencies). Run from repo root:

```bash
# 1. Build master register + concordance from spreadsheet
python3 scripts/build_master_concordance.py --xlsx "Materia Medica.xlsx" --out-dir data

# 2. Assign stable MMK IDs + semantic QA flags
python3 scripts/assign_master_ids.py --in data/master_concordance.csv --out-dir data

# 3. Build Beck↔Berendes alignment exports
python3 scripts/build_alignment_beck_berendes.py --xlsx "Materia Medica.xlsx" --out-dir data/alignments

# 4. (Optional) Compare curated TSV against generated alignments
python3 scripts/compare_beck_berendes_rough.py --out-dir data/alignments

# 5. Import canonical CSVs into SQLite (destructive — replaces dmm.db)
python3 scripts/import_csv.py

# 6. Export SQLite back to CSVs
python3 scripts/export_csv.py [table_name]
```

**Note:** `import_csv.py` has no argparse — it executes immediately when run. It deletes the existing `data/dmm.db` before rebuilding.

## Architecture

### Data Flow

`Materia Medica.xlsx` → pipeline scripts → `data/*.csv` (canonical) → `data/dmm.db` (derived)

The `.xlsx` is read as a ZIP of SpreadsheetML XML (no pandas/openpyxl). Berendes chaptering is the canonical axis for `chapter_key` to avoid Excel numeric-format collisions (e.g., `1.10` → `1.1`).

### Two Data Layers

1. **Canonical graph** (`data/entries.csv`, `alignments.csv`, `entities.csv`, `identifications.csv`, `editions.csv`, `manuscripts.csv`, `witnesses.csv`) — the authoritative relational data, imported into SQLite by `import_csv.py`.

2. **Workflow/QC layer** (`master_register.csv`, `master_concordance.csv`, `master_concordance_mm.csv`, `semantic_alignment_flags.csv`, `data/alignments/beck_berendes_*.csv`) — derived tables for human review and QA. Not imported into SQLite.

### Key Scripts

| Script | Input | Output | Purpose |
|--------|-------|--------|---------|
| `build_master_concordance.py` | .xlsx | master_register.csv, master_concordance.csv | Long + wide tables from spreadsheet |
| `assign_master_ids.py` | master_concordance.csv | master_concordance_mm.csv, semantic_alignment_flags.csv | Stable MMK IDs + Greek-lemma QA |
| `build_alignment_beck_berendes.py` | .xlsx | beck_berendes_edges/groups/span_edges.csv | Rich Beck↔Berendes alignment |
| `import_csv.py` | data/*.csv | data/dmm.db | CSV → SQLite with schema + views |
| `migrate_db.py` | dioscmatmad_db.xml | entries/alignments/entities/identifications.csv | One-time legacy XML migration |

### SQLite Schema

Seven tables: `editions`, `entries`, `alignments`, `entities`, `identifications`, `manuscripts`, `witnesses`. Entry IDs follow the format `edition:ref[:segment]` (e.g., `beck:1.29:seg1`). Alignment types: `equivalent`, `contains`, `part_of`, `related`. Three views: `v_aligned_entries`, `v_entries_full`, `v_identifications_full`. Full schema is in `scripts/import_csv.py` and documented in `plan.md`.

### Granularity Handling

Different editions have different structural granularity (e.g., Beck 1.29 covers what Berendes splits into 1.29–1.36). This is handled via composite chapter keys (`3.29;3.30` in `chapter_key_raw`, expanded in `chapter_key`), sub-chapter segments (`seg1`, `seg2`), and typed alignments (`contains`/`part_of`).

## Key Documentation

- `plan.md` — Conceptual model + full database schema
- `ALIGNER_WORKFLOW.md` — Script descriptions, run order, output file semantics
- `dmm_prd_wbs.md` — Product requirements + work breakdown structure (phases planned vs. done)

## Conventions

- 12 edition IDs: `wellmann`, `sprengel`, `desmoulins`, `matthioli`, `laguna`, `wechel`, `ruellius`, `lusitanus`, `berendes`, `barbaro`, `beck`, `gunther`
- All outputs are deterministically sorted with stable ID assignment
- QA is done via generated `*_qa.md` reports and `*_flags.csv` review files (no automated test suite)
- Source XML editions live in `src/` (TEI/XML, 1–13 MB each); full ingestion is a planned future phase
