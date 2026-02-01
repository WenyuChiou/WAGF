# Post-Hoc Validation Module (事後驗證模組)

> **適用範圍**: 此模組是**論文級分析工具**，不屬於通用框架。它專為 WRR 技術報告中的
> **洪水領域（PMT: TP/CP）** 實驗設計。灌溉領域分析（WSA/ACA）需要定製分類器。

> **用途**: 運行時驗證器在模擬過程中即時攔截幻覺。事後驗證器在模擬完成*後*對幻覺
> 進行分類與量化，使跨組比較成為可能。這對 Group A（基線）尤為重要，因為它沒有
> 運行時治理——其幻覺率只能通過回溯分析來測量。

Source: `broker/validators/posthoc/`

```
broker/validators/posthoc/
├── keyword_classifier.py       # Two-tier PMT keyword extraction (flood domain only)
├── thinking_rule_posthoc.py    # V1/V2/V3 verification rules (flood PMT checks)
└── unified_rh.py               # Cross-group R_H and EBE computation
```

---

## KeywordClassifier (關鍵詞分類器)

Extracts PMT construct labels (TP, CP) from unstructured free-text appraisals using a two-tier strategy:

- **Tier 1** — Explicit label regex: Matches `VH`, `H`, `M`, `L`, `VL` tokens directly (catches structured output from Groups B/C).
- **Tier 2** — PMT keyword matching: Curated dictionaries from literature (Rogers, 1975; Maddux & Rogers, 1983). Maps fear-arousal keywords ("severe", "catastrophic", "afraid") to High threat; resilience keywords ("safe", "protected", "minimal") to Low threat.

```python
from broker.validators.posthoc import KeywordClassifier

classifier = KeywordClassifier()
tp_level = classifier.classify_threat("I am very worried about the severe flooding")
# → "H"
cp_level = classifier.classify_coping("The grant makes elevation affordable")
# → "H"
```

**Domain Mapping**:
- **Flood (PMT)**: Default keyword dictionaries target TP (Threat Perception) / CP (Coping Perception)
- **Irrigation (WSA/ACA)**: Supply custom `ta_keywords` and `ca_keywords` via constructor, or use Tier 1 only (explicit label regex, domain-agnostic)

---

## ThinkingRulePostHoc (事後思維規則驗證)

Applies the same verification logic as the runtime `ThinkingValidator`, but on already-classified trace DataFrames. Three rules (V1/V2/V3) mirror the runtime PMT checks:

| Rule ID | Description | Condition |
| :--- | :--- | :--- |
| **V1** `relocation_threat_low` | Relocated under low threat perception | `relocated` transition + TP in {L, VL} |
| **V2** `elevation_threat_low` | Elevated under low threat perception | `elevated` transition + TP in {L, VL} |
| **V3** `extreme_threat_block` | Inaction under extreme threat | `do_nothing` + TP = VH |

Group A uses a relaxed threshold (`{L, VL, M}`) because keyword-inferred labels carry lower confidence than structured labels from Groups B/C.

---

## Unified R_H Computation (統一幻覺率計算)

The `compute_hallucination_rate()` function provides the single entry point for computing the hallucination rate with consistent methodology:

$$R_H = \frac{N_{\text{physical}} + N_{\text{thinking}}}{N_{\text{active}}}$$

$$\text{EBE} = H_{\text{norm}} \times (1 - R_H)$$

Where:
- $N_{\text{physical}}$: Re-elevation + post-relocation actions (from state transitions)
- $N_{\text{thinking}}$: V1 + V2 + V3 violations (from classified constructs)
- $N_{\text{active}}$: Agent-year pairs where the agent has not yet relocated
- $H_{\text{norm}}$: Normalized Shannon entropy of action distribution ($H / \log_2 4$)
- $\text{EBE}$: Effective Behavioral Entropy — a composite metric capturing both decision diversity and logical consistency

```python
from broker.validators.posthoc import compute_hallucination_rate

metrics = compute_hallucination_rate(df, group="C", ta_col="threat_appraisal")
print(f"R_H = {metrics['rh']:.3f}, EBE = {metrics['ebe']:.3f}")
# → R_H = 0.012, EBE = 0.847
```

### Cross-Group Methodology

```
Group A:  free text → keyword classifier → TP_inferred/CP_inferred → V1/V2/V3 → R_H
Group B/C: structured labels → TP_LABEL/CP_LABEL → ThinkingValidator → R_H
```

Same formula, different label source. The paper should clearly state this methodological distinction.
