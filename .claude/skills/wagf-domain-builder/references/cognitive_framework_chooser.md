# Cognitive Framework Chooser

Use this during S0 Q5. Do not pick the framework silently; surface the options and ask the user which one matches their theory.

The framework controls three things: appraisal fields in `agent_types.yaml`, thinking rules under `thinking_rules:` (NOT `rules:` — Phase 6N-C 2026-05-23 finding: the broker's `get_thinking_rules()` loader recognises only the keys `thinking_rules` or `coherence_rules`; a `rules:` block is silently dead config), and whether S4 uses `--framework custom`.

## PMT - Protection Motivation Theory

Status: pre-registered by the water domain.

Constructs: `threat_appraisal`, `coping_appraisal`.

Best for: hazard-protective actions where the agent weighs danger against ability to respond. Flood, fire, heat, public-health protection, and disaster preparedness usually fit PMT.

Examples in WAGF: `examples/governed_flood/` and the multi-agent flood work use PMT-style flood adaptation reasoning.

Use PMT when the question sounds like: "Does higher perceived threat make agents choose protective action, and does low coping ability explain inaction?"

Scaffold choice: use default `--framework pmt`; no `cognition/` package is needed.

## Utility Framework

Status: pre-registered.

Constructs: `cost_appraisal`, `benefit_appraisal`.

Best for: economic-actor decisions where the user cares about tradeoffs, budget, expected benefit, or welfare more than psychological threat.

Examples in WAGF: water-domain government and policy decisions use utility-style appraisals.

Use Utility when the question sounds like: "Does the agent choose the option with better expected payoff or public benefit under constraints?"

Scaffold choice: use a PMT scaffold only if the first smoke is exploratory, then edit YAML to the registered utility framework. For a clean first build, use `--framework custom` if the scaffold cannot emit the exact utility constructs you need.

## Financial Framework

Status: pre-registered.

Constructs: one compact utility-like financial appraisal, usually expressed as solvency, risk appetite, or affordability.

Best for: the simplest financial decision-maker, especially when the first domain only needs "can afford / cannot afford" behavior.

Examples in WAGF: water-domain insurance and finance-facing agents.

Use Financial when the question sounds like: "Does financial risk or solvency govern the choice?"

Scaffold choice: start with the default scaffold if the prompt can stay simple; otherwise use `--framework custom` and register the exact financial construct names.

## HBM - Health Belief Model

Status: registered in `examples/vaccination_demo/` as the non-water reference. A new domain still needs custom registration in its own package unless it directly imports and reuses that registration.

Constructs: `susceptibility`, `severity`, `benefits`, `barriers`, `self_efficacy`, `cues`.

Best for: health behavior, public health, vaccination, screening, treatment uptake, and preventive care.

Examples in WAGF: `examples/vaccination_demo/` uses HBM for individual vaccination decisions.

Use HBM when the question sounds like: "Does perceived susceptibility, self-efficacy, or barriers explain adoption of a health action?"

Scaffold choice: use `--framework custom`, then fill the generated `cognition/` package with `register_framework_metadata()` for the HBM constructs actually exposed in YAML.

## TPB - Theory of Planned Behavior

Status: not registered.

Constructs: `attitude`, `subjective_norms`, `perceived_behavioral_control`, `intention`.

Best for: planned health or social behavior where norms and intention matter, such as exercise, recycling, voting, or safety compliance.

Examples in WAGF: none yet.

Use TPB when the question sounds like: "Do attitudes, social norms, and perceived control explain intention and action?"

Scaffold choice: use `--framework custom`; the user must register TPB before `ThinkingValidator` can resolve it.

## Custom

Status: available through scaffolded boilerplate, but the user owns the theory.

Constructs: whatever the domain theory requires.

Best for: domains that do not fit hazard protection, health behavior, economic utility, or finance. Also use it for a known theory that WAGF has not registered yet.

Examples: energy justice, trust in institutions, technology acceptance, or domain-specific risk perception.

Scaffold choice:

```bash
python -m broker.tools.scaffold_domain <domain> \
  --output examples/<domain>_demo \
  --skills "<skills>" \
  --framework custom
```

The scaffold creates `cognition/` boilerplate. Replace the generated construct list with the theory's real constructs before S6.

## Decision Tree

1. Is the domain hazard-protective? Choose PMT.

2. Is it health behavior? Choose HBM with custom registration.

3. Is it economic optimization? Choose Utility.

4. Is it social or planned behavior? Choose TPB with custom registration.

5. None of the above, or a novel theory? Choose custom.

## If the User Is Unsure

Deferring this choice is OK for a first smoke. It is reasonable to start with PMT, write down that the framework is provisional in `.research/<domain>_brief.md`, and switch later if the first traces show PMT does not fit the reasoning.

Do not overfit the first build. The first target is a clean prompt, parseable appraisals, and audit traces that expose whether the framework is useful.
