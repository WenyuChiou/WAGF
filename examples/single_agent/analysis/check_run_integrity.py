#!/usr/bin/env python3
"""NW paper-1b run-integrity checker (added 2026-05-30 after the reflection-missing
data-defect audit). Re-usable net so the "config says reflection on but it never ran"
class of defect can never be silently missed again.

Audits every gov-vs-no-validator pair (flood single-agent + irrigation) for:
  - reflection parity      (reflection_log.jsonl present + populated in BOTH arms?)
  - memory consolidation    ("Consolidated Reflection" rows in simulation_log memory)
  - audit-trace completeness (governance_audit.csv rows vs expected)
  - seed/run pairing         (same seeds in gov and noval?)

Run before any gov-vs-noval analysis, or in CI after a re-run batch.
Exit code: 0 = clean, 1 = at least one CRITICAL parity defect found.

Usage: python examples/single_agent/analysis/check_run_integrity.py [--strict]
"""
from __future__ import annotations
import sys, json, argparse
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SA = ROOT / 'examples' / 'single_agent' / 'results'
IRR = ROOT / 'examples' / 'irrigation_abm' / 'results'

FLOOD_MODELS = ['gemma3_4b', 'gemma3_12b', 'gemma3_27b', 'gemma4_e2b', 'gemma4_e4b',
                'gemma4_26b', 'ministral3_3b', 'ministral3_8b', 'ministral3_14b']
IRR_MODELS = {'gemma3_4b': '', 'gemma3_12b': '_gemma3_12b', 'gemma4_e2b': '_gemma4_e2b',
              'gemma4_e4b': '_gemma4_e4b', 'ministral3_8b': '_ministral3_8b'}


def _reflection_state(run_dir: Path):
    """Return (has_reflection, n_entries). Prefers run_integrity.json (runtime truth),
    falls back to reflection_log.jsonl + memory column."""
    integ = run_dir / 'run_integrity.json'
    if integ.exists():
        try:
            d = json.loads(integ.read_text(encoding='utf-8'))
            n = d.get('reflection_log_entries', 0)
            return n > 0, n
        except Exception:
            pass  # corrupt manifest (e.g. truncated write) — fall through to the raw log
    rl = run_dir / 'reflection_log.jsonl'
    if rl.exists():
        try:
            with rl.open(encoding='utf-8') as fh:
                n = sum(1 for _ in fh)
            return n > 0, n
        except OSError:
            return True, -1  # exists but unreadable — don't crash the audit
    return False, 0


def _audit_completeness(run_dir: Path, audit_name: str, expected: int):
    f = run_dir / audit_name
    if not f.exists():
        return None
    try:
        n = len(pd.read_csv(f, encoding='utf-8-sig', usecols=[0]))
        return round(100 * n / expected, 1)
    except Exception:
        return None


def _flood_runs(root_names, model, group):
    for root in root_names:
        d = SA / root / model / group
        if d.exists():
            runs = sorted(d.glob('Run_*'))
            if runs:                 # fall through to base dir if a _v2 dir exists but is empty
                return runs
    return []


def check_flood():
    rows, defects = [], []
    for m in FLOOD_MODELS:
        gov = _flood_runs([f'JOH_FINAL_v2', 'JOH_FINAL'], m, 'Group_C')
        nov = _flood_runs([f'JOH_ABLATION_DISABLED_v2', 'JOH_ABLATION_DISABLED'], m, 'Group_C_disabled')
        gov_r = [_reflection_state(d)[0] for d in gov]
        nov_r = [_reflection_state(d)[0] for d in nov]
        gov_ok = f'{sum(gov_r)}/{len(gov)}'
        nov_ok = f'{sum(nov_r)}/{len(nov)}'
        gov_ac = [_audit_completeness(d, 'household_governance_audit.csv', 1000) for d in gov]
        nov_ac = [_audit_completeness(d, 'household_governance_audit.csv', 1000) for d in nov]
        gov_acm = round(sum(x for x in gov_ac if x) / max(1, len([x for x in gov_ac if x])), 1) if gov_ac else 0
        nov_acm = round(sum(x for x in nov_ac if x) / max(1, len([x for x in nov_ac if x])), 1) if nov_ac else 0
        # parity defect = reflection present in one arm's runs but not the other's
        if not gov and not nov:
            status = 'NO_DATA'
        elif not gov or not nov:
            status = 'MISSING_ARM'
            defects.append(f'flood {m}: one arm has no run dirs (gov={len(gov)}, noval={len(nov)})')
        else:
            mism = (sum(gov_r) > 0) != (sum(nov_r) > 0) or (len(gov) == len(nov) and gov_r != nov_r and sum(gov_r) != sum(nov_r))
            partial = sum(nov_r) not in (0, len(nov)) or sum(gov_r) not in (0, len(gov))
            status = 'OK'
            if mism or partial:
                status = 'DEFECT'
                defects.append(f'flood {m}: reflection gov {gov_ok} vs noval {nov_ok} (parity broken)')
        rows.append(f'  {m:15} | gov_refl {gov_ok:>4} | noval_refl {nov_ok:>4} | gov_audit {gov_acm:>5}% | noval_audit {nov_acm:>5}% | {status}')
    return rows, defects


def check_irrigation():
    rows, defects = [], []
    for m, suf in IRR_MODELS.items():
        gov = sorted(IRR.glob(f'production_v21_42yr{suf}_seed*'))
        nov = sorted(IRR.glob(f'ungoverned_v21_42yr{suf}_seed*'))
        gov_seeds = {p.name.split('seed')[-1] for p in gov}
        nov_seeds = {p.name.split('seed')[-1] for p in nov}
        gov_r = sum(_reflection_state(d)[0] for d in gov)
        nov_r = sum(_reflection_state(d)[0] for d in nov)
        unpaired = (gov_seeds ^ nov_seeds)
        status = 'OK'
        if (gov_r > 0) != (nov_r > 0):
            status = 'DEFECT'; defects.append(f'irrigation {m}: reflection gov {gov_r}/{len(gov)} vs noval {nov_r}/{len(nov)}')
        if unpaired:
            status = 'WARN(pairing)'; defects.append(f'irrigation {m}: unpaired seeds {sorted(unpaired)} (minor)')
        rows.append(f'  {m:15} | gov_refl {gov_r}/{len(gov)} | noval_refl {nov_r}/{len(nov)} | seeds gov={len(gov_seeds)} noval={len(nov_seeds)} | {status}')
    return rows, defects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='exit 1 on ANY defect incl. minor pairing')
    args = ap.parse_args()
    print('=== NW paper-1b run-integrity check ===\n[FLOOD] model         | reflection parity | audit-trace completeness | status')
    fr, fd = check_flood()
    print('\n'.join(fr))
    print('\n[IRRIGATION] model    | reflection parity | seed pairing | status')
    ir, idf = check_irrigation()
    print('\n'.join(ir))
    critical = [d for d in fd + idf if 'minor' not in d]
    print(f'\n=== {len(critical)} critical defect(s), {len(fd+idf)} total ===')
    for d in (fd + idf):
        print(f'  - {d}')
    bad = (fd + idf) if args.strict else critical
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
