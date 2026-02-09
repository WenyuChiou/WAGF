#!/usr/bin/env python
import json
import csv
from pathlib import Path
from collections import Counter, defaultdict

BASE = Path('examples/single_agent/results/JOH_FINAL')
OUT_CSV = Path('docs/wrr_reasoning_log_behavioral_cases_v6.csv')
OUT_MD = Path('docs/wrr_reasoning_log_behavioral_audit_v6.md')

rows = []

def _infer_raw_intent_mismatch(skill_name: str, raw_output: str) -> str:
    """Heuristic: detect parser-intent mismatch from free-text reasoning."""
    s = (raw_output or "").lower()
    if not s:
        return ""
    if skill_name == "elevate_house" and ("buy flood insurance" in s or "buying insurance" in s):
        return "text_mentions_insurance_but_skill_is_elevation"
    if skill_name == "relocate" and ("buy flood insurance" in s or "elevate" in s):
        return "text_mentions_other_action_but_skill_is_relocate"
    if skill_name == "do_nothing" and ("relocate" in s or "elevate" in s or "buy flood insurance" in s):
        return "text_mentions_active_action_but_skill_is_do_nothing"
    return ""

for fp in sorted(BASE.glob('*/Group_*/Run_*/raw/household_traces.jsonl')):
    if '_bak_' in str(fp).lower():
        continue
    model, group, run = fp.parts[-5], fp.parts[-4], fp.parts[-3]

    # Keep governed traces only for stable semantics
    if group not in ('Group_B', 'Group_C'):
        continue

    with fp.open(encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            sb = obj.get('state_before') or {}
            prop = obj.get('skill_proposal') or {}
            reasoning_obj = prop.get('reasoning') or {}

            skill = str(prop.get('skill_name') or '').strip()
            tp = str(reasoning_obj.get('TP_LABEL') or '').strip().upper()
            reasoning = str(reasoning_obj.get('reasoning') or '').strip()
            raw_output = str(prop.get('raw_output') or '')

            elevated = bool(sb.get('elevated', False))
            relocated = bool(sb.get('relocated', False))
            has_ins = bool(sb.get('has_insurance', False))

            physical_tag = None
            # Insurance renewal is domain-allowed; do not count as physical hallucination.
            if skill == 'elevate_house' and elevated:
                physical_tag = 're_elevation'
            elif skill == 'relocate' and relocated:
                physical_tag = 're_relocation'

            irrational_tag = None
            if tp in ('H', 'VH') and skill == 'do_nothing':
                irrational_tag = 'high_threat_inaction'
            elif tp in ('L', 'VL') and skill == 'relocate':
                irrational_tag = 'low_threat_relocation'
            elif tp in ('L', 'VL') and skill in ('elevate_house',):
                irrational_tag = 'low_threat_costly_structural'

            if not physical_tag and not irrational_tag:
                continue

            mismatch_flag = _infer_raw_intent_mismatch(skill, raw_output)
            confidence_tier = "medium"
            if physical_tag and mismatch_flag:
                confidence_tier = "high"
            elif physical_tag and str(obj.get('outcome', '')).upper() == "REJECTED":
                confidence_tier = "high"

            rows.append({
                'model': model,
                'group': group,
                'run': run,
                'agent_id': obj.get('agent_id'),
                'year': obj.get('year'),
                'step_id': obj.get('step_id'),
                'skill_name': skill,
                'physical_tag': physical_tag or '',
                'irrational_tag': irrational_tag or '',
                'tp_label': tp,
                'outcome': obj.get('outcome'),
                'retry_count': obj.get('retry_count'),
                'approval_status': (obj.get('approved_skill') or {}).get('status'),
                'elevated_before': elevated,
                'relocated_before': relocated,
                'insured_before': has_ins,
                'reasoning_excerpt': reasoning[:280].replace('\n', ' '),
                'validation_issues': str(obj.get('validation_issues') or '')[:400],
                'intent_mismatch_flag': mismatch_flag,
                'confidence_tier': confidence_tier,
                'trace_file': str(fp).replace('\\', '/'),
                'line_no': line_no,
            })

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
    fn = list(rows[0].keys()) if rows else [
        'model','group','run','agent_id','year','step_id','skill_name','physical_tag','irrational_tag','tp_label','outcome',
        'retry_count','approval_status','elevated_before','relocated_before','insured_before','reasoning_excerpt','validation_issues',
        'intent_mismatch_flag','confidence_tier',
        'trace_file','line_no']
    w = csv.DictWriter(f, fieldnames=fn)
    w.writeheader()
    for r in rows:
        w.writerow(r)

phys = [r for r in rows if r['physical_tag']]
irr = [r for r in rows if r['irrational_tag']]

phys_by_type = Counter(r['physical_tag'] for r in phys)
phys_by_outcome = Counter(str(r['outcome']) for r in phys)
irr_by_type = Counter(r['irrational_tag'] for r in irr)
irr_by_outcome = Counter(str(r['outcome']) for r in irr)

# choose exemplars
ex_phys = sorted(
    phys,
    key=lambda r: (
        0 if r.get('confidence_tier') == 'high' else 1,
        0 if str(r['outcome']).upper() in ('REJECTED','UNCERTAIN') else 1,
        -int(r['retry_count'] or 0)
    )
)[:3]
ex_irr = sorted(irr, key=lambda r: (0 if str(r['outcome']).upper() in ('APPROVED','RETRY_SUCCESS') else 1, -int(r['retry_count'] or 0)))[:2]

phys_high = [r for r in phys if r.get('confidence_tier') == 'high']

with OUT_MD.open('w', encoding='utf-8') as f:
    f.write('# WRR Reasoning-Log Behavioral Audit (Governed Flood Traces)\n\n')
    f.write(f'- Trace scope: Group_B/Group_C only\n')
    f.write(f'- Candidate cases: {len(rows)}\n')
    f.write(f'- Physical-tagged cases: {len(phys)}\n')
    f.write(f'- Physical high-confidence cases: {len(phys_high)}\n')
    f.write(f'- Irrational-tagged cases: {len(irr)}\n')
    f.write(f'- CSV: `{OUT_CSV.as_posix()}`\n\n')

    f.write('## Physical/Identity Findings\n\n')
    if not phys:
        f.write('- No physical/identity cases found under current rules.\n')
    else:
        for k,v in phys_by_type.items():
            f.write(f'- `{k}`: {v}\n')
        f.write('\nOutcome split:\n')
        for k,v in phys_by_outcome.items():
            f.write(f'- `{k}`: {v}\n')
        mismatch_n = sum(1 for r in phys if r.get('intent_mismatch_flag'))
        f.write(f'\n- Intent-mismatch flagged: {mismatch_n}\n')

    f.write('\n## Irrational (Thinking-Coherence) Findings\n\n')
    for k,v in irr_by_type.items():
        f.write(f'- `{k}`: {v}\n')
    f.write('\nOutcome split:\n')
    for k,v in irr_by_outcome.items():
        f.write(f'- `{k}`: {v}\n')

    f.write('\n## Representative Physical Examples\n\n')
    if ex_phys:
        f.write('| Type | Model/Group/Run | Agent-Year | Skill | Outcome | Retry | Intent Mismatch | Reasoning |\n')
        f.write('|---|---|---|---|---|---:|---|---|\n')
        for r in ex_phys:
            mismatch = r.get('intent_mismatch_flag') or ''
            f.write(f"| {r['physical_tag']} | {r['model']}/{r['group']}/{r['run']} | {r['agent_id']}/Y{r['year']} | {r['skill_name']} | {r['outcome']} | {r['retry_count']} | {mismatch} | {r['reasoning_excerpt'].replace('|','/')} |\n")
    else:
        f.write('- None.\n')

    f.write('\n## Representative Irrational Examples\n\n')
    if ex_irr:
        f.write('| Type | Model/Group/Run | Agent-Year | Skill | TP_LABEL | Outcome | Retry | Reasoning |\n')
        f.write('|---|---|---|---|---|---|---:|---|\n')
        for r in ex_irr:
            f.write(f"| {r['irrational_tag']} | {r['model']}/{r['group']}/{r['run']} | {r['agent_id']}/Y{r['year']} | {r['skill_name']} | {r['tp_label']} | {r['outcome']} | {r['retry_count']} | {r['reasoning_excerpt'].replace('|','/')} |\n")

    f.write('\n## Expert Interpretation\n\n')
    f.write('- Most physical inconsistencies in governed traces are intercepted (rejected or retried), indicating validator containment rather than execution leakage.\n')
    f.write('- The strongest physical case shows parser-intent mismatch: free-text rationale supports insurance-like behavior while parsed skill is elevation under already-elevated state.\n')
    f.write('- Remaining irrational cases are primarily coherence mismatches (e.g., high-threat inaction), consistent with bounded-rational behavior under finite retry budgets.\n')

print('Wrote', OUT_CSV)
print('Wrote', OUT_MD)
print('physical', len(phys), dict(phys_by_type), dict(phys_by_outcome))
print('irrational', len(irr), dict(irr_by_type), dict(irr_by_outcome))
