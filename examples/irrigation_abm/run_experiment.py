#!/usr/bin/env python3
"""
Irrigation ABM Experiment Runner — Hung & Yang (2021) LLM Adaptation.

Single production pipeline using the Water Agent Governance Framework (WAGF):
  Pillar 1 — Strict Governance  (water rights, curtailment, magnitude caps)
  Pillar 2 — Cognitive Memory   (HumanCentric engine + year-end reflection)
  Pillar 3 — Priority Schema    (important attributes enter context first)

Usage:
    python run_experiment.py                                        # defaults: gemma3:1b, 5yr, synthetic
    python run_experiment.py --model gemma3:4b --years 42 --real    # 78 CRSS agents, 42 years
    python run_experiment.py --model gemma3:4b --years 10 --agents 10  # 10 synthetic agents

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""
from __future__ import annotations

import argparse
import random
import sys
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from broker.agents import BaseAgent, AgentConfig
from examples.irrigation_abm.irrigation_env import (
    CRSS_DEMAND_TARGET_AF,
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    build_narrative_persona,
    build_water_situation_text,
    build_conservation_status,
    build_aca_hint,
    build_action_outcome_feedback,
    create_profiles_from_csv,
    describe_gap_reason,
    rebalance_clusters,
)
from broker.core.experiment import ExperimentBuilder
from broker.components.memory.engine import HumanCentricMemoryEngine
from broker.components.cognitive.reflection import ReflectionEngine
from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter
from broker.components.governance.registry import SkillRegistry
from broker.components.context.builder import TieredContextBuilder
from broker.interfaces.skill_types import ExecutionResult
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor
from examples.irrigation_abm.validators.irrigation_validators import (
    irrigation_governance_validator,
    reset_consecutive_tracker,
    update_consecutive_tracker,
)
import examples.irrigation_abm.validators.irrigation_validators as irr_validators

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IRRIGATION_SKILLS = [
    "increase_large", "increase_small", "maintain_demand",
    "decrease_small", "decrease_large",
]


# ---------------------------------------------------------------------------
# v0.6 coupling-layer flag resolution (--coupling CLI flag)
# ---------------------------------------------------------------------------
def _absolutize_prompt_template_paths(cfg_data: Dict[str, Any], original_config_dir: Path) -> None:
    """Rewrite every ``prompt_template_file`` value in ``cfg_data`` to an
    absolute path, resolved against the ORIGINAL config directory tree.
    Mutates ``cfg_data`` in place.

    Needed because the derived config copy this module writes lives in the
    run's output directory, not next to the original ``agent_types.yaml`` -
    any RELATIVE ``prompt_template_file`` reference has to keep resolving to
    the same file it always did, regardless of where the copy is written.
    Domain-block-name-agnostic (walks every top-level dict value, not just
    ``irrigation_farmer``) so a future second agent type with its own
    ``prompt_template_file`` is covered too.

    Two candidate bases are tried, in this order, and whichever resolves to
    a file that actually exists on disk wins:
      1. ``original_config_dir`` (the value's own directory - what
         ``broker/components/context/tiered.py``'s YAML-driven prompt
         loader assumes).
      2. ``original_config_dir.parent`` (the domain root - what irrigation's
         ``agent_types.yaml`` value, written as ``config/prompts/...``,
         actually needs; this runner reads the prompt file directly via the
         equivalent of ``config_dir / "prompts" / "irrigation_farmer.txt"``
         rather than through the YAML-driven loader).
    A reference matching neither is left unchanged - never worse than
    before, just not fixed.
    """
    for block in cfg_data.values():
        if not isinstance(block, dict):
            continue
        ref = block.get("prompt_template_file")
        if not ref or Path(ref).is_absolute():
            continue
        for base_dir in (original_config_dir, original_config_dir.parent):
            candidate = base_dir / ref
            if candidate.exists():
                block["prompt_template_file"] = str(candidate.resolve())
                break
        else:
            # Neither candidate base resolved to a real file (e.g. an
            # unusual --config-dir layout): left relative rather than
            # silently guessing, and reported so a run under that layout
            # is not just quietly worse.
            print(
                f"[coupling] prompt_template_file left relative: {ref} "
                f"(no candidate base resolved; runner reads prompts from "
                f"config_dir directly)"
            )


def _resolve_irrigation_coupling(
    cfg_data: Dict[str, Any],
    agent_config_path: Path,
    cli_flag: bool,
    output_dir: Path,
) -> Tuple[Path, bool]:
    """Resolve whether the v0.6 coupling layer
    (``broker.coupling.EnvironmentCouplingAdapter``, via
    ``ExperimentBuilder.with_coupling``) should wrap this run's sim engine.

    ONE switch, not two: the flag ``broker/coupling/flag.py``'s
    ``resolve_coupling_enabled`` reads is ``global_config.coupling.enable``
    in the agent_types YAML (Layer 1) or the DomainPack's
    ``coupling_enabled_default()`` (Layer 2, ``IrrigationDomainPack`` ->
    False). The ``--coupling`` CLI flag never gates coupling by a SEPARATE
    mechanism - it only WRITES that same Layer-1 key into an isolated copy
    of the config (mirroring ``--config-dir``'s isolation), so it can never
    edit the frozen on-disk ``agent_types.yaml``, and the builder's own
    two-layer resolution (invoked later, at ``.build()``) reads the exact
    key this function just set and agrees with the decision returned here.
    ``--coupling`` OVERRIDES an explicit ``enable: false`` already in the
    YAML (source is then reported as ``cli``, not ``yaml``) - the CLI flag
    is a request to turn coupling ON, not merely a default.

    The derived copy is written to ``<output_dir>/agent_types.coupling.yaml``
    (a PERSISTENT file, not a temp file deleted at process exit, so a failed
    or finished run can still be inspected) with ``sort_keys=False``, so the
    PARSED config differs from the original only by the added
    ``coupling.enable`` key - not a wholesale reformat. ``config_hash`` in
    the reproducibility manifest is a byte hash of this DERIVED file, so it
    is NOT comparable to a hash of the original; the original file's own
    byte hash is recorded separately, as ``derived_from_config_sha256``
    (``ExperimentRunner._collect_reproducibility_metadata``, read off the
    same ``runner.broker._derived_from_config`` attribute this function's
    caller sets). ``prompt_template_file`` references are rewritten to
    absolute paths first, when they resolve against a known base directory
    (see ``_absolutize_prompt_template_paths``; a reference that resolves
    against neither candidate, e.g. under an unusual ``--config-dir`` copy,
    is left relative and reported with a printed line rather than silently
    ignored) so they keep resolving correctly from the new location.

    Returns ``(effective_agent_config_path, coupling_enabled)``. When
    ``cli_flag`` is False and the YAML did not already declare the key,
    ``agent_config_path`` is returned unchanged and ``coupling_enabled`` is
    False - the default-OFF, byte-identical path.
    """
    from broker.coupling.flag import resolve_coupling_enabled
    from broker.domains.registry import DomainPackRegistry

    pack = DomainPackRegistry.get("irrigation")
    if cli_flag:
        cfg_data.setdefault("global_config", {}).setdefault("coupling", {})["enable"] = True
    enabled, source = resolve_coupling_enabled(cfg_data, pack)
    if not cli_flag:
        return agent_config_path, enabled
    _absolutize_prompt_template_paths(cfg_data, agent_config_path.parent)
    derived_path = output_dir / "agent_types.coupling.yaml"
    with open(derived_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg_data, fh, sort_keys=False)
    print(
        f"[coupling] enable={enabled} (source=cli --coupling; original "
        f"config {agent_config_path}; derived config written to {derived_path})"
    )
    return derived_path, enabled


# ---------------------------------------------------------------------------
# Profile → BaseAgent conversion
# ---------------------------------------------------------------------------
def _profiles_to_agents(
    profiles: List[IrrigationAgentProfile],
) -> Dict[str, BaseAgent]:
    """Convert IrrigationAgentProfile list to BaseAgent dict for ExperimentBuilder."""
    agents: Dict[str, BaseAgent] = {}
    for p in profiles:
        config = AgentConfig(
            name=p.agent_id,
            agent_type="irrigation_farmer",
            state_params=[],
            objectives=[],
            constraints=[],
            skills=IRRIGATION_SKILLS,
        )
        agent = BaseAgent(config)

        # Set custom attributes used by context builder and prompt template
        attrs = {
            "narrative_persona": p.narrative_persona,
            "basin": p.basin,
            "cluster": p.cluster,
            "water_right": p.water_right,
            "farm_size_acres": p.farm_size_acres,
            "crop_type": p.crop_type,
            "years_farming": p.years_farming,
            "has_efficient_system": p.has_efficient_system,
            "at_allocation_cap": False,
            "below_minimum_utilisation": False,
        }
        agent.custom_attributes = attrs
        for k, v in attrs.items():
            setattr(agent, k, v)

        agents[p.agent_id] = agent
    return agents


# ---------------------------------------------------------------------------
# Synthetic profile builder (for quick testing without CRSS data)
# ---------------------------------------------------------------------------
def _create_synthetic_profiles(
    n_agents: int,
    seed: int = 42,
) -> List[IrrigationAgentProfile]:
    """Create synthetic agent profiles with balanced cluster distribution."""
    from examples.irrigation_abm.learning.fql import (
        CLUSTER_AGGRESSIVE,
        CLUSTER_FORWARD_LOOKING,
        CLUSTER_MYOPIC,
    )

    rng = np.random.default_rng(seed)
    clusters = ["aggressive", "forward_looking_conservative", "myopic_conservative"]
    ref_configs = {
        "aggressive": CLUSTER_AGGRESSIVE,
        "forward_looking_conservative": CLUSTER_FORWARD_LOOKING,
        "myopic_conservative": CLUSTER_MYOPIC,
    }

    profiles = []
    for i in range(n_agents):
        basin = "upper_basin" if i < n_agents // 3 else "lower_basin"
        cluster = clusters[i % 3]
        ref = ref_configs[cluster]

        profile = IrrigationAgentProfile(
            agent_id=f"Agent_{i:03d}",
            basin=basin,
            cluster=cluster,
            mu=ref.mu + rng.normal(0, 0.02),
            sigma=ref.sigma + rng.normal(0, 0.1),
            alpha=ref.alpha + rng.normal(0, 0.02),
            gamma_param=ref.gamma + rng.normal(0, 0.02),
            epsilon=ref.epsilon + rng.normal(0, 0.01),
            regret=ref.regret + rng.normal(0, 0.1),
            forget=True,
            farm_size_acres=rng.uniform(200, 2000),
            water_right=rng.uniform(50_000, 200_000),
            crop_type=str(rng.choice(["alfalfa", "cotton", "vegetables", "corn"])),
            years_farming=int(rng.integers(5, 40)),
        )
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles


# ---------------------------------------------------------------------------
# Lifecycle Hooks
# ---------------------------------------------------------------------------
def _proposed_and_fallback(action_ctx: Optional[Dict[str, Any]]) -> Tuple[str, bool]:
    """(the agent's own proposal, whether it was overruled) for one year.

    On an approved row the executed skill IS the proposal. On a rejected
    row ExperimentRunner._apply_state_changes records ``proposed_skill``
    (None on UNCERTAIN rows, where no usable proposal existed) and
    ``was_fallback``. Memory salience reads the proposal, not the executed
    fallback (supply-side redesign, 2026-09-25, spec M1/M2/M4)."""
    ctx = action_ctx or {}
    was_fallback = bool(ctx.get("was_fallback", False))
    proposed = ctx.get("proposed_skill") if "proposed_skill" in ctx else ctx.get("skill_name", "")
    return (proposed or ""), was_fallback


def _unmet_frac(request: float, delivered: float) -> float:
    """1 - delivered / requested on [0, 1] (0 when nothing was requested).
    Rounded to 6 places so float noise cannot move a band edge."""
    if not request or request <= 0:
        return 0.0
    return round(min(1.0, max(0.0, 1.0 - float(delivered) / float(request))), 6)


class IrrigationLifecycleHooks:
    """Hooks that wire water state, memory injection, and reflection."""

    def __init__(
        self,
        env: IrrigationEnvironment,
        runner,  # ExperimentRunner (set after build)
        profiles: List[IrrigationAgentProfile],
        reflection_engine: Optional[ReflectionEngine],
        output_dir: Path,
    ):
        self.env = env
        self.runner = runner
        self.profiles = {p.agent_id: p for p in profiles}
        self.reflection_engine = reflection_engine
        self.output_dir = output_dir
        self.logs: List[Dict] = []
        self.yearly_decisions: Dict = {}
        # Feedback dashboard (attached after construction by main())
        self.metrics_tracker = None
        self.feedback_config: Dict = {}
        # Band importance / emotion for the yearly outcome memory line.
        self.memory_adapter = IrrigationAdapter()
        # memory.rejection_line_style for the yearly memory line (set by main()
        # from the irrigation_farmer.memory YAML block).
        self.rejection_line_style = "neutral"

    # -- the simulation-log's Lake Mead column, under the same flag --
    def _log_lake_mead_level(self):
        """Read ``lower_basin.lake_mead_level`` for the simulation log.

        Review P1-b: this column was the ONE physical-state read that stayed
        outside the ``coupling.context_contract`` guard. ``get_agent_context``
        (guarded) and this logger (unguarded, ``get_local(..., 0)``) read the
        SAME field, so with the flag ON a missing reservoir level would raise
        for the prompt and quietly write 0 into the analysis CSV — the two
        artifacts of one run disagreeing about whether the value existed.
        With the flag OFF the expression is character-for-character the old
        one, so every frozen corpus reproduces byte-identically.
        """
        if getattr(self.env, "_coupling_contract_active", False):
            level = self.env.get_local("lower_basin", "lake_mead_level")
            if level is None:
                raise KeyError(
                    "lake_mead_level is missing from lower_basin and "
                    "coupling.context_contract is ON: refusing to log 0 ft for a "
                    "reservoir level that was never set (the prompt path fails "
                    "loud on the same field, and the two must not disagree)."
                )
            return level
        return self.env.get_local("lower_basin", "lake_mead_level", 0)

    # -- pre_year: inject water situation context and regret feedback --
    def pre_year(self, year: int, env_state: Dict, agents: Dict):
        for aid, agent in agents.items():
            if not getattr(agent, "is_active", True):
                continue

            ctx = self.env.get_agent_context(aid)
            profile = self.profiles.get(aid)
            if profile is None:
                continue

            # Build dynamic context attributes for prompt template. The F05
            # snapshot (last year's settled request / delivery / reason) feeds
            # the "Last year you requested ..." sentence (spec S1).
            water_situation = build_water_situation_text(
                ctx, last_year=getattr(agent, "_last_year_outcome", None)
            )
            conservation = build_conservation_status(profile)

            agent.water_situation_text = water_situation
            agent.conservation_status = conservation
            agent.aca_hint = build_aca_hint(profile.cluster)

            # Sync ALL validator-relevant fields from environment → agent
            # These flow through custom_attributes → context["state"] → validation_context
            agent_state = self.env.get_agent_state(aid)
            validator_fields = {
                "agent_id": aid,  # Phase C: needed by consecutive_increase_cap_check
                "at_allocation_cap": agent_state.get("at_allocation_cap", False),
                "has_efficient_system": agent_state.get("has_efficient_system", False),
                "below_minimum_utilisation": agent_state.get("below_minimum_utilisation", False),
                "water_right": ctx.get("water_right", 0),
                "current_diversion": ctx.get("current_diversion", 0),
                "current_request": ctx.get("current_request", 0),
                "curtailment_ratio": ctx.get("curtailment_ratio", 0),
                "shortage_tier": ctx.get("shortage_tier", 0),
                # Removed: drought_index — broker auto-injects from env_context (was duplicate, fired Governance:Diagnostic)
                "cluster": ctx.get("cluster", "unknown"),
                "basin": ctx.get("basin", "unknown"),
                # Removed: total_basin_demand — broker auto-injects from env_context (was duplicate, fired Governance:Diagnostic)
                "loop_year": year,  # use "loop_year" to avoid collision with env_context["year"] (CRSS calendar year)
                # Supply-side redesign (2026-09-25): read by the supply-gap and
                # shortage rule messages (describe_gap_reason).
                "gap_reason": ctx.get("gap_reason", "none"),
                "delivery_ratio": ctx.get("delivery_ratio", 1.0),
                "lake_mead_level": ctx.get("lake_mead_level", 0),
            }
            for key, value in validator_fields.items():
                setattr(agent, key, value)
            if hasattr(agent, "custom_attributes"):
                agent.custom_attributes.update(validator_fields)

            # Feedback dashboard metrics are recorded in post_year from the
            # year's FINAL settlement (supply-side redesign, spec S2), so the
            # dashboard's latest row is last year's actual request and
            # delivery, the same numbers as the memory line and the "Last
            # year" sentence. Year 1 therefore shows no dashboard.

            # Inject combined action + outcome feedback from last year
            if year > 1:
                # F05 (2026-09-25 audit): by this point env.advance_year(year)
                # has already run and recomputed agent_state["diversion"]
                # under THIS year's provisional settlement
                # (irrigation_env.py: IrrigationEnvironment.advance_year),
                # and ctx["drought_index"]/["preceding_factor"] are this
                # year's too. Reading agent_state/ctx here for "last year's"
                # outcome silently reports year t's numbers under a year
                # t-1 label, disagreeing with the dashboard, which shows
                # the same live values under year t. Use the snapshot
                # post_year(year-1) captured at the END of year t-1,
                # before this year's advance_year() touched it.
                snapshot = getattr(agent, "_last_year_outcome", None)
                if snapshot:
                    prev_request = snapshot.get("request", 0)
                    prev_diversion = snapshot.get("diversion", 0)
                    prev_drought_index = snapshot.get("drought_index", 0)
                    prev_preceding_factor = snapshot.get("preceding_factor", 0)
                else:
                    # Defensive fallback only: post_year(year-1) always runs
                    # before pre_year(year) in ExperimentRunner.run, so this
                    # branch means a hook ordering change broke that
                    # invariant. Keep the run alive with the pre-F05 (stale)
                    # reading rather than crash a batch.
                    prev_request = agent_state.get("request", 0)
                    prev_diversion = agent_state.get("diversion", 0)
                    prev_drought_index = ctx.get("drought_index", 0)
                    prev_preceding_factor = ctx.get("preceding_factor", 0)
                action_ctx = getattr(agent, '_last_action_context', None)
                feedback = build_action_outcome_feedback(
                    action_ctx=action_ctx,
                    year=year - 1,
                    request=prev_request,
                    diversion=prev_diversion,
                    drought_index=prev_drought_index,
                    preceding_factor=prev_preceding_factor,
                    # F15 (2026-09-25 audit): Lower Basin agents' preceding_factor
                    # is the Lake Mead trend, not precipitation; basin selects the
                    # correct wording (build_water_situation_text already does this).
                    basin=ctx.get("basin", "upper_basin"),
                    # Supply-side redesign (spec S6): the same reason phrase as the
                    # situation text and rule messages; neutral or explicit wording
                    # of a rejected year (memory.rejection_line_style).
                    gap_reason=describe_gap_reason(snapshot or {}),
                    rejection_line_style=self.rejection_line_style,
                )
                # add_memory_for_agent (not add_memory) so the engine sees this
                # agent's memory_config (the irrigation_farmer.memory YAML
                # block, injected by ExperimentBuilder.build()'s Phase-12 step).
                #
                # Supply-side redesign (2026-09-25, spec M3): importance and
                # emotion are set here from the unmet fraction of LAST year's
                # final settlement and the agent's own proposal, instead of by
                # keyword match (which gave 1.0 to any line containing
                # "shortfall", so 5 percent unmet scored like 100 percent, and
                # filled the top 3 with 1.0 lines). A fallback year gets the
                # same band as an approved one.
                proposed, was_fallback = _proposed_and_fallback(action_ctx)
                unmet = _unmet_frac(prev_request, prev_diversion)
                salience_ctx = {"proposed_skill": proposed, "was_fallback": was_fallback,
                                "unmet_frac": unmet}
                self.runner.memory_engine.add_memory_for_agent(agent, feedback, {
                    "importance": self.memory_adapter.outcome_importance(unmet),
                    "emotion": self.memory_adapter.classify_emotion(proposed, salience_ctx),
                    "source": "personal",
                    "type": "outcome",
                })

    # -- post_step: record each agent's decision --
    def post_step(self, agent, result):
        # Use the runner's internal year counter (1-based), not env.current_year
        # which is the simulation year (e.g. 2020). The post_year hook receives
        # the same 1-based step counter from ExperimentRunner.
        year = getattr(self.runner, '_current_year', self.env.current_year)
        skill_name = None
        appraisals = {}

        if result and result.skill_proposal and result.skill_proposal.reasoning:
            r = result.skill_proposal.reasoning
            appraisals["wsa_label"] = next(
                (r[k] for k in ["WSA_LABEL", "water_scarcity_assessment",
                                "water_scarcity"] if k in r),
                "N/A",
            )
            appraisals["aca_label"] = next(
                (r[k] for k in ["ACA_LABEL", "adaptive_capacity_assessment",
                                "adaptive_capacity"] if k in r),
                "N/A",
            )

        if result and result.approved_skill:
            skill_name = result.approved_skill.skill_name
            # Read magnitude from environment state_changes, not LLM params:
            # the environment draws the Hung and Yang step (hy_step_af);
            # params.get("magnitude_pct") would be the LLM's discrete choice.
            exec_result = result.execution_result
            state_changes = exec_result.state_changes if exec_result else {}
            appraisals["magnitude_pct"] = state_changes.get("magnitude_pct_applied")
            # F07 follow-up: magnitude_pct_applied is the REALISED change
            # (after the water-right cap or the 10 percent floor); the drawn
            # step is logged beside it (percent and acre-ft) with its class.
            appraisals["magnitude_pct_sampled"] = state_changes.get("magnitude_pct_sampled")
            appraisals["magnitude_af"] = state_changes.get("magnitude_af")
            appraisals["magnitude_class"] = state_changes.get("magnitude_class")
            appraisals["is_exploration"] = state_changes.get("is_exploration", False)

            # Keep magnitude_fallback for debugging (indicates LLM didn't provide magnitude)
            params = result.approved_skill.parameters or {}
            appraisals["magnitude_fallback"] = params.get("magnitude_fallback", False)

        self.yearly_decisions[(agent.id, year)] = {
            "skill": skill_name,
            "appraisals": appraisals,
        }

        # Update consecutive increase tracker for Phase C/D validators
        if skill_name:
            update_consecutive_tracker(agent.id, skill_name)

    # -- post_year: logging, reflection --
    def post_year(self, year: int, agents: Dict):
        # Final settlement of the year (supply-side redesign, 2026-09-25;
        # keeps the F11b contract): every decision for this year has
        # executed by the time post_year runs, so settle_year() rebuilds
        # every agent's delivery from its final request and the frozen
        # 1 January snapshot, exactly once, before anything below reads
        # diversion (simulation_log.csv, the F05 snapshot, _batch_reflect).
        settlement = self.env.settle_year()
        basin_request_af = (
            settlement["ub_request_maf"] + settlement["lb_request_maf"]
        ) * 1e6

        for aid, agent in agents.items():
            agent_state = self.env.get_agent_state(aid)

            # F05 (2026-09-25 audit): snapshot THIS year's own outcome now.
            # request/diversion/drought_index/preceding_factor are all
            # correct for year `year` at this point (this year's decision
            # has executed and been settled, env.advance_year(year+1) has not
            # run yet). pre_year(year+1) reads this snapshot for its "last
            # year" memory line instead of re-querying live env state. Taken
            # from the SAME agent_state simulation_log.csv logs below, so
            # memory and the CSV always agree.
            basin_key = agent_state.get("basin", "lower_basin")
            agent._last_year_outcome = {
                "year": year,
                "request": agent_state.get("request", 0),
                "diversion": agent_state.get("diversion", 0),
                "gap_reason": agent_state.get("gap_reason", "none"),
                "curtailment_ratio": agent_state.get("curtailment_ratio", 0),
                "shortage_tier": self.env.institutions.get("colorado_compact", {}).get("shortage_tier", 0),
                "drought_index": self.env.global_state.get("drought_index", 0),
                "preceding_factor": self.env.get_local(basin_key, "preceding_factor", 0),
            }

            # F08+F33 (2026-09-25 audit): drought_count is a real, cumulative
            # per-agent counter (never written before this fix, so
            # IrrigationAdapter.compute_importance always saw 0), incremented
            # once per post_year call (every agent in `agents`, this hook
            # does not filter on is_active) when drought conditions hold.
            # Threshold 0.5 matches build_water_situation_text's own bucket
            # boundary for "Water supply is tight" (the >= 0.7 threshold used
            # by drought_severity_check is calibrated to a range the real
            # CRSS data never reaches -- see F04).
            drought_index_this_year = self.env.global_state.get("drought_index", 0)
            agent.drought_count = getattr(agent, "drought_count", 0) + (
                1 if drought_index_this_year >= 0.5 else 0
            )

            # Feedback dashboard: record this year's settled request and
            # delivery (spec S2). Sources are the context keys the YAML names;
            # after settle_year they equal the final request and delivery.
            if self.metrics_tracker is not None:
                settled = {
                    "current_request": agent_state.get("request", 0),
                    "current_diversion": agent_state.get("diversion", 0),
                }
                fb_metrics = {}
                for m_cfg in self.feedback_config.get("tracked_metrics", []):
                    src = m_cfg["source"]
                    fb_metrics[m_cfg["name"]] = float(settled.get(src, agent_state.get(src, 0)) or 0)
                self.metrics_tracker.record(aid, year, fb_metrics)

            dec = self.yearly_decisions.get((aid, year), {})
            skill = dec.get("skill") if isinstance(dec, dict) else dec
            appr = dec.get("appraisals", {}) if isinstance(dec, dict) else {}

            # Retrieve memory for logging (memory_engine.retrieve returns List[Dict]
            # with content/timestamp/importance/emotion; coerce to string before join)
            mem_items = self.runner.memory_engine.retrieve(agent, top_k=5)
            if isinstance(mem_items, list):
                mem_str = " | ".join(
                    (m.get("content", "") if isinstance(m, dict) else str(m))
                    for m in mem_items
                )
            else:
                mem_str = str(mem_items)

            profile = self.profiles.get(aid)
            self.logs.append({
                "agent_id": aid,
                "year": year,
                "cluster": profile.cluster if profile else "unknown",
                "basin": profile.basin if profile else "unknown",
                "yearly_decision": skill or "N/A",
                "wsa_label": appr.get("wsa_label", "N/A"),
                "aca_label": appr.get("aca_label", "N/A"),
                "request": agent_state.get("request", 0),
                "diversion": agent_state.get("diversion", 0),
                "water_right": agent_state.get("water_right", 0),
                "curtailment_ratio": agent_state.get("curtailment_ratio", 0),
                "drought_index": self.env.global_state.get("drought_index", 0),
                "shortage_tier": self.env.institutions.get("colorado_compact", {}).get("shortage_tier", 0),
                "lake_mead_level": self._log_lake_mead_level(),
                "mead_storage_maf": self.env._mead_storage[-1] if self.env._mead_storage else 0,
                # Supply-side redesign columns (appended; every older column
                # keeps its name). lake_mead_level / mead_storage_maf are the
                # 1 January values the agents saw; *_end_maf are this year's
                # end-of-year storages from the final settlement.
                "delivered": agent_state.get("diversion", 0),
                "delivery_ratio": agent_state.get("delivery_ratio", 1.0),
                "gap_reason": agent_state.get("gap_reason", "none"),
                "utilisation_delivered_pct": (
                    agent_state.get("diversion", 0) / agent_state.get("water_right", 1) * 100
                    if agent_state.get("water_right", 0) > 0 else 0
                ),
                "mead_storage_end_maf": settlement["mead_storage_end_maf"],
                "powell_storage_maf": settlement["powell_storage_maf"],
                "powell_storage_end_maf": settlement["powell_storage_end_maf"],
                "powell_release_maf": settlement["powell_release_maf"],
                "natural_flow_maf": settlement["natural_flow_maf"],
                "ub_delivered_maf": settlement["ub_delivered_maf"],
                "lb_phys_ratio": settlement["lb_phys_ratio"],
                # This year's FINAL request total (after every decision), not
                # the carried total advance_year() published to the prompts.
                "basin_request_af": basin_request_af,
                "basin_request_over_target": basin_request_af / CRSS_DEMAND_TARGET_AF,
                "has_efficient_system": agent_state.get("has_efficient_system", False),
                "below_minimum_utilisation": agent_state.get("below_minimum_utilisation", False),
                "utilisation_pct": (
                    agent_state.get("request", 0) / agent_state.get("water_right", 1) * 100
                    if agent_state.get("water_right", 0) > 0 else 0
                ),
                "magnitude_pct": appr.get("magnitude_pct"),
                "magnitude_pct_sampled": appr.get("magnitude_pct_sampled"),
                "magnitude_af": appr.get("magnitude_af"),
                "magnitude_class": appr.get("magnitude_class"),
                "magnitude_fallback": appr.get("magnitude_fallback", False),
                "is_exploration": appr.get("is_exploration", False),  # v12: Track ε-exploration
                "memory": mem_str,
            })

        # Print yearly summary
        n_agents = len(agents)
        decisions = [
            self.yearly_decisions.get((aid, year), {}).get("skill", "N/A")
            for aid in agents
        ]
        from collections import Counter
        counts = Counter(decisions)
        summary = " | ".join(f"{k}: {v}" for k, v in counts.most_common())
        drought = self.env.global_state.get("drought_index", 0)
        print(f"[Year {year}] {summary} (drought={drought:.2f})")

        # Batch year-end reflection
        if self.reflection_engine and self.reflection_engine.should_reflect("any", year):
            self._batch_reflect(year)

    def _batch_reflect(self, year: int):
        cfg = self.runner.broker.config.get_reflection_config()
        batch_size = cfg.get("batch_size", 10)
        candidates = []
        for aid, agent in self.runner.agents.items():
            if not getattr(agent, "is_active", True):
                continue
            mems = self.runner.memory_engine.retrieve(agent, top_k=10)
            if mems:
                # F08+F33 (2026-09-25 audit): every input below used to be
                # missing or in the wrong unit --
                # ``env.get_supply_ratio()`` does not exist on
                # IrrigationEnvironment (silent 1.0 fallback via hasattr),
                # ``last_decision``/``drought_count`` were never written to
                # custom_attributes (always "" / 0), and ``water_right``
                # is the raw acre-foot entitlement, not the 0-1 utilisation
                # fraction IrrigationAdapter.compute_importance expects --
                # so importance always landed on the adapter's fixed 0.90
                # and classify_emotion always returned a label outside
                # emotional_weights. Build the real, current-year values:
                # water_right_pct and supply_ratio from live env state,
                # recent_decision from the actual executed skill
                # (agent._last_action_context, set by
                # broker/core/experiment_runner.py:_apply_state_changes),
                # and drought_count from the cumulative counter post_year
                # maintains above.
                attrs = getattr(agent, "custom_attributes", {})
                agent_state = self.env.get_agent_state(aid)
                water_right = agent_state.get("water_right", 0) or 0
                request = agent_state.get("request", 0) or 0
                diversion = agent_state.get("diversion", 0) or 0
                action_ctx = getattr(agent, "_last_action_context", None) or {}
                # F08 code review (2026-09-25): diversion = request * (1 -
                # curtailment_ratio) is mathematically an exact tier ratio
                # (0.95/0.90/0.80/0.80...), but float64 division does not
                # always round-trip exactly -- measured 5-6% of random
                # requests landing on the wrong side of a 0.60/0.80
                # boundary in compute_importance's shortage branches purely
                # from float noise (the same class of bug F13 fixed in the
                # YAML assertion trigger). round(..., 6) removes that noise
                # without materially changing any real (non-boundary) ratio.
                #
                # Supply-side redesign (2026-09-25): agent_state here is read
                # after post_year's settle_year(), so diversion is the final
                # settled delivery for every agent (shortage tier, Powell
                # release limit, Mead availability), a continuous value.
                # Supply-side redesign (2026-09-25, spec M4): the adapter
                # reads the PROPOSED skill, the fallback flag and the unmet
                # fraction of the final settlement; recent_decision (the
                # executed skill) is kept for older readers.
                proposed, was_fallback = _proposed_and_fallback(action_ctx)
                agent_ctx = {
                    "water_right_pct": round(request / water_right, 6) if water_right > 0 else 0.5,
                    "supply_ratio": round(diversion / request, 6) if request > 0 else 1.0,
                    "unmet_frac": _unmet_frac(request, diversion),
                    "proposed_skill": proposed,
                    "was_fallback": was_fallback,
                    "years_farming": attrs.get("years_farming", 0),
                    "has_efficient_system": attrs.get("has_efficient_system", False),
                    "recent_decision": action_ctx.get("skill_name", ""),
                    "drought_count": getattr(agent, "drought_count", 0),
                    "cluster": attrs.get("cluster", ""),
                }
                candidates.append({
                    "agent_id": aid,
                    "memories": mems,
                    "context": agent_ctx,
                })

        if not candidates:
            return

        llm_call = self.runner.get_llm_invoke("irrigation_farmer")
        print(f"  [Reflection] {len(candidates)} agents in batches of {batch_size}...")
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i: i + batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(
                batch,
                year,
                reflection_questions=cfg.get("questions", []),
                persona_instruction=cfg.get("persona_instruction")
            )
            try:
                raw = llm_call(prompt)
                text = raw[0] if isinstance(raw, tuple) else raw
                insights = self.reflection_engine.parse_batch_reflection_response(
                    text, batch_ids, year
                )
                for aid, insight in insights.items():
                    if insight:
                        # Use adapter for dynamic importance instead of hardcoded 0.9
                        ctx_item = next((c for c in batch if c["agent_id"] == aid), None)
                        if ctx_item and ctx_item.get("context") and self.reflection_engine.adapter:
                            dynamic_imp = self.reflection_engine.compute_dynamic_importance(
                                ctx_item["context"]
                            )
                            insight.importance = dynamic_imp

                        self.reflection_engine.store_insight(aid, insight)
                        emotion = "major"
                        if self.reflection_engine.adapter and ctx_item and ctx_item.get("context"):
                            decision = ctx_item["context"].get("recent_decision", "")
                            emotion = self.reflection_engine.adapter.classify_emotion(
                                decision, ctx_item["context"]
                            )
                        self.runner.memory_engine.add_memory(
                            aid,
                            f"Consolidated Reflection: {insight.summary}",
                            {
                                # "importance", not "significance": HumanCentricMemoryEngine
                                # only reads metadata.get("importance", 0.5). See
                                # examples/irrigation_abm/tests/test_governance_mode_wiring.py::
                                # TestBatchReflectImportanceKey.
                                "importance": insight.importance,
                                "emotion": emotion,
                                "source": "personal",
                                "type": "reflection",
                            },
                        )
            except Exception as e:
                print(f"  [Reflection:Error] Batch {i // batch_size + 1}: {e}")
        print(f"  [Reflection] Year {year} complete.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    base = Path(__file__).parent

    # --- Output (moved early: a --coupling derived config file, below, is
    # written into this directory so it persists with the rest of the run's
    # artifacts instead of living in a temp dir) ---
    output_dir = Path(args.output) if args.output else base / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --config-dir lets a campaign point at an ISOLATED copy of the config tree so new
    # experiment arms never edit the frozen paper configs in examples/. Default is the
    # in-tree config dir, so every existing invocation is unchanged.
    config_dir = Path(args.config_dir).resolve() if args.config_dir else base / "config"
    if args.config_dir:
        # Every file this runner resolves off config_dir, so an incomplete copy is named
        # up front in one message rather than crashing partway through setup on whichever
        # file happens to be read first.
        missing = [f for f in ("agent_types.yaml", "skill_registry.yaml",
                               "prompts/irrigation_farmer.txt")
                   if not (config_dir / f).exists()]
        if missing:
            raise SystemExit(
                f"--config-dir {config_dir} is missing {missing}. An isolated config dir must be "
                "a complete copy of examples/irrigation_abm/config (including prompts/), not a "
                "partial overlay."
            )
        print(f"[Config] ISOLATED config dir: {config_dir}")
    ref_dir = PROJECT_ROOT / "ref"

    # --- Random seed ---
    seed = args.seed if args.seed is not None else random.randint(0, 1_000_000)
    random.seed(seed)
    np.random.seed(seed)

    # --- LLM config overrides ---
    from broker.utils.llm_utils import LLM_CONFIG
    if args.num_ctx:
        LLM_CONFIG.num_ctx = args.num_ctx
    if args.num_predict:
        LLM_CONFIG.num_predict = args.num_predict

    # --- Load config YAML (pilot phase selects config file) ---
    pilot_phase = args.pilot_phase

    # Reset module-level flags (safe for multi-run in same process)
    irr_validators.ENABLE_CONSECUTIVE_CAP = False
    irr_validators.ENABLE_ZERO_ESCAPE = False
    irr_validators.ENABLE_DEMAND_CEILING = True  # only gates a direct call; retired from dispatch

    # Ablation mode. Supply-side redesign (2026-09-25): demand_ceiling_stabilizer
    # and demand_floor_stabilizer are no longer dispatched (the basin limit is
    # physical availability in the water balance), so "no_demand_ceiling" is
    # now the default behaviour; the choice is kept so existing launchers
    # still parse.
    if getattr(args, "ablation_mode", None) == "no_demand_ceiling":
        irr_validators.ENABLE_DEMAND_CEILING = False
        print("[Ablation] no_demand_ceiling: already the default (the ceiling is retired from dispatch)")

    # Always use main config (pilot config merged into agent_types.yaml)
    agent_config_path = config_dir / "agent_types.yaml"
    if pilot_phase:
        print(f"[Pilot] Phase {pilot_phase}: using main config (governance levels set in agent_types.yaml)")

    # Enable Phase C/D validators via module-level flags
    if pilot_phase in ("C", "D"):
        if args.workers > 1:
            print("[Pilot] WARNING: Phase C/D consecutive tracker is not thread-safe, forcing --workers 1")
            args.workers = 1
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        print("[Pilot] Phase C validator enabled: consecutive_increase_cap")
    if pilot_phase == "D":
        irr_validators.ENABLE_ZERO_ESCAPE = True
        print("[Pilot] Phase D validator enabled: zero_escape")

    with open(agent_config_path, "r", encoding="utf-8") as f:
        cfg_data = yaml.safe_load(f)
    # PR-6 review P1-e: refuse a profile this config does not declare. This
    # runner takes `--governance-mode` as a FREE STRING (any custom profile the
    # YAML defines), so there is no `choices=` list to catch a typo, and
    # `get_thinking_rules` falls back to `default` in silence — a whole sweep
    # runs the wrong rule set and every artifact looks healthy. Checked in the
    # runner rather than by turning on
    # `global_config.governance.require_profile`, which lives inside the frozen
    # config and would change its contents.
    from broker.utils.agent_config import assert_governance_profile_declared
    assert_governance_profile_declared(
        cfg_data, args.governance_mode, "irrigation_farmer", agent_config_path)

    # --- v0.6 coupling-layer flag (--coupling CLI flag, default OFF) ---
    # May repoint agent_config_path at a derived config copy under output_dir
    # (never the frozen on-disk file) - see _resolve_irrigation_coupling's
    # docstring. original_agent_config_path is kept so the manifest can
    # record where the derived copy came from.
    original_agent_config_path = agent_config_path
    agent_config_path, coupling_active = _resolve_irrigation_coupling(
        cfg_data, agent_config_path, args.coupling, output_dir)
    if coupling_active:
        print("[coupling] enable=True - v0.6 EnvironmentCouplingAdapter wraps IrrigationEnvironment")

    global_cfg = cfg_data.get("global_config", {})

    # --- Optional: strip magnitude_pct from schema to reduce context size ---
    if args.no_magnitude:
        shared_fields = cfg_data.get("shared", {}).get("response_format", {}).get("fields", [])
        cfg_data["shared"]["response_format"]["fields"] = [
            f for f in shared_fields if f.get("key") != "magnitude_pct"
        ]
        print("[Config] magnitude_pct field removed from response schema (--no-magnitude)")

    # --- Load prompt template ---
    prompt_template_path = config_dir / "prompts" / "irrigation_farmer.txt"
    prompt_template = prompt_template_path.read_text(encoding="utf-8")

    # --- Load skill registry ---
    registry = SkillRegistry()
    registry.register_from_yaml(str(config_dir / "skill_registry.yaml"))

    # --- Create agent profiles ---
    if args.real:
        # Real 78-agent CRSS data
        from examples.irrigation_abm.irrigation_personas import (
            create_profiles_from_data,
        )
        params_csv = str(ref_dir / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv")
        crss_db = str(ref_dir / "CRSS_DB" / "CRSS_DB")
        profiles = create_profiles_from_data(
            params_csv_path=params_csv,
            crss_db_dir=crss_db,
            rng=np.random.default_rng(seed),
        )
        print(f"[Data] Loaded {len(profiles)} real CRSS agents from paper data")
    else:
        profiles = _create_synthetic_profiles(args.agents, seed)
        print(f"[Data] Created {len(profiles)} synthetic agents")

    # --- Optional cluster rebalancing ---
    if args.rebalance_clusters:
        from collections import Counter
        before = Counter(p.cluster for p in profiles)

        # Phase 1 + CRSS: Target 50%-30%-20% distribution
        from examples.irrigation_abm.irrigation_personas import rebalance_to_target
        target_dist = {
            "aggressive": 0.50,
            "forward_looking_conservative": 0.30,
            "myopic_conservative": 0.20,
        }

        # Runtime assertion: Verify target_dist matches synthetic initialization in irrigation_env.py
        # (Lines 251-254: clusters = ["aggressive"] * (n // 2) + ["forward"] * (n * 3 // 10) + ["myopic"] * (n * 2 // 10))
        synthetic_dist = {"aggressive": 0.50, "forward_looking_conservative": 0.30, "myopic_conservative": 0.20}
        assert target_dist == synthetic_dist, \
            f"target_dist {target_dist} must match synthetic initialization percentages {synthetic_dist}"

        rebalance_to_target(profiles, target_dist, rng=np.random.default_rng(seed))

        after = Counter(p.cluster for p in profiles)
        print(f"[Rebalance] Clusters: {dict(before)} → {dict(after)} (target: 50%-30%-20%)")

    # The action magnitude follows Hung and Yang (2021): per-agent mu, sigma
    # and grid step come from the profiles (create_profiles_from_data), not
    # from persona config (the former persona_scale / skill_magnitude bands
    # were removed on 2026-09-26).

    # --- Create environment and initialize ---
    # PR-9 coupling-retrofit (F1): opt-in fail-loud physical-state guard,
    # default OFF (byte-identical to pre-PR-9 behaviour). See
    # AgentTypeConfig.get_coupling_context_contract for what the flag
    # does and examples/irrigation_abm/irrigation_coupling.py for the guard.
    # run_fql_baseline.py has the SAME two lines (review P1-a): a flag that
    # reached only the governed arm would make the two arms of a comparison
    # differ in something other than governance. run_ungoverned_
    # experiment.py no longer has its own copy (irrigation case-alignment,
    # 2026-09) -- it is a thin wrapper that forwards to THIS main(), so it
    # shares this guard by construction rather than by keeping a duplicate
    # in sync. AgentTypeConfig.load caches per resolved path, so this is one
    # parse per config per process, not one per call site.
    from broker.utils.agent_config import AgentTypeConfig
    coupling_contract_active = AgentTypeConfig.load(
        str(agent_config_path)
    ).get_coupling_context_contract()
    if coupling_contract_active:
        print("[coupling] context_contract=True — get_agent_context() fails loud on a missing field")
    config = WaterSystemConfig(seed=seed)
    env = IrrigationEnvironment(config, coupling_contract_active=coupling_contract_active)
    env.initialize_from_profiles(profiles)

    # Load real CRSS precipitation projections when available
    if args.real:
        precip_csv = ref_dir / "CRSS_DB" / "CRSS_DB" / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
        if precip_csv.exists():
            env.load_crss_precipitation(str(precip_csv))
            print(f"[Data] Loaded real CRSS precipitation projections (2017-2060)")

    # --- Convert profiles → BaseAgent instances ---
    agents = _profiles_to_agents(profiles)

    # --- Memory engine (Pillar 2) --- must be created before ctx_builder
    irr_cfg = cfg_data.get("irrigation_farmer", {})
    irr_mem = irr_cfg.get("memory", {})
    gm = global_cfg.get("memory", {})
    rw = irr_mem.get("retrieval_weights", {})

    # --- Domain adapter (literature-informed reflection + memory) ---
    irrigation_adapter = IrrigationAdapter()
    adapter_rw = irrigation_adapter.retrieval_weights

    memory_engine = HumanCentricMemoryEngine(
        window_size=args.window_size,
        top_k_significant=gm.get("top_k_significant", 2),
        consolidation_prob=gm.get("consolidation_probability", 0.7),
        consolidation_threshold=gm.get("consolidation_threshold", 0.6),
        decay_rate=gm.get("decay_rate", 0.1),
        emotional_weights=irr_mem.get("emotional_weights"),
        source_weights=irr_mem.get("source_weights"),
        # Without this, _classify_emotion() (broker/components/memory/
        # engines/humancentric.py) falls back to its own generic keyword
        # bank (critical/major/positive/shift), whose labels don't match
        # the emotional_weights keys above (water_crisis/strategic_choice/
        # positive_outcome/social_feedback/baseline_observation) -- every
        # classification then misses and silently uses the 0.1 fallback.
        emotion_keywords=irr_mem.get("emotion_keywords"),
        W_recency=rw.get("recency", adapter_rw.get("W_recency", 0.3)),
        W_importance=rw.get("importance", adapter_rw.get("W_importance", 0.4)),
        W_context=rw.get("context", adapter_rw.get("W_context", 0.3)),
        ranking_mode=irr_mem.get("ranking_mode", "weighted"),
        seed=args.memory_seed,
        # Reserved retrieval slot(s) by memory type (irrigation: one of the
        # top-3 slots for a reflection when one exists). None = off.
        reserve_types=irr_mem.get("reserve_types"),
    )
    print(f"[Pillar 2] HumanCentricMemoryEngine (window={args.window_size}, mode={memory_engine.ranking_mode})")

    # --- Context builder ---
    ctx_builder = TieredContextBuilder(
        agents=agents,
        hub=None,  # No social graph for irrigation
        skill_registry=registry,
        prompt_templates={
            "irrigation_farmer": prompt_template,
            "default": prompt_template,
        },
        yaml_path=str(agent_config_path),
        memory_engine=memory_engine,
    )

    # --- Feedback dashboard (config-driven env feedback for agents) ---
    feedback_cfg = irr_cfg.get("feedback", {})
    _metrics_tracker = None  # set below if feedback is configured
    if feedback_cfg.get("tracked_metrics"):
        from broker.components.analytics.feedback import (
            AgentMetricsTracker,
            FeedbackDashboardProvider,
        )
        metric_names = [m["name"] for m in feedback_cfg["tracked_metrics"]]
        _metrics_tracker = AgentMetricsTracker(
            metric_names, window=feedback_cfg.get("trend_window", 5)
        )
        ctx_builder.providers.append(
            FeedbackDashboardProvider(_metrics_tracker, feedback_cfg)
        )
        print(f"[Feedback] Dashboard enabled: metrics={metric_names}, "
              f"assertions={len(feedback_cfg.get('assertions', []))}")

    # --- Performance tuning ---
    from broker.utils.performance_tuner import get_optimal_config, apply_to_llm_config
    perf = get_optimal_config(args.model)
    apply_to_llm_config(perf, num_ctx_override=args.num_ctx, num_predict_override=args.num_predict)

    # --- Build experiment ---
    # governance_mode == "disabled" is the single unified path for what used
    # to be a SEPARATE script (run_ungoverned_experiment.py): besides the
    # YAML thinking/identity rules being empty (agent_types.yaml's
    # governance.disabled block), the irrigation-specific physical/social/
    # behavioral checks in irrigation_governance_validator (water right cap,
    # drought severity, magnitude cap, demand floor/ceiling, curtailment
    # awareness, compact allocation, ...) are a SECOND, independent
    # governance layer, unconditionally wired in regardless of
    # governance_mode until this fix. An ungoverned run must have neither.
    custom_validators = (
        [] if args.governance_mode == "disabled" else [irrigation_governance_validator]
    )
    builder = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(env)
        .with_context_builder(ctx_builder)
        .with_skill_registry(registry)
        .with_memory_engine(memory_engine)
        .with_governance(args.governance_mode, str(agent_config_path))
        .with_custom_validators(custom_validators)
        .with_exact_output(str(output_dir))
        .with_workers(args.workers)
        .with_seed(seed)
    )
    if coupling_active:
        from examples.irrigation_abm.coupling_modules import (
            IrrigationBundle,
            build_irrigation_coupling_contract,
        )
        builder = builder.with_coupling(
            build_irrigation_coupling_contract(env), IrrigationBundle(env), domain="irrigation")
    runner = builder.build()
    if agent_config_path != original_agent_config_path:
        # Same hook run_flood.py uses for --retry-feedback-mode
        # (runner.broker._retry_feedback_mode, read generically by
        # ExperimentRunner._collect_reproducibility_metadata): set an
        # attribute directly on the already-built broker, read by the
        # generic manifest builder's derived_from_config field (next to
        # agent_types_config) - no broker init-time change needed.
        runner.broker._derived_from_config = str(original_agent_config_path)

    # --- Reflection engine (Pillar 2) ---
    refl_cfg = global_cfg.get("reflection", {})
    reflection_engine = ReflectionEngine(
        reflection_interval=refl_cfg.get("interval", 1),
        max_insights_per_reflection=2,
        insight_importance_boost=refl_cfg.get("importance_boost", 0.9),
        output_path=str(output_dir / "reflection_log.jsonl"),
        adapter=irrigation_adapter,
    )
    print(f"[Pillar 2] ReflectionEngine (interval={reflection_engine.reflection_interval}, adapter=IrrigationAdapter)")

    # --- Inject lifecycle hooks ---
    hooks = IrrigationLifecycleHooks(env, runner, profiles, reflection_engine, output_dir)
    # Attach feedback tracker so pre_year can record metrics
    hooks.metrics_tracker = _metrics_tracker
    hooks.feedback_config = feedback_cfg
    hooks.rejection_line_style = irr_mem.get("rejection_line_style", "neutral")
    if hooks.rejection_line_style not in ("neutral", "explicit"):
        raise SystemExit(
            f"irrigation_farmer.memory.rejection_line_style "
            f"{hooks.rejection_line_style!r} is not 'neutral' or 'explicit'."
        )
    runner.hooks.update({
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year,
    })

    # --- Reset pilot state ---
    reset_consecutive_tracker()

    # --- Run ---
    n_real = "real" if args.real else "synthetic"
    phase_str = f" | pilot={pilot_phase}" if pilot_phase else ""
    print(
        f"--- Irrigation ABM | {args.model} | {len(profiles)} agents ({n_real}) "
        f"| {args.years} years | seed={seed}{phase_str} ---"
    )
    runner.run(llm_invoke=create_llm_invoke(args.model, verbose=False))

    # Finalize audit
    if runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    # Save simulation log
    if hooks.logs:
        # Sanitize text for CSV compatibility
        sanitized_logs = []
        for log in hooks.logs:
            sanitized_log = {
                k: (v.replace('\n', ' ').replace('\r', ' ').strip() if isinstance(v, str) else v)
                for k, v in log.items()
            }
            sanitized_logs.append(sanitized_log)
        pd.DataFrame(sanitized_logs).to_csv(output_dir / "simulation_log.csv", index=False)

    GovernanceAuditor().print_summary()
    print(f"--- Complete! Results in {output_dir} ---")


def parse_args():
    p = argparse.ArgumentParser(
        description="Irrigation ABM Experiment (Hung 2021 - WAGF Pipeline)"
    )
    p.add_argument("--model", default="gemma3:1b")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--agents", type=int, default=5, help="Number of synthetic agents (ignored if --real)")
    p.add_argument("--real", action="store_true", help="Use real 78-agent CRSS data from paper")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--memory-seed", type=int, default=42)
    p.add_argument("--window-size", type=int, default=5)
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--num-ctx", type=int, default=None)
    p.add_argument("--num-predict", type=int, default=None)
    p.add_argument("--rebalance-clusters", action="store_true",
                   help="Rebalance cluster assignment so each cluster has >=15%% of agents")
    p.add_argument("--no-magnitude", action="store_true",
                   help="Disable magnitude_pct output (reduces context size)")
    p.add_argument("--pilot-phase", type=str, default=None,
                   choices=["A", "B", "C", "D"],
                   help="Pilot phase: A=baseline, B=BLOCK+retry, C=+consecutive_cap, D=+zero_escape")
    p.add_argument("--ablation-mode", type=str, default=None,
                   choices=["no_demand_ceiling"],
                   help="Kept for older launchers: no_demand_ceiling is now the default "
                        "(demand_ceiling_stabilizer is retired from dispatch).")
    # P0-1d: the governance profile was hardcoded to "strict" at the builder
    # call below, so the published irrigation corpus has only strict + disabled
    # arms and no enforcement-gradient condition could be run at all. Named
    # profiles resolve from agent_types.yaml's governance block; GovernanceProfiles
    # carries ConfigDict(extra="allow"), so new arm profiles are pure YAML
    # additions. Default "strict" reproduces every existing run byte-identically.
    p.add_argument("--config-dir", type=str, default=None,
                   help="Isolated config directory (complete copy of config/). Lets a campaign "
                        "run new arms without editing the frozen paper configs. Default: in-tree.")
    p.add_argument("--governance-mode", type=str, default="strict",
                   help="Governance profile name from agent_types.yaml "
                        "(strict | relaxed | grounded_v1 | disabled | any custom "
                        "profile defined there). A name the config does not "
                        "declare is REFUSED at startup rather than falling back "
                        "to 'default' silently.")
    p.add_argument("--coupling", action="store_true",
                   help="Enable the v0.6 coupling layer: wraps IrrigationEnvironment "
                        "in broker.coupling.EnvironmentCouplingAdapter using the "
                        "IrrigationBundle + contract from coupling_modules.py. Default "
                        "OFF; equivalent to global_config.coupling.enable: true in the "
                        "agent_types YAML, and OVERRIDES an explicit enable: false already "
                        "there (source is then reported as cli, not yaml). Writes a "
                        "derived config copy into --output (never edits the original file). "
                        "With the contract on, simulation_log.csv is byte-identical to a "
                        "contract-off run at the same seed/years/agents, and the governance "
                        "audit CSV is identical under broker.tools.compare_audit_csv apart "
                        "from two added world_request / world_contention_rule columns.")
    return p.parse_args()


if __name__ == "__main__":
    main()
