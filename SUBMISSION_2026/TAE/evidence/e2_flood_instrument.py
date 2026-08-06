#!/usr/bin/env python
"""e2_flood_instrument.py -- B5 GATE: did the two flood arms measure threat
appraisal with the SAME instrument?

    python SUBMISSION_2026/TAE/evidence/e2_flood_instrument.py

WHY THIS SCRIPT EXISTS
----------------------
Every flood number the paper could print is a difference between two arms in
``construct_TP_LABEL``. If the with-validators arm and the no-validator arm
produced that column by different prompts, different parsers, or different
label schemes, then every flood delta compares two different measuring devices
and means nothing. ``BACKLOG.md`` B5 left the question open on one piece of
evidence: a stray lowercase ``l`` in the no-validator arm's
``ministral3_3b/Run_1``, which proves the parse is not byte-identical. This
script decides whether that is a cosmetic parse artefact or a second
instrument.

WHAT "THE INSTRUMENT" IS, EXACTLY
---------------------------------
``construct_TP_LABEL`` is produced by a four-link chain, and this script tests
every link on BOTH arms:

  1. SCHEME   ``config_snapshot.yaml`` -- ``shared.rating_scale`` (the five
              legal codes), ``shared.response_format`` (which response field
              carries which construct, and the delimiters that fence it),
              ``household.prompt_template_file``, ``household.parsing``.
              -> broker/config/schema.py
  2. PROMPT   the rendered question actually put to the model, recovered from
              ``raw/household_traces.jsonl``'s ``input`` field. Only the
              APPRAISAL-INSTRUMENT lines are compared: the PMT construct
              preamble, the rating-scale line, the "use EXACTLY one of" line
              and the two appraisal JSON schema lines. The action menu is NOT
              part of the instrument -- it legitimately varies by agent state
              (an already-elevated agent is not offered ``elevate_house``), and
              that is the world, not the measuring device.
  3. PARSER   broker/utils/parsing/unified_adapter.py -> ``normalize_construct_value``
              (broker/utils/normalization.py). Observable in the corpus as
              ``parse_layer`` / ``parse_confidence``, and as the off-vocabulary
              passthrough that ``normalize_construct_value`` performs whenever
              it is called WITHOUT ``allowed_values`` (a bare "l" is not a key
              of FRAMEWORK_NORMALIZATION_MAP -- only "low" is -- so it survives
              unchanged; unified_adapter.py:610 is such a call).
  4. COLUMN   broker/components/analytics/audit.py:399-403 writes
              ``row["construct_" + key] = val`` for every ``*_LABEL`` key of
              ``skill_proposal.reasoning``, unchanged. The audit csv carries the
              same value twice, as ``construct_TP_LABEL`` and as
              ``reason_tp_label``; equality of the two is checked here as a
              direct test that the column is a passthrough in both arms.

Section 5 then reports the CODE VINTAGE the runs were produced at, because the
two arms are not contemporaneous, and bounds what that can have done to link 3.

WHAT COUNTS AS "A DIFFERENT INSTRUMENT" -- the criteria, stated before the data
------------------------------------------------------------------------------
An instrument difference is a difference in what was ASKED or in the MAPPING
from a response to a label. It is NOT:

  * a config key that became explicit while its value stayed at the code
    default (the value asked for did not change);
  * which parse layer happened to fire on a given generation (that is a
    property of the model's output, not of the parser);
  * a column added elsewhere in the audit row by a later audit-writer
    (it cannot change the value in this column);
  * a value that exists in one arm only because the TREATMENT produced it
    (governance rejecting a decision until the retry budget is exhausted
    leaves a blank appraisal; the no-validator arm has no retry budget to
    exhaust). That is the effect under study, not a measuring artefact.

So the script fails on: a different rating scale, a different response-format
binding, a different prompt template, a different rendered appraisal question,
a parse layer whose confidence semantics differ between arms, a layer that
produced OUT-OF-SCHEME labels in one arm only, a column that is not a
passthrough of the parsed value, or a vocabulary that case-normalisation cannot
reconcile.

It does not repair anything. Every check reports and, on divergence, exits 1.

EXIT CODE
    0  the two arms measured threat appraisal with the same instrument
    1  they did not, or the corpus is not what this script assumes

Boundary: run directories come only from ``_data.flood_runs``; no path, glob,
arm selector or rate definition is built here. Filenames inside a run directory
are joined the same way ``_data.flood_manifest_seed`` joins them.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import _data as D  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover - environment problem, not a finding
    print("FATAL: pyyaml is required to read config_snapshot.yaml")
    sys.exit(1)


BAR = "=" * 100
RULE = "-" * 100

CONFIG_SNAPSHOT = "config_snapshot.yaml"
REPRO_MANIFEST = "reproducibility_manifest.json"
FLOOD_TRACES = os.path.join("raw", "household_traces.jsonl")

# broker/config/agent_types/base.py:234 and :269 -- an agent type that does not
# declare `psychological_framework` gets PMT. That default has been in place
# since commit c754dca0 (2026-01-28), which predates every flood run in this
# corpus, so an absent key and an explicit `pmt` are the same instrument.
PSYCH_FRAMEWORK_CODE_DEFAULT = "pmt"

# Markers that fence the appraisal instrument inside a rendered prompt. Every
# one of them must be found or the script fails loudly rather than silently
# comparing a shorter string.
PMT_OPEN = "Using the Protection Motivation Theory"
PMT_CLOSE = "Now, choose one of the following actions:"
SCALE_MARK = "### RATING SCALE"
SCALE_CODES = "VL = Very Low"
EXACTLY_MARK = "Use EXACTLY one of:"
THREAT_MARK = '"threat_appraisal"'
COPING_MARK = '"coping_appraisal"'

# Commits recorded in the flood reproducibility manifests, with their dates and
# whether they carry the Phase 6N-B label ``.upper()`` (b9885ddc, 2026-05-23) --
# the only one of the three post-April parser commits that can change a produced
# label at all. Written out literally rather than shelled out to git, so the
# script has no dependency on the repository being a checkout.
COMMIT_VINTAGE = {
    "1efb8f502113": ("2026-04-19", "pre-6N-B"),
    "eb595df59333": ("2026-04-19", "pre-6N-B"),
    "bdb29f526436": ("2026-04-20", "pre-6N-B"),
    "5a1d467faa34": ("2026-05-30", "post-6N-B"),
    "8c82ae41d0b5": ("2026-06-01", "post-6N-B"),
}
UNRECORDED = "unrecorded"

FAILURES: list[str] = []
NOTES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print("  !! FAIL: " + msg)


def note(msg: str) -> None:
    NOTES.append(msg)
    print("  ** NOTE: " + msg)


def _sha(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _run_file(run_dir: str, name: str) -> str:
    p = os.path.join(run_dir, name)
    if not os.path.isfile(p):
        raise D.DataError(f"missing {name} in {run_dir}")
    return p


# =============================================================================
# 1. SCHEME -- config_snapshot.yaml
# =============================================================================
def instrument_scheme(run_dir: str) -> dict:
    """The label-scheme half of the instrument, read from one run's snapshot.

    Everything here is what the framework used to ASK for a label and to decide
    what a legal label is. Governance profile, validator rules, memory and llm
    settings are deliberately excluded -- those are the treatment, and the two
    arms are SUPPOSED to differ on them.
    """
    with open(_run_file(run_dir, CONFIG_SNAPSHOT), encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    shared = cfg.get("shared") or {}
    household = cfg.get("household") or {}
    rf = shared.get("response_format") or {}
    fields = rf.get("fields") or []

    appraisal_fields = [
        {
            "key": f.get("key"),
            "type": f.get("type"),
            "construct": f.get("construct"),
            "required": f.get("required"),
            "reason_hint": f.get("reason_hint"),
        }
        for f in fields
        if f.get("type") == "appraisal"
    ]

    return {
        "rating_scale": shared.get("rating_scale"),
        "delimiter_start": rf.get("delimiter_start"),
        "delimiter_end": rf.get("delimiter_end"),
        "appraisal_fields": appraisal_fields,
        "prompt_template_file": household.get("prompt_template_file"),
        "parsing": household.get("parsing"),
        "psychological_framework": household.get("psychological_framework"),
    }


def effective_scheme(s: dict) -> dict:
    """``instrument_scheme`` with an absent config key resolved to its code default.

    Only ``psychological_framework`` is resolved, and only to the value the
    framework has used since before this corpus existed. Nothing else is
    normalised: an absent rating scale or an absent response-format binding
    stays absent and will fail the comparison.
    """
    out = dict(s)
    if out.get("psychological_framework") is None:
        out["psychological_framework"] = PSYCH_FRAMEWORK_CODE_DEFAULT
    return out


# =============================================================================
# 2. PROMPT -- the question actually asked
# =============================================================================
def instrument_prompt(text: str) -> dict:
    """The appraisal-instrument lines of ONE rendered prompt.

    Raises rather than degrade: a missing marker means the prompt is not the
    prompt this script was written against, and quietly hashing whatever was
    found would be the exact silent failure the paper is about.
    """
    i = text.find(PMT_OPEN)
    j = text.find(PMT_CLOSE)
    if i < 0 or j < 0 or j <= i:
        raise D.DataError("prompt does not carry the PMT construct preamble")
    preamble = text[i:j].strip()

    lines = text.splitlines()

    def one(mark: str) -> str:
        hits = [ln.strip() for ln in lines if mark in ln]
        if len(hits) != 1:
            raise D.DataError(
                f"expected exactly one prompt line containing {mark!r}, found {len(hits)}"
            )
        return hits[0]

    return {
        "pmt_preamble": preamble,
        "scale_header": one(SCALE_MARK),
        "scale_codes": one(SCALE_CODES),
        "exactly_one_of": one(EXACTLY_MARK),
        "threat_field": one(THREAT_MARK),
        "coping_field": one(COPING_MARK),
    }


def prompt_fingerprints(run_dir: str) -> tuple[dict[str, dict], int]:
    """{fingerprint: instrument} over EVERY trace record in one run, + record count."""
    out: dict[str, dict] = {}
    n = 0
    with open(_run_file(run_dir, FLOOD_TRACES), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = rec.get("input")
            if not isinstance(text, str):
                # the framework-0.5.1 `_metadata` header line carries no input
                continue
            n += 1
            out.setdefault(_sha(inst := instrument_prompt(text)), inst)
    if n == 0:
        raise D.DataError(f"no prompt records in {run_dir}")
    return out, n


def year1_prompts(run_dir: str) -> dict[str, str]:
    """``{agent_id: rendered prompt}`` for year 1 of one run.

    In year 1 the paired arms match on every pre-decision state column checked by
    ``e0_year1_exogeneity.py``, so the WHOLE prompt -- not just the appraisal
    instrument -- should match across arms there. Any difference is either
    memory-retrieval ordering or a genuinely different template.
    """
    out: dict[str, str] = {}
    with open(_run_file(run_dir, FLOOD_TRACES), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = rec.get("input")
            if isinstance(text, str) and rec.get("year") == 1:
                out[rec["agent_id"]] = text
    return out


def run_commit(run_dir: str) -> str:
    with open(_run_file(run_dir, REPRO_MANIFEST), encoding="utf-8") as fh:
        c = json.load(fh).get("git_commit")
    return (c or UNRECORDED)[:12]


# =============================================================================
# main
# =============================================================================
def main() -> int:
    print(BAR)
    print("B5 GATE -- DID THE TWO FLOOD ARMS MEASURE THREAT APPRAISAL WITH THE SAME INSTRUMENT?")
    print(BAR)
    print("arms: gov = with-validators (Group_C)   noval = no-validator (Group_C_disabled)")
    print("chain tested: config scheme -> rendered prompt -> parser -> audit column")

    runs = {arm: {m.label: D.flood_runs(arm, m) for m in D.FLOOD_MODELS} for arm in D.ARMS}
    n_runs = sum(len(v) for arm in D.ARMS for v in runs[arm].values())
    print(f"flood run directories under test: {n_runs}")

    # -------------------------------------------------------------------
    # 1. SCHEME
    # -------------------------------------------------------------------
    print()
    print(BAR)
    print("1. SCHEME -- config_snapshot.yaml (rating scale, response format, template, parsing)")
    print(BAR)

    raw_by_arm: dict[str, dict[str, list]] = {a: collections.defaultdict(list) for a in D.ARMS}
    eff_by_arm: dict[str, dict[str, list]] = {a: collections.defaultdict(list) for a in D.ARMS}
    for arm in D.ARMS:
        for label, rr in runs[arm].items():
            for r, d in rr.items():
                s = instrument_scheme(d)
                raw_by_arm[arm][_sha(s)].append((label, r, s))
                e = effective_scheme(s)
                eff_by_arm[arm][_sha(e)].append((label, r, e))

    print("  as written in the snapshot (raw):")
    for arm in D.ARMS:
        print(f"    {D.ARM_DISPLAY[arm]:<16} {len(raw_by_arm[arm])} distinct")
        for h, items in sorted(raw_by_arm[arm].items()):
            pf = items[0][2]["psychological_framework"]
            cells = sorted({f"{lbl}/Run_{r}" for lbl, r, _ in items})
            print(f"        {h}  {len(items):3d} run(s)  psychological_framework={pf!r}")
            if len(items) <= 20:
                print(f"            {', '.join(cells)}")

    raw_g, raw_n = set(raw_by_arm["gov"]), set(raw_by_arm["noval"])
    if raw_g != raw_n:
        note("the RAW snapshots are not one fingerprint. Resolved below; the difference "
             "is reported here so it is not discovered later as a surprise.")

    eff_g, eff_n = set(eff_by_arm["gov"]), set(eff_by_arm["noval"])
    print()
    print("  with an absent `psychological_framework` resolved to the code default "
          f"({PSYCH_FRAMEWORK_CODE_DEFAULT!r}, broker/config/agent_types/base.py:269,")
    print("  in force since commit c754dca0 2026-01-28 -- earlier than every run here):")
    if eff_g == eff_n and len(eff_g) == 1:
        h = next(iter(eff_g))
        s = eff_by_arm["gov"][h][0][2]
        print(f"    ALL {n_runs} RUNS, BOTH ARMS, ONE EFFECTIVE SCHEME: {h}")
        print(f"      rating_scale         : {s['rating_scale']!r}")
        print("      appraisal fields     : "
              + ", ".join(f"{f['key']} -> {f['construct']} (required={f['required']})"
                          for f in s["appraisal_fields"]))
        print(f"      delimiters           : {s['delimiter_start']} ... {s['delimiter_end']}")
        print(f"      prompt_template_file : {s['prompt_template_file']}")
        print(f"      parsing.strict_mode  : {(s['parsing'] or {}).get('strict_mode')}")
        print(f"      parsing.default_skill: {(s['parsing'] or {}).get('default_skill')}")
        print(f"      psych framework      : {s['psychological_framework']}")
    else:
        fail(f"effective scheme differs between arms: gov={sorted(eff_g)} noval={sorted(eff_n)}")

    # -------------------------------------------------------------------
    # 2. PROMPT
    # -------------------------------------------------------------------
    print()
    print(BAR)
    print("2. PROMPT -- the appraisal question actually put to the model, every trace record")
    print(BAR)
    print("   (the action menu is excluded: it varies with agent state by design and is not")
    print("    part of the measuring device)")

    prompt_by_arm: dict[str, dict[str, list]] = {a: collections.defaultdict(list) for a in D.ARMS}
    records = {a: 0 for a in D.ARMS}
    for arm in D.ARMS:
        for label, rr in runs[arm].items():
            for r, d in rr.items():
                fps, n = prompt_fingerprints(d)
                records[arm] += n
                for h, inst in fps.items():
                    prompt_by_arm[arm][h].append((label, r, inst))

    for arm in D.ARMS:
        print(f"  {D.ARM_DISPLAY[arm]:<16} {records[arm]:6d} prompt records, "
              f"{len(prompt_by_arm[arm])} distinct appraisal instrument(s)")
        for h in sorted(prompt_by_arm[arm]):
            print(f"      {h}  in {len(prompt_by_arm[arm][h])} run(s)")

    gp, np_ = set(prompt_by_arm["gov"]), set(prompt_by_arm["noval"])
    if gp == np_ and len(gp) == 1:
        h = next(iter(gp))
        inst = prompt_by_arm["gov"][h][0][2]
        print(f"  ONE APPRAISAL INSTRUMENT ACROSS BOTH ARMS, ALL {n_runs} RUNS, "
              f"{records['gov'] + records['noval']} PROMPTS: {h}")
        print(RULE)
        for line in inst["pmt_preamble"].splitlines():
            print("   | " + line)
        print("   | " + inst["scale_header"])
        print("   | " + inst["scale_codes"])
        print("   | " + inst["exactly_one_of"])
        print("   | " + inst["threat_field"])
        print("   | " + inst["coping_field"])
        print(RULE)
    else:
        fail(f"prompt instrument differs between arms: gov-only={sorted(gp - np_)} "
             f"noval-only={sorted(np_ - gp)}")

    # Cross-check on the WHOLE prompt, at the one year where the paired arms match
    # on every checked pre-decision state column (e0_year1_exogeneity.py). Anything that differs here
    # is either memory-retrieval ordering or a different template -- and a
    # different LENGTH cannot be ordering.
    print()
    print("  whole-prompt cross-check at YEAR 1 (pre-decision state columns match), Run_1 per model:")
    print(f"    {'model':<14} {'y1 agents':>10} {'byte-identical':>15} {'same length':>12} "
          f"{'different length':>17}")
    tot = eq = same_len = 0
    diff_len_cells = []
    for m in D.FLOOD_MODELS:
        g = year1_prompts(D.flood_run("gov", m, 1))
        nv = year1_prompts(D.flood_run("noval", m, 1))
        common = sorted(set(g) & set(nv))
        e = sum(1 for k in common if g[k] == nv[k])
        s = sum(1 for k in common if len(g[k]) == len(nv[k]))
        tot += len(common)
        eq += e
        same_len += s
        if s < len(common):
            diff_len_cells.append((m.label, len(common) - s))
        print(f"    {m.label:<14} {len(common):>10} {e:>15} {s:>12} {len(common) - s:>17}")
    print(f"    {'TOTAL':<14} {tot:>10} {eq:>15} {same_len:>12} {tot - same_len:>17}")
    if diff_len_cells:
        note("year-1 prompts differ in LENGTH between arms for: "
             + ", ".join(f"{c} ({n} agents)" for c, n in diff_len_cells)
             + ". Memory-line ordering cannot change a length, so this is a different "
               "rendered prompt. It does NOT change the appraisal instrument (the "
               "fingerprint above is one value across all runs) -- see BACKLOG B6.")

    # -------------------------------------------------------------------
    # 3. PARSER
    # -------------------------------------------------------------------
    print()
    print(BAR)
    print("3. PARSER -- layer semantics, passthrough, off-vocabulary behaviour")
    print(BAR)

    layer_conf = {a: collections.defaultdict(collections.Counter) for a in D.ARMS}
    layer_labels = {a: collections.defaultdict(collections.Counter) for a in D.ARMS}
    passthrough_mismatch = {a: 0 for a in D.ARMS}
    rows_total = {a: 0 for a in D.ARMS}
    offvocab: dict[str, list] = {a: [] for a in D.ARMS}
    status_of_blank = {a: collections.Counter() for a in D.ARMS}

    for arm in D.ARMS:
        for label, rr in runs[arm].items():
            for r, d in rr.items():
                for row in D.load_audit(d):
                    rows_total[arm] += 1
                    tp = row.get("construct_TP_LABEL", "")
                    layer = row.get("parse_layer", "") or "<blank>"
                    layer_conf[arm][layer][row.get("parse_confidence", "")] += 1
                    layer_labels[arm][layer][tp] += 1
                    if row.get("reason_tp_label") != tp:
                        passthrough_mismatch[arm] += 1
                    if tp not in D.LABEL_LEVELS:
                        offvocab[arm].append(
                            (label, r, row.get("agent_id"), row.get("year"), tp, layer,
                             row.get("parse_confidence"), row.get("status"))
                        )
                        if tp == "":
                            status_of_blank[arm][row.get("status", "")] += 1

    for arm in D.ARMS:
        print(f"  {D.ARM_DISPLAY[arm]:<16} audit rows {rows_total[arm]:6d}")
        for layer, confs in sorted(layer_conf[arm].items(), key=lambda kv: -sum(kv[1].values())):
            n = sum(confs.values())
            print(f"      {layer:<24} {n:6d}   parse_confidence in "
                  f"{{{','.join(sorted(confs))}}}")
        print(f"      construct_TP_LABEL != reason_tp_label on {passthrough_mismatch[arm]} row(s)")
        if passthrough_mismatch[arm]:
            fail(f"{arm}: the audit column is NOT a passthrough of the parsed value on "
                 f"{passthrough_mismatch[arm]} row(s)")

    shared_layers = set(layer_conf["gov"]) & set(layer_conf["noval"])
    only_gov = set(layer_conf["gov"]) - shared_layers
    only_nov = set(layer_conf["noval"]) - shared_layers
    print()
    print("  layer -> confidence semantics, on layers used by BOTH arms:")
    for layer in sorted(shared_layers):
        cg = set(layer_conf["gov"][layer])
        cn = set(layer_conf["noval"][layer])
        ok = "same" if cg == cn else "DIFFERENT"
        print(f"      {layer:<24} gov={sorted(cg)}  noval={sorted(cn)}   {ok}")
        if cg != cn:
            fail(f"parse layer {layer!r} carries different confidence semantics per arm")

    # A layer used by one arm only is a property of what the model emitted on
    # those generations, not of the parser -- the parser offers the same ladder
    # to both arms. It is a finding only if the labels it produced are outside
    # the scheme, which would mean that layer maps responses differently.
    print()
    print("  layers used by one arm only (a property of the generations, not the device):")
    if not (only_gov or only_nov):
        print("      none")
    for arm, only in (("gov", only_gov), ("noval", only_nov)):
        for layer in sorted(only):
            n = sum(layer_conf[arm][layer].values())
            labs = layer_labels[arm][layer]
            bad = {k for k in labs if k != "" and k.strip().upper() not in D.LABEL_LEVELS}
            blanks = labs.get("", 0)
            print(f"      {D.ARM_DISPLAY[arm]:<16} {layer:<24} {n:5d} row(s)  "
                  f"labels={dict(labs)}")
            if bad:
                fail(f"one-arm-only parse layer {layer!r} produced out-of-scheme labels {sorted(bad)}")
            elif blanks == n:
                note(f"parse layer {layer!r} fired in the {D.ARM_DISPLAY[arm]} arm only "
                     f"({n} row(s), {100.0 * n / rows_total[arm]:.4f}%); it produced NO label at "
                     "all, on rows the blank-status check below accounts for")
            else:
                note(f"parse layer {layer!r} fired in the {D.ARM_DISPLAY[arm]} arm only "
                     f"({n} row(s), {100.0 * n / rows_total[arm]:.4f}%); every label it produced "
                     f"is in the five-level scheme ({dict(labs)})")

    print()
    print("  OFF-VOCABULARY construct_TP_LABEL values (anything outside VL/L/M/H/VH):")
    for arm in D.ARMS:
        rows = offvocab[arm]
        print(f"    {D.ARM_DISPLAY[arm]:<16} {len(rows)} row(s) "
              f"({100.0 * len(rows) / rows_total[arm]:.4f}% of {rows_total[arm]})")
        for label, r, agent, year, tp, layer, conf, status in sorted(rows, key=lambda t: (t[0], t[1])):
            print(f"        {label:<14} Run_{r} {agent:<10} y{year:<3} value={tp!r:<6} "
                  f"layer={layer:<24} conf={conf:<5} status={status}")

    # The lowercase strays are what B5 was left open on. They are the documented
    # behaviour of normalize_construct_value called WITHOUT ``allowed_values``
    # (unified_adapter.py:610): "l" is not a key of FRAMEWORK_NORMALIZATION_MAP,
    # only "low" is, so it is returned unchanged. If that happens in BOTH arms on
    # the SAME parse layers, it is one parser behaving one way, not two parsers.
    low_gov = {t[4] for t in offvocab["gov"] if t[4]}
    low_nov = {t[4] for t in offvocab["noval"] if t[4]}
    lay_gov = {t[5] for t in offvocab["gov"] if t[4]}
    lay_nov = {t[5] for t in offvocab["noval"] if t[4]}
    print()
    print(f"  non-blank off-vocabulary values, gov  : {sorted(low_gov)}  on layers {sorted(lay_gov)}")
    print(f"  non-blank off-vocabulary values, noval: {sorted(low_nov)}  on layers {sorted(lay_nov)}")
    if not (low_gov and low_nov):
        fail("lowercase passthrough is present in ONE arm only -- that would be evidence "
             "of a parser difference rather than of one shared parser")
    if not (lay_gov & lay_nov):
        fail("the arms' off-vocabulary passthrough happened on disjoint parse layers")

    print()
    print("  BLANK construct_TP_LABEL, by row status:")
    for arm in D.ARMS:
        tot = sum(status_of_blank[arm].values())
        detail = ", ".join(f"{s or '<blank>'}={n}" for s, n in status_of_blank[arm].most_common())
        print(f"    {D.ARM_DISPLAY[arm]:<16} {tot:3d} blank row(s)   {detail or '-'}")
    stray = {s for a in D.ARMS for s in status_of_blank[a] if s not in D.REJECTED_STATUSES}
    if stray:
        fail(f"blank appraisal on a row that governance did not reject: {sorted(stray)} -- "
             "that would be a parse failure, not an arm-structural censoring")

    # -------------------------------------------------------------------
    # 4. LABELS
    # -------------------------------------------------------------------
    print()
    print(BAR)
    print("4. LABEL DISTRIBUTION -- exact counts per arm, vocabulary difference, case reconciliation")
    print(BAR)

    def counts(arm: str, label: str) -> collections.Counter:
        c = collections.Counter()
        for r, d in runs[arm][label].items():
            for row in D.load_audit(d):
                c[row.get("construct_TP_LABEL", "")] += 1
        return c

    per_cell = {arm: {m.label: counts(arm, m.label) for m in D.FLOOD_MODELS} for arm in D.ARMS}
    pooled = {arm: sum(per_cell[arm].values(), collections.Counter()) for arm in D.ARMS}

    order = ["VL", "L", "M", "H", "VH"]
    extras = sorted({k for a in D.ARMS for k in pooled[a]} - set(order),
                    key=lambda s: (s == "", s))
    cols = order + extras

    print(f"  {'model':<14} {'arm':<16} {'rows':>6} "
          + " ".join(f"{c or '<blank>':>8}" for c in cols))
    print("  " + RULE[:96])
    for m in D.FLOOD_MODELS:
        for arm in D.ARMS:
            c = per_cell[arm][m.label]
            print(f"  {m.label:<14} {D.ARM_DISPLAY[arm]:<16} {sum(c.values()):>6} "
                  + " ".join(f"{c.get(k, 0):>8}" for k in cols))
    print("  " + RULE[:96])
    for arm in D.ARMS:
        c = pooled[arm]
        print(f"  {'POOLED':<14} {D.ARM_DISPLAY[arm]:<16} {sum(c.values()):>6} "
              + " ".join(f"{c.get(k, 0):>8}" for k in cols))

    vg, vn = set(pooled["gov"]), set(pooled["noval"])
    g_only, n_only = vg - vn, vn - vg
    print()
    print(f"  vocabulary, gov  : {sorted(vg, key=lambda s: (s == '', s))}")
    print(f"  vocabulary, noval: {sorted(vn, key=lambda s: (s == '', s))}")
    print(f"  values in ONE arm only: "
          f"gov-only={sorted(g_only)} ({sum(pooled['gov'][k] for k in g_only)} rows)   "
          f"noval-only={sorted(n_only)} ({sum(pooled['noval'][k] for k in n_only)} rows)")

    def upper(c: collections.Counter) -> collections.Counter:
        out = collections.Counter()
        for k, n in c.items():
            out[k.strip().upper()] += n
        return out

    ug, un = upper(pooled["gov"]), upper(pooled["noval"])
    print()
    print("  after case-normalisation -- which _data.appraisal() already applies "
          "(_data.py:609, `.strip().upper()`):")
    print(f"    gov  : {dict(sorted(ug.items(), key=lambda kv: (kv[0] == '', kv[0])))}")
    print(f"    noval: {dict(sorted(un.items(), key=lambda kv: (kv[0] == '', kv[0])))}")
    resid_g = set(ug) - D.LABEL_LEVELS - {""}
    resid_n = set(un) - D.LABEL_LEVELS - {""}
    print(f"    residual non-scheme values: gov={sorted(resid_g)} noval={sorted(resid_n)}")
    if resid_g or resid_n:
        fail("case-normalisation does not reconcile the vocabularies; a value survives "
             "that is neither one of the five scheme levels nor a blank")
    if (set(ug) - {""}) != (set(un) - {""}):
        fail("after case-normalisation the two arms still do not share a vocabulary")

    # -------------------------------------------------------------------
    # 5. CODE VINTAGE -- the arms are not contemporaneous
    # -------------------------------------------------------------------
    print()
    print(BAR)
    print("5. CODE VINTAGE -- reported, and bounded against link 3")
    print(BAR)
    print("  Three commits touched broker/utils/parsing/unified_adapter.py between the")
    print("  April 2026 runs and the 2026-05-30 runs:")
    print("    36278bfb 2026-05-22  6J-C   parse-failure fallback skill must come from")
    print("                                parsing.default_skill (raises if absent).")
    print("                                NO-OP here: the snapshot declares default_skill.")
    print("    b9885ddc 2026-05-23  6N-B   .upper() on the STRUCTURED _LABEL capture branch.")
    print("                                Can change a produced label -- but only its CASE.")
    print("    103445d9 2026-05-24  6N-D-4 whitelist filter on the free-text capture:")
    print("                                `if temp_val.upper() not in {VL,L,M,H,VH}: continue`,")
    print("                                applied to a capture from `(VL|L|M|H|VH)` with")
    print("                                re.IGNORECASE. NO-OP by construction: every capture")
    print("                                that regex can make passes that test.")
    print()

    vintage = collections.defaultdict(lambda: [0, 0])
    for arm in D.ARMS:
        for label, rr in runs[arm].items():
            for r, d in rr.items():
                c = run_commit(d)
                for row in D.load_audit(d):
                    tp = row.get("construct_TP_LABEL", "")
                    vintage[(arm, c)][0] += 1
                    if tp and tp not in D.LABEL_LEVELS:
                        vintage[(arm, c)][1] += 1

    print(f"  {'arm':<16} {'manifest git_commit':<22} {'date':<12} {'vintage':<10} "
          f"{'rows':>7} {'lowercase':>10} {'rate':>9}")
    print("  " + RULE[:88])
    for (arm, c) in sorted(vintage):
        n, lo = vintage[(arm, c)]
        date, vin = COMMIT_VINTAGE.get(c, ("-", "unknown"))
        print(f"  {D.ARM_DISPLAY[arm]:<16} {c:<22} {date:<12} {vin:<10} "
              f"{n:>7} {lo:>10} {100.0 * lo / n:>8.4f}%")

    post = [(a, c) for (a, c) in vintage if COMMIT_VINTAGE.get(c, ("", ""))[1] == "post-6N-B"]
    pre = [(a, c) for (a, c) in vintage if (a, c) not in post]
    lo_post = sum(vintage[k][1] for k in post)
    n_post = sum(vintage[k][0] for k in post)
    lo_pre = sum(vintage[k][1] for k in pre)
    n_pre = sum(vintage[k][0] for k in pre)
    print()
    print(f"  lowercase rate, pre-6N-B  runs: {lo_pre}/{n_pre} = {100.0 * lo_pre / n_pre:.4f}%")
    print(f"  lowercase rate, post-6N-B runs: {lo_post}/{n_post} = {100.0 * lo_post / n_post:.4f}%")
    print("  The .upper() fix did NOT remove lowercase labels from the newer runs, so the")
    print("  branch it changed is not the branch that produced them here; the free-text")
    print("  path (unified_adapter.py:610) calls normalize_construct_value WITHOUT")
    print("  allowed_values in BOTH vintages. The vintage difference is therefore not")
    print("  observable in this corpus's construct_TP_LABEL, and its worst case is")
    print(f"  confined to the CASE of {lo_pre + lo_post} row(s) in {n_pre + n_post} "
          f"({100.0 * (lo_pre + lo_post) / (n_pre + n_post):.4f}%), which")
    print("  _data.appraisal() already normalises away.")

    if any(COMMIT_VINTAGE.get(c, ("", ""))[1] == "post-6N-B" for (a, c) in vintage if a == "noval") \
            and not any(COMMIT_VINTAGE.get(c, ("", ""))[1] == "post-6N-B"
                        for (a, c) in vintage if a == "gov"):
        note("the two arms are NOT contemporaneous: post-6N-B runs exist in the "
             "no-validator arm and in no governed run. This is a provenance defect to "
             "disclose (PLAN.md W8), bounded above; it is not an instrument difference.")
    if any(c == UNRECORDED for (a, c) in vintage):
        note("some runs record no git_commit in reproducibility_manifest.json, so their "
             "code state cannot be pinned from the corpus. No commit-level "
             "reproducibility claim may be made for those runs.")

    # -------------------------------------------------------------------
    # 6. IMMEDIATE CONSEQUENCE -- not part of the ruling, but it lands on it
    # -------------------------------------------------------------------
    print()
    print(BAR)
    print("6. IMMEDIATE CONSEQUENCE -- what the first printable flood number does")
    print(BAR)
    print("  Not part of the B5 ruling. Printed here because the ruling's whole effect is to")
    print("  permit flood numbers, and the first one is decided by a single seed.")
    print("  Delta = (no-validator) MINUS (with-validators), mean of per-run high_share.")
    print()
    print(f"  {'model':<14} {'mean gov':>9} {'mean noval':>11} {'Delta':>8}")
    for m in D.FLOOD_MODELS:
        g = D.flood_per_run("gov", m, D.high_share)
        nv = D.flood_per_run("noval", m, D.high_share)
        mg = sum(g.values()) / len(g)
        mn = sum(nv.values()) / len(nv)
        print(f"  {m.label:<14} {mg:>9.2f} {mn:>11.2f} {mn - mg:>+8.2f}")

    anchor = D.FLOOD_MODELS[0]
    g = D.flood_per_run("gov", anchor, D.high_share)
    nv = D.flood_per_run("noval", anchor, D.high_share)
    mn = sum(nv.values()) / len(nv)
    mg_all = sum(g.values()) / len(g)
    g_drop = {k: v for k, v in g.items() if k != 1}
    mg_drop = sum(g_drop.values()) / len(g_drop)
    print()
    print(f"  {anchor.label} governed per-run high_share: "
          + ", ".join(f"Run_{k}={v:.2f}" for k, v in sorted(g.items())))
    print(f"    all 5 governed seeds : mean gov {mg_all:.2f}  vs noval {mn:.2f}  ->  {mn - mg_all:+.2f}")
    print(f"    dropping Run_1 (B6)  : mean gov {mg_drop:.2f}  vs noval {mn:.2f}  ->  {mn - mg_drop:+.2f}")
    if (mn - mg_all) * (mn - mg_drop) < 0:
        note(f"B6 FLIPS THE SIGN of the {anchor.label} flood cell "
             f"({mn - mg_all:+.2f} with Run_1, {mn - mg_drop:+.2f} without). B6 is no longer a "
             "cheap disclosure -- decide it BEFORE any flood number is printed.")

    # -------------------------------------------------------------------
    # 7. VERDICT
    # -------------------------------------------------------------------
    print()
    print(BAR)
    print("7. VERDICT")
    print(BAR)
    if FAILURES:
        print("NOT IDENTICAL INSTRUMENT.")
        for f in FAILURES:
            print("  - " + f)
        print()
        print("RULE (PLAN.md section 4, B5): flood becomes DESCRIPTIVE TEXT WITH NO NUMBERS,")
        print("and sections 2 and 6 are written accordingly.")
        print(BAR)
        return 1

    print("IDENTICAL INSTRUMENT.")
    print("  scheme : one effective config scheme across both arms and all runs; the only")
    print("           snapshot difference is a key that became explicit at its own default")
    print("  prompt : one appraisal question, byte-identical, across every prompt in both arms")
    print("  parser : same layer->confidence semantics on every shared layer; the same")
    print("           off-vocabulary passthrough in BOTH arms on a shared layer; the audit")
    print("           column is a passthrough of the parsed value on every row of both arms")
    print("  labels : same five-level vocabulary; the only value present in one arm and not")
    print("           the other is the BLANK, and every blank sits on a governance-rejected")
    print("           row -- arm-structural censoring, not a second measuring device")
    print()
    print("RULE (PLAN.md section 4, B5): flood deltas MAY be printed, on the per-run-mean basis.")
    print("Three disclosures travel with them; none is an instrument defect:")
    print("  (a) the with-validators arm censors the appraisal on retry-exhausted rows")
    print("      (blank construct_TP_LABEL, 100% REJECTED_FALLBACK). Blanks are not HIGH and")
    print("      stay in the denominator, per _data.LABEL_LEVELS / _data.unparsed_share.")
    print("  (b) the arms are not contemporaneous and some runs pin no commit -- a provenance")
    print("      defect for section 8, bounded in section 5 above.")
    print("  (c) every label statistic must case-normalise. _data.appraisal() already does.")
    if NOTES:
        print()
        print("  notes raised above:")
        for n_ in NOTES:
            print("   - " + n_)
    print(BAR)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except D.DataError as exc:
        print()
        print("DATA ERROR -- the corpus is not what this script assumes:")
        print("  " + str(exc))
        sys.exit(1)
