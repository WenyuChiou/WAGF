"""Rewrite Section 5 of WRR Paper v6 with tracked changes."""
import sys, os
os.chdir(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
sys.path.insert(0, r".claude\skills\docx")

from scripts.document import Document, DocxXMLEditor

doc = Document("paper/unpacked_v6", author="Claude", rsid="BE341ECD", track_revisions=True)
ed = doc["word/document.xml"]

# ── Paragraph formatting (matches existing style) ──
PPR = ('<w:pPr>'
       '<w:spacing w:after="120" w:line="480" w:lineRule="auto"/>'
       '<w:ind w:firstLine="360"/>'
       '<w:jc w:val="both"/>'
       '</w:pPr>')

def tracked_para(text):
    return DocxXMLEditor.suggest_paragraph(
        f'<w:p>{PPR}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )

# ── Locate existing nodes ──
h51 = ed.get_node(tag="w:p", contains="5.1 Setup")
h52 = ed.get_node(tag="w:p", contains="5.2 Results")

old = []
# Setup paragraphs
old.append(ed.get_node(tag="w:p", contains="To demonstrate domain transferability"))
old.append(ed.get_node(tag="w:p", contains="The irrigation domain stresses capabilities"))
old.append(ed.get_node(tag="w:p", contains="A key extension beyond the flood case study"))
# Results paragraphs (doc was partially rewritten in a prior session)
old.append(ed.get_node(tag="w:p", line_number=range(1820, 1838)))  # tracked ins: governance transfer
old.append(ed.get_node(tag="w:p", contains="Given currently archived artifacts"))
old.append(ed.get_node(tag="w:p", contains="Despite substantial governance pressure"))
old.append(ed.get_node(tag="w:p", contains="The irrigation case highlights the same metric"))
print(f"Found {sum(1 for n in old if n)} / 7 old paragraphs")

# ── New P1: Domain transfer + 5-skill + hybrid agency ──
P1 = (
    "To demonstrate domain transferability, we apply WAGF to irrigation demand management "
    "in the Colorado River Basin without modifying broker architecture. We instantiate 78 "
    "irrigation districts mapped one-to-one to CRSS diversion nodes (56 Upper Basin, 22 "
    "Lower Basin), simulated over 42 years (2019&#8211;2060) with CRSS PRISM precipitation "
    "projections (USBR, 2012). Three behavioral clusters derived from k-means analysis of "
    "calibrated FQL parameters (Hung and Yang, 2021) are mapped to LLM persona templates: "
    "Aggressive (large demand swings, low regret sensitivity), Forward-Looking Conservative "
    "(future-oriented, high regret sensitivity), and Myopic Conservative (status-quo biased, "
    "incremental adjustments). Agents select among five graduated skills (increase_large, "
    "increase_small, maintain_demand, decrease_small, decrease_large) through natural-language "
    "reasoning, while demand-change magnitude is independently sampled from "
    "cluster-parameterized Gaussian distributions at execution time&#8212;a hybrid agency "
    "design that separates qualitative strategic choice (LLM) from quantitative magnitude "
    "(code). Across flood and irrigation, the framework changes only in YAML-level artifacts: "
    "skill definitions, validator rules, appraisal constructs, and persona templates."
)

# ── New P2: Coupling + demand corridor ──
P2 = (
    "The irrigation domain introduces two extensions absent from the flood case. First, "
    "endogenous human&#8211;water coupling: agent demand decisions influence Lake Mead "
    "storage via an annual mass balance (SI Section S6), and the resulting elevation changes "
    "trigger USBR shortage tiers and curtailment ratios that constrain future "
    "decisions&#8212;creating a bidirectional feedback loop that the governance chain must "
    "mediate without hard-coded demand schedules. Second, a demand corridor bounds agent "
    "behavior between a per-agent floor (50% of water right; blocks over-conservation) and "
    "a basin-wide ceiling (6.0 MAF aggregate demand; blocks collective overshoot). This "
    "corridor is the institutional equivalent of the FQL reward function&#8217;s regret "
    "penalty: in reinforcement learning, over-demand is penalized through negative reward "
    "and agents self-regulate; in WAGF, the same equilibrium boundary is encoded as "
    "governance rules, reflecting how real-world administrative mechanisms (compacts, "
    "allocation limits) constrain behavior rather than relying on individual experiential "
    "learning alone."
)

# ── New P3: Governance outcomes ──
P3 = (
    "In current production traces (78 agents, years 1&#8211;27), governance outcomes "
    "remain active throughout multi-decadal simulation: 58.9% of agent-year decisions are "
    "approved on first attempt, 19.5% succeed after retry-mediated correction, and 40.4% "
    "are ultimately rejected (with maintain_demand executed as fallback). Importantly, "
    "retry-mediated recovery indicates that governance interventions function as corrective "
    "mechanisms preserving agent execution continuity, not purely terminal filters. "
    "Intervention counts are reported as governance workload indicators; because one "
    "decision can induce multiple retry attempts, retry statistics are not interpreted as "
    "counts of unique violating agents."
)

# ── New P4: Rule pressure + behavioral diversity ──
P4 = (
    "Rule-frequency diagnostics reveal that intervention burden concentrates on "
    "hydrologically meaningful constraints. The most frequently triggered rule is "
    "demand_ceiling_stabilizer (n=923), followed by high_threat_high_cope_no_increase "
    "(n=701) and curtailment_awareness_check (n=177), indicating that governance "
    "increasingly enforces feasibility boundaries under chronic shortage conditions. "
    "Cluster differentiation remains visible in governed outcomes and is qualitatively "
    "consistent with original FQL cluster behavior (Hung and Yang, 2021, Figure 7). "
    "Despite high rejection pressure, approved-action diversity remains substantial: "
    "normalized entropy over five actions yields H_norm = 0.74, supporting the claim "
    "that WAGF constrains implausible behaviors without collapsing the behavioral "
    "repertoire."
)

# ── New P5: R_H / R_R metric split ──
P5 = (
    "The irrigation case validates the metric framework introduced in Section 3. "
    "Infeasible proposals (e.g., increasing demand at allocation cap, decreasing below "
    "minimum utilization) contribute to feasibility hallucination rate R_H. Coherence "
    "failures that remain technically feasible (e.g., high scarcity assessment with high "
    "adaptive capacity selecting increase) are tracked as rationality deviation R_R "
    "through thinking-rule ERROR traces, enabling cross-domain comparison of governance "
    "performance without conflating infeasibility and bounded-rational behavior."
)

# ── Insert new paragraphs ──
nodes = ed.insert_after(h51, tracked_para(P1))
ed.insert_after(nodes[-1], tracked_para(P2))
print("[OK] Inserted new P1, P2 after 5.1 Setup")

nodes = ed.insert_after(h52, tracked_para(P3))
nodes = ed.insert_after(nodes[-1], tracked_para(P4))
ed.insert_after(nodes[-1], tracked_para(P5))
print("[OK] Inserted new P3, P4, P5 after 5.2 Results")

# ── Delete old paragraphs ──
deleted = 0
for i, para in enumerate(old):
    if para is None:
        continue
    try:
        # Paragraphs with tracked insertions need revert_insertion first
        ins_elements = para.getElementsByTagName("w:ins")
        if ins_elements:
            ed.revert_insertion(para)
            print(f"  P{i+1}: reverted tracked insertion")
        ed.suggest_deletion(para)
        deleted += 1
    except Exception as e:
        # If suggest_deletion still fails, try direct DOM removal as fallback
        try:
            parent = para.parentNode
            if parent:
                parent.removeChild(para)
                deleted += 1
                print(f"  P{i+1}: removed via DOM (fallback)")
        except Exception as e2:
            print(f"[WARN] Could not delete old paragraph {i+1}: {e} / {e2}")
print(f"[OK] Deleted {deleted} / 7 old paragraphs")

# ── Save (skip validation — cp950 encoding issue on Windows) ──
doc.save(validate=False)
print("[DONE] Section 5 rewrite saved to paper/unpacked_v6")
