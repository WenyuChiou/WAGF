#!/usr/bin/env python3
"""
Upload PDF attachments to Zotero items.

Usage:
    python upload_pdf_to_zotero.py
"""

import os
from pathlib import Path

try:
    from pyzotero import zotero
except ImportError:
    print("Error: pyzotero not installed. Run: pip install pyzotero")
    exit(1)


# Configuration
ZOTERO_API_KEY = "hLGhkxO20sXiKpMF62mGDeG2"
ZOTERO_LIBRARY_ID = "14772686"

# PDF paths
TEMP_DIR = Path(__file__).parent.parent / "temp_pdfs"


def upload_pdf(zot, item_key: str, pdf_path: Path, title: str = None):
    """
    Upload a PDF file as attachment to a Zotero item.

    Args:
        zot: Zotero client
        item_key: Parent item key
        pdf_path: Path to PDF file
        title: Optional attachment title
    """
    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return False

    file_size = pdf_path.stat().st_size
    if file_size < 1000:
        print(f"[ERROR] PDF too small ({file_size} bytes), likely invalid: {pdf_path}")
        return False

    print(f"[INFO] Uploading {pdf_path.name} ({file_size:,} bytes) to {item_key}...")

    try:
        # Use attachment_simple for linked file
        # This creates an "imported_file" attachment
        response = zot.attachment_simple([str(pdf_path)], item_key)

        if response:
            print(f"[OK] PDF uploaded successfully to {item_key}")
            return True
        else:
            print(f"[ERROR] Upload failed for {item_key}")
            return False

    except Exception as e:
        print(f"[ERROR] Exception during upload: {e}")
        return False


def main():
    """Upload PDFs for Task-050 literature."""
    zot = zotero.Zotero(ZOTERO_LIBRARY_ID, "user", ZOTERO_API_KEY)

    print("=" * 60)
    print("Uploading PDFs to Zotero")
    print("=" * 60)

    # Miller (1956) - XNCU5J2T
    miller_pdf = TEMP_DIR / "Miller_1956.pdf"
    if miller_pdf.exists():
        upload_pdf(zot, "XNCU5J2T", miller_pdf)
    else:
        print(f"[SKIP] Miller PDF not found: {miller_pdf}")

    # Cowan (2001) - NXZ6CFRI
    cowan_pdf = TEMP_DIR / "Cowan_2001.pdf"
    if cowan_pdf.exists() and cowan_pdf.stat().st_size > 10000:
        upload_pdf(zot, "NXZ6CFRI", cowan_pdf)
    else:
        print(f"[SKIP] Cowan PDF not available (requires institutional access)")
        print(f"       Manual download: https://doi.org/10.1017/S0140525X01003922")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
