# Computational Explanation: The Entropy Divergence (Year 1)

_Why does adding rules mathematically increase $H$ before any learning happens?_

## 1. The Input Vector ($X$)

The Large Language Model (LLM) is a function $f(X) \rightarrow P(Y)$.

- **Group A Input ($X_A$):** `[System: You are an agent.] [User: Flood Level is High.]`
- **Group B Input ($X_B$):** `[System: You are an agent. RULES: Do not relocate unless necessary. Check conditions.] [User: Flood Level is High.]`

## 2. The Logit Distribution ($Z$)

The model produces unnormalized scores (logits) for next tokens (Actions).

- **In Group A:** The token "Flood" strongly attends to the token "Relocate" (Training Bias).
  - $Z_{Relocate} \gg Z_{Others}$ (A "Spiky" distribution).
- **In Group B:** The token "Flood" attends to "Relocate", BUT the token "RULES" attends to "Check/Wait".
  - This **Attention Conflict** suppresses the magnitude of $Z_{Relocate}$.
  - $Z_{Relocate} \approx Z_{Insurance} \approx Z_{Elevation}$ (A "Flatter" distribution).

## 3. The Softmax & Entropy ($H$)

We convert Logits to Probabilities: $P_i = \frac{e^{Z_i}}{\sum e^{Z_j}}$.

- **Group A (Spiky Logits):**
  - $P(Relocate) = 0.8$, $P(Others) = 0.05$
  - $H = -\sum p \log p \approx 1.85$ (Low Diversity)

- **Group B (Flat Logits):**
  - $P(Relocate) = 0.4$, $P(Insurance) = 0.3$, $P(Elevate) = 0.3$
  - $H = - (0.4\log0.4 + 0.3\log0.3 + 0.3\log0.3) \approx 2.09$ (High Diversity)

## Conclusion

From a computational perspective, **Governance acts as a Regularizer**.
It penalizes the model's over-confidence in a single "Panic Path" by introducing competing attention heads (Rules), thereby flattening the output probability distribution and increasing Shannon Entropy.
