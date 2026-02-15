"""Add C&V (Convergent & Validity) validation references to Zotero for Paper 3."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pyzotero import zotero

ZOTERO_API_KEY = "hLGhkxO20sXiKpMF62mGDeG2"
ZOTERO_LIBRARY_ID = "14772686"
zot = zotero.Zotero(ZOTERO_LIBRARY_ID, "user", ZOTERO_API_KEY)

# Collection keys
METH = "D7WBAFPU"       # Methodology-LLM-ABM
INTRO = "XZ22GHJA"      # Paper3-WRR-LLM-Flood-ABM
ABM_METH = "27EPKPQF"   # ABM-Methodology

items_to_create = []

# 1. Campbell & Fiske (1959)
t = zot.item_template("journalArticle")
t["title"] = "Convergent and discriminant validation by the multitrait-multimethod matrix"
t["creators"] = [
    {"creatorType": "author", "firstName": "Donald T.", "lastName": "Campbell"},
    {"creatorType": "author", "firstName": "Donald W.", "lastName": "Fiske"},
]
t["publicationTitle"] = "Psychological Bulletin"
t["volume"] = "56"
t["issue"] = "2"
t["pages"] = "81-105"
t["date"] = "1959"
t["DOI"] = "10.1037/h0046016"
t["collections"] = [METH]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "MTMM"}, {"tag": "Discriminant-Validity"}]
items_to_create.append(t)

# 2. Cicchetti (1994)
t = zot.item_template("journalArticle")
t["title"] = "Guidelines, criteria, and rules of thumb for evaluating normed and standardized assessment instruments in psychology"
t["creators"] = [
    {"creatorType": "author", "firstName": "Domenic V.", "lastName": "Cicchetti"},
]
t["publicationTitle"] = "Psychological Assessment"
t["volume"] = "6"
t["issue"] = "4"
t["pages"] = "284-290"
t["date"] = "1994"
t["DOI"] = "10.1037/1040-3590.6.4.284"
t["collections"] = [METH]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "ICC"}, {"tag": "Reliability"}]
items_to_create.append(t)

# 3. Cohen (1988) - book
t = zot.item_template("book")
t["title"] = "Statistical Power Analysis for the Behavioral Sciences"
t["creators"] = [
    {"creatorType": "author", "firstName": "Jacob", "lastName": "Cohen"},
]
t["edition"] = "2nd ed."
t["publisher"] = "Lawrence Erlbaum Associates"
t["place"] = "Hillsdale, NJ"
t["date"] = "1988"
t["ISBN"] = "978-0-12-179060-8"
t["collections"] = [METH]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "Effect-Size"}, {"tag": "Statistics"}]
items_to_create.append(t)

# 4. Grimm et al. (2005)
t = zot.item_template("journalArticle")
t["title"] = "Pattern-oriented modeling of agent-based complex systems: Lessons from ecology"
t["creators"] = [
    {"creatorType": "author", "firstName": "Volker", "lastName": "Grimm"},
    {"creatorType": "author", "firstName": "Eloy", "lastName": "Revilla"},
    {"creatorType": "author", "firstName": "Uta", "lastName": "Berger"},
    {"creatorType": "author", "firstName": "Florian", "lastName": "Jeltsch"},
    {"creatorType": "author", "firstName": "Wolf M.", "lastName": "Mooij"},
    {"creatorType": "author", "firstName": "Steven F.", "lastName": "Railsback"},
    {"creatorType": "author", "firstName": "Hans-Hermann", "lastName": "Thulke"},
    {"creatorType": "author", "firstName": "Jacob", "lastName": "Weiner"},
    {"creatorType": "author", "firstName": "Thorsten", "lastName": "Wiegand"},
    {"creatorType": "author", "firstName": "Donald L.", "lastName": "DeAngelis"},
]
t["publicationTitle"] = "Science"
t["volume"] = "310"
t["issue"] = "5750"
t["pages"] = "987-991"
t["date"] = "2005"
t["DOI"] = "10.1126/science.1116681"
t["collections"] = [METH, ABM_METH]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "Pattern-Oriented-Modeling"}, {"tag": "ABM"}]
items_to_create.append(t)

# 5. Kellens, Terpstra & De Maeyer (2013)
t = zot.item_template("journalArticle")
t["title"] = "Perception and communication of flood risks: A systematic review of empirical research"
t["creators"] = [
    {"creatorType": "author", "firstName": "Wim", "lastName": "Kellens"},
    {"creatorType": "author", "firstName": "Teun", "lastName": "Terpstra"},
    {"creatorType": "author", "firstName": "Philippe", "lastName": "De Maeyer"},
]
t["publicationTitle"] = "Risk Analysis"
t["volume"] = "33"
t["issue"] = "1"
t["pages"] = "24-49"
t["date"] = "2013"
t["DOI"] = "10.1111/j.1539-6924.2012.01844.x"
t["collections"] = [INTRO, METH]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "Flood-Risk-Perception"}, {"tag": "Social-Norms"}]
items_to_create.append(t)

# 6. Lindell & Perry (2012)
t = zot.item_template("journalArticle")
t["title"] = "The Protective Action Decision Model: Theoretical modifications and additional evidence"
t["creators"] = [
    {"creatorType": "author", "firstName": "Michael K.", "lastName": "Lindell"},
    {"creatorType": "author", "firstName": "Ronald W.", "lastName": "Perry"},
]
t["publicationTitle"] = "Risk Analysis"
t["volume"] = "32"
t["issue"] = "4"
t["pages"] = "616-632"
t["date"] = "2012"
t["DOI"] = "10.1111/j.1539-6924.2011.01647.x"
t["collections"] = [INTRO, METH]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "PADM"}, {"tag": "Protective-Action"}]
items_to_create.append(t)

# 7. Thiele, Kurth & Grimm (2014)
t = zot.item_template("journalArticle")
t["title"] = "Facilitating parameter estimation and sensitivity analysis of agent-based models: A cookbook using NetLogo and R"
t["creators"] = [
    {"creatorType": "author", "firstName": "Jan C.", "lastName": "Thiele"},
    {"creatorType": "author", "firstName": "Winfried", "lastName": "Kurth"},
    {"creatorType": "author", "firstName": "Volker", "lastName": "Grimm"},
]
t["publicationTitle"] = "Journal of Artificial Societies and Social Simulation"
t["volume"] = "17"
t["issue"] = "3"
t["pages"] = "11"
t["date"] = "2014"
t["DOI"] = "10.18564/jasss.2503"
t["collections"] = [METH, ABM_METH]
t["tags"] = [{"tag": "Paper3-WRR"}, {"tag": "PEBA"}, {"tag": "Sensitivity-Analysis"}]
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
    date_val = items_to_create[idx]["date"]
    print(f"  [OK] {name} ({date_val}) -> {key}")

for idx_str, err in failed.items():
    idx = int(idx_str)
    c = items_to_create[idx]["creators"][0]
    name = c.get("lastName", c.get("name", ""))
    print(f"  [FAIL] {name}: {err}")

print(f"Created: {len(success)}, Failed: {len(failed)}")

# Add notes
notes_data = {
    0: "<p><b>Cited in:</b> Section 3.7 (L3 ICC Probing)</p><p><b>Role:</b> Used for discriminant validity analysis. TP-CP discriminant r=-0.095 confirms constructs are independent.</p>",
    1: "<p><b>Cited in:</b> Section 3.7 (L3 ICC)</p><p><b>Role:</b> ICC threshold classification: &lt;0.40 poor, 0.40-0.59 fair, 0.60-0.74 good, &gt;=0.75 excellent. Our ICC=0.96 is 'excellent'.</p>",
    2: "<p><b>Cited in:</b> Section 3.7 (L3 ICC Probing)</p><p><b>Role:</b> Eta-squared effect size classification. TP eta²=0.33, CP eta²=0.54 both 'large' (&gt;0.14).</p>",
    3: "<p><b>Cited in:</b> Section 3.7 (L2 EPI)</p><p><b>Role:</b> Foundation for multi-pattern validation approach. Our L2 EPI extends pattern-oriented validation to LLM-ABM.</p>",
    4: "<p><b>Cited in:</b> Section 3.7 (L1 CACR)</p><p><b>Role:</b> Social norms override individual PMT predictions in 4-8% of cases. Justifies allowing 20% non-coherence in CACR threshold.</p>",
    5: "<p><b>Cited in:</b> Section 3.7 (L1 CACR)</p><p><b>Role:</b> PADM framework: low-cost protective actions (insurance) can be habitual, not requiring high threat appraisal. Justifies allowing insurance under low-TP in coherence rules.</p>",
    6: "<p><b>Cited in:</b> Section 3.7 (L2 EPI)</p><p><b>Role:</b> PEBA methodology. Our EPI benchmark comparison follows this distributional validation approach.</p>",
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
