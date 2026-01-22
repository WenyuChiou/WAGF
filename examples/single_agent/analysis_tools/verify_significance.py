
import math

# Data from Analysis
# Llama 3.2 Group B: 49 Mismatches, Gap Rate 1.2744%
# Llama 3.2 Group C: 9 Mismatches, Gap Rate 0.3555%

# Calculate Totals
# GapRate = Mismatches / Total * 100 => Total = Mismatches / GapRate * 100
total_b = int(49 / 1.2744 * 100)
total_c = int(9 / 0.3555 * 100)

print(f"Estimated N (Group B): {total_b}")
print(f"Estimated N (Group C): {total_c}")

# Contingency Table
#         | Gap | No Gap
# Group B | 49  | Tb - 49
# Group C | 9   | Tc - 9

obs_b_gap = 49
obs_b_ok = total_b - 49
obs_c_gap = 9
obs_c_ok = total_c - 9

total_gap = obs_b_gap + obs_c_gap
total_ok = obs_b_ok + obs_c_ok
grand_total = total_b + total_c

# Expected Values
exp_b_gap = (total_b * total_gap) / grand_total
exp_b_ok = (total_b * total_ok) / grand_total
exp_c_gap = (total_c * total_gap) / grand_total
exp_c_ok = (total_c * total_ok) / grand_total

print(f"\nObserved: B=[{obs_b_gap}, {obs_b_ok}], C=[{obs_c_gap}, {obs_c_ok}]")
print(f"Expected: B=[{exp_b_gap:.2f}, {exp_b_ok:.2f}], C=[{exp_c_gap:.2f}, {exp_c_ok:.2f}]")

# Chi-Square Calculation
# X^2 = sum( (O - E)^2 / E )
chi2 = 0
for o, e in [
    (obs_b_gap, exp_b_gap), (obs_b_ok, exp_b_ok),
    (obs_c_gap, exp_c_gap), (obs_c_ok, exp_c_ok)
]:
    chi2 += ((o - e) ** 2) / e

print(f"\nChi-Squared Statistic: {chi2:.4f}")

# Critical Value approximation for df=1, p=0.05 is 3.841
# p=0.01 is 6.635
if chi2 > 6.635:
    print("Result: Significant at p < 0.01 (Very Strong Evidence)")
elif chi2 > 3.841:
    print("Result: Significant at p < 0.05 (Strong Evidence)")
else:
    print("Result: Not Significant (Null Hypothesis not rejected)")

# Effect Size (Phi Coefficient)
phi = math.sqrt(chi2 / grand_total)
print(f"Effect Size (Phi): {phi:.4f}")
