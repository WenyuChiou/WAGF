# -*- coding: utf-8 -*-
# =============================================================================
# StochasticABM-Revision.py - Traditional Stochastic ABM (no PMT terms)
# =============================================================================
# Author: Dr. Y. C. Ethan Yang @ Lehigh University
# Created: 2025/08/08
# Last Modified: 2025/12/04
#
# Optional: reads agent_initial_profiles.csv and flood_years.csv if present
# States: elevated (irreversible), has_insurance (annual), relocated (absorbing)
#
# MODIFICATION HISTORY (Line References)
# -----------------------------------------------------------------------------
# [2025/12/04] EVENT-DRIVEN TRUST UPDATE (Lines 189-212)
# -----------------------------------------------------------------------------
# TRUST IN INSURANCE (based on individual flood experience):
#   Scenario A: Insured + Flooded     -> -0.10
#               "The Hassle" - Filing claims is stressful and disappointing
#   Scenario B: Insured + Safe        -> +0.02
#               "Peace of Mind" - Feels responsible and protected
#   Scenario C: Not Insured + Flooded -> +0.05
#               "The Hard Lesson" - Regrets not having coverage
#   Scenario D: Not Insured + Safe    -> -0.02
#               "The Gambler's Reward" - Saved money, thinks insurance is waste
#
# TRUST IN NEIGHBORS (based on community_action_rate):
#   community_action_rate = (total_elevated + total_relocated) / NUM_AGENTS
#   - If rate > 30%                   -> +0.04 "Everyone is acting, they know something"
#   - If Flooded + rate < 10%         -> -0.05 "We are all sitting ducks here"
#   - Otherwise                       -> -0.01 (natural decay over time)
#
# Values clamped to [0.0, 1.0] after each update.
# =============================================================================
import numpy as np, pandas as pd, matplotlib.pyplot as plt, os      # import core libs for math, dataframes, plotting, filesystem

# ---------------- Params ----------------
NUM_AGENTS = 100                                                    # number of agents in the model
NUM_YEARS  = 10                                                     # number of simulated years
MEMORY_WINDOW = 5                                                   # how many recent events each agent remembers
FLOOD_PROB = 0.2                                                    # probability a community flood occurs in a year (if not fixed via CSV)
GRANT_PROB = 0.5                                                    # probability an elevation grant is available in a year
import argparse                                                     # CLI argument parsing
RNG_SEED   = int(os.environ.get('RNG_SEED', '42'))                 # random seed for reproducibility (read from env or default to 42)

# decision ?�temperature??(higher = more random)
TAU = 0.5                                                           # softmax temperature controlling stochasticity of choices

# Base utilities (tunable) ??small set, no PMT:
U0_DONOTHING = 0.6        # inertia                                      # baseline propensity to do nothing
U0_INS       = 0.3        # baseline preference for insurance             # baseline propensity to buy insurance
U0_ELEV      = 0.1        # baseline preference to elevate                # baseline propensity to elevate
U0_RELOC     = -1.5       # relocation rare by default                    # baseline propensity to relocate (negative = rare)

# Simple effects (tunable):
EFF_FLOOD_THIS_YEAR   = 0.8   # pushes actions when community flood happens   # effect of a community flood on action utilities
EFF_AGENT_FLOODED     = 1.2   # stronger push if personally flooded           # effect when that specific agent was flooded
EFF_GRANT_ON_ELEV     = 0.8   # elevation more attractive with grants         # grant increases elevation utility
#EFF_PEER_ELEV_SHARE   = 0.6   # bandwagon for elevation                       # peer effect: % elevated neighbors
#EFF_PEER_RELOC_SHARE  = 0.4   # bandwagon for relocation                      # peer effect: % relocated neighbors
COST_ELEV             = 1.0   # keeps elevation in check                      # effective cost term for elevation
COST_RELOC            = 2.0   # keeps relocation rare                         # effective cost term for relocation
MEMORY_DECAY          = 0.85  # 0<decay<1; closer to 1 = slower fade of older floods
COEF_MEM_INS          = 0.35  # memory effect on insurance utility
COEF_MEM_ELEV         = 0.35  # memory effect on elevation utility
COEF_MEM_RELOC        = 0.20  # memory effect on relocation utility (smaller => keeps relocation rarer)
COEF_MEM_NONE         = -0.20 # memory discourages inaction

rng = np.random.default_rng(RNG_SEED)                                     # RNG with fixed seed

def softmax(u, tau=TAU):
    u = np.array(u, dtype=float)                                          # ensure numpy array
    e = np.exp((u - u.max())/max(1e-6, tau))                              # numerically stable exponentiation with temperature
    return e / e.sum()                                                    # return normalized probabilities

# -------------- Init agents --------------
def init_random_agents(n):
    agents=[]                                                             # container for agent dicts
    for i in range(n):                                                    # create n agents
        agents.append(dict(
            id=f"Agent_{i+1}",                                           # unique agent id
            elevated=False, has_insurance=rng.random()<0.5, relocated=False,  # initial states
            flood_threshold=rng.uniform(0.4,0.9),                         # agent-specific flood susceptibility
            trust_ins=rng.uniform(0.2,0.5), trust_nei=rng.uniform(0.35,0.55), # trust levels (simple scalars)
            memory=[], flood_history=[]                                   # recent memory tags and yearly flood booleans
        ))
    return agents                                                         # return initialized population

def load_agents_from_csv(path):
    df = pd.read_csv(path)                                                # read initial agent profiles
    agents=[]
    for _,r in df.iterrows():                                             # iterate rows to build agent dicts
        mem = (str(r.get("memory","")).split(" | ") if pd.notna(r.get("memory")) else [])  # parse memory field if present
        agents.append(dict(
            id=r["id"],                                                   # use stored id
            elevated=bool(r["elevated"]),                                 # stored elevation status
            has_insurance=bool(r["has_insurance"]),                       # stored insurance status
            relocated=bool(r["relocated"]),                               # stored relocation status
            flood_threshold=float(r["flood_threshold"]),                  # stored susceptibility
            trust_ins=float(r["trust_in_insurance"]),                     # stored trust in insurance
            trust_nei=float(r["trust_in_neighbors"]),                     # stored trust in neighbors
            memory=mem, flood_history=[]                                  # memory from file; start fresh yearly flood history
        ))
    return agents                                                         # return loaded population

# -------------- Run simulation --------------
def run():
    # Optional fixed inputs — resolve paths relative to script directory
    base_path = os.path.dirname(os.path.abspath(__file__))
    profiles_path = os.path.join(base_path, "agent_initial_profiles.csv")
    fyears_path = os.path.join(base_path, "flood_years.csv")
    has_profiles = os.path.exists(profiles_path)
    has_fyears   = os.path.exists(fyears_path)

    agents = load_agents_from_csv(profiles_path) if has_profiles else init_random_agents(NUM_AGENTS)
                                                                          # load agents if file exists; else random init

    if has_fyears:
        flood_years = pd.read_csv(fyears_path).iloc[:,0].astype(int).tolist()
                                                                          # load flood years (assumes first column is year)
    else:
        flood_years = [y for y in range(1, NUM_YEARS+1) if rng.random() < FLOOD_PROB]
                                                                          # otherwise, generate random flood years
        pd.DataFrame({"Flood_Years": flood_years}).to_csv("flood_years.csv", index=False)
                                                                          # save generated flood years for reproducibility

    # Save randomized profiles if none provided
    if not has_profiles:
        prof = pd.DataFrame([{
            "id": a["id"], "elevated": a["elevated"], "has_insurance": a["has_insurance"],
            "relocated": a["relocated"], "trust_in_insurance": round(a["trust_ins"],2),
            "trust_in_neighbors": round(a["trust_nei"],2), "memory": " | ".join(a["memory"]),
            "flood_threshold": a["flood_threshold"]
        } for a in agents])                                              # build a DataFrame snapshot of initial agents
        prof.to_csv("agent_initial_profiles.csv", index=False)           # save profiles for deterministic reruns

    logs=[]                                                               # list to collect yearly records per agent

    for year in range(1, NUM_YEARS+1):                                    # simulate year by year
        flood_event = (year in flood_years)                               # whether community flood happened this year
        grant = (rng.random() < GRANT_PROB)                               # whether elevation grant is available

        active = [a for a in agents if not a["relocated"]]                # agents still making decisions
        if not active: break                                              # end early if everyone relocated

        elev_share = float(np.mean([a["elevated"] for a in active])) if active else 0.0
                                                                          # share of active agents already elevated
        reloc_share= 1.0 - len(active)/len(agents)                        # overall relocated share (among all agents)

        for a in active:                                                  # loop through active agents
            # Flood exposure
            flooded = False                                               # default: not flooded
            if flood_event:
                threshold = a["flood_threshold"]
                if a["elevated"]:
                    threshold *= 0.2 # 80% risk reduction for elevated homes
                
                if rng.random() < threshold:
                    flooded = True
            
            a["flood_history"].append(flooded)                            # record personal flood for this year

            # Maintain short memory (simple tags only)
            a["memory"].append("flooded" if flooded else ("flood" if flood_event else "no_flood"))
                                                                          # store a simple tag for this year
            a["memory"] = a["memory"][-MEMORY_WINDOW:]                    # keep only recent N memories

            # --- Decay?�weighted memory effect ---
            mem_sev = 0.0
            w = 1.0
            for tag in reversed(a["memory"]):            # most recent first
                if tag in ("flooded", "flood"):          # count both personal flood and community flood
                    mem_sev += w
                w *= MEMORY_DECAY                         # older memories count less

            # translate memory into small nudges on utilities (tune coefficients)
            mem_effect_ins = COEF_MEM_INS * mem_sev
            mem_effect_elev = COEF_MEM_ELEV * mem_sev
            mem_effect_reloc = COEF_MEM_RELOC * mem_sev # keep relocation rarer
            mem_effect_none = COEF_MEM_NONE * mem_sev # memory of floods discourages inaction

            # --- Simple, PMT?�free propensities ---
            U_donothing = U0_DONOTHING - 0.6*(flood_event) - 0.8*(flooded) + mem_effect_none # inertia reduced by flood signals
            U_ins   = U0_INS   + 0.5*(flood_event) + 0.8*(flooded) + 0.4*a["trust_ins"] + mem_effect_ins # insurance utility increases with flood & trust
            U_elev  = U0_ELEV  + EFF_FLOOD_THIS_YEAR*(flood_event) + EFF_AGENT_FLOODED*(flooded) + EFF_GRANT_ON_ELEV*(grant) + 0.2*a["trust_nei"]*elev_share - COST_ELEV + mem_effect_elev # elevation utility: flood/grant/peers minus cost
            U_reloc = U0_RELOC + EFF_FLOOD_THIS_YEAR*(flood_event) + EFF_AGENT_FLOODED*(flooded) + 0.2*a["trust_nei"]*reloc_share - COST_RELOC + mem_effect_reloc # relocation utility: flood/peers minus high cost
          
            if a["elevated"]:                                             # choice set if already elevated
                opts = ["Insurance","Relocate","DoNothing"]               # cannot elevate again
                ps = softmax([U_ins, U_reloc, U_donothing])               # convert utilities to probabilities
                choice = rng.choice(opts, p=ps)                           # draw one action
                a["has_insurance"] = (choice=="Insurance")                # set insurance for this year
                if choice=="Relocate": a["relocated"]=True                # relocation is absorbing
            else:                                                         # choice set if not elevated
                opts = ["Insurance","Elevate","Relocate","DoNothing"]     # has all four options
                ps = softmax([U_ins, U_elev, U_reloc, U_donothing])       # probabilities over four actions
                choice = rng.choice(opts, p=ps)                           # draw one action
                if choice=="Insurance": a["has_insurance"]=True           # insurance on for this year
                elif choice=="Elevate": a["elevated"]=True                # elevation becomes irreversible
                elif choice=="Relocate": a["relocated"]=True              # exit future decisions
                else: a["has_insurance"]=False                            # do nothing ??ensure insurance off

            # --- EVENT-DRIVEN TRUST UPDATE (Same Logic as LLM ABM) ---
            # 1. Update Trust in Insurance (4 Scenarios based on individual flood experience)
            if a["has_insurance"]:
                if flooded: 
                    # Scenario A: Insured + Flooded ("The Hassle")
                    a["trust_ins"] -= 0.10
                else:
                    # Scenario B: Insured + Safe ("Peace of Mind")
                    a["trust_ins"] += 0.02
            else:
                if flooded:
                    # Scenario C: Not Insured + Flooded ("The Hard Lesson")
                    a["trust_ins"] += 0.05
                else:
                    # Scenario D: Not Insured + Safe ("The Gambler's Reward")
                    a["trust_ins"] -= 0.02

            # 2. Update Trust in Neighbors (Social Proof)
            community_action_rate = elev_share + reloc_share
            if community_action_rate > 0.30:
                # High Activity: "Everyone is acting, they must know something."
                a["trust_nei"] += 0.04
            elif flooded and community_action_rate < 0.10:
                # Disaster + Inaction: "We are all sitting ducks here."
                a["trust_nei"] -= 0.05
            else:
                # Status Quo: Slight natural decay over time
                a["trust_nei"] -= 0.01

            # Clamp values between 0.0 and 1.0
            a["trust_ins"] = float(np.clip(a["trust_ins"], 0, 1))
            a["trust_nei"] = float(np.clip(a["trust_nei"], 0, 1))

            # Combined state for logging
            if a["relocated"]: state="Relocate"                           # absorbing state
            elif a["elevated"] and a["has_insurance"]: state="Both Flood Insurance and House Elevation"
                                                                          # both actions present
            elif a["elevated"]: state="Only House Elevation"              # only elevated
            elif a["has_insurance"]: state="Only Flood Insurance"         # only insured
            else: state="Do Nothing"                                      # neither

            logs.append(dict(
                agent_id=a["id"], year=year, decision=state,              # store ID, year, final state label
                flooded_this_year=flooded, elevated=a["elevated"],        # store outcomes and flags
                has_insurance=a["has_insurance"], relocated=a["relocated"],
                trust_in_insurance=round(a["trust_ins"],2), trust_in_neighbors=round(a["trust_nei"],2)
            ))                                                            # append one log row
        
        # Log status for previously relocated agents (to match LLM ABM behavior)
        for a in agents:
            if a["relocated"]:
                # Check if this agent already has a log entry for this year
                has_entry_this_year = any(log["agent_id"] == a["id"] and log["year"] == year for log in logs)
                if not has_entry_this_year:
                    # Agent relocated in a previous year, log "Already relocated" status
                    logs.append(dict(
                        agent_id=a["id"], year=year, decision="Already relocated",
                        flooded_this_year=False, elevated=a["elevated"],
                        has_insurance=a["has_insurance"], relocated=True,
                        trust_in_insurance=round(a["trust_ins"],2), trust_in_neighbors=round(a["trust_nei"],2)
                    ))

    return pd.DataFrame(logs), flood_years                                # return logs dataframe and flood years list

# -------------- Run & plots --------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rule-based stochastic flood ABM (no LLM)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    # Override global seed
    RNG_SEED = args.seed
    rng = np.random.default_rng(RNG_SEED)

    out_dir = args.output or "."
    os.makedirs(out_dir, exist_ok=True)

    df_log, flood_years = run()
    df_log.to_csv(os.path.join(out_dir, "simulation_log.csv"), index=False)
    print(f"Saved {len(df_log)} rows to {out_dir}/simulation_log.csv")

    # Summary stats
    active = df_log[~df_log["decision"].str.contains("relocated", case=False, na=False)]
    print(f"\nSkill distribution (active decisions):")
    print(active["decision"].value_counts(normalize=True).to_string())

    # Plot: Stacked adaptation states by year
    order = ["Do Nothing","Only Flood Insurance","Only House Elevation",
             "Both Flood Insurance and House Elevation","Relocate"]
    state_counts = (df_log.groupby(["year","decision"]).size()
                    .unstack(fill_value=0).reindex(columns=order, fill_value=0))
    ax = state_counts.plot(kind="bar", stacked=True, figsize=(12,6))
    ax.set_title(f"Rule-Based ABM: Adaptation States (seed={RNG_SEED})")
    ax.set_ylabel("Number of Agents"); ax.set_xlabel("Year")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "overall_adaptation_by_year.jpg"), dpi=300)
    plt.close()

