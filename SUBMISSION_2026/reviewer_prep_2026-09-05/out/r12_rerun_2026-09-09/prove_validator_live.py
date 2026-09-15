"""
prove_validator_live.py — direct proof the HBM thinking_rules validator is
LIVE on the vaccination NEW arm (JOH_T0-4b_gemma3_4b_88c21542), not merely
that no row in that batch happened to match a rule precondition.

Builds the SAME AgentValidator class the run used
(broker/validators/agent/agent_validator.py), loaded from the SAME YAML the
run actually snapshot-copied (examples/vaccination_demo/config/agent_types.yaml
in this worktree, commit 88c215429410 — the r12_rerun_zero_fires report
already confirmed this file's `thinking_rules:` block is byte-identical to
Run_42/Run_43's own config_snapshot.yaml), and calls
`AgentValidator.validate_thinking(...)` directly — the exact Tier-2 function
`_validate_internal` (broker/validators/agent/agent_validator.py:407) calls
when reasoning is present, which is what `AgentValidator.validate()`
(the SkillBrokerEngine-facing generic entry point, agent_validator.py:196)
delegates to.

Three cases, all derived from one real row
(Run_42 raw/individual_traces.jsonl, line 2 = Agent_001, year 1):
  (a) unmodified reasoning -> expect 0 results (APPROVED, no rule fires)
  (b) SUSCEPTIBILITY_LABEL forced to VL, decision kept get_vaccinated
      -> expect WARNING low_susceptibility_no_get_vaccinated
  (c) SUSCEPTIBILITY_LABEL=H, SELF_EFFICACY_LABEL=H (SEVERITY_LABEL already H
      in the source row), BARRIERS_LABEL forced to M (down from H, so the
      high_barriers_high_self_efficacy WARNING rule's own precondition does
      NOT also fire and confound the read), decision=refuse
      -> expect ERROR high_susceptibility_high_severity_high_efficacy_no_refuse

No GPU, no ollama, no pytest. Pure in-process construction of the validator
against the on-disk YAML plus one JSON row read from a completed run. Runs in
under a second.
"""
import json
import sys
from pathlib import Path

WORKTREE = Path("C:/Users/wenyu/Desktop/Lehigh/wagf-vax-runs")
sys.path.insert(0, str(WORKTREE))

from broker.validators.agent.agent_validator import AgentValidator, ValidationLevel  # noqa: E402
from broker.interfaces.skill_types import SkillProposal  # noqa: E402

CONFIG_PATH = WORKTREE / "examples/vaccination_demo/config/agent_types.yaml"
RUN_DIR = WORKTREE / "examples/vaccination_demo/results/JOH_T0-4b_gemma3_4b_88c21542/Run_42"
TRACES = RUN_DIR / "raw/individual_traces.jsonl"


def load_source_row():
    with open(TRACES, encoding="utf-8") as f:
        lines = f.readlines()
    # line 0 is a _metadata header record, not a trace row.
    rec = json.loads(lines[1])
    assert rec["agent_id"] == "Agent_001" and rec["year"] == 1, (
        f"expected Agent_001/year 1 at line index 1, got "
        f"{rec.get('agent_id')}/{rec.get('year')}"
    )
    return rec


def fmt_result(r):
    lv = r.metadata.get("level")
    lv_name = lv.value if isinstance(lv, ValidationLevel) else lv
    return {
        "valid": r.valid,
        "validator_name": r.validator_name,
        "level": lv_name,
        "rule_id": r.metadata.get("rule_id"),
        "blocked_skills_field": r.metadata.get("field"),
        "errors": r.errors,
        "warnings": r.warnings,
    }


def run_case(label, validator, agent_type, agent_id, decision, state, reasoning, expect):
    validator.reset()
    results = validator.validate_thinking(
        agent_type, agent_id, decision, state, reasoning, full_context=None,
    )
    print(f"\n=== Case {label}: {expect} ===")
    print(f"decision = {decision!r}")
    for k in ("SUSCEPTIBILITY_LABEL", "SEVERITY_LABEL", "BENEFITS_LABEL",
              "BARRIERS_LABEL", "SELF_EFFICACY_LABEL", "CUES_TO_ACTION_LABEL"):
        print(f"  reasoning[{k}] = {reasoning.get(k)!r}")
    print(f"validate_thinking() returned {len(results)} ValidationResult object(s):")
    if not results:
        print("  (none)")
    for r in results:
        print(" ", json.dumps(fmt_result(r), indent=2))
    print(f"validator.has_errors() = {validator.has_errors()}")
    print(f"validator.summary()    = {json.dumps(validator.summary(), indent=2)}")
    return results


def main():
    print(f"Config path : {CONFIG_PATH}")
    print(f"Config exists: {CONFIG_PATH.exists()}")
    print(f"Source row  : {TRACES}")

    rec = load_source_row()
    proposal = rec["skill_proposal"]
    base_reasoning = dict(proposal["reasoning"])  # copy — do not mutate source
    state = dict(rec["state_before"])
    agent_type = rec["agent_type"]
    agent_id = rec["agent_id"]

    print(f"\nSource row: agent_id={agent_id} year={rec['year']} "
          f"agent_type={agent_type} proposed skill_name={proposal['skill_name']!r}")
    print("Source reasoning labels (unmodified):")
    for k in ("SUSCEPTIBILITY_LABEL", "SEVERITY_LABEL", "BENEFITS_LABEL",
              "BARRIERS_LABEL", "SELF_EFFICACY_LABEL", "CUES_TO_ACTION_LABEL"):
        print(f"  {k} = {base_reasoning.get(k)!r}")

    validator = AgentValidator(config_path=str(CONFIG_PATH))
    rules = validator.config.get_thinking_rules(agent_type)
    print(f"\nLoaded {len(rules)} thinking_rules for agent_type={agent_type!r} "
          f"from {CONFIG_PATH.name}:")
    for r in rules:
        print(f"  - id={r.id} level={r.level} blocked_skills={r.blocked_skills} "
              f"conditions={r.conditions}")

    # --- Case (a): unmodified row -> expect 0 results ---------------------
    reasoning_a = dict(base_reasoning)
    results_a = run_case(
        "a", validator, agent_type, agent_id,
        decision=proposal["skill_name"],  # "get_vaccinated"
        state=state, reasoning=reasoning_a,
        expect="expect 0 results (APPROVED, no rule fires)",
    )

    # --- Case (b): sus forced to VL, decision=get_vaccinated --------------
    reasoning_b = dict(base_reasoning)
    reasoning_b["SUSCEPTIBILITY_LABEL"] = "VL"
    results_b = run_case(
        "b", validator, agent_type, agent_id,
        decision="get_vaccinated",
        state=state, reasoning=reasoning_b,
        expect="expect WARNING low_susceptibility_no_get_vaccinated",
    )

    # --- Case (c): R1 ERROR precondition, decision=refuse ------------------
    # high_susceptibility_high_severity_high_efficacy_no_refuse requires
    # SUSCEPTIBILITY_LABEL in {H,VH} AND SEVERITY_LABEL in {H,VH} AND
    # SELF_EFFICACY_LABEL in {H,VH}, blocked_skills=[refuse].
    # Source row already has SEVERITY_LABEL=H. Force SUSCEPTIBILITY_LABEL and
    # SELF_EFFICACY_LABEL to H. Also pull BARRIERS_LABEL down from its source
    # H to M so the WARNING rule high_barriers_high_self_efficacy_no_action
    # (BARRIERS in {H,VH} AND SELF_EFFICACY in {H,VH}, blocked=[delay,refuse])
    # does NOT also fire on this same case — keeps the ERROR-rule read clean.
    reasoning_c = dict(base_reasoning)
    reasoning_c["SUSCEPTIBILITY_LABEL"] = "H"
    reasoning_c["SELF_EFFICACY_LABEL"] = "H"
    reasoning_c["BARRIERS_LABEL"] = "M"
    results_c = run_case(
        "c", validator, agent_type, agent_id,
        decision="refuse",
        state=state, reasoning=reasoning_c,
        expect="expect ERROR high_susceptibility_high_severity_high_efficacy_no_refuse",
    )

    # --- Case (d): SAME case-c inputs, through the FULL engine entry point --
    # broker/core/skill_broker_engine.py:1062 calls
    # `validator.validate(proposal, context, self.skill_registry)` — the
    # generic dispatcher (agent_validator.py:196) that detects a
    # `SkillProposal`-shaped first arg and routes to `_validate_internal`
    # (agent_validator.py:242), which is the ONLY call path that also runs
    # `_categorize_results` (agent_validator.py:1075) into `self.errors` /
    # `self.warnings` — `validate_thinking()` alone (used in a/b/c above)
    # does not categorize. This closes the loop: same rule fires, AND
    # `has_errors()` now flips True the way the live engine would see it.
    validator.reset()
    proposal_c = SkillProposal(
        skill_name="refuse",
        agent_id=agent_id,
        reasoning=reasoning_c,
        agent_type=agent_type,
        parse_layer="enclosure+json",
    )
    engine_context = {"agent_type": agent_type, "agent_id": agent_id, "state": state}
    results_d = validator.validate(proposal_c, engine_context, None)
    print("\n=== Case d: same as (c), through validator.validate(proposal, context, registry) "
          "— the exact call skill_broker_engine.py:1062 makes ===")
    print(f"validate() returned {len(results_d)} ValidationResult object(s):")
    for r in results_d:
        print(" ", json.dumps(fmt_result(r), indent=2))
    print(f"validator.has_errors() = {validator.has_errors()}  (expect True)")
    print(f"validator.summary()    = {json.dumps(validator.summary(), indent=2)}")
    ok_d = validator.has_errors() and any(
        r.metadata.get("rule_id") == "high_susceptibility_high_severity_high_efficacy_no_refuse"
        for r in validator.errors
    )

    # --- Verdict ------------------------------------------------------------
    print("\n=== VERDICT ===")
    ok_a = len(results_a) == 0
    ok_b = (
        len(results_b) == 1
        and results_b[0].metadata.get("rule_id") == "low_susceptibility_no_get_vaccinated"
        and results_b[0].metadata.get("level") == ValidationLevel.WARNING
    )
    ok_c = any(
        r.metadata.get("rule_id") == "high_susceptibility_high_severity_high_efficacy_no_refuse"
        and r.metadata.get("level") == ValidationLevel.ERROR
        for r in results_c
    )
    print(f"Case a (clean row, no fire)                         : {'PASS' if ok_a else 'FAIL'}")
    print(f"Case b (forced VL susceptibility -> WARNING R2)     : {'PASS' if ok_b else 'FAIL'}")
    print(f"Case c (forced H/H/refuse -> ERROR R1, via validate_thinking direct): {'PASS' if ok_c else 'FAIL'}")
    print(f"Case d (same as c, via full validate(proposal,...) engine entry)   : {'PASS' if ok_d else 'FAIL'}")
    print(f"\nALL PASS: {ok_a and ok_b and ok_c and ok_d}")


if __name__ == "__main__":
    main()
