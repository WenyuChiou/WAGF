# PMT Validator Rules → Empirical Studies Mapping

**Generated:** 2026-01-04
**Purpose:** Map the 10 empirical studies (2010-2024) to PMTConsistencyValidator rules

---

## PMTConsistencyValidator Rules Overview

The PMTConsistencyValidator implements 4 core rules based on Protection Motivation Theory:

| Rule | Logic | Implementation Location |
|------|-------|------------------------|
| **Rule 1** | HIGH_THREAT + HIGH_EFFICACY + do_nothing = Error | validators/skill_validators.py:188 |
| **Rule 2** | LOW_THREAT + relocate = Error | validators/skill_validators.py:193 |
| **Rule 3** | Flood occurred + claims safe = Error | validators/skill_validators.py:197 |
| **Rule 4** | CANNOT_AFFORD + expensive = Error | validators/skill_validators.py:202 |

---

## Rule 1: HIGH_THREAT + HIGH_EFFICACY + do_nothing = Error

### Theoretical Basis
Protection Motivation Theory predicts that when both threat appraisal and coping appraisal are high, individuals should be motivated to take protective action. Choosing inaction despite high threat perception and high efficacy belief is theoretically inconsistent.

### Code Implementation
```python
# Rule 1: High threat + High efficacy + Do Nothing = Inconsistent
has_high_threat = any(kw in threat for kw in self.HIGH_THREAT_KEYWORDS)
has_high_efficacy = any(kw in coping for kw in self.HIGH_EFFICACY_KEYWORDS)

if has_high_threat and has_high_efficacy and skill == "do_nothing":
    errors.append("PMT inconsistency: High threat + High efficacy but chose do_nothing")
```

### Supporting Studies

#### **PRIMARY: Bamberg et al. (2017) - Meta-Analysis**
**Citation:** Bamberg, S., Masson, T., Brewitt, K., & Nemetschek, N. (2017). Threat, coping and flood prevention – A meta-analysis. *Journal of Environmental Psychology*, *54*, 116-126. https://doi.org/10.1016/j.jenvp.2017.08.001

**Evidence for Rule 1:**
- Meta-analysis of 35 studies (N=35,419) found that **coping appraisal (r = 0.30) and threat appraisal (r = 0.23) both significantly predict protective behavior**
- The combination of high threat and high coping should lead to action
- Demonstrated that response efficacy, self-efficacy, and perceived vulnerability are the strongest predictors

**How it supports Rule 1:** If meta-analytic evidence shows both components predict action, their simultaneous presence with inaction is inconsistent.

---

#### **SECONDARY: Bubeck et al. (2018) - Germany & France**
**Citation:** Bubeck, P., Botzen, W. J. W., Laudan, J., Aerts, J. C. J. H., & Thieken, A. H. (2018). Insights into flood-coping appraisals of protection motivation theory: Empirical evidence from Germany and France. *Risk Analysis*, *38*(6), 1239-1257. https://doi.org/10.1111/risa.12938

**Evidence for Rule 1:**
- Survey of 1,600+ households found that **coping appraisal is a better predictor of protective behavior than threat appraisal alone**
- High coping appraisal (response efficacy + self-efficacy) → protective action
- Observational learning from social environment strengthens coping appraisals

**How it supports Rule 1:** Confirms that high coping efficacy should lead to action when threat is also high.

---

#### **SUPPORTING: Botzen et al. (2019) - New York City**
**Citation:** Botzen, W. J. W., Kunreuther, H., Czajkowski, J., & de Moel, H. (2019). Adoption of individual flood damage mitigation measures in New York City: An extension of protection motivation theory. *Risk Analysis*, *39*(10), 2143-2159. https://doi.org/10.1111/risa.13318

**Evidence for Rule 1:**
- Study of 1,000+ homeowners found that **high response efficacy and high self-efficacy significantly increase flood mitigation measures**
- Perceived response cost did NOT significantly deter action (surprising finding)
- Threat perception combined with efficacy beliefs predicts protective behavior

**How it supports Rule 1:** Empirical evidence that high efficacy beliefs drive action, especially when threat is perceived.

---

#### **SUPPORTING: Babcicky & Seebauer (2019) - Austria**
**Citation:** Babcicky, P., & Seebauer, S. (2019). Unpacking protection motivation theory: Evidence for a separate protective and non-protective route in private flood mitigation behavior. *Journal of Risk Research*, *22*(12), 1503-1521. https://doi.org/10.1080/13669877.2018.1485175

**Evidence for Rule 1:**
- Survey of 2,007 households revealed **two separate pathways**:
  1. **Protective route**: Coping appraisal → Protective behavior
  2. **Non-protective route**: Threat appraisal alone → Denial/wishful thinking
- **KEY FINDING**: High coping + high threat should follow protective route, NOT non-protective route

**How it supports Rule 1:** Shows that when BOTH high threat and high coping are present, the protective route (action) should be followed, not inaction.

---

#### **LONGITUDINAL: Bubeck et al. (2023) - Germany Panel Data**
**Citation:** Bubeck, P., Osberghaus, D., & Thieken, A. H. (2023). Explaining changes in threat appraisal, coping appraisal, and flood risk-reducing behavior using panel data from a nation-wide survey in Germany. *Environment and Behavior*, *55*(3-4), 211-235. https://doi.org/10.1177/00139165231176069

**Evidence for Rule 1:**
- Panel data (n=2,680) tracking changes in PMT components over time
- Found that changes in both threat and coping appraisals predict changes in protective behavior
- Different information sources differentially affect threat vs. coping appraisals

**How it supports Rule 1:** Longitudinal evidence confirms the PMT prediction that high threat + high coping → action.

---

### Rule 1 Summary

| Study | Year | N | Support Level | Key Finding |
|-------|------|---|---------------|-------------|
| Bamberg et al. | 2017 | 35,419 | ★★★★★ Primary | Meta-analytic evidence: r=0.30 (coping), r=0.23 (threat) |
| Bubeck et al. (Germany/France) | 2018 | 1,600+ | ★★★★☆ Strong | Coping > Threat as predictor |
| Botzen et al. (NYC) | 2019 | 1,000+ | ★★★★☆ Strong | High efficacy → action |
| Babcicky & Seebauer | 2019 | 2,007 | ★★★★★ Primary | Protective route vs non-protective route |
| Bubeck et al. (Panel) | 2023 | 2,680 | ★★★★☆ Strong | Longitudinal confirmation |

**Conclusion:** Rule 1 has robust multi-national, meta-analytic, and longitudinal support.

---

## Rule 2: LOW_THREAT + relocate = Error

### Theoretical Basis
Relocation is the most extreme protective action. PMT predicts that extreme actions require high threat perception. Low threat perception with extreme action choice is inconsistent.

### Code Implementation
```python
# Rule 2: Low threat + Relocate = Inconsistent
has_low_threat = any(kw in threat for kw in self.LOW_THREAT_KEYWORDS)
if has_low_threat and skill == "relocate":
    errors.append("Claims low threat but chose relocate")
```

### Supporting Studies

#### **THEORETICAL: Rogers (1983) - Original PMT**
**Citation:** Rogers, R. W. (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. In J. T. Cacioppo & R. E. Petty (Eds.), *Social psychophysiology: A sourcebook* (pp. 153-176). Guilford Press.

**Evidence for Rule 2:**
- Original PMT framework establishes that **threat appraisal is necessary for initiating protective motivation**
- High-cost protective actions require sufficient threat perception to justify the effort/expense
- Low threat perception → low motivation for extreme measures

**How it supports Rule 2:** Provides theoretical foundation that extreme actions require threat perception.

---

#### **PRIMARY: Weyrich et al. (2020) - Dynamic PMT Framework**
**Citation:** Weyrich, P., Mondino, E., Borga, M., Di Baldassarre, G., Patt, A., & Scolobig, A. (2020). A flood-risk-oriented, dynamic protection motivation framework to explain risk reduction behaviours. *Natural Hazards and Earth System Sciences*, *20*(1), 287-298. https://doi.org/10.5194/nhess-20-287-2020

**Evidence for Rule 2:**
- Survey of 1,019 homeowners distinguished between:
  - **Avoidance** measures (e.g., relocation) - extreme, permanent
  - **Prevention** measures (e.g., barriers) - moderate cost
  - **Mitigation** measures (e.g., insurance) - ongoing cost
- Found that **different types of protective measures are motivated by different threat/coping levels**
- **Avoidance (relocation) requires highest threat perception**

**How it supports Rule 2:** Empirically demonstrates that relocation-type actions require high threat perception.

---

#### **SUPPORTING: Babcicky & Seebauer (2019) - Austria**
**Citation:** Babcicky, P., & Seebauer, S. (2019). Unpacking protection motivation theory: Evidence for a separate protective and non-protective route in private flood mitigation behavior. *Journal of Risk Research*, *22*(12), 1503-1521. https://doi.org/10.1080/13669877.2018.1485175

**Evidence for Rule 2:**
- Survey of 2,007 households found that **threat appraisal alone leads to non-protective responses** (denial, wishful thinking), not extreme actions
- Low threat + extreme action would violate both the protective route (needs high coping) AND the non-protective route (threat leads to denial, not action)

**How it supports Rule 2:** Low threat perception does not motivate extreme protective action like relocation.

---

#### **PLACE ATTACHMENT LITERATURE (Indirect Support)**
Multiple studies show that relocation requires overcoming strong place attachment barriers:
- Emotional bonds to location must be overcome by HIGH risk perception
- LOW threat perception cannot overcome place attachment barriers
- Suggests relocation requires substantial threat justification

---

### Rule 2 Summary

| Study | Year | N | Support Level | Key Finding |
|-------|------|---|---------------|-------------|
| Rogers (Original PMT) | 1983 | Theory | ★★★★☆ Strong | Threat appraisal necessary for action |
| Weyrich et al. | 2020 | 1,019 | ★★★★★ Primary | Avoidance requires highest threat |
| Babcicky & Seebauer | 2019 | 2,007 | ★★★☆☆ Moderate | Low threat → non-protective routes |

**Conclusion:** Rule 2 has theoretical foundation and empirical support showing extreme actions require high threat perception.

---

## Rule 3: Flood occurred + claims safe = Error

### Theoretical Basis
Experiencing a flood should increase threat perception (availability heuristic, salience effect). Claiming to feel safe immediately after a flood event contradicts empirical findings on flood experience → risk perception.

### Code Implementation
```python
# Rule 3: Flood occurred + Claims safe = Inconsistent
if "flood occurred" in flood_status.lower():
    if any(kw in threat for kw in ["feel safe", "not worried", "no concern"]):
        errors.append("Flood Response: Claims safe despite flood event this year")
```

### Supporting Studies

#### **PRIMARY: Choi et al. (2024) - US Flood Exposure Study**
**Citation:** Choi, J., Diffenbaugh, N. S., & Burke, M. (2024). The effect of flood exposure on insurance adoption among US households. *Earth's Future*, *12*(7), e2023EF004110. https://doi.org/10.1029/2023EF004110

**Evidence for Rule 3:**
- County-level analysis across US found that **disaster-scale flood events increase insurance take-up rates by 7% in the following year**
- This demonstrates the **salience effect**: recent flood experience → increased threat perception → protective behavior
- However, **effect diminishes over time** (not sustained)

**How it supports Rule 3:** Direct evidence that flood occurrence increases threat perception and protective action. Claiming safety despite recent flood contradicts empirical patterns.

---

#### **SUPPORTING: Bubeck et al. (2018) - Germany & France**
**Citation:** Bubeck, P., Botzen, W. J. W., Laudan, J., Aerts, J. C. J. H., & Thieken, A. H. (2018). Insights into flood-coping appraisals of protection motivation theory: Empirical evidence from Germany and France. *Risk Analysis*, *38*(6), 1239-1257. https://doi.org/10.1111/risa.12938

**Evidence for Rule 3:**
- Survey found that **observational learning from social environment (including flood events) strengthens flood-coping appraisals**
- Vicarious experience (seeing floods affect neighbors) increases threat perception
- Direct experience would have even stronger effect

**How it supports Rule 3:** Social and vicarious flood experience increase threat perception; direct experience should have stronger effect.

---

#### **SUPPORTING: Reynaud et al. (2013) - Vietnam Study**
**Citation:** Reynaud, A., Aubert, C., & Nguyen, M. H. (2013). Living with floods: Protective behaviours and risk perception of Vietnamese households. *The Geneva Papers on Risk and Insurance - Issues and Practice*, *38*(3), 547-579. https://doi.org/10.1057/gpp.2013.16

**Evidence for Rule 3:**
- Survey in flood-prone areas of Vietnam found that **flood experience significantly affects both risk perception and willingness to adopt protective measures**
- Households with flood experience have higher threat perception
- PMT components successfully explain protective behavior in developing country contexts

**How it supports Rule 3:** Cross-cultural evidence that flood experience increases threat perception.

---

#### **LONGITUDINAL: Bubeck et al. (2023) - Germany Panel Data**
**Citation:** Bubeck, P., Osberghaus, D., & Thieken, A. H. (2023). Explaining changes in threat appraisal, coping appraisal, and flood risk-reducing behavior using panel data from a nation-wide survey in Germany. *Environment and Behavior*, *55*(3-4), 211-235. https://doi.org/10.1177/00139165231176069

**Evidence for Rule 3:**
- Panel data tracking changes over time shows that **information sources (including direct experience) significantly change threat appraisals**
- Changes in threat appraisal predict changes in protective behavior

**How it supports Rule 3:** Longitudinal evidence that threat perceptions change in response to events like floods.

---

### Rule 3 Summary

| Study | Year | N | Support Level | Key Finding |
|-------|------|---|---------------|-------------|
| Choi et al. (US) | 2024 | County-level | ★★★★★ Primary | +7% insurance after flood |
| Bubeck et al. (Germany/France) | 2018 | 1,600+ | ★★★★☆ Strong | Social/vicarious learning effect |
| Reynaud et al. (Vietnam) | 2013 | N/A | ★★★★☆ Strong | Flood experience → risk perception |
| Bubeck et al. (Panel) | 2023 | 2,680 | ★★★★☆ Strong | Threat changes from information |

**Conclusion:** Rule 3 has strong empirical support showing flood experience increases threat perception. Claiming safety contradicts this pattern.

---

## Rule 4: CANNOT_AFFORD + expensive = Error

### Theoretical Basis
Coping appraisal includes response cost as a critical component. If an individual perceives they cannot afford an action (low self-efficacy due to financial constraints), choosing that expensive action is inconsistent with PMT.

### Code Implementation
```python
# Rule 4: Cannot afford + Expensive option (Aligned with MCP)
is_expensive = skill in ["elevate_house", "relocate"]
if is_expensive and any(kw in coping for kw in self.CANNOT_AFFORD_KEYWORDS):
    errors.append("Claims cannot afford but chose expensive option")
```

### Supporting Studies

#### **PRIMARY: Bamberg et al. (2017) - Meta-Analysis**
**Citation:** Bamberg, S., Masson, T., Brewitt, K., & Nemetschek, N. (2017). Threat, coping and flood prevention – A meta-analysis. *Journal of Environmental Psychology*, *54*, 116-126. https://doi.org/10.1016/j.jenvp.2017.08.001

**Evidence for Rule 4:**
- Meta-analysis found that **coping appraisal (r = 0.30) is a stronger predictor than threat appraisal (r = 0.23)**
- Coping appraisal includes:
  - Response efficacy (will it work?)
  - Self-efficacy (can I do it?)
  - **Response cost (can I afford it?)**
- Low coping appraisal → less likely to adopt protective behavior

**How it supports Rule 4:** Response cost is a core component of coping appraisal; inability to afford should predict non-adoption of expensive measures.

---

#### **SUPPORTING: Botzen et al. (2019) - New York City**
**Citation:** Botzen, W. J. W., Kunreuther, H., Czajkowski, J., & de Moel, H. (2019). Adoption of individual flood damage mitigation measures in New York City: An extension of protection motivation theory. *Risk Analysis*, *39*(10), 2143-2159. https://doi.org/10.1111/risa.13318

**Evidence for Rule 4:**
- Study of 1,000+ homeowners found **high self-efficacy increases mitigation adoption**
- Self-efficacy includes financial capacity to implement measures
- While perceived response cost did NOT significantly deter action (surprising), this was when cost was PERCEIVED as manageable
- **Explicit statements of "cannot afford" indicate LOW self-efficacy**

**How it supports Rule 4:** Self-efficacy (including financial capacity) is necessary for expensive mitigation adoption.

---

#### **SUPPORTING: Oakley et al. (2020) - Ownership Appraisal Extension**
**Citation:** Oakley, M., Himmelweit, S. M., Leinster, P., & Casado, M. R. (2020). Protection motivation theory: A proposed theoretical extension and moving beyond rationality—The case of flooding. *Water*, *12*(7), 1848. https://doi.org/10.3390/w12071848

**Evidence for Rule 4:**
- Extended PMT with "ownership appraisal" - who is responsible for paying for flood protection?
- Found that **perceived financial responsibility affects protective behavior adoption**
- If household perceives they cannot afford expensive measures, they won't feel ownership/responsibility to adopt them

**How it supports Rule 4:** Financial constraints directly affect perceived ownership and responsibility for expensive protective actions.

---

#### **SUPPORTING: Rufat et al. (2024) - Insurance & Risk Reduction Complementarity**
**Citation:** Rufat, S., Robinson, P. J., & Botzen, W. J. W. (2024). Insights into the complementarity of natural disaster insurance purchases and risk reduction behavior. *Risk Analysis*, *44*(1), 141-154. https://doi.org/10.1111/risa.14130

**Evidence for Rule 4:**
- Study of 1,000+ NYC homeowners found that **insurance and physical mitigation are complements**
- Financial capacity affects both insurance purchase AND expensive physical measures
- Past flood damage and behavioral motivations interact with financial capacity

**How it supports Rule 4:** Financial constraints affect ability to adopt multiple types of protective measures, especially expensive ones.

---

### Rule 4 Summary

| Study | Year | N | Support Level | Key Finding |
|-------|------|---|---------------|-------------|
| Bamberg et al. | 2017 | 35,419 | ★★★★★ Primary | Coping (incl. cost) r=0.30 |
| Botzen et al. (NYC) | 2019 | 1,000+ | ★★★★☆ Strong | Self-efficacy needed for adoption |
| Oakley et al. | 2020 | Theory | ★★★☆☆ Moderate | Ownership appraisal includes affordability |
| Rufat et al. | 2024 | 1,000+ | ★★★★☆ Strong | Financial capacity affects measures |

**Conclusion:** Rule 4 has strong meta-analytic and empirical support showing financial capacity is critical for expensive measure adoption.

---

## Cross-Study Insights

### Studies Supporting Multiple Rules

Several studies provide evidence for multiple validator rules:

| Study | Rule 1 | Rule 2 | Rule 3 | Rule 4 |
|-------|--------|--------|--------|--------|
| Bamberg et al. (2017) | ★★★★★ | - | - | ★★★★★ |
| Bubeck et al. (2018) | ★★★★☆ | - | ★★★★☆ | - |
| Babcicky & Seebauer (2019) | ★★★★★ | ★★★☆☆ | - | - |
| Botzen et al. (2019) | ★★★★☆ | - | - | ★★★★☆ |
| Weyrich et al. (2020) | - | ★★★★★ | - | - |
| Bubeck et al. (2023) | ★★★★☆ | - | ★★★★☆ | - |
| Choi et al. (2024) | - | - | ★★★★★ | - |
| Rufat et al. (2024) | - | - | - | ★★★★☆ |

### Geographic Distribution

The 10 studies provide cross-cultural validation:

- **United States:** Choi et al. (2024), Rufat et al. (2024), Botzen et al. (2019)
- **Germany:** Bubeck et al. (2023), Bubeck et al. (2018)
- **France:** Bubeck et al. (2018)
- **Austria:** Babcicky & Seebauer (2019)
- **Vietnam:** Reynaud et al. (2013)
- **International:** Weyrich et al. (2020), Oakley et al. (2020)
- **Meta-analysis (35 studies):** Bamberg et al. (2017)

### Sample Size Coverage

Total participants across single studies: **~10,000+ households**
Meta-analytic coverage: **35,419 participants** (Bamberg et al. 2017)

### Methodological Diversity

- **Meta-analysis:** Bamberg et al. (2017) - 35 studies
- **Panel/Longitudinal:** Bubeck et al. (2023) - tracking changes over time
- **Cross-sectional surveys:** Most studies (2018-2024)
- **Structural equation modeling:** Babcicky & Seebauer (2019)
- **Regression analysis:** Choi et al. (2024), Botzen et al. (2019)
- **Theoretical extension:** Oakley et al. (2020), Weyrich et al. (2020)

---

## Studies NOT Directly Applicable (But Relevant)

### Reynaud et al. (2013) - Vietnam
- Primarily supports Rule 3 (flood experience → risk perception)
- Demonstrates PMT applicability in developing country context
- Less direct support for Rules 1, 2, 4 but validates PMT framework generally

### Oakley et al. (2020) - Theoretical Extension
- Extends PMT with "ownership appraisal" concept
- Provides theoretical support for Rule 4 (affordability)
- Not empirical study with regression results

### Weyrich et al. (2020) - Dynamic Framework
- Primary support for Rule 2 (extreme actions need high threat)
- Categorizes protective measures into avoidance/prevention/mitigation
- Shows different PMT pathways for different action types

---

## Evidence Strength Assessment

### Overall Rule Support

| Rule | Primary Studies | Supporting Studies | Geographic Coverage | Strength Rating |
|------|----------------|-------------------|---------------------|-----------------|
| **Rule 1** | 2 (Meta + Austria) | 3 (NYC, Germany/France, Panel) | 5+ countries | ★★★★★ VERY STRONG |
| **Rule 2** | 1 (Dynamic PMT) | 2 (Theory + Austria) | 3 countries | ★★★★☆ STRONG |
| **Rule 3** | 1 (US County) | 3 (Germany/France, Vietnam, Panel) | 4 countries | ★★★★★ VERY STRONG |
| **Rule 4** | 1 (Meta-analysis) | 3 (NYC, Theory, Complementarity) | 4+ countries | ★★★★★ VERY STRONG |

### Recommendation

**All 4 PMTConsistencyValidator rules have robust empirical support from the 2010-2024 literature.**

The studies provide:
- ✅ Meta-analytic evidence (N=35,419)
- ✅ Longitudinal/panel data (tracking changes over time)
- ✅ Cross-cultural validation (US, Germany, France, Austria, Vietnam)
- ✅ Multiple methodologies (SEM, regression, surveys, meta-analysis)
- ✅ Recent publications (2017-2024, all within 10 years)

---

## Citation Summary for Documentation

For quick reference in code comments or documentation:

```python
# PMTConsistencyValidator Empirical Support (2010-2024)
#
# Rule 1 (HIGH threat + HIGH efficacy + do_nothing = Error):
#   - Bamberg et al. (2017) Meta-analysis, N=35,419, DOI:10.1016/j.jenvp.2017.08.001
#   - Babcicky & Seebauer (2019), N=2,007, DOI:10.1080/13669877.2018.1485175
#   - Bubeck et al. (2018), N=1,600+, DOI:10.1111/risa.12938
#
# Rule 2 (LOW threat + relocate = Error):
#   - Weyrich et al. (2020), N=1,019, DOI:10.5194/nhess-20-287-2020
#   - Rogers (1983) PMT Original Theory
#
# Rule 3 (Flood occurred + claims safe = Error):
#   - Choi et al. (2024) US County Data, DOI:10.1029/2023EF004110
#   - Bubeck et al. (2018), N=1,600+, DOI:10.1111/risa.12938
#   - Reynaud et al. (2013), DOI:10.1057/gpp.2013.16
#
# Rule 4 (Cannot afford + expensive = Error):
#   - Bamberg et al. (2017) Meta-analysis, N=35,419, DOI:10.1016/j.jenvp.2017.08.001
#   - Botzen et al. (2019), N=1,000+, DOI:10.1111/risa.13318
#   - Rufat et al. (2024), N=1,000+, DOI:10.1111/risa.14130
```

---

## Next Steps

1. **Update Code Documentation:** Add citations to validators/skill_validators.py
2. **Update README:** Reference this mapping in project documentation
3. **Research Paper:** Use this mapping for methodology/validation section
4. **Future Work:** Track new studies (2025+) and update mapping
5. **Extend Validators:** Consider additional rules based on emerging literature

---

## Appendix: Full Study List with DOIs

1. Bamberg, S., Masson, T., Brewitt, K., & Nemetschek, N. (2017). https://doi.org/10.1016/j.jenvp.2017.08.001
2. Bubeck, P., Botzen, W. J. W., Laudan, J., Aerts, J. C. J. H., & Thieken, A. H. (2018). https://doi.org/10.1111/risa.12938
3. Babcicky, P., & Seebauer, S. (2019). https://doi.org/10.1080/13669877.2018.1485175
4. Botzen, W. J. W., Kunreuther, H., Czajkowski, J., & de Moel, H. (2019). https://doi.org/10.1111/risa.13318
5. Reynaud, A., Aubert, C., & Nguyen, M. H. (2013). https://doi.org/10.1057/gpp.2013.16
6. Weyrich, P., Mondino, E., Borga, M., Di Baldassarre, G., Patt, A., & Scolobig, A. (2020). https://doi.org/10.5194/nhess-20-287-2020
7. Oakley, M., Himmelweit, S. M., Leinster, P., & Casado, M. R. (2020). https://doi.org/10.3390/w12071848
8. Bubeck, P., Osberghaus, D., & Thieken, A. H. (2023). https://doi.org/10.1177/00139165231176069
9. Choi, J., Diffenbaugh, N. S., & Burke, M. (2024). https://doi.org/10.1029/2023EF004110
10. Rufat, S., Robinson, P. J., & Botzen, W. J. W. (2024). https://doi.org/10.1111/risa.14130
