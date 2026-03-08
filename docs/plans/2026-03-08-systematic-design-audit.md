# Systematic Design Audit

Date: 2026-03-08
Scope: WAGF core architecture, theory layer, and water-sector reference implementations

## Executive Summary

WAGF is now a credible research-grade governance framework for LLM-driven ABM in human-water systems. Its strongest design property is not any single flood or irrigation case, but the separation between:

- a reusable governance core in `broker/`
- theory/domain metadata in water-domain packs
- runnable reference implementations in `examples/`

The framework is already strong enough to support continuation papers and external ABM experimentation. The main remaining weakness is not scientific validity, but uneven surface design: some parts present as a clean framework, while others still expose research-era coupling, large runners, or paper-oriented workspaces.

The practical conclusion is:

- the core design is coherent
- the water-sector identity is clear and should remain primary
- the extension path beyond water is plausible but should remain secondary
- the next quality gains come from boundary hardening and developer-facing entry cleanup, not new features

## Design Identity

WAGF should be described as:

- a governance middleware for LLM-driven ABM
- designed first for human-water systems
- using theory-grounded validation to convert raw LLM outputs into auditable simulation behavior

It should not be described as:

- a flood-only framework
- a generic planner
- a prompt-engineering wrapper

This identity is already reflected in:

- `README.md`
- `ARCHITECTURE.md`
- `docs/guides/domain_pack_guide.md`
- `docs/guides/experiment_design_guide.md`

## Current Layering

The repository now reads as four surfaces:

1. Framework core
   - `broker/`
   - `providers/`
   - `tests/`

2. Water-sector reference implementations
   - `examples/single_agent/`
   - `examples/irrigation_abm/`
   - `examples/multi_agent/flood/`

3. Tutorials and templates
   - `examples/quickstart/`
   - `examples/minimal/`
   - `examples/minimal_nonwater/`
   - `examples/multi_agent_simple/`
   - `examples/governed_flood/`

4. Manuscript and local research workspaces
   - `paper/`
   - `.ai/`
   - `examples/archive/`
   - `examples/multi_agent/flood/paper3/`

This is the right overall shape for a paper-first, release-aware research framework.

## Core Architectural Strengths

### 1. Governance pipeline is structurally real

`broker/core/skill_broker_engine.py` shows a genuine governance loop:

- bounded context construction
- skill proposal parsing
- registry filtering and retrieval
- validator routing
- retry with structured intervention
- execution only through the simulation engine
- full audit writing

This is the framework's central contribution. The design is materially stronger than prompt-only ABM agents because the LLM never receives direct state mutation authority.

### 2. Theory is implemented, not just narrated

The water domain pack registers multiple behavioral frameworks in:

- `broker/domains/water/__init__.py`
- `broker/domains/water/thinking_checks.py`

Current registered theory families include:

- `pmt`
- `cognitive_appraisal`
- `utility`
- `financial`

This is important because it means the framework's psychological grounding exists in executable metadata, not only in papers.

### 3. Configuration-first design is mostly sound

Across the framework, reusable behavior is configured through:

- `agent_types.yaml`
- `skill_registry.yaml`
- prompt templates
- governance rule definitions
- memory settings

This is the right abstraction for ABM developers. It lowers the amount of Python they need to touch when adapting a case.

### 4. Reference implementations are scientifically differentiated

The three main water-sector cases are not redundant:

- `examples/single_agent/`: single-agent flood validation and ablation
- `examples/irrigation_abm/`: irrigation decision-making with cognitive appraisal
- `examples/multi_agent/flood/`: institutional and cross-agent flood dynamics

Together they show that the broker is not tied to a single action space or one theory.

## Main Design Risks

### 1. Core still contains example-facing coupling

There are still direct imports or optional re-exports from `examples/` inside `broker/`, notably in:

- `broker/validators/governance/__init__.py`
- `broker/interfaces/artifacts.py`
- `broker/components/events/generators/hazard.py`
- `broker/components/events/generators/impact.py`

This does not break the framework, but it weakens the claim that `broker/` is fully domain-agnostic. The most important issue is not comments mentioning examples; it is runtime-level dependency paths that still reach into example directories.

### 2. Some runners remain too research-oriented

The largest runnable cases still have large, multi-responsibility entrypoints:

- `examples/single_agent/run_flood.py`
- `examples/multi_agent/flood/run_unified_experiment.py`

These scripts are useful for paper reproduction, but they are not yet ideal as developer-facing exemplars because they combine orchestration, configuration overrides, analysis-side behavior, and simulation wiring in one place.

### 3. Surface quality is inconsistent

Some repo surfaces are clean and well-positioned, but others still carry:

- mixed encoding artifacts
- very long research README files
- legacy wording
- analysis or manuscript assumptions close to runtime surfaces

This is most visible in older example readmes and some guide documents.

### 4. Multi-skill is bounded, not general

The current multi-skill system in:

- `broker/interfaces/skill_types.py`
- `broker/core/skill_broker_engine.py`

is best understood as bounded composite action:

- primary skill
- optional secondary skill
- sequential execution
- default disabled

This is a useful feature, but it should remain documented as constrained composite behavior rather than a general planner.

## Assessment by Reference Implementation

### Single-Agent Flood

Strengths:

- strongest validation narrative
- best-developed ablation logic
- clearest demonstration of governance, memory, and PMT coherence

Weaknesses:

- `README.md` is still too research-heavy and noisy for first-time ABM developers
- `run_flood.py` is large and carries many concerns at once
- `agent_types.yaml` is rich but difficult to read as a minimal customization surface

Verdict:

- strongest scientific reference implementation
- not yet the cleanest developer-facing one

### Irrigation ABM

Strengths:

- conceptually distinct from flood
- now properly aligned to Cognitive Appraisal Theory
- shows the framework can govern long-horizon resource management

Weaknesses:

- still carries strong paper-reproduction framing
- some terminology and documentation still need full consistency cleanup

Verdict:

- strongest proof that WAGF is not flood-only
- still best read as a research implementation before a polished developer template

### Multi-Agent Flood

Strengths:

- best institutional and multi-role demonstration
- now has a clearer developer-facing entry README
- `paper3/` is increasingly separated from runtime

Weaknesses:

- runtime package still sits close to paper-oriented assets
- configuration surface is powerful but still dense for new users
- some broker interfaces still depend on MA-specific example code

Verdict:

- strongest proof of scope and ambition
- still the least polished as a general reusable implementation surface

## ABM Developer Readiness

For ABM developers, WAGF is already usable if they are comfortable reading YAML and Python. The main value proposition is:

- define actions in a skill registry
- define constructs and rules in agent config
- assemble a simulation environment
- let the broker enforce decision coherence

What is already ready:

- governance mental model
- theory registration path
- templates and tutorials
- provider abstraction
- test surface for many core behaviors

What still needs hardening:

- cleaner developer entrypoints for large reference implementations
- fewer example-to-core runtime imports
- more explicit "minimum files to modify" guides per reference implementation
- continued wording cleanup where older theory labels remain in docs

## Priority Recommendations

### Priority 1: Finish boundary hardening

Reduce runtime-level imports from `broker/` into `examples/` wherever possible. The highest-value targets are artifact and validator wiring.

### Priority 2: Split developer entry from research dossier everywhere

The MA flood pack already moved in this direction. The same pattern should be applied to:

- `examples/single_agent/`
- later, selected irrigation surfaces if needed

### Priority 3: Make configuration surfaces easier to modify

Each primary reference implementation should have a short guide that answers:

- which files are mandatory to understand
- which files are the first ones to modify
- which files are paper-specific and can be ignored

### Priority 4: Keep water-sector-first positioning stable

Do not flatten the repo into a generic anything-framework. The current strongest message is:

- reusable governance core
- water-sector-first identity
- extension path available but secondary

This is more defensible scientifically and clearer for users.

## Recommended Near-Term Work

The most effective next steps are:

1. Split `examples/single_agent/README.md` into developer and research versions.
2. Add config-surface README files for the main reference implementations.
3. Gradually remove remaining `broker/ -> examples/` runtime imports.
4. Continue document wording cleanup so the repo tells one consistent story.

## Bottom Line

WAGF is no longer just a collection of water-sector experiments. It now has the shape of a real framework.

Its strongest qualities are:

- theory-grounded governance
- strong auditability
- reusable broker architecture
- multiple serious water-sector reference implementations

Its main remaining weaknesses are:

- inconsistent surface polish
- residual example coupling in core modules
- research-heavy entrypoints for large cases

That means the project is in a strong continuation phase:

- scientifically mature enough for follow-on papers
- architecturally coherent enough for external ABM developers to learn from
- still one structured cleanup cycle away from feeling like a polished public framework release
