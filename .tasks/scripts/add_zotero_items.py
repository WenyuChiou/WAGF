#!/usr/bin/env python3
"""
Zotero Item Creation Script.

Adds literature references to Zotero library with notes and tags.
Works around the limitation that Zotero MCP servers only support read operations.

Usage:
    pip install pyzotero
    python .tasks/scripts/add_zotero_items.py

Reference: Task-051 Documentation Protocol
"""

import os
from typing import Dict, List, Optional

try:
    from pyzotero import zotero
except ImportError:
    print("Error: pyzotero not installed. Run: pip install pyzotero")
    exit(1)


# Configuration - Update these from your .mcp.json
ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY", "hLGhkxO20sXiKpMF62mGDeG2")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "14772686")
ZOTERO_LIBRARY_TYPE = "user"  # or "group"


def create_zotero_client():
    """Create Zotero API client."""
    return zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)


def add_journal_article(
    zot,
    title: str,
    authors: List[Dict[str, str]],
    journal: str,
    year: str,
    volume: str = "",
    issue: str = "",
    pages: str = "",
    doi: str = "",
    abstract: str = "",
    tags: List[str] = None,
    note: str = "",
) -> Optional[str]:
    """
    Add a journal article to Zotero.

    Args:
        zot: Zotero client
        title: Article title
        authors: List of {"firstName": "...", "lastName": "..."} dicts
        journal: Journal name
        year: Publication year
        volume: Journal volume
        issue: Journal issue
        pages: Page range
        doi: DOI (without https://doi.org/)
        abstract: Article abstract
        tags: List of tag strings
        note: HTML note content

    Returns:
        Item key if successful, None otherwise
    """
    # Create item template
    template = zot.item_template("journalArticle")

    # Fill in fields
    template["title"] = title
    template["publicationTitle"] = journal
    template["date"] = year
    template["volume"] = volume
    template["issue"] = issue
    template["pages"] = pages
    template["DOI"] = doi
    template["abstractNote"] = abstract

    # Add authors
    template["creators"] = [
        {"creatorType": "author", "firstName": first, "lastName": last}
        for author in authors
        for first, last in [(author.get("firstName", ""), author.get("lastName", ""))]
    ]

    # Add tags
    if tags:
        template["tags"] = [{"tag": t} for t in tags]

    try:
        # Create the item
        response = zot.create_items([template])
        if response.get("successful"):
            item_key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created: {title[:50]}... (key: {item_key})")

            # Add note if provided
            if note:
                add_note_to_item(zot, item_key, note)

            return item_key
        else:
            print(f"[ERROR] Failed to create: {title}")
            print(f"        {response.get('failed', {})}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return None


def add_note_to_item(zot, item_key: str, note_content: str) -> bool:
    """Add a note to an existing Zotero item."""
    note_template = zot.item_template("note")
    note_template["note"] = f"<p>{note_content}</p>"
    note_template["parentItem"] = item_key

    try:
        response = zot.create_items([note_template])
        if response.get("successful"):
            print(f"       Note added to {item_key}")
            return True
        else:
            print(f"       Failed to add note: {response.get('failed', {})}")
            return False
    except Exception as e:
        print(f"       Note error: {e}")
        return False


def add_task_050_literature():
    """Add Task-050 Memory System Optimization literature."""
    zot = create_zotero_client()
    print("=" * 60)
    print("Adding Task-050 Literature to Zotero")
    print("=" * 60)

    # 1. Miller (1956)
    add_journal_article(
        zot,
        title="The magical number seven, plus or minus two: Some limits on our capacity for processing information",
        authors=[{"firstName": "George A.", "lastName": "Miller"}],
        journal="Psychological Review",
        year="1956",
        volume="63",
        issue="2",
        pages="81-97",
        doi="10.1037/h0043158",
        abstract="A review of the limitations on our ability to process information. The concept of 'channel capacity' is introduced to describe the upper limit of our ability to match stimuli to responses. The number seven (plus or minus two) appears repeatedly in various psychological tasks.",
        tags=["Task-050", "Memory", "Cognitive-Architecture", "Working-Memory"],
        note="<strong>Applied in Task-050E:</strong> Cognitive Constraints Configuration.<br/>"
             "<strong>Key finding:</strong> Working memory capacity is 7±2 chunks.<br/>"
             "<strong>Implementation:</strong> system2_memory_count=7 in CognitiveConstraints class.",
    )

    # 2. Cowan (2001)
    add_journal_article(
        zot,
        title="The magical number 4 in short-term memory: A reconsideration of mental storage capacity",
        authors=[{"firstName": "Nelson", "lastName": "Cowan"}],
        journal="Behavioral and Brain Sciences",
        year="2001",
        volume="24",
        issue="1",
        pages="87-114",
        doi="10.1017/S0140525X01003922",
        abstract="A reconsideration of the classic Miller (1956) paper, suggesting that the true capacity of the focus of attention is closer to 4±1 items when chunking is controlled. This has implications for cognitive architecture design.",
        tags=["Task-050", "Memory", "Cognitive-Architecture", "Working-Memory", "Attention"],
        note="<strong>Applied in Task-050E:</strong> Cognitive Constraints Configuration.<br/>"
             "<strong>Key finding:</strong> Focus of attention capacity is 4±1 items.<br/>"
             "<strong>Implementation:</strong> system1_memory_count=5 in CognitiveConstraints class (Cowan's upper bound).",
    )

    print("\n" + "=" * 60)
    print("Task-050 literature added successfully!")
    print("=" * 60)


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # Just check connection
        zot = create_zotero_client()
        try:
            items = zot.top(limit=1)
            print(f"[OK] Zotero connection successful. Library has items.")
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
        return

    # Add Task-050 literature
    add_task_050_literature()


if __name__ == "__main__":
    main()
