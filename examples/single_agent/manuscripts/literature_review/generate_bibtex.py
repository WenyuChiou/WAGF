import json
import sys
from datetime import datetime

def generate_bibtex(json_path, bib_path):
    """
    Convert the verify_citations.py JSON output to BibTeX format.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {json_path}")
        return

    metadata_map = data.get('metadata', {})
    verified = data.get('verified', [])
    
    print(f"Found {len(metadata_map)} verified citations.")
    
    bib_entries = []
    
    for doi, meta in metadata_map.items():
        # Create a citation key: AuthorYear
        authors_raw = meta.get('authors', 'Unknown')
        first_author = authors_raw.split(',')[0].strip().split(' ')[0] # Basic split
        year = meta.get('year', 'n.d.')
        
        # Cleanup citation key
        cite_key = f"{first_author}{year}".replace(' ', '').replace('.', '')
        
        # Fallback for duplicates could be handled, but simple approach first
        
        entry = "@article{" + cite_key + ",\n"
        entry += f"  author = {{{authors_raw}}},\n"
        entry += f"  title = {{{meta.get('title', '')}}},\n"
        entry += f"  journal = {{{meta.get('journal', '')}}},\n"
        entry += f"  year = {{{year}}},\n"
        if meta.get('volume'):
            entry += f"  volume = {{{meta['volume']}}},\n"
        if meta.get('pages'):
            entry += f"  pages = {{{meta['pages']}}},\n"
        entry += f"  doi = {{{doi}}},\n"
        entry += "}\n"
        
        bib_entries.append(entry)

    with open(bib_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(bib_entries))
        
    print(f"Successfully wrote {len(bib_entries)} entries to {bib_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_bibtex.py <json_report_path> <output_bib_path>")
        sys.exit(1)
        
    generate_bibtex(sys.argv[1], sys.argv[2])
