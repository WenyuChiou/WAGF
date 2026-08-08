"""Check the ICLR main-text page limit on the rendered manuscript.

The ICLR 2027 limit is nine pages excluding references.  Static source checks
cannot see float placement, so this gate reads the compiled PDF and locates the
first bibliography page using both the rendered reference heading/entries and
the final-paper statements.  It fails closed when the PDF or a reference
marker is missing.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "paper" / "manuscript.pdf"
REPORT = ROOT / "checks" / "iclr_page_report.json"


def pdftotext_executable() -> str | None:
    """Find Poppler's text extractor, including the per-user MiKTeX install."""

    found = shutil.which("pdftotext")
    if found:
        return found
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = (
            Path(local_app_data)
            / "Programs"
            / "MiKTeX"
            / "miktex"
            / "bin"
            / "x64"
            / "pdftotext.exe"
        )
        if candidate.is_file():
            return str(candidate)
    return None


def page_texts(pdf: Path) -> tuple[list[str], str]:
    """Extract page text with Poppler; fall back to pypdf when unavailable.

    The ICLR style embeds fonts whose glyph map can make pypdf return numeric
    glyph identifiers.  Poppler preserves the rendered headings and lets this
    gate inspect the actual PDF rather than trusting source order.
    """

    executable = pdftotext_executable()
    if executable:
        page_count = len(PdfReader(str(pdf)).pages)
        texts: list[str] = []
        for page in range(1, page_count + 1):
            result = subprocess.run(
                [executable, "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
                capture_output=True,
                check=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            texts.append(result.stdout)
        return texts, "pdftotext"

    reader = PdfReader(str(pdf))
    return [(page.extract_text() or "") for page in reader.pages], "pypdf"


def compact_line(line: str) -> str:
    """Remove typography spacing from small-caps headings."""

    return "".join(character for character in line.lower() if character.isalpha())


def heading_pages(texts: list[str], headings: set[str]) -> list[int]:
    pages: list[int] = []
    for index, text in enumerate(texts, start=1):
        if any(compact_line(line) in headings for line in text.splitlines()):
            pages.append(index)
    return pages


def heading_locations(texts: list[str], heading: str) -> list[tuple[int, int]]:
    """Return one-based page/line locations for an exact rendered heading."""

    locations: list[tuple[int, int]] = []
    for page, text in enumerate(texts, start=1):
        for line_number, line in enumerate(text.splitlines(), start=1):
            if compact_line(line) == heading:
                locations.append((page, line_number))
    return locations


def first_rendered_marker(
    texts: list[str], marker: str
) -> tuple[int, int] | None:
    """Return the first page/line containing a data-display caption marker."""

    for page, text in enumerate(texts, start=1):
        for line_number, line in enumerate(text.splitlines(), start=1):
            if marker in line:
                return page, line_number
    return None


def page_has_material_before_heading(text: str, heading: str) -> bool:
    """Detect main text on a page whose bibliography starts below it.

    The ICLR limit excludes references, but a page can legally contain the
    final paragraph of the main text above the ``References`` heading.  Ignore
    only the running header, blank lines, and page-number-only lines.
    """

    for line in text.splitlines():
        compact = compact_line(line)
        stripped = line.strip()
        if compact == heading:
            return False
        if not stripped or stripped.isdigit():
            continue
        if stripped.lower().startswith("under review as a conference paper"):
            continue
        return True
    return False


def display_path(path: Path) -> str:
    """Return a portable path for the committed JSON report."""

    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--max-main-pages", type=int, default=9)
    args = parser.parse_args()

    errors: list[str] = []
    pdf = args.pdf.resolve()
    if not pdf.exists() or pdf.stat().st_size == 0:
        errors.append(f"missing rendered PDF: {pdf}")
        texts: list[str] = []
        extractor = None
    else:
        texts, extractor = page_texts(pdf)

    required_statements = {
        "reproducibilitystatement",
        "aiusestatement",
        "ethicsstatement",
    }
    statement_locations = {
        heading: heading_locations(texts, heading)
        for heading in required_statements
    }
    statement_pages = sorted(
        {
            page
            for locations in statement_locations.values()
            for page, _line in locations
        }
    )
    reference_pages = heading_pages(texts, {"references"})
    if not reference_pages:
        errors.append("could not locate a rendered bibliography page")
    missing_statements = sorted(
        heading for heading, locations in statement_locations.items() if not locations
    )
    if missing_statements:
        errors.append(
            "missing rendered ICLR statements: " + ", ".join(missing_statements)
        )

    first_reference_page = min(reference_pages) if reference_pages else None
    main_pages = None
    if first_reference_page:
        reference_text = texts[first_reference_page - 1]
        main_pages = first_reference_page - 1
        if page_has_material_before_heading(reference_text, "references"):
            main_pages += 1
    if main_pages is not None and main_pages > args.max_main_pages:
        errors.append(
            f"main text uses {main_pages} pages; limit is {args.max_main_pages}"
        )

    if first_reference_page:
        late_statements = sorted(
            heading
            for heading, locations in statement_locations.items()
            if any(page >= first_reference_page for page, _line in locations)
        )
        if late_statements:
            errors.append(
                "ICLR statements must precede references: "
                + ", ".join(late_statements)
            )

    figure4_marker = "Figure 4: Executed-action denominator gap"
    table3_marker = "Table 3: Secondary cross-testbed boundary check"
    figure4_location = first_rendered_marker(texts, figure4_marker)
    table3_location = first_rendered_marker(texts, table3_marker)
    if figure4_location is None or table3_location is None:
        errors.append("could not locate the rendered Figure 4/Table 3 captions")
    elif figure4_location >= table3_location:
        errors.append("rendered Figure 4 must precede the secondary Table 3 check")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "pdf": display_path(pdf),
        "extractor": extractor,
        "total_pages": len(texts),
        "main_pages": main_pages,
        "max_main_pages": args.max_main_pages,
        "statement_pages": statement_pages,
        "statement_locations": statement_locations,
        "reference_pages": reference_pages,
        "figure4_caption": figure4_location,
        "table3_caption": table3_location,
        "errors": errors,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
