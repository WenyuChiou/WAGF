"""Phase E: Add reflection feedback gap discussion to WRR v6."""
import sys, os
os.chdir(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
sys.path.insert(0, r".claude\skills\docx")

from scripts.document import Document, DocxXMLEditor

doc = Document(r"paper\unpacked_v6", author="Claude", rsid="E8F849E9", track_revisions=True)
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

# ── Change 1: Insert NEW paragraph after "Cross-model testing" ──
cross_model = ed.get_node(tag="w:p", contains="Cross-model testing across Gemma 3 model sizes")
new_text = (
    "A structural distinction between reinforcement-learning agents and LLM agents informs "
    "governance design. In the FQL baseline (Hung and Yang, 2021), agents update Q-values through "
    "a reward function that includes a regret penalty for over-demand; this endogenous feedback "
    "enables self-regulation without external constraints. LLM agents, by contrast, receive "
    "individual-level feedback through episodic memory (e.g., &#8220;I requested 115,000 AF but "
    "received only 95,000 AF&#8221;) and reflective summaries, but do not observe basin-level "
    "externalities: no agent is informed that collective demand exceeded available supply or that "
    "its increase contributed to another agent&#8217;s curtailment. This asymmetry &#8212; individual "
    "consequence visibility without commons-level attribution &#8212; means that even with multi-year "
    "memory, agents cannot learn to self-regulate aggregate demand. The governance layer compensates "
    "for this gap by enforcing institutional constraints (demand corridor, shortage-tier curtailment) "
    "that are functionally equivalent to the reward-based convergence mechanism in FQL. This design "
    "mirrors real-world water governance, where administrative rules (compacts, annual allocation "
    "limits) constrain behavior rather than relying on individual actors&#8217; experiential learning "
    "(Schlager and Ostrom, 1992; Pulwarty and Melis, 2001)."
)
ed.insert_after(cross_model, tracked_para(new_text))
print("[OK] Change 1: Inserted RL vs LLM feedback gap paragraph")

# ── Change 2: Expand future work with system-level feedback direction ──
future_run = ed.get_node(tag="w:r", contains="Future work should extend")

old_future = (
    "Future work should extend multi-agent interaction governance, develop data-informed "
    "rule induction, and provide fuller inferential summaries for R_R alongside R_H/EBE "
    "across domains. WAGF, metric definitions, and experiment code are released open-source "
    "at [GitHub URL]."
)
insert_sentence = (
    " Additionally, injecting system-level feedback into agent reflection &#8212; such as "
    "basin-wide supply-demand balance or collective action outcomes &#8212; could test whether "
    "larger LLMs develop commons awareness that reduces dependence on hard governance constraints, "
    "bridging the gap between reward-based self-regulation and institutional rule enforcement."
)
# Keep text before insertion point, insert new sentence, keep remainder
keep_before = (
    "Future work should extend multi-agent interaction governance, develop data-informed "
    "rule induction, and provide fuller inferential summaries for R_R alongside R_H/EBE "
    "across domains."
)
keep_after = (
    " WAGF, metric definitions, and experiment code are released open-source "
    "at [GitHub URL]."
)
replacement = (
    f'<w:r><w:t xml:space="preserve">{keep_before}</w:t></w:r>'
    f'<w:ins w:id="200" w:author="Claude" w:date="2026-02-07T22:00:00Z">'
    f'<w:r><w:rPr><w:rFonts w:cs="Times New Roman"/></w:rPr>'
    f'<w:t xml:space="preserve">{insert_sentence}</w:t></w:r></w:ins>'
    f'<w:r><w:t xml:space="preserve">{keep_after}</w:t></w:r>'
)
ed.replace_node(future_run, replacement)
print("[OK] Change 2: Expanded future work with system-level feedback")

# ── Change 3: Append 6th limitation to limitations paragraph ──
lim_run = ed.get_node(tag="w:r", contains="Several limitations remain")
lim_text = (
    "Several limitations remain. First, primary results are based on single-seed runs "
    "(N=100 agents supports within-run contrast, but cross-seed uncertainty is not quantified). "
    "Second, LLM sampling sensitivity (temperature, top-p, top-k) is not systematically evaluated. "
    "Third, validator rules are expert-authored; automated rule induction remains future work. "
    "Fourth, R_R is currently used as an audit diagnostic and is not yet summarized with the same "
    "inferential depth as R_H/EBE across all case studies. Finally, warning-level governance is "
    "intentionally non-blocking, so behaviorally questionable yet technically feasible decisions "
    "can still pass execution."
)
new_lim = (
    " Sixth, the reflection mechanism provides agents with individual action-outcome feedback "
    "but not basin-level externalities; whether richer system-level feedback could reduce governance "
    "dependence with more capable LLMs remains untested."
)
replacement_lim = (
    f'<w:r><w:t>{lim_text}</w:t></w:r>'
    f'<w:ins w:id="201" w:author="Claude" w:date="2026-02-07T22:00:00Z">'
    f'<w:r><w:rPr><w:rFonts w:cs="Times New Roman"/></w:rPr>'
    f'<w:t xml:space="preserve">{new_lim}</w:t></w:r></w:ins>'
)
ed.replace_node(lim_run, replacement_lim)
print("[OK] Change 3: Appended 6th limitation")

doc.save(validate=False)
print("[DONE] Phase E changes saved")
