# Cross-Cutting Findings

## 1. Does Full-vs-Flat effect depend on memory policy?
Only CLEAN has both institutional conditions, so the observed Full-vs-Flat delta is identified only inside CLEAN. Pooled CLEAN Full MG-Owner insurance share is 0.323 versus 0.296 in CLEAN Flat, but there is no LEGACY Flat arm to test the same contrast under ratchet-enabled memory. The current design therefore supports a within-CLEAN institutional comparison, not a full 2x2 moderation claim.

## 2. Does memory policy moderate the MG-Owner trap?
LEGACY_Full_42 has MG-Owner do-nothing at 0.602 with Y13 insurance at 0.390. CLEAN Full shifts that to do-nothing 0.675 and Y13 insurance 0.290; CLEAN Flat reaches do-nothing 0.703 and Y13 insurance 0.257. The memory shift from LEGACY to CLEAN is larger than the institutional shift from Full to Flat inside CLEAN.

## 3. Does past_reference phrase frequency depend on institutional policy?
Inside CLEAN, owner past-reference rates average 0.018 in Full and 0.018 in Flat; renter rates are 0.068 and 0.066. Both are far below LEGACY_Full_42, where owner and renter rates average 0.202 and 0.292. That points to memory policy, not institutional policy, as the main driver of ratchet phrases.

## 4. Is the action space collapse under CLEAN worse under Flat?
Across the two renter cells, relocation averages 0.000 in CLEAN Full and 0.001 in CLEAN Flat, versus 0.010 in LEGACY Full. Flat slightly increases renter exit pressure, but both CLEAN conditions remain much more compressed than LEGACY on overall action diversity.

## 5. Does insurance_rate_sfha drift toward or away from the empirical range when institutional dynamics are removed?
CLEAN Full averages insurance_rate_sfha 0.829; CLEAN Flat averages 0.787. The empirical band is [0.30, 0.60], so both remain too high, but Flat moves closer to the upper bound than Full.

## 6. Cross-seed variance on MG-Owner metrics: is it bigger than the Full-vs-Flat effect?
The pooled Full-vs-Flat delta in MG-Owner do-nothing is 0.027. The within-condition seed SD is 0.005 for CLEAN Full and 0.015 for CLEAN Flat. The institutional effect is directionally larger than Full-condition seed noise, but not cleanly separated from all seed spread, so it should be reported with SE rather than as a deterministic shift.