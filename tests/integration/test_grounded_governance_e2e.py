"""PR-6 — a world-grounded rule, observed end to end in a real audit trace.

Every other PR-6 test drives the validator directly. That proves the rule
EVALUATES; it does not prove the rule reaches the CSV a reader will actually
open. Four separate things sit between the two, and each of them has failed
before in this repo: the environment has to publish the variable under the key
the rule names, the broker has to carry it into the validation context, the
validator has to stamp `grounding` on the firing, and the audit writer has to
turn on the grounding columns for the profile. A unit test passes with any one
of them broken.

So this drives `ExperimentBuilder` + `ExperimentRunner` against the SHIPPED
flood config's `grounded_v1` profile and asserts on the rows in
`household_governance_audit.csv`.

The shipped `--model mock` emits `{"decision": N}` and no construct labels, so
every row fails the response-format check first and no thinking rule of any kind
can fire — which is why the mock here emits a full response instead. It is a
stand-in for the model, not a stand-in for the framework: nothing in `broker/`
is patched, and the config, the rule, the broker pipeline and the audit writer
are all the production ones.

The scenario is the one in `docs/guides/governance_layers.md` §2: an agent that
reports `TP_LABEL: VL` and chooses `do_nothing`, every year, unchanged. In the
years with no flood the profile has nothing to say and the decision is APPROVED.
In the flood years the same self-report is REJECTED. The self-report never
moves; the verdict does; and that difference is exactly what a world-grounded
rule buys.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOOD_CONFIG = REPO_ROOT / "examples" / "single_agent" / "agent_types.yaml"
FLOOD_REGISTRY = REPO_ROOT / "examples" / "single_agent" / "skill_registry.yaml"

GROUNDED_RULE_ID = "observed_flood_low_threat_inaction"
FLOOD_YEARS = (2, 3)  # the sim below publishes flood_event from year 2 on


@pytest.fixture(autouse=True, scope="module")
def _restore_global_registries():
    """Import + build side effects are process-global; hand them back.

    Importing ``examples.single_agent`` registers the flood DomainPack, and
    ``ExperimentBuilder.build()`` writes ``GOVERNANCE_PROFILE`` into the real
    environment. Both outlive this module and would silently change what a later
    test resolves.
    """
    import os

    from broker.domains.registry import DomainPackRegistry
    from broker.utils.agent_config import AgentTypeConfig

    saved_packs = dict(DomainPackRegistry._packs)
    saved_profile = os.environ.get("GOVERNANCE_PROFILE")
    yield
    DomainPackRegistry.clear()
    for name, pack in saved_packs.items():
        DomainPackRegistry._packs[name] = pack
    if saved_profile is None:
        os.environ.pop("GOVERNANCE_PROFILE", None)
    else:
        os.environ["GOVERNANCE_PROFILE"] = saved_profile
    AgentTypeConfig.clear_cache()


class _FloodYearSimulation:
    """Minimal environment. Publishes ``flood_event`` — the variable the
    grounded rule reads, and the one no agent can write."""

    def __init__(self, flood_years=FLOOD_YEARS):
        self.year = 0
        self.flood_years = set(flood_years)

    def advance_year(self):
        self.year += 1
        return {
            "current_year": self.year,
            "flood_event": self.year in self.flood_years,
            "grant_available": False,
            "situation": f"Year {self.year}.",
        }

    def execute_skill(self, approved_skill):
        from broker.interfaces.skill_types import ExecutionResult
        return ExecutionResult(success=True, state_changes={})


def _build_agents():
    from broker.agents import AgentConfig, BaseAgent
    from broker.agents.base import Skill, StateParam

    skills = [
        Skill("do_nothing", "Do nothing", None, "none"),
        Skill("buy_insurance", "Buy insurance", "has_insurance", "increase"),
        Skill("elevate_house", "Elevate the house", "elevated", "increase"),
        Skill("relocate", "Relocate", "relocated", "increase"),
    ]
    state = [StateParam("savings", (0.0, 1_000_000.0), 50_000.0, "Savings")]
    return {
        name: BaseAgent(AgentConfig(
            name=name, agent_type="household", state_params=state,
            objectives=[], constraints=[], skills=skills,
        ))
        for name in ("H1", "H2")
    }


def _label_emitting_invoke(prompt):
    """A model that answers "low threat, do nothing" every single year.

    Fixed on purpose: the whole point is that the SELF-REPORT never changes, so
    any change in the verdict can only have come from the world.
    """
    from broker.utils.llm_utils import LLMStats

    payload = {
        "decision": "do_nothing",
        "threat_appraisal": "VL",
        "coping_appraisal": "H",
        "TP_REASON": "test harness value, not a model output",
        "CP_REASON": "test harness value, not a model output",
    }
    return json.dumps(payload), LLMStats(retries=0, success=True)


@pytest.fixture(scope="module")
def grounded_run(tmp_path_factory):
    """Run the experiment ONCE; every test below reads the artifacts."""
    import examples.single_agent  # noqa: F401 — registers the flood DomainPack
    from broker.components.memory.engine import WindowMemoryEngine
    from broker.core.experiment import ExperimentBuilder

    output_dir = Path(tmp_path_factory.mktemp("pr6_grounded_e2e"))
    runner = (
        ExperimentBuilder()
        .with_model("mock")
        .with_years(3)
        .with_agents(_build_agents())
        .with_simulation(_FloodYearSimulation())
        .with_skill_registry(str(FLOOD_REGISTRY))
        .with_memory_engine(WindowMemoryEngine(window_size=3))
        .with_governance("grounded_v1", str(FLOOD_CONFIG))
        .with_exact_output(str(output_dir))
        .with_workers(1)
        .with_seed(42)
    ).build()
    # The one substitution: a model that emits construct labels. Injected at the
    # runner's own per-agent-type cache seam, so no broker code is patched.
    runner._llm_cache["household"] = _label_emitting_invoke
    runner._llm_cache["default"] = _label_emitting_invoke
    runner.run()

    with open(output_dir / "household_governance_audit.csv",
              newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    return {"output_dir": output_dir, "rows": rows}


def test_the_run_wrote_a_row_per_agent_year(grounded_run):
    assert len(grounded_run["rows"]) == 6  # 2 agents x 3 years


def test_the_grounding_columns_are_present_for_a_grounded_profile(grounded_run):
    """Auto-on: a profile that declares a world-grounded rule gains the columns
    without an operator remembering a second flag, so a grounded run cannot be
    launched with the evidence for its own headline switched off."""
    header = grounded_run["rows"][0].keys()
    assert "rules_world_grounded" in header
    assert "rules_self_report" in header


def test_a_flood_year_row_names_the_grounded_rule(grounded_run):
    """THE end-to-end assertion. The rule fired, blocked the action, and the
    audit row says the antecedent read the world rather than the model's own
    labels."""
    flood_rows = [r for r in grounded_run["rows"] if int(r["year"]) in FLOOD_YEARS]
    assert flood_rows, "the sim must publish a flood in at least one year"
    for row in flood_rows:
        assert row["status"] == "REJECTED", row
        assert row["rules_triggered"] == GROUNDED_RULE_ID, row
        assert row["rules_world_grounded"] == GROUNDED_RULE_ID, row
        assert row["rules_self_report"] == "", row


def test_the_same_self_report_is_approved_in_a_year_with_no_flood(grounded_run):
    """The self-report is byte-identical across every row — `TP_LABEL: VL`,
    `do_nothing`. Only the world differs, and only the world can explain the
    difference in verdict. No rule conditioned on `TP_LABEL` alone could produce
    this contrast."""
    quiet = [r for r in grounded_run["rows"] if int(r["year"]) not in FLOOD_YEARS]
    assert quiet
    for row in quiet:
        assert row["construct_TP_LABEL"] == "VL", row
        assert row["proposed_skill"] == "do_nothing", row
        assert row["status"] == "APPROVED", row
        assert row["rules_world_grounded"] == "", row


def test_the_run_is_not_flagged_when_the_variable_was_published(grounded_run):
    """The guardrail fires when a grounded profile ran and its variable was
    never readable. Here it was, so the run must come back clean — a guardrail
    that flagged a healthy run would be trained away within a week."""
    integrity = json.loads(
        (grounded_run["output_dir"] / "run_integrity.json").read_text(
            encoding="utf-8"))
    assert integrity["world_grounded_rows"] == 6
    assert integrity["world_rules_unevaluable_rows"] == 0
    assert integrity["integrity_ok"] is True
