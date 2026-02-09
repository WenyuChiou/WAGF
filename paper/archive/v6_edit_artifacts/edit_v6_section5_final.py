"""Phase 2: Update Section 5 P3/P4/P5 with final 42yr metrics."""
import sys, os
os.chdir(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
sys.path.insert(0, r".claude\skills\docx")

from scripts.document import Document, DocxXMLEditor

doc = Document(r"paper\unpacked_v6", author="Claude", rsid="DEBFB010", track_revisions=True)
ed = doc["word/document.xml"]

PPR = ('<w:pPr>'
       '<w:spacing w:after="120" w:line="480" w:lineRule="auto"/>'
       '<w:ind w:firstLine="360"/>'
       '<w:jc w:val="both"/>'
       '</w:pPr>')

def tracked_para(text):
    return DocxXMLEditor.suggest_paragraph(
        f'<w:p>{PPR}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )

# ── Find existing P3, P4, P5 (tracked insertions from session BE341ECD) ──
p3 = ed.get_node(tag="w:p", contains="governance outcomes remain active")
p4 = ed.get_node(tag="w:p", contains="Rule-frequency diagnostics")
p5 = ed.get_node(tag="w:p", contains="irrigation case validates")

# ── Step 1: Revert old insertions and remove ──
for label, para in [("P3", p3), ("P4", p4), ("P5", p5)]:
    ins_elements = para.getElementsByTagName("w:ins")
    if ins_elements:
        ed.revert_insertion(para)
    parent = para.parentNode
    if parent:
        parent.removeChild(para)
    print(f"[OK] Removed old {label}")

# ── Step 2: Find insertion point (after 5.2 Results heading or last remaining para) ──
# The P3/P4/P5 were after the "5.2 Results" heading. Find it.
results_heading = ed.get_node(tag="w:p", contains="5.2 Results")
if results_heading is None:
    # Fallback: find any paragraph near deleted zone
    results_heading = ed.get_node(tag="w:p", contains="5.1 Setup")
    print("[WARN] Could not find 5.2 Results heading, using 5.1 Setup as anchor")

# ── Step 3: Insert new P3, P4, P5 ──
new_p3 = (
    "Over the full 42-year production run (78 agents, 3,276 agent-year decisions), "
    "governance outcomes remain active throughout multi-decadal simulation: 37.7% of "
    "agent-year decisions are approved on first attempt, 22.4% succeed after "
    "retry-mediated correction, and 39.8% are ultimately rejected (with maintain_demand "
    "executed as fallback). Importantly, retry-mediated recovery indicates that "
    "governance interventions function as corrective mechanisms preserving agent "
    "execution continuity, not purely terminal filters. Intervention counts are "
    "reported as governance workload indicators; because one decision can induce "
    "multiple retry attempts, retry statistics are not interpreted as counts of "
    "unique violating agents."
)

new_p4 = (
    "Rule-frequency diagnostics reveal that intervention burden concentrates on "
    "hydrologically meaningful constraints. The most frequently triggered rule is "
    "demand_ceiling_stabilizer (n = 1,420), followed by high_threat_high_cope_no_increase "
    "(n = 1,180) and curtailment_awareness (n = 499), indicating that governance "
    "increasingly enforces feasibility boundaries under chronic shortage conditions. "
    "Cluster differentiation remains visible in governed outcomes and is qualitatively "
    "consistent with original FQL cluster behavior (Hung and Yang, 2021, Figure 7). "
    "Despite high rejection pressure, proposed-action diversity yields H_norm = 0.74 "
    "(normalized Shannon entropy over five skills); governance compression reduces "
    "executed diversity to H_norm = 0.39, reflecting institutional conservatism under "
    "chronic shortage. This entropy reduction quantifies how governance rules narrow "
    "the feasible action space while preserving the behavioral repertoire at the "
    "proposal stage."
)

new_p5 = (
    "The irrigation case validates the metric framework introduced in Section 3. "
    "Infeasible proposals (e.g., increasing demand at allocation cap, decreasing below "
    "minimum utilization) contribute to feasibility hallucination rate R_H. Coherence "
    "failures that remain technically feasible (e.g., high scarcity assessment with "
    "high adaptive capacity selecting increase) are tracked as rationality deviation "
    "R_R through thinking-rule ERROR traces, enabling cross-domain comparison of "
    "governance performance without conflating infeasibility and bounded-rational "
    "behavior (Figure 3)."
)

# Insert after results heading — use returned DOM nodes as next anchor
anchor = results_heading
for label, text in [("P3", new_p3), ("P4", new_p4), ("P5", new_p5)]:
    xml_str = tracked_para(text)
    inserted_nodes = ed.insert_after(anchor, xml_str)
    # Use the last inserted DOM node as next anchor
    anchor = inserted_nodes[-1] if inserted_nodes else anchor
    print(f"[OK] Inserted new {label}")

doc.save(validate=False)
print("[DONE] Phase 2 edits saved")
