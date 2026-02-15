# Wave 2 Expert Review: LLM Engineering Specialist

**Reviewer**: Dr. Kevin Liu (LLM Engineering Specialist)
**Focus**: Prompt-output alignment, hallucination detection, cross-LLM portability, scaling
**Date**: 2026-02-14
**Overall Score**: 3.1 / 5.0

**One-sentence summary**: The C&V module has a well-factored theory abstraction layer (BehavioralTheory protocol) and solid metric definitions, but its trace extraction pipeline is brittle to LLM output format variation, hallucination detection is domain-hardcoded, and CACR conflates prompt compliance with genuine reasoning -- all fixable, but requiring deliberate LLM-engineering work before the module can claim universality.

---

## Dimension Scores

| Dimension | Score | Summary |
|-----------|-------|---------|
| D1: LLM Output Parsing Robustness | 2.5 / 5 | Fixed path extraction; no schema negotiation or fallback parsing |
| D2: Hallucination Detection Generalizability | 1.5 / 5 | Three hardcoded flood rules; no protocol, no registry |
| D3: Prompt-Metric Alignment | 2.5 / 5 | CACR measures correlation not causation; CGR partially mitigates |
| D4: LLM Calibration & Sycophancy | 2.0 / 5 | No sycophancy probes; no adversarial tests; ICC is necessary but not sufficient |
| D5: Cross-LLM Portability | 3.0 / 5 | Theory protocol is LLM-agnostic; trace format and extraction are not |
| D6: Scaling to Large Trace Volumes | 2.5 / 5 | Pure Python for-loops; will not survive 1M+ traces |
| D7: Roadmap to Universal Grade | 3.5 / 5 | Architecture is 80% there; implementation needs targeted refactoring |

---

## Top 3 LLM-Engineering Strengths

### S1: BehavioralTheory Protocol is genuinely extensible

The `BehavioralTheory` Protocol (runtime-checkable, duck-typed) is one of the best abstractions I have seen in LLM-ABM validation code. The PMT, TPB, and IrrigationWSA examples demonstrate that a new domain can be added by implementing ~5 methods without touching L1 computation logic. The `extract_constructs` / `get_coherent_actions` / `is_sensible_action` triad cleanly separates theory specification from metric computation. This is a publishable design pattern.

### S2: CGR breaks the CACR circularity problem

The Construct Grounding Rate is a clever anti-circularity mechanism. By deriving "expected" construct levels from objective state variables (flood zone, income, flood count) and comparing them against LLM-assigned labels, CGR provides an independent check on whether the LLM is actually reading the context or just parroting prompt structure. The adjacent-match tolerance (plus/minus 1 ordinal level) and Cohen's kappa are appropriate for ordinal construct spaces. This addresses one of the most common critiques of construct-action metrics in LLM-ABM work.

### S3: The UNKNOWN sentinel strategy is correct

Returning `"UNKNOWN"` for failed extractions (rather than defaulting to `"M"` or silently dropping traces) is the right LLM-engineering choice. It allows downstream metrics to exclude uninterpretable outputs without biasing CACR upward. The extraction failure count is surfaced, which is essential for diagnosing whether an LLM's output format is compatible with the pipeline. Many frameworks I have reviewed silently default to a mid-level, inflating coherence rates.

---

## Top 3 LLM-Engineering Gaps

### G1: Trace extraction is hardwired to a single JSON schema

The extraction functions (`_extract_tp_label`, `_extract_cp_label`, `_extract_action`) assume a fixed two-level nesting: `trace["skill_proposal"]["reasoning"]["TP_LABEL"]`. This is a WAGF-specific schema. Other frameworks (AutoGen, CrewAI, LangGraph) emit traces in completely different formats. Even within WAGF, if the prompt template changes the key name from `TP_LABEL` to `threat_perception_level`, extraction breaks silently (returns UNKNOWN, inflating the failure count without error).

**Critical failure mode**: If an LLM returns reasoning as a free-text string instead of a structured dict (common with Claude, GPT-4 in non-JSON mode, and all open-weight models without constrained decoding), the `isinstance(reasoning, dict)` check will fail and every trace falls through to `"UNKNOWN"`. The module has no regex fallback, no schema negotiation, and no LLM-specific adapter layer.

### G2: Hallucination detection has no extensibility mechanism

`_is_hallucination()` in `flood.py` contains exactly 3 rules, all flood-specific:
1. Elevate when already elevated
2. Act after buyout
3. Renter elevating

There is no registry, no protocol, no base class. The function is imported directly in `l1_micro.py`. A finance domain would need entirely different rules (e.g., short-selling a delisted stock, buying options after expiry). An epidemic domain needs yet another set (e.g., vaccinating an already-immune agent). The current design requires forking `l1_micro.py` for each domain, which defeats the purpose of the modular architecture.

### G3: CACR cannot distinguish genuine reasoning from prompt echoing

When the LLM prompt contains explicit PMT construct labels (e.g., "Assess your Threat Perception: VL/L/M/H/VH"), CACR measures whether the LLM echoes those labels consistently with an action lookup table. This is prompt compliance, not theory coherence. A model that memorizes "if TP=VH and CP=H, output elevate" scores perfectly on CACR without any genuine threat-coping reasoning.

CGR partially mitigates this (by checking if construct labels match objective state), but CACR itself remains a correlation metric. The framework has no:
- Ablation test (remove construct labels from prompt, re-run, compare CACR)
- Counterfactual probe (present contradictory state vs. label, check which the LLM follows)
- Free-text reasoning analysis (does the reasoning chain mention relevant factors before labeling?)

---

## Specific Recommendations

### R1: Schema-Negotiated Trace Extraction

Replace hardcoded path extraction with a configurable `TraceSchema`:

```python
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

@dataclass
class TraceSchema:
    """Configurable trace field extraction paths."""
    action_paths: List[str] = field(default_factory=lambda: [
        "approved_skill.skill_name",
        "skill_proposal.skill_name",
    ])
    construct_paths: Dict[str, List[str]] = field(default_factory=dict)
    # e.g., {"TP": ["skill_proposal.reasoning.TP_LABEL", "TP_LABEL"]}

    fallback_regex: Optional[Dict[str, str]] = None
    # e.g., {"TP": r"Threat Perception:\s*(VL|L|M|H|VH)"}

    action_normalizer: Optional[Callable] = None

    def extract_field(self, trace: Dict, paths: List[str], default="UNKNOWN") -> str:
        for path in paths:
            value = trace
            for key in path.split("."):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    value = None
                    break
            if value is not None and isinstance(value, str):
                return value
        # Regex fallback for free-text LLM output
        if self.fallback_regex:
            import re
            raw_text = str(trace.get("raw_output", ""))
            for path_key, pattern in self.fallback_regex.items():
                if path_key in [p.split(".")[-1] for p in paths]:
                    match = re.search(pattern, raw_text)
                    if match:
                        return match.group(1)
        return default
```

This allows each domain/LLM combination to declare its trace schema at configuration time, with regex fallback for free-text outputs.

### R2: HallucinationDetector Protocol

```python
from typing import Dict, List, Protocol

class HallucinationDetector(Protocol):
    """Domain-specific hallucination detection."""

    @property
    def name(self) -> str: ...

    def is_hallucination(self, trace: Dict) -> bool: ...

    def explain(self, trace: Dict) -> Optional[str]:
        """Return human-readable explanation if hallucination, else None."""
        ...

class FloodHallucinationDetector:
    """Flood ABM: physically impossible actions given agent state."""

    @property
    def name(self) -> str:
        return "flood_physical"

    def is_hallucination(self, trace: Dict) -> bool:
        # ... existing 3 rules ...
        pass

    def explain(self, trace: Dict) -> Optional[str]:
        # ... return "Renter cannot elevate" etc. ...
        pass

class CompositeHallucinationDetector:
    """Chains multiple detectors."""

    def __init__(self, detectors: List[HallucinationDetector]):
        self._detectors = detectors

    def is_hallucination(self, trace: Dict) -> bool:
        return any(d.is_hallucination(trace) for d in self._detectors)
```

This mirrors the BehavioralTheory pattern. The `explain()` method is essential for debugging -- when R_H spikes, researchers need to know which rule fired, not just a boolean.

### R3: Sycophancy / Prompt-Echo Detection Protocol

Add a new L3 sub-metric: **Prompt-Independence Score (PIS)**.

```python
def compute_prompt_independence_score(
    traces_with_labels: List[Dict],      # Standard run (prompts include TP_LABEL)
    traces_without_labels: List[Dict],    # Ablated run (prompts omit construct labels)
    theory: BehavioralTheory,
) -> Dict:
    """
    Measures how much CACR depends on explicit construct labels in the prompt.

    If PIS ~= 1.0: LLM reasons independently of prompt labels.
    If PIS ~= 0.0: LLM is parroting prompt structure.
    """
    cacr_with = compute_l1_metrics(traces_with_labels, theory=theory).cacr
    cacr_without = compute_l1_metrics(traces_without_labels, theory=theory).cacr

    # PIS = CACR_without / CACR_with (capped at 1.0)
    pis = min(cacr_without / cacr_with, 1.0) if cacr_with > 0 else 0.0

    return {
        "pis": round(pis, 4),
        "cacr_with_labels": round(cacr_with, 4),
        "cacr_without_labels": round(cacr_without, 4),
        "interpretation": (
            "genuine_reasoning" if pis > 0.7
            else "partially_prompted" if pis > 0.4
            else "prompt_dependent"
        ),
    }
```

This requires two experiment runs (one with labels, one without), but it is the only rigorous way to test whether CACR reflects genuine theory alignment. The WAGF governance pipeline already supports prompt variants, so this should be achievable.

### R4: Vectorized Trace Processing for Scale

The current per-trace for-loop in `compute_l1_metrics` will not scale beyond ~100K traces. For 1M+ traces (finance, epidemiology, traffic):

```python
import pandas as pd
import numpy as np

def compute_l1_metrics_vectorized(
    traces_df: pd.DataFrame,  # Pre-parsed into DataFrame
    theory: BehavioralTheory,
    agent_type: str = "owner",
) -> L1Metrics:
    """Vectorized L1 computation for large trace volumes."""

    # Vectorized construct extraction (theory must support batch mode)
    constructs_df = traces_df[["TP_LABEL", "CP_LABEL"]].copy()
    valid_mask = (constructs_df != "UNKNOWN").all(axis=1)

    # Vectorized coherence check via merge with rule table
    rules_df = pd.DataFrame([
        {"TP": tp, "CP": cp, "coherent_actions": actions}
        for (tp, cp), actions in theory._rules.items()
    ])

    merged = constructs_df[valid_mask].merge(
        rules_df, left_on=["TP_LABEL", "CP_LABEL"],
        right_on=["TP", "CP"], how="left"
    )

    coherent_mask = merged.apply(
        lambda r: r["action"] in r["coherent_actions"]
        if isinstance(r["coherent_actions"], list) else False, axis=1
    )

    # ... rest vectorized similarly
```

This is a Phase 2 optimization -- not needed for the current 5K-52K trace regime, but architecturally important to plan for. The key insight is that `BehavioralTheory.get_coherent_actions` should also support a batch mode returning a boolean mask.

### R5: Domain-Agnostic CGR via GroundingRule Registry

```python
from typing import Callable, Dict, List

class GroundingRule:
    """Maps objective state fields to expected construct levels."""

    def __init__(
        self,
        construct: str,  # e.g., "TP"
        state_fields: List[str],  # e.g., ["flood_zone", "flood_count"]
        grounding_fn: Callable[[Dict], str],  # state_before -> expected level
    ):
        self.construct = construct
        self.state_fields = state_fields
        self.grounding_fn = grounding_fn

class CGREngine:
    """Domain-agnostic CGR computation."""

    def __init__(self, rules: List[GroundingRule]):
        self._rules = {r.construct: r for r in rules}

    def compute(self, traces: List[Dict], theory: BehavioralTheory) -> Dict:
        # ... generic CGR using registered rules ...
        pass

# Usage for flood:
flood_cgr = CGREngine([
    GroundingRule("TP", ["flood_zone", "flood_count"], ground_tp_from_state),
    GroundingRule("CP", ["mg", "income", "elevated"], ground_cp_from_state),
])

# Usage for irrigation:
irrigation_cgr = CGREngine([
    GroundingRule("WSA", ["reservoir_level", "drought_months"], ground_wsa_from_state),
    GroundingRule("ACA", ["crop_diversity", "savings"], ground_aca_from_state),
])
```

---

## Minimum Viable Universal Roadmap

### Must Change (before claiming universality)

| Priority | Item | Effort | Type |
|----------|------|--------|------|
| P0 | **HallucinationDetector protocol** -- extract flood.py rules behind interface | 1 day | LLM-engineering |
| P0 | **TraceSchema configuration** -- replace hardcoded extraction paths | 2 days | LLM-engineering |
| P1 | **CGR grounding rule registry** -- make ground_tp/cp pluggable | 1 day | Domain-engineering |
| P1 | **Benchmark registry for L2** -- already half-done (BenchmarkRegistry exists), just decouple EMPIRICAL_BENCHMARKS from flood.py | 1 day | Domain-engineering |
| P1 | **Null model accepts domain-specific action pools** -- currently hardcodes _OWNER_ACTIONS/_RENTER_ACTIONS | 0.5 day | Domain-engineering |
| P2 | **Trace schema docs** -- JSON Schema or Pydantic model for expected trace format | 1 day | Documentation |

### Can Wait (nice-to-have, not blocking universality)

| Priority | Item | Effort | Type |
|----------|------|--------|------|
| P3 | Temporal validation (epidemic curves, trajectories) | 3-5 days | Domain-engineering |
| P3 | Paradigm B continuous-construct support | 2-3 days | LLM-engineering |
| P3 | Sycophancy / PIS probes | 2 days (experiment cost) | LLM-engineering |
| P3 | Vectorized trace processing | 2 days | Performance |
| P4 | Ensemble aggregation across seeds | 1 day | Statistical |
| P4 | Wasserstein distance for distribution comparison | 1 day | Statistical |

### What is NOT an LLM-engineering problem

Items 1 (temporal validation), 5 (null model skew), and 7 (ensemble aggregation) from the Wave 1 consensus are pure statistics/domain-modeling problems, not LLM-engineering problems. They should be addressed by domain experts, not by changing the LLM integration layer.

Items 2 (CGR pluggability), 3 (hallucination detection), and 4 (Paradigm B) are hybrid -- they require both LLM-engineering insight (how do different LLMs represent constructs?) and domain-engineering work (what are the valid construct spaces?).

---

## Would I Adopt This for My Own LLM-ABM Research?

**Conditionally yes**, under two conditions:

1. **After P0 items are implemented** (HallucinationDetector protocol + TraceSchema). Without these, I would need to fork l1_micro.py and trace_reader.py for any non-flood domain, which defeats the purpose of a shared validation module.

2. **With explicit PIS or ablation testing** for any paper claiming "theory-aligned LLM behavior." CACR alone is insufficient evidence for a peer-reviewed publication claiming LLM agents genuinely reason according to PMT/TPB/etc. The CGR metric helps, but it measures label accuracy, not reasoning quality. A reviewer familiar with LLM evaluation will flag this distinction.

The BehavioralTheory protocol, the L0-L1-L2-L3 tiered structure, and the CGR anti-circularity mechanism are genuine contributions. The metric definitions (CACR, EBE, EPI) are well-motivated and would pass methodological review. The implementation just needs the extraction layer to be decoupled from the flood-specific trace format, and the hallucination detection to be made pluggable.

If these changes were made, this would be one of the most rigorous validation frameworks for LLM-ABM that I am aware of -- most published work relies on subjective face validity or simple output-distribution comparisons. The construct-action coherence approach, combined with grounding and bootstrap CIs, sets a higher bar.

---

## Appendix: Specific Code Issues Noted

1. **`_normalize_action` linear scan** (trace_reader.py:59-73): The `for standard, variants in mappings.items()` loop is O(n*m) where n is number of standard actions and m is average variants. For a hot path called per-trace, this should be a flat dict lookup:
   ```python
   _ACTION_MAP = {}
   for standard, variants in mappings.items():
       for v in variants:
           _ACTION_MAP[v] = standard
   # Then: return _ACTION_MAP.get(action, action)
   ```

2. **`compute_l1_metrics` print statement** (l1_micro.py:123): `print(f"  WARNING: ...")` should use `logging.warning()` for production use, or at minimum be suppressible. In a 1000-seed ensemble, this will produce 1000 identical warnings.

3. **Agent type inference by ID heuristic** (l1_micro.py:219-228): `int(agent_id.replace("H", "")) > 200 -> renter` is extremely fragile. If a different domain uses agent IDs like "A001", this crashes. The heuristic should be clearly documented as flood-specific and guarded with a domain check.

4. **`_cohens_kappa` does not handle degenerate cases well** (cgr.py:106-125): When all observations fall in one cell, kappa is undefined (0/0). The current handling returns 1.0 when p_o = p_e = 1.0, which is technically correct but should be flagged as "trivial agreement" in the output.

5. **Null model flood probability** (null_model.py:62-64): `0.20` and `0.05` are hardcoded flood probabilities. For an epidemic null model, these would be infection probabilities. This should be a parameter, not a constant.

---

*Review conducted by Dr. Kevin Liu, LLM Engineering Specialist. Based on source code review of the validation/ package (14 Python files, ~1,100 LOC) within the WAGF governed_broker_framework repository.*
