#!/usr/bin/env python3
"""
Helper script to prepare MIMIC notes CSV from various sources
Supports MIMIC-III and MIMIC-IV formats
"""

import argparse
import csv
import sys
from pathlib import Path
import sqlite3


def extract_from_mimic3_db(db_path: str, output_path: str, limit: int = 100):
    """
    Extract notes from MIMIC-III database
    
    Expected tables: NOTEEVENTS
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
    SELECT 
        ROW_ID as note_id,
        CATEGORY as note_type,
        TEXT as text
    FROM NOTEEVENTS
    WHERE CATEGORY IN ('Discharge summary', 'Progress note', 'ED')
    LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['note_id', 'note_type', 'text'])
        writer.writerows(rows)
    
    conn.close()
    print(f"Extracted {len(rows)} notes to {output_path}")


def extract_from_mimic4_db(db_path: str, output_path: str, limit: int = 100):
    """
    Extract notes from MIMIC-IV database
    
    Expected tables: mimiciv_note.note
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
    SELECT 
        note_id,
        category as note_type,
        text
    FROM mimiciv_note.note
    WHERE category IN ('Discharge summary', 'Progress note', 'ED')
    LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['note_id', 'note_type', 'text'])
        writer.writerows(rows)
    
    conn.close()
    print(f"Extracted {len(rows)} notes to {output_path}")


def extract_from_mimic4_csv(mimic_dir: str, output_path: str, limit: int = 100):
    """
    Extract notes from MIMIC-IV CSV files
    
    MIMIC-IV notes are typically in: note/note.csv.gz
    But may need to be downloaded separately from PhysioNet
    """
    import gzip
    from pathlib import Path
    import random
    
    # Try multiple possible locations
    possible_paths = [
        Path(mimic_dir) / "note" / "note.csv.gz",
        Path(mimic_dir) / "mimiciv" / "note" / "note.csv.gz",
        Path(mimic_dir) / "mimiciv" / "3.1" / "note" / "note.csv.gz",
        Path(mimic_dir) / "note.csv.gz",
    ]
    
    note_file = None
    for path in possible_paths:
        if path.exists():
            note_file = path
            break
    
    if not note_file:
        # Search recursively
        mimic_path = Path(mimic_dir)
        if mimic_path.exists():
            found_files = list(mimic_path.rglob("note.csv.gz"))
            if found_files:
                note_file = found_files[0]
                print(f"Found note file at: {note_file}")
    
    if not note_file or not note_file.exists():
        raise FileNotFoundError(
            f"Could not find note.csv.gz in {mimic_dir}.\n"
            f"Tried: {[str(p) for p in possible_paths]}\n"
            f"\nNote: MIMIC-IV notes may need to be downloaded separately.\n"
            f"Check: https://physionet.org/content/mimiciv/3.1/"
        )
    
    print(f"Reading notes from: {note_file}")
    
    notes = []
    with gzip.open(note_file, 'rt', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = row.get('category', '').strip()
            # Filter for relevant note types
            if category in ['Discharge summary', 'Progress note', 'ED', 'Nursing', 'Nursing/other']:
                notes.append({
                    'note_id': row.get('note_id', ''),
                    'note_type': category,
                    'text': row.get('text', '')
                })
    
    # Random sample if limit specified
    if limit and len(notes) > limit:
        import random
        random.seed(42)
        notes = random.sample(notes, limit)
    
    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['note_id', 'note_type', 'text'])
        writer.writeheader()
        writer.writerows(notes)
    
    print(f"Extracted {len(notes)} notes to {output_path}")


def convert_csv_format(input_path: str, output_path: str):
    """
    Convert existing CSV to expected format
    
    Expected columns: note_id, note_type, text
    """
    with open(input_path, 'r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=['note_id', 'note_type', 'text'])
            writer.writeheader()
            
            for row in reader:
                # Map common column names
                note_id = row.get('note_id') or row.get('row_id') or row.get('id')
                note_type = row.get('note_type') or row.get('category') or row.get('type')
                text = row.get('text') or row.get('TEXT') or row.get('note_text')
                
                if note_id and text:
                    writer.writerow({
                        'note_id': note_id,
                        'note_type': note_type or 'Unknown',
                        'text': text
                    })
    
    print(f"Converted CSV saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Prepare MIMIC notes CSV for evaluation")
    parser.add_argument("--input", required=True, help="Input file/directory (CSV, SQLite DB, or MIMIC-IV directory)")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--format", choices=["mimic3_db", "mimic4_db", "mimic4_csv", "csv"], default="csv", help="Input format")
    parser.add_argument("--limit", type=int, default=100, help="Limit number of notes")
    
    args = parser.parse_args()
    
    if args.format == "mimic3_db":
        extract_from_mimic3_db(args.input, args.output, args.limit)
    elif args.format == "mimic4_db":
        extract_from_mimic4_db(args.input, args.output, args.limit)
    elif args.format == "mimic4_csv":
        extract_from_mimic4_csv(args.input, args.output, args.limit)
    else:
        convert_csv_format(args.input, args.output)


if __name__ == "__main__":
    main()
