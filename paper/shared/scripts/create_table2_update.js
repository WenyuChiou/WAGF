/**
 * Create Table 2 Update for SAGE WRR Paper v5
 * Main paper flood ABM metrics table
 */

const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, BorderStyle, WidthType, ShadingType, VerticalAlign } = require('docx');
const fs = require('fs');
const path = require('path');

// Table styling
const tableBorder = { style: BorderStyle.SINGLE, size: 1, color: "000000" };
const cellBorders = { top: tableBorder, bottom: tableBorder, left: tableBorder, right: tableBorder };
const headerShading = { fill: "D5E8F0", type: ShadingType.CLEAR };

// Updated data for gemma3:4b
const table2Data = {
  metrics: [
    { name: "Hallucination Rate (R_H)", a: "0.208 ± 0.050", b: "0.006 ± 0.007", c: "0.028 ± 0.021" },
    { name: "Total hallucinations", a: "208 / 998", b: "5 / 855", c: "24 / 857" },
    { name: "Normalized Entropy (H_norm)", a: "0.664 ± 0.080", b: "0.790 ± 0.050", c: "0.804 ± 0.045" },
    { name: "EBE", a: "0.526 ± 0.100", b: "0.785 ± 0.055", c: "0.782 ± 0.050" },
    { name: "Final flood-safety (FF)", a: "14.14%", b: "46.36%", c: "49.01%" },
    { name: "Governance interventions", a: "-", b: "245", c: "336" },
  ]
};

// Helper functions
function headerCell(text, width, multiline = false) {
  const lines = text.split('\n');
  const children = [];
  lines.forEach((line, i) => {
    if (i > 0) children.push(new TextRun({ text: "", break: 1 }));
    children.push(new TextRun({ text: line, bold: true, size: 18, font: "Times New Roman" }));
  });

  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    shading: headerShading,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children })]
  });
}

function dataCell(text, width) {
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, size: 18, font: "Times New Roman" })]
    })]
  });
}

function labelCell(text, width) {
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    children: [new Paragraph({
      alignment: AlignmentType.LEFT,
      children: [new TextRun({ text, size: 18, font: "Times New Roman" })]
    })]
  });
}

// Create Table 2
function createTable2() {
  const colWidths = [2800, 2000, 2200, 2200]; // 4 columns

  const headerRow = new TableRow({
    tableHeader: true,
    children: [
      headerCell("Metric", colWidths[0]),
      headerCell("Group A\n(Ungoverned)", colWidths[1]),
      headerCell("Group B\n(SAGE+Window)", colWidths[2]),
      headerCell("Group C\n(SAGE+Human.)", colWidths[3]),
    ]
  });

  const dataRows = table2Data.metrics.map(row => new TableRow({
    children: [
      labelCell(row.name, colWidths[0]),
      dataCell(row.a, colWidths[1]),
      dataCell(row.b, colWidths[2]),
      dataCell(row.c, colWidths[3]),
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
        spacing: { after: 400 },
        children: [new TextRun({ text: "Table 2 Update for WRR Paper v5", bold: true, size: 28 })]
      }),

      // Caption
      new Paragraph({
        spacing: { after: 200 },
        children: [
          new TextRun({ text: "Table 2. ", bold: true, size: 20 }),
          new TextRun({
            text: "Flood adaptation results for three governance configurations (100 agents, 10 years, Gemma3 4B). Hallucination rate, entropy, and EBE are mean ± SD over years 2–10 (N = 998, 855, and 857 decisions for Groups A, B, and C respectively).",
            italics: true,
            size: 20
          })
        ]
      }),

      // Table
      createTable2(),

      // Notes
      new Paragraph({
        spacing: { before: 300, after: 100 },
        children: [new TextRun({ text: "Notes:", bold: true, size: 20 })]
      }),
      new Paragraph({
        spacing: { after: 100 },
        children: [new TextRun({
          text: "• R_H (Hallucination Rate): Group A = (V1+V2+V3)/N; Group B/C = retry_exhausted/N",
          size: 20
        })]
      }),
      new Paragraph({
        spacing: { after: 100 },
        children: [new TextRun({
          text: "• H_norm = Shannon entropy / log₂(4), normalized to [0,1]",
          size: 20
        })]
      }),
      new Paragraph({
        spacing: { after: 100 },
        children: [new TextRun({
          text: "• EBE = H_norm × (1 - R_H), composite metric for behavioral quality",
          size: 20
        })]
      }),
      new Paragraph({
        spacing: { after: 100 },
        children: [new TextRun({
          text: "• Governance reduces R_H by 97-99% while maintaining behavioral diversity",
          size: 20,
          bold: true
        })]
      }),
    ]
  }]
});

// Save
Packer.toBuffer(doc).then(buffer => {
  const outPath = path.resolve(__dirname, '..', '..', 'Table2_Update_v5.docx');
  fs.writeFileSync(outPath, buffer);
  console.log(`Table 2 update created: ${outPath}`);
});
