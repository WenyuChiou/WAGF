# SA Flood Experiment Modular Refactor

> **For Claude/Gemini/Codex:** Execute this plan task-by-task. Each task is independent and can be done in parallel.

**Goal:** Refactor the monolithic `run_flood.py` (1126 lines) into a modular architecture with pluggable components.

**Architecture:** Dependency Injection pattern - components are injected into the experiment runner rather than hardcoded. Each component can be swapped without modifying other files.

**Tech Stack:** Python 3.10+, existing broker framework, cognitive_governance

**Worktree:** `.worktrees/sa-modular` (branch: `feat/sa-modular-refactor`)

---

## Overview

```
Current:
examples/single_agent/run_flood.py (1126 lines, everything mixed)

Target:
examples/single_agent_modular/
├── run_flood.py              # Entry point only (~50 lines)
├── components/
│   ├── __init__.py
│   ├── context_builder.py    # FinalContextBuilder
│   ├── memory_factory.py     # Memory engine factory (PLUGGABLE)
│   ├── simulation.py         # ResearchSimulation
│   └── hooks.py              # FinalParityHook
├── agents/
│   ├── __init__.py
│   └── loader.py             # Agent initialization
├── analysis/
│   ├── __init__.py
│   └── plotting.py           # Visualization
└── config/
    ├── __init__.py
    └── experiment_config.py  # CLI + YAML config
```

---

## Task 1: Create Directory Structure

**Files:**
- Create: `examples/single_agent_modular/`
- Create: `examples/single_agent_modular/components/`
- Create: `examples/single_agent_modular/agents/`
- Create: `examples/single_agent_modular/analysis/`
- Create: `examples/single_agent_modular/config/`

**Step 1: Create directories**

```bash
cd /path/to/governed_broker_framework
mkdir -p examples/single_agent_modular/components
mkdir -p examples/single_agent_modular/agents
mkdir -p examples/single_agent_modular/analysis
mkdir -p examples/single_agent_modular/config
```

**Step 2: Create __init__.py files**

```bash
touch examples/single_agent_modular/__init__.py
touch examples/single_agent_modular/components/__init__.py
touch examples/single_agent_modular/agents/__init__.py
touch examples/single_agent_modular/analysis/__init__.py
touch examples/single_agent_modular/config/__init__.py
```

**Step 3: Copy config files from original**

```bash
cp examples/single_agent/agent_types.yaml examples/single_agent_modular/
cp examples/single_agent/skill_registry.yaml examples/single_agent_modular/
cp examples/single_agent/agent_initial_profiles.csv examples/single_agent_modular/
cp examples/single_agent/flood_years.csv examples/single_agent_modular/
```

**Step 4: Commit**

```bash
git add examples/single_agent_modular/
git commit -m "feat(sa-modular): create directory structure"
```

---

## Task 2: Extract Simulation Component

**Files:**
- Create: `examples/single_agent_modular/components/simulation.py`
- Source: `examples/single_agent/run_flood.py` lines 214-278

**Step 1: Create simulation.py**

```python
"""
Flood Simulation Environment.

Handles flood event scheduling, grant availability, and skill execution.
"""
import random
from typing import Dict, List, Any
from broker.interfaces.skill_types import ExecutionResult

# Research Constants
FLOOD_PROBABILITY = 0.2
GRANT_PROBABILITY = 0.5


class ResearchSimulation:
    """
    Simulation environment for flood adaptation research.

    Manages:
    - Flood event scheduling (fixed years or probabilistic)
    - Grant availability
    - Skill execution and state changes
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        flood_years: List[int] = None,
        flood_mode: str = "fixed",
        flood_probability: float = FLOOD_PROBABILITY
    ):
        self.agents = agents
        self.flood_years = flood_years or []
        self.flood_mode = flood_mode
        self.flood_probability = flood_probability
        self.current_year = 0
        self.flood_event = False
        self.grant_available = False

    def advance_year(self) -> Dict[str, Any]:
        """Advance simulation by one year and determine events."""
        self.current_year += 1

        if self.flood_mode == "prob":
            self.flood_event = random.random() < self.flood_probability
        else:
            self.flood_event = self.current_year in self.flood_years

        self.grant_available = random.random() < GRANT_PROBABILITY

        return {
            "flood_event": self.flood_event,
            "grant_available": self.grant_available,
            "current_year": self.current_year
        }

    def execute_skill(self, approved_skill) -> ExecutionResult:
        """Execute an approved skill and return state changes."""
        agent_id = approved_skill.agent_id
        agent = self.agents[agent_id]
        skill = approved_skill.skill_name
        state_changes = {}

        if skill == "elevate_house":
            if getattr(agent, "elevated", False):
                return ExecutionResult(success=False, error="House already elevated.")
            state_changes["elevated"] = True

        elif skill == "buy_insurance":
            state_changes["has_insurance"] = True

        elif skill == "relocate":
            state_changes["relocated"] = True
            agent.is_active = False

        # Insurance expiry logic
        if skill != "buy_insurance":
            state_changes["has_insurance"] = False

        return ExecutionResult(success=True, state_changes=state_changes)


def classify_adaptation_state(agent) -> str:
    """Classify agent's current adaptation state for reporting."""
    if getattr(agent, "relocated", False):
        return "Relocate"
    elevated = getattr(agent, "elevated", False)
    has_insurance = getattr(agent, "has_insurance", False)
    if elevated and has_insurance:
        return "Both Flood Insurance and House Elevation"
    elif elevated:
        return "Only House Elevation"
    elif has_insurance:
        return "Only Flood Insurance"
    else:
        return "Do Nothing"
```

**Step 2: Commit**

```bash
git add examples/single_agent_modular/components/simulation.py
git commit -m "feat(sa-modular): extract ResearchSimulation component"
```

---

## Task 3: Extract Memory Factory (PLUGGABLE)

**Files:**
- Create: `examples/single_agent_modular/components/memory_factory.py`
- Source: `examples/single_agent/run_flood.py` lines 189-211, 754-841

**Step 1: Create memory_factory.py**

```python
"""
Memory Engine Factory.

PLUGGABLE: To add a new memory system:
1. Import or define your engine class
2. Add a case to create_memory_engine()
3. Register any SDK scorers if needed

No other files need to change.
"""
from typing import Dict, Any, Optional
from broker.components.memory_engine import (
    WindowMemoryEngine,
    ImportanceMemoryEngine,
    HumanCentricMemoryEngine,
    HierarchicalMemoryEngine,
    create_memory_engine as broker_create_engine
)


class DecisionFilteredMemoryEngine:
    """
    Proxy memory engine that filters out decision memories.
    Maintains parity with baseline experiment.
    """

    def __init__(self, inner):
        self.inner = inner

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        if "Decided to:" in content:
            return
        return self.inner.add_memory(agent_id, content, metadata)

    def add_memory_for_agent(self, agent, content: str, metadata: Optional[Dict[str, Any]] = None):
        if "Decided to:" in content:
            return
        if hasattr(self.inner, 'add_memory_for_agent'):
            return self.inner.add_memory_for_agent(agent, content, metadata)
        return self.inner.add_memory(agent.id, content, metadata)

    def retrieve(self, agent, query: Optional[str] = None, top_k: int = 3, **kwargs):
        return self.inner.retrieve(agent, query=query, top_k=top_k, **kwargs)

    def clear(self, agent_id: str):
        return self.inner.clear(agent_id)


def create_memory_engine(
    engine_type: str,
    config: Dict[str, Any],
    window_size: int = 5,
    ranking_mode: str = "legacy",
    filter_decisions: bool = True
):
    """
    Factory function for memory engines.

    Args:
        engine_type: One of "window", "importance", "humancentric", "hierarchical", "universal"
        config: YAML config dict (agent_types.yaml content)
        window_size: Memory window size
        ranking_mode: "legacy" or "weighted" for humancentric
        filter_decisions: Whether to filter "Decided to:" memories

    Returns:
        Memory engine instance

    To add a new memory system:
        1. Add a new elif branch here
        2. Import/define your engine class
        3. That's it - no other files need changes
    """
    global_cfg = config.get('global_config', {})
    household_mem = config.get('household', {}).get('memory', {})
    shared_mem = config.get('shared', {}).get('memory_config', {})

    # Merge configs
    final_mem_cfg = {**shared_mem, **household_mem}
    retrieval_w = final_mem_cfg.get('retrieval_weights', {})
    global_mem = global_cfg.get('memory', {})

    engine = None

    if engine_type == "window":
        engine = WindowMemoryEngine(window_size=window_size)
        print(f" Using WindowMemoryEngine (sliding window, size={window_size})")

    elif engine_type == "importance":
        flood_categories = {
            "critical": ["flood", "flooded", "damage", "severe", "destroyed"],
            "high": ["grant", "elevation", "insurance", "protected"],
            "medium": ["neighbor", "relocated", "observed", "pct%"]
        }
        engine = ImportanceMemoryEngine(
            window_size=window_size,
            top_k_significant=global_mem.get('top_k_significant', 2),
            decay_rate=global_mem.get('decay_rate', 0.1),
            categories=flood_categories
        )
        print(f" Using ImportanceMemoryEngine (active retrieval with flood-specific keywords)")

    elif engine_type == "humancentric":
        engine = HumanCentricMemoryEngine(
            window_size=window_size,
            top_k_significant=global_mem.get('top_k_significant', 2),
            consolidation_prob=global_mem.get('consolidation_probability', 0.7),
            consolidation_threshold=global_mem.get('consolidation_threshold', 0.6),
            decay_rate=global_mem.get('decay_rate', 0.1),
            emotional_weights=final_mem_cfg.get("emotional_weights"),
            source_weights=final_mem_cfg.get("source_weights"),
            W_recency=retrieval_w.get("recency", 0.3),
            W_importance=retrieval_w.get("importance", 0.5),
            W_context=retrieval_w.get("context", 0.2),
            ranking_mode=ranking_mode,
            seed=42
        )
        print(f" Using HumanCentricMemoryEngine (emotional encoding, window={window_size})")

    elif engine_type == "hierarchical":
        engine = HierarchicalMemoryEngine(
            window_size=window_size,
            semantic_top_k=3
        )
        print(f" Using HierarchicalMemoryEngine (Tiered: Core, Episodic, Semantic)")

    elif engine_type == "universal":
        engine = broker_create_engine(
            engine_type="universal",
            window_size=window_size,
            top_k_significant=global_mem.get('top_k_significant', 2),
            consolidation_prob=global_mem.get('consolidation_probability', 0.7),
            consolidation_threshold=global_mem.get('consolidation_threshold', 0.6),
            decay_rate=global_mem.get('decay_rate', 0.1),
            emotional_weights=final_mem_cfg.get("emotional_weights"),
            source_weights=final_mem_cfg.get("source_weights"),
            W_recency=retrieval_w.get("recency", 0.3),
            W_importance=retrieval_w.get("importance", 0.5),
            W_context=retrieval_w.get("context", 0.2),
            ranking_mode="dynamic",
            arousal_threshold=final_mem_cfg.get("arousal_threshold", 0.5),
            ema_alpha=final_mem_cfg.get("ema_alpha", 0.3),
            seed=42
        )
        print(f" Using UniversalCognitiveEngine (v3 Surprise Engine, window={window_size})")

    else:
        # Default fallback
        engine = WindowMemoryEngine(window_size=window_size)
        print(f" Using WindowMemoryEngine (default fallback)")

    # Apply decision filter if requested
    if filter_decisions:
        engine = DecisionFilteredMemoryEngine(engine)

    return engine


# =============================================================================
# EXTENSION POINT: Add new memory systems here
# =============================================================================
#
# Example: Adding a new "semantic" memory engine
#
# 1. Import or define:
#    from my_package import SemanticMemoryEngine
#
# 2. Add case in create_memory_engine():
#    elif engine_type == "semantic":
#        engine = SemanticMemoryEngine(
#            embedding_model=config.get("embedding_model", "all-MiniLM-L6-v2"),
#            ...
#        )
#
# 3. Done! Use with: --memory-engine semantic
```

**Step 2: Commit**

```bash
git add examples/single_agent_modular/components/memory_factory.py
git commit -m "feat(sa-modular): extract pluggable memory factory"
```

---

## Task 4: Extract Context Builder

**Files:**
- Create: `examples/single_agent_modular/components/context_builder.py`
- Source: `examples/single_agent/run_flood.py` lines 59-186

**Step 1: Create context_builder.py**

```python
"""
Flood-Specific Context Builder.

Extends TieredContextBuilder with flood domain verbalization and skill filtering.
"""
from typing import Dict, Any
from broker.components.context_builder import TieredContextBuilder


def _get_flood_ext(profile):
    """Get flood extension from agent profile."""
    return getattr(profile, "extensions", {}).get("flood")


def _ext_value(ext, key, default=None):
    """Safely get value from extension dict or object."""
    if ext is None:
        return default
    if isinstance(ext, dict):
        return ext.get(key, default)
    return getattr(ext, key, default)


class FloodContextBuilder(TieredContextBuilder):
    """
    Context builder specialized for flood adaptation experiments.

    Features:
    - Verbalizes trust values into natural language
    - Filters skills based on agent state (e.g., no elevate if already elevated)
    - Formats memory for prompt compatibility
    - Generates dynamic skill maps for parser
    """

    def __init__(self, *args, sim=None, memory_top_k: int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        self.sim = sim
        self.memory_top_k = memory_top_k

    def _verbalize_trust(self, trust_value: float, category: str = "insurance") -> str:
        """Convert numeric trust to natural language."""
        if category == "insurance":
            if trust_value >= 0.8:
                return "strongly trust"
            elif trust_value >= 0.5:
                return "moderately trust"
            elif trust_value >= 0.2:
                return "have slight doubts about"
            else:
                return "deeply distrust"
        elif category == "neighbors":
            if trust_value >= 0.8:
                return "highly rely on"
            elif trust_value >= 0.5:
                return "generally trust"
            elif trust_value >= 0.2:
                return "are skeptical of"
            else:
                return "completely ignore"
        return "trust"

    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        """Build context with flood-specific enhancements."""
        agent = self.agents[agent_id]

        # Retrieve memories with world state for surprise engine
        if hasattr(self.hub, 'memory_engine') and self.hub.memory_engine:
            current_depth = _ext_value(
                _get_flood_ext(agent), 'base_depth_m', 0.0
            ) if self.sim.flood_event else 0.0
            world_state = {"flood_depth": current_depth}

            personal_memory = self.hub.memory_engine.retrieve(
                agent,
                top_k=self.memory_top_k,
                world_state=world_state
            )
        else:
            personal_memory = []

        # Get base context
        context = super().build(agent_id, **kwargs)
        personal = context.get('personal', {})
        personal['memory'] = personal_memory

        # Extract live agent state
        elevated = getattr(agent, 'elevated', False)
        has_insurance = getattr(agent, 'has_insurance', False)
        trust_ins = getattr(agent, 'trust_in_insurance', 0.5)
        trust_nb = getattr(agent, 'trust_in_neighbors', 0.5)

        # Inject verbalized variables
        personal['elevation_status_text'] = (
            "Your house is already elevated, which provides very good protection."
            if elevated else "You have not elevated your home."
        )
        personal['insurance_status'] = "have" if has_insurance else "do not have"
        personal['trust_insurance_text'] = self._verbalize_trust(trust_ins, "insurance")
        personal['trust_neighbors_text'] = self._verbalize_trust(trust_nb, "neighbors")

        # Filter available skills
        available_skills = context.get('available_skills', [])
        filtered_skills = []
        for s in available_skills:
            skill_id = s.get('skill_name') if isinstance(s, dict) else s
            if skill_id == "elevate_house" and elevated:
                continue
            filtered_skills.append(s)
        context['available_skills'] = filtered_skills

        # Format memory for prompt
        mem_val = personal.get('memory', [])
        if isinstance(mem_val, dict):
            lines = []
            if mem_val.get("core"):
                core_str = " ".join([f"{k}={v}" for k, v in mem_val["core"].items()])
                lines.append(f"CORE: {core_str}")
            if mem_val.get("semantic"):
                lines.append("HISTORIC:")
                lines.extend([f"  - {m}" for m in mem_val["semantic"]])
            if mem_val.get("episodic"):
                lines.append("RECENT:")
                lines.extend([f"  - {m}" for m in mem_val["episodic"]])
            personal['memory'] = "\n".join(lines) if lines else "No memory available"
        elif isinstance(mem_val, list):
            personal['memory'] = "\n".join([f"- {m}" for m in mem_val])

        # Generate options text and skill map
        dynamic_skill_map = {}
        if elevated:
            personal['options_text'] = (
                "1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)\n"
                "2. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)\n"
                "3. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"
            )
            personal['valid_choices_text'] = "1, 2, or 3"
            dynamic_skill_map = {
                "1": "buy_insurance",
                "2": "relocate",
                "3": "do_nothing"
            }
        else:
            personal['options_text'] = (
                "1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)\n"
                "2. Elevate your house (High upfront cost but can prevent most physical damage.)\n"
                "3. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)\n"
                "4. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"
            )
            personal['valid_choices_text'] = "1, 2, 3, or 4"
            dynamic_skill_map = {
                "1": "buy_insurance",
                "2": "elevate_house",
                "3": "relocate",
                "4": "do_nothing"
            }

        personal['skills'] = personal['options_text']
        personal['dynamic_skill_map'] = dynamic_skill_map
        context["skill_variant"] = "elevated" if elevated else "non_elevated"

        return context
```

**Step 2: Commit**

```bash
git add examples/single_agent_modular/components/context_builder.py
git commit -m "feat(sa-modular): extract FloodContextBuilder"
```

---

## Task 5: Extract Lifecycle Hooks

**Files:**
- Create: `examples/single_agent_modular/components/hooks.py`
- Source: `examples/single_agent/run_flood.py` lines 279-491

**Step 1: Create hooks.py**

```python
"""
Flood Experiment Lifecycle Hooks.

Handles pre_year, post_step, post_year logic for flood simulation.
"""
import random
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional

from .simulation import classify_adaptation_state

# Research Constants
RANDOM_MEMORY_RECALL_CHANCE = 0.2
PAST_EVENTS = [
    "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
    "Some residents reported delays when processing their flood insurance claims",
    "A few households in the area elevated their homes before recent floods",
    "The city previously introduced a program offering elevation support to residents",
    "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
]


class FloodHooks:
    """
    Lifecycle hooks for flood adaptation experiment.

    Manages:
    - pre_year: Flood events, memories, social observation
    - post_step: State changes, decision logging
    - post_year: Trust updates, reflection, logging
    """

    def __init__(
        self,
        sim,
        runner,
        reflection_engine=None,
        output_dir=None
    ):
        self.sim = sim
        self.runner = runner
        self.reflection_engine = reflection_engine
        self.logs = []
        self.yearly_decisions = {}
        self.output_dir = Path(output_dir) if output_dir else Path(".")

    def pre_year(self, year: int, env, agents: Dict[str, Any]):
        """Pre-year hook: determine flood, add memories."""
        flood_event = self.sim.flood_event

        # Calculate global stats
        active_agents = [a for a in self.sim.agents.values() if not getattr(a, 'relocated', False)]
        total_elevated = sum(1 for a in active_agents if getattr(a, 'elevated', False))
        total_relocated = len(self.sim.agents) - len(active_agents)

        for agent in self.sim.agents.values():
            if getattr(agent, 'relocated', False):
                if len(agent.flood_history) < year:
                    agent.flood_history.append(False)
                continue

            flooded = False
            if flood_event:
                if not agent.elevated:
                    if random.random() < agent.flood_threshold:
                        flooded = True
                        mem = f"Year {year}: Got flooded with $10,000 damage on my house."
                    else:
                        mem = f"Year {year}: A flood occurred, but my house was spared damage."
                else:
                    if random.random() < agent.flood_threshold:
                        flooded = True
                        mem = f"Year {year}: Despite elevation, the flood was severe enough to cause damage."
                    else:
                        mem = f"Year {year}: A flood occurred, but my house was protected by its elevation."
            else:
                mem = f"Year {year}: No flood occurred this year."

            agent.flood_history.append(flooded)
            yearly_memories = [mem]

            # Grant memory
            if self.sim.grant_available:
                yearly_memories.append(f"Year {year}: Elevation grants are available.")

            # Social observation
            num_others = len(self.sim.agents) - 1
            if num_others > 0:
                elev_pct = round(((total_elevated - (1 if agent.elevated else 0)) / num_others) * 100)
                reloc_pct = round((total_relocated / num_others) * 100)
                yearly_memories.append(
                    f"Year {year}: I observe {elev_pct}% of neighbors elevated and {reloc_pct}% relocated."
                )

            # Stochastic recall
            if random.random() < RANDOM_MEMORY_RECALL_CHANCE:
                yearly_memories.append(f"Suddenly recalled: '{random.choice(PAST_EVENTS)}'.")

            # Add consolidated memory
            consolidated_mem = " | ".join(yearly_memories)
            self.runner.memory_engine.add_memory(agent.id, consolidated_mem)

    def post_step(self, agent, result):
        """Post-step hook: log decision, apply state changes."""
        year = self.sim.current_year
        skill_name = None
        appraisals = {}

        if result and result.skill_proposal and result.skill_proposal.reasoning:
            reasoning = result.skill_proposal.reasoning
            for key in ["threat_appraisal", "THREAT_APPRAISAL_LABEL", "threat"]:
                if key in reasoning:
                    appraisals["threat_appraisal"] = reasoning[key]
                    break
            for key in ["coping_appraisal", "COPING_APPRAISAL_LABEL", "coping"]:
                if key in reasoning:
                    appraisals["coping_appraisal"] = reasoning[key]
                    break

        if result and result.approved_skill:
            skill_name = result.approved_skill.skill_name

        self.yearly_decisions[(agent.id, year)] = {
            "skill": skill_name,
            "appraisals": appraisals
        }

        # Apply state changes
        if result and hasattr(result, 'state_changes') and result.state_changes:
            agent.apply_delta(result.state_changes)

        # Update flood threshold on elevation
        if result.approved_skill and result.approved_skill.skill_name == "elevate_house":
            agent.flood_threshold = max(0.001, round(agent.flood_threshold * 0.2, 2))

    def post_year(self, year: int, agents: Dict[str, Any]):
        """Post-year hook: update trust, reflection, logging."""
        total_elevated = sum(1 for a in agents.values() if getattr(a, 'elevated', False))
        total_relocated = sum(1 for a in agents.values() if getattr(a, 'relocated', False))
        community_action_rate = (total_elevated + total_relocated) / len(agents)

        for agent in agents.values():
            if not getattr(agent, 'relocated', False):
                # Trust updates
                last_flood = agent.flood_history[-1] if agent.flood_history else False
                has_ins = getattr(agent, 'has_insurance', False)
                trust_ins = getattr(agent, 'trust_in_insurance', 0.5)

                if has_ins:
                    trust_ins += (-0.10 if last_flood else 0.02)
                else:
                    trust_ins += (0.05 if last_flood else -0.02)
                agent.trust_in_insurance = max(0.0, min(1.0, trust_ins))

                trust_nb = getattr(agent, 'trust_in_neighbors', 0.5)
                if community_action_rate > 0.30:
                    trust_nb += 0.04
                elif last_flood and community_action_rate < 0.10:
                    trust_nb -= 0.05
                else:
                    trust_nb -= 0.01
                agent.trust_in_neighbors = max(0.0, min(1.0, trust_nb))

            # Log entry
            mem_items = self.runner.memory_engine.retrieve(agent, top_k=5)
            mem_str = " | ".join(mem_items)

            decision_data = self.yearly_decisions.get((agent.id, year), {})
            yearly_decision = decision_data.get("skill") if isinstance(decision_data, dict) else decision_data
            appraisals = decision_data.get("appraisals", {}) if isinstance(decision_data, dict) else {}

            if yearly_decision is None and getattr(agent, "relocated", False):
                yearly_decision = "relocated"

            self.logs.append({
                "agent_id": agent.id,
                "year": year,
                "cumulative_state": classify_adaptation_state(agent),
                "yearly_decision": yearly_decision or "N/A",
                "threat_appraisal": appraisals.get("threat_appraisal", "N/A"),
                "coping_appraisal": appraisals.get("coping_appraisal", "N/A"),
                "elevated": getattr(agent, 'elevated', False),
                "has_insurance": getattr(agent, 'has_insurance', False),
                "relocated": getattr(agent, 'relocated', False),
                "trust_insurance": getattr(agent, 'trust_in_insurance', 0),
                "trust_neighbors": getattr(agent, 'trust_in_neighbors', 0),
                "memory": mem_str
            })

        # Print stats
        df_year = pd.DataFrame([l for l in self.logs if l['year'] == year])
        stats = df_year['cumulative_state'].value_counts()
        categories = [
            "Do Nothing", "Only Flood Insurance", "Only House Elevation",
            "Both Flood Insurance and House Elevation", "Relocate"
        ]
        stats_str = " | ".join([f"{cat}: {stats.get(cat, 0)}" for cat in categories])
        print(f"[Year {year}] Stats: {stats_str}")
        print(f"[Year {year}] Avg Trust: Ins={df_year['trust_insurance'].mean():.3f}, Nb={df_year['trust_neighbors'].mean():.3f}")

        # Batch reflection (if enabled)
        if self.reflection_engine and self.reflection_engine.should_reflect("any", year):
            self._run_batch_reflection(year)

    def _run_batch_reflection(self, year: int):
        """Run batch reflection for all agents."""
        refl_cfg = self.runner.broker.config.get_reflection_config()
        batch_size = refl_cfg.get("batch_size", 10)

        candidates = []
        for agent_id, agent in self.sim.agents.items():
            if getattr(agent, "relocated", False):
                continue
            memories = self.runner.memory_engine.retrieve(agent, top_k=10)
            if memories:
                candidates.append({"agent_id": agent_id, "memories": memories})

        if not candidates:
            return

        print(f" [Reflection:Batch] Processing {len(candidates)} agents in batches of {batch_size}...")
        llm_call = self.runner.get_llm_invoke("household")

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i+batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(batch, year)

            try:
                raw_res = llm_call(prompt)
                response_text = raw_res[0] if isinstance(raw_res, tuple) else raw_res

                insights = self.reflection_engine.parse_batch_reflection_response(response_text, batch_ids, year)
                for agent_id, insight in insights.items():
                    if insight:
                        self.reflection_engine.store_insight(agent_id, insight)
                        self.runner.memory_engine.add_memory(
                            agent_id,
                            f"Consolidated Reflection: {insight.summary}",
                            {"significance": 0.9, "emotion": "major", "source": "personal"}
                        )
            except Exception as e:
                print(f" [Reflection:Batch:Error] Batch {i//batch_size+1} failed: {e}")

        print(f" [Reflection:Batch] Completed reflection for Year {year}.")
```

**Step 2: Commit**

```bash
git add examples/single_agent_modular/components/hooks.py
git commit -m "feat(sa-modular): extract FloodHooks component"
```

---

## Task 6: Extract Agent Loader

**Files:**
- Create: `examples/single_agent_modular/agents/loader.py`
- Source: `examples/single_agent/run_flood.py` lines 494-609

**Step 1: Create loader.py**

```python
"""
Agent Loading and Initialization.

Supports loading from:
- Survey data (Excel)
- CSV profiles
"""
from pathlib import Path
from typing import Dict, Any, Optional


def _get_flood_ext(profile):
    return getattr(profile, "extensions", {}).get("flood")


def _ext_value(ext, key, default=None):
    if ext is None:
        return default
    if isinstance(ext, dict):
        return ext.get(key, default)
    return getattr(ext, key, default)


def load_agents_from_survey(
    survey_path: Path,
    max_agents: int = 100,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Load agents from real survey data.

    Uses the survey module to:
    1. Parse Excel survey data
    2. Classify MG/NMG status
    3. Assign flood zones
    4. Generate RCV values
    """
    from broker.modules.survey.agent_initializer import initialize_agents_from_survey
    from cognitive_governance.agents import BaseAgent, AgentConfig

    profiles, stats = initialize_agents_from_survey(
        survey_path=survey_path,
        max_agents=max_agents,
        seed=seed,
        include_hazard=True,
        include_rcv=True
    )

    print(f"[Survey] Loaded {stats['total_agents']} agents from survey")
    print(f"[Survey] MG: {stats['mg_count']} ({stats['mg_ratio']:.1%}), NMG: {stats['nmg_count']}")

    agents = {}
    for profile in profiles:
        config = AgentConfig(
            name=profile.agent_id,
            agent_type="household",
            state_params=[],
            objectives=[],
            constraints=[],
            skills=[],
        )

        flood_ext = _get_flood_ext(profile)
        base_depth = _ext_value(flood_ext, "base_depth_m", 0.0)
        flood_zone = _ext_value(flood_ext, "flood_zone", "unknown")

        base_threshold = 0.3 if base_depth > 0 else 0.1
        if flood_zone in ("deep", "very_deep", "extreme"):
            base_threshold = 0.5
        elif flood_zone == "moderate":
            base_threshold = 0.4
        elif flood_zone == "shallow":
            base_threshold = 0.3

        agent = BaseAgent(config)
        agent.id = profile.agent_id
        agent.agent_type = "household"
        agent.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]

        agent.custom_attributes = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False,
            "trust_in_insurance": 0.5,
            "trust_in_neighbors": 0.5,
            "flood_threshold": base_threshold,
            "identity": profile.identity,
            "is_mg": profile.is_mg,
            "group": profile.group_label,
            "narrative_persona": profile.generate_narrative_persona() or "You are a homeowner with a strong attachment to your community.",
        }

        for k, v in agent.custom_attributes.items():
            setattr(agent, k, v)

        agent.flood_history = []
        agents[agent.id] = agent

    return agents


def load_agents_from_csv(
    profiles_path: Path,
    stress_test: Optional[str] = None
) -> Dict[str, Any]:
    """Load agents from CSV profile file."""
    from broker import load_agents_from_csv as broker_load

    agents = broker_load(str(profiles_path), {
        "id": "id", "elevated": "elevated", "has_insurance": "has_insurance",
        "relocated": "relocated", "trust_in_insurance": "trust_in_insurance",
        "trust_in_neighbors": "trust_in_neighbors", "flood_threshold": "flood_threshold",
        "memory": "memory"
    }, agent_type="household")

    for a in agents.values():
        a.flood_history = []
        a.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
        for k, v in a.custom_attributes.items():
            if k not in ["id", "agent_type"]:
                setattr(a, k, v)

        if not hasattr(a, 'narrative_persona') or not a.narrative_persona:
            a.narrative_persona = "You are a homeowner with a strong attachment to your community."
            a.custom_attributes['narrative_persona'] = a.narrative_persona

    # Apply stress test profiles if specified
    if stress_test:
        _apply_stress_test(agents, stress_test)

    return agents


def _apply_stress_test(agents: Dict[str, Any], stress_test: str):
    """Apply stress test profile modifications."""
    if stress_test == "veteran":
        print(f"[StressTest] Applying 'Optimistic Veteran' profile...")
        for v in agents.values():
            v.trust_in_insurance = 0.9
            v.trust_in_neighbors = 0.1
            v.flood_threshold = 0.8
            v.narrative_persona = (
                f"You are a wealthy homeowner who has lived here for 30 years. "
                f"You believe only depths > {v.flood_threshold}m pose any real threat."
            )
    elif stress_test == "panic":
        print(f"[StressTest] Applying 'Panic Machine' profile...")
        for p in agents.values():
            p.flood_threshold = 0.1
            p.narrative_persona = (
                "You are highly anxious with limited savings. "
                f"Any depth > {p.flood_threshold}m is catastrophic."
            )
```

**Step 2: Commit**

```bash
git add examples/single_agent_modular/agents/loader.py
git commit -m "feat(sa-modular): extract agent loader"
```

---

## Task 7: Extract Plotting

**Files:**
- Create: `examples/single_agent_modular/analysis/plotting.py`
- Source: `examples/single_agent/run_flood.py` lines 983-1052

**Step 1: Create plotting.py**

```python
"""
Visualization for Flood Adaptation Experiments.
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def clean_decision_detailed_plot(state_str: str) -> str:
    """Normalize state string for plotting."""
    s = str(state_str).lower()
    if "relocate" in s:
        return "Relocate (Departing)"
    has_ins = "insurance" in s or "buy_insurance" in s
    has_ele = "elevation" in s or "elevate" in s
    if ("both" in s and "insurance" in s and "elevation" in s) or (has_ins and has_ele):
        return "Insurance + Elevation"
    elif has_ins:
        return "Insurance"
    elif has_ele:
        return "Elevation"
    return "Do Nothing"


def plot_adaptation_results(csv_path: Path, output_dir: Path):
    """Generate stacked bar plot of adaptation evolution."""
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return

        CATEGORIES = [
            "Do Nothing", "Insurance", "Elevation",
            "Insurance + Elevation", "Relocate (Departing)"
        ]
        TAB10 = plt.get_cmap("tab10").colors
        COLOR_MAP = {
            "Do Nothing": TAB10[0],
            "Insurance": TAB10[1],
            "Elevation": TAB10[2],
            "Insurance + Elevation": TAB10[3],
            "Relocate (Departing)": TAB10[4]
        }

        state_col = 'cumulative_state' if 'cumulative_state' in df.columns else 'decision'
        if state_col not in df.columns:
            return

        # Handle attrition
        df['temp_state_check'] = df[state_col].astype(str).str.lower()
        reloc_rows = df[df['temp_state_check'].str.contains("relocate")]
        if not reloc_rows.empty:
            first_reloc = reloc_rows.groupby('agent_id')['year'].min().reset_index()
            first_reloc.columns = ['agent_id', 'first_reloc_year']
            df = df.merge(first_reloc, on='agent_id', how='left')
            df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]

        df['norm_raw'] = df[state_col].astype(str)

        # Calculate distribution
        years = sorted(df['year'].unique())
        records = []
        for y in years:
            year_data = df[df['year'] == y]
            states = year_data['norm_raw'].apply(clean_decision_detailed_plot)
            counts = states.value_counts()
            records.append([counts.get(cat, 0) for cat in CATEGORIES])

        df_res = pd.DataFrame(records, columns=CATEGORIES, index=years)

        # Plot
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = [COLOR_MAP[c] for c in CATEGORIES]
        df_res.plot(kind='bar', stacked=True, color=colors, ax=ax, width=0.85)

        ax.set_title("Adaptation Strategy Evolution (Cumulative)", fontsize=14, fontweight='bold')
        ax.set_xlabel("Year")
        ax.set_ylabel("Population Count")
        ax.set_ylim(0, 100)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        ax.legend(title="State", bbox_to_anchor=(1.05, 1), loc='upper left')

        plt.tight_layout()
        save_path = output_dir / "adaptation_cumulative_state.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Generated plot: {save_path}")
    except Exception as e:
        print(f"Plotting failed: {e}")
```

**Step 2: Commit**

```bash
git add examples/single_agent_modular/analysis/plotting.py
git commit -m "feat(sa-modular): extract plotting module"
```

---

## Task 8: Create Entry Point

**Files:**
- Create: `examples/single_agent_modular/run_flood.py`

**Step 1: Create clean entry point (~100 lines)**

```python
"""
SA Flood Adaptation Experiment - Modular Version.

Entry point that wires together pluggable components.
To modify any component, edit the corresponding file in components/ or agents/.
"""
import sys
import yaml
import random
import argparse
import pandas as pd
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from broker import ExperimentBuilder
from broker.components.social_graph import NeighborhoodGraph
from broker.components.interaction_hub import InteractionHub
from broker.components.skill_registry import SkillRegistry
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor

# Local modular components
from components.simulation import ResearchSimulation
from components.memory_factory import create_memory_engine
from components.context_builder import FloodContextBuilder
from components.hooks import FloodHooks
from agents.loader import load_agents_from_csv, load_agents_from_survey
from analysis.plotting import plot_adaptation_results


def main():
    parser = argparse.ArgumentParser(description="SA Flood Experiment (Modular)")
    parser.add_argument("--model", type=str, default="llama3.2:3b")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--memory-engine", type=str, default="window",
                        choices=["window", "importance", "humancentric", "hierarchical", "universal"])
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--governance-mode", type=str, default="strict",
                        choices=["strict", "relaxed", "disabled"])
    parser.add_argument("--survey-mode", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # Seed
    seed = args.seed or random.randint(0, 1000000)
    random.seed(seed)

    # Paths
    base_path = Path(__file__).parent
    config_path = base_path / "agent_types.yaml"

    # Load config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Load agents (PLUGGABLE: edit agents/loader.py)
    if args.survey_mode:
        survey_path = base_path.parent / "multi_agent" / "input" / "initial_household data.xlsx"
        agents = load_agents_from_survey(survey_path, max_agents=args.agents, seed=seed)
    else:
        agents = load_agents_from_csv(base_path / "agent_initial_profiles.csv")

    # Load flood years
    flood_years = sorted(pd.read_csv(base_path / "flood_years.csv")['Flood_Years'].tolist())

    # Create components (PLUGGABLE: edit respective files)
    sim = ResearchSimulation(agents, flood_years)

    memory_engine = create_memory_engine(  # Edit components/memory_factory.py
        engine_type=args.memory_engine,
        config=config,
        window_size=args.window_size
    )

    registry = SkillRegistry()
    registry.register_from_yaml(str(base_path / "skill_registry.yaml"))

    graph = NeighborhoodGraph(list(agents.keys()), k=4)
    hub = InteractionHub(graph)

    ctx_builder = FloodContextBuilder(  # Edit components/context_builder.py
        agents=agents,
        hub=hub,
        sim=sim,
        skill_registry=registry,
        prompt_templates={"household": config.get('household', {}).get('prompt_template', '')},
        yaml_path=str(config_path),
        memory_top_k=args.window_size
    )

    # Output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        model_folder = f"{args.model.replace(':','_')}_{args.governance_mode}"
        output_dir = base_path / "results" / model_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build experiment
    builder = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(sim)
        .with_context_builder(ctx_builder)
        .with_skill_registry(registry)
        .with_memory_engine(memory_engine)
        .with_governance(args.governance_mode, config_path)
        .with_exact_output(str(output_dir))
        .with_seed(seed)
    )

    runner = builder.build()

    # Inject hooks (PLUGGABLE: edit components/hooks.py)
    hooks = FloodHooks(sim, runner, output_dir=output_dir)
    runner.hooks = {
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year
    }

    # Run
    runner.run(llm_invoke=create_llm_invoke(args.model, verbose=args.verbose))

    # Finalize
    if runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    # Save logs
    csv_path = output_dir / "simulation_log.csv"
    pd.DataFrame(hooks.logs).to_csv(csv_path, index=False)

    # Plot (PLUGGABLE: edit analysis/plotting.py)
    plot_adaptation_results(csv_path, output_dir)

    # Summary
    GovernanceAuditor().print_summary()
    print(f"--- Complete! Results in {output_dir} ---")


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add examples/single_agent_modular/run_flood.py
git commit -m "feat(sa-modular): create clean entry point"
```

---

## Task 9: Verify and Test

**Step 1: Run quick test**

```bash
cd examples/single_agent_modular
python run_flood.py --model llama3.2:3b --years 3 --agents 10 --verbose
```

**Step 2: Compare with original**

```bash
# Run original
cd ../single_agent
python run_flood.py --model llama3.2:3b --years 3 --agents 10 --output /tmp/original

# Run modular
cd ../single_agent_modular
python run_flood.py --model llama3.2:3b --years 3 --agents 10 --output /tmp/modular

# Compare outputs
diff /tmp/original/simulation_log.csv /tmp/modular/simulation_log.csv
```

**Step 3: Final commit**

```bash
git add .
git commit -m "test(sa-modular): verify parity with original"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-01-27-sa-modular-refactor.md`.

**For Gemini CLI / Codex:**
1. Clone repo and checkout worktree: `cd .worktrees/sa-modular`
2. Execute tasks 1-9 in order
3. Each task is independent after Task 1 (directory structure)
4. Run verification in Task 9 to confirm parity

**Parallel Execution Option:**
- Tasks 2-7 can run in parallel (all extract from original)
- Task 8 depends on Tasks 2-7
- Task 9 depends on Task 8
