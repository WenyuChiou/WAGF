"""A synthetic finished-run directory for the PR-5 replay/ablation tests.

Synthetic rather than a copy of a real run, for two reasons: the tests
must pass in a clean checkout with no scratchpad, and a fixture the repo
owns cannot drift out from under them when a run directory is deleted.

The prompt below has the same shape the flood household template
renders — persona, memory bullets carrying the yearly cues, the trust
sentence, and a numbered options block the production parser reads — so
the real ``ModelAdapter`` parses replies to it exactly as it does in a
live run.

Not named ``test_*``, so pytest does not collect it.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOOD_CONFIG = REPO_ROOT / "examples" / "single_agent" / "agent_types.yaml"

PROMPT_TEMPLATE = """You are a homeowner in a city, with a strong attachment to your community.
You have not elevated your home.
Your memory includes:
- Year {year}: No flood occurred this year. | Year {year}: Elevation grants are available. | Year {year}: I observe 25% of neighbors elevated and 0% relocated.
- A few households in the area elevated their homes before recent floods

You currently do not have flood insurance.
You have slight doubts about the insurance company. You are skeptical of your neighbors' judgment.

Now, choose one of the following actions:
1. Buy flood insurance (Lower cost, provides partial financial protection)
2. Elevate your house (High upfront cost but can prevent most physical damage)
3. Relocate (Requires leaving your neighborhood but eliminates flood risk)
4. Do nothing (Require no financial investment or effort this year)

<<<DECISION_START>>>
{{"decision": "<Enter the numeric ID (1-4) of your chosen action.>"}}
<<<DECISION_END>>>
"""


#: The numeric option each recordable skill corresponds to in the prompt
#: above, so a test decider and the recorded trace can be made to agree.
DECISION_ID = {"buy_insurance": 1, "elevate_house": 2,
               "relocate": 3, "do_nothing": 4}


def write_run_dir(
    root: Path, n_agents: int = 2, n_years: int = 2,
    recorded_skill: str = "buy_insurance",
) -> Path:
    """Write ``root/run`` as a finished flood run and return the path.

    ``recorded_skill`` is the decision the traces say the agent made. A
    test whose replay decider returns something else at baseline is
    testing the mismatch path, not the intervention — which is why the
    parameter exists rather than being hard-coded.
    """
    decision_id = DECISION_ID[recorded_skill]
    run_dir = root / "run"
    (run_dir / "raw").mkdir(parents=True)

    lines = [json.dumps({
        "_metadata": {"framework_version": "0.6.0", "audit_schema_version": 2,
                      "git_commit_short": "deadbeefcafe"},
        "agent_type": "household",
    })]
    seed = 43
    for year in range(1, n_years + 1):
        for index in range(1, n_agents + 1):
            lines.append(json.dumps({
                "run_id": "exp_test", "step_id": year, "year": year, "seed": seed,
                "agent_id": f"Agent_{index}", "model": "mock",
                "input": PROMPT_TEMPLATE.format(year=year),
                "raw_output": '{"decision": %d}' % decision_id,
                "memory_pre": [{"content": "a past flood", "importance": 0.4}],
                "environment_context": {"flood_event": False, "grant_available": True,
                                        "current_year": year, "premium_rate": 0.02},
                "state_before": {"id": f"Agent_{index}", "elevated": False,
                                 "has_insurance": False, "relocated": False,
                                 "trust_in_insurance": 0.34, "trust_in_neighbors": 0.4,
                                 "name": f"Agent_{index}"},
                "skill_proposal": {"skill_name": recorded_skill,
                                   "parse_layer": "enclosure+json"},
                "approved_skill": {"skill_name": recorded_skill, "status": "APPROVED"},
                "outcome": "APPROVED",
                "agent_type": "household",
            }))
            seed += 1
    (run_dir / "raw" / "household_traces.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")

    (run_dir / "reproducibility_manifest.json").write_text(json.dumps({
        "model": "mock", "seed": 42, "num_years": n_years,
        "agent_types_config": str(FLOOD_CONFIG),
        "git_commit": "deadbeefcafe0000000000000000000000000000",
    }), encoding="utf-8")
    return run_dir
