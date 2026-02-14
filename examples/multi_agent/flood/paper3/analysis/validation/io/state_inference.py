"""
State Inference from Decision Traces.

Infers final agent state from cumulative decision traces, because the
simulation engine does not populate state_after with decision outcomes.
"""

from typing import Dict, List

from validation.io.trace_reader import _normalize_action, _extract_action


def _extract_final_states(traces: List[Dict]) -> Dict[str, Dict]:
    """Extract final state for each agent from traces (legacy: reads state_after)."""
    final_states = {}

    for trace in traces:
        agent_id = trace.get("agent_id", "")
        year = trace.get("year", 0)

        if agent_id not in final_states or year > final_states[agent_id].get("_year", 0):
            state = trace.get("state_after", {})
            state["_year"] = year
            final_states[agent_id] = state

    return final_states


def _extract_final_states_from_decisions(traces: List[Dict]) -> Dict[str, Dict]:
    """
    Infer final state from cumulative decision traces.

    - Insurance: True if agent chose buy_insurance in LAST year only
      (insurance is annual, lapses if not renewed)
    - Elevated: True if agent EVER chose elevate (irreversible)
    - Bought out: True if agent EVER chose buyout (irreversible)
    - Relocated: True if agent EVER chose relocate (irreversible)
    """
    agent_decisions: Dict[str, Dict] = {}

    for trace in traces:
        agent_id = trace.get("agent_id", "")
        if not agent_id:
            continue

        outcome = trace.get("outcome", "")
        if outcome in ("REJECTED", "UNCERTAIN"):
            continue
        if not trace.get("validated", True):
            continue

        year = trace.get("year", 0)
        action = _normalize_action(_extract_action(trace))

        if agent_id not in agent_decisions:
            agent_decisions[agent_id] = {
                "actions": set(),
                "max_year": year,
                "last_action": action,
                "last_state": dict(trace.get("state_after", {})),
            }

        agent_decisions[agent_id]["actions"].add(action)
        if year > agent_decisions[agent_id]["max_year"]:
            agent_decisions[agent_id]["max_year"] = year
            agent_decisions[agent_id]["last_action"] = action
            agent_decisions[agent_id]["last_state"] = dict(trace.get("state_after", {}))

    final_states: Dict[str, Dict] = {}
    for agent_id, info in agent_decisions.items():
        actions = info["actions"]
        state = dict(info["last_state"])

        last_action = info.get("last_action", "")
        state["has_insurance"] = last_action == "buy_insurance"
        state["elevated"] = "elevate" in actions
        state["bought_out"] = "buyout" in actions
        state["relocated"] = "relocate" in actions
        state["_year"] = info["max_year"]

        final_states[agent_id] = state

    return final_states
