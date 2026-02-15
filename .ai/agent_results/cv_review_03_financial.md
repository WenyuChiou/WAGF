# Expert Review: Dr. Priya Sharma -- Financial Behavior ABM

**Reviewer**: Dr. Priya Sharma, Behavioral Finance, LLM-based Financial Agent Models
**Domain**: 1000 retail investors, portfolio decisions (buy/sell/hold/rebalance), 5-year horizon, Prospect Theory agents
**Date**: 2026-02-14
**Files Reviewed**: 9 files across `validation/theories/`, `validation/metrics/`, `validation/engine.py`, and `broker/validators/calibration/README.md`

---

## Overall Score: 3.3/5.0

---

## Dimension Scores

| # | Dimension | Score | Notes |
|---|-----------|-------|-------|
| D1 | Theory Protocol Extensibility | 2.5 | Paradigm B acknowledged in docstring but not operationalized; protocol forces discrete construct levels |
| D2 | Construct-Action Coherence (CACR) | 2.0 | Fundamentally assumes Paradigm A lookup tables; Prospect Theory cannot express continuous value functions this way |
| D3 | Construct Grounding (CGR) | 3.0 | Rule-based grounding is sound for ordinal constructs; no pathway for continuous grounding (gain/loss magnitude, reference point) |
| D4 | L2 Macro Benchmarks | 4.0 | Weighted EPI with registered benchmark functions is well-designed and domain-agnostic in principle |
| D5 | Null Model Design | 3.5 | Uniform random baseline is appropriate for discrete actions; needs adaptation for continuous portfolio allocations |
| D6 | Bootstrap / Statistical Rigor | 4.5 | Generic, well-implemented; works for any metric that takes a list of traces |
| D7 | Engine Pipeline Orchestration | 4.0 | Clean load-compute-report pipeline; theory injection via Protocol is the right design |
| D8 | Documentation & Onboarding | 3.5 | README is thorough for the flood domain; Paradigm B integration path is undocumented |
| D9 | Scalability to My Domain (1000 agents x 5yr x 252 trading days) | 2.5 | Trace-by-trace iteration will be slow at ~1.26M decisions; no batched/vectorized pathway |
| D10 | Adoption Readiness for Finance | 2.5 | Would require significant protocol extensions before I could use it |

---

## Top 3 Strengths

### S1. Theory Protocol Design is Conceptually Right (base.py)
The `BehavioralTheory` Protocol with `get_coherent_actions`, `extract_constructs`, and `is_sensible_action` is the correct abstraction boundary. The fact that it is a runtime-checkable Protocol (not an ABC) means I can implement it in my own codebase without inheriting from WAGF classes. The docstring explicitly acknowledges Paradigm B (frame-conditional theories), which tells me the designers know the limitation exists. The `is_sensible_action` fallback is a pragmatic escape hatch that could absorb some of the fuzziness Prospect Theory requires.

### S2. BenchmarkRegistry + Weighted EPI is Domain-Portable (flood.py, l2_macro.py)
The `@_registry.register("benchmark_name")` decorator pattern with `_compute_benchmark` dispatch is clean engineering. I could define financial benchmarks (equity premium puzzle range 4-8%, home bias 60-80%, disposition effect 1.2-2.0x) using the same pattern. The weighted EPI computation correctly handles missing benchmarks (`if value is not None`) and weights by importance. The `mg_adaptation_gap` benchmark with weight=2.0 shows that researchers can encode domain priors about which benchmarks matter most. This maps directly to my need to weight the disposition effect benchmark higher than aggregate return benchmarks.

### S3. Bootstrap CI is Fully Generic (bootstrap.py)
The `bootstrap_ci` function with `extractor` lambda and `**kwargs` pass-through is textbook good design. I can immediately use this for confidence intervals on any financial metric (Sharpe ratio, turnover rate, loss aversion coefficient). No modifications needed. The seed-based reproducibility is essential for my SEC-filing-calibrated experiments where reviewers will demand replicability.

---

## Top 3 Gaps

### G1. Paradigm B is Acknowledged but Not Implemented -- This is My Showstopper

The `base.py` docstring says "Paradigm B (Frame-Conditional): Prospect Theory, Nudge -> tendency matching" but the actual Protocol signature is:

```python
def get_coherent_actions(
    self, construct_levels: Dict[str, str], agent_type: str
) -> List[str]:
```

This signature assumes:
- **Discrete construct levels** (`Dict[str, str]` like `{"TP": "VH"}`). Prospect Theory operates on continuous value functions: `v(x) = x^alpha` for gains, `-lambda * (-x)^beta` for losses, with typical `alpha=0.88, beta=0.88, lambda=2.25` (Tversky & Kahneman 1992). There is no natural discretization. Do I quantize the gain/loss magnitude into VL/L/M/H/VH? That loses the nonlinearity that IS the theory.
- **Deterministic coherent action lists**. Prospect Theory predicts probabilistic tendencies: risk-seeking in losses (preferring a gamble over a certain loss), risk-averse in gains (preferring a sure gain over a gamble). The "coherent" action for a loss-frame agent is not a list -- it is a probability distribution over actions that shifts toward risk-seeking options.
- **Frame as a construct dimension**. I could encode `{"frame": "LOSS", "magnitude": "H"}` but this is a lossy approximation. The reference point (which determines gain vs. loss frame) is agent-specific and time-varying -- it depends on the agent's purchase price, recent portfolio peak, or aspiration level.

**What I need**: `get_coherent_action_distribution(continuous_state: Dict[str, float], agent_type: str) -> Dict[str, float]` returning probability weights over actions, with coherence measured as KL-divergence from the theoretical distribution rather than set membership.

### G2. CGR Cannot Ground Continuous Constructs

The CGR module (`cgr.py`) is deeply PMT-shaped. `ground_tp_from_state` maps discrete flood indicators to ordinal TP levels. For Prospect Theory, the analogous grounding would be:

- **Reference point grounding**: From CRSP return data, I know the agent's cost basis. The "grounded" reference point is the purchase price. The LLM's implicit reference point (revealed by whether it frames a position as a gain or loss) should align.
- **Value function curvature**: Given a $10K loss, PT predicts `v(-10K) = -2.25 * 10000^0.88`. The LLM's "distress level" should correlate with this nonlinear function, not with linear loss magnitude.
- **Probability weighting**: PT predicts overweighting of small probabilities (buying lottery-like stocks) and underweighting of moderate probabilities. This is a continuous function `w(p) = p^gamma / (p^gamma + (1-p)^gamma)^(1/gamma)`.

None of these can be expressed as VL/L/M/H/VH ordinal levels with Cohen's kappa. I would need:
- Spearman/Pearson correlation between grounded continuous values and LLM-expressed values
- Nonlinear regression to estimate whether the LLM's implicit value function matches PT parameters
- Possibly Wasserstein distance between the grounded probability weighting function and the LLM's revealed weighting

The existing CGR framework would need a parallel `ContinuousCGR` pathway.

### G3. Null Model Assumes Uniform Random Over Discrete Actions

`null_model.py` generates uniform random actions from `_OWNER_ACTIONS` / `_RENTER_ACTIONS`. For financial agents:

- The action space is not categorical. "Rebalance to 60/40 stocks/bonds" vs. "rebalance to 70/30" are not two discrete actions -- they form a continuous allocation simplex.
- A meaningful null model for financial agents would be a random walk portfolio (each period, random allocation) or a "zero-intelligence trader" (Gode & Sunder 1993) that submits random limit orders within budget constraints.
- The null model EPI distribution needs to reflect what random financial agents would produce in terms of aggregate metrics (Sharpe ratio, turnover, disposition effect). Uniform random over {buy, sell, hold, rebalance} is not economically meaningful because "buy what?" and "sell how much?" matter enormously.

This is not a bug in the WAGF code -- it is correctly implemented for discrete-action domains. But it reveals that the framework's implicit assumption is a small, enumerable action space.

---

## Specific Recommendations

### R1. Add a `ContinuousBehavioralTheory` Protocol (Priority: HIGH)

```python
@runtime_checkable
class ContinuousBehavioralTheory(Protocol):
    """Paradigm B: Frame-conditional theories with continuous state."""

    @property
    def name(self) -> str: ...

    @property
    def state_dimensions(self) -> List[str]:
        """Continuous state dimensions (e.g., ['gain_loss_magnitude', 'probability', 'reference_point'])."""
        ...

    def get_coherent_distribution(
        self, state: Dict[str, float], agent_type: str
    ) -> Dict[str, float]:
        """Return probability distribution over actions given continuous state.
        E.g., {"hold": 0.1, "sell": 0.7, "buy": 0.2} for a loss-frame agent."""
        ...

    def extract_state(self, trace: Dict) -> Dict[str, float]:
        """Extract continuous state from decision trace."""
        ...

    def coherence_score(
        self, state: Dict[str, float], action: str, agent_type: str
    ) -> float:
        """Continuous coherence score [0,1] instead of binary coherent/not."""
        ...
```

Then `compute_l1_metrics` would branch: if `isinstance(theory, ContinuousBehavioralTheory)`, compute mean coherence score instead of binary CACR. This preserves backward compatibility while opening Paradigm B.

### R2. Add KL-Divergence-Based CACR for Continuous Theories (Priority: HIGH)

Instead of binary "action in coherent_actions", compute:

```python
def compute_continuous_cacr(traces, theory: ContinuousBehavioralTheory, agent_type: str) -> float:
    """CACR analog: mean coherence score across traces."""
    scores = []
    for trace in traces:
        state = theory.extract_state(trace)
        action = _extract_action(trace)
        scores.append(theory.coherence_score(state, action, agent_type))
    return np.mean(scores)
```

The threshold would change from binary (>=0.75) to continuous (mean coherence >=0.60 or similar). This preserves the spirit of CACR while accommodating probabilistic theories.

### R3. Vectorize Trace Processing for Scale (Priority: MEDIUM)

My domain has 1000 agents x 252 trading days x 5 years = 1,260,000 decisions. The current `for trace in traces` loop in `compute_l1_metrics` will be unacceptably slow. Recommendation:

```python
# Vectorized path (optional, activated when traces are DataFrames)
def compute_l1_metrics_vectorized(
    trace_df: pd.DataFrame,
    theory: "BehavioralTheory",
    agent_type: str,
) -> L1Metrics:
    """Vectorized L1 computation for large trace datasets."""
    # Batch extract constructs
    # Vectorized coherence checking via merge with rules table
    # np.isin for action matching
    ...
```

### R4. Extend Null Model to Support Continuous Action Spaces (Priority: MEDIUM)

Add a `NullModelConfig` that allows custom action generation:

```python
@dataclass
class NullModelConfig:
    action_generator: Callable[[np.random.Generator, str], Any]  # (rng, agent_type) -> action
    trace_builder: Callable[[Any, Dict], Dict]  # (action, agent_meta) -> trace dict
```

For finance: `action_generator` could sample from a Dirichlet distribution over asset classes. For discrete domains, the current uniform sampling is a special case.

### R5. Add L2 Benchmarks for Time-Series Properties (Priority: LOW)

The current benchmarks are cross-sectional (rates at simulation end). Financial ABMs need temporal benchmarks:
- Autocorrelation of returns (should match CRSP: near-zero for daily, slightly negative for weekly)
- Volatility clustering (GARCH effects from behavioral herding)
- Volume-volatility correlation (positive, ~0.3-0.5)

The `BenchmarkRegistry` decorator pattern supports this -- I would just register new functions. But the `_compute_benchmark` dispatch assumes `(df, traces, ins_col, elev_col)` signature. A more generic signature like `(df, traces, **kwargs)` would be cleaner.

### R6. Document the Paradigm B Integration Path (Priority: LOW)

The README mentions `framework="financial"` as a valid option for `CVRunner` but provides no example of what a financial framework implementation looks like. Adding a `ProspectTheoryExample` to `examples.py` (even if simplified) would dramatically lower the adoption barrier.

---

## Detailed Analysis: Can Prospect Theory Fit the BehavioralTheory Protocol?

**Short answer**: Only with severe lossy approximation.

I could implement a `ProspectTheory` class that satisfies the Protocol:

```python
class ProspectTheoryApprox:
    @property
    def dimensions(self) -> List[str]:
        return ["frame", "magnitude"]  # LOSS/GAIN x VL/L/M/H/VH

    def get_coherent_actions(self, construct_levels, agent_type):
        frame = construct_levels.get("frame", "GAIN")
        mag = construct_levels.get("magnitude", "M")
        if frame == "LOSS" and mag in ("H", "VH"):
            return ["hold", "double_down"]  # risk-seeking in large losses
        elif frame == "GAIN" and mag in ("H", "VH"):
            return ["sell", "hedge"]  # risk-averse in large gains
        else:
            return ["hold", "rebalance"]
```

But this collapses the continuous nonlinear value function into a 2x5 lookup table, destroying:
- The reference-dependence mechanism (what counts as gain vs. loss depends on agent-specific reference point)
- The diminishing sensitivity curve (the difference between $1K and $2K loss matters more than between $101K and $102K loss)
- The probability weighting function (overweighting tail events)
- The interaction between value and weighting (which produces the four-fold pattern: risk-seeking for low-probability gains AND high-probability losses)

This is like implementing fluid dynamics as a lookup table of "flow: HIGH/LOW" x "viscosity: HIGH/LOW" -> "turbulent/laminar". Technically possible, scientifically misleading.

---

## Detailed Analysis: What Null Model for Financial Agents?

The correct null model hierarchy for financial ABMs:

1. **Tier 0**: Random walk portfolio (Malkiel 1973). Each period, each agent randomly allocates across assets. This is the analog of the current uniform random action model.

2. **Tier 1**: Zero-intelligence traders with budget constraints (Gode & Sunder 1993). Agents submit random limit orders but cannot spend more than their wealth. This already produces some realistic market properties (price convergence) from pure mechanism design.

3. **Tier 2**: Noise traders (DeLong, Shleifer, Summers, Vishny 1990). Agents follow random sentiment shocks around fundamental value. This produces excess volatility and mean reversion, testing whether the LLM agents add value beyond sentiment noise.

The WAGF null model (Tier 0 equivalent) would set a very low bar for financial ABMs because even random portfolios can hit some aggregate benchmarks by chance (e.g., market-cap weighted random allocation approximates an index fund). I would want Tier 2 as the null to demonstrate that LLM Prospect Theory agents produce the specific behavioral signatures (disposition effect, loss aversion asymmetry) that noise traders do not.

---

## Detailed Analysis: Using CRSP/SEC as L2 Benchmarks

I have rich empirical data:

| Benchmark | Range | Source | WAGF Mapping |
|-----------|-------|--------|--------------|
| Disposition Effect Ratio | 1.2-2.0 | Odean (1998), Barber & Odean (2000) | `@_registry.register("disposition_effect")` |
| Equity Premium | 4-8% annualized | Mehra & Prescott (1985) | `@_registry.register("equity_premium")` |
| Annual Portfolio Turnover | 50-100% retail | Barber & Odean (2000) | `@_registry.register("turnover_rate")` |
| Home Bias | 60-80% domestic | French & Poterba (1991) | `@_registry.register("home_bias")` |
| Loss Aversion Lambda | 1.5-2.5 | Tversky & Kahneman (1992) | Would need custom metric |
| January Effect | 1-3% excess return | Rozeff & Kinney (1976) | Temporal benchmark (new category) |

The `BenchmarkRegistry` + `_compute_benchmark` pattern handles the first four well. The loss aversion lambda and January effect would require extending the benchmark computation to accept time-series traces and estimate behavioral parameters -- this goes beyond rate computation into parameter estimation, which is a fundamentally different statistical task.

---

## Would You Adopt?

**Conditionally yes, with significant investment.**

I would adopt the following components immediately:
- `bootstrap_ci` -- drop-in usable for any metric
- `BenchmarkRegistry` + weighted EPI -- after registering financial benchmarks
- `null_model` pattern -- after implementing Tier 2 null for finance
- Validation engine pipeline structure -- load/compute/report is clean

I would NOT adopt until resolved:
- `BehavioralTheory` Protocol must support continuous state (R1)
- CACR must support probabilistic coherence (R2)
- CGR must support continuous construct grounding (G2)
- Trace processing must be vectorizable for 1.26M decisions (R3)

**Estimated integration effort**: 3-4 weeks for a postdoc to implement the continuous extensions, register financial benchmarks, and build a Prospect Theory adapter. Without the extensions, I would have to build a parallel validation stack from scratch, which defeats the purpose of adopting a shared framework.

**Bottom line**: The architecture is sound and the engineering quality is high. The fundamental limitation is that it was built for Paradigm A (construct-action mapping) theories and Paradigm B (frame-conditional) support is acknowledged but not yet realized. For my financial ABM work, this is the difference between a usable framework and an inspirational reference implementation.

---

*Review completed 2026-02-14. Dr. Priya Sharma, Behavioral Finance Research Group.*
