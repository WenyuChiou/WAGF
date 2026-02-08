# How to Assemble an Agent: The "Stacking Blocks" Guide

**🌐 Language: [English](agent_assembly.md) | [中文](agent_assembly_zh.md)**

The Water Agent Governance Framework treats cognitive capabilities as modular "blocks." This guide explains how to toggle these features to create agents of varying intelligence and governance levels, primarily for ablation studies.

## 🧱 The Building Blocks

You enable or disable these blocks using command-line arguments in `run_flood.py`.

### 1. The Body (Execution Engine)

_Always On._
This is the base capability to interact with the world (e.g., `do_nothing`). Without other blocks, the agent is a random walker or purely reactive.

### 2. The Eyes (Context Lens)

_Command Flag:_ `--memory-engine window`
_Function:_ Filters history to a strict window (e.g., last 5 events).
_Effect:_ Prevents context overflow errors but causes "Goldfish Amnesia" (forgetting past disasters).

### 3. The Hippo (Memory Engine)

_Command Flag:_ `--memory-engine humancentric`
_Function:_ Enables **Tiered Memory** (Window + Salience + Long-Term).
_Effect:_ Allows the agent to prioritize high-impact memories (like floods) even if they happened years ago, solving the amnesia problem.

### 4. The Superego (Skill Broker)

_Command Flag:_ `--governance-mode strict`
_Function:_ Enforces "Thinking Rules." Validates that the agent's Thought Process (TP) matches its Action.
_Effect:_ Prevents "Hallucination" (illegal moves) and "Logical Drift" (saying one thing, doing another).

---

## 🏗️ Common Assemblages (Benchmarks)

### Type A: The "Naive" Agent (Baseline)

A standard LLM agent with no governance or special memory.

```bash
python run_flood.py --memory-engine window --governance-mode monitor
```

**Behavior**: Highly erratic. Often forgets insurance after a few years.

### Type B: The "Governed" Agent

Corrects logical errors but still suffers from memory loss.

```bash
python run_flood.py --memory-engine window --governance-mode strict
```

**Behavior**: Decisions are legal, but short-sighted.

### Type C: The "Rational" Agent (Full Stack)

The complete cognitive architecture.

```bash
python run_flood.py --memory-engine humancentric --governance-mode strict
```

**Behavior**: Shows long-term adaptation traits (e.g., maintaining insurance for decades).
