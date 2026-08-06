#!/usr/bin/env python3
"""submission_gate.py -- one command that answers "is this actually ready to submit".

    python SUBMISSION_2026/TAE/paper/submission_gate.py

Every answer below is MEASURED off disk. Nothing is read out of BACKLOG.md,
STATUS.md, SUBMISSION_READINESS.md or any other hand-written tracking document,
because prose goes stale silently and this file exists because it did: on
2026-08-03 four separate claims in those documents were false at the moment they
were read -- a page-limit PASS resting on evidence that no longer existed, a
note claiming page slack that had already been spent, an artifact statement
promising three figures when there are four, and a STATUS.md stale within hours
of being written.

So: a PASS here means a check ran and looked at something. Each gate prints what
it looked at, so a PASS is auditable rather than trusted. Where this file and a
tracking document disagree, THIS FILE IS NOT AUTOMATICALLY RIGHT EITHER -- go
read the artefact it names. It is only harder to fool, because it re-derives the
answer every run.

THE SEVEN GATES, in the order they run (which is dependency order, not the order
they are numbered in anyone's checklist):

  evidence   run_all.py, the 15-script pipeline that regenerates every number,
             table and figure from the raw decision corpus. Runs FIRST because
             it rewrites figures/, and a page count taken before it would be a
             count of the previous figures.
  figures    every figure manuscript.md references exists, has the .png sibling
             the .docx branch needs, and is not older than the sources it was
             generated from. Runs after `evidence` so it sees the current files.
  build      make_bibliography --check, substitute.py, build.py (whose
             _escape_tex is the non-ASCII guard), then pdflatex twice; LaTeX
             error count and overfull-box count read out of manuscript.log.
  pages      the BODY ends within 8 pages. Not a page count: references and
             appendices are excluded from the limit, so the gate finds the page
             the References heading is actually set on and confirms nothing but
             references follows it.
  fonts      every embedded font, by type, resolved through Type0 wrappers to
             the descendant that actually carries the glyphs.
  anonymity  the PDF's text AND its metadata, plus every figure PDF and PNG,
             carry no author name, email, institution, account name or local
             path. Cross-checked against ANONYMITY.md, but measured, not trusted.
  citations  every .bib entry cited, every [n] backed by an entry, the counts
             equal, and every entry's note field recording a fetched
             verification page (this project's own standing rule after the
             2026-05-20 fabrication incident).

EXIT CODE
    0   every gate PASSED. Nothing was skipped.
    1   at least one gate FAILED.
    2   nothing failed, but a gate was SKIPPED or could not be evaluated, so
        readiness is UNVERIFIED. A skip never counts as a pass.

WHY THE FRESHNESS RULE IS "NOT OLDER THAN ITS SOURCES"
A figure PDF whose mtime predates the script that draws it means the paper
embeds a picture no current code produces -- the classic silent staleness, and
the same failure mode as a stale prose claim. So the rule is:

    mtime(figures/X.pdf) >= mtime(evidence/X.py)
    and, if evidence/X.py imports the shared data module,
    mtime(figures/X.pdf) >= mtime(evidence/_data.py)
    and mtime(manuscript.pdf) >= mtime(figures/X.pdf)

The middle clause matters because a figure script usually contains no numbers;
_data.py is where the corpus is read and the guards live, so editing _data.py
can change every figure without touching a single figure script. The last clause
is the same rule one level up: a manuscript PDF older than a figure it embeds is
showing the previous picture.

Equal mtimes pass. Filesystem timestamp resolution is coarser than a fast
rebuild, and "regenerated in the same second" is not staleness.

NO PERSONAL DATA IS EVER PRINTED. The anonymity gate needs to search for an
author name, an email and an account name, so it derives them at runtime from
build.py's CAMERA_READY constants and from this machine's own home directory,
and reports any hit BY LABEL and LOCATION only -- "author-email (build.py) found
in figures/fig2_mechanism.pdf, uncompressed object 12" -- never by value. The
same rule applies to anything read out of the decision corpus: this file reads
no respondent data at all.

Standard library only. Python 3. Runs on Windows; all output is ASCII, because a
console on a legacy codepage that drops a glyph must never look like a failing
check.

OPTIONS
    --no-build        do not rebuild; check the manuscript.pdf already on disk
                      (the report says which, and how old it is)
    --skip-evidence   skip run_all.py (~60 s). The gate is reported SKIPPED and
                      the exit code becomes 2, never 0.
    --strict-truetype reject embedded TrueType outlines in addition to the
                      venue-blocking Type 3 class. By default, embedded
                      TrueType is accepted because the official template
                      permits Type 1 or embedded TrueType.
    --allow-truetype  backward-compatible alias for the default policy; Type 3
                      remains a hard failure.
    --quiet           table and verdict only; suppress the per-gate detail.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../SUBMISSION_2026/TAE/paper
TAE = HERE.parent                                # .../SUBMISSION_2026/TAE
FIGURES_DIR = TAE / "figures"
EVIDENCE_DIR = TAE / "evidence"

MANUSCRIPT_MD = HERE / "manuscript.md"
SUBSTITUTED_MD = HERE / "manuscript.substituted.md"
MANUSCRIPT_TEX = HERE / "manuscript.tex"
MANUSCRIPT_PDF = HERE / "manuscript.pdf"
MANUSCRIPT_LOG = HERE / "manuscript.log"
REFERENCES_BIB = HERE / "references.bib"
ANONYMITY_MD = HERE / "ANONYMITY.md"
RUN_ALL = EVIDENCE_DIR / "run_all.py"
DATA_MODULE = EVIDENCE_DIR / "_data.py"

BODY_PAGE_LIMIT = 8          # NeurIPS 2026 TAE workshop: 8 pages excl. refs + appendices
VENUE_CFP_URL = "https://tai-eval.github.io/cfp/"
VENUE_WORKSHOP_TITLE = "TAE (Trust-AI-Eval): Can We Trust AI Evaluation?"
PDFLATEX_CANDIDATES = [
    r"C:\Users\%s\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe" % os.environ.get("USERNAME", ""),
    r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe",
]

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


# =============================================================================
# Gate result
# =============================================================================

class Gate:
    """One check. `headline` is the one line that goes in the table; `evidence`
    is what it looked at; `remedy` is what to do about it, and is the reason a
    FAIL here is worth more than a red light."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.status = PASS
        self.headline = ""
        self.evidence: list[str] = []
        self.remedy: list[str] = []

    def fail(self, remedy: str) -> None:
        self.status = FAIL
        self.remedy.append(remedy)

    def skip(self, why: str) -> None:
        self.status = SKIP
        self.remedy.append(why)

    def note(self, line: str) -> None:
        self.evidence.append(line)


# =============================================================================
# A small read-only PDF reader. Enough for a gate, and no more.
#
# pdftex writes uncompressed cross-reference tables and no object streams at
# this configuration, so every indirect object is findable in the raw bytes.
# If that ever changes the reader says so rather than reporting zero pages and
# zero fonts as a clean bill of health -- see Pdf.trouble.
# =============================================================================

# The leading lookbehind is load-bearing: without it "170 0 obj" also registers
# an object 70, and the later, wrong body silently replaces the real one.
_OBJ_RE = re.compile(rb"(?<![0-9])(\d+)\s+0\s+obj\b")
_STR_RE = re.compile(rb"\((?:[^()\\]|\\.)*\)", re.S)
_TEXT_TOKENS = re.compile(
    rb"BT\b"
    rb"|(?P<tm>[-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+ (?P<tx>-?[\d.]+) (?P<ty>-?[\d.]+) Tm)"
    rb"|(?P<td>(?P<dx>-?[\d.]+) (?P<dy>-?[\d.]+) T[dD])"
    rb"|(?P<tstar>T\*)"
    rb"|(?P<str>\((?:[^()\\]|\\.)*\))",
    re.S,
)


def _pdf_unescape(s: bytes) -> bytes:
    """Resolve the escapes inside a PDF literal string. pdftex emits (, ) and
    every non-ASCII glyph as three-digit octal, so skipping this step loses the
    parentheses and mangles anything accented."""
    out = bytearray()
    i = 0
    simple = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
    while i < len(s):
        c = s[i]
        if c != 0x5C:
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= len(s):
            break
        d = s[i]
        if d in simple:
            out.append(simple[d])
            i += 1
        elif 0x30 <= d <= 0x37:
            digits = ""
            while i < len(s) and 0x30 <= s[i] <= 0x37 and len(digits) < 3:
                digits += chr(s[i])
                i += 1
            out.append(int(digits, 8) & 0xFF)
        elif d in (0x0A, 0x0D):
            i += 1
        else:
            out.append(d)
            i += 1
    return bytes(out)


class Pdf:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.trouble: list[str] = []
        self.raw = path.read_bytes()
        self.objects: dict[int, bytes] = {}
        for m in _OBJ_RE.finditer(self.raw):
            num = int(m.group(1))
            start = m.end()
            end = self.raw.find(b"endobj", start)
            if end < 0:
                continue
            self.objects[num] = self.raw[start:end]
        if b"/ObjStm" in self.raw:
            self.trouble.append(
                "this PDF uses compressed object streams (/ObjStm); the font and "
                "metadata scan below sees only the objects outside them"
            )

    # -- streams ------------------------------------------------------------

    def stream(self, num: int) -> bytes:
        body = self.objects.get(num, b"")
        i = body.find(b"stream")
        if i < 0:
            return b""
        j = i + 6
        if body[j:j + 2] == b"\r\n":
            j += 2
        elif body[j:j + 1] in (b"\n", b"\r"):
            j += 1
        k = body.rfind(b"endstream")
        data = body[j:k] if k > j else b""
        if b"/FlateDecode" in body[:i]:
            try:
                data = zlib.decompress(data)
            except zlib.error:
                try:                       # truncated tail: take what decodes
                    data = zlib.decompressobj().decompress(data)
                except zlib.error:
                    return b""
        return data

    def all_streams(self) -> list[tuple[int, bytes]]:
        out = []
        for num in self.objects:
            s = self.stream(num)
            if s:
                out.append((num, s))
        return out

    # -- page tree ----------------------------------------------------------

    def page_objects(self) -> list[int]:
        """Page object numbers in reading order, via the page tree. Falls back
        to object order only if the tree cannot be walked, and says so."""
        root = None
        for num, body in self.objects.items():
            if re.search(rb"/Type\s*/Catalog", body):
                m = re.search(rb"/Pages\s+(\d+)\s+0\s+R", body)
                if m:
                    root = int(m.group(1))
                break
        ordered: list[int] = []
        if root is not None:
            seen: set[int] = set()

            def walk(n: int) -> None:
                if n in seen or n not in self.objects:
                    return
                seen.add(n)
                body = self.objects[n]
                if re.search(rb"/Type\s*/Pages", body):
                    kids = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
                    if kids:
                        for km in re.finditer(rb"(\d+)\s+0\s+R", kids.group(1)):
                            walk(int(km.group(1)))
                elif re.search(rb"/Type\s*/Page[^s]", body):
                    ordered.append(n)

            walk(root)
        if not ordered:
            self.trouble.append("page tree unreadable; falling back to object order")
            ordered = sorted(n for n, b in self.objects.items()
                             if re.search(rb"/Type\s*/Page[^s]", b))
        return ordered

    def page_count(self) -> int:
        return len(self.page_objects())

    def _contents_of(self, page_obj: int) -> bytes:
        body = self.objects.get(page_obj, b"")
        m = re.search(rb"/Contents\s+(\d+)\s+0\s+R", body)
        if m:
            return self.stream(int(m.group(1)))
        m = re.search(rb"/Contents\s*\[(.*?)\]", body, re.S)
        if m:
            return b"\n".join(self.stream(int(x)) for x in re.findall(rb"(\d+)\s+0\s+R", m.group(1)))
        return b""

    def page_lines(self, page_obj: int) -> list[tuple[float, str]]:
        """[(baseline_y, text)] for one page, top of page first.

        Only the page's own content stream is read. Text inside a figure's Form
        XObject is deliberately NOT included -- it is not body text, it must not
        move the page count, and the anonymity gate scans every stream anyway."""
        s = self._contents_of(page_obj)
        y = 0.0
        leading = 0.0
        rows: list[tuple[float, str]] = []
        for m in _TEXT_TOKENS.finditer(s):
            if m.group(0) == b"BT":
                y = 0.0
            elif m.group("tm"):
                y = float(m.group("ty"))
            elif m.group("td"):
                dy = float(m.group("dy"))
                y += dy
                if dy:
                    leading = dy
            elif m.group("tstar"):
                y += leading
            elif m.group("str"):
                rows.append((y, _pdf_unescape(m.group("str")[1:-1]).decode("latin-1")))
        merged: dict[float, list[str]] = {}
        for yy, t in rows:
            merged.setdefault(round(yy, 1), []).append(t)
        return sorted(((yy, "".join(parts)) for yy, parts in merged.items()),
                      key=lambda r: -r[0])

    def pages_text(self) -> list[str]:
        return ["".join(t for _, t in self.page_lines(p)) for p in self.page_objects()]

    # -- fonts --------------------------------------------------------------

    def _basefont(self, body: bytes, num: int) -> str:
        """/BaseFont is usually a name, but pdftex writes it as an indirect
        reference for fonts it inherited from an embedded figure. Following the
        reference is the difference between naming the font and reporting
        "(unnamed)" for exactly the fonts that came in from a figure."""
        m = re.search(rb"/BaseFont\s*/([#\w+.-]+)", body)
        if m:
            return m.group(1).decode("latin-1")
        m = re.search(rb"/BaseFont\s+(\d+)\s+0\s+R", body)
        if m:
            target = self.objects.get(int(m.group(1)), b"")
            n = re.search(rb"^\s*/([#\w+.-]+)", target)
            if n:
                return n.group(1).decode("latin-1")
        return "(unnamed obj %d)" % num

    def fonts(self) -> list[tuple[str, str]]:
        """[(basefont, leaf_subtype)]. Type0 wrappers are resolved to the
        descendant font that actually carries the glyph outlines, because that
        is the one whose type the venue's checker reports."""
        found: dict[str, str] = {}
        for num, body in self.objects.items():
            if not re.search(rb"/Type\s*/Font", body):
                continue
            sub = re.search(rb"/Subtype\s*/(\w+)", body)
            if not sub:
                continue
            subtype = sub.group(1).decode("latin-1")
            name = self._basefont(body, num)
            if subtype == "Type0":
                desc = re.search(rb"/DescendantFonts\s*\[?\s*(\d+)\s+0\s+R", body)
                if desc:
                    dbody = self.objects.get(int(desc.group(1)), b"")
                    dsub = re.search(rb"/Subtype\s*/(\w+)", dbody)
                    if dsub:
                        found[name] = dsub.group(1).decode("latin-1")
                        continue
                found[name] = "Type0(unresolved)"
            else:
                found[name] = subtype
        return sorted(found.items())

    def metadata(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key in ("Producer", "Creator", "Author", "Title", "Subject", "Keywords"):
            vals = []
            pat = re.compile(rb"/" + key.encode() + rb"\s*(\((?:[^()\\]|\\.)*\))", re.S)
            for m in pat.finditer(self.raw):
                vals.append(_pdf_unescape(m.group(1)[1:-1]).decode("latin-1"))
            if vals:
                out[key] = " | ".join(sorted(set(vals)))
        return out


TYPE1_FAMILY = {"Type1", "MMType1", "CIDFontType0"}
TRUETYPE_FAMILY = {"TrueType", "CIDFontType2"}


def png_text_chunks(path: Path) -> list[str]:
    """Every tEXt/iTXt/zTXt payload in a PNG. matplotlib writes a Software
    chunk; other tools have been known to write the source path next to it,
    which is why the whole payload is read rather than grepped for a name."""
    data = path.read_bytes()
    out: list[str] = []
    pos = 8
    while pos + 8 <= len(data):
        try:
            length = struct.unpack(">I", data[pos:pos + 4])[0]
        except struct.error:
            break
        ctype = data[pos + 4:pos + 8]
        if ctype in (b"tEXt", b"iTXt", b"zTXt"):
            payload = data[pos + 8:pos + 8 + length]
            if ctype == b"zTXt":
                try:
                    sep = payload.index(b"\0")
                    payload = payload[:sep] + b" " + zlib.decompress(payload[sep + 2:])
                except Exception:
                    pass
            out.append(payload.replace(b"\0", b" ").decode("latin-1", "replace"))
        if ctype == b"IEND":
            break
        pos += 12 + length
    return out


# =============================================================================
# manuscript.md structure
# =============================================================================

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FIGURE_MARKER = re.compile(r"<!--\s*FIGURE\s+(\d+)\s*--\s*(\S+?)\s*-->", re.IGNORECASE)
_HEADING = re.compile(r"^##\s+(.*?)\s*(?:<!--.*)?$", re.M)
_BIB_BEGIN = "<!-- BIBLIOGRAPHY:BEGIN"


def manuscript_text() -> str:
    return MANUSCRIPT_MD.read_text(encoding="utf-8")


def body_prose() -> str:
    """The manuscript body with every HTML comment removed. The comments carry
    the author's own working notes -- including, at the time of writing, two
    sentences about how many figures there used to be -- and a prose check that
    read them would be checking the notes rather than the paper."""
    text = manuscript_text()
    cut = text.find(_BIB_BEGIN)
    if cut > 0:
        text = text[:cut]
    return _HTML_COMMENT.sub(" ", text)


def figure_markers() -> list[tuple[int, str, int]]:
    """[(figure_number, path_relative_to_TAE, manuscript.md line)]"""
    text = manuscript_text()
    out = []
    for m in _FIGURE_MARKER.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        out.append((int(m.group(1)), m.group(2), line))
    return out


def headings() -> list[tuple[str, int]]:
    text = manuscript_text()
    return [(m.group(1).strip(), text.count("\n", 0, m.start()) + 1)
            for m in _HEADING.finditer(text)]


def normalise(s: str) -> str:
    """Kerning splits words across show-operators, so 'Refer ences' and
    'References' are the same heading. Comparisons are made on the
    space-stripped, lowercased form."""
    return re.sub(r"[^a-z0-9\[\]]+", "", s.lower())


# =============================================================================
# GATE 1 -- evidence pipeline
# =============================================================================

def gate_evidence(skip: bool) -> tuple[Gate, dict[str, str]]:
    """Returns the gate and {script_name: PASS|FAIL} so the figures gate can say
    whether a figure on disk came from a script that exited zero."""
    g = Gate("evidence")
    per_script: dict[str, str] = {}

    if not RUN_ALL.is_file():
        g.fail("evidence/run_all.py is missing; the pipeline cannot be verified at all")
        g.headline = "run_all.py not found"
        return g, per_script

    n_declared = len(re.findall(r'^\s*"(\w[\w.]*\.py)",\s*$',
                                RUN_ALL.read_text(encoding="utf-8"), re.M))

    if skip:
        g.skip("--skip-evidence was passed; run without it before submitting")
        g.headline = "SKIPPED (%d scripts not run)" % n_declared
        g.note("run_all.py declares %d scripts; none were executed this run" % n_declared)
        return g, per_script

    t0 = time.time()
    proc = subprocess.run([sys.executable, str(RUN_ALL)],
                          cwd=str(TAE), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    dt = time.time() - t0
    out = proc.stdout or ""

    # run_all.py prints its own summary table; read the verdict off that rather
    # than re-deriving it, so the two can never disagree.
    for m in re.finditer(r"^(\S+\.py)\s+(PASS|FAIL)\s", out, re.M):
        per_script[m.group(1)] = m.group(2)
    total = re.search(r"total (\d+) script\(s\): (\d+) PASS, (\d+) not-PASS", out)

    if total:
        n, npass, nfail = (int(x) for x in total.groups())
    else:
        n, npass, nfail = n_declared, len([v for v in per_script.values() if v == PASS]), \
            len([v for v in per_script.values() if v != PASS])

    g.headline = "%d scripts, %d PASS, %d non-zero (%.0fs)" % (n, npass, nfail, dt)
    g.note("ran: %s (cwd %s)" % (RUN_ALL, TAE))
    g.note("run_all.py exit code %d; its own summary reports %d/%d clean" % (proc.returncode, npass, n))

    if proc.returncode == 0 and nfail == 0:
        return g, per_script

    failed = sorted(k for k, v in per_script.items() if v != PASS)
    g.note("non-zero: " + (", ".join(failed) if failed else "(summary table unparsed)"))

    # Six scripts failing for one reason is one problem, not six. Pull the
    # distinct exception lines out so the report says which.
    causes: dict[str, int] = {}
    for m in re.finditer(r"^(?:\s*\|\s*)?(?:_data\.)?(\w*Error): (.+)$", out, re.M):
        msg = m.group(2).strip()
        msg = re.sub(r"[A-Za-z]:[\\/][^\s'\"]+[\\/]", "<path>/", msg)
        causes[msg] = causes.get(msg, 0) + 1
    if causes:
        g.note("distinct failure cause(s): %d (traceback occurrences, not script count)"
               % len(causes))
        for msg, cnt in sorted(causes.items(), key=lambda kv: -kv[1])[:4]:
            g.note("   seen %-3dx  %s" % (cnt, msg[:150]))

    g.fail("read the captured tail: python %s   "
           "(these scripts exit non-zero ON PURPOSE when a value disagrees with "
           "the verified list, so a failure is a finding, not necessarily a bug)"
           % RUN_ALL.relative_to(TAE.parent.parent))
    if len(causes) == 1:
        g.remedy.append("all %d failures share ONE cause, printed above -- fix that and "
                        "re-run before reading anything else as broken" % nfail)
    return g, per_script


# =============================================================================
# GATE 2 -- figures
# =============================================================================

def gate_figures(per_script: dict[str, str], evidence_ran: bool) -> Gate:
    g = Gate("figures")
    markers = figure_markers()
    if not markers:
        g.fail("no <!-- FIGURE n -- path --> markers found in manuscript.md; either the "
               "paper has no figures or the marker convention changed and this gate is blind")
        g.headline = "no figure markers found"
        return g

    numbers = [n for n, _, _ in markers]
    if numbers != list(range(1, len(numbers) + 1)):
        g.fail("figure markers are numbered %s; they must run 1..N in document order"
               % numbers)

    data_mtime = DATA_MODULE.stat().st_mtime if DATA_MODULE.is_file() else 0.0
    fresh = 0

    for num, rel, line in markers:
        art = (TAE / rel).resolve()
        stem = Path(rel).stem
        png = FIGURES_DIR / (stem + ".png")
        gen = EVIDENCE_DIR / (stem + ".py")

        if not art.is_file():
            g.fail("Figure %d references %s (manuscript.md line %d) and that file does not "
                   "exist; run evidence/%s.py, or fix the marker path" % (num, rel, line, stem))
            continue
        if not png.is_file():
            g.fail("Figure %d has %s but no %s; build.py's .docx branch embeds the PNG "
                   "sibling and will print [FIGURE NOT FOUND] without it"
                   % (num, rel, png.relative_to(TAE)))

        if not gen.is_file():
            g.fail("Figure %d (%s) has no generator at evidence/%s.py, so its freshness "
                   "cannot be established; name the generator after the figure or record "
                   "the mapping here" % (num, rel, stem))
            continue

        a_m = art.stat().st_mtime
        sources = [(gen, gen.stat().st_mtime)]
        if data_mtime and re.search(r"^\s*(from|import)\s+_data\b",
                                    gen.read_text(encoding="utf-8", errors="replace"), re.M):
            sources.append((DATA_MODULE, data_mtime))

        stale = [(p, m) for p, m in sources if m > a_m]
        if stale:
            for p, m in stale:
                g.fail("STALE PICTURE: %s is %s older than %s. The paper embeds a figure no "
                       "current code produces. Run: python %s"
                       % (rel, _ago(m - a_m), p.relative_to(TAE), gen.relative_to(TAE)))
        else:
            fresh += 1

        if evidence_ran:
            st = per_script.get(stem + ".py")
            if st == FAIL:
                g.fail("Figure %d's generator evidence/%s.py exited non-zero this run, so %s "
                       "is whatever survived from the last clean run -- it is NOT evidence "
                       "for the current corpus. Fix the evidence gate first."
                       % (num, stem, rel))

    # The count in the prose, against the count on disk. This is the exact
    # defect class that shipped an artifact statement promising three figures
    # when there were four.
    g.evidence.extend(_prose_count_findings(g, len(markers)))

    g.headline = "%d referenced, %d on disk, %d not older than their sources" % (
        len(markers), sum(1 for _, r, _ in markers if (TAE / r).is_file()), fresh)
    g.note("rule: artefact mtime >= generator mtime (and >= _data.py when imported); "
           "manuscript.pdf mtime >= artefact mtime (checked after the build, below)")
    for num, rel, line in markers:
        art = TAE / rel
        g.note("  Fig %d  %-38s %s  gen evidence/%s.py"
               % (num, rel, _stamp(art), Path(rel).stem))
    return g


def figures_vs_pdf(g: Gate) -> None:
    """Does the built PDF embed the figures that are on disk now?

    Deliberately evaluated AFTER the build gate rather than inside gate_figures,
    which has to run before it (the evidence pipeline rewrites figures/, and a
    freshness check taken after the build would be comparing the PDF against
    files the build never saw). Comparing an about-to-be-replaced PDF against a
    just-regenerated figure reports staleness that the very next step fixes."""
    if not MANUSCRIPT_PDF.is_file():
        g.fail("no manuscript.pdf, so no figure can be confirmed to be in the built paper")
        return
    pdf_m = MANUSCRIPT_PDF.stat().st_mtime
    late = []
    for num, rel, _ in figure_markers():
        art = TAE / rel
        if art.is_file() and art.stat().st_mtime > pdf_m:
            late.append((num, rel, art.stat().st_mtime - pdf_m))
    for num, rel, delta in late:
        g.fail("manuscript.pdf is %s older than %s, so the built paper shows the previous "
               "version of Figure %d. Rebuild: python paper/build.py && pdflatex manuscript.tex"
               % (_ago(delta), rel, num))
    if not late:
        g.note("manuscript.pdf (%s) is at least as new as all %d embedded figures"
               % (_stamp(MANUSCRIPT_PDF), len(figure_markers())))


_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "both": 2}


def _prose_count_findings(g: Gate, n_figures: int) -> list[str]:
    """Does a sentence in the body claim a number of figures or tables that the
    document does not have?"""
    prose = body_prose()
    n_tables = len(re.findall(r"^\*\*Table\s+\d+\.", prose, re.M))
    actual = {"figures": n_figures, "tables": n_tables}
    lines: list[str] = []
    pat = re.compile(r"\b(?:all\s+|both\s+)?(one|two|three|four|five|six|seven|eight|nine|ten|"
                     r"both|\d+)\s+(figures|tables)\b", re.I)
    for m in pat.finditer(prose):
        raw = m.group(1).lower()
        claimed = _WORD_NUM.get(raw, int(raw) if raw.isdigit() else None)
        kind = m.group(2).lower()
        if claimed is None:
            continue
        line_no = prose.count("\n", 0, m.start()) + 1
        ctx = re.sub(r"\s+", " ", prose[max(0, m.start() - 60):m.end() + 30]).strip()
        if claimed != actual[kind]:
            g.fail('the body says "%s" but there are %d %s. manuscript.md near line %d: '
                   "...%s... -- fix the sentence or the artefact"
                   % (m.group(0), actual[kind], kind, line_no, ctx))
        else:
            lines.append('  prose "%s" agrees with the %d %s on disk' % (m.group(0), actual[kind], kind))
    lines.append("  counted %d figure markers and %d table captions in the body"
                 % (n_figures, n_tables))
    return lines


def _stamp(p: Path) -> str:
    if not p.is_file():
        return "MISSING"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))


def _ago(seconds: float) -> str:
    seconds = abs(seconds)
    if seconds < 90:
        return "%.0f s" % seconds
    if seconds < 5400:
        return "%.0f min" % (seconds / 60)
    if seconds < 172800:
        return "%.1f hr" % (seconds / 3600)
    return "%.1f days" % (seconds / 86400)


# =============================================================================
# GATE 3 -- build chain
# =============================================================================

def _run(cmd: list[str], cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def find_pdflatex() -> str | None:
    found = shutil.which("pdflatex")
    if found:
        return found
    for cand in PDFLATEX_CANDIDATES:
        if cand and Path(cand).is_file():
            return cand
    return None


def gate_build(do_build: bool) -> Gate:
    g = Gate("build")

    if not do_build:
        if not MANUSCRIPT_PDF.is_file():
            g.fail("--no-build was passed but there is no manuscript.pdf to check. "
                   "Run without --no-build.")
            g.headline = "no PDF and no build"
            return g
        g.headline = "NOT REBUILT -- checking the existing PDF (%s)" % _stamp(MANUSCRIPT_PDF)
        g.note("--no-build: the four build guards did NOT run this pass.")
        g.note("existing artefacts: manuscript.pdf %s | manuscript.tex %s | manuscript.log %s"
               % (_stamp(MANUSCRIPT_PDF), _stamp(MANUSCRIPT_TEX), _stamp(MANUSCRIPT_LOG)))
        if MANUSCRIPT_MD.is_file() and MANUSCRIPT_MD.stat().st_mtime > MANUSCRIPT_PDF.stat().st_mtime:
            g.fail("manuscript.md is %s NEWER than manuscript.pdf -- the PDF being checked is "
                   "not the current source. Re-run without --no-build."
                   % _ago(MANUSCRIPT_MD.stat().st_mtime - MANUSCRIPT_PDF.stat().st_mtime))
        _log_findings(g)
        return g

    steps: list[str] = []

    # 1. bibliography guard (--check: validate, never rewrite the master source)
    p = _run([sys.executable, "make_bibliography.py", "--check"], HERE)
    steps.append("make_bibliography --check exit %d" % p.returncode)
    if p.returncode != 0:
        g.fail("make_bibliography.py --check failed:\n      %s\n      Fix references.bib, then: "
               "python make_bibliography.py" % _first_lines(p.stdout + p.stderr, 4))
    else:
        g.note("bibliography: " + _first_lines(p.stdout, 1))

    # 2. claim markers -- both directions
    p = _run([sys.executable, "substitute.py"], HERE)
    steps.append("substitute exit %d" % p.returncode)
    if p.returncode != 0:
        g.fail("substitute.py failed -- a {{CLAIM:...}} marker is unsourced or a CLAIMS entry "
               "is unused:\n      %s" % _first_lines(p.stdout + p.stderr, 6))
    else:
        g.note("claims: " + _first_lines(p.stdout, 1))

    # 3. build.py -- the non-ASCII guard lives inside _escape_tex
    p = _run([sys.executable, "build.py"], HERE)
    steps.append("build exit %d" % p.returncode)
    combined = p.stdout + p.stderr
    if p.returncode != 0:
        hint = ""
        if "un-mappable non-ASCII character" in combined:
            m = re.search(r"un-mappable non-ASCII character.*", combined)
            hint = "\n      NON-ASCII GUARD TRIPPED: %s\n      Add it to _TEX_UNICODE in build.py." \
                   % (m.group(0)[:160] if m else "")
        g.fail("build.py failed:%s\n      %s" % (hint, _first_lines(combined, 6)))
    else:
        ok = "un-mappable non-ASCII character" not in combined
        g.note("build.py: .tex and .docx produced; non-ASCII guard %s"
               % ("clean (no un-mappable character reached LaTeX)" if ok else "REPORTED A CHARACTER"))
        for w in re.findall(r"^\s*WARNING: .*$", combined, re.M):
            g.fail("build.py warned: %s" % w.strip())

    # 4. pdflatex, twice (cross-references and the .aux page numbers need pass 2)
    tex = find_pdflatex()
    if not tex:
        g.fail("pdflatex not found on PATH nor at any known MiKTeX location; the PDF cannot "
               "be built or verified. Install MiKTeX or put pdflatex on PATH.")
        g.headline = "; ".join(steps) + "; pdflatex MISSING"
        return g
    g.note("pdflatex: %s" % tex)
    rc = None
    for i in (1, 2):
        try:
            p = _run([tex, "-interaction=nonstopmode", "-halt-on-error", "manuscript.tex"], HERE)
        except subprocess.TimeoutExpired:
            g.fail("pdflatex pass %d timed out" % i)
            rc = -1
            break
        rc = p.returncode
        if rc != 0:
            g.fail("pdflatex pass %d exited %d. Last LaTeX error:\n      %s"
                   % (i, rc, _first_lines("\n".join(re.findall(r"^!.*$", p.stdout, re.M)), 3)
                      or "(none printed; read manuscript.log)"))
            break
    steps.append("pdflatex x2 exit %s" % rc)

    _log_findings(g)
    g.headline = "; ".join(steps)
    return g


# =============================================================================
# GATE 4 -- official TAE workshop contract
# =============================================================================

def gate_venue() -> Gate:
    """Check source-level requirements that distinguish TAE from NeurIPS main."""
    g = Gate("venue")
    if not MANUSCRIPT_TEX.is_file():
        g.fail("manuscript.tex is missing; the official TAE template contract cannot be checked")
        g.headline = "missing manuscript.tex"
        return g

    tex = MANUSCRIPT_TEX.read_text(encoding="utf-8", errors="replace")
    style = re.search(r"\\usepackage\s*\[([^]]+)\]\s*\{neurips_2026\}", tex)
    if not style or style.group(1).replace(" ", "") != "dblblindworkshop":
        observed = style.group(1) if style else "(missing)"
        g.fail("manuscript.tex must load \\usepackage[dblblindworkshop]{neurips_2026}; "
               "observed [%s]" % observed)
    else:
        g.note("submission style: [dblblindworkshop]")

    if re.search(r"\\usepackage\s*\[[^]]*\bfinal\b[^]]*\]\s*\{neurips_2026\}", tex):
        g.fail("manuscript.tex loads the [final] option; TAE submissions must remain blind")

    title = re.search(r"^\\workshoptitle\s*\{([^}]*)\}", tex, re.M)
    if not title or title.group(1).strip() != VENUE_WORKSHOP_TITLE:
        observed = title.group(1).strip() if title else "(missing)"
        g.fail("\\workshoptitle must be %r; observed %r" % (VENUE_WORKSHOP_TITLE, observed))
    else:
        g.note("workshop title: %s" % VENUE_WORKSHOP_TITLE)

    g.note("requirements source: %s (checked 2026-08-04)" % VENUE_CFP_URL)
    g.note("CFP contract: anonymized single PDF, up to 8 body pages, non-archival poster workshop")
    g.headline = "TAE workshop option/title PASS; CFP contract recorded"
    return g


def _log_findings(g: Gate) -> None:
    """LaTeX error count and overfull-box count, read out of manuscript.log.
    An overfull box is text past the right margin -- the venue sees it, and the
    author usually does not."""
    if not MANUSCRIPT_LOG.is_file():
        g.fail("manuscript.log is missing; LaTeX errors and overfull boxes cannot be counted")
        return
    log = MANUSCRIPT_LOG.read_text(encoding="utf-8", errors="replace")
    errors = re.findall(r"^!.*$", log, re.M)
    overfull = re.findall(r"^Overfull \\[hv]box.*$", log, re.M)
    underfull = re.findall(r"^Underfull \\[hv]box.*$", log, re.M)
    pages = re.search(r"Output written on \S+ \((\d+) pages?, (\d+) bytes\)", log)
    g.note("manuscript.log (%s): %d LaTeX error(s), %d overfull box(es), %d underfull"
           % (_stamp(MANUSCRIPT_LOG), len(errors), len(overfull), len(underfull)))
    if pages:
        g.note("  log says: %s pages, %s bytes" % (pages.group(1), pages.group(2)))
    if errors:
        for e in errors[:5]:
            g.fail("LaTeX error: %s" % e.strip()[:160])
    if overfull:
        for o in overfull[:5]:
            g.fail("overfull box (text past the margin): %s" % o.strip()[:160])


def _first_lines(s: str, n: int) -> str:
    lines = [l for l in (s or "").splitlines() if l.strip()]
    return "\n      ".join(lines[:n])


# =============================================================================
# GATE 5 -- page limit
# =============================================================================

def gate_pages(pdf: Pdf | None) -> Gate:
    g = Gate("pages")
    if pdf is None:
        g.fail("no manuscript.pdf to measure")
        g.headline = "no PDF"
        return g

    page_objs = pdf.page_objects()
    n_pages = len(page_objs)
    per_page = [pdf.page_lines(p) for p in page_objs]
    flat = ["".join(t for _, t in lines) for lines in per_page]
    norm = [normalise(t) for t in flat]

    # The References heading is the only place in the document where the word is
    # immediately followed by the first reference label, optionally past a line
    # number. Body prose that merely uses the word "reference" cannot match.
    ref_page = None
    ref_y = None
    for i, (n, lines) in enumerate(zip(norm, per_page), start=1):
        if re.search(r"references\d*\[1\]", n):
            ref_page = i
            for y, t in lines:
                if normalise(t).startswith("references"):
                    ref_y = y
                    break
            break
    if ref_page is None:                       # heading and [1] split across a page break
        for i, n in enumerate(norm, start=1):
            if n.rstrip("0123456789").endswith("references"):
                ref_page = i
                break

    heads = headings()
    ref_line = next((ln for h, ln in heads if h.lower().startswith("references")), None)
    body_heads = [(h, ln) for h, ln in heads
                  if not h.lower().startswith("references")
                  and not h.lower().startswith("appendix")]

    if ref_page is None:
        g.fail("could not locate the References heading in the PDF, so the body's extent is "
               "unknown. Do not read this as a pass. Check that build.py still emits "
               "\\section*{References} and that manuscript.md line %s is intact."
               % (ref_line if ref_line else "?"))
        g.headline = "%d pages; References not located" % n_pages
        return g

    # Does any BODY content sit on the References page? The limit counts BODY
    # pages, and a References heading typeset at the very top of page N means the
    # body ended on page N-1. This is measured, not assumed: body lines are the
    # ones typeset above the heading on that page, the same test the slack note
    # below already used to say "References is the first thing on page N, so the
    # body ends on page N-1". Until 2026-08-03 that note and the limit check
    # disagreed -- the check read body_pages = ref_page unconditionally, so a
    # body that ended exactly on the limit was reported as overrunning it by one
    # page. The default when the heading's position is unknown stays the strict
    # one, so this cannot convert a real overflow into a pass.
    body_on_ref_page = True
    if ref_y is not None:
        _ref_lines = per_page[ref_page - 1]
        body_on_ref_page = any(y > ref_y + 1 for y, _ in _ref_lines)
    body_pages = ref_page if body_on_ref_page else ref_page - 1
    g.note("PDF: %s (%s), %d pages" % (MANUSCRIPT_PDF.name, _stamp(MANUSCRIPT_PDF), n_pages))
    g.note("References heading typeset on page %d (manuscript.md line %s); the 8-page limit "
           "excludes it and everything after" % (ref_page, ref_line))

    # Nothing but references may follow. Measured by looking for any body
    # heading's text on a later page, not by trusting the section order.
    intruders = []
    for h, ln in body_heads:
        target = normalise(re.sub(r"^\d+\s+", "", h))
        if len(target) < 6:
            continue
        for i in range(ref_page, n_pages):     # pages strictly after ref_page
            if target in norm[i]:
                intruders.append((h, ln, i + 1))
    for h, ln, pg in intruders:
        g.fail('body section "%s" (manuscript.md line %d) appears on page %d, AFTER References '
               "begins on page %d. The 8-page body is not contiguous; move it before the "
               "reference list." % (h, ln, pg, ref_page))

    if body_pages > BODY_PAGE_LIMIT:
        last_body = body_heads[-1] if body_heads else ("?", 0)
        g.fail("body runs to page %d; the limit is %d. References begins on page %d "
               "(manuscript.md line %s) and the last body section is \"%s\" at line %d. "
               "Cut roughly %d page(s) of body, or reclaim space with build.py's "
               "FIGURE_WIDTH_FRACTION."
               % (body_pages, BODY_PAGE_LIMIT, ref_page, ref_line,
                  last_body[0], last_body[1], body_pages - BODY_PAGE_LIMIT))

    # An independent second opinion on the same question, from pdflatex's own
    # .aux: the page each numbered section started on.
    aux = HERE / "manuscript.aux"
    if aux.is_file():
        toc = re.findall(r"\\contentsline \{section\}\{\\numberline \{(\d+)\}(.*?)\}\{(\d+)\}",
                         aux.read_text(encoding="utf-8", errors="replace"))
        if toc:
            last = max(toc, key=lambda t: int(t[2]))
            g.note("cross-check, manuscript.aux: %d numbered sections, the last starting on "
                   "page %s (section %s)" % (len(toc), last[2], last[0]))
            if int(last[2]) > BODY_PAGE_LIMIT:
                g.fail("manuscript.aux puts numbered section %s on page %s, past the %d-page "
                       "limit" % (last[0], last[2], BODY_PAGE_LIMIT))

    # How much room is left on the last body page. This replaces the hand-written
    # "about 9 lines of slack" note that had already been spent when it was read.
    slack_txt = ""
    if ref_y is not None:
        # Baseline skip: the modal gap between consecutive baselines, taken only
        # over gaps a running paragraph can produce. Line-number labels and
        # footnote-sized runs sit at their own smaller leading and would drag a
        # naive mode down to about half the body's, which is how a slack figure
        # ends up roughly double the truth.
        deltas: list[float] = []
        for lines in per_page:
            ys = sorted({y for y, _ in lines})
            deltas += [round(b - a, 1) for a, b in zip(ys, ys[1:]) if 8.0 <= (b - a) <= 16.0]
        skip = max(set(deltas), key=deltas.count) if deltas else 10.9

        # Bottom of the text block, measured on the page the body ends on, not
        # across the document: a figure page has content lower than a text page.
        ref_lines = per_page[ref_page - 1]
        ys_here = sorted(y for y, _ in ref_lines)
        folio = ys_here[0] if ys_here else 0.0
        body_floor = min((y for y, t in ref_lines
                          if y > folio + 5 and not t.strip().isdigit()), default=ref_y)

        # The last body line is the lowest one ABOVE the References heading.
        # Slack is what fits between it and the floor: new body lines go below
        # it and push the reference list onto the next page, which costs
        # nothing, until a body line itself would land past the floor.
        above = [y for y, _ in ref_lines if y > ref_y + 1]
        if above:
            last_body_y = min(above)
            spare = int((last_body_y - body_floor) // skip)
            slack_txt = "; %d body line(s) spare on p%d" % (spare, ref_page)
            g.note("slack: last body line on page %d sits at y=%.1f, the text block's bottom on "
                   "that page is y=%.1f, body baseline skip %.1f pt -> about %d more body "
                   "line(s) fit before the body itself spills onto page %d. Estimate: assumes "
                   "the dominant baseline skip, no float reflow, and that the reference list "
                   "may move down freely."
                   % (ref_page, last_body_y, body_floor, skip, spare, ref_page + 1))
        else:
            g.note("slack: References is the first thing on page %d, so the body ends on page "
                   "%d and the slack on that page is not measured here."
                   % (ref_page, ref_page - 1))

    g.headline = "%d pp; body ends p%d, References from p%d, limit %d%s" % (
        n_pages, body_pages, ref_page, BODY_PAGE_LIMIT, slack_txt)
    return g


# =============================================================================
# GATE 6 -- fonts
# =============================================================================

def gate_fonts(pdf: Pdf | None, strict_truetype: bool = False) -> Gate:
    g = Gate("fonts")
    if pdf is None:
        g.fail("no manuscript.pdf to inspect")
        g.headline = "no PDF"
        return g

    fonts = pdf.fonts()
    if not fonts:
        g.fail("no embedded fonts found at all -- the reader failed, not the PDF. "
               "Do not read this as a pass.")
        g.headline = "font table unreadable"
        return g

    # Attribute each font to the file it came from, so a remedy names a script.
    origins: dict[str, list[str]] = {}
    for fig in sorted(FIGURES_DIR.glob("*.pdf")):
        try:
            for name, _ in Pdf(fig).fonts():
                origins.setdefault(name, []).append("figures/" + fig.name)
        except Exception:
            continue

    def origin(name: str) -> str:
        where = origins.get(name)
        if not where:
            return "paper/manuscript.tex"
        return where[0] if len(where) == 1 else "%s (+%d more)" % (where[0], len(where) - 1)

    t1 = [f for f in fonts if f[1] in TYPE1_FAMILY]
    tt = [f for f in fonts if f[1] in TRUETYPE_FAMILY]
    t3 = [f for f in fonts if f[1] == "Type3"]
    other = [f for f in fonts if f[1] not in TYPE1_FAMILY | TRUETYPE_FAMILY | {"Type3"}]

    g.note("%d embedded font(s) in %s, resolved through Type0 wrappers to the descendant "
           "that carries the outlines:" % (len(fonts), MANUSCRIPT_PDF.name))
    for name, sub in fonts:
        g.note("  %-34s %-14s %s" % (name, sub, origin(name)))

    if t3:
        for name, _ in t3:
            g.fail("TYPE 3 BITMAP FONT: %s (from %s). The NeurIPS template says in plain "
                   "words: \"If your file contains type 3 fonts... we will ask you to fix "
                   "it.\" This is the venue-blocking class." % (name, origin(name)))
        g.remedy.append("a Type 3 usually arrives from the template's line-number font or from "
                        "matplotlib's default pdf.fonttype=3; the figure scripts already set "
                        "pdf.fonttype=42, so check the LaTeX side first")

    if tt:
        files = sorted({f for n, _ in tt for f in origins.get(n, ["the LaTeX build"])})
        if not strict_truetype:
            g.note("embedded TrueType is accepted under the official template policy: "
                   "the venue permits Type 1 or embedded TrueType; Type 3 remains forbidden")
            for name, sub in tt:
                g.note("  accepted: %-30s %s" % (name, sub))
        else:
            g.fail("%d embedded font(s) are TrueType outlines, not Type 1: %s. They come from "
                   "%s -- matplotlib's pdf.fonttype=42 setting in the figure scripts, which "
                   "was the fix for a Type 3 and traded one non-Type-1 kind for another."
                   % (len(tt), ", ".join(n for n, _ in tt), ", ".join(files)))
            g.remedy.append("remove the --strict-truetype policy for the submission gate, or "
                            "convert the figure fonts to Type 1; the official template permits "
                            "embedded TrueType and still rejects Type 3.")

    for name, sub in other:
        g.fail("font %s has unrecognised subtype %s; classify it before submitting" % (name, sub))

    for t in pdf.trouble:
        g.fail("PDF reader caveat: %s" % t)

    g.headline = "%d embedded: %d Type 1, %d TrueType, %d Type 3" % (
        len(fonts), len(t1), len(tt), len(t3))
    return g


# =============================================================================
# GATE 7 -- anonymity
# =============================================================================

def _identity_needles() -> list[tuple[str, str]]:
    """[(label, value)] -- derived at runtime, never hardcoded, and only the
    LABEL is ever printed. Values come from build.py's own camera-ready
    constants and from this machine's account and repository path, so the gate
    works on any checkout without carrying anyone's name in its source."""
    needles: list[tuple[str, str]] = []
    src = ""
    try:
        src = (HERE / "build.py").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    for const, label in (("AUTHOR_NAME", "author-name (build.py)"),
                         ("AUTHOR_EMAIL", "author-email (build.py)"),
                         ("AUTHOR_AFFILIATION", "affiliation (build.py)")):
        m = re.search(r'^%s\s*=\s*"([^"]+)"' % const, src, re.M)
        if m and len(m.group(1)) >= 4:
            needles.append((label, m.group(1)))
            if const == "AUTHOR_EMAIL" and "@" in m.group(1):
                needles.append(("email-handle (build.py)", m.group(1).split("@")[0]))
            if const == "AUTHOR_NAME":
                for part in m.group(1).split():
                    if len(part) >= 4:
                        needles.append(("author-name-part (build.py)", part))
    home = Path.home().name
    if len(home) >= 3:
        needles.append(("this machine's account name", home))
    generic = {"users", "desktop", "documents", "paper", "figures", "evidence",
               "submission_2026", "tae", "appdata", "local", "programs"}
    for part in TAE.parts:
        if len(part) >= 5 and part.lower() not in generic and not re.match(r"^[A-Za-z]:", part):
            needles.append(("repository path component", part))
    # de-duplicate on value, keep the first (most specific) label
    seen: set[str] = set()
    out = []
    for label, val in needles:
        if val.lower() not in seen:
            seen.add(val.lower())
            out.append((label, val))
    return out


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9.-]{2,}\.[A-Za-z]{2,}")
_WINPATH_RE = re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}[A-Za-z0-9._-]+", re.I)
_NIXPATH_RE = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+")


def _scan(blob: str, needles: list[tuple[str, str]]) -> list[str]:
    """Return LABELS only. Never the matched text."""
    hits = []
    low = blob.lower()
    for label, val in needles:
        if val.lower() in low:
            hits.append(label)
    if _EMAIL_RE.search(blob):
        hits.append("an email address (regex)")
    if _WINPATH_RE.search(blob):
        hits.append("a Windows user path (regex)")
    if _NIXPATH_RE.search(blob):
        hits.append("a Unix home path (regex)")
    return sorted(set(hits))


def gate_anonymity(pdf: Pdf | None) -> Gate:
    g = Gate("anonymity")
    needles = _identity_needles()
    if not needles:
        g.fail("could not derive any identity needle from build.py or the environment, so "
               "this gate checked nothing. Do not read it as a pass.")
        g.headline = "no needles derived"
        return g
    g.note("%d identity needle(s) derived at runtime from build.py's camera-ready constants "
           "and this machine's account/repository path. Values are never printed; only the "
           "label and the location of a hit." % len(needles))
    g.note("plus three regexes: any email address, any Windows user path, any Unix home path.")

    # -- the blind/camera-ready switch --------------------------------------
    src = (HERE / "build.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^CAMERA_READY\s*=\s*(True|False)", src, re.M)
    if not m:
        g.fail("CAMERA_READY not found in build.py; the blind/de-anonymised switch cannot be "
               "confirmed")
    elif m.group(1) == "True":
        g.fail("build.py has CAMERA_READY = True -- this build is DE-ANONYMISED (populated "
               "\\author{} and the [final] style option). Set it False and rebuild before "
               "submitting. ANONYMITY.md section 6.")
    else:
        g.note("build.py CAMERA_READY = False (blind submission state)")

    if MANUSCRIPT_TEX.is_file():
        tex = MANUSCRIPT_TEX.read_text(encoding="utf-8", errors="replace")
        am = re.search(r"\\author\s*\{(.*?)\}", tex, re.S)
        if am and am.group(1).strip():
            g.fail("manuscript.tex has a non-empty \\author{} block; it must be empty for a "
                   "double-blind submission")
        else:
            g.note("manuscript.tex: \\author{} is empty")
        if re.search(r"\\usepackage\[[^\]]*\bfinal\b[^\]]*\]\{neurips_2026\}", tex):
            g.fail("manuscript.tex loads neurips_2026 with the [final] option, which "
                   "de-anonymises the page; blind submissions use [dblblindworkshop] alone")

    # -- source files --------------------------------------------------------
    for f in (MANUSCRIPT_MD, SUBSTITUTED_MD, MANUSCRIPT_TEX):
        if not f.is_file():
            continue
        hits = _scan(f.read_text(encoding="utf-8", errors="replace"), needles)
        # ANONYMITY.md documents these as expected only inside build.py.
        if hits:
            g.fail("%s contains: %s. Read the hit in context (ANONYMITY.md section 6 lists the "
                   "known false-positive class) and remove it before building."
                   % (f.name, "; ".join(hits)))
        else:
            g.note("%-28s clean (%d needles + 3 regexes)" % (f.name, len(needles)))

    # -- the PDF: text, every stream, and the metadata -----------------------
    scanned = 0
    if pdf is not None:
        meta = pdf.metadata()
        g.note("manuscript.pdf metadata: " + ("; ".join("%s=%s" % (k, v) for k, v in meta.items())
                                              or "(none)"))
        for k, v in meta.items():
            for h in _scan(v, needles):
                g.fail("manuscript.pdf metadata field /%s contains: %s. Strip it "
                       "(ANONYMITY.md section 4) before submitting." % (k, h))
        blob = pdf.raw.decode("latin-1", "replace")
        for num, s in pdf.all_streams():
            blob += "\n" + s.decode("latin-1", "replace")
        for h in _scan(blob, needles):
            g.fail("manuscript.pdf carries %s inside its bytes (text, an object stream, or an "
                   "embedded font name). ANONYMITY.md section 4 has the strip recipe." % h)
        scanned += 1

    # -- every figure PDF and PNG the manuscript embeds ----------------------
    for num, rel, _ in figure_markers():
        art = TAE / rel
        if art.is_file():
            try:
                fp = Pdf(art)
            except Exception as e:
                g.fail("could not read %s to check its metadata: %s" % (rel, type(e).__name__))
                continue
            meta = fp.metadata()
            blob = fp.raw.decode("latin-1", "replace")
            for _, s in fp.all_streams():
                blob += "\n" + s.decode("latin-1", "replace")
            hits = _scan(blob, needles)
            if hits:
                g.fail("%s contains: %s. matplotlib and pdflatex both stamp their own "
                       "/Producer and /Creator, and a figure script run from a user directory "
                       "can bake the path in. Regenerate or strip." % (rel, "; ".join(hits)))
            else:
                g.note("%-38s clean | %s" % (rel, "; ".join("%s=%s" % kv for kv in meta.items())[:70]))
            scanned += 1
        png = FIGURES_DIR / (Path(rel).stem + ".png")
        if png.is_file():
            chunks = png_text_chunks(png)
            hits = _scan("\n".join(chunks), needles)
            if hits:
                g.fail("%s has a PNG text chunk containing: %s. Strip the tEXt/iTXt chunks."
                       % (png.name, "; ".join(hits)))
            else:
                g.note("%-38s clean | text chunks: %s"
                       % ("figures/" + png.name, "; ".join(c[:48] for c in chunks) or "(none)"))
            scanned += 1

    # -- cross-check the checklist, without trusting it ----------------------
    if ANONYMITY_MD.is_file():
        txt = ANONYMITY_MD.read_text(encoding="utf-8", errors="replace")
        unticked = len(re.findall(r"^\s*-\s*\[ \]", txt, re.M))
        ticked = len(re.findall(r"^\s*-\s*\[[xX]\]", txt, re.M))
        g.note("ANONYMITY.md present: %d checklist item(s), %d ticked, %d unticked. Ticks are "
               "hand-written and are NOT evidence -- the measurements above are."
               % (ticked + unticked, ticked, unticked))
    else:
        g.note("ANONYMITY.md not found; nothing to cross-check against (the measurements above "
               "still stand on their own)")

    g.headline = "%d artefact(s) scanned, %d needle(s), 0 values printed" % (scanned, len(needles))
    return g


# =============================================================================
# GATE 8 -- citations
# =============================================================================

_BODY_CITE = re.compile(r"\[(\d+)\]")


def gate_citations(pdf: Pdf | None) -> Gate:
    g = Gate("citations")

    if not REFERENCES_BIB.is_file():
        g.fail("references.bib not found")
        g.headline = "no .bib"
        return g

    sys.path.insert(0, str(HERE))
    try:
        import make_bibliography as mb          # reuse the real parser, never a second copy
    except Exception as e:
        g.fail("could not import make_bibliography.py (%s: %s); the citation numbering cannot "
               "be checked against its single source of truth" % (type(e).__name__, e))
        g.headline = "make_bibliography unimportable"
        return g

    try:
        entries = mb.parse_bib(REFERENCES_BIB)
    except Exception as e:
        g.fail("references.bib does not parse (%s: %s)" % (type(e).__name__, e))
        g.headline = ".bib unparseable"
        return g

    cited = list(mb.CITED_ORDER)
    n = len(cited)

    text = manuscript_text()
    head = text.split(mb.BEGIN, 1)[0] if mb.BEGIN in text else text
    body_cites = sorted({int(x) for x in _BODY_CITE.findall(head)})

    g.note("references.bib: %d entries, %d of them in make_bibliography.CITED_ORDER" % (len(entries), n))
    g.note("manuscript.md body: %d distinct [n] citations, highest [%d]"
           % (len(body_cites), max(body_cites) if body_cites else 0))

    missing_key = [k for k in cited if k not in entries]
    for k in missing_key:
        g.fail("CITED_ORDER names '%s' but references.bib has no such entry" % k)

    uncited = [i for i in range(1, n + 1) if i not in body_cites]
    for i in uncited:
        g.fail("reference [%d] (%s) is in the list but nothing in the body cites it. Cite it or "
               "remove it from CITED_ORDER." % (i, cited[i - 1] if i <= n else "?"))

    overrun = [i for i in body_cites if i > n]
    for i in overrun:
        g.fail("the body cites [%d] but there are only %d entries. Add the entry to "
               "CITED_ORDER or fix the number." % (i, n))

    if not missing_key and not uncited and not overrun:
        g.note("counts agree: %d entries cited, %d numbers used in the body, 1..%d contiguous"
               % (n, len(body_cites), n))

    # The rendered list in the built PDF, as a third opinion. Only the text
    # below the References heading is read, so a body citation cannot be
    # mistaken for a list label.
    if pdf is not None:
        labels = _pdf_reference_labels(pdf)
        if labels:
            g.note("built PDF reference list: labels [%d]..[%d], %d entries typeset"
                   % (min(labels), max(labels), len(labels)))
            if sorted(labels) != list(range(1, n + 1)):
                g.fail("the typeset reference list carries labels %s but CITED_ORDER has %d "
                       "entries -- the PDF is not the current bibliography. Re-run "
                       "make_bibliography.py, then rebuild."
                       % (_compact(sorted(labels)), n))
        else:
            g.note("could not read reference labels out of the built PDF (not a failure on its "
                   "own; the .md and .bib checks above are the binding ones)")

    # This project's own standing rule, after the 2026-05-20 incident in which a
    # subagent fabricated ~30% of a reference list: an entry with no fetched
    # page does not belong in the file.
    unverified = []
    for key, fields in sorted(entries.items()):
        note = fields.get("note", "")
        has_url = bool(re.search(r"https?://", note))
        has_date = bool(re.search(r"\b20\d\d-\d\d-\d\d\b", note))
        if not (has_url and has_date):
            why = []
            if not note:
                why.append("no note field")
            else:
                if not has_url:
                    why.append("no fetched URL")
                if not has_date:
                    why.append("no verification date")
            unverified.append((key, ", ".join(why), key in cited))
    if unverified:
        for key, why, is_cited in unverified:
            g.fail("references.bib entry '%s' (%s) records no fetched verification page: %s. "
                   "Fetch the page, put the URL and the date in its note field, or delete the "
                   "entry -- the standing rule after the 2026-05-20 fabrication incident."
                   % (key, "CITED" if is_cited else "not cited", why))
    else:
        g.note("all %d .bib entries carry a note with a fetched URL and an ISO verification "
               "date (cited and uncited alike)" % len(entries))

    not_in_order = sorted(set(entries) - set(cited))
    if not_in_order:
        g.note("%d verified entry/entries kept but not cited (deliberate, per the .bib's own "
               "header): %s" % (len(not_in_order), ", ".join(not_in_order)))

    g.headline = "%d entries, %d cited, body uses [1]..[%d], %d unverified" % (
        len(entries), n, max(body_cites) if body_cites else 0, len(unverified))
    return g


def _pdf_reference_labels(pdf: Pdf) -> list[int]:
    """Numbers [k] typeset at or below the References heading."""
    page_objs = pdf.page_objects()
    started = False
    labels: list[int] = []
    for p in page_objs:
        lines = pdf.page_lines(p)
        for y, t in lines:
            nt = normalise(t)
            if not started and nt.startswith("references"):
                started = True
                continue
            if started:
                m = re.match(r"\[(\d+)\]", t.strip())
                if m:
                    labels.append(int(m.group(1)))
    return labels


def _compact(nums: list[int]) -> str:
    return "[" + "],[".join(str(x) for x in nums[:6]) + ("],..." if len(nums) > 6 else "]")


# =============================================================================
# report
# =============================================================================

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser(
        description="Measure whether the TAE submission is ready. Reads the artefacts, "
                    "not the tracking documents.")
    ap.add_argument("--no-build", action="store_true",
                    help="check the manuscript.pdf already on disk instead of rebuilding")
    ap.add_argument("--skip-evidence", action="store_true",
                    help="skip run_all.py (~60s); the gate is SKIPPED and the exit code is never 0")
    ap.add_argument("--strict-truetype", action="store_true",
                    help="reject embedded TrueType outlines; Type 3 always fails")
    ap.add_argument("--allow-truetype", action="store_true",
                    help="backward-compatible alias for the default embedded-TrueType policy")
    ap.add_argument("--quiet", action="store_true", help="table and verdict only")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 100)
    print("TAE SUBMISSION GATE -- every answer below is measured off disk, not read out of a "
          "tracking document")
    print("=" * 100)
    print("paper      : %s" % HERE)
    print("limit      : body <= %d pages, references and appendices excluded" % BODY_PAGE_LIMIT)
    print("build      : %s" % ("EXISTING PDF (--no-build)" if args.no_build
                               else "rebuild (make_bibliography -> substitute -> build -> pdflatex x2)"))
    print("python     : %s  (%s)" % (sys.version.split()[0], sys.executable))
    sys.stdout.flush()

    gates: list[Gate] = []

    g_ev, per_script = gate_evidence(args.skip_evidence)
    gates.append(g_ev)
    g_fig = gate_figures(per_script, evidence_ran=not args.skip_evidence)
    gates.append(g_fig)
    gates.append(gate_build(do_build=not args.no_build))
    gates.append(gate_venue())
    figures_vs_pdf(g_fig)          # only meaningful once the build has run

    pdf = None
    if MANUSCRIPT_PDF.is_file():
        try:
            pdf = Pdf(MANUSCRIPT_PDF)
        except Exception as e:
            print("\nWARNING: manuscript.pdf could not be read (%s: %s)" % (type(e).__name__, e))

    gates.append(gate_pages(pdf))
    gates.append(gate_fonts(pdf, strict_truetype=args.strict_truetype and not args.allow_truetype))
    gates.append(gate_anonymity(pdf))
    gates.append(gate_citations(pdf))

    # -- the table ----------------------------------------------------------
    print()
    print("=" * 100)
    print("%-11s %-6s %s" % ("GATE", "RESULT", "WHAT IT MEASURED"))
    print("-" * 100)
    for g in gates:
        print("%-11s %-6s %s" % (g.name, g.status, g.headline[:80]))
    print("-" * 100)

    # -- the detail ---------------------------------------------------------
    if not args.quiet:
        for g in gates:
            print()
            print("%s  [%s]  %s" % ("-" * 3, g.name.upper(), "-" * (90 - len(g.name))))
            for line in g.evidence:
                print("   " + line)
            if g.remedy:
                print("   WHAT TO DO:")
                for i, r in enumerate(g.remedy, 1):
                    print("   %2d. %s" % (i, r))

    # -- the verdict --------------------------------------------------------
    failed = [g.name for g in gates if g.status == FAIL]
    skipped = [g.name for g in gates if g.status == SKIP]
    print()
    print("=" * 100)
    if failed:
        code = 1
        print("VERDICT: NOT READY -- %d of %d gates FAILED (%s)%s. Fix the WHAT TO DO items "
              "above, then re-run." % (len(failed), len(gates), ", ".join(failed),
                                       "; %d skipped (%s)" % (len(skipped), ", ".join(skipped))
                                       if skipped else ""))
    elif skipped:
        code = 2
        print("VERDICT: UNVERIFIED -- nothing failed, but %d gate(s) were SKIPPED (%s), so "
              "readiness is not established. Re-run without the skip flag."
              % (len(skipped), ", ".join(skipped)))
    else:
        code = 0
        print("VERDICT: READY -- all %d gates PASSED against the artefacts on disk "
              "(%.0fs)." % (len(gates), time.time() - t0))
    print("=" * 100)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
