# Computational Explanation: The Entropy Calculation Process (SQ2)

_How we mathematically measure the diversity of agentic behavior across groups._

## 1. Data Collection & Normalization

For each model scale and experimental group (A, B, C):

1. **Decision Capture**: We extract raw decision strings from `simulation_log.csv`.
2. **Normalization**: Decisions are mapped into 5 categorical bins:
   - `DN`: Do Nothing
   - `FI`: Flood Insurance
   - `HE`: House Elevation
   - `Both HE + FI`: Combined Mitigation
   - `RL`: Relocate (Departing)

## 2. The Shannon Entropy Formula ($H$)

We calculate the **Shannon Entropy** to quantify the "spread" or "certainty" of agent behavior:

$$H = -\sum_{i=1}^{k} p_i \log_2(p_i)$$

Where:

- $p_i$ is the probability (frequency) of action $i$ in the population.
- $k=5$ (the number of possible actions).

## 3. Normalization ($H_{norm}$)

To ensure the metric is comparable and interpretable (0.0 to 1.0), we normalize by the maximum possible entropy ($\log_2 k$):

$$H_{norm} = \frac{H}{\log_2(5)} \approx \frac{H}{2.3219}$$

- **$H_{norm} \approx 0$**: Collapsed behavior (everyone chooses the same action, e.g., Group A Panic).
- **$H_{norm} \approx 1$**: Uniform distribution (maximum diversity of adaptation paths).

## Conclusion: Governance as a Regularizer

As seen in Year 1 data, **Governance increases $H$** by suppressing the model's training bias towards a single "Panic Path" (Relocation), thereby flattening the probability distribution and preserving agentic plurality.
