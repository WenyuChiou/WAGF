"""R6 -- how much of the corpus was decided by a fallback parsing layer.

WHAT IT ANSWERS
  "Your agents emit free text. How often did your parser fail to read a proper
   answer and fall back to grabbing a digit or a keyword? Those rows are not model
   decisions, they are parser decisions."

COLUMNS -- these DO exist in the released corpora, so this table is AVAILABLE
  parse_layer        e.g. "enclosure+json", "enclosure+json+digit",
                     "enclosure+keyword", "enclosure+json+keyword", "" (blank)
  parse_confidence   0.95 for a clean structured parse, 0.7 for a keyword rescue,
                     0.0 for a blank layer.
  (`base_layer` does NOT exist in either corpus; that column is reported absent.)

CLASSIFICATION -- stated so it can be disputed rather than guessed at
  clean_structured  parse_layer contains "json" and contains neither "digit" nor
                    "keyword". The model produced a parseable structured answer.
  digit_fallback    parse_layer contains "digit".
  keyword_fallback  parse_layer contains "keyword" (and no "digit").
  blank             parse_layer empty -- no layer succeeded at all. In the
                    irrigation corpus every blank row also carries status
                    REJECTED_FALLBACK.
  fallback_share_pct = digit + keyword + blank, as a share of all rows. This is the
  number a reviewer is asking for.

TWO CORPORA, DIFFERENT PROVENANCE -- never pooled
  released    examples/irrigation_abm/results (gemma3:4b v21) and
              examples/single_agent/results (flood gemma3_4b). Paper data.
  TAE         SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42..46.
              *** UNRELEASED, provenance RED, disclosure only. *** These runs carry
              the extra P0-1a first-attempt columns and are not part of any
              published corpus. The known figure for seed 42 is 10.47 %; this script
              recomputes it rather than quoting it.

OUTPUT
  out/r6_parser_layer_share.csv

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r6_parser_layer_share.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

TAE_RUNS = os.path.join(C.SUB, "TAE", "runs")
FLOOD_MODEL = "gemma3_4b"
FLOOD_ARMS = {
    "governed": ("JOH_FINAL", "Group_C"),
    "ungoverned": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}


def classify(layer: str) -> str:
    s = (layer or "").strip().lower()
    if not s:
        return "blank"
    if "digit" in s:
        return "digit_fallback"
    if "keyword" in s:
        return "keyword_fallback"
    if "json" in s:
        return "clean_structured"
    return "other"


def _measure(corpus, provenance, domain, arm, seed, aud):
    if "parse_layer" not in aud[0]:
        raise PrepError(f"{corpus}/{arm}/{seed}: no parse_layer column")
    n = len(aud)
    buckets = {}
    layers = {}
    conf = []
    for r in aud:
        lay = (r.get("parse_layer") or "").strip()
        buckets[classify(lay)] = buckets.get(classify(lay), 0) + 1
        layers[lay or "<blank>"] = layers.get(lay or "<blank>", 0) + 1
        v = (r.get("parse_confidence") or "").strip()
        if v:
            conf.append(float(v))
    fb = buckets.get("digit_fallback", 0) + buckets.get("keyword_fallback", 0) \
        + buckets.get("blank", 0)
    return {
        "corpus": corpus, "provenance": provenance, "domain": domain,
        "arm": arm, "seed": seed, "n_rows": n,
        "has_base_layer_col": "base_layer" in aud[0],
        "n_clean_structured": buckets.get("clean_structured", 0),
        "n_digit_fallback": buckets.get("digit_fallback", 0),
        "n_keyword_fallback": buckets.get("keyword_fallback", 0),
        "n_blank_layer": buckets.get("blank", 0),
        "n_other_layer": buckets.get("other", 0),
        # the exact layer string the 10.47 % figure on record counts, isolated so the
        # two numbers can be reconciled instead of argued about
        "n_layer_enclosure_json_digit": layers.get("enclosure+json+digit", 0),
        "share_layer_enclosure_json_digit_pct":
            100.0 * layers.get("enclosure+json+digit", 0) / n,
        "fallback_share_pct": 100.0 * fb / n,
        "mean_parse_confidence": C.mean(conf) if conf else float("nan"),
        "distinct_parse_layers": " | ".join(f"{k}={v}" for k, v in sorted(layers.items())),
    }


def main() -> int:
    C.banner("R6  parser-layer share")
    rows = []

    print("  released irrigation (gemma3:4b v21)")
    for arm in ("governed", "ungoverned"):
        for s in L.paired_seeds(""):
            rows.append(_measure("released", "GREEN (paper corpus)", "irrigation",
                                 arm, s, L.load_audit(L.run_dir(arm, "", s))))

    print("  released flood (gemma3_4b single-agent)")
    for arm, (root, group) in FLOOD_ARMS.items():
        for run, (seed, rd) in C.flood_runs(root, FLOOD_MODEL, group).items():
            rows.append(_measure("released", "GREEN (paper corpus)", "flood", arm,
                                 f"{seed}({run})",
                                 C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))))

    print("  TAE firstattempt_gov (UNRELEASED, provenance RED, disclosure only)")
    if not os.path.isdir(TAE_RUNS):
        raise PrepError(f"missing {TAE_RUNS}")
    tae = sorted(d for d in os.listdir(TAE_RUNS) if d.startswith("firstattempt_gov_seed"))
    if not tae:
        raise PrepError(f"no firstattempt_gov_seed* dirs under {TAE_RUNS}")
    for d in tae:
        p = os.path.join(TAE_RUNS, d, "irrigation_farmer_governance_audit.csv")
        rows.append(_measure("TAE_firstattempt", "RED (unreleased, disclosure only)",
                             "irrigation", "governed", d.split("seed")[-1],
                             C.read_csv(p)))

    C.write_csv(
        "r6_parser_layer_share.csv",
        ["corpus", "provenance", "domain", "arm", "seed", "n_rows",
         "has_base_layer_col", "n_clean_structured", "n_digit_fallback",
         "n_keyword_fallback", "n_blank_layer", "n_other_layer",
         "n_layer_enclosure_json_digit", "share_layer_enclosure_json_digit_pct",
         "fallback_share_pct", "mean_parse_confidence", "distinct_parse_layers"],
        rows)

    print(f"\n  {'corpus':17s} {'domain':11s} {'arm':11s} {'seeds':>5s} "
          f"{'fallback share % (mean +/- sd)':>32s}")
    groups = {}
    for r in rows:
        groups.setdefault((r["corpus"], r["domain"], r["arm"]), []).append(
            r["fallback_share_pct"])
    for k, v in sorted(groups.items()):
        print(f"  {k[0]:17s} {k[1]:11s} {k[2]:11s} {len(v):>5d} "
              f"{C.mean(v):22.2f} +/- {C.sd(v):5.2f}")
    s42 = [r for r in rows if r["corpus"] == "TAE_firstattempt" and r["seed"] == "42"]
    if s42:
        r = s42[0]
        print("\n  TAE seed 42 -- reconciliation with the 10.47 % figure on record:")
        print(f"    layer `enclosure+json+digit` alone           "
              f"{r['share_layer_enclosure_json_digit_pct']:6.2f} %  <- this IS the 10.47 %")
        print(f"    every digit layer                           "
              f"{100.0 * r['n_digit_fallback'] / r['n_rows']:6.2f} %")
        print(f"    every non-clean layer (digit+keyword+blank)  "
              f"{r['fallback_share_pct']:6.2f} %  <- the honest reviewer-facing number")
    print("\n  `base_layer` column present anywhere: "
          f"{any(r['has_base_layer_col'] for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
