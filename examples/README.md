# Benchmarks & Examples

**🌐 Language: [English](README.md) | [中文](README_zh.md)**

This directory contains reproduction scripts and experimental results for the Governed Broker Framework.

## 📂 Directory Structure

| Directory                            | Content                                                                                                                       | Status           |
| :----------------------------------- | :---------------------------------------------------------------------------------------------------------------------------- | :--------------- |
| **[`single_agent/`](single_agent/)** | **Longitudinal Flood Study (JOH Benchmark)**. 100-agent simulations focused on memory retention and adaptation over 10 years. | ✅ **Active**    |
| **[`multi_agent/`](multi_agent/)**   | **Social Dynamics**. Simulations involving peer effects, insurance market interactions, and government subsidies.             | 🚧 _In Progress_ |

## 🚀 How to Run Benchmarks

### Single Agent Benchmark (JOH Paper)

Replicates the "Ablation Study" (Group A vs B vs C).

```bash
# Run the full triple-comparison suite
cd single_agent
./run_joh_triple.ps1 -Model llama3.2:3b -Agents 100 -Years 10
```

### Stress Testing

Run specific stress scenarios (Panic, Amnesia, etc.).

```bash
python single_agent/run_flood.py --stress-test panic --agents 50
```
