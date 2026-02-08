# WRR Section 2 Review and Rewrite Plan (WAGF v6)

## Scope

- Target: `paper/SAGE_WRR_Paper_v6.docx`, Section 2 (`2. WAGF Architecture`)
- Goal: align Chapter 2 narrative with current architecture figure and repository implementation
- Constraint: WRR Technical Note style (concise, method-focused, no over-claiming)

## Quick Skim Summary (Repo Architecture)

Core implementation is in `broker/`:
- Broker runtime: `broker/core/skill_broker_engine.py`
- Model adapter/parsing: `broker/utils/model_adapter.py`
- Skill registry: `broker/components/skill_registry.py`
- Validators: `broker/validators/`, `broker/governance/`
- Context builder: `broker/core/unified_context_builder.py` and `broker/components/context_builder.py`
- Memory engines: `broker/components/memory_engine.py`
- Reflection engine: `broker/components/reflection_engine.py`
- Audit logging: `broker/components/audit_writer.py`, `broker/utils/agent_config.py` (`GovernanceAuditor`)

Domain instantiation is configuration-driven in `examples/`:
- Flood domain: `examples/multi_agent/flood/...`
- Irrigation domain: `examples/irrigation_abm/...`

## Independent Reviewer Findings (Section 2)

### High

1. Figure reference mismatch risk:
- Current 2.2 text says six-phase pipeline is in `Figure 2`, but architecture pipeline is often represented as `Figure 1`.
- Reviewer attack: "Which figure is the system architecture of the method?"

2. Table semantic mismatch in 2.3:
- Section 2.3 text frames `Table 1` as domain instantiation, but current document shows a flood cross-model metrics table.
- Reviewer attack: "Architecture section points to a results table."

3. Conceptual boundary is under-specified:
- Figure shows LLM layer, Governed Broker, and System Execution layer with audit loops, but Section 2 text still reads mostly as "three-pillar summary."
- Reviewer attack: "Method boundary and responsibility separation not explicit enough."

### Medium

4. Figure and paragraph terminology are not fully synchronized:
- Figure uses `Model Adapter & Parser`, `Skill Registry`, `Validator`, `Auditor`, `Action Execution`, `Memory & Retrieval`, `Reflection`.
- Section text uses `three pillars` and `SkillRegistry pipeline`, but not all visible boxes are named in prose.

5. WAGF renaming consistency debt remains in support docs/scripts:
- Multiple files still use `SAGE` labels.
- Not always fatal for review, but can increase confusion in revision rounds.

## Rewrite Strategy for Section 2

Use a two-layer narrative:
1. System boundary and responsibility (LLM -> Broker -> Execution)
2. Internal mechanism of the Broker (proposal, validation, execution gate, audit, memory/context/reflection feedback)

This avoids conflict between "three pillars" and "pipeline components."

## Proposed Section 2 Structure (Paragraph-Level)

### 2.0 Architecture Overview (new opening paragraph, ~120-150 words)

Purpose:
- State strict separation of responsibilities:
  - LLM proposes
  - WAGF validates/governs
  - Environment executes state transitions
- Clarify that WAGF does not directly decide actions or mutate environment state.

### 2.1 Broker Pipeline (rewrite current 2.1/2.2 blend, ~180-230 words)

Paragraph should explicitly follow figure boxes:
1. Context assembly (`Context Builder` + memory retrieval signals)
2. LLM response and skill proposal (`Model Adapter & Parser`)
3. Skill lookup and pre/post conditions (`Skill Registry`)
4. Rule evaluation (`Validator`) with block/retry logic
5. Approved action handoff (`Action Execution` in simulation layer)
6. Trace persistence (`Auditor`)

Include one sentence on parser fallback robustness (JSON -> delimiters -> regex -> digit extraction).

### 2.2 Governance Components (three pillars as design principles, ~160-200 words)

Reframe pillars as cross-cutting components:
- Governance rules (identity/thinking/warning priority)
- Cognitive memory (window vs human-centric)
- Priority context (tiered truncation-resistant prompting)

This preserves existing contribution language while matching pipeline reality.

### 2.3 Domain Instantiation (tightened, ~130-170 words)

Keep configuration-only claim but avoid wrong table pointer:
- If Table 1 remains metrics table, remove "Table 1 instantiation" pointer from this paragraph.
- Mention domain-specific logic through YAML skill definitions, validators, prompt templates, and appraisal constructs.
- Flood and irrigation examples stay, but keep claims strictly "demonstrated in two domains."

## Figure-to-Code Mapping Snippet (for rebuttal/readability)

Can be added in SI or methods appendix:
- `Model Adapter & Parser` -> `broker/utils/model_adapter.py`
- `Skill Registry` -> `broker/components/skill_registry.py`
- `Validator` -> `broker/validators/*`, `broker/governance/*`
- `Auditor` -> `broker/components/audit_writer.py`
- `Context Builder` -> `broker/core/unified_context_builder.py`
- `Memory & Retrieval` -> `broker/components/memory_engine.py`
- `Reflection` -> `broker/components/reflection_engine.py`
- `Broker runtime` -> `broker/core/skill_broker_engine.py`

## Editing Checklist Before Text Rewrite

1. Confirm final figure numbering for architecture and pipeline (Figure 1 vs Figure 2).
2. Decide whether Section 2 includes one architecture figure or architecture + pipeline figure.
3. Resolve Table 1 role:
- Option A: keep metrics table in results section and remove Table 1 pointer in Section 2.
- Option B: restore domain-instantiation table in Section 2 and renumber metrics table.
4. Freeze component names exactly as shown in figure (avoid synonym drift).

## Suggested Next Step

After confirmation of Figure/Table numbering, apply direct rewrite to `paper/SAGE_WRR_Paper_v6.docx` Section 2 with one commit per subsection block:
1. `2.0/2.1` boundary + pipeline
2. `2.2` pillar reframing
3. `2.3` domain instantiation pointer fix
