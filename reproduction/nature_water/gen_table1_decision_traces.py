#!/usr/bin/env python3
"""Main-text Table 1: two single-agent traces (one irrigation, one flood) in the
WITH-VALIDATORS condition, EXECUTED final actions. Each trace shows the recalled
memory accumulating explicit evidence that the action fails, the validators
rejecting every year (3 retries), and the agent re-proposing the same
appraisal-contradicting action, which executes. Quotes are verbatim sentences."""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import re, pandas as pd
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL

SA = Path('examples/single_agent/results'); IRR = Path('examples/irrigation_abm/results')
DEC = {'do_nothing':'Do nothing','buy_insurance':'Buy insurance','elevate_house':'Elevate house',
       'relocate':'Relocate','relocated':'Relocated','increase_large':'Increase (large)',
       'increase_small':'Increase (small)','maintain_demand':'Maintain',
       'decrease_small':'Decrease (small)','decrease_large':'Decrease (large)'}
RULEMAP = {'high_threat_high_cope_no_increase':'WSA-ACA coherence (V12)','curtailment_awareness':'curtailment (V9)',
           'demand_ceiling_stabilizer':'demand ceiling (V5)','extreme_threat_block':'extreme-threat block (V13)',
           'elevation_block':'re-elevation block','supply_gap_block':'supply gap (V8)'}
TIER={'VL':'very low','L':'low','M':'medium','H':'high','VH':'very high'}

def collapse(x): return re.sub(r'\s+',' ',str(x)).strip()
def clean_rules(s):
    parts=[p.strip() for p in str(s).split('|') if p.strip() and p.strip().lower() not in ('nan','unknown')]
    return ', '.join(RULEMAP.get(p,p) for p in parts) or '(none)'
def expected(domain, prim):
    if domain=='irrig':
        return 'conserve (maintain or decrease)' if prim in ('H','VH') else 'no strong expectation'
    return 'protect (insure / elevate / relocate)' if prim in ('H','VH') else 'no costly action'
def keyquote(full, key, n=230):
    full=collapse(full); i=full.lower().find(key.lower())
    if i<0: return '“'+(full[:n].rsplit(' ',1)[0]+'…')+'”'
    st=full.rfind('. ',0,i); st=0 if st<0 else st+2
    en=full.find('. ',i); en=len(full) if en<0 else en+1
    q=full[st:en].strip()
    if len(q)>n: q=q[:n].rsplit(' ',1)[0]+'…'
    return '“'+q+'”'
def memcue(mem, n=120):
    mem=str(mem)
    if mem.lower() in ('nan',''): return '(no prior memory)'
    items=[collapse(p) for p in mem.split('|')]
    # prefer a reflection that records failure, else a concrete event line, else any reflection
    pick=next((p for p in items if 'Consolidated Reflection' in p and re.search(r'shortfall|catastroph|failed|poor choice|not viable|did not',p,re.I)), None) \
        or next((p for p in reversed(items) if re.search(r'unmet|received|shortfall|flood occurred|elevat|relocat|grants|insurance',p,re.I)), None) \
        or next((p for p in items if 'Consolidated Reflection' in p), None) \
        or items[-1]
    return pick[:n].rsplit(' ',1)[0]+'…' if len(pick)>n else pick

def summ(ar, col, lab, n=92):
    if ar is None or col not in ar.index: return ''
    s=collapse(ar[col])
    if s.lower() in ('nan','none','') or s.upper()==lab or len(s)<=4: return ''
    return s[:n].rsplit(' ',1)[0]+'…' if len(s)>n else s

def get_row(domain, agent, y, key):
    if domain=='flood':
        run=SA/'JOH_FINAL'/'gemma3_4b'/'Group_C'/'Run_1'; audit='household_governance_audit.csv'
        A1=('TA','reason_tp_label','reason_tp_reason'); A2=('CP','reason_cp_label','reason_cp_reason')
    else:
        run=IRR/'production_v21_42yr_seed42'; audit='irrigation_farmer_governance_audit.csv'
        A1=('WSA','reason_wsa_label','reason_wsa_reason'); A2=('ACA','reason_aca_label','reason_aca_reason')
    sl=pd.read_csv(run/'simulation_log.csv',encoding='utf-8-sig'); au=pd.read_csv(run/audit,encoding='utf-8-sig')
    sr=sl[(sl.agent_id==agent)&(sl.year==y)]; ar=au[(au.agent_id==agent)&(au.year==y)]
    if not len(sr): return None
    sr=sr.iloc[0]; ar=ar.iloc[0] if len(ar) else None
    prim=str(ar[A1[1]]).upper() if ar is not None else '?'; sec=str(ar[A2[1]]).upper() if ar is not None else '?'
    dec=str(sr['yearly_decision']).lower()
    return dict(year=y, prim=(A1[0],prim,TIER.get(prim,'')), sec=(A2[0],sec),
                prim_sum=summ(ar,A1[2],prim), sec_sum=summ(ar,A2[2],sec),
                decision=DEC.get(dec,dec), mismatch=(prim in ('H','VH') and (dec.startswith('increase') or dec=='do_nothing')),
                status=str(ar['status']) if ar is not None and 'status' in ar.index else '',
                retry=str(ar['retry_count']) if ar is not None and 'retry_count' in ar.index else '',
                rules=clean_rules(ar['failed_rules']) if ar is not None and 'failed_rules' in ar.index else '(none)',
                mem=memcue(sr.get('memory','')),
                quote=keyquote(ar['reason_reasoning'],key) if ar is not None and 'reason_reasoning' in ar.index else '')

TRACES=[
 dict(domain='irrig', agent='ColoradoUsesBelowShiprockNM_CoAgUteMtnUte', disp='Irrigation: Colorado uses below Shiprock NM (governed)',
      phenom='Persistent demand escalation under worsening scarcity. The recalled memory records each shortfall, the WSA-ACA-coherence and curtailment validators reject the proposal every year and three retries are spent, yet the agent re-proposes a large increase and it executes, even in year 13.',
      rows=[(1,'skeptical of forecasts'),(2,'capitalize'),(3,'consistent shortages'),(13,'aggressively increase')]),
 dict(domain='flood', agent='Agent_89', disp='Flood: Agent 89 (governed)',
      phenom='Trust-deficit protection gap. After elevating (year 2) the household appraises high threat for years but refuses the one remaining option, insurance, on distrust; the extreme-threat-block validator rejects do-nothing and three retries are spent, yet do-nothing executes in years 3 and 4 before the household relocates in year 5.',
      rows=[(2,'distrust'),(3,'distrust the insurance'),(4,'avoiding flood insurance'),(5,'relocation seems drastic')]),
]

# ---- doc ----
doc=Document(); sec=doc.sections[0]
sec.orientation=WD_ORIENT.LANDSCAPE; sec.page_width,sec.page_height=Inches(11),Inches(8.5)
sec.left_margin=sec.right_margin=Inches(0.5)
doc.styles['Normal'].font.name='Calibri'; doc.styles['Normal'].font.size=Pt(8.5)
GREEN=RGBColor(0x1E,0x82,0x49); RED=RGBColor(0xC0,0x39,0x2B); GREY=RGBColor(0x66,0x66,0x66); BLUE=RGBColor(0x00,0x72,0xB2)

cap=doc.add_paragraph()
r=cap.add_run('Table 1 | Two decision traces in which the executed action contradicts the agent’s own appraisal under the full validator stack.'); r.bold=True; r.font.size=Pt(9)
r2=cap.add_run(' Governed condition, Gemma-3 4B, executed final actions. For each agent-year the recalled memory, the validators that '
   'fired, the retries spent and the agent’s verbatim reasoning are shown. In the red rows the executed action contradicts the '
   'appraisal-implied expectation: the proposal was rejected and the three-retry budget was spent, but the agent re-proposed the '
   'same action and it executed. The irrigation agent escalates demand as scarcity worsens even as its own memory records each '
   'shortfall; the flood household refuses insurance on distrust and so takes no action in successive high-threat years. This '
   'contested-then-executed pattern, and the divergence between recalled memory and action, cannot arise in a fixed-function ABM, '
   'where the action is a deterministic function of state. WSA, Water Scarcity Appraisal; ACA, Adaptive Capacity Appraisal; TA, '
   'Threat Appraisal; CP, Coping Appraisal; tiers VL/L/M/H/VH; validator identifiers as in Supplementary Table 2.')
r2.font.size=Pt(8)

def emit(tr):
    h=doc.add_paragraph(); hr=h.add_run(tr['disp']); hr.bold=True; hr.font.size=Pt(9.5)
    ph=doc.add_paragraph(); pr=ph.add_run(tr['phenom']); pr.italic=True; pr.font.size=Pt(7.5); pr.font.color.rgb=GREY
    cols=['Yr','Appraisal (label + the agent’s own summary)','Executed','Validators fired (retries)','Recalled memory / reflection','Reason the agent gave for the chosen action (verbatim)']
    widths=[0.3,2.45,0.9,1.35,2.2,2.8]
    t=doc.add_table(rows=1,cols=len(cols)); t.style='Light Grid Accent 1'; t.autofit=False
    for i,(c,w) in enumerate(zip(cols,widths)):
        cell=t.rows[0].cells[i]; cell.width=Inches(w)
        rr=cell.paragraphs[0].add_run(c); rr.bold=True; rr.font.size=Pt(8.5)
    for (y,key) in tr['rows']:
        rec=get_row(tr['domain'],tr['agent'],y,key)
        if not rec: continue
        cells=t.add_row().cells
        for i,w in enumerate(widths): cells[i].width=Inches(w); cells[i].vertical_alignment=WD_ALIGN_VERTICAL.TOP
        cells[0].paragraphs[0].add_run(str(rec['year'])).font.size=Pt(8.5)
        ap=cells[1].paragraphs[0]; n,l,word=rec['prim']
        b=ap.add_run(f'{n} = {l}'); b.bold=True; b.font.size=Pt(8.5)
        if word: ww=ap.add_run(f' ({word})'); ww.font.size=Pt(7.5)
        if rec['prim_sum']: ap.add_run(f". {rec['prim_sum']}").font.size=Pt(7.5)
        ap2=cells[1].add_paragraph(); s2=ap2.add_run(f"{rec['sec'][0]} = {rec['sec'][1]}"); s2.bold=True; s2.font.size=Pt(8)
        if rec['sec_sum']: ap2.add_run(f". {rec['sec_sum']}").font.size=Pt(7.5)
        dr=cells[2].paragraphs[0].add_run(rec['decision']); dr.bold=True; dr.font.size=Pt(9.5)
        dr.font.color.rgb=(RED if rec['mismatch'] else GREEN)
        gp=cells[3].paragraphs[0]
        st=gp.add_run('Rejected' if rec['status']=='REJECTED' else rec['status']); st.bold=True; st.font.size=Pt(8)
        st.font.color.rgb=(RED if rec['status']=='REJECTED' else GREEN)
        gp.add_run(f"  ·  {rec['retry']} retries").font.size=Pt(7.5)
        gp2=cells[3].add_paragraph(); gp2.add_run(rec['rules']).font.size=Pt(7.5)
        mr=cells[4].paragraphs[0].add_run(rec['mem']); mr.font.size=Pt(7.5)
        if 'Consolidated Reflection' in rec['mem'] or 'unmet' in rec['mem'] or 'shortfall' in rec['mem']:
            mr.font.color.rgb=RED
        qr=cells[5].paragraphs[0].add_run(rec['quote']); qr.font.size=Pt(7.5); qr.italic=True

for tr in TRACES:
    emit(tr)
foot=doc.add_paragraph()
fr=foot.add_run('Read each row left to right: appraisal severe → theory expects conservation/protection → executed the opposite (red) '
   '→ validators fired and three retries were spent → the recalled memory already recorded the failure → the agent re-proposed the '
   'same action in its reasoning, and it executed. Memory in red marks evidence the agent itself recorded that the action had failed.')
fr.font.size=Pt(8); fr.italic=True; fr.font.color.rgb=GREY

OUT=Path('paper/nature_water/WAGF_agent_decision_logs.docx')
try:
    doc.save(OUT)
except PermissionError:
    OUT=Path('paper/nature_water/WAGF_agent_decision_logs_v3.docx'); doc.save(OUT)
    print('  (master locked -> saved as _v3)')
print('wrote',OUT,OUT.stat().st_size,'bytes')
