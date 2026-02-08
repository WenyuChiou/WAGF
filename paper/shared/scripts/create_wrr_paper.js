const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, LevelFormat, PageBreak,
  TabStopType, TabStopPosition
} = require("docx");

const FONT = "Times New Roman";
const SZ = 24; // 12pt
const H1 = 28; // 14pt
const H2 = 26; // 13pt
const LS = 480; // double-spaced
const M = 1440; // 1 inch margins

const n = (t) => new TextRun({ text: t, font: FONT, size: SZ });
const b = (t) => new TextRun({ text: t, font: FONT, size: SZ, bold: true });
const i = (t) => new TextRun({ text: t, font: FONT, size: SZ, italics: true });
const sup = (t) => new TextRun({ text: t, font: FONT, size: SZ, superScript: true });
const sub = (t) => new TextRun({ text: t, font: FONT, size: SZ, subScript: true });

const p = (runs, opts = {}) => new Paragraph({
  spacing: { line: LS, after: 120 },
  alignment: opts.align || AlignmentType.JUSTIFIED,
  indent: opts.indent ? { firstLine: 360 } : undefined,
  children: typeof runs === "string" ? [n(runs)] : runs,
  ...(opts.extra || {}),
});

const h1 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 360, after: 240, line: LS },
  children: [new TextRun({ text: t, font: FONT, size: H1, bold: true })],
});
const h2 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 240, after: 120, line: LS },
  children: [new TextRun({ text: t, font: FONT, size: H2, bold: true })],
});
const eq = (runs) => new Paragraph({
  spacing: { line: LS, before: 120, after: 120 },
  alignment: AlignmentType.CENTER,
  children: runs,
});
const figPlaceholder = (text) => new Paragraph({
  spacing: { before: 240, after: 60, line: LS },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: `[${text}]`, font: FONT, size: SZ, italics: true, color: "CC0000" })],
});
const pb = () => new Paragraph({ children: [new PageBreak()] });

// Table 1
const tb = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
const tbs = { top: tb, bottom: tb, left: tb, right: tb };
const hs = { fill: "D9E2F3", type: ShadingType.CLEAR };
const tc = (text, w, hdr) => new TableCell({
  borders: tbs, width: { size: w, type: WidthType.DXA },
  shading: hdr ? hs : undefined, verticalAlign: VerticalAlign.CENTER,
  children: [new Paragraph({ spacing: { line: 276 }, children: [new TextRun({ text, font: FONT, size: 20, bold: !!hdr })] })],
});
const tr = (cells) => new TableRow({ children: cells });

const table1 = new Table({
  columnWidths: [2200, 3580, 3580],
  rows: [
    new TableRow({ tableHeader: true, children: [tc("Component", 2200, 1), tc("Flood Adaptation", 3580, 1), tc("Irrigation Management", 3580, 1)] }),
    tr([tc("Skills", 2200), tc("elevate, insure, relocate, both, do_nothing", 3580), tc("increase, decrease, efficiency, acreage, maintain", 3580)]),
    tr([tc("Physical validators", 2200), tc("already_elevated, already_insured", 3580), tc("water_right_cap, already_efficient", 3580)]),
    tr([tc("Institutional validators", 2200), tc("\u2014", 3580), tc("compact_allocation, drought_severity", 3580)]),
    tr([tc("Memory engine", 2200), tc("Flood trauma recall", 3580), tc("Regret feedback", 3580)]),
    tr([tc("Appraisal framework", 2200), tc("PMT (threat/coping)", 3580), tc("Dual appraisal (WSA/ACA)", 3580)]),
    tr([tc("Agents", 2200), tc("100 households \u00d7 10 yr", 3580), tc("78 districts \u00d7 42 yr", 3580)]),
  ],
});

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: SZ } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: H1, bold: true, font: FONT }, paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: H2, bold: true, font: FONT }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "kp", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{
    properties: {
      page: { margin: { top: M, right: M, bottom: M, left: M }, pageNumbers: { start: 1 } },
    },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "WAGF: Governance Middleware for LLM-Driven Water ABMs", font: FONT, size: 18, italics: true, color: "666666" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Page ", font: FONT, size: 18 }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 }), new TextRun({ text: " of ", font: FONT, size: 18 }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 18 })] })] }) },
    children: [
      // ═══ TITLE ═══
      new Paragraph({ spacing: { after: 120, line: LS }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "WAGF: A Governance Middleware for LLM-Driven Agent-Based Models of Human\u2013Water Systems", font: FONT, size: 32, bold: true })] }),
      new Paragraph({ spacing: { after: 60, line: LS }, alignment: AlignmentType.CENTER, children: [n("Wen-Yu Chen"), sup("1"), n(", Second Author"), sup("1")] }),
      new Paragraph({ spacing: { after: 240, line: LS }, alignment: AlignmentType.CENTER, children: [sup("1"), new TextRun({ text: "Department of Civil and Environmental Engineering, Lehigh University, Bethlehem, PA, USA", font: FONT, size: 22, italics: true })] }),
      new Paragraph({ spacing: { after: 360, line: LS }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Corresponding author: Wen-Yu Chen (wec225@lehigh.edu)", font: FONT, size: 22 })] }),

      // ═══ KEY POINTS ═══
      h1("Key Points"),
      new Paragraph({ numbering: { reference: "kp", level: 0 }, spacing: { line: LS }, children: [n("WAGF eliminates 33% hallucination rate in ungoverned LLM agents while preserving genuine behavioral diversity")] }),
      new Paragraph({ numbering: { reference: "kp", level: 0 }, spacing: { line: LS }, children: [n("Effective Behavioral Entropy (EBE) metric separates true decision diversity from hallucination-inflated entropy")] }),
      new Paragraph({ numbering: { reference: "kp", level: 0 }, spacing: { line: LS, after: 240 }, children: [n("Governance middleware transfers across domains: flood adaptation (100 agents, 10 yr) and irrigation (78 agents, 42 yr)")] }),

      // ═══ ABSTRACT ═══
      h1("Abstract"),
      p([n("Large language models (LLMs) offer a promising path toward cognitively realistic agent-based models (ABMs) for water resources planning, but unconstrained LLM agents produce physically impossible decisions\u2014a phenomenon we term "), i("behavioral hallucination"), n(". We present WAGF (Water Agent Governance Framework), an open-source middleware that enforces domain-specific physical and institutional constraints on LLM-driven agents while preserving emergent behavioral diversity. WAGF implements a three-pillar architecture: (1) a rule-based validator chain that rejects impossible actions, (2) a tiered cognitive memory system that encodes prior experience, and (3) a priority context builder that structures LLM prompts with domain knowledge. We introduce the Effective Behavioral Entropy (EBE) metric, defined as EBE = H"), sub("norm"), n(" \u00d7 (1 \u2212 R"), sub("H"), n("), which disentangles genuine decision diversity from hallucination-inflated entropy. In a flood adaptation case study (100 agents, 10 years, 7 LLM configurations), ungoverned agents exhibit a 33% hallucination rate; WAGF-governed agents reduce this to <2% while maintaining EBE 32% higher. We demonstrate domain transferability through a Colorado River irrigation case study (78 districts, 42 years). The framework, metrics, and experiment code are available at [GitHub URL].")]),

      // ═══ PLS ═══
      h1("Plain Language Summary"),
      p("Artificial intelligence language models can power virtual agents that make human-like decisions in water management simulations. However, without oversight, these agents make impossible choices\u2014like buying flood insurance they already own or elevating a home that is already raised. We developed WAGF, a software layer that checks each agent\u2019s decision against physical and institutional rules before it takes effect, while still allowing agents to make diverse, realistic choices. We show that unchecked agents make impossible decisions 33% of the time, inflating the apparent diversity of their behavior. Our governance middleware eliminates these errors while preserving genuine decision-making variety. We demonstrate the approach in two water domains: household flood adaptation and Colorado River irrigation management."),

      pb(),

      // ═══ 1. INTRODUCTION ═══
      h1("1. Introduction"),
      p([n("Agent-based models (ABMs) have become a central tool for understanding coupled human\u2013water systems, from flood risk adaptation (Aerts et al., 2018; Di Baldassarre et al., 2013) to irrigation management under scarcity (Hung & Yang, 2021). Traditional ABMs rely on utility-maximizing or rule-based agents whose behavioral diversity is limited by the modeler\u2019s ability to enumerate decision heuristics (Filatova et al., 2013; Berglund, 2015). Large language models (LLMs) offer a fundamentally different approach: generative agents that produce heterogeneous, context-sensitive decisions from natural-language reasoning (Park et al., 2023; Gao et al., 2024). Recent work has demonstrated that LLMs can autonomously handle complex scientific tasks (Boiko et al., 2023), suggesting their potential for realistic behavioral simulation in socio-hydrological systems (Sivapalan et al., 2012).")], { indent: true }),

      p([n("However, LLM agents produce plausible but physically impossible outputs\u2014a well-documented limitation in natural language generation known as hallucination (Ji et al., 2023). In water resource ABMs, this manifests as agents re-elevating already-elevated homes, purchasing insurance they already own, or requesting water allocations exceeding their legal rights. These behavioral hallucinations are structurally analogous to model collapse in recursive training (Shumailov et al., 2024): without external constraints, LLM agents converge on patterns that appear diverse but violate domain physics. Existing LLM-ABM frameworks lack mechanisms for enforcing physical and institutional constraints on agent decisions, leaving hallucination rates unquantified and uncontrolled.")], { indent: true }),

      p([n("We address this gap with three contributions. First, we present WAGF (Water Agent Governance Framework), an open-source middleware that enforces domain-specific constraints on LLM-driven agents through a three-pillar architecture: a rule-based validator chain, a tiered cognitive memory system, and a priority context builder. Second, we introduce the Effective Behavioral Entropy (EBE) metric that disentangles genuine decision diversity from hallucination-inflated entropy. Third, we demonstrate WAGF\u2019s domain transferability through two case studies\u2014household flood adaptation (100 agents, 10 years) and Colorado River irrigation management (78 districts, 42 years)\u2014showing that governance eliminates behavioral hallucination while preserving emergent diversity.")], { indent: true }),

      // ═══ 2. WAGF ARCHITECTURE ═══
      h1("2. WAGF Architecture"),
      h2("2.1 Three-Pillar Design"),
      p([n("WAGF operates as a middleware layer between LLM agents and the simulation engine, following a strict separation of concerns: the LLM makes decisions, WAGF validates them, and the simulation engine executes approved actions (Figure 1). This design ensures that the governance layer never generates decisions or mutates simulation state directly.")], { indent: true }),

      p([n("The first pillar, "), b("governance"), n(", implements a rule-based validator chain defined in YAML configuration files. Each rule specifies a condition (e.g., agent has already adopted efficient irrigation) and a consequence (block the action, with an explanatory message). Rules are evaluated in priority order: identity rules (physical impossibilities) take precedence over thinking rules (behavioral coherence checks), which take precedence over warnings. When a proposed action is rejected, WAGF re-prompts the LLM with the rejection reason, allowing the agent to revise its decision (up to three retries). This approach draws on constitutional AI principles (Bai et al., 2022), applying rule-based constraints rather than learned reward signals.")], { indent: true }),

      p([n("The second pillar, "), b("cognitive memory"), n(", provides agents with structured access to their decision history. WAGF supports multiple memory engines: a sliding-window engine that maintains recent events (Group B baseline), and a human-centric engine that encodes episodic memories with emotional arousal weights and applies stochastic consolidation and decay (Group C). Memory content is injected into the LLM prompt as contextual background, enabling agents to learn from experience without requiring fine-tuning.")], { indent: true }),

      p([n("The third pillar, "), b("priority context"), n(", structures the information provided to LLMs using a tiered builder. Tier 1 (must-include) contains the agent\u2019s current state, environmental conditions, and available actions. Tier 2 (should-include) adds memory summaries and social observations. Tier 3 (nice-to-have) provides historical trends and institutional background. This tiering ensures that critical decision context is never truncated by token limits, following principles from instruction-tuned prompt design (Ouyang et al., 2022; Wei et al., 2022).")], { indent: true }),

      h2("2.2 Skill Registry and Validator Chain"),
      p([n("WAGF defines agent capabilities as named \u201cskills\u201d with pre- and post-conditions. The SkillBrokerEngine processes each decision through a six-phase pipeline: (1) context assembly, (2) LLM inference via Ollama (Ollama, 2024), (3) response parsing with a four-layer fallback (JSON, enclosure delimiters, regex, digit extraction), (4) validation against the rule chain, (5) execution of approved skills, and (6) audit logging (Figure 2). Every decision is logged with its validation status, enabling post-hoc hallucination analysis.")], { indent: true }),

      h2("2.3 Domain Instantiation"),
      p([n("WAGF is domain-agnostic: the same engine serves both flood adaptation and irrigation management (Table 1). Domain specificity is achieved entirely through configuration\u2014skill definitions, validator rules, and prompt templates\u2014without modifying core code. For flood adaptation, skills include home elevation, insurance purchase, and relocation, with Protection Motivation Theory (Rogers, 1975, 1983) providing the appraisal framework. For irrigation, skills include demand adjustment, efficiency adoption, and acreage reduction, with a dual-appraisal framework (Water Scarcity Assessment / Adaptive Capacity Assessment) adapted from Hung and Yang (2021).")], { indent: true }),

      // Table 1
      new Paragraph({ spacing: { before: 240, after: 60, line: LS }, alignment: AlignmentType.CENTER, children: [b("Table 1. "), n("WAGF instantiation for two water resource domains.")] }),
      table1,
      new Paragraph({ spacing: { after: 240 }, children: [] }),

      // ═══ 3. METRICS ═══
      h1("3. Metrics"),
      p([n("We define "), i("behavioral hallucination"), n(" as an action a"), sub("t"), n(" proposed by an LLM agent that violates physical or institutional constraints given the agent\u2019s state s"), sub("t\u22121"), n(" at the previous timestep. Formally, let \u0391(s"), sub("t\u22121"), n(") denote the set of feasible actions given state s"), sub("t\u22121"), n(". An action is a behavioral hallucination if a"), sub("t"), n(" \u2209 \u0391(s"), sub("t\u22121"), n("). This differs from textual hallucination (Ji et al., 2023) in that the output may be linguistically coherent but physically impossible. The hallucination rate is:")]),
      eq([n("R"), sub("H"), n(" = n"), sub("hall"), n(" / n"), sub("total"), n("          (1)")]),
      p([n("The Effective Behavioral Entropy (EBE) combines normalized Shannon entropy (Shannon, 1948) with the hallucination penalty:")]),
      eq([n("EBE = H"), sub("norm"), n(" \u00d7 (1 \u2212 R"), sub("H"), n(") = [H / log"), sub("2"), n("(k)] \u00d7 [1 \u2212 n"), sub("hall"), n(" / n"), sub("total"), n("]          (2)")]),
      p([n("where k is the number of available actions and H = \u2212\u03A3 p"), sub("i"), n(" log"), sub("2"), n(" p"), sub("i"), n(" is the Shannon entropy of the observed action distribution. EBE ranges from 0 (no diversity or entirely hallucinated) to 1 (maximum diversity with zero hallucination). When computing corrected entropy, hallucinated actions are replaced with the agent\u2019s default action (DoNothing for flood, maintain_demand for irrigation). We report both raw and corrected entropy alongside EBE to enable comparison (Jost, 2006).")]),

      pb(),

      // ═══ 4. FLOOD CASE STUDY ═══
      h1("4. Case Study 1: Flood Adaptation"),
      h2("4.1 Experimental Design"),
      p([n("We simulate 100 household agents making annual flood adaptation decisions over 10 years in a flood-prone community. Flood events occur in years 3, 4, and 9, with a baseline annual flood probability of 0.20. Agents choose among five actions: elevate their home, purchase insurance, relocate, both (elevate + insure), or do nothing.")], { indent: true }),
      p([n("We compare three governance configurations using Gemma 3 4B (Gemma Team, 2024) as the primary LLM: Group A (ungoverned\u2014raw LLM output executed directly), Group B (WAGF governance with sliding-window memory), and Group C (WAGF governance with human-centric memory and priority context schema). All groups use identical initial agent profiles, flood sequences, and random seeds to isolate the effect of governance.")], { indent: true }),

      h2("4.2 Hallucination Detection and Correction"),
      p([n("We identify behavioral hallucinations by comparing each agent\u2019s proposed action against its state at the previous timestep. An agent that proposes to elevate an already-elevated home, insure an already-insured property, or perform \u201cboth\u201d when one component is already completed is flagged as hallucinating (Equation 1). Year 1 is excluded because no prior state exists.")], { indent: true }),
      p([n("Group A exhibits a mean hallucination rate of 33.3% across years 2\u201310, with rates increasing over time as more agents accumulate protective measures (from 22% in year 2 to 40% in year 10). Group B reduces hallucination to 6.1% through governance intervention, while Group C achieves 1.9% by combining governance with human-centric memory that reinforces prior decisions.")], { indent: true }),

      h2("4.3 Results"),
      p([n("Figure 3 presents the key results. Ungoverned agents (Group A) show high raw entropy (mean H"), sub("norm"), n(" = 0.61) that appears to indicate rich behavioral diversity, but EBE reveals this is largely hallucination-inflated: mean EBE = 0.41 (Equation 2). Governed agents maintain higher effective diversity\u2014Group B: EBE = 0.56, Group C: EBE = 0.56\u2014despite lower raw entropy, because their decisions are physically valid.")], { indent: true }),
      p([n("The most striking behavioral difference is relocation. Group A produces zero cumulative relocations\u2014agents repeatedly choose \u201cdo nothing\u201d or hallucinate impossible actions, never reaching the psychological threshold for relocation. Group B achieves 32% cumulative relocation and Group C reaches 37%, demonstrating that governance enables rather than constrains meaningful behavioral diversity. The year-9 flood event is particularly informative: Group C adds 12 new relocations (memory of years 3\u20134 floods amplifies the response), while Group B adds only 1 (window memory has already forgotten early trauma).")], { indent: true }),

      figPlaceholder("FIGURE 3: Flood Results \u2014 (a) Raw vs corrected entropy with EBE, (b) Cumulative relocation curves"),

      // ═══ 5. IRRIGATION CASE STUDY ═══
      h1("5. Case Study 2: Colorado River Irrigation"),
      h2("5.1 Setup"),
      p([n("We demonstrate WAGF\u2019s domain transferability by applying it to irrigation demand management in the Colorado River Basin, following Hung and Yang (2021). We simulate 78 irrigation districts over a 42-year planning horizon (2019\u20132060) using CRSS precipitation projections (USBR, 2012). Districts are mapped one-to-one onto real Upper Basin and Lower Basin diversion nodes from the CRSS database: 56 Upper Basin agents across seven state groups (WY, UT, CO, NM, AZ) and 22 Lower Basin agents (e.g., Imperial Irrigation District, Yuma County WUA, Mohave Valley IDD).")], { indent: true }),
      p([n("Each district is assigned to one of three behavioral clusters calibrated via Farmer Q-Learning by Hung and Yang (2021): "), i("Aggressive"), n(" (bold demand swings, magnitude default 20%), "), i("Forward-Looking Conservative"), n(" (cautious planning, 10%), and "), i("Myopic Conservative"), n(" (status-quo bias, 5%). Agents choose among five skills per year: increase_demand, decrease_demand, adopt_efficiency (one-time drip irrigation investment), reduce_acreage (fallow farmland), and maintain_demand. Each demand-change skill carries a cluster-specific magnitude cap (30%/15%/10%), allowing quantitative heterogeneity within the governed action space (Yang et al., 2009; Hadjimichael et al., 2020).")], { indent: true }),
      p([n("The irrigation domain uses a dual-appraisal framework adapted from Protection Motivation Theory: Water Scarcity Assessment (WSA) evaluates perceived drought threat from supply signals (drought index, shortage tier, curtailment ratio), while Adaptive Capacity Assessment (ACA) evaluates farm-level coping resources (financial flexibility, technology status, utilisation margin). Governance rules enforce physical constraints\u2014agents cannot request water beyond their legal right (water_right_cap), adopt technology they already own (already_efficient), or reduce demand below a 10% utilisation floor (minimum_utilisation_floor)\u2014and institutional constraints derived from the Colorado River Compact (compact_allocation, drought_severity). The experiment uses Gemma 3 4B with strict governance and human-centric memory (5-year window, importance-weighted episodic storage).")], { indent: true }),

      h2("5.2 Results"),
      p([n("Figure 4 presents aggregate demand trajectories by basin. Upper Basin WAGF-governed agents request 39.7% more water than the CRSS static baseline over 42 years, but after curtailment enforcement the actual diversion narrows to +28.8%\u2014the gap between \u201cpaper water\u201d (requested) and \u201cwet water\u201d (delivered) that is a central tension in Colorado River management (Hadjimichael et al., 2020). Lower Basin agents show a smaller divergence (+18.2% request, +9.1% diversion), consistent with the more constrained institutional environment of junior rights holders.")], { indent: true }),
      p([n("Governance produces 526 interventions across 3,276 agent-year decisions (16.1% intervention rate), with 173 successful retries (agents self-corrected after receiving the violation message) and zero parsing failures. The two most frequently triggered rules are high_threat_no_maintain (340 triggers, blocking status-quo decisions during high-scarcity years) and low_threat_no_increase (183 triggers, preventing demand increases during low-scarcity periods). An additional 1,055 warning-level observations flag high_threat_high_cope_no_increase\u2014a coherence monitor that records but does not block demand increases when both threat and coping capacity are high.")], { indent: true }),
      p([n("Cluster differentiation emerges clearly from the LLM-driven decisions. Aggressive agents allocate 40.9% of decisions to increase_demand; Forward-Looking Conservative agents allocate 78.6% to decrease_demand; Myopic Conservative agents allocate 80.2% to maintain_demand. This behavioral stratification mirrors the qualitative patterns documented in the FQL calibration (Hung & Yang, 2021, Figure 5), despite operating through natural-language reasoning rather than Q-value updates.")], { indent: true }),
      p([n("Notably, governance catches a hallucination type absent in the flood domain: "), i("economic hallucination"), n(", where persona-anchored conservative agents repeatedly reduce demand until utilisation approaches zero\u2014a physically possible but economically absurd trajectory. The minimum_utilisation_floor identity rule, combined with a magnitude taper near the floor, prevents this spiral while allowing genuine conservation behavior. Over 42 years, efficient-system adoption rises from 1.3% to 70.5% of agents, and the decision mix shifts from 41% increase_demand (first decade) to 35% (last decade) with decrease_demand rising from 19% to 30%\u2014reflecting adaptive learning under sustained drought pressure.")], { indent: true }),

      figPlaceholder("FIGURE 4: WAGF-governed irrigation demand vs. CRSS baseline (a) Upper Basin, (b) Lower Basin, 2019\u20132060");

      pb(),

      // ═══ 6. DISCUSSION ═══
      h1("6. Discussion"),
      p([n("EBE provides a diagnostic that raw entropy cannot: the ability to distinguish genuine behavioral diversity from hallucination artifacts. In Group A, raw H"), sub("norm"), n(" averages 0.61\u2014suggesting moderate diversity\u2014but EBE corrects this to 0.41, revealing that one-third of apparent diversity is physically impossible. This finding implies that studies reporting LLM-ABM behavioral richness without hallucination accounting may overestimate the quality of emergent behavior. We recommend that the community adopt hallucination-corrected metrics alongside raw diversity measures (Jost, 2006).")], { indent: true }),
      p([n("Cross-model robustness testing across seven LLM configurations (Gemma 3 4B/12B/27B, DeepSeek R1 1.5B/8B/14B/32B) reveals that governance prevents mode collapse\u2014a phenomenon where ungoverned models converge on a single dominant action. Gemma 3 12B exhibits 79% hallucination in Group A (mode collapse to \u201cBoth\u201d), while DeepSeek R1 8B locks into Elevation (97%). Governed groups maintain H"), sub("norm"), n(" in the 0.3\u20130.8 range across all model sizes (Gemma Team, 2024; Guo et al., 2025).")], { indent: true }),
      p([n("Several limitations warrant discussion. First, our primary results are based on single-seed runs (N=100 agents provides within-run statistical power, but cross-seed variability is not quantified). Second, LLM temperature is fixed at the model default; sensitivity to sampling parameters remains unexplored. Third, the irrigation case study demonstrates governance transferability but produces limited behavioral diversity due to uniform environmental signals. Fourth, the soft governance design\u2014where rejected actions still execute with REJECTED status after maximum retries\u2014is intentional for measurement purposes but would require hard enforcement in operational applications.")], { indent: true }),

      // ═══ 7. CONCLUSIONS ═══
      h1("7. Conclusions"),
      p([n("We have presented WAGF, the first governance middleware for LLM-driven agent-based models of human\u2013water systems, along with the Effective Behavioral Entropy (EBE) metric for measuring genuine decision diversity. Three findings emerge from our two-domain validation.")], { indent: true }),
      p([n("First, behavioral hallucination is structural, not stochastic. Ungoverned LLM agents produce 33% physically impossible decisions in flood adaptation, with rates increasing as agents accumulate state\u2014a systematic failure that cannot be resolved by prompt engineering alone.")], { indent: true }),
      p([n("Second, governance enables rather than constrains diversity. WAGF-governed agents achieve 32% higher EBE than ungoverned agents, and their cumulative relocation rates (32\u201337%) far exceed the ungoverned baseline (0%), demonstrating that physically valid decision spaces produce richer behavioral outcomes.")], { indent: true }),
      p([n("Third, WAGF transfers across domains without core code changes. The same governance engine serves both flood adaptation (PMT appraisal, 5 skills, 100 agents) and irrigation management (dual appraisal, 5 skills, 78 districts) through configuration-only instantiation, supporting the vision of reusable infrastructure for socio-hydrological ABMs (Giuliani et al., 2022; Castelletti et al., 2010).")], { indent: true }),
      p([n("Future work should address multi-agent interaction governance (agents currently decide independently), dynamic rule learning (governance rules are currently static), and integration with larger basin-scale models (Berglund, 2015). WAGF, the EBE metric, and all experiment code are available open-source at [GitHub URL].")], { indent: true }),

      pb(),

      // ═══ BACK MATTER ═══
      h1("Data Availability Statement"),
      p("Simulation logs, agent configurations, and analysis scripts are archived at [Zenodo DOI] and available at [GitHub URL] under the MIT License. The CRSS precipitation projections are from the U.S. Bureau of Reclamation (USBR, 2012). All raw LLM traces (JSONL format) and governance audit logs are included in the archive to support independent verification."),
      h1("Conflict of Interest"),
      p("The authors declare no conflicts of interest relevant to this study."),
      h1("Author Contributions"),
      p([b("Wen-Yu Chen: "), n("Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Writing \u2013 Original Draft, Visualization. "), b("[Second Author]: "), n("Supervision, Writing \u2013 Review & Editing, Funding acquisition.")]),
      h1("Acknowledgments"),
      p("This work was supported by [funding source]."),

      pb(),

      // ═══ REFERENCES ═══
      h1("References"),
      p([n("Aerts, J. C. J. H., et al. (2018). Integrating human behaviour dynamics into flood disaster risk assessment. "), i("Nature Climate Change"), n(", 8(3), 193\u2013199.")]),
      p([n("Bai, Y., et al. (2022). Constitutional AI: Harmlessness from AI feedback. "), i("arXiv:2212.08073"), n(".")]),
      p([n("Berglund, E. Z. (2015). Using agent-based modeling for water resources planning and management. "), i("J. Water Resour. Plan. Manag."), n(", 141(11), 04015025.")]),
      p([n("Boiko, D. A., et al. (2023). Emergent autonomous scientific research capabilities of large language models. "), i("Nature"), n(", 624, 570\u2013578.")]),
      p([n("Bubeck, P., et al. (2012). A review of risk perceptions and other factors that influence flood mitigation behavior. "), i("Risk Analysis"), n(", 32(9), 1481\u20131495.")]),
      p([n("Castelletti, A., et al. (2010). Tree-based reinforcement learning for optimal water reservoir operation. "), i("Water Resour. Res."), n(", 46(9), W09507.")]),
      p([n("Di Baldassarre, G., et al. (2013). Socio-hydrology: Conceptualising human-flood interactions. "), i("Hydrol. Earth Syst. Sci."), n(", 17(8), 3295\u20133303.")]),
      p([n("Filatova, T., et al. (2013). Spatial agent-based models for socio-ecological systems. "), i("Environ. Model. Softw."), n(", 45, 1\u20137.")]),
      p([n("Gao, C., et al. (2024). Large language models empowered agent-based modeling and simulation: A survey. "), i("Humanit. Soc. Sci. Commun."), n(", 11, 1498.")]),
      p([n("Gemma Team (2024). Gemma: Open models based on Gemini research and technology. "), i("arXiv:2403.08295"), n(".")]),
      p([n("Giuliani, M., et al. (2016). Is robustness really robust? "), i("Climatic Change"), n(", 135(3), 409\u2013424.")]),
      p([n("Giuliani, M., et al. (2022). Is it worth using AI to solve the water crisis? "), i("Water Resour. Res."), n(", 58(4), e2021WR031219.")]),
      p([n("Guo, D., et al. (2025). DeepSeek-R1: Incentivizing reasoning capability in LLMs via reinforcement learning. "), i("arXiv:2501.12948"), n(".")]),
      p([n("Hadjimichael, A., et al. (2020). Defining robustness for diverse stakeholder interests in institutionally complex river basins. "), i("Earth\u2019s Future"), n(", 8(7), e2020EF001503.")]),
      p([n("Herman, J. D., et al. (2015). How should robustness be defined for water systems planning under change? "), i("J. Water Resour. Plan. Manag."), n(", 141(10), 04015012.")]),
      p([n("Hung, C.-L., & Yang, Y. C. E. (2021). An agent-based modeling approach for water resources management under uncertainty. "), i("Water Resour. Res."), n(", 57(10), e2021WR030519.")]),
      p([n("Ji, Z., et al. (2023). Survey of hallucination in natural language generation. "), i("ACM Comput. Surv."), n(", 55(12), 1\u201338.")]),
      p([n("Jost, L. (2006). Entropy and diversity. "), i("Oikos"), n(", 113(2), 363\u2013375.")]),
      p([n("Kanta, L., & Zechman, E. (2014). Complex adaptive systems framework for urban water resources. "), i("J. Water Resour. Plan. Manag."), n(", 140(1), 75\u201385.")]),
      p([n("Ollama (2024). Ollama: Run large language models locally. https://ollama.com")]),
      p([n("Ouyang, L., et al. (2022). Training language models to follow instructions with human feedback. "), i("NeurIPS"), n(", 35, 27730\u201327744.")]),
      p([n("Park, J. S., et al. (2023). Generative agents: Interactive simulacra of human behavior. "), i("ACM UIST"), n(", 1\u201322.")]),
      p([n("Rao, A. S., & Georgeff, M. P. (1995). BDI agents: From theory to practice. "), i("Proc. 1st Int. Conf. Multi-Agent Syst."), n(", 312\u2013319.")]),
      p([n("Rogers, R. W. (1975). A protection motivation theory of fear appeals and attitude change. "), i("The Journal of Psychology"), n(", 91(1), 93\u2013114.")]),
      p([n("Rogers, R. W. (1983). Cognitive and psychological processes in fear appeals and attitude change. In J. Cacioppo & R. Petty (Eds.), "), i("Social Psychophysiology"), n(" (pp. 153\u2013176). Guilford Press.")]),
      p([n("Shannon, C. E. (1948). A mathematical theory of communication. "), i("Bell Syst. Tech. J."), n(", 27(3), 379\u2013423.")]),
      p([n("Shumailov, I., et al. (2024). AI models collapse when trained on recursively generated data. "), i("Nature"), n(", 631, 755\u2013759.")]),
      p([n("Sivapalan, M., et al. (2012). Socio-hydrology: A new science of people and water. "), i("Hydrol. Process."), n(", 26(8), 1270\u20131276.")]),
      p([n("Touvron, H., et al. (2023). Llama 2: Open foundation and fine-tuned chat models. "), i("arXiv:2307.09288"), n(".")]),
      p([n("U.S. Bureau of Reclamation (2012). Colorado River Simulation System (CRSS). Washington, DC.")]),
      p([n("Wei, J., et al. (2022). Chain-of-thought prompting elicits reasoning in large language models. "), i("NeurIPS"), n(", 35, 24824\u201324837.")]),
      p([n("Yang, Y. C. E., et al. (2009). A decentralized optimization algorithm for multiagent system-based watershed management. "), i("Water Resour. Res."), n(", 45(8), W08430.")]),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("paper/SAGE_WRR_Paper.docx", buf);
  console.log("Created paper/SAGE_WRR_Paper.docx with full prose");
});

