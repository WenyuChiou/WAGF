# ANONYMITY.md — double-blind checklist, TAE submission

NeurIPS 2026 TAE workshop is **double-blind** (`\usepackage[dblblindworkshop]{neurips_2026}`) and
**non-archival**. `DECISION.md` §1 and `PLAN.md` §8 both name this a hard constraint that is easy to
forget. `PLAN.md` schedules a dedicated red-team day for it (Block 4, 19 Aug) — this file is what that
day checks against, and it should also be re-run once more on submission day (`PLAN.md` §7, R2).

Run every check below before `manuscript.tex` / `manuscript.docx` leave this folder, and again
immediately before upload to OpenReview.

---

## 1. The two predecessor works — third person only, always

Two of this project's own prior works are directly on-topic and will want citing:

- The group's own **WRR 2026 predecessor**.
- The **Nature Water manuscript** (paused; see `PLAN.md` §9 — do not touch that manuscript itself
  from this workspace, but it may still be *cited* here).

**Rule:** cite both exactly as any other prior work would be cited — third person, no claim of
authorship, no phrase that discloses the author overlap.

| ❌ Do not write | ✅ Write instead |
|---|---|
| "In our previous work [X]…" | "Prior work [X] showed…" |
| "We previously found…" | "\[Author names withheld\] (2026) reported…" or "A related study reported…" |
| "As shown in our companion paper…" | "A concurrent study on the same testbed reports…" |
| "Building on our own irrigation results…" | "Building on prior irrigation-domain results…" |
| Any sentence assuming the reader knows both papers share authors | State the relationship only in terms of *topic overlap*, never *authorship overlap* |

Checklist:
- [ ] Every citation of the WRR 2026 predecessor is third person.
- [ ] Every citation of the Nature Water manuscript is third person.
- [ ] No sentence anywhere implies "our other paper" / "our companion work" / "our prior submission".
- [ ] If either predecessor is unpublished or under review, cite it in a way that does not itself
      deanonymize (no "personal communication", no specific unpublished venue name that maps to one
      lab).

---

## 2. No identifying repository, path, or URL

This repo (`governed_broker_framework`), its owner, its local paths, and its host account are all
identifying.

Checklist:
- [ ] No `github.com/<owner>/...` link, including in a "code available at" sentence. If code
      availability must be claimed, use an **anonymized** hosting link (e.g. an anonymous GitHub
      mirror, or "code will be released upon publication") — never the real repo URL.
- [ ] No local filesystem path anywhere in the PDF — not in body text, not in a figure image, not in
      a figure/table caption, not in an appendix, not in any attached CSV. In particular:
      `C:\Users\wenyu\...`, `C:/Users/wenyu/...`, `Desktop/Lehigh/...`,
      `governed_broker_framework`.
- [ ] No institution name ("Lehigh", or any co-author's institution) anywhere, including in a
      data/ethics statement ("collected under [Institution] IRB protocol …" — use "our institution's
      IRB" instead).
- [ ] Figure files themselves carry no identifying text baked into the image (check `figures/*.png`
      at full resolution, not just the caption).

---

## 3. No acknowledgements, no funding statement

- [ ] No "Acknowledgements" section in the submitted PDF.
- [ ] No funding-source statement (grant numbers, sponsor names) in the submitted PDF. Add these back
      only in the camera-ready version after acceptance, if the venue requires them then.
- [ ] No "This work extends X's undergraduate thesis" / "we thank Prof. Y" — any sentence that names a
      real person.

---

## 4. Author metadata, not just author text

Text can be clean while file metadata still identifies the authors. Both outputs need a metadata
check, not just a body-text read.

**PDF (after compiling `manuscript.tex`):**

```
# inspect
exiftool manuscript.pdf | grep -iE "author|creator|producer|title"
# or, without exiftool (this machine has no exiftool on PATH; pypdf is what
# the 2026-08-03 sweep actually used):
python -c "from pypdf import PdfReader; r=PdfReader('manuscript.pdf'); print(dict(r.metadata))"

# strip
exiftool -all= manuscript.pdf
```

**Figure PDFs (the four files `\includegraphics`'d into `manuscript.tex` — check
each one, not just the compiled manuscript.pdf; matplotlib and pdflatex both
stamp their own /Producer and /Creator strings independently of what the
containing PDF says):**

```
cd SUBMISSION_2026/TAE/figures
python -c "
from pypdf import PdfReader
for f in ['fig0_problem_schematic.pdf','fig1_rule_layers.pdf','fig2_mechanism.pdf','fig3_consequence.pdf']:
    print(f, '->', dict(PdfReader(f).metadata))
"
```

**Figure PNGs (matplotlib's PNG writer embeds a `tEXt` `Software` chunk; on a
machine without exiftool, PIL's `Image.info` only surfaces *some* text chunks,
so a raw PNG-chunk scan is the more thorough check — this is what the
2026-08-03 sweep ran):**

```
cd SUBMISSION_2026/TAE/figures
python -c "
import struct, glob
def text_chunks(path):
    data = open(path, 'rb').read()
    pos, out = 8, []
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8]
        if ctype in (b'tEXt', b'iTXt', b'zTXt'):
            out.append((ctype, data[pos+8:pos+8+length][:200]))
        pos += 8 + length + 4
    return out
for f in sorted(glob.glob('*.png')):
    print(f, '->', text_chunks(f))
"
```

A path or username would show up as part of a chunk's payload text, or (for
the PDFs) inside `/Producer`, `/Creator`, or a nonstandard key a generation
tool added — read the whole dict/list, do not just grep it for "wenyu", since
a differently-cased Windows account name or a repo directory name would slip
past a narrow grep.

**DOCX** (Word keeps the OS account name as "Author" / "Last saved by" in `docProps/core.xml`):

```
python - <<'PY'
from docx import Document
d = Document("manuscript.docx")
props = d.core_properties
props.author = ""
props.last_modified_by = ""
props.comments = ""
d.save("manuscript.docx")
PY
```

Checklist:
- [ ] PDF `Author` / `Creator` / `Producer` fields do not contain a real name or the local Windows
      account name (`wenyu`).
- [ ] DOCX `core_properties.author` and `last_modified_by` are blank (only relevant if a `.docx` is
      ever exported to PDF as a submission path — the primary path is the `.tex` → PDF route).
- [ ] LaTeX build tool (if not plain `pdflatex`/`pdftex`) is not leaking a machine hostname into
      `/Producer` — recheck after every recompile, this resets on each build.

---

## 5. The `build.py` blind/camera-ready switch — where the author block actually lives

`build.py` holds the ONE place the real author identity is recorded in this repository, so that
camera-ready never means retyping it into `manuscript.tex` by hand (where it could drift from what
OpenReview has on file, or get left in by accident). Near the top of `build.py`:

```python
AUTHOR_NAME = "Wenyu Chiou"
AUTHOR_EMAIL = "wec324@lehigh.edu"
AUTHOR_AFFILIATION = "Lehigh University"

CAMERA_READY = False   # False = blind submission (default). True = camera-ready.
```

`CAMERA_READY` gates two things at once, both computed inside `_tex_preamble()`:

1. `\author{}` — emitted empty when `False`, emitted with the three constants above when `True`.
2. The style package's option list — `[dblblindworkshop]` when `False`, `[dblblindworkshop, final]`
   when `True`. `final` is what `neurips_2026.sty`'s `\if@neuripsfinal` / `\@trackname` machinery
   actually keys off to typeset the author block on the page, so `final` is the real de-anonymising
   switch — `\author{...}` alone with `final` absent would not surface on the compiled page, but
   leaving stale author content in the source is still a defect worth avoiding, hence gating both
   together from one flag.

**Checklist:**
- [ ] `CAMERA_READY = False` in `build.py` for every submission-stage build (confirmed 2026-08-03:
      the constant is `False` and the compiled `manuscript.tex` shows `\usepackage[dblblindworkshop]`
      and `\author{}` empty — see the Section 7 run log below).
- [ ] `AUTHOR_NAME` / `AUTHOR_EMAIL` / `AUTHOR_AFFILIATION` are correct NOW, even though they are
      inert while `CAMERA_READY` is `False` — confirm them once so camera-ready is a one-line flip,
      not a content edit made under acceptance-day time pressure.
- [ ] Flipping `CAMERA_READY` to `True` happens only after acceptance, as the LAST step, and the
      resulting `.tex`/`.pdf` is never what gets uploaded as (or mistaken for) the blind submission.
      `build.py`'s own run-summary print states which mode just built, in case of doubt.

---

## 6. Grep sweep — run before every submission-candidate PDF/tex is produced

From the repository root (`governed_broker_framework/`), against the paper source only:

```bash
# --- first-person self-citation patterns (Section 1 above) ---
grep -inE "our (previous|prior|companion|earlier) (work|paper|study|submission)|we (previously|earlier) (showed|found|reported|demonstrated)|in our (WRR|Nature Water|companion) (paper|manuscript)" \
  SUBMISSION_2026/TAE/paper/manuscript.md SUBMISSION_2026/TAE/paper/manuscript.tex

# --- identifying paths / URLs / institution / owner handle / author name+email (Section 2) ---
# "wec324" and "wenyu" also catch the AUTHOR_EMAIL / AUTHOR_NAME constants in build.py leaking
# into the body text by accident (they must appear ONLY inside build.py's CAMERA_READY block,
# never in manuscript.md/.tex -- see Section 5 above).
grep -inE "governed_broker_framework|Desktop.Lehigh|C:.Users.wenyu|github\.com/[A-Za-z0-9_-]+/governed|(^|[^A-Za-z])Lehigh([^A-Za-z]|$)|wec324|(^|[^A-Za-z])wenyu([^A-Za-z]|$)|Wenyu Chiou" \
  SUBMISSION_2026/TAE/paper/manuscript.md SUBMISSION_2026/TAE/paper/manuscript.tex SUBMISSION_2026/TAE/paper/manuscript.substituted.md

# --- acknowledgement / funding language (Section 3) ---
grep -inE "acknowledg|we thank|funded by|grant (no|number)|IRB protocol [A-Za-z0-9-]+" \
  SUBMISSION_2026/TAE/paper/manuscript.md SUBMISSION_2026/TAE/paper/manuscript.tex

# --- figure/table caption paths (figures are generated elsewhere in TAE/figures/) ---
grep -inE "C:.Users|/Users/[a-z]+/|Desktop" \
  SUBMISSION_2026/TAE/figures/*.csv
```

A clean sweep prints **nothing** from any of the four commands. Any hit is read and dispositioned by
hand — this grep is a net, not a verdict; a false positive (e.g. "our approach" describing the
method, not a citation) is expected and fine, a true positive is not.

**Known false-positive class:** "our approach" / "our claim" / "our data" describing *this* paper's
own method is normal academic voice and is not a double-blind violation — only sentences that
reference a *separate, identifiable prior work by the same authors* are. Read every grep hit in
context before acting on it.

---

## 7. Run log — what has actually been confirmed, and when

This section is a log, not a checklist: each entry records a real run of the checks above, on a
specific date, against specific files, with the actual result — so "was this ever checked" has an
answer instead of a hope. Add a new entry every time the sweep is run; do not overwrite old entries.

**2026-08-03 — full sweep, submission-stage build**

Context: `build.py`'s `CAMERA_READY` switch was added (Section 5) and the manuscript was rebuilt and
recompiled from a clean pipeline run (`make_bibliography.py` → `substitute.py` → `build.py` →
`pdflatex` ×2) immediately before this sweep, so the checks below ran against the exact files that
pipeline produced, not a stale artifact.

| Check | Command / method | Result |
|---|---|---|
| `manuscript.tex` line ~49 `\author{}` | `grep -n "author{" manuscript.tex` | Empty: `\author{}`, preceded by `\usepackage[dblblindworkshop]{neurips_2026}` |
| PDF metadata | `pypdf.PdfReader('manuscript.pdf').metadata` | `Author=''`, `Title=''`, `Creator='LaTeX with hyperref'`, `Producer='MiKTeX pdfTeX-1.40.28'` — no name, no path, no hostname |
| Figure PDF metadata (all 4: fig0_problem_schematic, fig1_rule_layers, fig2_mechanism, fig3_consequence) | `pypdf.PdfReader(f).metadata` per file | fig0 (pdflatex-produced): `Producer='MiKTeX pdfTeX-1.40.28'`, no `/Author`. fig1–3 (matplotlib-produced): `Creator='Matplotlib v3.10.7...'`, `Producer='Matplotlib pdf backend v3.10.7'`, no `/Author`, no path |
| Figure PNG metadata (fig0_problem_schematic, fig1_rule_layers, fig2_mechanism, fig3_consequence, fig0_generated) | raw PNG `tEXt`/`iTXt`/`zTXt` chunk scan (exiftool not on PATH on this machine) | fig1–3 carry one generic `tEXt` chunk each, `Software: Matplotlib version3.10.7, https://matplotlib.org/` — no path, no username. fig0_problem_schematic and fig0_generated carry no text chunks at all |
| Grep sweep, all 4 commands in Section 6 | run from repo root against `manuscript.md`, `manuscript.tex`, `manuscript.substituted.md`, and `figures/*.csv` | All four commands returned zero matches (including the extended pattern that also checks for `wec324`/`wenyu`/`Wenyu Chiou`) |
| First-person self-citation to the WRR/Nature Water predecessors (Section 1) | `grep -inE "WRR|Nature Water|companion|concurrent study|prior work" manuscript.md` | Zero matches — the current draft does not cite either predecessor yet, so there is nothing to disposition |
| Acknowledgements / funding | covered by the Section 6 grep | Zero matches |
| Build artifacts (`manuscript.log`, `.aux`, `.out`) | `grep -c wenyu manuscript.log manuscript.aux manuscript.out` | `manuscript.log` contains 63 hits (expected — pdflatex logs full local font/package paths on every run); `.aux`/`.out` are clean. **Not a leak**: the entire `SUBMISSION_2026/` tree is `.gitignore`d (confirmed via `git check-ignore`) and `.log`/`.aux` are build byproducts, never the file uploaded to OpenReview — but do not attach `manuscript.log` to a submission or a supplementary zip |
| DOCX metadata | not re-run this pass (the `.tex` → `pdflatex` route is what produces the actual submission PDF; `manuscript.docx` is the author's own read/comment copy) | **NOT checked 2026-08-03** — run the Section 4 DOCX snippet before `manuscript.docx` is ever shared outside this workspace |

**Not yet checked as of 2026-08-03** (carried forward, not silently dropped):
- DOCX core-properties author/last-modified-by (see row above).
- The final 28 Aug re-run required by Section 8 below — today's run satisfies "before this candidate
  leaves the folder," not the submission-day re-check.
- OpenReview web-form fields (title/abstract/TL;DR) — no submission form has been opened yet.

---

## 8. Final pre-submission pass (do again on 28 Aug, `PLAN.md` §3 Block "Submit")

- [ ] All of §1–§6 above re-run on the exact PDF/tex that will be uploaded, not an earlier draft, and
      logged as a new dated entry in §7.
- [ ] `\author{}` in `manuscript.tex` is empty (or contains only the venue's placeholder text, if any
      is required) and `build.py`'s `CAMERA_READY` is still `False`.
- [ ] `\usepackage[dblblindworkshop]{neurips_2026}` is present and unmodified (no `, final`).
- [ ] OpenReview submission form fields (title, abstract, "TL;DR" if present) independently re-read for
      the same violations — the checklist above covers the PDF, not the web form.
- [ ] `manuscript.docx` core-properties author/last-modified-by blanked if it will ever be shared
      outside this workspace (Section 4).
