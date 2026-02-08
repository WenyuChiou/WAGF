# JOH Supplementary Material (v4)

> **Associated with**: Governance Scaling Laws: Quantifying the Efficiency of Bounded Rationality in LLM-Based Hydro-Social Agents

## S1. Architectural Robustness (Cross-Model Validation)

While the main text focuses on the **Scaling Laws** within the Qwen 2.5 family, we previously conducted extensive validation across diverse model architectures to ensure the **Water Agent Governance Framework** is not overfitting to a specific model family. This section summarizes findings from **Llama 3.2** (Meta) and **Gemma 2** (Google).

### S1.1 The "Brake" vs. "Compass" Effect

Comparing Llama 3.2 (a high-entropy, creative model) with Gemma 2 (a rigid, logical model) revealed that the Governance Framework adapts its role dynamically:

- **For Llama 3.2 (The "Brake" Effect)**:
  - **Baseline Behavior**: Llama exhibited "Panic Loops" in Group A, with a relocation rate exceeding 80% upon the first flood signal.
  - **Governance Intervention**: The framework acted primarily as a **Constraint**, actively blocking invalid moves (`blocks > 140`).
  - **Result**: It successfully suppressed panic, stabilizing the system.

- **For Gemma 2 (The "Compass" Effect)**:
  - **Baseline Behavior**: Gemma exhibited "Inertia," refusing to move even when risks were critical (`Action Rate < 10%`).
  - **Governance Intervention**: The framework acted as an **Enabler**, guiding the model through the PMT logic steps to realize that "Relocation" was the rational choice.
  - **Result**: It successfully activated protection, overcoming inertia.

This cross-model validation confirms that the framework is **Architecure-Agnostic**, functioning as a universal cognitive stabilizer regardless of the underlying model's bias.

---

## S2. Detailed Experimental Configuration

### S2.1 Language Model Backbones

The specific versions validated for Scaling Laws were:

- **Tier 1 (Tiny)**: Qwen2.5-1.5B (`qwen2.5:1.5b`)
- **Tier 2 (Small)**: Qwen2.5-3B (`qwen2.5:3b`)
- **Tier 3 (Base)**: Qwen2.5-7B (`qwen2.5:7b`)
- **Tier 4 (Mid)**: Qwen2.5-14B (`qwen2.5:14b`)
- **Tier 5 (Large)**: Qwen2.5-32B (`qwen2.5:32b`)

All models were quantized to 4-bit (GGUF k4_m) for consistent memory footprint comparison.

## S3. Stress Test Protocols ("Stress Marathon")

To test the limits of the framework ("Adversarial Governance"), we deployed four personas:

1.  **"The Panic Machine"**: High anxiety, low flood threshold (0.1m).
2.  **"The Optimistic Veteran"**: High confidence, high flood threshold (0.8m).
3.  **"The Memory Goldfish"**: Window Size = 2.
4.  **"The Format Breaker"**: Explicitly instructed to output non-JSON text.

Results from these stress tests are detailed in the main text's "Robustness" section.
