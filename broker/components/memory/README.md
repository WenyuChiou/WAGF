# Memory Write Policy — Guide for New MA Experiments

**Audience:** You are writing a new multi-agent experiment on this broker framework and you want your lifecycle hooks to inherit safe memory-write defaults without accidentally reintroducing the rationalization ratchet discovered in Paper 3.

**TL;DR** (30 seconds): wrap your memory engine with `PolicyFilteredMemoryEngine`, register a category mapping dict for your domain, and tag each `add_memory` call with a `content_type` in metadata. The default policy (`CLEAN_POLICY`) blocks three risky content types that cause self-reinforcing construct labels. Existing experiments that omit the policy block reproduce legacy behavior exactly.

For the full architectural rationale and the Gemma 4 ratchet evidence, see `.ai/broker_memory_governance_architecture.md` and the `gemma4_pa_saturation` project memory.

## What problem does this solve?

Gemma 4 e4b (and likely any future confident LLM) exhibits a "rationalization ratchet" when its own first-person reasoning is stored in memory and retrieved in subsequent decision cycles. Renters in the Paper 3 MA flood experiment drifted from a calibrated 22% H+VH Place Attachment in Year 1 to a saturated 87% by Year 13 — 67% of renters showed this drift. The mechanism: the LLM invoked PA=H as a discursive justification for sustained inaction ("Relocation is too drastic due to high place attachment"), that reasoning was stored via `add_memory(...)`, and in the next year the LLM read its own prior confabulation as if it were external evidence and reinforced the label.

Any new MA experiment where the lifecycle writes first-person LLM output back into memory can trigger this. The broker-level memory governance facility prevents it by **filtering at the engine level** so you don't have to remember a per-call gate at every `add_memory` site.

## The 30-second mental model

```
  Your lifecycle hook                  Broker proxy
       |                                    |
       |  add_memory(                       |
       |    agent_id,                       |
       |    "I decided X because...",       |
       |    metadata={                      |
       |      category: "decision_reasoning",
       |      content_type: AGENT_SELF_REPORT,
       |    })                              |
       |                                    |
       +---------------------------------->  |  classify() says AGENT_SELF_REPORT
                                             |  policy says allow_agent_self_report = False
                                             |  → DROP. increment dropped_counts.
                                             |
                                             |  For content_type == EXTERNAL_EVENT:
                                             |  → FORWARD to inner engine.
```

The proxy is transparent to everything else (retrieval, clearing, custom methods) via `__getattr__` forwarding. Only writes classified as disallowed content types are silently dropped.

## Quickstart: 4 steps to safe defaults

### 1. Create a domain category mapping

`examples/multi_agent/YOUR_EXPERIMENT/memory/content_type_mapping.py`:

```python
from broker.components.memory.content_types import MemoryContentType

MY_DOMAIN_CATEGORY_MAP = {
    # --- Safe categories (default allowed) ---
    "drought_event":       MemoryContentType.EXTERNAL_EVENT,
    "water_delivery":      MemoryContentType.EXTERNAL_EVENT,
    "allocation_cut":      MemoryContentType.INSTITUTIONAL_STATE,
    "irrigation_history":  MemoryContentType.INITIAL_FACTUAL,
    "neighbor_usage":      MemoryContentType.SOCIAL_OBSERVATION,

    # --- Risky categories (your ratchet sources) ---
    "decision_reasoning":   MemoryContentType.AGENT_SELF_REPORT,
    "water_attachment":     MemoryContentType.INITIAL_NARRATIVE,  # if you seed first-person narratives
}
```

Only list the category strings your writers actually use. The classifier also has default rules for common names like `flood_event`, `policy_decision`, `social_observation` — your domain mapping is added on top, overriding defaults when you want different behavior.

### 2. Wire the policy into your runner

```python
from broker.components.memory import (
    PolicyFilteredMemoryEngine, load_initial_memories_from_json
)
from broker.config.memory_policy import load_from_config
from examples.multi_agent.YOUR_EXPERIMENT.memory.content_type_mapping import MY_DOMAIN_CATEGORY_MAP

# 1. Construct your base engine as before
memory_engine = WindowMemoryEngine(window_size=5)  # or whatever

# 2. Load the policy from your config yaml (or use CLEAN_POLICY directly)
memory_policy = load_from_config(agent_config.get("global_config", {}))

# 3. Wrap it
memory_engine = PolicyFilteredMemoryEngine(
    memory_engine, memory_policy,
    domain_mapping=MY_DOMAIN_CATEGORY_MAP,
)

# 4. (Optional) use the broker initial-memory loader
if initial_memories_path.exists():
    report = load_initial_memories_from_json(
        memory_engine, initial_memories_path,
        agent_id_filter=set(all_agents.keys()),
        domain_mapping=MY_DOMAIN_CATEGORY_MAP,
    )
    print(f"[INFO] {report.summary()}")

# 5. Pass the wrapped engine to your lifecycle hook
my_hooks = MyLifecycleHooks(memory_engine=memory_engine, ...)
```

### 3. Tag every `add_memory` call in your lifecycle hook

```python
from broker.components.memory.content_types import MemoryContentType

# In your post_step / post_year / pre_year methods:
memory_engine.add_memory(
    agent.id,
    f"Year {year}: water allocation cut to {allocation} acre-feet",
    metadata={
        "source": "personal",
        "category": "allocation_cut",
        "content_type": MemoryContentType.INSTITUTIONAL_STATE.value,
    },
)
```

The `content_type` key is the primary signal. The `category` key is helpful for debugging and aids the classifier when callers forget the explicit tag.

### 4. Add the policy block to your experiment yaml

```yaml
global_config:
  memory_write_policy:
    # Omit this entire block for legacy-reproduction experiments.
    # Present with empty dict → CLEAN_POLICY defaults (safe).
    # Set individual fields to override:
    allow_agent_self_report: false      # default: block ratchet
    allow_initial_narrative: false      # default: block Y1 priming
    # All other fields inherit CLEAN defaults.
```

Done. Your new experiment now inherits safe defaults. The ratchet cannot form because the proxy silently drops any write classified as `AGENT_SELF_REPORT` regardless of which code path writes it — even a new contributor adding a sneaky `memory_engine.add_memory(...)` somewhere will not bypass the filter.

## The content-type taxonomy

The canonical enum is `broker.components.memory.content_types.MemoryContentType`:

| Value | Default CLEAN allow? | Typical content |
|---|---|---|
| `EXTERNAL_EVENT` | allowed | Physical events (flood hit, damage recorded, no-flood year) |
| `AGENT_ACTION` | allowed | Record of what the agent did (`"Year 5: I chose buy_insurance"`) |
| `SOCIAL_OBSERVATION` | allowed | Aggregated peer behavior (`"3 of 4 neighbors elevated"`) |
| `INSTITUTIONAL_STATE` | allowed | State changes by institutional agents (subsidy rate, CRS discount) |
| `INSTITUTIONAL_REFLECTION` | allowed | Gov/insurance reflection summary (non-household agents) |
| `INITIAL_FACTUAL` | allowed | Y0 seed memories with verifiable facts only |
| `AGENT_SELF_REPORT` | **BLOCKED** | LLM's first-person psychological narrative — the ratchet source |
| `AGENT_REFLECTION_QUOTE` | **BLOCKED** | Reflection that embeds a retrieved memory (memory-of-memory) |
| `INITIAL_NARRATIVE` | **BLOCKED** | Y0 seed with first-person PMT narrative |

Three types are blocked under CLEAN_POLICY; six are allowed. `LEGACY_POLICY` allows all nine (used only when reproducing pre-2026-04-11 experiments).

## What happens if my categories aren't in the mapping?

The classifier has a **default rules** dict that recognizes common category names like `flood_event`, `policy_decision`, `social_observation`, etc. If none of those match and you didn't register a domain mapping, the classifier falls back to `EXTERNAL_EVENT` (safe — allowed under CLEAN_POLICY).

This **fails open** on purpose. A category the classifier cannot identify is more likely to be a legitimate event that you forgot to list than a risky ratchet source. The cost of failing closed would be legitimate memories silently disappearing and breaking your experiment invisibly. The cost of failing open is that some ratchet sources might slip through — recoverable via audit, because you can always inspect the classifier's decision per-call (see `stats()` below).

**Recommendation**: always register a domain mapping, even if it only covers your ratchet-source categories. You don't need to enumerate every safe category — the default rules handle the common ones.

## Debugging: "where did my memories go?"

If an agent seems to be missing expected memories during a run, the first thing to check is the reproducibility manifest:

```bash
python -c "
import json
m = json.load(open('results/YOUR_OUTPUT/reproducibility_manifest.json'))
print(json.dumps(m.get('memory_write_policy', 'MISSING'), indent=2))
"
```

The manifest (when a policy-wrapped engine is in use) includes a `memory_write_policy` section with the exact policy in effect and per-content-type drop counts. Example output:

```json
{
  "policy": {
    "allow_external_event": true,
    "allow_agent_self_report": false,
    "allow_initial_narrative": false,
    ...
  },
  "dropped_counts": {
    "agent_self_report": 5162,
    "initial_narrative": 800
  },
  "allowed_counts": {
    "external_event": 2600,
    "social_observation": 2600,
    "institutional_state": 26
  },
  "domain_mapping_size": 16
}
```

Interpret:
- `dropped_counts.agent_self_report = 5162`: the proxy silently dropped 5162 LLM-reasoning writes across the whole run. These are the ratchet blocks working as intended. For a 400-agent × 13-year run this is roughly what you'd expect (one per household decision that generated reasoning text).
- `dropped_counts.initial_narrative = 800`: 800 Y0 seed memories of first-person PMT narrative were dropped during initial loading (400 agents × 2 categories).
- `allowed_counts.external_event = 2600`: factual event memories all made it through (400 agents × ~6.5 events per year on average).

If you see `dropped_counts.external_event > 0`, something is wrong — legitimate writes are being blocked, which should never happen under any sane policy configuration. File a bug.

During a run, the policy and initial load report are also logged once at startup:

```
[INFO] Memory write policy: {'allow_external_event': True, 'allow_agent_self_report': False, ...}
[INFO] Loaded 2400 initial memories across 400 agents (dropped 800 by policy: initial_narrative=800)
```

## FAQ

**Q: My experiment doesn't use `ExperimentBuilder`. Can I still use the policy filter?**

Yes. The filter is a standalone proxy class. Just construct it directly:

```python
from broker.components.memory.policy_filter import PolicyFilteredMemoryEngine
from broker.config.memory_policy import CLEAN_POLICY

memory_engine = PolicyFilteredMemoryEngine(
    my_raw_engine, CLEAN_POLICY,
    domain_mapping=MY_DOMAIN_CATEGORY_MAP,
)
```

Hand `memory_engine` to your lifecycle hook instead of the raw engine. Everything else is the same.

**Q: My lifecycle hook inherits from an existing base class that already writes memories. Do I need to change the base class?**

No. The filter is applied at the engine level, not the hook level. As long as your base class uses the memory engine you pass into it, writes go through the filter regardless of where they originate.

**Q: Can I register multiple domain mappings?**

Only one per proxy instance. If you need different policies for different agent types in the same experiment, construct multiple proxy instances wrapping the same inner engine — but this is an unusual pattern. Most experiments use a single policy for the whole simulation.

**Q: I'm running an ablation experiment — how do I reproduce the buggy legacy behavior intentionally?**

Omit the `memory_write_policy` block from your config yaml entirely. `load_from_config` returns `LEGACY_POLICY` when the block is absent, which allows all nine content types through. The reproducibility manifest will not include a `memory_write_policy` section (because the engine is not wrapped), making it easy to tell apart from clean-policy runs.

**Q: I added a new category to my domain mapping mid-project and old runs are now reporting different numbers.**

They shouldn't be — the old runs' reproducibility manifest captured the policy dict and the domain_mapping size at run time. If you re-run an old config with new code, the policy itself is unchanged but the classifier may now produce different results for newly-mapped categories. Best practice: version your domain mapping dict in git and never retroactively change an old entry. Add new categories at the bottom with a comment noting when they were added.

**Q: How do I test my domain mapping?**

Write a test like this:

```python
from broker.components.memory.content_types import MemoryContentType
from broker.components.memory.policy_filter import PolicyFilteredMemoryEngine
from broker.config.memory_policy import CLEAN_POLICY
from examples.multi_agent.YOUR_EXPERIMENT.memory.content_type_mapping import MY_DOMAIN_CATEGORY_MAP


class MockEngine:
    def __init__(self): self.calls = []
    def add_memory(self, aid, content, metadata=None):
        self.calls.append((aid, content, metadata))


def test_known_ratchet_source_blocked():
    inner = MockEngine()
    proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=MY_DOMAIN_CATEGORY_MAP)
    proxy.add_memory("a1", "text", {"category": "decision_reasoning"})
    assert len(inner.calls) == 0
    assert proxy.dropped_counts["agent_self_report"] == 1


def test_factual_event_allowed():
    inner = MockEngine()
    proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=MY_DOMAIN_CATEGORY_MAP)
    proxy.add_memory("a1", "drought hit", {"category": "drought_event"})
    assert len(inner.calls) == 1
```

See `examples/multi_agent/flood/paper3/tests/test_flood_content_type_mapping.py` for a complete example covering every flood category.

**Q: The policy filter is silently dropping writes. Can I get an exception instead for debugging?**

Not currently by design — silent drops are the safe default for production runs (an exception in `add_memory` would crash a run and lose data). For debugging, inspect `proxy.dropped_counts` and `proxy.allowed_counts` after each year, or add a custom wrapper around `PolicyFilteredMemoryEngine` that raises on drop.

## Single-agent experiments

Single-agent experiments (`examples/single_agent/`) are **not affected** by this system. The single-agent flood runner has its own `DecisionFilteredMemoryEngine` proxy pattern (`examples/single_agent/run_flood.py:211-226`) and its own memory write conventions. The broker governance layer is opt-in — any runner that doesn't call `PolicyFilteredMemoryEngine(...)` gets the raw engine it always did.

Paper 1b (Nature Water) single-agent flood results and single-agent irrigation results are preserved byte-for-byte by this refactor. The broker governance rollout never touched any file under `examples/single_agent/`.
