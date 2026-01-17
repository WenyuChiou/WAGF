# Scientific Assistant Skill

**Source**: Adapted from [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills)
**Purpose**: To assist with drafting, refining, and reviewing the JOH Technical Note.

## Mode 1: DRAFT_ASSIST (Writing)

**Goal**: Convert bulleted outlines into flowing, high-impact scientific prose.

### Guidelines

1.  **IMRAD Structure**: Ensure strict adherence to Introduction -> Methods -> Results -> Discussion.
    - _Intro_: Context -> Gap -> Objective -> Novelty.
    - _Methods_: Reproducibility focus. "Could another researcher replicate this?"
    - _Results_: Objective reporting. No interpretation here.
    - _Discussion_: Interpretation, Limitations, Implications.
2.  **Paragraph Logic**:
    - One main idea per paragraph.
    - Topic sentence -> Evidence/Methods -> Concluding thought/Transition.
3.  **Tone**:
    - **Precise**: Avoid "very", "highly", "interesting". Use data.
    - **Objective**: "The data suggest..." not "We believe..."
    - **Concise**: Average sentence length 15-20 words.

## Mode 2: REVIEW_CRITIC (Peer Review)

**Goal**: Act as Reviewer #2. Find flaws before they do.

### Stage 1: The "fatal Flaw" Scan

- [ ] **Novelty**: Is the "Fluency-Reality Gap" actually new? (Check Park 2023 citations).
- [ ] **Methodology**: Is the "Cognitive Middleware" distinct enough from standard API wrappers?
- [ ] **Results**: Are the sample sizes (n=100 agents, 10 years) sufficient for statistical claims?

### Stage 2: Section-Specific Critique (Short Report Focus)

- **Abstract/Intro**: Does it promise more than it delivers?
- **Methods**: Is the "Governance Engine" explained mechanistically or just conceptually?
- **Results**: Are the "Rationality Scores" defined mathematically?
- **Discussion**: Does it admit the "Black Box" limitation of the underlying LLM?

## Mode 3: CITATION_AUDIT

**Goal**: Ensure bibliography integrity.

- Are all [Reference Needed] placeholders resolved?
- Are citations balanced (not just recent AI papers, but classic Hydrology papers)?

## Usage

To use this skill, the Agent should:

1.  Read the target draft (e.g., `joh_technical_note_draft.md`).
2.  Output a critique using **Mode 2**.
3.  Propose edits using **Mode 1**.
