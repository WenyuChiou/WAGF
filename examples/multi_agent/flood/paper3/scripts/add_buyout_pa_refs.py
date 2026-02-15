"""Add buyout/PA governance references to Zotero for Paper 3."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pyzotero import zotero

ZOTERO_API_KEY = "hLGhkxO20sXiKpMF62mGDeG2"
ZOTERO_LIBRARY_ID = "14772686"
zot = zotero.Zotero(ZOTERO_LIBRARY_ID, "user", ZOTERO_API_KEY)

# Collection keys
RQ2 = "V74GSCPK"    # RQ2-Institutional-Feedback
INTRO = "XZ22GHJA"  # Paper3-WRR-LLM-Flood-ABM
RQ1 = "W2FV7HXK"    # RQ1-Memory-Heterogeneity
METH = "D7WBAFPU"   # Methodology-LLM-ABM

items_to_create = []

# 1. Binder, Baker & Barile (2015)
t = zot.item_template("journalArticle")
t["title"] = "Rebuild or Relocate? Resilience and Postdisaster Decision-Making After Hurricane Sandy"
t["creators"] = [
    {"creatorType": "author", "firstName": "Sherri Brokopp", "lastName": "Binder"},
    {"creatorType": "author", "firstName": "Carmen K.", "lastName": "Baker"},
    {"creatorType": "author", "firstName": "John P.", "lastName": "Barile"},
]
t["publicationTitle"] = "American Journal of Community Psychology"
t["volume"] = "56"
t["issue"] = "1-2"
t["pages"] = "180-196"
t["date"] = "2015"
t["DOI"] = "10.1007/s10464-015-9727-x"
t["collections"] = [RQ2, INTRO]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "Place-Attachment"}, {"tag": "Buyout"}]
items_to_create.append(t)

# 2. de Vries & Fraser (2012)
t = zot.item_template("journalArticle")
t["title"] = "Citizen Engagement in the Post-Disaster Recovery Process: A Case Study from Christchurch, New Zealand"
t["creators"] = [
    {"creatorType": "author", "firstName": "Daniel H.", "lastName": "de Vries"},
    {"creatorType": "author", "firstName": "James C.", "lastName": "Fraser"},
]
t["publicationTitle"] = "Global Environmental Change"
t["volume"] = "22"
t["issue"] = "2"
t["pages"] = "475-483"
t["date"] = "2012"
t["DOI"] = "10.1016/j.gloenvcha.2012.01.003"
t["collections"] = [RQ2]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "Buyout"}, {"tag": "Community-Ties"}]
items_to_create.append(t)

# 3. Kick et al. (2011)
t = zot.item_template("journalArticle")
t["title"] = "Repetitive Flood Victims and Acceptance of FEMA Mitigation Offers: An Analysis with Community-System Policy Implications"
t["creators"] = [
    {"creatorType": "author", "firstName": "Edward L.", "lastName": "Kick"},
    {"creatorType": "author", "firstName": "James C.", "lastName": "Fraser"},
    {"creatorType": "author", "firstName": "Gregory M.", "lastName": "Fulber"},
    {"creatorType": "author", "firstName": "Eric", "lastName": "Johnson"},
    {"creatorType": "author", "firstName": "Robert C.", "lastName": "Bolin"},
]
t["publicationTitle"] = "Disasters"
t["volume"] = "35"
t["issue"] = "3"
t["pages"] = "510-539"
t["date"] = "2011"
t["DOI"] = "10.1111/j.1467-7717.2011.01226.x"
t["collections"] = [RQ2]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "Buyout"}, {"tag": "Repetitive-Loss"}]
items_to_create.append(t)

# 4. FEMA (2005)
t = zot.item_template("report")
t["title"] = "Repetitive Loss Strategy"
t["creators"] = [{"creatorType": "author", "name": "Federal Emergency Management Agency"}]
t["institution"] = "Federal Emergency Management Agency"
t["place"] = "Washington, DC"
t["date"] = "2005"
t["collections"] = [RQ2]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "FEMA"}, {"tag": "Repetitive-Loss"}]
items_to_create.append(t)

# 5. Kousky & Michel-Kerjan (2017)
t = zot.item_template("journalArticle")
t["title"] = "Examining Flood Insurance Claims in the United States: Six Key Findings"
t["creators"] = [
    {"creatorType": "author", "firstName": "Carolyn", "lastName": "Kousky"},
    {"creatorType": "author", "firstName": "Erwann O.", "lastName": "Michel-Kerjan"},
]
t["publicationTitle"] = "Journal of Risk and Insurance"
t["volume"] = "84"
t["issue"] = "3"
t["pages"] = "819-850"
t["date"] = "2017"
t["DOI"] = "10.1111/jori.12106"
t["collections"] = [RQ2, METH]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "NFIP"}, {"tag": "Flood-Insurance"}]
items_to_create.append(t)

# 6. Grothmann & Reusswig (2006)
t = zot.item_template("journalArticle")
t["title"] = "People at Risk of Flooding: Why Some Residents Take Precautionary Action While Others Do Not"
t["creators"] = [
    {"creatorType": "author", "firstName": "Torsten", "lastName": "Grothmann"},
    {"creatorType": "author", "firstName": "Fritz", "lastName": "Reusswig"},
]
t["publicationTitle"] = "Natural Hazards"
t["volume"] = "38"
t["issue"] = "1-2"
t["pages"] = "101-120"
t["date"] = "2006"
t["DOI"] = "10.1007/s11069-005-8604-6"
t["collections"] = [INTRO, RQ1]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "PMT"}, {"tag": "Flood-Adaptation"}]
items_to_create.append(t)

# Create all items
print(f"Creating {len(items_to_create)} items...")
resp = zot.create_items(items_to_create)

success = resp.get("successful", {})
failed = resp.get("failed", {})

created_keys = {}
for idx_str, item_data in success.items():
    key = item_data["key"] if isinstance(item_data, dict) else item_data
    idx = int(idx_str)
    c = items_to_create[idx]["creators"][0]
    name = c.get("lastName", c.get("name", ""))
    created_keys[idx] = key
    print(f"  [OK] {name} ({items_to_create[idx]['date']}) -> {key}")

for idx_str, err in failed.items():
    idx = int(idx_str)
    c = items_to_create[idx]["creators"][0]
    name = c.get("lastName", c.get("name", ""))
    print(f"  [FAIL] {name}: {err}")

print(f"Created: {len(success)}, Failed: {len(failed)}")

# Add notes
notes_data = {
    0: "<p><b>Cited in:</b> Section 3.2 (Governance), Section 5.4 (Discussion)</p><p><b>Role:</b> Empirical evidence that high place attachment is the primary predictor of buyout refusal post-Sandy. Justifies the high_pa_blocks_buyout governance rule (PA=VH/H blocks buyout_program).</p>",
    1: "<p><b>Cited in:</b> Section 3.2 (Governance)</p><p><b>Role:</b> Documents how community bonds and emotional ties to place create resistance to relocation/buyout. Referenced in high_pa_blocks_buyout YAML rule message.</p>",
    2: "<p><b>Cited in:</b> Section 3.2 (Governance), Section 5.4 (Discussion)</p><p><b>Role:</b> Empirical study of buyout acceptance among repetitive flood victims. PA-high residents refuse at significantly higher rates. Supports both buyout_repetitive_loss and high_pa_blocks_buyout rules.</p>",
    3: "<p><b>Cited in:</b> Section 3.2 (Governance)</p><p><b>Role:</b> Defines FEMA Repetitive Loss (RL) classification: 2+ flood claims >= $1,000 in any 10-year period. Direct basis for buyout_repetitive_loss validator requiring flood_count >= 2.</p>",
    4: "<p><b>Cited in:</b> Section 3.2 (Governance)</p><p><b>Role:</b> Empirical analysis of NFIP claims showing flood zone != flood risk. LOW-zone properties can still experience repeated flooding.</p>",
    5: "<p><b>Cited in:</b> Section 1 (Introduction), Section 3.2 (Governance), RQ1 (Memory)</p><p><b>Role:</b> Foundational PMT study for flood adaptation. Repeated flood experience is necessary for protective action. Justifies flood_zone_appropriateness status_quo_bias rule.</p>",
}

note_items = []
for idx, note_html in notes_data.items():
    if idx in created_keys:
        nt = zot.item_template("note")
        nt["note"] = note_html
        nt["parentItem"] = created_keys[idx]
        note_items.append(nt)

if note_items:
    note_resp = zot.create_items(note_items)
    n_ok = len(note_resp.get("successful", {}))
    n_fail = len(note_resp.get("failed", {}))
    print(f"Notes: {n_ok} created, {n_fail} failed")

print("Done!")
