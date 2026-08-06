"""Static preflight for the anonymous ICLR manuscript.

This is intentionally not a substitute for the official TeX build.  It
checks the parts that can be validated without a TeX engine: citation
coverage, referenced figures, required sections, placeholder text, Unicode
surprises, and the generated figure file formats.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
MANUSCRIPT = PAPER / "manuscript.tex"
BIB = PAPER / "references.bib"
FIGURES = ROOT / "figures" / "active"
REPORT = ROOT / "checks" / "manuscript_static_report.json"


def find_tex_engine() -> str | None:
    """Find a TeX executable on PATH or in common per-user MiKTeX locations."""

    for executable in ("pdflatex", "xelatex", "lualatex", "tectonic"):
        found = shutil.which(executable)
        if found:
            return found

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        miktex_bin = (
            Path(local_app_data)
            / "Programs"
            / "MiKTeX"
            / "miktex"
            / "bin"
            / "x64"
        )
        for executable in ("pdflatex.exe", "xelatex.exe", "lualatex.exe"):
            candidate = miktex_bin / executable
            if candidate.is_file():
                return str(candidate)
    return None


def main() -> int:
    tex = MANUSCRIPT.read_text(encoding="utf-8")
    bib = BIB.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    cited: set[str] = set()
    for match in re.finditer(r"\\cite[a-zA-Z]*\{([^}]+)\}", tex):
        cited.update(key.strip() for key in match.group(1).split(","))
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    missing_citations = sorted(cited - bib_keys)
    unused_bib = sorted(bib_keys - cited)
    if missing_citations:
        errors.append(f"missing bibliography keys: {missing_citations}")
    if unused_bib:
        warnings.append(f"unused bibliography keys: {unused_bib}")

    figure_paths = re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", tex)
    missing_figures = []
    for relative in figure_paths:
        path = (PAPER / relative).resolve()
        if not path.exists() or path.stat().st_size == 0:
            missing_figures.append(relative)
    if missing_figures:
        errors.append(f"missing figure files: {missing_figures}")

    required_sections = [
        "\\section{Introduction}",
        "\\section{Evaluation Setting}",
        "\\section{The Denominator Moves}",
        "\\section{World-State Composition as a Descriptive Mechanism}",
        "\\section{Different Denominators Answer Different Questions}",
        "\\section{Reporting Protocol and Limitations}",
        "\\section{Conclusion}",
        "\\subsection*{AI Use Statement}",
        "\\subsection*{Ethics Statement}",
        "\\subsection*{Reproducibility Statement}",
    ]
    missing_sections = [section for section in required_sections if section not in tex]
    if missing_sections:
        errors.append(f"missing required sections: {missing_sections}")

    placeholders = re.findall(r"TODO|TBD|FIXME|PLACEHOLDER|XXXX|\?\?", tex, flags=re.IGNORECASE)
    if placeholders:
        errors.append(f"placeholder tokens found: {placeholders}")

    non_ascii = sorted({char for char in tex + bib if ord(char) > 127})
    if non_ascii:
        errors.append(f"non-ASCII characters require review: {non_ascii}")

    begin_envs = re.findall(r"\\begin\{([^}]+)\}", tex)
    end_envs = re.findall(r"\\end\{([^}]+)\}", tex)
    if sorted(begin_envs) != sorted(end_envs):
        errors.append("LaTeX begin/end environment multiset is unbalanced")

    if r"\iclrfinalcopy" in tex:
        errors.append("final-copy switch is enabled in the anonymous draft")
    if r"\author{}" not in tex:
        warnings.append("author block is not empty; double-blind metadata needs review")
    bibliography_position = tex.find(r"\bibliography{")
    statement_position = tex.find(r"\subsection*{AI Use Statement}")
    if bibliography_position >= 0 and statement_position >= bibliography_position:
        errors.append("ICLR statements should precede the bibliography")

    figure_checks = {}
    for figure_name in [
        "fig1_rule_layers.pdf",
        "fig2_mechanism.pdf",
        "fig3_consequence.pdf",
    ]:
        path = FIGURES / figure_name
        if not path.exists():
            errors.append(f"missing expected figure: {figure_name}")
            continue
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            figure_checks[figure_name] = {"pages": len(reader.pages), "bytes": path.stat().st_size}
            if len(reader.pages) != 1:
                errors.append(f"{figure_name}: expected one page, got {len(reader.pages)}")

    png = FIGURES / "figure1_concept.png"
    if png.exists():
        with Image.open(png) as image:
            figure_checks["figure1_concept.png"] = {
                "size": list(image.size),
                "mode": image.mode,
            }
            if image.mode not in {"RGB", "RGBA"}:
                errors.append(f"figure1_concept.png has unexpected mode {image.mode}")
    else:
        errors.append("missing expected figure: figure1_concept.png")

    tex_words = re.sub(r"\\[a-zA-Z]+", " ", tex)
    tex_words = re.sub(r"[^A-Za-z0-9%+.-]+", " ", tex_words)
    word_count = len([word for word in tex_words.split() if word])
    tex_engine = find_tex_engine()
    result = {
        "status": "PASS" if not errors else "FAIL",
        "build_status": (
            f"TEX_ENGINE_AVAILABLE:{tex_engine}"
            if tex_engine
            else "BLOCKED_NO_TEX_ENGINE"
        ),
        "manuscript": str(MANUSCRIPT.relative_to(ROOT)).replace("\\", "/"),
        "cited_keys": sorted(cited),
        "bibliography_keys": sorted(bib_keys),
        "figure_paths": figure_paths,
        "figure_checks": figure_checks,
        "approximate_word_count": word_count,
        "warnings": warnings,
        "errors": errors,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
