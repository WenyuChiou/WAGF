/**
 * Create SI Tables for SAGE WRR Paper v5
 * Multi-model comparison tables for flood ABM metrics
 */

const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, BorderStyle, WidthType, ShadingType, VerticalAlign,
        HeadingLevel, PageBreak } = require('docx');
const fs = require('fs');
const path = require('path');

// Table styling
const tableBorder = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
const cellBorders = { top: tableBorder, bottom: tableBorder, left: tableBorder, right: tableBorder };
const headerShading = { fill: "D5E8F0", type: ShadingType.CLEAR };

// Multi-model data from WRR_technical_notes_flood_v2.md
const multiModelData = [
  { model: "gemma3:4b", group: "A", n: 998, retry: "-", rh: "20.84", hnorm: "0.664", ebe: "0.526", ff: "14.14" },
  { model: "gemma3:4b", group: "B", n: 855, retry: "245", rh: "0.58", hnorm: "0.790", ebe: "0.785", ff: "46.36" },
  { model: "gemma3:4b", group: "C", n: 857, retry: "336", rh: "2.80", hnorm: "0.804", ebe: "0.782", ff: "49.01" },
  { model: "gemma3:12b", group: "A", n: 999, retry: "-", rh: "9.71", hnorm: "0.471", ebe: "0.426", ff: "17.58" },
  { model: "gemma3:12b", group: "B", n: 883, retry: "4", rh: "0.00", hnorm: "0.478", ebe: "0.478", ff: "32.69" },
  { model: "gemma3:12b", group: "C", n: 962, retry: "0", rh: "0.00", hnorm: "0.473", ebe: "0.473", ff: "33.41" },
  { model: "gemma3:27b", group: "A", n: 1000, retry: "-", rh: "8.70", hnorm: "0.696", ebe: "0.635", ff: "32.67" },
  { model: "gemma3:27b", group: "B", n: 984, retry: "2", rh: "0.00", hnorm: "0.629", ebe: "0.629", ff: "46.15" },
  { model: "gemma3:27b", group: "C", n: 997, retry: "8", rh: "0.00", hnorm: "0.685", ebe: "0.685", ff: "52.29" },
  { model: "ministral3:3b", group: "A", n: 991, retry: "-", rh: "13.82", hnorm: "0.436", ebe: "0.375", ff: "10.10" },
  { model: "ministral3:3b", group: "B", n: 688, retry: "217", rh: "1.45", hnorm: "0.755", ebe: "0.744", ff: "54.53" },
  { model: "ministral3:3b", group: "C", n: 764, retry: "202", rh: "0.13", hnorm: "0.640", ebe: "0.639", ff: "42.77" },
  { model: "ministral3:8b", group: "A", n: 984, retry: "-", rh: "11.99", hnorm: "0.753", ebe: "0.662", ff: "18.55" },
  { model: "ministral3:8b", group: "B", n: 948, retry: "167", rh: "0.00", hnorm: "0.627", ebe: "0.627", ff: "43.63" },
  { model: "ministral3:8b", group: "C", n: 816, retry: "100", rh: "0.00", hnorm: "0.629", ebe: "0.629", ff: "40.34" },
  { model: "ministral3:14b", group: "A", n: 973, retry: "-", rh: "11.61", hnorm: "0.481", ebe: "0.425", ff: "16.95" },
  { model: "ministral3:14b", group: "B", n: 889, retry: "97", rh: "0.00", hnorm: "0.695", ebe: "0.695", ff: "55.01" },
  { model: "ministral3:14b", group: "C", n: 927, retry: "148", rh: "0.00", hnorm: "0.713", ebe: "0.713", ff: "51.51" },
];

// R_H by model size summary
const modelSizeSummary = [
  { family: "Gemma3", size: "4B", rh_a: "20.84%", rh_b: "0.58%", rh_c: "2.80%", reduction: "97-99%" },
  { family: "Gemma3", size: "12B", rh_a: "9.71%", rh_b: "0.00%", rh_c: "0.00%", reduction: "100%" },
  { family: "Gemma3", size: "27B", rh_a: "8.70%", rh_b: "0.00%", rh_c: "0.00%", reduction: "100%" },
  { family: "Ministral3", size: "3B", rh_a: "13.82%", rh_b: "1.45%", rh_c: "0.13%", reduction: "90-99%" },
  { family: "Ministral3", size: "8B", rh_a: "11.99%", rh_b: "0.00%", rh_c: "0.00%", reduction: "100%" },
  { family: "Ministral3", size: "14B", rh_a: "11.61%", rh_b: "0.00%", rh_c: "0.00%", reduction: "100%" },
];

// Helper: Create header cell
function headerCell(text, width) {
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    shading: headerShading,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold: true, size: 18, font: "Times New Roman" })]
    })]
  });
}

// Helper: Create data cell
function dataCell(text, width, bold = false) {
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold, size: 18, font: "Times New Roman" })]
    })]
  });
}

// Create Table S2: Multi-Model Comparison
function createTableS2() {
  const colWidths = [1300, 700, 600, 700, 900, 900, 900, 900]; // 8 columns

  const headerRow = new TableRow({
    tableHeader: true,
    children: [
      headerCell("Model", colWidths[0]),
      headerCell("Group", colWidths[1]),
      headerCell("N", colWidths[2]),
      headerCell("Retry", colWidths[3]),
      headerCell("R_H(%)", colWidths[4]),
      headerCell("H_norm", colWidths[5]),
      headerCell("EBE", colWidths[6]),
      headerCell("FF(%)", colWidths[7]),
    ]
  });

  const dataRows = multiModelData.map(row => {
    const isGroupA = row.group === "A";
    return new TableRow({
      children: [
        dataCell(row.model, colWidths[0], isGroupA),
        dataCell(`Group_${row.group}`, colWidths[1]),
        dataCell(row.n.toString(), colWidths[2]),
        dataCell(row.retry, colWidths[3]),
        dataCell(row.rh, colWidths[4], isGroupA),
        dataCell(row.hnorm, colWidths[5]),
        dataCell(row.ebe, colWidths[6]),
        dataCell(row.ff, colWidths[7]),
      ]
    });
  });

  return new Table({
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows]
  });
}

// Create Table S3: R_H by Model Size
function createTableS3() {
  const colWidths = [1500, 800, 1200, 1200, 1200, 1200]; // 6 columns

  const headerRow = new TableRow({
    tableHeader: true,
    children: [
      headerCell("Model Family", colWidths[0]),
      headerCell("Size", colWidths[1]),
      headerCell("Group A R_H", colWidths[2]),
      headerCell("Group B R_H", colWidths[3]),
      headerCell("Group C R_H", colWidths[4]),
      headerCell("Reduction", colWidths[5]),
    ]
  });

  const dataRows = modelSizeSummary.map(row => new TableRow({
    children: [
      dataCell(row.family, colWidths[0]),
      dataCell(row.size, colWidths[1]),
      dataCell(row.rh_a, colWidths[2], true),
      dataCell(row.rh_b, colWidths[3]),
      dataCell(row.rh_c, colWidths[4]),
      dataCell(row.reduction, colWidths[5]),
    ]
  }));

  return new Table({
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows]
  });
}

// Create the document
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Times New Roman", size: 24 } }
    }
  },
  sections: [{
    children: [
      // Title
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [new TextRun({ text: "Supporting Information - Additional Tables", bold: true, size: 28 })]
      }),

      // Table S2
      new Paragraph({
        spacing: { before: 400, after: 200 },
        children: [
          new TextRun({ text: "Table S2. ", bold: true, size: 20 }),
          new TextRun({ text: "Multi-model comparison of flood adaptation metrics across three governance configurations (100 agents, 10 years). R_H = hallucination rate; H_norm = normalized entropy; EBE = effective behavioral entropy; FF = final flood-safety adoption rate.", italics: true, size: 20 })
        ]
      }),
      createTableS2(),

      // Page break
      new Paragraph({ children: [new PageBreak()] }),

      // Table S3
      new Paragraph({
        spacing: { before: 400, after: 200 },
        children: [
          new TextRun({ text: "Table S3. ", bold: true, size: 20 }),
          new TextRun({ text: "R_H by model size. Larger models show lower ungoverned hallucination rates. Governance reduces R_H to near-zero for all model sizes.", italics: true, size: 20 })
        ]
      }),
      createTableS3(),

      // Key findings
      new Paragraph({
        spacing: { before: 400, after: 200 },
        children: [new TextRun({ text: "Key Findings:", bold: true, size: 24 })]
      }),
      new Paragraph({
        spacing: { after: 100 },
        children: [new TextRun({ text: "1. Larger models hallucinate less: R_H decreases with model size (4B: 20.84% → 27B: 8.70%)", size: 22 })]
      }),
      new Paragraph({
        spacing: { after: 100 },
        children: [new TextRun({ text: "2. Governance is highly effective: Even for smallest models, R_H drops to <3%", size: 22 })]
      }),
      new Paragraph({
        spacing: { after: 100 },
        children: [new TextRun({ text: "3. 12B+ models achieve near-zero R_H with governance", size: 22 })]
      }),
    ]
  }]
});

// Save the document
Packer.toBuffer(doc).then(buffer => {
  const outPath = path.resolve(__dirname, '..', '..', 'SAGE_WRR_SI_Tables_v5.docx');
  fs.writeFileSync(outPath, buffer);
  console.log(`SI tables created: ${outPath}`);
});
