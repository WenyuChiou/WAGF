#!/usr/bin/env python3
"""Add RQ3 references to Zotero (Paper3-WRR-LLM-Flood-ABM collection)."""
import sys, time, os
sys.stdout.reconfigure(encoding="utf-8")
from pyzotero import zotero

ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY", "hLGhkxO20sXiKpMF62mGDeG2")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "14772686")
COLLECTION = "XZ22GHJA"  # Paper3-WRR-LLM-Flood-ABM

zot = zotero.Zotero(ZOTERO_LIBRARY_ID, "user", ZOTERO_API_KEY)

def add_note(zot, item_key, content):
    note = zot.item_template("note")
    if not content.strip().startswith("<"):
        content = f"<p>{content}</p>"
    note["note"] = content
    note["parentItem"] = item_key
    try:
        r = zot.create_items([note])
        return bool(r.get("successful"))
    except Exception as e:
        print(f"  Note error: {e}")
        return False

items = [
    {
        "type": "journalArticle",
        "title": "We are at risk, and so what? Place attachment, environmental risk perceptions and preventive coping behaviours",
        "authors": [
            {"firstName": "Stefano", "lastName": "De Dominicis"},
            {"firstName": "Ferdinando", "lastName": "Fornara"},
            {"firstName": "Uberta", "lastName": "Ganucci Cancellieri"},
            {"firstName": "Clare", "lastName": "Twigger-Ross"},
            {"firstName": "Marino", "lastName": "Bonaiuto"},
        ],
        "journal": "Journal of Environmental Psychology",
        "volume": "43",
        "pages": "66-78",
        "year": "2015",
        "doi": "10.1016/j.jenvp.2015.05.010",
        "tags": ["PA", "place-attachment", "flood", "RQ3", "Paper3"],
        "note": "<h2>Reading Note</h2><p><b>Cited in:</b> Paper 3, Section 4.4 RQ3</p><p><b>Role:</b> Evidence that place attachment moderates risk perception and reduces protective coping.</p><p><b>Key finding:</b> High PA weakens positive effect of risk perception on preventive behavior.</p>",
    },
    {
        "type": "journalArticle",
        "title": "The risk perception paradox - Implications for governance and communication of natural hazards",
        "authors": [
            {"firstName": "Gisela", "lastName": "Wachinger"},
            {"firstName": "Ortwin", "lastName": "Renn"},
            {"firstName": "Chloe", "lastName": "Begg"},
            {"firstName": "Christian", "lastName": "Kuhlicke"},
        ],
        "journal": "Risk Analysis",
        "volume": "33",
        "issue": "6",
        "pages": "1049-1065",
        "year": "2013",
        "doi": "10.1111/j.1539-6924.2012.01942.x",
        "tags": ["trust", "risk-perception", "review", "RQ3", "Paper3"],
        "note": "<h2>Reading Note</h2><p><b>Cited in:</b> Paper 3, Section 4.4 RQ3 (replaces Terpstra 2011)</p><p><b>Role:</b> Review: trust in authorities is strongest predictor of protective behavior alongside personal experience.</p>",
    },
    {
        "type": "journalArticle",
        "title": "Understanding the effects of past flood events and perceived and estimated flood risks on individuals' voluntary flood insurance purchase behavior",
        "authors": [
            {"firstName": "Wanyun", "lastName": "Shao"},
            {"firstName": "Siyuan", "lastName": "Xian"},
            {"firstName": "Ning", "lastName": "Lin"},
            {"firstName": "Howard", "lastName": "Kunreuther"},
            {"firstName": "Nida", "lastName": "Jackson"},
            {"firstName": "Kirby", "lastName": "Goidel"},
        ],
        "journal": "Water Research",
        "volume": "108",
        "pages": "391-400",
        "year": "2017",
        "doi": "10.1016/j.watres.2016.11.021",
        "tags": ["trust", "flood-insurance", "empirical", "RQ3", "Paper3"],
        "note": "<h2>Reading Note</h2><p><b>Cited in:</b> Paper 3, Section 4.4 RQ3 (replaces Terpstra 2011)</p><p><b>Role:</b> Empirical: trust in local government promotes voluntary flood insurance purchase (US Gulf Coast).</p>",
    },
    {
        "type": "conferencePaper",
        "title": "Language models don't always say what they think: Unfaithful explanations in chain-of-thought prompting",
        "authors": [
            {"firstName": "Miles", "lastName": "Turpin"},
            {"firstName": "Julian", "lastName": "Michael"},
            {"firstName": "Ethan", "lastName": "Perez"},
            {"firstName": "Samuel R.", "lastName": "Bowman"},
        ],
        "conference": "Advances in Neural Information Processing Systems (NeurIPS 2023)",
        "year": "2023",
        "doi": "",
        "url": "https://arxiv.org/abs/2305.04388",
        "tags": ["unfaithful-CoT", "LLM", "Discussion", "Paper3"],
        "note": "<h2>Reading Note</h2><p><b>Cited in:</b> Paper 3, Section 5.3 Limitations</p><p><b>Role:</b> Key ref for unfaithful CoT limitation. LLM reasoning traces may not reflect actual decision process.</p>",
    },
]

created = 0
for item in items:
    query = item.get("doi") or item["title"][:50]
    existing = zot.items(q=query, limit=5)
    is_dup = any(
        e["data"]["title"].lower() == item["title"].lower()
        or (item.get("doi") and e["data"].get("DOI", "") == item["doi"])
        for e in existing
    )
    if is_dup:
        print(f'[SKIP] Already exists: {item["title"][:60]}')
        continue

    tmpl = zot.item_template(item["type"])
    tmpl["title"] = item["title"]
    tmpl["creators"] = [{"creatorType": "author", **a} for a in item["authors"]]
    if item["type"] == "journalArticle":
        tmpl["publicationTitle"] = item.get("journal", "")
        tmpl["volume"] = item.get("volume", "")
        tmpl["issue"] = item.get("issue", "")
        tmpl["pages"] = item.get("pages", "")
    elif item["type"] == "conferencePaper":
        tmpl["conferenceName"] = item.get("conference", "")
    tmpl["date"] = item.get("year", "")
    tmpl["DOI"] = item.get("doi", "")
    tmpl["url"] = item.get("url", "")
    tmpl["tags"] = [{"tag": t} for t in item.get("tags", [])]
    tmpl["collections"] = [COLLECTION]

    resp = zot.create_items([tmpl])
    if resp.get("successful"):
        key = list(resp["successful"].values())[0]["key"]
        add_note(zot, key, item["note"])
        print(f'[OK] {item["title"][:60]}... ({key})')
        created += 1
    else:
        reason = resp.get("failed", {})
        print(f'[FAIL] {item["title"][:60]} - {reason}')
    time.sleep(1)

print(f"\nDone: {created} created")
