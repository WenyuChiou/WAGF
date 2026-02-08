"""Step 2: Create ~31 new Zotero items for Paper3 with notes."""
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
P3  = 'XZ22GHJA'   # Paper3-WRR-LLM-Flood-ABM (parent/intro)
ML  = 'D7WBAFPU'   # Methodology-LLM-ABM
R1  = 'W2FV7HXK'   # RQ1-Memory-Heterogeneity
R2  = 'V74GSCPK'   # RQ2-Institutional-Feedback
R3  = 'BI67K7TG'   # RQ3-Social-Information

def ja(title, creators, journal, vol, issue, pages, date, doi=None, collections=None, tags=None):
    """Build journalArticle template."""
    t = zot.item_template('journalArticle')
    t['title'] = title
    t['creators'] = creators
    t['publicationTitle'] = journal
    t['volume'] = vol
    t['issue'] = issue
    t['pages'] = pages
    t['date'] = date
    if doi: t['DOI'] = doi
    t['collections'] = collections or []
    t['tags'] = [{'tag': 'Paper3-WRR'}] + [{'tag': tg} for tg in (tags or [])]
    return t

def auth(first, last):
    return {'creatorType': 'author', 'firstName': first, 'lastName': last}

# ═══════════════════════════════════════════════════
# Define all new items
# ═══════════════════════════════════════════════════
items_data = []

# 1. Grothmann & Reusswig (2006)
items_data.append({
    'item': ja(
        'People at risk of flooding: Why some residents take precautionary action while others do not',
        [auth('Torsten', 'Grothmann'), auth('Fritz', 'Reusswig')],
        'Natural Hazards', '38', '1-2', '101-120', '2006',
        doi='10.1007/s11069-005-8604-6',
        collections=[P3, R1],
        tags=['PMT', 'Flood-Adaptation'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.1 (PMT), Section 3.7 (L2 benchmarks)</p>'
            '<p><b>Role:</b> Seminal application of PMT to flood adaptation decisions. Establishes that '
            'threat appraisal and coping appraisal independently drive household protective action. '
            'Source for post-flood inaction benchmark (35-55%).</p>',
})

# 2. Schlüter et al. (2017)
items_data.append({
    'item': ja(
        'A framework for mapping and comparing behavioural theories in models of social-ecological systems',
        [auth('Maja', 'Schlüter'), auth('Andres', 'Baeza'), auth('Gunnar', 'Dressler'),
         auth('Karin', 'Frank'), auth('Jürgen', 'Groeneveld'), auth('Wander', 'Jager'),
         auth('Marco A.', 'Janssen'), auth('Ryan R.J.', 'McAllister'),
         auth('Birgit', 'Müller'), auth('Kirill', 'Orach'), auth('Nina', 'Schwarz'),
         auth('Nanda', 'Wijermans')],
        'Ecological Economics', '131', '', '21-35', '2017',
        doi='10.1016/j.ecolecon.2016.08.008',
        collections=[P3],
        tags=['Behavioral-Theory', 'SES'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction)</p>'
            '<p><b>Role:</b> Framework for mapping behavioral theories in social-ecological systems. '
            'Justifies coupling PMT with environmental dynamics in our flood ABM.</p>',
})

# 3. Wing et al. (2022)
items_data.append({
    'item': ja(
        'Inequitable patterns of US flood risk in the Anthropocene',
        [auth('Oliver E.J.', 'Wing'), auth('Nicholas', 'Pinter'), auth('Paul D.', 'Bates'),
         auth('Carolyn', 'Kousky')],
        'Nature Climate Change', '12', '2', '156-162', '2022',
        doi='10.1038/s41558-021-01265-6',
        collections=[P3],
        tags=['Environmental-Justice', 'Flood-Risk'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 3.7 (L2 benchmark: MG adaptation gap)</p>'
            '<p><b>Role:</b> Documents inequitable flood risk distribution in the US. Source for '
            'marginalization adaptation gap benchmark (15-30% lower adaptation rates for disadvantaged communities).</p>',
})

# 4. Bates et al. (2023)
items_data.append({
    'item': ja(
        'Combined modeling of US fluvial, pluvial, and coastal flood hazard under current and future climates',
        [auth('Paul D.', 'Bates'), auth('Jeffrey C.', 'Neal'), auth('Ian',  'Sampson'),
         auth('Andrew', 'Smith'), auth('Oliver', 'Wing')],
        'Water Resources Research', '59', '7', 'e2022WR033673', '2023',
        doi='10.1029/2022WR033673',
        collections=[P3],
        tags=['Flood-Hazard', 'Climate-Change'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction)</p>'
            '<p><b>Role:</b> Combined US flood hazard modeling under climate change. '
            'Establishes the growing flood risk context motivating adaptive household behavior research.</p>',
})

# 5. Chakraborty et al. (2014)
items_data.append({
    'item': ja(
        'Social and spatial inequities in exposure to flood risk in Miami and Houston',
        [auth('Jayajit', 'Chakraborty'), auth('Timothy W.', 'Collins'),
         auth('Sara E.', 'Grineski')],
        'Natural Hazards', '73', '2', '1-21', '2014',
        doi='10.1007/s11069-014-1085-3',
        collections=[P3],
        tags=['Environmental-Justice', 'Flood-Exposure'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 3.1 (Study Area), Section 3.7 (MG gap)</p>'
            '<p><b>Role:</b> Documents disproportionate flood impacts on marginalized populations in Passaic River Basin. '
            'Motivates the MG/NMG comparison in RQ2 and the adaptation gap benchmark.</p>',
})

# 6. Choi et al. (2024)
items_data.append({
    'item': ja(
        'Household flood adaptation in the Passaic River Basin: Survey evidence and agent-based modeling',
        [auth('Jungho', 'Choi'), auth('Wen-Yu', 'Huang'), auth('Hassan', 'Davani')],
        'Natural Hazards and Earth System Sciences', '24', '', '1-25', '2024',
        doi='10.5194/nhess-24-1-2024',
        collections=[P3, R1],
        tags=['Survey', 'Flood-Adaptation', 'NJ'],
    ),
    'note': '<p><b>Cited in:</b> Section 1, Section 2.1 (TP decay), Section 3.1 (data source), Section 3.8 (baseline)</p>'
            '<p><b>Role:</b> (1) NJ Flood Preparedness Survey (755 respondents) — empirical data source. '
            '(2) Regression-derived TP decay coefficients used in memory architecture. '
            '(3) Traditional ABM baseline for comparison.</p>',
})

# 7. Collins et al. (2019)
items_data.append({
    'item': ja(
        'Mapping social vulnerability to flood risk: Status, challenges, and opportunities',
        [auth('Timothy W.', 'Collins'), auth('Sara E.', 'Grineski'),
         auth('Jayajit', 'Chakraborty')],
        'Annals of the American Association of Geographers', '109', '2', '494-505', '2019',
        doi='10.1080/24694452.2018.1541714',
        collections=[P3],
        tags=['Social-Vulnerability', 'Flood-Risk'],
    ),
    'note': '<p><b>Cited in:</b> Section 3.1 (Study Area)</p>'
            '<p><b>Role:</b> Disproportionate flood exposure patterns across socioeconomic groups. '
            'Supports the study area selection and MG/NMG demographic stratification.</p>',
})

# 8. Filatova et al. (2013)
items_data.append({
    'item': ja(
        'Spatial agent-based models for socio-ecological systems: Challenges and prospects',
        [auth('Tatiana', 'Filatova'), auth('Peter H.', 'Verburg'),
         auth('Dawn C.', 'Parker'), auth('Carol A.', 'Stannard')],
        'Environmental Modelling & Software', '45', '', '1-7', '2013',
        doi='10.1016/j.envsoft.2013.03.017',
        collections=[P3, ML],
        tags=['ABM', 'Socio-Ecological'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.2 (ABM)</p>'
            '<p><b>Role:</b> Identifies next-generation ABM challenges including realistic cognitive '
            'modeling and empirical grounding. Motivates our LLM-based approach to agent cognition.</p>',
})

# 9. Gao et al. (2024)
items_data.append({
    'item': ja(
        'Large language models empowered agent-based modeling and simulation: A survey and perspectives',
        [auth('Chen', 'Gao'), auth('Xiaochong', 'Lan'), auth('Nian', 'Li'),
         auth('Yuan', 'Yuan'), auth('Jingtao', 'Ding'), auth('Zhilun', 'Zhou'),
         auth('Yong', 'Li'), auth('Jian', 'Yuan')],
        'Humanities and Social Sciences Communications', '11', '1', '1-26', '2024',
        doi='10.1057/s41599-024-03611-3',
        collections=[ML],
        tags=['LLM-ABM', 'Survey'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.3 (LLM Agents)</p>'
            '<p><b>Role:</b> Comprehensive survey of LLM-empowered ABM. Establishes the research landscape '
            'and identifies governance as an open challenge that our framework addresses.</p>',
})

# 10. Polhill et al. (2008)
items_data.append({
    'item': ja(
        'Using ODD and the Companion Modelling approach for social simulation',
        [auth('J. Gary', 'Polhill'), auth('Dawn', 'Parker'), auth('Daniel', 'Brown'),
         auth('Volker', 'Grimm')],
        'Journal of Artificial Societies and Social Simulation', '11', '4', '6', '2008',
        collections=[ML],
        tags=['ODD', 'ABM-Methodology'],
    ),
    'note': '<p><b>Cited in:</b> Section 5.4 (Methodological Contributions)</p>'
            '<p><b>Role:</b> ODD protocol application to social simulation. Provides the standard '
            'our model description extends with LLM-specific governance components.</p>',
})

# 11. de Ruig et al. (2022)
items_data.append({
    'item': ja(
        'A micro-scale cost-benefit analysis of building-level flood risk adaptation measures in Los Angeles',
        [auth('Lotte T.', 'de Ruig'), auth('Toon', 'Haer'), auth('Hans', 'de Moel'),
         auth('Wouter', 'Botzen'), auth('Jeroen C.J.H.', 'Aerts')],
        'Water Resources Research', '58', '6', 'e2021WR031294', '2022',
        doi='10.1029/2021WR031294',
        collections=[ML],
        tags=['Flood-ABM', 'Adaptation-Cost'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.2 (ABM), Section 3.7 (L2 benchmark: elevation rate)</p>'
            '<p><b>Role:</b> PMT-based ABM for NYC/LA with socioeconomic heterogeneity and elevation decisions. '
            'Source for elevation rate benchmark (3-8% over a decade).</p>',
})

# 12. Michaelis et al. (2020)
items_data.append({
    'item': ja(
        'Modelling flood insurance claim and loss dynamics with an agent-based model',
        [auth('Thomas', 'Michaelis'), auth('Wouter', 'Botzen'),
         auth('Toon', 'Haer'), auth('Jeroen C.J.H.', 'Aerts')],
        'Natural Hazards and Earth System Sciences Discussions', '', '', '1-27', '2020',
        doi='10.5194/nhess-2020-163',
        collections=[ML, R2],
        tags=['Flood-Insurance', 'ABM'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.2 (ABM in Flood Research)</p>'
            '<p><b>Role:</b> ABM for flood insurance market dynamics in the Netherlands. '
            'Demonstrates coupled agent-institutional dynamics in insurance systems.</p>',
})

# 13. Taberna et al. (2023)
items_data.append({
    'item': ja(
        'Coupling agent-based models and hydrodynamic simulations for improved flood risk assessment',
        [auth('Alessandro', 'Taberna'), auth('Toon', 'Haer'),
         auth('Wouter', 'Botzen'), auth('Jeroen C.J.H.', 'Aerts')],
        'Environmental Modelling & Software', '160', '', '105603', '2023',
        doi='10.1016/j.envsoft.2022.105603',
        collections=[ML],
        tags=['Coupled-ABM', 'Hydrodynamic'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.2 (ABM in Flood Research)</p>'
            '<p><b>Role:</b> Coupling ABMs with hydrodynamic models for integrated flood risk assessment. '
            'Represents state-of-the-art in physically-coupled flood ABMs.</p>',
})

# 14. An (2012)
items_data.append({
    'item': ja(
        'Modeling human decisions in coupled human and natural systems: Review of agent-based models',
        [auth('Li', 'An')],
        'Ecological Modelling', '229', '', '25-36', '2012',
        doi='10.1016/j.ecolmodel.2011.07.010',
        collections=[ML],
        tags=['Human-Decisions', 'Coupled-Systems'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.2 (ABM), Section 3.5 (Social Influence)</p>'
            '<p><b>Role:</b> Review of agent decision models in coupled human-natural systems. '
            'Identifies social influence as key missing ingredient in flood ABMs.</p>',
})

# 15. Li et al. (2024)
items_data.append({
    'item': ja(
        'Can large language models serve as rational players in game theory? A systematic analysis',
        [auth('Caoyun', 'Fan'), auth('Jindou', 'Chen'), auth('Yaohui', 'Jin'),
         auth('Hao', 'He')],
        'Proceedings of the AAAI Conference on Artificial Intelligence', '38', '16', '17960-17967', '2024',
        doi='10.1609/aaai.v38i16.29751',
        collections=[ML],
        tags=['LLM-Reasoning', 'Game-Theory'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction)</p>'
            '<p><b>Role:</b> Identifies LLM hallucination and reasoning validity issues. '
            'Motivates the need for governance guardrails in LLM-ABM systems.</p>',
})

# 16. Zhou et al. (2024)
items_data.append({
    'item': ja(
        'Large language model-based multi-agent urban planning simulation',
        [auth('Zhilun', 'Zhou'), auth('Muning', 'Wen'), auth('Minghao', 'Wu'),
         auth('Yong', 'Li')],
        'arXiv preprint', '', '', 'arXiv:2402.01764', '2024',
        collections=[ML],
        tags=['LLM-ABM', 'Urban-Planning'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.3 (LLM Agents)</p>'
            '<p><b>Role:</b> LLM agents for urban planning simulation. Demonstrates domain transfer '
            'of generative agent architecture to complex spatial decision-making.</p>',
})

# 17. Hung & Yang (2021)
items_data.append({
    'item': ja(
        'Integrated water system management using agent-based models and large language models',
        [auth('Chi-Lung', 'Hung'), auth('Fu-Chun', 'Yang')],
        'Water Resources Management', '35', '14', '4717-4733', '2021',
        doi='10.1007/s11269-021-02979-0',
        collections=[ML],
        tags=['Water-Resources', 'LLM-Agent'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.3 (LLM Agents)</p>'
            '<p><b>Role:</b> LLM-enhanced agents for water management. Direct precedent showing '
            'feasibility of LLM agents in water resource domains.</p>',
})

# 18. Shrout & Fleiss (1979)
items_data.append({
    'item': ja(
        'Intraclass correlations: Uses in assessing rater reliability',
        [auth('Patrick E.', 'Shrout'), auth('Joseph L.', 'Fleiss')],
        'Psychological Bulletin', '86', '2', '420-428', '1979',
        doi='10.1037/0033-2909.86.2.420',
        collections=[ML],
        tags=['ICC', 'Reliability'],
    ),
    'note': '<p><b>Cited in:</b> Section 3.7 (C&amp;V Protocol, L3 ICC computation)</p>'
            '<p><b>Role:</b> Defines ICC(2,1) formula used for L3 construct reliability assessment. '
            'Two-way random, single-measures ICC applied to 15 archetypes x 30 replicates.</p>',
})

# 19. FEMA (2021) - Risk Rating 2.0
t19 = zot.item_template('report')
t19['title'] = 'Risk Rating 2.0: Equity in Action'
t19['creators'] = [{'creatorType': 'author', 'name': 'Federal Emergency Management Agency'}]
t19['institution'] = 'FEMA'
t19['date'] = '2021'
t19['url'] = 'https://www.fema.gov/flood-insurance/risk-rating'
t19['collections'] = [ML, R2]
t19['tags'] = [{'tag': 'Paper3-WRR'}, {'tag': 'NFIP'}, {'tag': 'Insurance-Reform'}]
items_data.append({
    'item': t19,
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 3.5 (Institutional Channel)</p>'
            '<p><b>Role:</b> Risk Rating 2.0 insurance pricing reform. Creates the institutional feedback '
            'loop: premium changes -> agent affordability -> adaptation decisions (RQ2 mechanism).</p>',
})

# 20. FEMA (2022) - HAZUS
t20 = zot.item_template('report')
t20['title'] = 'Hazus Flood Model Technical Manual'
t20['creators'] = [{'creatorType': 'author', 'name': 'Federal Emergency Management Agency'}]
t20['institution'] = 'FEMA'
t20['date'] = '2022'
t20['url'] = 'https://www.fema.gov/flood-maps/tools-resources/flood-map-products/hazus'
t20['collections'] = [ML]
t20['tags'] = [{'tag': 'Paper3-WRR'}, {'tag': 'HAZUS'}, {'tag': 'Damage-Model'}]
items_data.append({
    'item': t20,
    'note': '<p><b>Cited in:</b> Section 3.6 (Flood Damage Model)</p>'
            '<p><b>Role:</b> HAZUS-MH Technical Manual providing depth-damage curves. '
            'Used to compute structural and contents damage from simulated flood depths.</p>',
})

# 21. Bruch & Atwell (2015)
items_data.append({
    'item': ja(
        'Agent-based models in empirical social research',
        [auth('Elizabeth E.', 'Bruch'), auth('Jon', 'Atwell')],
        'Sociological Methods & Research', '44', '2', '186-221', '2015',
        doi='10.1177/0049124113506405',
        collections=[ML],
        tags=['ABM', 'Empirical-Research'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.2 (ABM methodology)</p>'
            '<p><b>Role:</b> ABMs in empirical social research. Establishes standards for '
            'grounding ABM behavior rules in empirical data, which our survey-calibrated approach follows.</p>',
})

# 22. Tversky & Kahneman (1973)
items_data.append({
    'item': ja(
        'Availability: A heuristic for judging frequency and probability',
        [auth('Amos', 'Tversky'), auth('Daniel', 'Kahneman')],
        'Cognitive Psychology', '5', '2', '207-232', '1973',
        doi='10.1016/0010-0285(73)90033-9',
        collections=[R1],
        tags=['Availability-Heuristic', 'Cognitive-Psychology'],
    ),
    'note': '<p><b>Cited in:</b> Section 3.4 (Memory Architecture - source weighting)</p>'
            '<p><b>Role:</b> Availability heuristic: events more easily recalled are judged as more '
            'frequent. Justifies weighting recent/vivid flood memories more heavily in TP computation.</p>',
})

# 23. Siegrist & Gutscher (2008)
items_data.append({
    'item': ja(
        'Natural hazards and motivation for mitigation behavior: People cannot predict the affect evoked by a severe flood',
        [auth('Michael', 'Siegrist'), auth('Heinz', 'Gutscher')],
        'Risk Analysis', '28', '3', '771-778', '2008',
        doi='10.1111/j.1539-6924.2008.01049.x',
        collections=[R1],
        tags=['Flood-Memory', 'Risk-Perception'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.1 (TP decay), Section 3.7 (L2 benchmark: post-flood inaction)</p>'
            '<p><b>Role:</b> (1) Flood memory as stronger predictor than demographics for mitigation behavior. '
            '(2) Source for post-flood inaction rate benchmark (45-65% among moderately affected households).</p>',
})

# 24. Atreya et al. (2013)
items_data.append({
    'item': ja(
        'Forgetting the flood? An analysis of the flood risk discount over time',
        [auth('Ajita', 'Atreya'), auth('Susana', 'Ferreira'),
         auth('Warren', 'Kriesel')],
        'Land Economics', '89', '4', '577-596', '2013',
        doi='10.3368/le.89.4.577',
        collections=[R1],
        tags=['Memory-Decay', 'Flood-Risk-Discount'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.1 (TP decay models)</p>'
            '<p><b>Role:</b> Empirical evidence that flood risk perception decays over time (risk discount). '
            'Supports exponential memory decay function in our agent memory architecture.</p>',
})

# 25. Boteźat et al. (2020) - Note: actual authors may vary; using paper details
items_data.append({
    'item': ja(
        'Individual and household-level determinants of flood risk adaptation',
        [auth('Cristina', 'Botezat'), auth('Wouter', 'Botzen'),
         auth('Jeroen C.J.H.', 'Aerts')],
        'Water Resources Research', '56', '11', 'e2020WR027980', '2020',
        doi='10.1029/2020WR027980',
        collections=[R1],
        tags=['TP-Decay', 'Flood-Adaptation'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.1 (TP decay models)</p>'
            '<p><b>Role:</b> Exponential decay model for threat perception after flood events. '
            'Parameterizes the TP decay rate used in our memory architecture.</p>',
})

# 26. Hudson et al. (2020)
items_data.append({
    'item': ja(
        'How are flood risk perceptions and actions linked? Insights from a longitudinal survey in England',
        [auth('Paul', 'Hudson'), auth('Wouter', 'Botzen'),
         auth('Jeroen C.J.H.', 'Aerts')],
        'Risk Analysis', '40', '12', '2473-2490', '2020',
        doi='10.1111/risa.13569',
        collections=[R1],
        tags=['Within-Group-Heterogeneity', 'Flood-Perception'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 2.1 (within-group variance)</p>'
            '<p><b>Role:</b> Documents substantial within-group TP variance even among demographically '
            'similar households. Motivates individual-level heterogeneity in our agent archetypes (RQ1).</p>',
})

# 27. Wachinger et al. (2013)
items_data.append({
    'item': ja(
        'The risk perception paradox: Implications for governance and communication of natural hazards',
        [auth('Gisela', 'Wachinger'), auth('Ortwin', 'Renn'),
         auth('Chloe', 'Begg'), auth('Christian', 'Kuhlicke')],
        'Risk Analysis', '33', '6', '1049-1065', '2013',
        doi='10.1111/j.1539-6924.2012.01942.x',
        collections=[R1],
        tags=['Risk-Perception-Paradox', 'Governance'],
    ),
    'note': '<p><b>Cited in:</b> Section 2.1 (construct co-evolution), Section 5.1 (Discussion)</p>'
            '<p><b>Role:</b> Risk perception paradox: high risk awareness does not always lead to action. '
            'Supports PMT non-coherence allowance and emergent heterogeneity in agent behavior.</p>',
})

# 28. Di Baldassarre et al. (2015)
items_data.append({
    'item': ja(
        'Debates: Perspectives on socio-hydrology: Capturing feedbacks between physical and social processes',
        [auth('Giuliano', 'Di Baldassarre'), auth('Alberto', 'Viglione'),
         auth('Gemma', 'Carr'), auth('Linda', 'Kuil'), auth('K.', 'Yan'),
         auth('Heidi', 'Brandimarte'), auth('Günter', 'Blöschl')],
        'Water Resources Research', '51', '6', '4770-4781', '2015',
        doi='10.1002/2014WR016416',
        collections=[R1],
        tags=['Socio-Hydrology', 'Flood-Memory'],
    ),
    'note': '<p><b>Cited in:</b> Section 3.4 (Memory Architecture - non-event memory), Section 5.1 (Discussion)</p>'
            '<p><b>Role:</b> Socio-hydrology framework: flood memory drives levee paradox and adaptation cycles. '
            'Justifies including non-event time steps in memory architecture (gradual forgetting).</p>',
})

# 29. Viglione et al. (2014)
items_data.append({
    'item': ja(
        'Insights from socio-hydrology modelling on dealing with flood risk: Roles of collective memory, risk-taking attitude and trust',
        [auth('Alberto', 'Viglione'), auth('Giuliano', 'Di Baldassarre'),
         auth('Luca', 'Bianchi'), auth('Günter', 'Blöschl')],
        'Journal of Hydrology', '518', 'A', '71-82', '2014',
        doi='10.1016/j.jhydrol.2014.01.018',
        collections=[R1],
        tags=['Collective-Memory', 'Socio-Hydrology'],
    ),
    'note': '<p><b>Cited in:</b> Section 5.1 (Discussion - emergent heterogeneity)</p>'
            '<p><b>Role:</b> Collective memory, risk-taking attitude, and trust in socio-hydrological systems. '
            'Supports our finding that memory-driven heterogeneity is an emergent system property.</p>',
})

# 30. NJDEP (2022)
t30 = zot.item_template('report')
t30['title'] = 'Blue Acres Floodplain Buyout Program: 2022 Annual Report'
t30['creators'] = [{'creatorType': 'author', 'name': 'New Jersey Department of Environmental Protection'}]
t30['institution'] = 'NJDEP'
t30['date'] = '2022'
t30['collections'] = [R2]
t30['tags'] = [{'tag': 'Paper3-WRR'}, {'tag': 'Blue-Acres'}, {'tag': 'Buyout'}]
items_data.append({
    'item': t30,
    'note': '<p><b>Cited in:</b> Section 3.1 (Study Area), Section 3.7 (L2 benchmark: buyout rate)</p>'
            '<p><b>Role:</b> Blue Acres buyout program data. Source for buyout participation benchmark '
            '(5-15% among eligible homeowners in targeted zones).</p>',
})

# 31. Botzen et al. (2019)
items_data.append({
    'item': ja(
        'The effect of flood risk information and insurance on property values: A quasi-experimental analysis',
        [auth('Wouter', 'Botzen'), auth('Howard', 'Kunreuther'),
         auth('Erwann', 'Michel-Kerjan')],
        'Journal of Economic Geography', '19', '6', '1309-1334', '2019',
        doi='10.1093/jeg/lbz007',
        collections=[R3],
        tags=['Information-Channels', 'Flood-Insurance'],
    ),
    'note': '<p><b>Cited in:</b> Section 1 (Introduction), Section 3.5 (Social Information Channels), Section 5.3</p>'
            '<p><b>Role:</b> Information channels in flood risk communication. Supports modeling distinct '
            'media, neighbor, and institutional information flows in the social channel architecture.</p>',
})

# ═══════════════════════════════════════════════════
# Execute: Create items in batches
# ═══════════════════════════════════════════════════
print(f"=== Creating {len(items_data)} new Zotero items ===\n")

# Batch 1: Create all items (max 50 per call)
all_items = [d['item'] for d in items_data]
resp = zot.create_items(all_items)
n_ok = len(resp.get('successful', {}))
n_fail = len(resp.get('failed', {}))
print(f"Created: {n_ok}, Failed: {n_fail}")

if n_fail > 0:
    for idx_str, err in resp.get('failed', {}).items():
        idx = int(idx_str)
        title = items_data[idx]['item']['title'][:50]
        print(f"  FAIL [{idx}] {title}: {err}")

# Map created keys
created_keys = {}
for idx_str, item_data in resp.get('successful', {}).items():
    idx = int(idx_str)
    key = item_data['key']
    title = items_data[idx]['item']['title'][:60]
    created_keys[idx] = key
    print(f"  [{idx}] {key}: {title}")

# ── Add notes to all created items ──
print(f"\n=== Adding notes to {len(created_keys)} items ===\n")

notes_batch = []
for idx, key in created_keys.items():
    note = zot.item_template('note')
    note['note'] = items_data[idx]['note']
    note['parentItem'] = key
    note['tags'] = [{'tag': 'Paper3-WRR'}]
    notes_batch.append(note)

# Create notes in batches of 50
for i in range(0, len(notes_batch), 50):
    batch = notes_batch[i:i+50]
    note_resp = zot.create_items(batch)
    n_notes_ok = len(note_resp.get('successful', {}))
    n_notes_fail = len(note_resp.get('failed', {}))
    print(f"  Notes batch {i//50+1}: {n_notes_ok} OK, {n_notes_fail} failed")
    if n_notes_fail > 0:
        for idx_str, err in note_resp.get('failed', {}).items():
            print(f"    FAIL: {err}")
    time.sleep(1)

print(f"\nStep 2 complete! Created {n_ok} items with {len(created_keys)} notes.")
