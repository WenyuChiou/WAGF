#!/usr/bin/env python3
"""8 completed flood models: integrity check + unified conditional AAI + EHE +
paired-t + R1/R3/R4 counts (5 seeds). gemma3_27b excluded (still running)."""
import sys; sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,'examples/single_agent/analysis')
from compute_flood_metrics import process_llm_csv
import pandas as pd, glob, os, numpy as np
from scipy import stats

RES='examples/single_agent/results'
MODELS=['gemma3_4b','gemma3_12b','gemma4_e2b','gemma4_e4b','gemma4_26b','ministral3_3b','ministral3_8b','ministral3_14b','gemma3_27b']

def run_dirs(model, gov):
    roots=(['JOH_FINAL_v2','JOH_FINAL'] if gov else ['JOH_ABLATION_DISABLED_v2','JOH_ABLATION_DISABLED'])
    grp='Group_C' if gov else 'Group_C_disabled'
    for root in roots:
        rs=sorted(glob.glob(f'{RES}/{root}/{model}/{grp}/Run_*'))
        if rs: return rs
    return []

def metrics(rundir):
    """returns (aai_conditional, ehe, R1, R3, R4, n_nonmedium, n_total)"""
    sl=pd.read_csv(rundir+'/simulation_log.csv',encoding='utf-8-sig')
    au=pd.read_csv(rundir+'/household_governance_audit.csv',encoding='utf-8-sig')
    m=sl.merge(au[['agent_id','year','reason_tp_label']],on=['agent_id','year'],how='left')
    m=m[m['yearly_decision'].astype(str).str.lower()!='relocated']
    ta=m['reason_tp_label'].astype(str).str.upper(); dec=m['yearly_decision'].astype(str).str.lower()
    R1=int(((ta.isin(['H','VH']))&(dec=='do_nothing')).sum())
    R3=int(((ta.isin(['VL','L']))&(dec=='relocate')).sum())
    R4=int(((ta.isin(['VL','L']))&(dec=='elevate_house')).sum())
    den=int((ta.isin(['H','VH','VL','L'])).sum())          # non-medium denominator
    aai=100*(R1+R3+R4)/den if den else np.nan
    ehe=process_llm_csv(rundir+'/simulation_log.csv')[0]
    return aai,ehe,R1,R3,R4,den,len(m)

def reflog_ok(rundir):
    rl=rundir+'/reflection_log.jsonl'
    return os.path.exists(rl) and sum(1 for _ in open(rl,encoding='utf-8')) > 50

print(f"{'model':14}|{'gov n/refl':>11}|{'nov n/refl':>11}| AAI gov  AAI nov  dAAI  p(AAI) | EHE gov EHE nov dEHE p(EHE)| R1 g/n  R3 g/n R4 g/n")
rows={}
for mdl in MODELS:
    gd=run_dirs(mdl,True); nd=run_dirs(mdl,False)
    g=[metrics(r) for r in gd]; n=[metrics(r) for r in nd]
    grefl=sum(reflog_ok(r) for r in gd); nrefl=sum(reflog_ok(r) for r in nd)
    ga=np.array([x[0] for x in g]); na=np.array([x[0] for x in n])
    ge=np.array([x[1] for x in g]); ne=np.array([x[1] for x in n])
    # paired by index (Run order = seed order); align lengths
    L=min(len(ga),len(na))
    ta_,pa=stats.ttest_rel(na[:L],ga[:L]) if L>1 else (np.nan,np.nan)
    te_,pe=stats.ttest_rel(ge[:L],ne[:L]) if L>1 else (np.nan,np.nan)
    R1g=sum(x[2] for x in g); R3g=sum(x[3] for x in g); R4g=sum(x[4] for x in g)
    R1n=sum(x[2] for x in n); R3n=sum(x[3] for x in n); R4n=sum(x[4] for x in n)
    rows[mdl]=dict(aai_g=ga.mean(),aai_g_sd=ga.std(ddof=1),aai_n=na.mean(),aai_n_sd=na.std(ddof=1),
                   daai=na.mean()-ga.mean(),paai=pa, ehe_g=ge.mean(),ehe_g_sd=ge.std(ddof=1),
                   ehe_n=ne.mean(),ehe_n_sd=ne.std(ddof=1),dehe=ge.mean()-ne.mean(),pehe=pe,
                   R1g=R1g,R3g=R3g,R4g=R4g,R1n=R1n,R3n=R3n,R4n=R4n,ng=len(gd),nn=len(nd),
                   ga_arr=ga[:L],na_arr=na[:L],ge_arr=ge[:L],ne_arr=ne[:L])
    print(f"{mdl:14}|{len(gd)}/{grefl:>2} runs |{len(nd)}/{nrefl:>2} runs | {ga.mean():6.2f}  {na.mean():6.2f} {na.mean()-ga.mean():+6.2f} {pa:6.3f} | {ge.mean():.3f}  {ne.mean():.3f} {ge.mean()-ne.mean():+5.3f} {pe:5.3f}| {R1g}/{R1n}  {R3g}/{R3n} {R4g}/{R4n}")

# emit SI-ready rows
print('\n=== SI Supplementary Table 1 rows (Inconsistency conditional %, R1,R3,R4, EHE) ===')
NAME={'gemma3_4b':'Gemma-3 4B','gemma3_12b':'Gemma-3 12B','gemma4_e2b':'Gemma-4 e2b','gemma4_e4b':'Gemma-4 e4b',
      'gemma4_26b':'Gemma-4 26B','ministral3_3b':'Ministral 3B','ministral3_8b':'Ministral 8B','ministral3_14b':'Ministral 14B','gemma3_27b':'Gemma-3 27B'}
for mdl in MODELS:
    r=rows[mdl]
    print(f"| {NAME[mdl]} | LLM (no validator) | {r['nn']} | {r['aai_n']:.1f} ± {r['aai_n_sd']:.1f} | {r['R1n']} | {r['R3n']} | {r['R4n']} | {r['ehe_n']:.3f} ± {r['ehe_n_sd']:.3f} |")
    print(f"| | Governed LLM | {r['ng']} | {r['aai_g']:.1f} ± {r['aai_g_sd']:.1f} | {r['R1g']} | {r['R3g']} | {r['R4g']} | {r['ehe_g']:.3f} ± {r['ehe_g_sd']:.3f} |")
print('\n=== SI Supplementary Table 6 rows (dAAI [CI] p ; dEHE [CI] p) ===')
TC=2.776  # t_crit df=4
def ci(arr):
    m=arr.mean(); se=arr.std(ddof=1)/np.sqrt(len(arr)); return m, m-TC*se, m+TC*se
for mdl in MODELS:
    r=rows[mdl]
    da,dlo,dhi=ci(r['na_arr']-r['ga_arr'])          # dAAI = noval - gov
    ea,elo,ehi=ci(r['ge_arr']-r['ne_arr'])          # dEHE = gov - noval
    pstr=lambda p: '<0.001' if p<0.001 else f'{p:.3f}'
    print(f"| {NAME[mdl]} | {r['nn']} | +{da:.2f} | [{dlo:+.2f}, {dhi:+.2f}] | {pstr(r['paai'])} | {ea:+.3f} | [{elo:+.3f}, {ehi:+.3f}] | {pstr(r['pehe'])} |")
