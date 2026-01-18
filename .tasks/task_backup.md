# Task: Gemma Static Behavior Investigation & Context Cleanup

## Status

- **Task ID:** task-003 (Full Benchmark)
- **Current Mode:** EXECUTION
- **Objective:** Run full benchmarking suite across 4 models and 2 engines.
- **Update:** Confirmed root cause (Trust Reset) and fixed `InteractionHub`. Verified with `verify_fix.py`.
- **Status:** Benchmark restarted (Run ID: `ce0d98c4...`). Running Year 1.
- **Status:** Done. Gemma Window analysis complete and verified.
- **Status:** Experiments Concluded. Gemma 3 data successfully validated (Stability +37%). DeepSeek R1 halted due to computational cost (Reasoning Overhead).
- **Next:** Finalize Technical Note (JOH) and prepare submission package.

## Checklist

### 1. Parity Infrastructure & Cleanup (COMPLETE)

- [x] Fix `run_flood.py`: Strict Option Text Parity (elevated vs non-elevated)
- [x] Fix `run_flood.py`: Insurance Renewal Logic (Annual expiry)
- [x] Fix `run_flood.py`: Memory Message Parity (Strict baseline strings)
- [x] Fix `run_flood.py`: 80% Risk Reduction on Elevation

### 2. Large Scale Running (Phase 1: Baselines)

- [x] **Gemma 3 4B Group A (Baseline)** - ✅ COMPLETE
  - [x] Use original code logic via `run_baseline_original.py` (FIXED Prompt Encoding)
  - [x] Complete 10-year tracking for 100 agents (Validated with `run_final_v2.py`)
- [x] **Llama 3.2 3B Group A (Baseline)** - ✅ COMPLETE
  - [x] Logic: Original Baseline Parity
- [ ] **Data Organization**: Move results to `results/JOH_FINAL/<model>/Group_A`
- [x] **Desktop vs Repo Comparison**: Confirmed logic parity (Memory Window=5, Deterministic Trust). Differences due to Model (Gemma vs Llama).

### 3. Scenario B: Triple-Run Benchmark (N=3) - MARATHON 🚀

- [ ] **Scenario B: Triple-Run Benchmark (N=3)** - 🔄 RUNNING 🚀
  - [x] **Llama 3.2 3B**: **COMPLETE** (Verified Run 3/3 Group C)
  - [/] **Gemma 3 4B**: **RUNNING** (Run 3/3 Group A: Year 10 Finished -> Starting Group B)
  - [/] **Sequential Group (Large Models)**: GPT-OSS 20B & DeepSeek R1 8B - **DEEPSEEK STARTED** (Run 1/3 Group A: Year 8)
- [ ] **Consistency Analysis**: Compute AC (Adaptation Consistency) across the 3 runs for 4 models.

### 4. Stress Test Marathon - MARATHON 🚀

- [/] **Parallel Group**: Llama 3.2 3B & Gemma 3 4B
  - [/] Execute via `run_stress_marathon.ps1` (N=10 runs/scenario)
- [ ] **Sequential Group**: GPT-OSS 20B & DeepSeek R1 8B
  - [ ] Execute via `run_stress_marathon.ps1`

### 3. Data Integrity & Verification

- [ ] Ensure all `simulation_log.csv` contain `yearly_decision`
- [ ] Verify `household_traces.jsonl` are cleaned for each run
- [x] Compare adaptation distributions against baseline results (Gemma discrepancies resolved)
- [ ] Verify `household_traces.jsonl` are cleaned for each run

### 4. Context & Cognitive Audit

- [x] **Audit Context Construction**: Review `ContextBuilder` and `agent_types.yaml` for potential biasing factors.
- [x] **Document Context Issues**: Create `context_issues_audit.md` listing potential problems (Threat Inflation, Memory Clutter, Structural Bias).
- [x] **Update README**: Add architectural documentation for Context Design and Cognitive Biases in `README.md`.
- [x] **Propose Mitigations**: Suggest fixes (Prompt Tuning verified via Discrepancy Check).
- [x] **Cleanup Configurations**: Removed ambiguous `JOH_Macro/config.yaml` to standardize on `agent_types.yaml`.

### 5. Documentation Separation & Cleanup

- [x] **Migrate Technical Specs**: Move Disaster Model & Agent Init details from root README to `examples/single_agent/README.md`.
- [x] **Clean Root README**: Remove specific experiment details (SA, SQs) from `README.md`.
- [x] **Clean Root Chinese README**: Remove specific experiment details from `README_zh.md` and sync new Cognitive Architecture section.
- [x] **Optimize SA README**: Reframe `examples/single_agent/README.md` as Framework Validation (Groups A/B/C).

### 6. Comprehensive Benchmark Analysis

- [x] **Analysis Prep**: Created `run_control_benchmark.ps1` (Group A) and `analysis/comprehensive_analysis.py`.
- [/] **Data Collection**: `run_joh_suite.ps1` re-running with visible logs (Group B/C).
  - [x] **Legacy Analysis (Group A)**: Analyzed `old_results`. Llama 3.2: 95% Panic (Relocation Baseline) -> 84% (Governed). Gemma: 53% -> 73% Adaptation. Integrated audit validation into `comprehensive_analysis.py`.
- [ ] **Generate Analysis Reports**: Create "All-Encompassing" Benchmark Reports (EN/CH).
- [ ] **Verification**: Validate "Rational Convergence" and "Hallucination Fix" metrics.

### 7. Stress Testing (Validation)

- [x] **Tooling**: Created `analyze_stress.py` and `run_stress_multi.ps1`.
- [/] **Scenario Enhancement**:
  - [x] **ST-1 Panic**: Forced 70% flood frequency (7/10 years) in `run_flood.py`.
  - [x] **ST-4 Format**: Injected anti-format persona in `run_flood.py`.
- [ ] **Data Collection (In Progress)**:
  - [ ] `run_stress_marathon.ps1` (N=10 runs each):
    - [ ] Llama 3.2 3B: Ready to launch.
    - [ ] Gemma 3 4B: Ready to launch.
- [ ] **Scientific Visualization**:
  - [ ] Generate Sankey diagrams including **"Validator Correction"** nodes.
  - [ ] Map CP (Coping Appraisal) as "Financial Capability" proxy in Discussion.

### 7. Technical Note Development (JOH)

- [x] **Validation Section**: Drafted "Stress Testing the Cognitive Architecture" (Table 1 integrated into Sec 3).
- [x] **Reports**: Created `joh_stress_validation_report.md` and `joh_model_comparison_report.md`.
- [x] **Results Section**: Finalized and consolidated with Discussion (Sec 4).
- [x] **Structure Optimization**: Streamlined to 5 Sections (Intro, Method, Experiment, Results, Conclusion).
- [x] **Define Technical Roadmap**: Refined `joh_technical_note_roadmap.md` with **4 Architectural Pillars** (Context, Governance, World, Memory) and 5 KPIs.
- [x] **Problem Verification**:
  - [x] Validate **Hallucination Gap** across models (Logic Blocks in Group B).
  - [x] Validate **Inaction Bias** in small models (Adaptation Gain Group A->B).
  - [x] Validate **Panic Mitigation** (Relocation Reduction Group A->B).
- [x] **KPI Calculation**:
  - [x] Compute **Rationality Score (RS)** for all finished runs.
  - [x] Compute **Relocation Coefficient (RC)** to quantify "The Panic Machine" baseline.
  - [x] Analyze **Memory Goldfish Effect** via Group B vs C deltas.
- [x] **Strategic Enhancement Implementation (Stacked PRs)** ✅:
  - [x] **Priority 1: Explainable Governance (PR #1: Self-Correction Trace)** `5ab2e43`:
    - [x] Update `SkillBrokerEngine` to capture "Rejection Metadata" from validators.
    - [x] Modify `ModelAdapter` to inject "Reason for Intervention" into the retry prompt.
    - [x] **Verified**: Test syntax and imports passed. SA 3-agent run passed.
  - [x] **Step 5: Batch Reflection Optimization (Pillar 2)**
  - [x] Create implementation plan for Batch Reflection (PR #4).
  - [x] Implement `generate_batch_reflection_prompt` & `parse_batch_reflection_response` in `ReflectionEngine` (Code Action: 4 files).
  - [x] Update `run_flood.py` to collect and process reflection batches.
  - [x] Verify efficiency (3 agents tested: 0.9 importance confirmed).
- [ ] **Step 6: Future Module Optimization (Post-Experiment)**
  - [ ] Implement Rule Caching (Governance).
  - [ ] Implement Vector Storage (Memory).
  - [x] **Priority 3: Domain Alignment (PR #3: Constrained Perception)** `7c0b4a4`:
    - [x] Added `PrioritySchemaProvider` to `ContextBuilder` for YAML-driven attribute weighting.
    - [x] Verified import test passed.

### 8. Final Results Harvesting (JOH Submission) 🚀

- [x] **Step 1: Strict Experiment Separation**
  - [x] Update `run_flood.py` with `PrioritySchemaProvider` argument (Pillar 3).
  - [x] Create `run_joh_macro.ps1` (Quantitative: Group C).
  - [x] Create `run_joh_stress.ps1` (Qualitative: Stress Test).
- [x] **Step 2: JOH Macro Benchmark Execution**
  - [x] Run `run_joh_stress.ps1` (Quick check for traces). ✅ Verified!
  - [x] Implement parallel suite `run_joh_suite.ps1` with path restructuring.
  - [x] Run parallel small-scale verification (B+C, 5 agents). ✅ Verified!
  - [x] **Step 2.6: Fix Interim Log Collision**
  - [x] Debug and fix state persistence bug (`run_flood.py`, `memory_engine.py`, `llm_utils.py`)
- [x] Archive corrupted simulation data and reset environment
- [/] Re-run prioritized Llama 3.2 3B and Gemma 3 4B simulations
  - [/] Launch 100-agent, 10-year Group B (Window Memory) for Llama
  - [/] Launch 100-agent, 10-year Group C (Hierarchical Memory) for Llama
  - [x] Skip Group A (already preserved in `old_results`)
- [x] **Core Framework Optimization (Task-012)**
  - [x] Plan `BaseAgent.apply_delta` interface
  - [x] Add Parity Verification logic per user request
  - [x] Compare Agent 1 in desktop gemma log vs repo gemma log to find discrepancy
- [x] Identify "Shallow Memory" bug as root cause
- [x] **Investigation**: Repo vs Desktop Discrepancy
  - [x] Compare logs (Agent 1 behavior)
  - [x] Confirm "Small Window + Random Seed" as root cause of instability
- [/] **Phase 2: Tiered Memory System (Group C)** in `run_tiered_memory.py`
  - [x] Basic Tiered Memory structure (Short-term window + Long-term storage)
  - [/] Verify with test run
  - [ ] Integrate into benchmark runner
  - [x] Verify Implementation (`feat/core-persistence-implementation-012` branch verified)
- [x] Merge Task-012 to main/dev (Already Up-to-Date)
- [x] Git Commit Final Fixes (Task 011/012)
- [/] Project Structure Cleanup
  - [ ] Delete temporary/redundant files (e.g., `debug_output.txt`, legacy `results_window`)
  - [ ] Consolidate analysis reports under `examples/single_agent/analysis/reports/`
  - [ ] Ensure project is lint-free/clean
- [/] Final Scientific Manuscript (JOH Technical Note)
  - [ ] Draft final sections in Word format
  - [ ] Integrate full BibTeX bibliography
  - [ ] Embed Figures 1-4 with final data
- [/] Validate re-run data parity for Groups B & C
  - [x] Define 4 Scenarios (Panic, Veteran, Memory, Format) in [stress_test_scenarios.md](file:///C:/Users/wenyu/.gemini/antigravity/brain/507f7c8b-0020-4e20-9706-a4e0d5a38ac9/stress_test_scenarios.md).
  - [/] Execute **ST-1: The Panic Machine** (Governance/Logic) for Llama - 🔄 RE-RUNNING.
  - [/] Execute **ST-2: The Optimistic Veteran** (Pillar 3/Bias) for Llama - 🔄 RE-RUNNING.
  - [/] Execute **ST-3: The Memory Goldfish** (Pillar 4/Memory) for Llama - 🔄 RE-RUNNING.
  - [/] Execute **ST-4: The Format Breaker** (Pillar 1/Syntax) for Llama - 🔄 RE-RUNNING.
- [ ] **Step 3: Paper Drafting & Scientific Synthesis**
  - [x] Define 5 Core Metrics (RS, IY, AM, AA, PR) in [analysis_metrics_framework.md](file:///C:/Users/wenyu/.gemini/antigravity/brain/507f7c8b-0020-4e20-9706-a4e0d5a38ac9/analysis_metrics_framework.md).
  - [x] Create Paper Skeleton with PMT/CoALA grounding in [joh_technical_note_skeleton.md](file:///C:/Users/wenyu/.gemini/antigravity/brain/507f7c8b-0020-4e20-9706-a4e0d5a38ac9/joh_technical_note_skeleton.md).
  - [x] Map Figure 1-4 to specific experiment output files.
  - [x] Create [joh_paper_bibliography.md](file:///C:/Users/wenyu/.gemini/antigravity/brain/507f7c8b-0020-4e20-9706-a4e0d5a38ac9/joh_paper_bibliography.md).
  - [x] **Fix Citation Gap**: Added AQUAH/W-Agent to Intro & Bibliography.
  - [x] Create [joh_paper_structure_blueprint.md](file:///C:/Users/wenyu/.gemini/antigravity/brain/507f7c8b-0020-4e20-9706-a4e0d5a38ac9/joh_paper_structure_blueprint.md).
  - [x] Create [research_execution_protocol.md](file:///C:/Users/wenyu/.gemini/antigravity/brain/507f7c8b-0020-4e20-9706-a4e0d5a38ac9/research_execution_protocol.md).
  - [x] Refine `joh_evaluator.py` for batch multi-model processing.
- [x] Run Full parallel benchmark (B+C, 100 agents). 🚀 100% COMPLETE.
- [x] Integrate [scientific_assistant_skill.md](file:///H:/我的雲端硬碟/github/governed_broker_framework/examples/single_agent/manuscripts/JOH_Note/scientific_assistant_skill.md).
- [x] Conduct Initial Self-Review Audit [review_report.md](file:///H:/我的雲端硬碟/github/governed_broker_framework/examples/single_agent/manuscripts/JOH_Note/review_report.md).
- [ ] **Step 3: Data Analysis & Comparison**
  - [x] Run parallel benchmark (Group B vs Group C, 100 agents).
  - [x] Extract Rationality Score (RS) Comparison.
- [x] **Step 4: Documentation & Final Reporting**
  - [x] Document Pillar 2 Memory Architecture (Working vs Long-term vs Reflection).
  - [ ] Conduct Fidelity Index (FI) Manual Trace Review.
  - [x] Updated Session Handoff Log for next AI session.
- [ ] **Step 4: Final Figures**
  - [ ] Figure 1: 3-Pillar Architecture Diagram.
  - [ ] Figure 2: Rationality Score Comparison (Group A/B/C).
  - [ ] Figure 3: Adaptation Trend (Group B vs C).

### 8. Gemini API Integration (Universal Module)

- [x] **Research**: Audit existing model plugins for API interface patterns.
- [x] **Design**: Define the `UnifiedModelInterface` for API-based models.
- [x] **Implementation**:
  - [x] Create `GeminiAPIPlugin` (implemented as `GeminiProvider`).
  - [x] Implement rate-limiting and retry logic for API stability (`RateLimitedProvider`).
- [x] **Verification**: Run a single-agent test simulation using Gemini 2.0. ✅ Verified with 1.5 Flash.

### 9. JOH Experiment Completion

- [/] **Stress Tests**:
  - [x] Llama 3.2 3B - COMPLETE.
  - [/] Gemma 3 4B - IN PROGRESS (Run 3/10 Paníc).
  - [/] DeepSeek R1 8B - **HALTED** (Excluded from Stress Test).
  - [-] GPT-OSS - **CANCELLED** (Excluded from Stress Test).
- [/] **Macro Benchmarks (Groups B/C)**:
  - [x] Llama 3.2 3B - COMPLETE.
  - [x] Gemma 3 4B - **COMPLETE** (Marathon Run 3 validated).
  - [-] GPT-OSS - **CANCELLED** (Sufficient data from Gemma/Llama).
  - [-] DeepSeek R1 8B - **HALTED** (Performance Trade-off documented).
- [/] **Data Management**:
  - [x] Relocate DeepSeek R1 Stress results to `examples/single_agent/results/`.
  - [ ] Archive partial DeepSeek traces for "Reasoning Cost" appendix.
- [/] **Academic Writing (Scientific Skill Integration)**:
  - [x] Stage 1: Outline Refinement (Professional Narrative).
  - [x] Stage 2: Paragraph Development (Transition sentences, active voice).
  - [x] Methods: Explicit Reproducibility/Traceability sections. (Added 'Core Persistence')
  - [x] References: Citation integration (BibTeX & In-text).
  - [x] **Memory Chapter**: Rewrote Section 2.4 with rigorous citations (Park, Baddeley, Tulving).
  - [x] **Reference Analysis**: Created `ref/paper_analysis/literature_review_summary.md` and organized `ref` folder.
  - [x] Literature Search: Factuality vs Faithfulness Hallucinations (Gao et al., 2024).
  - [x] Abstract: Drafted.
  - [x] Case Study: Condensed to "Illustrative Application" with "Phantom Elevation" validation story.
- [ ] **Step 5: Paper Analysis & Automation (Reviewer Feedback)**
  - [x] **Analysis 5.1: Stochastic Instability Quantification**
    - [x] Compare Group A, B, C seeds (Variance analysis). (Group C reduces B's instability by ~37%)
    - [x] Calculate Rationality Score (RS) vs. Memory Window size. (Group C: 1.0 vs Group A: N/A)
  - [x] **Analysis 5.2: Memory Mechanism Validation**
    - [x] Extract "Sawtooth Curve" data (Action spike on trauma recall).
    - [x] Verify backstory persistence in Group C. (Confirmed in `simulation_log.csv`)
  - [x] **Visualization 5.3: Figure Generation**
    - [x] Figure 1: Stacking Blocks (Modular Architecture).
    - [x] Figure 2: Inter-run Variance (Stochastic Instability).
    - [x] Figure 3: Single-Agent Sawtooth Persistence.
    - [x] Figure 4: JSON Audit Trace (XAI Snapshot).
  - [x] **Scripting 5.4: Automation**
    - [x] Build `generate_paper_figs.py` for automated plotting.

### 10. Final Submission Packaging (Next Step)

- [ ] **Technical Note Final Polish**:
  - [ ] Review Section 1 (Intro) flow.
  - [ ] Confirm Figure 1-4 rendering.
- [ ] **Artifact Archival**:
  - [ ] Zip `results/JOH_FINAL` for reproducibility.
  - [ ] Clean `examples/single_agent` of temp scripts.

## Phase 5: Post-Submission Optimization (Future v4.0)

- [ ] **Wire-up Reflection Engine**
  - [ ] Integrate `broker/components/reflection_engine.py` into `run_flood.py`.
  - [ ] Call `generate_batch_reflection_prompt` at the end of each simulation year.
  - [ ] Ensure reflections are saved back to `MemoryEngine` as consolidated insights.
- [ ] **Memory Scalability**
  - [ ] Replace List-based storage with Vector Store (FAISS/Chroma).
  - [ ] Implement "Bucketing" for importance-based retrieval to avoid O(N) sort.
- [ ] **Governance State Machine**
  - [ ] Upgrade Validator functions to stateful Classes for global budget tracking.
