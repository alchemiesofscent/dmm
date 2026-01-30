#!/usr/bin/env python3
"""
Export SQLite database tables to CSV files for editing.

This allows roundtrip editing:
1. Export to CSV
2. Edit in spreadsheet
3. Re-import with import_csv.py

Usage:
    python scripts/export_csv.py [table_name]

If table_name is provided, only that table is exported.
Otherwise, all tables are exported.
"""

import argparse
import csv
import sqlite3
from pathlib import Path

# Table definitions with column order
TABLES = {
    'editions': [
        'id', 'name', 'language', 'type', 'tei_file', 'base_url'
    ],
    'entries': [
        'id', 'edition_id', 'ref', 'segment', 'term', 'term_greek',
        'term_latin', 'page', 'div_id', 'seg_id', 'url', 'notes'
    ],
    'alignments': [
        'entry_a', 'entry_b', 'alignment_type', 'confidence', 'notes'
    ],
    'entities': [
        'id', 'type', 'modern_name', 'wikidata_id', 'wikipedia_url', 'notes'
    ],
    'identifications': [
        'entry_id', 'entity_id', 'confidence', 'notes'
    ],
    'manuscripts': [
        'id', 'name', 'siglum', 'repository', 'shelfmark',
        'date_century', 'iiif_manifest', 'digitization_url', 'notes'
    ],
    'witnesses': [
        'entry_id', 'manuscript_id', 'folio', 'line', 'reading',
        'iiif_canvas', 'iiif_region', 'apparatus_note'
    ],
}


def export_table(conn, table_name, columns, output_path):
    """Export a table to CSV."""
    cursor = conn.cursor()

    # Get data
    column_list = ', '.join(columns)
    cursor.execute(f'SELECT {column_list} FROM {table_name}')
    rows = cursor.fetchall()

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f'Exported {len(rows)} rows to {output_path}')
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description='Export SQLite tables to CSV')
    parser.add_argument('table', nargs='?', help='Table to export (default: all)')
    parser.add_argument('--output-dir', '-o', help='Output directory (default: data/)')
    args = parser.parse_args()

    # Paths
    project_dir = Path(__file__).parent.parent
    data_dir = Path(args.output_dir) if args.output_dir else project_dir / 'data'
    db_path = data_dir / 'dmm.db'

    if not db_path.exists():
        print(f'Database not found: {db_path}')
        print('Run import_csv.py first to create the database.')
        return 1

    # Connect
    conn = sqlite3.connect(db_path)

    # Determine which tables to export
    if args.table:
        if args.table not in TABLES:
            print(f'Unknown table: {args.table}')
            print(f'Available tables: {", ".join(TABLES.keys())}')
            return 1
        tables_to_export = {args.table: TABLES[args.table]}
    else:
        tables_to_export = TABLES

    # Export
    print(f'Exporting from {db_path} to {data_dir}/')
    for table_name, columns in tables_to_export.items():
        output_path = data_dir / f'{table_name}.csv'
        export_table(conn, table_name, columns, output_path)

    conn.close()
    print('\nExport complete!')


if __name__ == '__main__':
    main()
