"""Step 1: Reassign existing Zotero items to Paper3 collections + add Paper3 notes."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
from pyzotero import zotero
import time

ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID")
ZOTERO_LIBRARY_TYPE = os.environ.get("ZOTERO_LIBRARY_TYPE", "user")

if not ZOTERO_API_KEY or not ZOTERO_LIBRARY_ID:
    raise RuntimeError(
        "Missing Zotero credentials. Set ZOTERO_API_KEY and ZOTERO_LIBRARY_ID "
        "in environment variables."
    )

zot = zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)

# Paper3 collection keys
P3_PARENT = 'XZ22GHJA'   # Paper3-WRR-LLM-Flood-ABM
METH_LLM  = 'D7WBAFPU'   # Methodology-LLM-ABM
RQ1_MEM   = 'W2FV7HXK'   # RQ1-Memory-Heterogeneity
RQ2_INST  = 'V74GSCPK'   # RQ2-Institutional-Feedback
RQ3_SOC   = 'BI67K7TG'   # RQ3-Social-Information

# Existing items to reassign: {key: (target_collections, note_html)}
EXISTING_ITEMS = {
    'NV3BZ94J': {
        'collections': [P3_PARENT],
        'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.1 (PMT Background)</p>'
               '<p><b>Role:</b> Original PMT formulation. Foundation for the entire behavioral '
               'framework: threat appraisal (TP) and coping appraisal (CP) drive protective action decisions.</p>',
    },
    '65IXMWP2': {
        'collections': [P3_PARENT],
        'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.1 (PMT Background)</p>'
               '<p><b>Role:</b> Revised PMT with cognitive and physiological processes. Establishes '
               'the dual-construct (TP+CP) model used for agent decision-making.</p>',
    },
    'R76GP2F7': {
        'collections': [P3_PARENT],
        'note': '<p><b>Cited in:</b> Section 2.1 (PMT Background)</p>'
               '<p><b>Role:</b> Meta-analysis of threat, coping, and flood prevention. Validates that '
               'both TP and CP independently predict protective action, justifying our dual-construct agent model.</p>',
    },
    'W9CJWAQU': {
        'collections': [P3_PARENT, RQ1_MEM],
        'note': '<p><b>Cited in:</b> Section 2.1 (PMT Background), Section 3.7 (CACR threshold)</p>'
               '<p><b>Role:</b> Systematic review of risk perceptions and protective behaviors. '
               'Combined with Kellens (2013) and Grothmann (2006), justifies 20% non-coherence allowance in CACR.</p>',
    },
    'XEBQWVQK': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.3 (LLM Agents), Section 3.2 (WAGF Framework)</p>'
               '<p><b>Role:</b> Generative Agents (Smallville). Foundation for LLM agent architecture with '
               'memory stream, reflection, and planning. Our WAGF framework extends this with governance layer.</p>',
    },
    'RMNEUT7F': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.3 (LLM Agents)</p>'
               '<p><b>Role:</b> AgentTorch: scalable LLM-ABM infrastructure for epidemiology. '
               'Demonstrates feasibility of large-scale LLM-ABM; our work extends to flood adaptation domain.</p>',
    },
    'H9FH54VD': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.3 (LLM Agents), Section 3.7 (L3 Validation)</p>'
               '<p><b>Role:</b> (1) Survey of LLM-based agents for social simulation (Nature MI). '
               '(2) Psychometric framework for evaluating LLM personality traits — basis for our L3 ICC probing.</p>',
    },
    '67PWUHTW': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 2.2 (ABM in Flood Research)</p>'
               '<p><b>Role:</b> ABM textbook reference. Establishes foundational ABM methodology '
               'and design principles followed in our model architecture.</p>',
    },
    'WIM3EDT2': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 3.7 (C&amp;V Protocol), Section 5.4 (Methodological Contributions)</p>'
               '<p><b>Role:</b> Pattern-oriented modeling. Foundation for our L2 EPI benchmark validation: '
               'comparing simulated aggregate patterns against 8 empirical benchmarks.</p>',
    },
    'XZC8MQXF': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 5.4 (Methodological Contributions)</p>'
               '<p><b>Role:</b> Updated ODD protocol for describing ABMs. Our model description follows '
               'ODD+D conventions extended with LLM-specific components.</p>',
    },
    'KK8HTHGG': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 3.7 (L2 Methodology), Section 5.4 (Methodological Contributions)</p>'
               '<p><b>Role:</b> PEBA (Pattern-oriented Empirical Benchmarking) methodology. '
               'Our EPI benchmark comparison follows this distributional validation approach.</p>',
    },
    'ISX2GHUZ': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 2.2 (ABM methodology)</p>'
               '<p><b>Role:</b> ODD+D protocol extension adding decision-making details. '
               'Provides the template for documenting our PMT-based agent decision rules.</p>',
    },
    '3NQ2MD2S': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 2.2 (ABM in Flood Research)</p>'
               '<p><b>Role:</b> Early flood ABM with threshold-based rules. Represents the first-generation '
               'approach our LLM-based architecture aims to improve upon.</p>',
    },
    'ZIM66T3N': {
        'collections': [METH_LLM, RQ1_MEM],
        'note': '<p><b>Cited in:</b> Section 2.1 (PMT), Section 2.2 (ABM), Section 3.4 (Memory Architecture)</p>'
               '<p><b>Role:</b> PMT-based ABM with social influence and Bayesian TP updating for NYC. '
               'Key precedent for our approach; our work replaces Bayesian updating with LLM reasoning.</p>',
    },
    'KDW7SEFR': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 2.3 (LLM Agents)</p>'
               '<p><b>Role:</b> Using LLMs to simulate multiple humans in experimental settings. '
               'Demonstrates LLM agents can replicate human subject study results.</p>',
    },
    '2A835ZNC': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 3.7 (C&amp;V Protocol, L3), Section 4.1 (Validation)</p>'
               '<p><b>Role:</b> Foundational method for discriminant validity. TP-CP discriminant '
               'r = -0.095 confirms constructs are independent in our LLM agent model.</p>',
    },
    '3Q6M3GUB': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 3.7 (C&amp;V Protocol, L3 threshold), Section 4.1</p>'
               '<p><b>Role:</b> ICC threshold classification: &lt;0.40 poor, 0.40-0.59 fair, '
               '0.60-0.74 good, &ge;0.75 excellent. Our ICC=0.96 falls in "excellent" range.</p>',
    },
    '3WU9N524': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 4.1 (Validation, L3 effect sizes)</p>'
               '<p><b>Role:</b> Eta-squared effect size classification: small=0.01, medium=0.06, '
               'large=0.14. TP &eta;&sup2;=0.33 and CP &eta;&sup2;=0.54 both qualify as "large".</p>',
    },
    'PJ2ZRDPT': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 3.3 (Agent Decision Rules), Section 3.7 (L1 coherence)</p>'
               '<p><b>Role:</b> PADM framework: low-cost protective actions (insurance) can be '
               'habitual/heuristic. Justifies allowing insurance under low-TP in PMT coherence rules.</p>',
    },
    '8WDHBFX3': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 3.6 (Flood Damage Model)</p>'
               '<p><b>Role:</b> HAZUS-MH depth-damage functions used to compute structural and '
               'contents damage from flood depth for each agent household.</p>',
    },
    'UKBECRHG': {
        'collections': [METH_LLM],
        'note': '<p><b>Cited in:</b> Section 4.2 (RQ1 Results - behavioral diversity)</p>'
               '<p><b>Role:</b> Shannon entropy used to measure behavioral diversity across agent '
               'archetypes and time steps. Confirms agents maintain heterogeneous strategies.</p>',
    },
    '54D6KUGU': {
        'collections': [P3_PARENT, RQ1_MEM],
        'note': '<p><b>Cited in:</b> Section 3.7 (CACR threshold justification)</p>'
               '<p><b>Role:</b> Systematic review finding social norms override PMT predictions in '
               '4-8% of cases. Justifies allowing 20% non-coherence in CACR (&ge;0.80).</p>',
    },
    'FT3KA4HD': {
        'collections': [RQ1_MEM],
        'note': '<p><b>Cited in:</b> Section 3.4 (Memory Architecture)</p>'
               '<p><b>Role:</b> Ebbinghaus forgetting curve. Foundation for exponential memory decay '
               'function used in agent memory system: w(t) = e^(-&lambda;t).</p>',
    },
    'K5M2CCDA': {
        'collections': [RQ1_MEM],
        'note': '<p><b>Cited in:</b> Section 3.4 (Memory Architecture - emotional weighting)</p>'
               '<p><b>Role:</b> Negativity bias in risk perception. Justifies asymmetric emotional '
               'weighting where flood events receive higher salience than non-events.</p>',
    },
    'APGFIDNR': {
        'collections': [RQ2_INST],
        'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 3.7 (L2 benchmarks)</p>'
               '<p><b>Role:</b> NFIP pricing dynamics and disaster-driven policy windows. Source for '
               'insurance uptake benchmarks (30-50% SFHA, 5-10% annual lapse rate).</p>',
    },
    'U4FVXBH4': {
        'collections': [RQ2_INST],
        'note': '<p><b>Cited in:</b> Section 3.7 (L2 benchmark: insurance uptake)</p>'
               '<p><b>Role:</b> Learning about infrequent events: flood insurance behavior after '
               'hurricanes. Source for post-hurricane insurance uptake spikes (40-50%).</p>',
    },
    'V2KWAFB8': {
        'collections': [RQ3_SOC],
        'note': '<p><b>Cited in:</b> Section 3.5 (Social Information Channels)</p>'
               '<p><b>Role:</b> Social learning theory. Foundation for the gossip channel: agents '
               'learn from observing neighbors\' adaptation choices (observational learning).</p>',
    },
    'W3IJLZM8': {
        'collections': [RQ3_SOC],
        'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 3.5 (Social Channels), Section 5.3</p>'
               '<p><b>Role:</b> Social media and risk communication during natural disasters. '
               'Justifies modeling three distinct information channels (media, neighbor, institutional).</p>',
    },
}

# ── Step 1: Reassign existing items ──
print("=== Step 1: Reassigning existing items to Paper3 collections ===\n")
updated = 0
failed = 0
for item_key, config in EXISTING_ITEMS.items():
    try:
        item = zot.item(item_key)
        current_cols = item['data'].get('collections', [])
        new_cols = list(set(current_cols + config['collections']))
        if new_cols != current_cols:
            item['data']['collections'] = new_cols
            zot.update_item(item)
            creators = item['data'].get('creators', [])
            name = creators[0]['lastName'] if creators else '?'
            year = item['data'].get('date', '')[:4]
            added = [c for c in config['collections'] if c not in current_cols]
            print(f"  OK {item_key}: {name} ({year}) +{len(added)} collections")
            updated += 1
        else:
            print(f"  SKIP {item_key}: already in target collections")
        time.sleep(0.3)
    except Exception as e:
        print(f"  FAIL {item_key}: {e}")
        failed += 1

print(f"\nReassigned: {updated}, Skipped: {len(EXISTING_ITEMS)-updated-failed}, Failed: {failed}")

# ── Step 2: Add Paper3-specific notes to existing items ──
print("\n=== Step 2: Adding Paper3 notes to existing items ===\n")
notes_created = 0
notes_failed = 0
for item_key, config in EXISTING_ITEMS.items():
    try:
        note = zot.item_template('note')
        note['note'] = config['note']
        note['parentItem'] = item_key
        note['tags'] = [{'tag': 'Paper3-WRR'}]
        resp = zot.create_items([note])
        if resp.get('successful'):
            print(f"  OK note for {item_key}")
            notes_created += 1
        else:
            print(f"  FAIL note for {item_key}: {resp}")
            notes_failed += 1
        time.sleep(0.3)
    except Exception as e:
        print(f"  FAIL note for {item_key}: {e}")
        notes_failed += 1

print(f"\nNotes created: {notes_created}, Failed: {notes_failed}")
print("\nStep 1 complete!")
