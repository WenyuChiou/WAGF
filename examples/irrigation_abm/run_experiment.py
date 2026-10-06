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
import json
import random
import re
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
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    build_narrative_persona,
    build_water_situation_text,
    build_action_outcome_feedback,
    build_option_notes,
    build_option_texts,
    build_simulation_log_row,
    create_profiles_from_csv,
    dashboard_sharing_flags,
    describe_gap_reason,
    read_lake_mead_level_for_log,
    rebalance_clusters,
)
from broker.core.experiment import ExperimentBuilder
from broker.components.memory.engine import HumanCentricMemoryEngine
from broker.components.cognitive.reflection import ReflectionEngine, store_reflection_memory
from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter
from broker.components.governance.registry import SkillRegistry
from broker.components.context.builder import TieredContextBuilder
from broker.interfaces.skill_types import ExecutionResult
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor
from examples.irrigation_abm.validators.irrigation_validators import (
    ALL_IRRIGATION_CHECKS,
    irrigation_governance_validator,
    supply_rule_fields,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# v3 (WP2 spec 2.2, 2026-09-29): three skills -- the LLM chooses the
# direction only, the environment draws the whole Hung and Yang
# magnitude (replaces the five-skill "increase_large"/"increase_small"/
# "decrease_small"/"decrease_large" set).
IRRIGATION_SKILLS = [
    "increase_demand", "maintain_demand", "decrease_demand",
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
            # WP1b re-review (MEDIUM 2, 2026-09-29): a mock-smoke-only
            # profile must NOT be assigned a real sub-basin (precip_group
            # stays None) -- an earlier version of this fix round-robinned
            # the nine real ones, which put a synthetic agent inside a REAL
            # sub-basin's request cap (Agent_002 landing in UT2 and getting
            # 29 percent of its request, a number that describes UT2's real
            # farms, not this mock agent). synthetic_no_subbasin=True
            # instead routes it to IrrigationEnvironment.
            # initialize_from_profiles's unconstrained pool bucket
            # (logged once there), the correct "this agent has no real
            # location" treatment.
            precip_group=None,
            synthetic_no_subbasin=(basin == "upper_basin"),
            # WP1c review round 2 (LOW 6): this mock agent's id ("Agent_NNN")
            # is never one of the 22 real Lower Basin names in
            # lb_priority_split_v3.csv either, regardless of basin -- same
            # "this agent has no real location/entitlement" treatment as
            # synthetic_no_subbasin above, unconditional on basin since it
            # is harmless (unused) for an Upper Basin profile.
            synthetic_no_priority_split=True,
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


# Every stored reflection starts with this; the full line is
# "Consolidated Reflection (written in {calendar year}): {summary}" (spec 4.7).
_REFLECTION_MEMORY_PREFIX = "Consolidated Reflection"

# Stripped from both ends of a summary before it is stored (spec 4.7): quotes,
# whitespace and the trailing comma of a JSON-residue copy ('"...",', L3 M8).
_REFLECTION_STRIP_CHARS = ' \t\n"\'“”‘’,'

# A figure a reflection summary can quote (spec 4.7, review HIGH 1): a number
# with thousands separators ("20,155"), a plain number, optionally followed by
# a unit: "%" or "percent" (a share), "million" (million acre-ft), or an
# acre-ft unit ("acre-ft", "acre-feet", "AF"). Not preceded by a letter,
# digit, point or comma, so "UT2" or the tail of a longer number never match.
_FIGURE = re.compile(
    r"(?<![\w.,])(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<unit>\s*(?:%|percent\b|million\b|acre[- ]?f(?:ee|oo)?t\b|af\b))?",
    re.IGNORECASE,
)

# A summary figure within this relative distance of a figure of the same kind
# in the agent's own memory text counts as that figure, rounded (review HIGH 1:
# "about 20,000 acre-ft" for a memory line's 20,155 is the agent's own figure).
_FIGURE_TOLERANCE = 0.05


def _normalize_reflection_text(text: str) -> str:
    """Collapse internal whitespace and strip quotes, whitespace and commas
    from both ends (spec 4.7), so a reflection is stored as one clean line."""
    collapsed = " ".join((text or "").split())
    return collapsed.strip(_REFLECTION_STRIP_CHARS)


def _is_reflection_memory(item: Any) -> bool:
    """True for a stored reflection (a retrieved memory payload carries its
    content but not its ``type``, so the fixed prefix identifies it)."""
    content = item.get("content", "") if isinstance(item, dict) else str(item)
    return str(content).startswith(_REFLECTION_MEMORY_PREFIX)


def _figures(text: str) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    """(volumes, percentages) quoted in ``text``, each as (as written, value).

    A volume is a number with thousands separators, a plain number of four or
    more digits that is not a calendar year (1900 to 2100), or any number
    followed by an acre-ft unit or "million" (scaled to acre-ft). A percentage
    is a number followed by "%" or "percent". Any other bare number (a count,
    a tier, a day of the month, a year) is not a figure."""
    volumes: List[Tuple[str, float]] = []
    percents: List[Tuple[str, float]] = []
    for m in _FIGURE.finditer(text):
        num = m.group("num")
        unit = (m.group("unit") or "").strip().lower()
        value = float(num.replace(",", ""))
        written = m.group(0).strip()
        if unit in ("%", "percent"):
            percents.append((written, value))
        elif unit == "million":
            volumes.append((written, value * 1e6))
        elif unit:
            volumes.append((written, value))
        elif "," in num:
            volumes.append((written, value))
        elif "." not in num and len(num) >= 4 and not (len(num) == 4 and 1900 <= value <= 2100):
            volumes.append((written, value))
    return volumes, percents


def _near(value: float, pool: List[float]) -> bool:
    return any(abs(value - ref) <= _FIGURE_TOLERANCE * abs(ref) for ref in pool)


def _foreign_figures(summary: str, own_text: str) -> List[str]:
    """Figures in ``summary`` that match no figure of the same kind in
    ``own_text`` (the agent's own memory lines the reflection was written
    from), within ``_FIGURE_TOLERANCE``. A reflection that quotes one is not
    stored (spec 4.7; L3 M8: 201 prompts showed an acre-ft figure that
    belonged to another agent).

    Review HIGH 1 (2026-09-30): rounding is tolerated ("about 20,000
    acre-ft" matches a memory line's 20,155), and figures written without
    separators ("14420 acre-ft") and percentages are checked too. A
    percentage also matches the complement of a memory percentage (a
    delivered share is 100 minus the unmet share the memory line states), and
    0 and 100 percent always match (a full delivery or none, nobody's own
    figure)."""
    own_volumes, own_percents = _figures(own_text)
    volume_pool = [v for _, v in own_volumes]
    percent_pool = [p for _, p in own_percents] + [100.0 - p for _, p in own_percents] + [0.0, 100.0]
    volumes, percents = _figures(summary)
    return ([w for w, v in volumes if not _near(v, volume_pool)]
            + [w for w, p in percents if not _near(p, percent_pool)])


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

        Delegates to the shared ``read_lake_mead_level_for_log`` (2026-09-27
        fix) so this runner and ``run_fql_baseline.py`` fail the same way;
        see that function's docstring for the coupling-contract guard this
        preserves (Review P1-b).
        """
        return read_lake_mead_level_for_log(self.env)

    def _retries_name_rules(self) -> bool:
        """False in the placebo and silent arms, whose retry prompts carry no
        rule text: their memory line of an overruled year then says "under a
        governance rule" instead of naming the rule (spec 4.5). Read from the
        broker at each call, so a --retry-feedback-mode override applies. A
        runner without a broker, or a broker without the mode, raises (review
        LOW 10): falling back to "full" would name rules in a placebo run."""
        broker = getattr(self.runner, "broker", None)
        if broker is None or not hasattr(broker, "_retry_feedback_mode"):
            raise RuntimeError(
                "IrrigationLifecycleHooks: the runner's broker has no "
                "_retry_feedback_mode; refusing to guess whether this arm's "
                "retries name the rules."
            )
        mode = broker._retry_feedback_mode
        if mode not in ("full", "placebo", "silent"):
            raise ValueError(f"IrrigationLifecycleHooks: unknown _retry_feedback_mode {mode!r}.")
        return mode == "full"

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
            # the "Last year you requested ..." sentence (spec 4.3); in the
            # first year there is none and the sentence states the 2018 use.
            water_situation = build_water_situation_text(
                ctx, last_year=getattr(agent, "_last_year_outcome", None)
            )
            agent.water_situation_text = water_situation

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
                # Re-review 2026-09-29 (NIT, then round 4 LOW 2): read by
                # curtailment_awareness_check's acre-feet wording (the
                # F04 startup check caught this key having no producer).
                # Direct index, not .get(..., 0): get_agent_context sets
                # this unconditionally (HIGH 2), so a missing value here
                # is a real wiring defect, not a legitimate "no shortage"
                # case to silently paper over with a fabricated 0.
                "lb_shortage_volume_maf": ctx["lb_shortage_volume_maf"],
                # WP1b re-review (HIGH 1, 2026-09-29): read by
                # _sharing_sentence (irrigation_validators.py) to name WHO
                # shares a shortage with this agent. Without these two,
                # _sharing_sentence could not tell a sub-basin-scoped
                # shortfall from a basin-wide one and fell back to naming
                # "other Upper Basin users" for every Upper Basin agent,
                # even one (e.g. a UT1 agent) whose real sharing group is
                # its own ten-or-so-member sub-basin.
                "supply_group": ctx.get("supply_group"),
                "ub_subbasin_member_count": ctx.get("ub_subbasin_member_count"),
                # WP2 (spec 2.6): {skill_id: option text} computed from
                # THIS year's base (last year's committed delivery,
                # agent_state["base_af"] -- spec 2.1) and this agent's own
                # water right / floor. SkillFilterMixin._inject_options_text
                # (broker/core/_skill_filtering.py) reads this ahead of the
                # skill registry's static description once it reaches
                # context["state"] via custom_attributes (AttributeProvider).
                # WP2 review round 1 (LOW 8): direct indexing, not
                # .get(key, default) -- IrrigationEnvironment._reset_requests_to_base
                # sets base_af for every agent every year, and
                # get_agent_context always sets water_right, so a missing
                # key here is a real wiring defect, not a legitimate
                # "agent has none yet" case to silently paper over with 0.
                "option_text_overrides": build_option_texts(
                    profile,
                    base=agent_state["base_af"],
                    water_right=ctx["water_right"],
                    floor=ctx["water_right"] * self.env.config.min_utilisation_fraction,
                ),
                # WP3 (spec 3.3): read by describe_gap_reason in the supply
                # rule's block message when this agent's own junior-priority
                # water is cut (gap code lb_junior_tier_cut, item 22); None
                # for an Upper Basin agent. Direct index: get_agent_context
                # always sets it.
                "lb_junior_tier_cut_fraction": ctx["lb_junior_tier_cut_fraction"],
                # WP3 (spec 3.3): the supply rule's inputs, computed once from
                # this year's provisional settlement at every agent's keep
                # request (irrigation_validators.supply_rule_fields). The
                # rule reads them from here, and the audit writes them as
                # state_<key> columns (global_config.audit.state_columns) in
                # EVERY arm, so the disabled arm can be scored post hoc on
                # the same numbers.
                **supply_rule_fields(ctx, agent_state),
            }
            # The supply rule's text says "the {keep} acre-ft you received
            # last year": WP2 (spec 2.1) resets every request to last year's
            # receipt before the provisional settlement, so the keep request
            # IS the base. A mismatch means that reset did not run (a
            # hold_requests_fixed replay, which this runner refuses above).
            if abs(validator_fields["supply_keep_request_af"] - agent_state["base_af"]) > 1e-6:
                raise ValueError(
                    f"{aid}: keep request {validator_fields['supply_keep_request_af']} "
                    f"differs from last year's receipt base_af={agent_state['base_af']}; "
                    "the WP2 reset to the base did not run before this decision."
                )
            for key, value in validator_fields.items():
                setattr(agent, key, value)
            if hasattr(agent, "custom_attributes"):
                agent.custom_attributes.update(validator_fields)
            # Spec item 29e (refined 2026-09-30): the random-step line after
            # the options names only the directions the menu offers (the
            # identity rules hide an increase exactly when at_allocation_cap
            # and a decrease exactly when below_minimum_utilisation, above);
            # the item-23 sentence appears only when an increase is offered
            # and last year's delivery was below its request.
            agent.option_notes = build_option_notes(
                increase_offered=not validator_fields["at_allocation_cap"],
                decrease_offered=not validator_fields["below_minimum_utilisation"],
                last_year=getattr(agent, "_last_year_outcome", None),
            )

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
                # post_year(year-1) always runs before pre_year(year) in
                # ExperimentRunner.run; a missing snapshot means that order
                # broke, and the stale live values are not last year's (WP4:
                # no fallback to them).
                snapshot = getattr(agent, "_last_year_outcome", None)
                if not snapshot:
                    raise RuntimeError(
                        f"{aid}: pre_year({year}) found no last-year snapshot; "
                        f"post_year({year - 1}) must run first."
                    )
                prev_request = snapshot["request"]
                prev_diversion = snapshot["diversion"]
                action_ctx = getattr(agent, '_last_action_context', None)
                # ExperimentRunner._apply_state_changes stamps the context
                # with the loop year of a decision that EXECUTED; a year in
                # which nothing executed (an ABORTED decision) leaves an older
                # context behind, which must not be reported as last year's
                # action (WP6 P5(b) finding). The request then stayed at the
                # base the environment reset it to.
                decision_read = bool(action_ctx) and action_ctx.get("year") == snapshot["year"]
                if not decision_read:
                    action_ctx = None
                feedback = build_action_outcome_feedback(
                    action_ctx=action_ctx,
                    # WP4 (spec 4.5, L3 M14): calendar years, as everywhere
                    # else in the prompt.
                    year=snapshot["calendar_year"],
                    request=prev_request,
                    diversion=prev_diversion,
                    preceding_factor=snapshot["preceding_factor"],
                    # F15: the Lower Basin signal is Lake Mead, not precipitation.
                    basin=ctx["basin"],
                    # The past-tense form of the reason the situation text and
                    # the rule messages use (spec 4.4).
                    gap_reason=describe_gap_reason(snapshot, "past"),
                    rejection_line_style=self.rejection_line_style,
                    # Spec 4.5: placebo and silent retries name no rule, so
                    # neither does their memory line (L3 M13).
                    name_rule=self._retries_name_rules(),
                    subbasin=snapshot.get("supply_group") is not None,
                    decision_read=decision_read,
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
                    # Item 36b: the calendar year this outcome line is
                    # ABOUT (same value the line itself names), read by
                    # HumanCentricMemoryEngine's decay_by_calendar_year
                    # option (default off elsewhere; on in irrigation).
                    "year": snapshot["calendar_year"],
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
            # Review 2026-09-28 (fix 5): the agent's own precipitation and
            # flag for the year (spec 1.6), for the simulation_log.csv
            # columns -- frozen for the whole year (advance_year sets
            # them once), so this is the same value the agent's own
            # decision saw, not a re-roll.
            agent_context = self.env.get_agent_context(aid)

            # F05 (2026-09-25 audit): snapshot THIS year's own outcome now.
            # request/diversion/drought_index/preceding_factor are all
            # correct for year `year` at this point (this year's decision
            # has executed and been settled, env.advance_year(year+1) has not
            # run yet). pre_year(year+1) reads this snapshot for its "last
            # year" memory line instead of re-querying live env state. Taken
            # from the SAME agent_state simulation_log.csv logs below, so
            # memory and the CSV always agree.
            agent._last_year_outcome = {
                "year": year,
                # WP4 (spec 4.5): the calendar year the memory line names.
                "calendar_year": self.env.current_year,
                "request": agent_state.get("request", 0),
                "diversion": agent_state.get("diversion", 0),
                "gap_reason": agent_state.get("gap_reason", "none"),
                "curtailment_ratio": agent_state.get("curtailment_ratio", 0),
                "shortage_tier": self.env.institutions.get("colorado_compact", {}).get("shortage_tier", 0),
                "drought_index": self.env.global_state.get("drought_index", 0),
                # WP4: the agent's OWN flag (its sub-basin's for the Upper
                # Basin, spec 1.6), the one its situation text showed; the
                # snapshot read the basin-level legacy flag before, so an
                # Upper Basin memory line could contradict the prompt.
                "preceding_factor": agent_context["preceding_factor"],
                # WP1b re-review (MEDIUM 5, 2026-09-29): describe_gap_reason
                # needs this to pick the single-member (UT2) wording for
                # both the "Last year ..." situation-text sentence and the
                # memory line, which both read this same F05 snapshot.
                "ub_subbasin_member_count": agent_context.get("ub_subbasin_member_count"),
                # WP4: describe_gap_reason's junior-priority phrase states
                # the settled cut share (item 22). It was missing here, so a
                # --real run raised in the year after the first tier year.
                "lb_junior_tier_cut_fraction": agent_state.get("lb_junior_tier_cut_fraction"),
                # WP4: whether the Upper Basin memory line may say "your
                # sub-basin" (None for a synthetic mock agent).
                "supply_group": agent_context.get("supply_group"),
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
            # WP4 (spec 4.6): the row is labelled with the calendar year, and
            # the hidden flags that pick the warning's "who shares" wording
            # come from this year's settled gap_reason.
            if self.metrics_tracker is not None:
                settled = {
                    "current_request": agent_state.get("request", 0),
                    "current_diversion": agent_state.get("diversion", 0),
                    # Spec item 29f: whether a declared shortage can cut this
                    # agent's water picks the Lower Basin warning's wording.
                    **dashboard_sharing_flags({
                        **agent_state,
                        "lb_junior_entitlement_af": agent_context["lb_junior_entitlement_af"],
                    }),
                }
                fb_metrics = {}
                for m_cfg in self.feedback_config.get("tracked_metrics", []):
                    src = m_cfg["source"]
                    fb_metrics[m_cfg["name"]] = float(settled.get(src, agent_state.get(src, 0)) or 0)
                self.metrics_tracker.record(aid, self.env.current_year, fb_metrics)

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
            self.logs.append(build_simulation_log_row(
                agent_id=aid,
                year=year,
                cluster=profile.cluster if profile else "unknown",
                basin=profile.basin if profile else "unknown",
                yearly_decision=skill or "N/A",
                wsa_label=appr.get("wsa_label", "N/A"),
                aca_label=appr.get("aca_label", "N/A"),
                agent_state=agent_state,
                drought_index=self.env.global_state.get("drought_index", 0),
                shortage_tier=self.env.institutions.get("colorado_compact", {}).get("shortage_tier", 0),
                lake_mead_level=self._log_lake_mead_level(),
                mead_storage_maf=self.env._mead_storage[-1] if self.env._mead_storage else 0,
                settlement=settlement,
                basin_request_af=basin_request_af,
                magnitude_pct=appr.get("magnitude_pct"),
                magnitude_pct_sampled=appr.get("magnitude_pct_sampled"),
                magnitude_af=appr.get("magnitude_af"),
                magnitude_class=appr.get("magnitude_class"),
                magnitude_fallback=appr.get("magnitude_fallback", False),
                is_exploration=appr.get("is_exploration", False),  # v12: Track ε-exploration
                memory=mem_str,
                # WP2 (spec 2.1): the keep request this year started from --
                # last year's committed delivery, set once a year by
                # IrrigationEnvironment._reset_requests_to_base.
                base_af=agent_state.get("base_af"),
                precipitation_mm=agent_context.get("precipitation"),
                precipitation_flag=agent_context.get("precipitation_flag"),
            ))

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
        """Year-end reflection (spec 4.7; L3 M8, D11; PI item 8).

        One agent per call (``global_config.reflection.batch_size: 1``). The
        input is what the memory engine retrieves for the agent at the end of
        the year (legacy mode: the 5 most recent working items plus up to 2
        long-term items of highest decayed importance; the ``top_k`` passed
        below is ignored in that mode), with every earlier reflection
        dropped, so a reflection is written from outcome lines only and
        cannot restate an old lesson. Those lines run through the previous
        year: this year's outcome line is added at the start of next year
        (``pre_year``). The summary is stripped of quotes, whitespace and
        trailing commas, and is not stored when it is empty or quotes a
        figure that matches no figure of that input within 5 percent
        (``_foreign_figures``; each drop is printed with its figures). A
        stored summary reads "Consolidated Reflection (written in {Y}):
        {summary}", Y the calendar year just ended, and
        ``reflection.keep_latest_only`` replaces the agent's earlier
        reflection (the framework option, ``store_reflection_memory``).
        Under ``keep_latest_only`` an agent whose new summary is not stored
        (empty, foreign figure, unreadable reply, failed call) loses its
        earlier reflection too (review HIGH 1), so a prompt never shows a
        reflection older than the end of the previous year (S10).
        """
        cfg = self.runner.broker.config.get_reflection_config()
        batch_size = cfg.get("batch_size", 10)
        keep_latest_only = self.runner.broker.config.get_reflection_keep_latest_only()
        written_in = self.env.current_year
        candidates = []
        for aid, agent in self.runner.agents.items():
            if not getattr(agent, "is_active", True):
                continue
            mems = [m for m in self.runner.memory_engine.retrieve(agent, top_k=10)
                    if not _is_reflection_memory(m)]
            if mems:
                # F08+F33 (2026-09-25 audit): the adapter's importance and
                # emotion read real, current-year values -- water_right_pct
                # and supply_ratio from the settled state, recent_decision
                # from the executed skill (agent._last_action_context), and
                # drought_count from the counter post_year maintains. Rounded
                # to 6 places so float noise cannot move a band edge.
                # Supply-side redesign (spec M4): the adapter also reads the
                # PROPOSED skill, the fallback flag and the unmet fraction.
                attrs = getattr(agent, "custom_attributes", {})
                agent_state = self.env.get_agent_state(aid)
                water_right = agent_state.get("water_right", 0) or 0
                request = agent_state.get("request", 0) or 0
                diversion = agent_state.get("diversion", 0) or 0
                action_ctx = getattr(agent, "_last_action_context", None) or {}
                # Same rule as pre_year: a context stamped with an earlier
                # loop year describes no decision of this year (nothing
                # executed: an ABORTED decision).
                if action_ctx.get("year") != year:
                    action_ctx = {}
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
        stored = 0
        skipped_empty = 0
        skipped_foreign = 0
        no_reply = 0
        replaced = 0
        stored_ids = set()
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i: i + batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(
                batch,
                written_in,
                reflection_questions=cfg.get("questions", []),
                persona_instruction=cfg.get("persona_instruction")
            )
            # Only the model call and its parsing may fail and be skipped (as
            # before WP4); storing runs outside the try, so a store error
            # (e.g. keep_latest_only on an engine without remove_by_type)
            # stops the run instead of being printed and dropped.
            try:
                raw = llm_call(prompt)
                text = raw[0] if isinstance(raw, tuple) else raw
                insights = self.reflection_engine.parse_batch_reflection_response(
                    text, batch_ids, year
                )
            except Exception as e:
                print(f"  [Reflection:Error] Batch {i // batch_size + 1}: {e}")
                no_reply += len(batch_ids)
                continue
            no_reply += sum(1 for aid in batch_ids if not insights.get(aid))
            for aid, insight in insights.items():
                if not insight:
                    continue
                ctx_item = next((c for c in batch if c["agent_id"] == aid), None)
                if ctx_item and ctx_item.get("context") and self.reflection_engine.adapter:
                    insight.importance = self.reflection_engine.compute_dynamic_importance(
                        ctx_item["context"]
                    )
                # store_insight and the reflection_log.jsonl line it writes
                # stay unconditional, so every summary the model wrote is
                # in the log even when it is not stored below.
                self.reflection_engine.store_insight(aid, insight)
                emotion = "major"
                if self.reflection_engine.adapter and ctx_item and ctx_item.get("context"):
                    emotion = self.reflection_engine.adapter.classify_emotion(
                        ctx_item["context"].get("recent_decision", ""), ctx_item["context"]
                    )

                summary = _normalize_reflection_text(str(getattr(insight, "summary", "") or ""))
                if not summary:
                    skipped_empty += 1
                    continue
                own_text = " ".join(
                    (m.get("content", "") if isinstance(m, dict) else str(m))
                    for m in (ctx_item or {}).get("memories", [])
                )
                foreign = _foreign_figures(summary, own_text)
                if foreign:
                    skipped_foreign += 1
                    print(f"  [reflect] {aid}: not stored, {', '.join(foreign)} matches no "
                          f"figure in its memory within 5 percent: {summary}")
                    continue
                replaced += store_reflection_memory(
                    self.runner.memory_engine,
                    aid,
                    f"{_REFLECTION_MEMORY_PREFIX} (written in {written_in}): {summary}",
                    {
                        # "importance", not "significance": HumanCentricMemoryEngine
                        # only reads metadata.get("importance", 0.5). See
                        # examples/irrigation_abm/tests/test_governance_mode_wiring.py::
                        # TestBatchReflectImportanceKey.
                        "importance": insight.importance,
                        "emotion": emotion,
                        "source": "personal",
                        "type": "reflection",
                        # Item 36b: see the matching comment on the outcome
                        # memory above.
                        "year": written_in,
                    },
                    keep_latest_only=keep_latest_only,
                )
                stored_ids.add(aid)
                stored += 1
        # Review HIGH 1: store_reflection_memory removes an earlier
        # reflection only when it stores a new one. Every other outcome above
        # (an empty or foreign summary, an unreadable reply, a failed call)
        # would leave last year's reflection in place, so remove it here.
        removed_stale = 0
        if keep_latest_only:
            for c in candidates:
                if c["agent_id"] not in stored_ids:
                    removed_stale += self.runner.memory_engine.remove_by_type(
                        c["agent_id"], "reflection")
        print(f"  [Reflection] Year {year} complete.")
        print(f"  [reflect] year {year}: stored {stored} reflections, "
              f"skipped {skipped_empty} empty, not stored {skipped_foreign} with a "
              f"figure foreign to the agent's memory, {no_reply} with no readable "
              f"reply, replaced {replaced} earlier reflection items, removed "
              f"{removed_stale} earlier reflection items of agents with no new one")


def _record_paper_water_margin_provenance(
    output_dir: Path, paper_water_margin: float, is_real: bool
) -> None:
    """Additively record ``--paper-water-margin`` in this run's two provenance files.

    ``ExperimentRunner._finalize_experiment`` (broker/core/experiment_runner.py)
    already wrote ``reproducibility_manifest.json`` and ``config_snapshot.yaml``
    by the time ``runner.run()`` returns; this patches both in place with one
    additive key each rather than teaching the generic broker manifest about
    an irrigation-only CLI parameter. ``paper_water_margin`` is recorded even
    for a synthetic (non ``--real``) run, since it is a resolved CLI value
    either way (a synthetic run just never calls the code path that reads
    it). Wrapped so a provenance-write problem (disk full, permissions) can
    never fail the experiment itself -- same posture as the broker's own
    manifest-enrichment try/except (F3 fix).
    """
    try:
        manifest_path = output_dir / "reproducibility_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["paper_water_margin"] = paper_water_margin
            manifest["paper_water_margin_applied"] = bool(is_real)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record paper_water_margin in "
              f"reproducibility_manifest.json: {e}")

    try:
        snapshot_path = output_dir / "config_snapshot.yaml"
        if snapshot_path.exists():
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = yaml.safe_load(f)
            snapshot = snapshot or {}
            snapshot.setdefault("metadata", {})
            snapshot["metadata"]["paper_water_margin"] = paper_water_margin
            snapshot["metadata"]["paper_water_margin_applied"] = bool(is_real)
            with open(snapshot_path, "w", encoding="utf-8") as f:
                yaml.dump(snapshot, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record paper_water_margin in "
              f"config_snapshot.yaml: {e}")


def _record_step_bin_source_provenance(
    output_dir: Path, profiles: List[IrrigationAgentProfile], is_real: bool
) -> None:
    """Additively record every profile's ``step_bin_source`` (spec 2.4:
    "grid" or "rescaled") in this run's two provenance files (WP2 review
    round 1, MEDIUM 2; spec 7.2's "the step_bin_source list").

    Same pattern as ``_record_paper_water_margin_provenance`` above
    (patches the two files ``ExperimentRunner._finalize_experiment``
    already wrote), but PER-AGENT rather than a single scalar: a dict
    ``{agent_id: step_bin_source}`` for every profile, ``None`` for a
    synthetic profile (non ``--real``, or any profile builder other than
    ``create_profiles_from_data``) that never computed one. Recorded
    unconditionally like the other two -- a run with no real step bins at
    all still gets a manifest key showing that, rather than a silently
    absent one indistinguishable from "the write failed". Wrapped so a
    provenance-write problem can never fail the experiment itself.
    """
    step_bin_source = {p.agent_id: p.step_bin_source for p in profiles}
    try:
        manifest_path = output_dir / "reproducibility_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["step_bin_source"] = step_bin_source
            manifest["step_bin_source_applied"] = bool(is_real)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record step_bin_source in "
              f"reproducibility_manifest.json: {e}")

    try:
        snapshot_path = output_dir / "config_snapshot.yaml"
        if snapshot_path.exists():
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = yaml.safe_load(f)
            snapshot = snapshot or {}
            snapshot.setdefault("metadata", {})
            snapshot["metadata"]["step_bin_source"] = step_bin_source
            snapshot["metadata"]["step_bin_source_applied"] = bool(is_real)
            with open(snapshot_path, "w", encoding="utf-8") as f:
                yaml.dump(snapshot, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record step_bin_source in "
              f"config_snapshot.yaml: {e}")


def _record_hold_requests_fixed_provenance(
    output_dir: Path, hold_requests_fixed: bool
) -> None:
    """Additively record ``WaterSystemConfig.hold_requests_fixed`` in this
    run's two provenance files (WP2 review round 2, LOW 3).

    Same pattern as ``_record_paper_water_margin_provenance`` above.
    Always recorded (not conditioned on ``--real``, unlike the other two
    provenance functions here): the switch is meaningful for BOTH real
    and synthetic runs alike, and its value is resolved regardless. This
    runner's own ``main()`` asserts ``hold_requests_fixed is False`` right
    after constructing ``WaterSystemConfig`` -- this function records
    THAT already-verified value, so the manifest can only ever show
    ``False`` for a run that reached this point, never a value the
    assertion would have already refused to let through. Wrapped so a
    provenance-write problem can never fail the experiment itself.
    """
    try:
        manifest_path = output_dir / "reproducibility_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["hold_requests_fixed"] = hold_requests_fixed
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record hold_requests_fixed in "
              f"reproducibility_manifest.json: {e}")

    try:
        snapshot_path = output_dir / "config_snapshot.yaml"
        if snapshot_path.exists():
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = yaml.safe_load(f)
            snapshot = snapshot or {}
            snapshot.setdefault("metadata", {})
            snapshot["metadata"]["hold_requests_fixed"] = hold_requests_fixed
            with open(snapshot_path, "w", encoding="utf-8") as f:
                yaml.dump(snapshot, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record hold_requests_fixed in "
              f"config_snapshot.yaml: {e}")


def _record_governance_dispatch_provenance(
    output_dir: Path, dispatched_checks: List[str]
) -> None:
    """Additively record the irrigation checks this run dispatched (WP3,
    spec 3.1 acceptance: every manifest shows the dispatched checks beside
    the resolved thinking and identity rules and ``appraisal_freeze``, which
    the generic manifest already carries).

    ``dispatched_checks`` is the names of ``ALL_IRRIGATION_CHECKS`` when the
    runner wires ``irrigation_governance_validator`` (every profile but
    ``disabled``), and ``[]`` when it wires no custom validator. Same
    pattern as ``_record_hold_requests_fixed_provenance``; wrapped so a
    provenance-write problem can never fail the experiment itself.
    """
    try:
        manifest_path = output_dir / "reproducibility_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["irrigation_dispatched_checks"] = list(dispatched_checks)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record irrigation_dispatched_checks in "
              f"reproducibility_manifest.json: {e}")

    try:
        snapshot_path = output_dir / "config_snapshot.yaml"
        if snapshot_path.exists():
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = yaml.safe_load(f)
            snapshot = snapshot or {}
            snapshot.setdefault("metadata", {})
            snapshot["metadata"]["irrigation_dispatched_checks"] = list(dispatched_checks)
            with open(snapshot_path, "w", encoding="utf-8") as f:
                yaml.dump(snapshot, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record irrigation_dispatched_checks in "
              f"config_snapshot.yaml: {e}")


def _record_water_system_config_provenance(
    output_dir: Path, config
) -> None:
    """Additively record ``WaterSystemConfig.powell_release_mode``,
    ``powell_post2026_equalization`` and ``lb_non_ag_total_maf`` in this
    run's two provenance files (re-review 2026-09-29 round 4, MEDIUM 4;
    spec items 25-27).

    Same pattern as ``_record_hold_requests_fixed_provenance`` above,
    which it is called alongside in ``main()``'s abort-safe ``finally``
    block: every real run of this domain resolves these three values
    regardless of ``--real``/``--model``, and WP7's launch checklist
    requires every manifest to show ``ub_supply_mode`` / ``appraisal_freeze``
    / etc. -- these three are the same kind of value, just not yet wired
    into the generic broker manifest (an irrigation-only WaterSystemConfig
    concern, no generic-framework home). Wrapped so a provenance-write
    problem can never fail the experiment itself.

    WP6 (spec 7.2): also ``ub_supply_mode``, ``ub_subbasin_supply_variant``
    and the pinned sha256 that the environment checks each of the Upper
    Basin sub-basin tables against whenever it loads them -- the supply
    table of the variant in use (``ub_subbasin_supply_v3_sha256``), the
    envelope table (``ub_subbasin_envelope_v3_sha256``) and the per-variant
    mean-flow table the flow-share sentence divides by
    (``ub_subbasin_variant_means_v3_sha256``) -- the same module constants
    ``run_fql_baseline._pinned_v3_data_checksums`` records, so the WP6
    provenance guard compares them across the LLM runs and the FQL
    reference. A failed checksum lookup leaves only those keys out (the
    guard then refuses the run); the other keys are still recorded.
    """
    try:
        water_system = {
            "powell_release_mode": config.powell_release_mode,
            "powell_post2026_equalization": config.powell_post2026_equalization,
            "lb_non_ag_total_maf": config.lb_non_ag_total_maf,
            "ub_supply_mode": config.ub_supply_mode,
            "ub_subbasin_supply_variant": config.ub_subbasin_supply_variant,
            # Item 36e: 0.0 (default, byte-identical) unless a CPU
            # sensitivity run sets it.
            "lb_return_flow_fraction": config.lb_return_flow_fraction,
            # 2026-10-06 CPU rerun finding: 0.10 (default, byte-identical)
            # unless --min-utilisation-fraction sets it.
            "min_utilisation_fraction": config.min_utilisation_fraction,
        }
    except Exception as e:
        print(f"[Provenance] WARNING: could not resolve the water-system keys for "
              f"reproducibility_manifest.json and config_snapshot.yaml: {e}")
        return
    try:
        from examples.irrigation_abm.irrigation_env import (
            UB_SUBBASIN_ENVELOPE_SHA256,
            UB_SUBBASIN_VARIANT_MEANS_SHA256,
            _UB_SUBBASIN_SUPPLY_VARIANT_FILES,
        )
        water_system["ub_subbasin_supply_v3_sha256"] = _UB_SUBBASIN_SUPPLY_VARIANT_FILES[
            config.ub_subbasin_supply_variant][1]
        water_system["ub_subbasin_envelope_v3_sha256"] = UB_SUBBASIN_ENVELOPE_SHA256
        water_system["ub_subbasin_variant_means_v3_sha256"] = UB_SUBBASIN_VARIANT_MEANS_SHA256
    except Exception as e:
        print(f"[Provenance] WARNING: could not resolve the Upper Basin sub-basin "
              f"table checksums; the manifest records the other water-system keys "
              f"without them: {e}")
    try:
        manifest_path = output_dir / "reproducibility_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest.update(water_system)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record the water-system keys "
              f"{sorted(water_system)} in reproducibility_manifest.json: {e}")

    try:
        snapshot_path = output_dir / "config_snapshot.yaml"
        if snapshot_path.exists():
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = yaml.safe_load(f)
            snapshot = snapshot or {}
            snapshot.setdefault("metadata", {})
            snapshot["metadata"].update(water_system)
            with open(snapshot_path, "w", encoding="utf-8") as f:
                yaml.dump(snapshot, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record the water-system keys "
              f"{sorted(water_system)} in config_snapshot.yaml: {e}")


def _record_memory_options_provenance(output_dir: Path, memory_engine) -> None:
    """Additively record the three item-36b HumanCentricMemoryEngine
    options in this run's two provenance files (Opus review P3-2,
    2026-10-06).

    Same pattern as ``_record_hold_requests_fixed_provenance`` above:
    always recorded (not conditioned on ``--real``), reads the already-
    type-checked, already-constructed engine's own attributes rather
    than re-deriving them from the YAML dict a caller could have built
    the engine from, and never fails the run over a provenance-write
    problem.
    """
    try:
        options = {
            "deterministic_consolidation": memory_engine.deterministic_consolidation,
            "decay_ignore_emotion": memory_engine.decay_ignore_emotion,
            "decay_by_calendar_year": memory_engine.decay_by_calendar_year,
        }
    except AttributeError as e:
        print(f"[Provenance] WARNING: memory_engine has no item-36b options to "
              f"record (not a HumanCentricMemoryEngine?): {e}")
        return

    try:
        manifest_path = output_dir / "reproducibility_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest.update(options)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record the memory options "
              f"{sorted(options)} in reproducibility_manifest.json: {e}")

    try:
        snapshot_path = output_dir / "config_snapshot.yaml"
        if snapshot_path.exists():
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = yaml.safe_load(f)
            snapshot = snapshot or {}
            snapshot.setdefault("metadata", {})
            snapshot["metadata"].update(options)
            with open(snapshot_path, "w", encoding="utf-8") as f:
                yaml.dump(snapshot, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record the memory options "
              f"{sorted(options)} in config_snapshot.yaml: {e}")


def _record_cluster_method_provenance(
    output_dir: Path, cluster_method: str, is_real: bool
) -> None:
    """Additively record ``--cluster-method`` in this run's two provenance files.

    Same pattern and rationale as ``_record_paper_water_margin_provenance``
    above (which it is called alongside, not instead of): patches the two
    files ``ExperimentRunner._finalize_experiment`` already wrote, rather
    than teaching the generic broker manifest about an irrigation-only CLI
    parameter. Recorded even for a synthetic (non ``--real``) run, since it
    is a resolved CLI value either way (a synthetic run never calls
    ``create_profiles_from_data``, the only place ``cluster_method`` is
    read). Wrapped so a provenance-write problem can never fail the
    experiment itself.
    """
    try:
        manifest_path = output_dir / "reproducibility_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["cluster_method"] = cluster_method
            manifest["cluster_method_applied"] = bool(is_real)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record cluster_method in "
              f"reproducibility_manifest.json: {e}")

    try:
        snapshot_path = output_dir / "config_snapshot.yaml"
        if snapshot_path.exists():
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = yaml.safe_load(f)
            snapshot = snapshot or {}
            snapshot.setdefault("metadata", {})
            snapshot["metadata"]["cluster_method"] = cluster_method
            snapshot["metadata"]["cluster_method_applied"] = bool(is_real)
            with open(snapshot_path, "w", encoding="utf-8") as f:
                yaml.dump(snapshot, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record cluster_method in "
              f"config_snapshot.yaml: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _resolve_resume_source(raw: str) -> Path:
    """``--resume-from`` accepts either a crashed run's ``llm_journal.jsonl``
    directly, or that run's ``--output`` directory (the file is assumed to
    be named ``llm_journal.jsonl`` inside it -- the one name this runner
    ever writes it under, both for a fresh ``--llm-journal`` run and for a
    resumed run's own new journal).
    """
    path = Path(raw)
    if path.is_dir():
        path = path / "llm_journal.jsonl"
    if not path.exists():
        raise SystemExit(f"--resume-from {raw}: no journal file found at {path}")
    return path


def _irrigation_identifying_config(
    args: argparse.Namespace, *,
    agent_config_path=None, prompt_template_path=None, skill_registry_path=None,
) -> dict:
    """The CLI-level "identifying config" for the LLM-call journal header
    and resume check (broker.utils.llm_journal.check_identifying_config).

    Mirrors, under the SAME keys, the generic fields
    ``ExperimentRunner._build_llm_journal_manager`` already derives on its
    own from the built experiment (model / seed / memory_seed /
    governance_profile / num_years / num_steps) -- harmless duplication,
    not drift, since both are derived from this same CLI's own ``args`` --
    plus every other CLI flag with no generic home that can change what an
    agent is asked or how (the "prompt-affecting flags" a resume must not
    silently change). Excludes ``--workers`` (explicitly allowed to differ
    between a crashed run and its resume), ``--output`` / ``--llm-journal``
    / ``--resume-from`` (not identifying -- they say where/whether to
    journal, not what the experiment is), and ``--pilot-phase`` /
    ``--ablation-mode`` (refused at startup, before this is ever called).

    ``agent_config_path`` / ``prompt_template_path`` / ``skill_registry_path``,
    when given (once ``main()`` has resolved them -- the agent-types YAML
    post any ``--coupling`` derivation, the prompt template file, and the
    skill registry YAML, all read from ``--config-dir``): their sha256 is
    added too. Sampling params, the prompt text, and the skill menu live
    in these files, not in any CLI flag, and only affect the LIVE years of
    a resumed run (the replayed years already have their recorded
    answers) -- but a silent change there underneath an unchanged
    ``--config-dir`` is still exactly the kind of "different experiment" a
    resume must refuse, and a path string alone cannot catch an in-place
    edit.

    Git identity (commit, dirty, and a hash of the uncommitted diff) is
    folded in unconditionally via :func:`_git_state_at_launch`, computed
    independently of ``ExperimentRunner.__init__``'s own capture
    (broker/core/experiment_runner.py) because this runs during the
    resume preflight, before any runner exists.
    """
    config = {
        "model": args.model,
        "seed": args.seed,
        "memory_seed": args.memory_seed,
        "governance_profile": args.governance_mode,
        "num_years": args.years,
        "num_steps": None,
        "real": args.real,
        "agents": args.agents,
        "paper_water_margin": args.paper_water_margin,
        "cluster_method": args.cluster_method,
        "window_size": args.window_size,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "rebalance_clusters": args.rebalance_clusters,
        "no_magnitude": args.no_magnitude,
        "config_dir": args.config_dir,
        "coupling": args.coupling,
        "retry_feedback_mode": args.retry_feedback_mode,
    }
    if agent_config_path is not None:
        import hashlib
        config["agent_config_sha256"] = hashlib.sha256(
            Path(agent_config_path).read_bytes()
        ).hexdigest()
    if prompt_template_path is not None:
        import hashlib
        config["prompt_template_sha256"] = hashlib.sha256(
            Path(prompt_template_path).read_bytes()
        ).hexdigest()
    if skill_registry_path is not None:
        import hashlib
        config["skill_registry_sha256"] = hashlib.sha256(
            Path(skill_registry_path).read_bytes()
        ).hexdigest()
    git_commit, git_dirty, git_diff_sha256 = _git_state_at_launch()
    config["git_commit"] = git_commit
    config["git_dirty"] = git_dirty
    config["git_diff_sha256"] = git_diff_sha256
    return config


def _git_state_at_launch():
    """``(commit, dirty, diff_sha256)`` for the CURRENT process's git state.

    ``dirty`` uses ``git status --porcelain --untracked-files=no``: an
    UNTRACKED file (e.g. the crashed run's own output, when ``--output``
    sits inside the repo tree) must never flip this -- otherwise a
    clean-tree run could never be resumed once its own crash artifacts
    exist as untracked files, and would fail with a misleading "the code
    has changed" message. ``diff_sha256`` is the sha256 of ``git diff
    HEAD`` (tracked, uncommitted changes only; the empty string's hash
    when the tree is clean) -- ``dirty`` alone cannot tell two DIFFERENT
    sets of uncommitted edits apart (both compare True/True), so a
    resume's refusal check compares ``diff_sha256``, not ``dirty``;
    ``dirty`` is kept for a human reading the header.

    Returns ``("unavailable", None, None)`` when git itself is unavailable
    (not a repo, no git binary): never raises, since manifest/header
    enrichment must not fail a run over this.
    """
    try:
        import hashlib
        import subprocess
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
        ).decode().strip()
        dirty = len(subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()) > 0
        diff_bytes = subprocess.check_output(
            ["git", "diff", "HEAD"], stderr=subprocess.DEVNULL,
        )
        diff_sha256 = hashlib.sha256(diff_bytes).hexdigest()
        return commit, dirty, diff_sha256
    except Exception:
        return "unavailable", None, None


def main():
    args = parse_args()
    # v3 (WP3, spec 3.2): the pilot phases and the ablation mode switched
    # checks that v3 no longer dispatches (consecutive_increase_cap_check,
    # zero_escape_check, demand_ceiling_stabilizer), so either flag would now
    # silently do nothing. Refused before anything is written.
    if args.pilot_phase is not None or args.ablation_mode is not None:
        raise SystemExit(
            "--pilot-phase and --ablation-mode are retired in the v3 "
            "governance (irrigation_v3_spec_2026-09-28.md section 3.2): the "
            "checks they switched are no longer dispatched, so the flag would "
            "change nothing. Choose an arm with --governance-mode (strict, "
            "feasibility_only, disabled) and --retry-feedback-mode (full, "
            "placebo, silent) instead."
        )
    if args.rebalance_clusters and args.cluster_method == "hy2021":
        raise SystemExit(
            "--rebalance-clusters cannot be combined with --cluster-method "
            "hy2021: rebalancing reassigns clusters toward a target "
            "distribution by FQL-parameter distance, which would overwrite "
            "Hung & Yang (2021) Figure 7's own published per-entity "
            "assignment (HY2021_CLUSTER_LABELS) that --cluster-method "
            "hy2021 exists to preserve. Pass --cluster-method "
            "legacy_centroid if you want the rebalanced distribution."
        )
    # 2026-10-06 Opus review P2-1: config/agent_types.yaml's three
    # minimum_utilisation_floor rule messages hard-code "10% of your
    # water right" (deliberately not templated -- a templating pass is
    # its own change, not this one). An LLM agent blocked under a
    # DIFFERENT floor would be told the wrong number, so this runner
    # refuses any --min-utilisation-fraction other than the config
    # default (0.10) rather than show a stale message. The 0 and 0.05 x W
    # floor CPU sensitivities (provenance C6b) stay FQL-only
    # (run_fql_baseline.py never shows this message to an LLM) until the
    # rule message is templated.
    if args.min_utilisation_fraction is not None and args.min_utilisation_fraction != 0.10:
        raise SystemExit(
            f"--min-utilisation-fraction {args.min_utilisation_fraction} is refused on "
            "this LLM-governed runner: config/agent_types.yaml's "
            "minimum_utilisation_floor rule message hard-codes \"10% of your water "
            "right\" and is not templated, so an LLM agent blocked under a "
            "different floor would be told the wrong number. Floor sensitivities "
            "(0 and 0.05 x W, provenance C6b) are FQL-only for now -- use "
            "run_fql_baseline.py's --min-utilisation-fraction instead -- until "
            "that message is templated."
        )

    # --- Crash-resume: resolve the source journal and read its header
    # early (cheap: one small file read). The actual checks run below,
    # once output_dir (directory-collision) and then agent_config_path /
    # prompt_template_path (content/git identity) are resolved -- still
    # all well before any heavy setup (--real's CRSS data load). ---
    resume_source_path = None
    source_header = None
    if args.resume_from:
        from broker.utils.llm_journal import read_journal_header
        resume_source_path = _resolve_resume_source(args.resume_from)
        try:
            source_header = read_journal_header(resume_source_path)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"--resume-from {args.resume_from}: {exc}")

    base = Path(__file__).parent

    # --- Output (moved early: a --coupling derived config file, below, is
    # written into this directory so it persists with the rest of the run's
    # artifacts instead of living in a temp dir) ---
    output_dir = Path(args.output) if args.output else base / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Crash-resume: refuse at the DIRECTORY level before anything else
    # is written into output_dir. LLMJournalManager also refuses at the
    # FILE level (output_path == resume_from, broker/utils/llm_journal.py),
    # but that only fires once the journal is opened for writing, deep
    # inside build()/run() -- by then a --coupling derived config copy may
    # already have been written under output_dir, and opening the SAME
    # journal file with "w" would destroy the very journal being replayed
    # before it could even be read. Checking the directory here, before
    # output_dir receives anything, fails before any of that -- and also
    # prevents reflection_log.jsonl (appended, never truncated) from
    # picking up a second, duplicate copy of the replayed years' entries.
    if resume_source_path is not None:
        if resume_source_path.parent.resolve() == output_dir.resolve():
            raise SystemExit(
                f"--output {output_dir} is the SAME directory as the "
                f"source run being resumed from "
                f"({resume_source_path.parent}). A resumed run must write "
                f"to a NEW directory; pass a different --output."
            )

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
    skill_registry_path = config_dir / "skill_registry.yaml"
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

    # --- Load config YAML ---
    agent_config_path = config_dir / "agent_types.yaml"

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

    # --- Crash-resume: the full identifying-config check, now that
    # agent_config_path (post --coupling resolution), prompt_template_path
    # and skill_registry_path are all resolved -- still well before
    # --real's CRSS data load, the actually heavy step. See
    # _irrigation_identifying_config's docstring for why the config/
    # prompt/registry hashes and git identity matter even though
    # --config-dir alone already compares equal in the CLI-args check this
    # folds in. ONE comparison, ONE error message: git_commit / git_dirty /
    # git_diff_sha256 are now first-class entries in both dicts (source
    # from the header, current from _irrigation_identifying_config's own
    # call to _git_state_at_launch), so check_identifying_config refuses
    # on a commit OR a diff-hash mismatch exactly like any other
    # identifying field, with no separate bespoke check needed.
    if resume_source_path is not None:
        from broker.utils.llm_journal import RESUME_PROVENANCE_KEY, check_identifying_config
        current_identifying = _irrigation_identifying_config(
            args, agent_config_path=agent_config_path,
            prompt_template_path=prompt_template_path,
            skill_registry_path=skill_registry_path,
        )
        try:
            check_identifying_config(
                source_header, current_identifying,
                # "workers" is now a header key (ExperimentRunner.
                # _build_llm_journal_manager records it generically, for
                # every run, journalled or not resumed), but
                # _irrigation_identifying_config deliberately never puts it
                # in current_identifying -- see that function's own
                # docstring on why --workers is allowed to differ between a
                # crashed run and its resume. Without "workers" here too,
                # source_header's always-present key vs current_identifying's
                # always-absent one would refuse EVERY resume, at any worker
                # count, the moment the header started recording it.
                allowed_to_differ=(RESUME_PROVENANCE_KEY, "workers"),
            )
        except ValueError as exc:
            raise SystemExit(str(exc))

    # --- Load skill registry ---
    registry = SkillRegistry()
    registry.register_from_yaml(str(skill_registry_path))

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
            paper_water_margin=args.paper_water_margin,
            cluster_method=args.cluster_method,
        )
        print(
            f"[Data] Loaded {len(profiles)} real CRSS agents from paper data "
            f"(paper_water_margin={args.paper_water_margin}, "
            f"cluster_method={args.cluster_method})"
        )
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
    config_kwargs: Dict[str, Any] = {}
    if args.lb_non_ag_total_maf is not None:
        config_kwargs["lb_non_ag_total_maf"] = args.lb_non_ag_total_maf
    if args.lb_return_flow_fraction is not None:
        config_kwargs["lb_return_flow_fraction"] = args.lb_return_flow_fraction
    if args.min_utilisation_fraction is not None:
        config_kwargs["min_utilisation_fraction"] = args.min_utilisation_fraction
    config = WaterSystemConfig(seed=seed, **config_kwargs)
    # WP2 review round 2 (LOW 3): hold_requests_fixed is for replays and
    # CPU diagnostics only (WaterSystemConfig's own docstring) -- this
    # runner never exposes a flag for it (test_hold_requests_fixed_
    # never_set_by_a_runner asserts that), so a True value here could only
    # come from a change to THIS line; fail loud rather than let a real
    # LLM run silently skip the WP2 keep-tracks-delivery reset.
    assert config.hold_requests_fixed is False, (
        "run_experiment.py must never construct WaterSystemConfig with "
        "hold_requests_fixed=True -- that switch is for replays and CPU "
        "diagnostics only"
    )
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

    _mem_window = int(irr_mem.get("window_size", args.window_size))
    _mem_sig = int(irr_mem.get("top_k_significant", gm.get("top_k_significant", 2)))
    if "window_size" in irr_mem and args.window_size != _mem_window:
        print(f"[Memory] WARNING: --window-size {args.window_size} ignored; "
              f"irrigation_farmer.memory.window_size = {_mem_window} is used")
    memory_engine = HumanCentricMemoryEngine(
        # Composed retrieval sizes: the agent-type memory block wins, so the
        # engine (post_year log, year-end reflection) and the prompt
        # (MemoryProvider pass-through) use one window and one significant
        # count; --window-size applies only when the block does not set it.
        window_size=_mem_window,
        top_k_significant=_mem_sig,
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
        # Reserved retrieval slot(s) by memory type (framework option,
        # weighted mode only); not set for irrigation since 2026-09-26.
        reserve_types=irr_mem.get("reserve_types"),
        # Item 36b (2026-10-05 design-basis audit + fix proposals, spec
        # item 36b): three generic, opt-in framework options (default
        # off everywhere, including here, unless global_config.memory
        # sets them -- irrigation's agent_types.yaml turns all three on).
        deterministic_consolidation=gm.get("deterministic_consolidation", False),
        decay_ignore_emotion=gm.get("decay_ignore_emotion", False),
        decay_by_calendar_year=gm.get("decay_by_calendar_year", False),
    )
    print(f"[Pillar 2] HumanCentricMemoryEngine (window={memory_engine.window_size}, top_k_significant={memory_engine.top_k_significant}, mode={memory_engine.ranking_mode})")

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
    # v3 (WP3, spec 3.1): strict, placebo, silent and feasibility_only run
    # the supply rule (ALL_IRRIGATION_CHECKS); disabled runs none. Recorded
    # in the manifest after the run (_record_governance_dispatch_provenance).
    dispatched_checks = (
        [check.__name__ for check in ALL_IRRIGATION_CHECKS] if custom_validators else []
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
    # Crash-resume journal (broker/utils/llm_journal.py): --resume-from
    # implies journaling continues (so the resumed run can itself be
    # resumed again), even if --llm-journal was not also passed.
    if args.llm_journal or args.resume_from:
        builder = builder.with_llm_journal(str(output_dir / "llm_journal.jsonl"))
    if resume_source_path is not None:
        builder = builder.with_resume_journal(str(resume_source_path))
    runner = builder.build()
    if args.llm_journal or args.resume_from:
        # Same `runner.broker._xxx = ...` idiom as _derived_from_config /
        # _retry_feedback_mode below: set directly on the already-built
        # runner, read by ExperimentRunner._build_llm_journal_manager
        # (called at the top of runner.run(), before this attribute would
        # otherwise be needed).
        runner._llm_journal_identifying_extra = _irrigation_identifying_config(
            args, agent_config_path=agent_config_path,
            prompt_template_path=prompt_template_path,
            skill_registry_path=skill_registry_path,
        )
    if agent_config_path != original_agent_config_path:
        # Same hook run_flood.py uses for --retry-feedback-mode
        # (runner.broker._retry_feedback_mode, read generically by
        # ExperimentRunner._collect_reproducibility_metadata): set an
        # attribute directly on the already-built broker, read by the
        # generic manifest builder's derived_from_config field (next to
        # agent_types_config) - no broker init-time change needed.
        runner.broker._derived_from_config = str(original_agent_config_path)

    # Red-team objection 3 ablation (default None = whatever
    # global_config.governance.retry_feedback_mode in agent_types.yaml
    # resolved to on the engine, normally "full"). Same mechanism
    # run_flood.py's --retry-feedback-mode uses: SkillBrokerEngine.
    # set_retry_feedback_mode (opus review, 2026-09-27) validates the mode,
    # sets the already-constructed broker's resolved attribute, re-logs via
    # logger.info in the engine's own startup shape ("[Governance]
    # retry_feedback_mode=%s", parity with flood -- both runners now share
    # the SAME log line instead of each printing their own), and re-runs the
    # W2 advisory-channel-conflict check against the NEW value. Called here,
    # before runner.run() below, rather than editing the loaded YAML:
    # RetryMixin._governance_retry_loop reads `self._retry_feedback_mode` at
    # every retry call (not just once at engine construction), so setting it
    # here governs every retry for the whole run.
    # ExperimentRunner._finalize_experiment / _collect_reproducibility_
    # metadata already read this same attribute generically (domain-
    # agnostic, shared with flood) into config_snapshot.yaml's
    # metadata.retry_feedback_mode and reproducibility_manifest.json's
    # retry_feedback_mode key -- no irrigation-specific manifest patch
    # needed, unlike _record_paper_water_margin_provenance below (which
    # exists only because paper_water_margin has no generic-framework home).
    if args.retry_feedback_mode is not None:
        runner.broker.set_retry_feedback_mode(args.retry_feedback_mode)

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

    # --- Run ---
    n_real = "real" if args.real else "synthetic"
    print(
        f"--- Irrigation ABM | {args.model} | {len(profiles)} agents ({n_real}) "
        f"| {args.years} years | seed={seed} ---"
    )
    # Spec item 24 fix round: runner.run() can now raise LLMFailureRateAborted
    # (the LLM safeguard, on by default for this domain). Pre-fix, the four
    # _record_*_provenance patches, the explicit audit finalize, and the
    # simulation_log.csv save all ran only AFTER runner.run() returned, so an
    # abort skipped every one of them -- including
    # _record_hold_requests_fixed_provenance, whose value every manifest must
    # carry (see main()'s own `assert config.hold_requests_fixed is False`
    # above). try/finally: these run whether the call above returned or
    # raised, and the exception (if any) still propagates afterward so the
    # process still exits non-zero with the safeguard's one-line reason.
    try:
        runner.run(llm_invoke=create_llm_invoke(args.model, verbose=False))
    finally:
        # Water-right history-anchor provenance (Change 1): additive patch of
        # the two files ExperimentRunner._finalize_experiment already wrote,
        # done here rather than inside broker/ since paper_water_margin is an
        # irrigation-domain-only CLI parameter (irrigation_farmer's
        # create_profiles_from_data, --real only) with no generic-framework
        # home. Never fails the run over a provenance write (same posture as
        # broker's own manifest-enrichment try/except, F3 fix) -- each of the
        # four functions below already guards its own body and only prints a
        # WARNING on failure, so none of them can mask an in-flight abort.
        _record_paper_water_margin_provenance(output_dir, args.paper_water_margin, args.real)
        _record_cluster_method_provenance(output_dir, args.cluster_method, args.real)
        _record_step_bin_source_provenance(output_dir, profiles, args.real)
        _record_hold_requests_fixed_provenance(output_dir, env.config.hold_requests_fixed)
        _record_water_system_config_provenance(output_dir, env.config)
        _record_memory_options_provenance(output_dir, memory_engine)
        _record_governance_dispatch_provenance(output_dir, dispatched_checks)

        # Finalize audit. Also already called from inside
        # ExperimentRunner._finalize_experiment's own finally (run() wraps
        # its whole loop in try/finally too), so this is belt-and-braces
        # rather than the only path -- kept for the pre-existing explicit
        # call sequence here.
        if runner.broker.audit_writer:
            runner.broker.audit_writer.finalize()

        # Save simulation log. hooks.logs accumulates per-year as the run
        # progresses, so an aborted run still has every year it completed
        # before the abort in it, and the CSV below carries exactly those.
        if hooks.logs:
            # Sanitize text for CSV compatibility
            sanitized_logs = []
            for log in hooks.logs:
                sanitized_log = {
                    k: (v.replace('\n', ' ').replace('\r', ' ').strip() if isinstance(v, str) else v)
                    for k, v in log.items()
                }
                sanitized_logs.append(sanitized_log)
            log_df = pd.DataFrame(sanitized_logs)
            if "precipitation_flag" in log_df.columns:
                # Re-review 2026-09-29 (NIT): a mix of int 0/1 (Upper Basin)
                # and None (Lower Basin, MEDIUM 4) upcasts a plain int column
                # to float64, rendering "1.0"/"0.0" in the CSV instead of
                # "1"/"0". pandas' nullable Int64 dtype keeps real values as
                # ints and a missing one blank, matching precipitation_mm's
                # own blank-for-missing behavior.
                log_df["precipitation_flag"] = log_df["precipitation_flag"].astype("Int64")
            log_df.to_csv(output_dir / "simulation_log.csv", index=False)

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
    p.add_argument("--paper-water-margin", type=float, default=0.4,
                   help="Water-right history-anchor margin, on [0, 1]: the share by "
                        "which a real agent's legal ceiling may exceed its 1971-2018 "
                        "observed peak. Item 36f/36g (2026-10-05): basin-specific -- "
                        "Lower Basin water_right = grid_top_af alone; Upper Basin "
                        "water_right = (1 + paper_water_margin) * peak_obs_af alone "
                        "(no grid-top term). Only affects --real profiles "
                        "(create_profiles_from_data). Default 0.4 (see "
                        "irrigation_personas.create_profiles_from_data docstring and "
                        "docs/irrigation_physics.md for the derivation). Recorded in "
                        "reproducibility_manifest.json and config_snapshot.yaml.")
    p.add_argument("--lb-non-ag-total-maf", type=float, default=None,
                   help="LB non-farm total (M&I + tribal + CAP + system losses, MAF/yr). "
                        "Default: WaterSystemConfig's own default (5.2, the record-"
                        "implied value at lb_return_flow_fraction=0.0 -- see "
                        "analysis/hindcast_v3.py (record_implied_non_ag)). A "
                        "--lb-return-flow-fraction sensitivity run (below) MUST pass "
                        "the record-implied value for that SAME fraction here (derived "
                        "first via 'python analysis/hindcast_v3.py "
                        "--lb-return-flow-fraction f'; see the runbook's return-flow "
                        "sensitivity pair) -- the 5.2 default was derived at f=0.0, and "
                        "pairing a non-zero f with the f=0.0 constant double-counts "
                        "water the fraction already credits back to Mead. Recorded via "
                        "_record_water_system_config_provenance.")
    p.add_argument("--lb-return-flow-fraction", type=float, default=None,
                   help="Item 36e (2026-10-05) CPU sensitivity: the share of the LB "
                        "agricultural draw treated as reused downstream (e.g. "
                        "credited toward the Mexico delivery) instead of charged "
                        "against Mead's outflow, on [0, 0.5]. Default: "
                        "WaterSystemConfig's own default (0.0, byte-identical). "
                        "Recorded via _record_water_system_config_provenance.")
    p.add_argument("--min-utilisation-fraction", type=float, default=None,
                   help="2026-10-06 CPU rerun finding (spec item 36k): the minimum-use "
                        "floor, as a fraction of each agent's water right, on [0, 1]. "
                        "Default: WaterSystemConfig's own default (0.10, byte-"
                        "identical). REFUSED at any other value on this runner "
                        "(config/agent_types.yaml's minimum_utilisation_floor message "
                        "hard-codes 10% and is not templated) -- the 0 and 0.05 "
                        "sensitivities (provenance C6b) are FQL-only; use "
                        "run_fql_baseline.py instead. Recorded via "
                        "_record_water_system_config_provenance.")
    p.add_argument("--cluster-method", type=str, default="hy2021",
                   choices=["hy2021", "legacy_centroid"],
                   help="How each real CRSS agent's persona cluster (aggressive / "
                        "forward_looking_conservative / myopic_conservative) is "
                        "assigned. 'hy2021' (default): Hung & Yang (2021) Figure 7's "
                        "own published per-entity assignment (HY2021_CLUSTER_LABELS "
                        "in irrigation_personas.py). 'legacy_centroid': the prior "
                        "4-D nearest-centroid heuristic (_infer_cluster), "
                        "byte-identical to pre-2026-09-28 behaviour -- use this to "
                        "reproduce a corpus generated before --cluster-method "
                        "existed (e.g. the 431adb5e corpus). Only affects --real "
                        "profiles (create_profiles_from_data). Recorded in "
                        "reproducibility_manifest.json and config_snapshot.yaml.")
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
                   help="RETIRED in v3 (WP3): refused at startup. The checks the "
                        "phases switched (consecutive_cap, zero_escape) are no "
                        "longer dispatched.")
    p.add_argument("--ablation-mode", type=str, default=None,
                   choices=["no_demand_ceiling"],
                   help="RETIRED in v3 (WP3): refused at startup. "
                        "demand_ceiling_stabilizer is not dispatched.")
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
                        "(v3: strict | feasibility_only | disabled; the placebo "
                        "and silent arms are strict with --retry-feedback-mode). "
                        "A name the config does not declare is REFUSED at "
                        "startup rather than falling back to 'default' silently.")
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
    p.add_argument("--llm-journal", action="store_true",
                   help="Record every LLM call this run makes to "
                        "llm_journal.jsonl in --output, so the run can be "
                        "resumed with --resume-from if it crashes. Implied "
                        "(always on) when --resume-from is given, so a "
                        "resumed run can itself be resumed again. See "
                        "'Resuming a crashed run' in examples/irrigation_abm/"
                        "README.md.")
    p.add_argument("--resume-from", type=str, default=None,
                   help="Resume a crashed run from its llm_journal.jsonl -- "
                        "pass either that file directly or the crashed run's "
                        "--output directory. Years already completed are "
                        "replayed from the journal (answered from the "
                        "recorded calls, never re-sent to the model); the "
                        "first incomplete year onward runs live. Refuses to "
                        "resume (SystemExit) if an identifying setting -- "
                        "model, seed, memory seed, governance mode, years, "
                        "real/synthetic, or any other prompt-affecting flag "
                        "-- differs from the source run (--workers may "
                        "differ). Output always goes to a NEW --output "
                        "directory; the source run's files are never "
                        "modified. See 'Resuming a crashed run' in "
                        "examples/irrigation_abm/README.md.")
    p.add_argument("--retry-feedback-mode", type=str, default=None,
                   choices=["full", "placebo", "silent"],
                   help="Red-team objection 3 ablation, same three arms as "
                        "run_flood.py's flag of the same name. 'full' (default "
                        "behaviour): the governance retry prompt carries the real "
                        "rule id/reason/suggestion. 'placebo': the validator still "
                        "rejects on the same rules/schedule/fallback, but the "
                        "LLM-facing retry text is a fixed, content-free sentence. "
                        "'silent': the retry prompt is the ORIGINAL prompt, "
                        "byte-for-byte, on every attempt -- no header, no closer, "
                        "no framing at all. None (default) leaves "
                        "global_config.governance.retry_feedback_mode (default "
                        "'full') in agent_types.yaml unchanged, so prompt bytes "
                        "stay identical to a run with this flag omitted entirely. "
                        "Replaces the old config_variants/silent_gemma3_4b/ "
                        "full-config-copy approach (removed 2026-09-27): use "
                        "this flag against the in-tree config instead of "
                        "--config-dir pointing at a stale copy.")
    return p.parse_args()


if __name__ == "__main__":
    main()
