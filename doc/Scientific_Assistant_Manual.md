# Scientific Assistant (SA) User Manual

**Version**: 1.0 (Integration with JOH Cognitive Architecture)
**Last Updated**: 2026-01-18

## 1. What is the Scientific Assistant?

The Scientific Assistant (SA) is a specialized "Persona Skill" designed to help you write, review, and refine scientific manuscripts (specifically the **JOH Technical Note**). It acts as a "second brain" that holds the project's specific architectural knowledge.

## 2. Core Capabilities (Modes)

You can activate different modes by explicitly telling the Agent: _"Activate SA Mode X"_.

### Mode 1: DRAFT_ASSIST (Writing)

- **Function**: Converts your bullet points into academic prose.
- **Style**: Objective, precise, IMRAD structure.
- **Usage**: _"SA Mode 1: Rewrite this paragraph to sound more like a Nature methodology section."_

### Mode 2: REVIEW_CRITIC (Peer Review)

- **Function**: Simulates "Reviewer #2". Finds flaws in logic or claims.
- **Checklist**: Novelty, Methodology, Results, Discussion.
- **Usage**: _"SA Mode 2: Critique the Abstract of the current draft. Be harsh."_

### Mode 3: CITATION_AUDIT (Bibliography)

- **Function**: Checks if citations are balanced and resolved.
- **Usage**: _"SA Mode 3: Scan the document for missing references."_

### Mode 4: COGNITIVE_ARCHITECT (System Explanation) **[NEW]**

- **Function**: Explains the internal mechanics of the Governed Broker Framework.
- **Key Topics**:
  - **Skill Registry**: Why we use YAML validation (Mechanism 1).
  - **Hierarchical Memory**: How "Trauma Recall" works (Mechanism 2).
- **Usage**: _"SA Mode 4: Explain to me how the memory weighting algorithm works again?"_

## 3. Persistent Memory

The SA's knowledge is stored in `doc/dev_notes_gemini/scientific_assistant_skill.md`. This file contains the instructions that define its behavior.

To "install" this skill on a new machine:

1.  Open the project.
2.  Tell the AI: _"Please read `doc/dev_notes_gemini/scientific_assistant_skill.md` to load your persona."_

## 4. Best Practices for Collaboration

- **Iterative Review**: Use Mode 2 to critique -> Mode 1 to fix.
- **Fact Checking**: Use Mode 4 to verify that the _paper's claims_ match the _code's reality_.
- **Traceability**: Always ask the SA to link claims back to specific artifacts (e.g., "Show me the `run_stress_marathon.ps1` line that defines this parameter.").
