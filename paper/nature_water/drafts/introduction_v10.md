# Nature Water — Introduction (v14 — water-first preview, constraint paradox removed)
## Date: 2026-02-13 | Target: ~830 words | Analysis format
## Narrative: tension-first → Harvard Water Program → historical evolution → decision format gap → LLM paradigm shift → governance
## Status: 2 rounds of expert review (NW + ABM), both Minor Revisions → final polish applied

---

## Introduction

For six decades, computational models of water resource systems have represented human decisions in a single paradigm: as computable mappings from system states to actions. Whether the mapping is a linear program, a coupled differential equation, or an agent's decision rule, the person choosing how much water to divert, whether to buy flood insurance, or when to reduce irrigation is reduced to a parameterized function. This paradigm — established when the Harvard Water Program introduced operations research to water planning (Maass et al., 1962) — enabled rigorous engineering analysis but compressed the reasoning process into a mathematical object, foreclosing a question that water governance increasingly demands we answer: not just what people decide, but how they reason toward those decisions.

Subsequent frameworks expanded the scope of human–water modelling without departing from this numerical paradigm. Coupled human–natural systems theory recognized that human decisions and physical processes co-evolve through feedback loops (Liu et al., 2007). Sociohydrology formalized water-specific feedbacks — levee effects, supply–demand cycles, reservoir operation — as coupled differential equations, but human behaviour entered these equations as aggregate parameters rather than as individual reasoning processes (Sivapalan et al., 2012; Di Baldassarre et al., 2019). As Blair and Buytaert (2016) observed in their review of socio-hydrological modelling, models could represent that populations respond to flood risk, but not how individuals reason toward protective action.

Agent-based modelling introduced individual-level decision-making by representing heterogeneous agents who act on local information and interact through shared environments (Epstein and Axtell, 1996; Bonabeau, 2002). In water research, Berglund (2015) modelled irrigation scheduling in the Yakima Basin through threshold-based allocation rules; Haer et al. (2017) used Protection Motivation Theory to drive household flood-adaptation choices through threat and coping appraisal scores; Hung and Yang (2021) encoded prior-appropriation operating rules (the seniority-based water rights system governing western US rivers) for Colorado River demand management. More recent approaches have introduced adaptive mechanisms — Bayesian belief updating, reinforcement learning policies (Castilla-Rho et al., 2015), and BDI cognitive architectures — that allow agents to learn and extrapolate beyond initial conditions. Yet even these approaches map numerical state vectors to numerical actions; the decision architecture — state representation, action space, and behavioural theory — must be redesigned for each domain (An, 2012; Müller et al., 2013), drawing from a fragmented landscape of over 40 distinct behavioural theories that Schlüter et al. (2017) mapped across agent-based applications. All agents within a given simulation follow the same cognitive model, differing only in parameter values — a structural rigidity that limits the representation of qualitatively different reasoning strategies within a single population.

Large language models introduce a qualitatively different representational format: agents that reason in natural language rather than through numerical functions. Instead of mapping state variables to actions through parameterized functions, a language-based agent reads contextual information — drought indices, water rights, neighbour behaviour, institutional announcements — and generates a decision through linguistic reasoning that can reference domain knowledge, weigh trade-offs, and articulate justifications. Generative agents have demonstrated believable social behaviours including persona maintenance and adaptive planning (Park et al., 2023); structured environments such as Concordia have shown that language agents can operate within defined action spaces (Vezhnevets et al., 2023); and large-scale social simulations have begun exploring population-level dynamics with over 1,000 LLM agents (Guo et al., 2024). This body of work suggests that natural language may serve as a medium for representing the reasoning processes that numerical formats compress away.

Yet language-based agents carry risks that are acute for scientific simulation. An agent might propose a water allocation that violates mass balance, a home elevation on an already-elevated structure, or a demand increase beyond its legal water right. These constraint violations — distinct from the factual hallucinations studied in natural language processing (Huang et al., 2025) — arise because LLMs lack inherent physical grounding, and their frequency varies substantially across model families and scales. Most existing LLM-agent studies lack empirical behavioural benchmarking against observed patterns. The question is not whether language-based agents can reason about water decisions — early evidence suggests they can — but whether their outputs can be governed by the physical and institutional constraints that define real water systems.

Answering this governance question connects computation to institutional theory. Constraints are conventionally expected to reduce the space of available actions. But Ostrom (1990) observed that well-designed institutions for managing common-pool resources do not merely restrict behaviour — they define feasibility boundaries within which diverse adaptive strategies become viable. We hypothesized that architectural governance — validating agent proposals against physical and institutional rules before execution — would produce a structurally analogous outcome at the computational level: eliminating physically impossible outputs while preserving or expanding the space of plausible decisions. We note that this is a structural parallel between institutional rules governing communities and computational validators governing artificial agents, requiring empirical rather than theoretical justification.

Here we test this hypothesis across two contrasting water domains: irrigation management in the Colorado River Basin (78 agents, 42 years, generating over 9,800 governed decisions across three seeds) and household flood adaptation (100 agents, 10 years, stochastic flood events, 3,000 governed decisions validated against empirical behavioural benchmarks). Governed agents exploit water more aggressively during abundance and curtail during drought — a pattern of adaptive exploitation whose underlying reasoning, visible in natural language, is compressed away by parameterized decision functions. Ungoverned agents collapse into repetitive behavioural patterns. Removing a single institutional rule — the demand ceiling — collapsed this drought coupling while increasing behavioural diversity, establishing that governance channels diversity toward adaptive patterns rather than merely expanding the action space. Governed agents also produced higher behavioural diversity than a hand-coded Protection Motivation Theory baseline (Haer et al., 2017) operating under the same behavioural theory — demonstrating that language-based reasoning generates qualitatively richer decision repertoires than numerical threshold models. This governance effect on behavioural diversity is positive for five of six language models tested, three statistically significant. Governance also nearly eliminates physically irrational behaviour, with significant reductions in four of six models. Because each institutional rule can be independently enabled, disabled, or reconfigured, the approach functions as a method for experimentally probing how specific institutional designs shape adaptive water behaviour — a computationally governed representation of how people reason about water under uncertainty.

---

### Word count: ~830
### Changes from v9 → v10 (R1 reviewer response):
- **Opening**: Tension-first ("six decades, single paradigm") instead of factual Harvard statement
- **ABM characterization**: Added Bayesian/RL/BDI acknowledgment + argued they still map R^n→R^m
- **"confined to deterministic logic"** → **"computable mappings from system states to actions"** — accurate for all approaches including stochastic
- **Three limitations** compressed into ABM paragraph: domain-redesign + theory fragmentation + behavioral rigidity
- **"from scratch"** → **"redesigned for each domain"** with An (2012), Müller (2013) citations
- **"fundamentally different"** → **"qualitatively different"**
- **Schlüter** reframed: "mapped across applications" not "little standardization"
- **Grimm 2005** removed — POM not about reusability; cite in Methods/Validation
- **Guo et al. (2024)** added for LLM-ABM scale
- **Castilla-Rho et al. (2017)** added as RL example
- **"22/35 studies"** → "Most existing LLM-agent studies lack empirical behavioural benchmarking" (detail to Discussion)
- **Ostrom** qualified: "structural parallel... requiring empirical rather than theoretical justification"
- **"broker core"** removed from results preview
- **Final sentence** split; "constraint scaffolding effect" given own moment
- **Concrete scale** added: "6,500 governed decisions", "5,000 governed decisions validated against 8 empirical benchmarks"
- **Blair & Buytaert** elevated to stronger syntactic position
- **Behavioral rigidity** added as ABM limitation

### R2 polish (final):
- **f(x)=y** → **"parameterized function"** / **"computable mappings"** — accommodates stochastic models (ABM N1)
- **Hallucination** reframed: lead with water-specific constraint violations, distinguish from NLP factual hallucination (ABM N3, NW N5)
- **P5→P6 transition**: "Answering this governance question connects..." smooths the pivot (NW N3)
- **"constraint scaffolding effect"** glossed as "what we term" on first use (NW N4, ABM N2)

### v10 → v11:
- **P7 final sentence extended**: Added method contribution seed — domain-agnostic broker + rule ablation capability → "transferable method for probing how specific institutional designs shape adaptive behaviour"
- Plants seeds for Discussion "computational laboratory" harvest
- ~15 words added (total ~845)

### Review history:
- R1: NW reviewer (10 issues) + ABM reviewer (10 issues) → all addressed
- R2: NW reviewer (Minor Revisions, 5 minor new) + ABM reviewer (Minor Revisions, 4 minor new) → all addressed
- **Final verdict: ACCEPTED by both reviewers after R2 polish**
