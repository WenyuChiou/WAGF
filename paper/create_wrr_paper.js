const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, LevelFormat, PageBreak,
  Math: OoxmlMath, MathRun, MathFraction, MathSubScript, MathSuperScript,
  TabStopType, TabStopPosition
} = require("docx");

// AGU/WRR formatting constants
const FONT = "Times New Roman";
const BODY_SIZE = 24; // 12pt
const H1_SIZE = 28;   // 14pt
const H2_SIZE = 26;   // 13pt
const LINE_SPACING = 480; // double-spaced (240 = single)
const MARGIN = 1440; // 1 inch

// Helper: body paragraph
function bodyPara(text, opts = {}) {
  const runs = typeof text === "string"
    ? [new TextRun({ text, font: FONT, size: BODY_SIZE })]
    : text;
  return new Paragraph({
    spacing: { line: LINE_SPACING, after: 120 },
    alignment: opts.align || AlignmentType.LEFT,
    indent: opts.indent ? { firstLine: 360 } : undefined,
    children: runs,
  });
}

function boldRun(text) {
  return new TextRun({ text, font: FONT, size: BODY_SIZE, bold: true });
}
function italicRun(text) {
  return new TextRun({ text, font: FONT, size: BODY_SIZE, italics: true });
}
function normalRun(text) {
  return new TextRun({ text, font: FONT, size: BODY_SIZE });
}
function superRun(text) {
  return new TextRun({ text, font: FONT, size: BODY_SIZE, superScript: true });
}
function subRun(text) {
  return new TextRun({ text, font: FONT, size: BODY_SIZE, subScript: true });
}

// Helper: section heading
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 240, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT, size: H1_SIZE, bold: true })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT, size: H2_SIZE, bold: true })],
  });
}

// Helper: comment placeholder (italic gray)
function placeholder(text) {
  return new Paragraph({
    spacing: { line: LINE_SPACING, after: 60 },
    children: [new TextRun({ text: `[${text}]`, font: FONT, size: BODY_SIZE, italics: true, color: "888888" })],
  });
}

// ─── Table 1: Domain Mapping ───
const tBorder = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
const tBorders = { top: tBorder, bottom: tBorder, left: tBorder, right: tBorder };
const headerShading = { fill: "D9E2F3", type: ShadingType.CLEAR };

function tableCell(text, opts = {}) {
  return new TableCell({
    borders: tBorders,
    width: { size: opts.width || 3120, type: WidthType.DXA },
    shading: opts.header ? headerShading : undefined,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      spacing: { line: 276 },
      children: [new TextRun({ text, font: FONT, size: 20, bold: !!opts.header })],
    })],
  });
}

const table1 = new Table({
  columnWidths: [2200, 3580, 3580],
  rows: [
    new TableRow({ tableHeader: true, children: [
      tableCell("Component", { header: true, width: 2200 }),
      tableCell("Flood Adaptation", { header: true, width: 3580 }),
      tableCell("Irrigation Management", { header: true, width: 3580 }),
    ]}),
    new TableRow({ children: [
      tableCell("Skills", { width: 2200 }),
      tableCell("elevate, insure, relocate, both, do_nothing", { width: 3580 }),
      tableCell("increase, decrease, efficiency, acreage, maintain", { width: 3580 }),
    ]}),
    new TableRow({ children: [
      tableCell("Physical validators", { width: 2200 }),
      tableCell("already_elevated, already_insured", { width: 3580 }),
      tableCell("water_right_cap, already_efficient", { width: 3580 }),
    ]}),
    new TableRow({ children: [
      tableCell("Institutional validators", { width: 2200 }),
      tableCell("\u2014", { width: 3580 }),
      tableCell("compact_allocation, drought_severity", { width: 3580 }),
    ]}),
    new TableRow({ children: [
      tableCell("Memory engine", { width: 2200 }),
      tableCell("Flood trauma recall", { width: 3580 }),
      tableCell("Regret feedback", { width: 3580 }),
    ]}),
    new TableRow({ children: [
      tableCell("Appraisal framework", { width: 2200 }),
      tableCell("PMT (threat/coping)", { width: 3580 }),
      tableCell("Dual appraisal (WSA/ACA)", { width: 3580 }),
    ]}),
    new TableRow({ children: [
      tableCell("Agents", { width: 2200 }),
      tableCell("100 households \u00d7 10 yr", { width: 3580 }),
      tableCell("78 districts \u00d7 42 yr", { width: 3580 }),
    ]}),
  ],
});

// ─── Build Document ───
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT, size: BODY_SIZE } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: H1_SIZE, bold: true, font: FONT },
        paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: H2_SIZE, bold: true, font: FONT },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "key-points",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        pageNumbers: { start: 1 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "SAGE: Governance Middleware for LLM-Driven Water ABMs", font: FONT, size: 18, italics: true, color: "666666" })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Page ", font: FONT, size: 18 }),
            new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 }),
            new TextRun({ text: " of ", font: FONT, size: 18 }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 18 }),
          ],
        })],
      }),
    },
    children: [
      // ═══ TITLE ═══
      new Paragraph({
        spacing: { after: 120, line: LINE_SPACING },
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "SAGE: A Governance Middleware for LLM-Driven Agent-Based Models of Human\u2013Water Systems", font: FONT, size: 32, bold: true })],
      }),
      // Authors
      new Paragraph({
        spacing: { after: 60, line: LINE_SPACING },
        alignment: AlignmentType.CENTER,
        children: [
          normalRun("Wen-Yu Chen"),
          superRun("1"),
          normalRun(", Second Author"),
          superRun("1"),
        ],
      }),
      // Affiliation
      new Paragraph({
        spacing: { after: 240, line: LINE_SPACING },
        alignment: AlignmentType.CENTER,
        children: [
          superRun("1"),
          new TextRun({ text: "Department of Civil and Environmental Engineering, Lehigh University, Bethlehem, PA, USA", font: FONT, size: 22, italics: true }),
        ],
      }),
      // Corresponding author
      new Paragraph({
        spacing: { after: 360, line: LINE_SPACING },
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Corresponding author: Wen-Yu Chen (wec225@lehigh.edu)", font: FONT, size: 22 })],
      }),

      // ═══ KEY POINTS ═══
      h1("Key Points"),
      new Paragraph({
        numbering: { reference: "key-points", level: 0 },
        spacing: { line: LINE_SPACING },
        children: [normalRun("SAGE eliminates 33% hallucination rate in ungoverned LLM agents while preserving genuine behavioral diversity")],
      }),
      new Paragraph({
        numbering: { reference: "key-points", level: 0 },
        spacing: { line: LINE_SPACING },
        children: [normalRun("Effective Behavioral Entropy (EBE) metric separates true decision diversity from hallucination-inflated entropy")],
      }),
      new Paragraph({
        numbering: { reference: "key-points", level: 0 },
        spacing: { line: LINE_SPACING, after: 240 },
        children: [normalRun("Governance middleware transfers across domains: flood adaptation (100 agents, 10 yr) and irrigation (78 agents, 42 yr)")],
      }),

      // ═══ ABSTRACT ═══
      h1("Abstract"),
      bodyPara([
        normalRun("Large language models (LLMs) offer a promising path toward cognitively realistic agent-based models (ABMs) for water resources planning, but unconstrained LLM agents produce physically impossible decisions\u2014a phenomenon we term "),
        italicRun("behavioral hallucination"),
        normalRun(". We present SAGE (Structured Agent Governance Engine), an open-source middleware that enforces domain-specific physical and institutional constraints on LLM-driven agents while preserving emergent behavioral diversity. SAGE implements a three-pillar architecture: (1) a rule-based validator chain that rejects impossible actions, (2) a tiered cognitive memory system that encodes prior experience, and (3) a priority context builder that structures LLM prompts with domain knowledge. We introduce the Effective Behavioral Entropy (EBE) metric, defined as EBE = H"),
        subRun("norm"),
        normalRun(" \u00d7 (1 \u2212 R"),
        subRun("H"),
        normalRun("), which disentangles genuine decision diversity from hallucination-inflated entropy. In a flood adaptation case study (100 agents, 10 years, 7 LLM configurations), ungoverned agents exhibit a 33% hallucination rate; SAGE-governed agents reduce this to <2% while maintaining EBE 32% higher. We demonstrate domain transferability through a Colorado River irrigation case study (78 districts, 42 years). The framework, metrics, and experiment code are available at [GitHub URL]."),
      ]),

      // ═══ PLAIN LANGUAGE SUMMARY ═══
      h1("Plain Language Summary"),
      bodyPara("Artificial intelligence language models can power virtual agents that make human-like decisions in water management simulations. However, without oversight, these agents make impossible choices\u2014like buying flood insurance they already own or elevating a home that is already raised. We developed SAGE, a software layer that checks each agent\u2019s decision against physical and institutional rules before it takes effect, while still allowing agents to make diverse, realistic choices. We show that unchecked agents make impossible decisions 33% of the time, inflating the apparent diversity of their behavior. Our governance middleware eliminates these errors while preserving genuine decision-making variety. We demonstrate the approach in two water domains: household flood adaptation and Colorado River irrigation management."),

      new Paragraph({ children: [new PageBreak()] }),

      // ═══ SECTION 1: INTRODUCTION ═══
      h1("1. Introduction"),
      placeholder("~800 words. Para 1: LLMs in ABMs \u2014 promise (Park et al., 2023; Gao et al., 2024; Boiko et al., 2023). Para 2: Hallucination problem (Ji et al., 2023; Shumailov et al., 2024). Para 3: Gap + 3 contributions."),

      // ═══ SECTION 2: SAGE ARCHITECTURE ═══
      h1("2. SAGE Architecture"),
      h2("2.1 Three-Pillar Design"),
      placeholder("Pillar 1: Governance (rule-based validator chain). Pillar 2: Cognitive Memory. Pillar 3: Priority Context Builder. Reference Figure 1."),
      h2("2.2 Skill Registry and Validator Chain"),
      placeholder("Skills: named actions with pre/post conditions. SkillBrokerEngine pipeline. Retry logic. Audit trail. Reference Figure 2."),
      h2("2.3 Domain Instantiation"),
      placeholder("Reference Table 1 below."),

      // Table 1
      new Paragraph({
        spacing: { before: 240, after: 60, line: LINE_SPACING },
        alignment: AlignmentType.CENTER,
        children: [boldRun("Table 1. "), normalRun("SAGE instantiation for two water resource domains.")],
      }),
      table1,
      new Paragraph({ spacing: { after: 240 }, children: [] }),

      // ═══ SECTION 3: METRICS ═══
      h1("3. Metrics"),
      // Hallucination Rate
      bodyPara([
        normalRun("We define "),
        italicRun("behavioral hallucination"),
        normalRun(" as an action a"),
        subRun("t"),
        normalRun(" proposed by an LLM agent that violates physical or institutional constraints given the agent\u2019s state s"),
        subRun("t\u22121"),
        normalRun(" at the previous timestep. Formally, let A(s"),
        subRun("t\u22121"),
        normalRun(") denote the set of feasible actions given state s"),
        subRun("t\u22121"),
        normalRun(". An action is a behavioral hallucination if a"),
        subRun("t"),
        normalRun(" \u2209 A(s"),
        subRun("t\u22121"),
        normalRun("). This differs from textual hallucination (Ji et al., 2023) in that the output may be linguistically coherent but physically impossible. The hallucination rate is:"),
      ]),
      // Eq 1
      new Paragraph({
        spacing: { line: LINE_SPACING, before: 120, after: 120 },
        alignment: AlignmentType.CENTER,
        children: [
          normalRun("R"),
          subRun("H"),
          normalRun(" = n"),
          subRun("hall"),
          normalRun(" / n"),
          subRun("total"),
          normalRun("          (1)"),
        ],
      }),
      // EBE definition
      bodyPara([
        normalRun("The Effective Behavioral Entropy (EBE) combines normalized Shannon entropy (Shannon, 1948) with the hallucination penalty:"),
      ]),
      // Eq 2
      new Paragraph({
        spacing: { line: LINE_SPACING, before: 120, after: 120 },
        alignment: AlignmentType.CENTER,
        children: [
          normalRun("EBE = H"),
          subRun("norm"),
          normalRun(" \u00d7 (1 \u2212 R"),
          subRun("H"),
          normalRun(") = [H / log"),
          subRun("2"),
          normalRun("(k)] \u00d7 [1 \u2212 n"),
          subRun("hall"),
          normalRun(" / n"),
          subRun("total"),
          normalRun("]          (2)"),
        ],
      }),
      bodyPara([
        normalRun("where k is the number of available actions and H = \u2212\u03A3 p"),
        subRun("i"),
        normalRun(" log"),
        subRun("2"),
        normalRun(" p"),
        subRun("i"),
        normalRun(" is the Shannon entropy of the observed action distribution. EBE ranges from 0 (no diversity or entirely hallucinated) to 1 (maximum diversity with zero hallucination). When computing corrected entropy, hallucinated actions are replaced with the agent\u2019s default action (DoNothing for flood, maintain_demand for irrigation)."),
      ]),

      new Paragraph({ children: [new PageBreak()] }),

      // ═══ SECTION 4: FLOOD CASE STUDY ═══
      h1("4. Case Study 1: Flood Adaptation"),
      h2("4.1 Experimental Design"),
      placeholder("100 household agents, 10-year simulation, flood events at years 3, 4, 9. Three groups: A (raw LLM), B (SAGE + window memory), C (SAGE + human-centric memory). Primary model: Gemma 3 4B. PMT appraisal framework."),
      h2("4.2 Hallucination Detection and Correction"),
      placeholder("Method: compare decision against prior-year state. Group A: 33% hallucination rate. Groups B/C: <2%. Reference Equations 1\u20132."),
      h2("4.3 Results"),
      placeholder("Reference Figure 3. Key findings: Group A EBE=0.41 (hallucination inflates), Group C EBE=0.54 (32% higher). Cumulative relocation: A=1%, B=33%, C=43%."),

      // Figure 3 placeholder
      new Paragraph({
        spacing: { before: 240, after: 60, line: LINE_SPACING },
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "[FIGURE 3: Flood Results \u2014 Hallucination panel + cumulative relocation]", font: FONT, size: BODY_SIZE, italics: true, color: "CC0000" })],
      }),

      // ═══ SECTION 5: IRRIGATION CASE STUDY ═══
      h1("5. Case Study 2: Colorado River Irrigation"),
      h2("5.1 Setup"),
      placeholder("78 irrigation districts from CRSS database. 42-year horizon (2019\u20132060). Hung & Yang (2021) as validation reference. Dual-appraisal: WSA (Water Scarcity Assessment), ACA (Adaptive Capacity Assessment)."),
      h2("5.2 Results"),
      placeholder("Reference Figure 4. Governance maintains physically feasible demand trajectories. Institutional constraints prevent over-extraction."),

      // Figure 4 placeholder
      new Paragraph({
        spacing: { before: 240, after: 60, line: LINE_SPACING },
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "[FIGURE 4: Irrigation Results \u2014 Demand trajectories by cluster]", font: FONT, size: BODY_SIZE, italics: true, color: "CC0000" })],
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ═══ SECTION 6: DISCUSSION ═══
      h1("6. Discussion"),
      placeholder("~500 words. Para 1: EBE as diagnostic (Jost, 2006). Para 2: Cross-model robustness (7 configurations). Para 3: Limitations (single-run, temperature, 78 agents, ~5% latency overhead)."),

      // ═══ SECTION 7: CONCLUSIONS ═══
      h1("7. Conclusions"),
      placeholder("~300 words. 3 contributions: SAGE architecture, EBE metric, two-domain validation. Future: multi-agent interaction governance, dynamic rule learning."),

      // ═══ DATA AVAILABILITY ═══
      h1("Data Availability Statement"),
      bodyPara("Simulation logs, agent configurations, and analysis scripts are archived at [Zenodo DOI] and available at [GitHub URL] under the MIT License. The CRSS precipitation projections are from the U.S. Bureau of Reclamation (USBR, 2012). All raw LLM traces (JSONL format) and governance audit logs are included in the archive to support independent verification."),

      // ═══ COI ═══
      h1("Conflict of Interest"),
      bodyPara("The authors declare no conflicts of interest relevant to this study."),

      // ═══ CREDIT ═══
      h1("Author Contributions"),
      bodyPara([
        boldRun("Wen-Yu Chen: "),
        normalRun("Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Writing \u2013 Original Draft, Visualization. "),
        boldRun("[Second Author]: "),
        normalRun("Supervision, Writing \u2013 Review & Editing, Funding acquisition."),
      ]),

      // ═══ ACKNOWLEDGMENTS ═══
      h1("Acknowledgments"),
      bodyPara("This work was supported by [funding source]."),

      new Paragraph({ children: [new PageBreak()] }),

      // ═══ REFERENCES ═══
      h1("References"),
      placeholder("32 references from Zotero library. Export in AGU format."),
    ],
  }],
});

// Save
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("paper/SAGE_WRR_Paper.docx", buffer);
  console.log("Created paper/SAGE_WRR_Paper.docx");
});
