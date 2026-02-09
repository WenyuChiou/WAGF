#!/usr/bin/env python3
"""
Add WRR theory references to Zotero with notes and collection assignment.

Targets:
- Lindell & Perry (2012) PADM
- Kahneman & Tversky (1979) Prospect Theory
"""

from __future__ import annotations

import os
from typing import Optional

from pyzotero import zotero


ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY", "hLGhkxO20sXiKpMF62mGDeG2")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "14772686")
ZOTERO_LIBRARY_TYPE = "user"

# Collections from .claude/skills/zotero-write/SKILL.md
COLL_PMT_BEHAVIOR = "6AFGP7RT"
COLL_BOUNDED_RATIONALITY = "QD723EMF"


def client() -> zotero.Zotero:
    return zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)


def find_existing_by_doi(z: zotero.Zotero, doi: str) -> Optional[str]:
    doi_norm = doi.strip().lower()
    for item in z.everything(z.items(q=doi, itemType="journalArticle")):
        data = item.get("data", {})
        if str(data.get("DOI", "")).strip().lower() == doi_norm:
            return item.get("key")
    return None


def add_note(z: zotero.Zotero, parent_key: str, note_html: str) -> None:
    nt = z.item_template("note")
    nt["parentItem"] = parent_key
    nt["note"] = note_html
    z.create_items([nt])


def create_or_skip_item(
    z: zotero.Zotero,
    title: str,
    creators: list[dict],
    journal: str,
    year: str,
    volume: str,
    issue: str,
    pages: str,
    doi: str,
    tags: list[str],
    collections: list[str],
    note_html: str,
) -> str:
    existing = find_existing_by_doi(z, doi)
    if existing:
        print(f"[SKIP] Exists DOI={doi} key={existing}")
        return existing

    t = z.item_template("journalArticle")
    t["title"] = title
    t["creators"] = creators
    t["publicationTitle"] = journal
    t["date"] = year
    t["volume"] = volume
    t["issue"] = issue
    t["pages"] = pages
    t["DOI"] = doi
    t["tags"] = [{"tag": x} for x in tags]
    t["collections"] = collections

    resp = z.create_items([t])
    if not resp.get("successful"):
        raise RuntimeError(f"Failed creating item for DOI={doi}: {resp}")
    item_key = list(resp["successful"].values())[0]["key"]
    print(f"[OK] Created DOI={doi} key={item_key}")
    add_note(z, item_key, note_html)
    print(f"[OK] Note added key={item_key}")
    return item_key


def main() -> None:
    z = client()
    _ = z.top(limit=1)
    print("[OK] Zotero connection")

    create_or_skip_item(
        z=z,
        title="The Protective Action Decision Model: Theoretical Modifications and Additional Evidence",
        creators=[
            {"creatorType": "author", "firstName": "Michael K.", "lastName": "Lindell"},
            {"creatorType": "author", "firstName": "Ronald W.", "lastName": "Perry"},
        ],
        journal="Risk Analysis",
        year="2012",
        volume="32",
        issue="4",
        pages="616-632",
        doi="10.1111/j.1539-6924.2011.01647.x",
        tags=["WRR-2026", "WAGF", "PADM", "ABM-Theory", "Task-Paper-Revision"],
        collections=[COLL_PMT_BEHAVIOR],
        note_html=(
            "<p><strong>WRR usage:</strong> Intro theory-grounded ABM examples (flood appraisal-action logic).</p>"
            "<p><strong>Role in manuscript:</strong> Supports PADM framing alongside PMT for protective action decisions.</p>"
        ),
    )

    create_or_skip_item(
        z=z,
        title="Prospect Theory: An Analysis of Decision under Risk",
        creators=[
            {"creatorType": "author", "firstName": "Daniel", "lastName": "Kahneman"},
            {"creatorType": "author", "firstName": "Amos", "lastName": "Tversky"},
        ],
        journal="Econometrica",
        year="1979",
        volume="47",
        issue="2",
        pages="263-291",
        doi="10.2307/1914185",
        tags=["WRR-2026", "WAGF", "Prospect-Theory", "ABM-Theory", "Task-Paper-Revision"],
        collections=[COLL_BOUNDED_RATIONALITY],
        note_html=(
            "<p><strong>WRR usage:</strong> Intro theory-grounded ABM examples (irrigation utility/risk behavior under scarcity).</p>"
            "<p><strong>Role in manuscript:</strong> Supports Prospect Theory interpretation for irrigation-demand decision framing.</p>"
        ),
    )

    print("[DONE] WRR theory references processed.")


if __name__ == "__main__":
    main()
