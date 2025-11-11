#!/usr/bin/env python3

import csv
import sys
from pathlib import Path


def strip_prefix_from_csv(csv_file: str, prefix: str) -> None:
    """
    Load a CSV file, strip the given prefix from the 'Name' field,
    and overwrite the file with the modified data.
    
    Args:
        csv_file: Path to the CSV file
        prefix: Prefix string to remove from 'Name' values
    """
    file_path = Path(csv_file)
    
    if not file_path.exists():
        print(f"Error: File '{csv_file}' not found.", file=sys.stderr)
        sys.exit(1)
    
    # Read the CSV file
    rows = []
    with open(file_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        if fieldnames is None:
            print(f"Error: CSV file '{csv_file}' is empty or invalid.", file=sys.stderr)
            sys.exit(1)
        
        if 'Name' not in fieldnames:
            print(f"Error: CSV file does not contain a 'Name' column.", file=sys.stderr)
            print(f"Available columns: {', '.join(fieldnames)}", file=sys.stderr)
            sys.exit(1)
        
        for row in reader:
            # Strip the prefix from the Name field
            if row['Name'].startswith(prefix):
                row['Name'] = row['Name'][len(prefix):]
            rows.append(row)
    
    # Write back to the same file
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Successfully processed {len(rows)} rows in '{csv_file}'")
    print(f"Stripped prefix: '{prefix}'")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python strip_prefix.py <csv_file> <prefix>", file=sys.stderr)
        print("\nExample: python strip_prefix.py data.csv '/path/to/remove/'", file=sys.stderr)
        sys.exit(1)
    
    csv_file = sys.argv[1]
    prefix = sys.argv[2]
    
    strip_prefix_from_csv(csv_file, prefix)
