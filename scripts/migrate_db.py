#!/usr/bin/env python3
"""
Migrate dioscmatmad_db.xml to normalized CSV files.

This script extracts data from the XML database and creates:
- entries.csv: Textual entries per edition
- alignments.csv: Entry-to-entry mappings (entries from same XML row are aligned)
- identifications.csv: Scholarly attributions from _spec fields
- entities.csv: Botanical entities extracted from identifications
- manuscripts.csv: Placeholder for manuscript data
- witnesses.csv: Placeholder for manuscript witness data

Usage:
    python scripts/migrate_db.py
"""

import csv
import html
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# Edition prefix mappings from XML attributes to edition IDs
EDITION_PREFIXES = {
    'wm': 'wellmann',     # wm_id, wm_name, wm_pag, wm_tt
    'sp': 'sprengel',     # sp_id, sp_name, sp_pag, sp_url, sp_spec, sp_lat
    'br': 'berendes',     # br_id, br_name, br_pag, br_tt, br_spec, br_grk
    'bk': 'beck',         # bk_id, bk_name, bk_tt, bk_grk
    'gn': 'gunther',      # gn_id, gn_name, gn_tt, gn_spec, gn_grk, gn_eng
    'sl': 'laguna',       # sl_id, sl_name, sl_pag, sl_tt, sl_spec, sl_grk
    'ba': 'barbaro',      # ba_id, ba_name, ba_pag, ba_img
    'lu': 'lusitanus',    # lu_id, lu_name, lu_pag, lu_other
    'mo': 'monardes',     # mo_id, mo_name, mo_pag (uses Roman numerals)
    'ma': 'matthioli',    # ma_id, ma_name, ma_pag, ma_grk, ma_tt
    'mh': 'desmoulins',   # mh_id, mh_name, mh_pag
}

# Additional prefixes that provide supplementary info but aren't main editions
SUPPLEMENTARY_PREFIXES = {
    'ws': 'wellmann_sprengel',  # ws_id, ws_name, ws_br, ws_sl (cross-reference)
    'hu': 'hungarian',    # hu_name, hu_pag
    'va': 'valenciana',   # va_name, va_pag
    'lsj': 'lsj',         # lsj_id, lsj_bk, lsj_grk, lsj_eng, lsj_spec
}


def clean_html(text):
    """Strip HTML tags and decode entities from text."""
    if not text:
        return ''
    # Decode HTML entities
    text = html.unescape(text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Clean up whitespace
    text = ' '.join(text.split())
    return text.strip()


def extract_species_name(spec_text):
    """Extract botanical species names from specification text."""
    if not spec_text:
        return []

    # Clean HTML
    text = clean_html(spec_text)

    # Look for patterns like "Iris germanica", "Meum athamanticum", etc.
    # Typically genus + species, sometimes with author
    species_pattern = r'([A-Z][a-z]+\s+[a-z]+(?:\s+[A-Z][a-z]*\.?)?)'
    matches = re.findall(species_pattern, text)

    # Also look for just genus names or family names
    if not matches:
        # Try to find any capitalized botanical-looking names
        genus_pattern = r'\b([A-Z][a-z]+(?:aceae|ales)?)\b'
        matches = re.findall(genus_pattern, text)

    return list(set(matches))


def parse_xml(xml_path):
    """Parse the XML database and extract all items."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    items = []
    for item in root.findall('item'):
        items.append(dict(item.attrib))

    return items


def extract_entries(items):
    """Extract entries for each edition from items."""
    entries = []

    for item in items:
        book = item.get('book', '')
        item_id = item.get('id', '')
        nerid = item.get('nerid', '')
        tuid = item.get('tuid', '')
        notes = item.get('notes', '')

        # Process each edition prefix
        for prefix, edition_id in EDITION_PREFIXES.items():
            # Get the reference ID (chapter.section)
            ref_key = f'{prefix}_id'
            ref = item.get(ref_key, '')

            if not ref:
                continue

            # Build entry ID
            entry_id = f'{edition_id}:{ref}'

            # Get term/name
            name_key = f'{prefix}_name'
            term = item.get(name_key, '')
            term = clean_html(term)

            # Get Greek form if available
            grk_key = f'{prefix}_grk'
            term_greek = item.get(grk_key, '')

            # Get page number
            pag_key = f'{prefix}_pag'
            page = item.get(pag_key, '')

            # Get div ID for TEI linking
            tt_key = f'{prefix}_tt'
            div_id = item.get(tt_key, '')

            # Get URL if available
            url_key = f'{prefix}_url'
            url = item.get(url_key, '')

            entry = {
                'id': entry_id,
                'edition_id': edition_id,
                'ref': ref,
                'segment': '',  # No segments in current data
                'term': term,
                'term_greek': term_greek,
                'term_latin': '',  # Could extract from sp_lat
                'page': page,
                'div_id': div_id,
                'seg_id': '',
                'url': url,
                'notes': '',
                '_item_id': item_id,  # Internal tracking
                '_nerid': nerid,
                '_tuid': tuid,
            }

            # Special handling for Sprengel Latin term
            if prefix == 'sp':
                entry['term_latin'] = item.get('sp_lat', '')

            entries.append(entry)

    return entries


def extract_alignments(items, entries):
    """Create alignments between entries that share the same XML item."""
    alignments = []

    # Group entries by their source item_id
    entries_by_item = {}
    for entry in entries:
        item_id = entry.get('_item_id', '')
        if item_id not in entries_by_item:
            entries_by_item[item_id] = []
        entries_by_item[item_id].append(entry)

    # Create pairwise alignments within each item group
    seen_pairs = set()
    for item_id, item_entries in entries_by_item.items():
        # Sort entries by edition for consistent ordering
        item_entries.sort(key=lambda e: e['edition_id'])

        # Create alignments between all pairs
        for i, entry_a in enumerate(item_entries):
            for entry_b in item_entries[i+1:]:
                pair = tuple(sorted([entry_a['id'], entry_b['id']]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    alignments.append({
                        'entry_a': entry_a['id'],
                        'entry_b': entry_b['id'],
                        'alignment_type': 'equivalent',
                        'confidence': 'certain',
                        'notes': '',
                    })

    return alignments


def extract_identifications(items, entries):
    """Extract botanical identifications from _spec fields."""
    identifications = []
    entities = {}  # entity_name -> entity_data

    # Build a lookup of entries by edition + ref
    entry_lookup = {}
    for entry in entries:
        key = (entry['edition_id'], entry['ref'])
        entry_lookup[key] = entry['id']

    for item in items:
        # Check each edition's _spec field
        for prefix, edition_id in EDITION_PREFIXES.items():
            spec_key = f'{prefix}_spec'
            spec_text = item.get(spec_key, '')

            if not spec_text:
                continue

            # Get the entry ID for this edition's entry
            ref_key = f'{prefix}_id'
            ref = item.get(ref_key, '')
            if not ref:
                continue

            entry_id = entry_lookup.get((edition_id, ref))
            if not entry_id:
                continue

            # Extract species names from spec text
            species_names = extract_species_name(spec_text)

            for species_name in species_names:
                # Create or update entity
                entity_id = species_name.lower().replace(' ', '_').replace('.', '')
                if entity_id not in entities:
                    entities[entity_id] = {
                        'id': entity_id,
                        'type': 'plant',  # Default, could be refined
                        'modern_name': species_name,
                        'wikidata_id': '',
                        'wikipedia_url': '',
                        'notes': '',
                    }

                # Create identification
                identifications.append({
                    'entry_id': entry_id,
                    'entity_id': entity_id,
                    'confidence': 'certain',  # From published edition
                    'notes': f'Extracted from {edition_id}',
                })

    # Remove duplicate identifications
    seen = set()
    unique_identifications = []
    for ident in identifications:
        key = (ident['entry_id'], ident['entity_id'])
        if key not in seen:
            seen.add(key)
            unique_identifications.append(ident)

    return unique_identifications, list(entities.values())


def write_csv(filepath, data, fieldnames):
    """Write data to CSV file."""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)
    print(f'Wrote {len(data)} rows to {filepath}')


def create_empty_templates(data_dir):
    """Create empty template CSVs for manuscripts and witnesses."""

    # manuscripts.csv template
    manuscripts_fields = [
        'id', 'name', 'siglum', 'repository', 'shelfmark',
        'date_century', 'iiif_manifest', 'digitization_url', 'notes'
    ]
    manuscripts_example = [{
        'id': 'vindob_gr_1',
        'name': 'Codex Vindobonensis med. gr. 1',
        'siglum': 'V',
        'repository': 'Österreichische Nationalbibliothek',
        'shelfmark': 'Cod. med. gr. 1',
        'date_century': '6',
        'iiif_manifest': '',
        'digitization_url': '',
        'notes': 'Vienna Dioscorides',
    }]
    write_csv(data_dir / 'manuscripts.csv', manuscripts_example, manuscripts_fields)

    # witnesses.csv template
    witnesses_fields = [
        'entry_id', 'manuscript_id', 'folio', 'line', 'reading',
        'iiif_canvas', 'iiif_region', 'apparatus_note'
    ]
    witnesses_example = [{
        'entry_id': 'wellmann:1.1',
        'manuscript_id': 'vindob_gr_1',
        'folio': '',
        'line': '',
        'reading': '',
        'iiif_canvas': '',
        'iiif_region': '',
        'apparatus_note': '',
    }]
    write_csv(data_dir / 'witnesses.csv', witnesses_example, witnesses_fields)


def main():
    # Paths
    project_dir = Path(__file__).parent.parent
    xml_path = project_dir / 'dioscmatmad_db.xml'
    data_dir = project_dir / 'data'

    # Ensure data directory exists
    data_dir.mkdir(exist_ok=True)

    print(f'Parsing {xml_path}...')
    items = parse_xml(xml_path)
    print(f'Found {len(items)} items')

    # Extract entries
    print('Extracting entries...')
    entries = extract_entries(items)
    print(f'Extracted {len(entries)} entries')

    # Extract alignments
    print('Creating alignments...')
    alignments = extract_alignments(items, entries)
    print(f'Created {len(alignments)} alignments')

    # Extract identifications and entities
    print('Extracting identifications...')
    identifications, entities = extract_identifications(items, entries)
    print(f'Extracted {len(identifications)} identifications')
    print(f'Found {len(entities)} unique entities')

    # Write CSVs
    entry_fields = [
        'id', 'edition_id', 'ref', 'segment', 'term', 'term_greek',
        'term_latin', 'page', 'div_id', 'seg_id', 'url', 'notes'
    ]
    write_csv(data_dir / 'entries.csv', entries, entry_fields)

    alignment_fields = ['entry_a', 'entry_b', 'alignment_type', 'confidence', 'notes']
    write_csv(data_dir / 'alignments.csv', alignments, alignment_fields)

    identification_fields = ['entry_id', 'entity_id', 'confidence', 'notes']
    write_csv(data_dir / 'identifications.csv', identifications, identification_fields)

    entity_fields = ['id', 'type', 'modern_name', 'wikidata_id', 'wikipedia_url', 'notes']
    write_csv(data_dir / 'entities.csv', entities, entity_fields)

    # Create template files for manuscripts and witnesses
    print('Creating template files...')
    create_empty_templates(data_dir)

    print('\nMigration complete!')
    print(f'Output files written to {data_dir}/')


if __name__ == '__main__':
    main()
