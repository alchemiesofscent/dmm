#!/usr/bin/env python3
"""
Import CSV files into SQLite database.

This script creates the dmm.db SQLite database from the CSV files in data/.

Usage:
    python scripts/import_csv.py
"""

import csv
import sqlite3
from pathlib import Path

# Database schema
SCHEMA = """
-- Editions table (static reference)
CREATE TABLE IF NOT EXISTS editions (
    id TEXT PRIMARY KEY,        -- wellmann, laguna, beck...
    name TEXT,                  -- "Wellmann (1907-1914)"
    language TEXT,              -- grc, lat, deu, eng, spa, fra
    type TEXT,                  -- critical, translation, ms, commentary
    tei_file TEXT,              -- path to TEI XML if available
    base_url TEXT               -- for external links
);

-- Entries table (textual references in editions)
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,        -- edition_id:ref[:segment]
    edition_id TEXT REFERENCES editions(id),
    ref TEXT,                   -- chapter/section ref (1.1, 1.59, 1.72...)
    segment TEXT,               -- NULL for whole chapter, or "seg1", "seg2"
    term TEXT,                  -- the word/phrase as it appears
    term_greek TEXT,            -- Greek form if applicable
    term_latin TEXT,            -- Latin form if applicable
    page TEXT,                  -- page number in edition
    div_id TEXT,                -- div-13 etc. for TEI anchor
    seg_id TEXT,                -- seg-1 etc. for TEI segment anchor
    url TEXT,                   -- external link
    notes TEXT
);

-- Alignments table (many-to-many between entries)
CREATE TABLE IF NOT EXISTS alignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_a TEXT REFERENCES entries(id),
    entry_b TEXT REFERENCES entries(id),
    alignment_type TEXT,        -- "equivalent", "contains", "part_of", "related"
    confidence TEXT,            -- "certain", "probable", "uncertain"
    notes TEXT,
    UNIQUE(entry_a, entry_b)
);

-- Entities table (botanical/natural things)
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,        -- auto-generated or Wikidata Q-number
    type TEXT,                  -- plant, animal, mineral, preparation
    modern_name TEXT,           -- "Iris germanica L."
    wikidata_id TEXT,           -- Q12345
    wikipedia_url TEXT,
    notes TEXT
);

-- Identifications table (scholarly attributions)
CREATE TABLE IF NOT EXISTS identifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT REFERENCES entries(id),
    entity_id TEXT REFERENCES entities(id),
    confidence TEXT,            -- certain, probable, uncertain
    notes TEXT,
    UNIQUE(entry_id, entity_id)
);

-- Manuscripts table (physical witnesses)
CREATE TABLE IF NOT EXISTS manuscripts (
    id TEXT PRIMARY KEY,        -- vindob_gr_1, paris_gr_2179...
    name TEXT,                  -- "Codex Vindobonensis med. gr. 1"
    siglum TEXT,                -- V, P, N (critical apparatus sigla)
    repository TEXT,            -- "Österreichische Nationalbibliothek"
    shelfmark TEXT,             -- "Cod. med. gr. 1"
    date_century INTEGER,       -- 6 (for 6th century)
    iiif_manifest TEXT,         -- IIIF manifest URL
    digitization_url TEXT,      -- Link to digital facsimile
    notes TEXT
);

-- Witnesses table (manuscript readings linked to entries)
CREATE TABLE IF NOT EXISTS witnesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT REFERENCES entries(id),
    manuscript_id TEXT REFERENCES manuscripts(id),
    folio TEXT,                 -- "113r", "f.45v"
    line TEXT,                  -- line number if applicable
    reading TEXT,               -- the text as it appears in this ms
    iiif_canvas TEXT,           -- direct link to IIIF canvas
    iiif_region TEXT,           -- xywh coordinates for the passage
    apparatus_note TEXT,        -- critical apparatus info
    UNIQUE(entry_id, manuscript_id)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_entries_edition ON entries(edition_id);
CREATE INDEX IF NOT EXISTS idx_entries_ref ON entries(ref);
CREATE INDEX IF NOT EXISTS idx_alignments_entry_a ON alignments(entry_a);
CREATE INDEX IF NOT EXISTS idx_alignments_entry_b ON alignments(entry_b);
CREATE INDEX IF NOT EXISTS idx_identifications_entry ON identifications(entry_id);
CREATE INDEX IF NOT EXISTS idx_identifications_entity ON identifications(entity_id);
CREATE INDEX IF NOT EXISTS idx_witnesses_entry ON witnesses(entry_id);
CREATE INDEX IF NOT EXISTS idx_witnesses_manuscript ON witnesses(manuscript_id);

-- View to find all entries aligned with a given entry (substance cluster)
CREATE VIEW IF NOT EXISTS v_aligned_entries AS
SELECT
    a.entry_a as source_entry,
    a.entry_b as aligned_entry,
    a.alignment_type,
    a.confidence
FROM alignments a
UNION ALL
SELECT
    a.entry_b as source_entry,
    a.entry_a as aligned_entry,
    a.alignment_type,
    a.confidence
FROM alignments a;

-- View to get full entry info with edition name
CREATE VIEW IF NOT EXISTS v_entries_full AS
SELECT
    e.*,
    ed.name as edition_name,
    ed.language as edition_language,
    ed.type as edition_type
FROM entries e
LEFT JOIN editions ed ON e.edition_id = ed.id;

-- View to get identifications with entity details
CREATE VIEW IF NOT EXISTS v_identifications_full AS
SELECT
    i.*,
    e.term,
    e.ref,
    e.edition_id,
    ent.modern_name,
    ent.type as entity_type,
    ent.wikidata_id
FROM identifications i
JOIN entries e ON i.entry_id = e.id
JOIN entities ent ON i.entity_id = ent.id;
"""


def import_csv_to_table(conn, csv_path, table_name, id_column=None):
    """Import a CSV file into a SQLite table."""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f'  No data in {csv_path}')
        return 0

    # Get column names from CSV
    columns = list(rows[0].keys())

    # Build INSERT statement
    placeholders = ', '.join(['?' for _ in columns])
    column_names = ', '.join(columns)
    sql = f'INSERT OR REPLACE INTO {table_name} ({column_names}) VALUES ({placeholders})'

    # Insert rows
    cursor = conn.cursor()
    count = 0
    for row in rows:
        values = [row.get(col, '') or None for col in columns]
        try:
            cursor.execute(sql, values)
            count += 1
        except sqlite3.Error as e:
            print(f'  Error inserting row: {e}')
            print(f'  Row: {row}')

    conn.commit()
    return count


def main():
    # Paths
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / 'data'
    db_path = data_dir / 'dmm.db'

    # Remove existing database
    if db_path.exists():
        db_path.unlink()
        print(f'Removed existing database: {db_path}')

    # Connect and create schema
    print(f'Creating database: {db_path}')
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    # Import tables in dependency order
    tables = [
        ('editions.csv', 'editions'),
        ('entries.csv', 'entries'),
        ('alignments.csv', 'alignments'),
        ('entities.csv', 'entities'),
        ('identifications.csv', 'identifications'),
        ('manuscripts.csv', 'manuscripts'),
        ('witnesses.csv', 'witnesses'),
    ]

    for csv_file, table_name in tables:
        csv_path = data_dir / csv_file
        if csv_path.exists():
            print(f'Importing {csv_file}...')
            count = import_csv_to_table(conn, csv_path, table_name)
            print(f'  Imported {count} rows into {table_name}')
        else:
            print(f'  Skipping {csv_file} (not found)')

    # Validate foreign keys
    print('\nValidating foreign keys...')
    conn.execute('PRAGMA foreign_keys = ON')

    # Check for orphaned entries (edition_id not in editions)
    cursor = conn.execute('''
        SELECT COUNT(*) FROM entries
        WHERE edition_id NOT IN (SELECT id FROM editions)
    ''')
    orphaned = cursor.fetchone()[0]
    if orphaned:
        print(f'  Warning: {orphaned} entries have invalid edition_id')
    else:
        print('  All entries have valid edition_id')

    # Check for orphaned alignments
    cursor = conn.execute('''
        SELECT COUNT(*) FROM alignments
        WHERE entry_a NOT IN (SELECT id FROM entries)
           OR entry_b NOT IN (SELECT id FROM entries)
    ''')
    orphaned = cursor.fetchone()[0]
    if orphaned:
        print(f'  Warning: {orphaned} alignments have invalid entry references')
    else:
        print('  All alignments have valid entry references')

    # Check for orphaned identifications
    cursor = conn.execute('''
        SELECT COUNT(*) FROM identifications
        WHERE entry_id NOT IN (SELECT id FROM entries)
    ''')
    orphaned = cursor.fetchone()[0]
    if orphaned:
        print(f'  Warning: {orphaned} identifications have invalid entry_id')
    else:
        print('  All identifications have valid entry_id')

    # Print summary statistics
    print('\nDatabase statistics:')
    for table_name in ['editions', 'entries', 'alignments', 'entities', 'identifications', 'manuscripts', 'witnesses']:
        cursor = conn.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'  {table_name}: {count} rows')

    conn.close()
    print(f'\nDatabase created: {db_path}')


if __name__ == '__main__':
    main()
