# Institutional LLM-Agent Prompt Design: Literature Justification

**Generated**: 2026-03-14
**Purpose**: Verifiable references for reviewer challenges to institutional design elements in the multi-agent flood ABM governance prompts.

---

## 1. CRS as Reward for Achievement, Not Incentive

### Design Element
The FEMA Community Rating System (CRS) awards premium discounts based on earned activity credits across 19 creditable activities. Communities must demonstrate sustained mitigation effort to maintain their class rating. This is modeled in the government agent's prompt as a reward mechanism tied to demonstrated community mitigation progress.

### References

**R1.1. FEMA CRS Coordinator's Manual (2017)**
- **Citation**: Federal Emergency Management Agency. (2017). *National Flood Insurance Program Community Rating System: Coordinator's Manual*. FIA-15/2017. Washington, DC: FEMA.
- **URL**: https://www.fema.gov/sites/default/files/documents/fema_community-rating-system_coordinators-manual_2017.pdf
- **Confidence**: HIGH (official FEMA document, publicly available PDF)
- **Relevance**: The authoritative guide defining all 19 creditable CRS activities, credit point calculations, documentation requirements, and class rating determination. Establishes that CRS is a performance-based system where communities earn credits through verified activities, not merely by enrolling.

**R1.2. FEMA CRS Class Rating Table**
- **Citation**: Federal Emergency Management Agency. (n.d.). *Community Rating System*. FEMA.gov.
- **URL**: https://www.fema.gov/floodplain-management/community-rating-system
- **Confidence**: HIGH (official FEMA webpage, verified content)
- **Relevance**: Defines the 10-class system with point thresholds (500-4500+) and corresponding SFHA premium discounts (5%-45%). Class 10 = no participation/no discount; Class 1 = 4,500+ points/45% discount. Over 1,500 communities participate.

**R1.3. 44 CFR Parts 59-61 (NFIP Regulatory Authority)**
- **Citation**: Code of Federal Regulations, Title 44, Chapter I, Subchapter B, Parts 59-61. *National Flood Insurance Program*.
- **URL**: https://www.ecfr.gov/current/title-44/chapter-I/subchapter-B/part-59
- **Confidence**: HIGH (official eCFR, verified)
- **Relevance**: Provides the regulatory basis for the NFIP and CRS. Part 59 covers general provisions; Part 61 covers insurance coverage and rates. Authority derives from 42 U.S.C. 4001 et seq. (National Flood Insurance Act of 1968).

**R1.4. National Flood Insurance Act of 1968**
- **Citation**: National Flood Insurance Act of 1968, Pub. L. 90-448, Title XIII, 82 Stat. 572 (codified at 42 U.S.C. 4001-4127).
- **URL**: https://www.fema.gov/sites/default/files/2020-07/national-flood-insurance-act-1968.pdf
- **Confidence**: HIGH (statutory text on FEMA.gov)
- **Relevance**: The statutory authority for the entire NFIP framework, including community participation requirements and the foundation for CRS.

**R1.5. 2021 Addendum to the CRS Coordinator's Manual**
- **Citation**: Federal Emergency Management Agency. (2021). *Addendum to the 2017 CRS Coordinator's Manual*. Washington, DC: FEMA.
- **URL**: https://www.fema.gov/sites/default/files/documents/fema_community-rating-system_coordinators-manual_addendum-2021.pdf
- **Confidence**: HIGH (official FEMA document)
- **Relevance**: Updates to CRS credit calculations effective January 2021. Together with the 2017 Manual, constitutes the complete current CRS guidance.

---

## 2. "Example of Good Reasoning" as SOP Simulation

### Design Element
Government agent prompts include structured reasoning examples (decision memo format) to simulate how real agencies document and justify decisions using Structured Analytic Techniques.

### References

**R2.1. Heuer & Pherson, *Structured Analytic Techniques for Intelligence Analysis* (3rd ed.)**
- **Citation**: Pherson, R. H., & Heuer, R. J., Jr. (2019). *Structured Analytic Techniques for Intelligence Analysis* (3rd ed.). CQ Press/SAGE. ISBN: 978-1-5063-6893-1.
- **URL**: https://collegepublishing.sagepub.com/products/structured-analytic-techniques-for-intelligence-analysis-3-255432
- **Confidence**: HIGH (verified ISBN, publisher page on SAGE)
- **Relevance**: Defines 66 structured analytic techniques used across intelligence, law enforcement, homeland security, and policy analysis. Adopted by dozens of US and international agencies. Establishes the principle that structured reasoning templates reduce cognitive biases and improve decision quality -- directly analogous to our use of reasoning examples in LLM prompts.

**R2.2. FEMA Benefit-Cost Analysis Reference Guide**
- **Citation**: Federal Emergency Management Agency. (2009). *Benefit-Cost Analysis Reference Guide*. Washington, DC: FEMA.
- **URL**: https://www.fema.gov/sites/default/files/2020-04/fema_bca_reference-guide.pdf
- **Confidence**: HIGH (official FEMA PDF, publicly available)
- **Relevance**: Demonstrates that FEMA requires structured, quantitative reasoning (BCA with BCR >= 1.0) for all hazard mitigation grant decisions. The BCA toolkit follows OMB cost-effectiveness guidelines. This justifies embedding structured cost-benefit reasoning templates in the government agent's prompt.

**R2.3. USGS Decision Memorandum Template**
- **Citation**: U.S. Geological Survey. (n.d.). *Decision Memorandum Template*. USGS.gov.
- **URL**: https://www.usgs.gov/media/files/decision-memorandum-template
- **Confidence**: HIGH (official USGS resource page, verified existence)
- **Relevance**: A real federal agency template for structured executive decision-making. Demonstrates that government agencies use standardized memo formats with defined sections (background, alternatives, recommendation) -- the exact pattern our prompt examples simulate.

**R2.4. Administrative Procedure Act (APA), 5 U.S.C. 551 et seq.**
- **Citation**: Administrative Procedure Act, Pub. L. 79-404, 60 Stat. 237 (1946) (codified at 5 U.S.C. 551-559).
- **URL**: https://www.epa.gov/laws-regulations/summary-administrative-procedure-act
- **Confidence**: HIGH (federal statute, EPA summary verified)
- **Relevance**: The APA requires federal agencies to provide documented rationale for decisions, including "statement of the rule's basis and purpose" and evidence of "reasoned decisionmaking." Agency decisions must withstand judicial review by demonstrating adequate explanation based on essential facts. This legal requirement justifies why our government agent prompt models documented reasoning processes.

---

## 3. Budget Sustainability Projection as Decision Input

### Design Element
The government agent considers projected budget depletion rates when making subsidy allocation decisions, mirroring real federal budget planning practices.

### References

**R3.1. OMB Circular A-11: Preparation, Submission, and Execution of the Budget**
- **Citation**: Office of Management and Budget. (2025). *Circular No. A-11: Preparation, Submission, and Execution of the Budget*. Executive Office of the President.
- **URL**: https://www.whitehouse.gov/wp-content/uploads/2025/08/a11.pdf
- **Confidence**: HIGH (official White House/OMB document, 1,079 pages)
- **Relevance**: Known as the "Budget Bible," A-11 provides legally binding guidance to all executive branch agencies on budget preparation, including multi-year projections, apportionment processes, and standardized budget methods. Directly justifies modeling government agents that consider budget sustainability when allocating subsidies.

**R3.2. GPRA Modernization Act of 2010**
- **Citation**: Government Performance and Results Modernization Act of 2010, Pub. L. 111-352, 124 Stat. 3866 (2011).
- **URL**: https://obamawhitehouse.archives.gov/omb/mgmt-gpra/gplaw2m (original GPRA 1993 text)
- **Confidence**: HIGH (federal statute, verified via Congress.gov and White House archives)
- **Relevance**: Requires federal agencies to develop strategic plans (3-5 year horizon), set annual performance targets, and report on results. Mandates systematic accountability for program outcomes. Justifies the government agent's projection of budget depletion as a forward-looking performance management practice.

**R3.3. Foundations for Evidence-Based Policymaking Act of 2018 (Evidence Act)**
- **Citation**: Foundations for Evidence-Based Policymaking Act of 2018, Pub. L. 115-435, 132 Stat. 5529.
- **URL**: https://www.congress.gov/bill/115th-congress/house-bill/4174
- **Confidence**: HIGH (Congress.gov, verified)
- **Relevance**: Requires agencies to develop evidence-building plans as part of strategic planning, including evaluation plans and data-driven decision-making. Establishes Chief Data Officer and Evaluation Officer roles. Justifies embedding quantitative budget analysis into the government agent's decision process.

---

## 4. Distinguishing "Immediate Crisis" vs "Recurring Severe Event"

### Design Element
The government agent prompt distinguishes between novel/immediate flood crises and recurring severe events, triggering different response protocols. This reflects real disaster management practice.

### References

**R4.1. FEMA Hazard Mitigation Assistance Program and Policy Guide (v2.1)**
- **Citation**: Federal Emergency Management Agency. (2025). *Hazard Mitigation Assistance Program and Policy Guide* (Version 2.1). Washington, DC: FEMA.
- **URL**: https://www.fema.gov/grants/mitigation/learn/hazard-mitigation-assistance-guidance
- **Confidence**: HIGH (official FEMA guidance, effective January 20, 2025)
- **Relevance**: Explicitly distinguishes between Repetitive Loss (RL) and Severe Repetitive Loss (SRL) properties, with different eligibility criteria and cost-share provisions (up to 100% federal share for SRL). The FMA Swift Current program streamlines funding specifically for properties with claims-based histories of repeated flooding. This directly justifies the prompt's differentiation between novel and recurring flood events.

**R4.2. Birkland, *Lessons of Disaster***
- **Citation**: Birkland, T. A. (2007). *Lessons of Disaster: Policy Change after Catastrophic Events*. Georgetown University Press. ISBN: 978-1-58901-121-2.
- **URL**: https://press.georgetown.edu/Book/Lessons-of-Disaster
- **Confidence**: HIGH (verified via Georgetown University Press, JSTOR, Amazon)
- **Relevance**: Analyzes how governments learn differently from initial vs. repeated disasters. Introduces the concept of "event-induced attention" and demonstrates that the type of disaster affects the type of policy learning. Documents "unlearning" -- how disaster lessons decay over time without recurring reinforcement. Directly supports differentiating government response protocols for novel vs. recurring hazards.

**R4.3. Bubeck, Botzen, & Aerts (2012), "A Review of Risk Perceptions and Other Factors that Influence Flood Mitigation Behavior"**
- **Citation**: Bubeck, P., Botzen, W. J. W., & Aerts, J. C. J. H. (2012). A review of risk perceptions and other factors that influence flood mitigation behavior. *Risk Analysis*, 32(9), 1481-1495.
- **DOI**: 10.1111/j.1539-6924.2011.01783.x
- **URL**: https://onlinelibrary.wiley.com/doi/10.1111/j.1539-6924.2011.01783.x
- **Confidence**: HIGH (verified DOI, Wiley Online Library)
- **Relevance**: Reviews the relationship between flood risk perception and mitigation behavior, finding that repeated flood experience shapes risk perception but does not straightforwardly translate to increased mitigation action. Supports modeling differentiated government responses to communities with different exposure histories.

**R4.4. Kousky & Michel-Kerjan (2017), "Examining Flood Insurance Claims in the United States"**
- **Citation**: Kousky, C., & Michel-Kerjan, E. (2017). Examining flood insurance claims in the United States: Six key findings. *Journal of Risk and Insurance*, 84(3), 819-850.
- **DOI**: 10.1111/jori.12106
- **URL**: https://onlinelibrary.wiley.com/doi/abs/10.1111/jori.12106
- **Confidence**: HIGH (verified DOI, Wiley Online Library)
- **Relevance**: First large-scale analysis of 1M+ NFIP claims (1978-2012), documenting the concentration of losses in repetitive loss properties. Provides empirical basis for why government programs distinguish between first-time and repeat flood victims in policy design.

---

## 5. CRS Score-Proportionality (Weak Mitigation -> Low Discount)

### Design Element
The government agent scales CRS discounts proportionally to demonstrated mitigation effort, reflecting the actual CRS class structure.

### References

**R5.1. CRS Class Rating Table (FEMA)**
- **Citation**: Federal Emergency Management Agency. (n.d.). *Community Rating System*. FEMA.gov.
- **URL**: https://www.fema.gov/floodplain-management/community-rating-system
- **Confidence**: HIGH (verified via WebFetch, exact table extracted)
- **Relevance**: The actual CRS class table showing strict proportionality:

| Credit Points | Class | SFHA Discount |
|--------------|-------|---------------|
| 4,500+       | 1     | 45%           |
| 4,000-4,499  | 2     | 40%           |
| 3,500-3,999  | 3     | 35%           |
| 3,000-3,499  | 4     | 30%           |
| 2,500-2,999  | 5     | 25%           |
| 2,000-2,499  | 6     | 20%           |
| 1,500-1,999  | 7     | 15%           |
| 1,000-1,499  | 8     | 10%           |
| 500-999      | 9     | 5%            |
| 0-499        | 10    | 0%            |

Each 500-point increment yields exactly 5% additional discount. Communities with minimal effort (Class 9-10) receive minimal or no discount. This linear proportionality is exactly what the government agent implements.

**R5.2. CRS Coordinator's Manual (2017)** -- see R1.1 above
- **Relevance for this element**: Documents the 19 activities across 4 categories (Public Information, Mapping & Regulations, Flood Damage Reduction, Warning & Response) with specific point values ranging from individual activity caps to the 4,500+ total for Class 1. Verification cycles (typically 3-year for recertification) ensure sustained effort.

---

## 6. Government Fiscal Responsibility Check (High Subsidy + Low Progress -> Decrease)

### Design Element
The government agent reduces subsidies when a community receives high support but shows low mitigation progress, reflecting real program evaluation and sunset provision practices.

### References

**R6.1. GAO, *Program Evaluation: Key Terms and Concepts* (GAO-21-404SP)**
- **Citation**: U.S. Government Accountability Office. (2021). *Program Evaluation: Key Terms and Concepts* (GAO-21-404SP). Washington, DC: GAO.
- **URL**: https://www.gao.gov/products/gao-21-404sp
- **Confidence**: HIGH (official GAO publication, verified)
- **Relevance**: Defines program evaluation as "systematic assessment using data collection and analysis of one or more programs to assess effectiveness and efficiency." Establishes the conceptual framework for evaluating whether government subsidies are achieving intended outcomes -- the exact logic embedded in the government agent's fiscal responsibility check.

**R6.2. GPRA Modernization Act of 2010** -- see R3.2 above
- **Relevance for this element**: Requires agencies to annually set performance targets AND report the degree to which previous year's targets were met. This "performance gap" reporting directly parallels the government agent's logic of comparing subsidy levels against mitigation progress.

**R6.3. Foundations for Evidence-Based Policymaking Act of 2018** -- see R3.3 above
- **Relevance for this element**: Mandates evaluation plans concurrent with annual performance plans. Agencies must systematically identify whether programs are achieving their goals using evidence, justifying subsidy adjustments when outcomes fall short.

**R6.4. GAO, *Results-Oriented Government: GPRA Has Established a Solid Foundation for Achieving Greater Results* (GAO-04-38)**
- **Citation**: U.S. Government Accountability Office. (2004). *Results-Oriented Government: GPRA Has Established a Solid Foundation for Achieving Greater Results* (GAO-04-38). Washington, DC: GAO.
- **URL**: https://www.gao.gov/products/gao-04-38
- **Confidence**: HIGH (official GAO report, verified URL)
- **Relevance**: Evaluates how GPRA implementation improved agency accountability, finding that performance measurement frameworks help identify programs where investment is not yielding results. Supports the agent's logic of reducing subsidies for underperforming programs.

**R6.5. Sunset Provisions in Government Programs**
- **Citation**: Fiveable. (n.d.). Sunset Provisions. In *Fundamentals of American Government*.
- **URL**: https://fiveable.me/fundamentals-american-government/key-terms/sunset-provisions
- **Confidence**: MEDIUM (educational resource, not primary source; verified concept)
- **Relevance**: Sunset provisions place fixed termination dates on programs absent affirmative reauthorization. 35 states enacted general sunset laws starting in the 1970s. While this is a secondary source, the concept is well-established in public administration: programs that fail periodic review face termination. This parallels the government agent's logic of reducing support for programs not meeting performance thresholds.

**R6.5b. (Primary source alternative for sunset provisions)**
- **Citation**: Kearney, R. C. (2025). An iridescent sunset: An empirical analysis of sunset legislation. *Journal of Regulatory Economics*.
- **DOI**: See https://link.springer.com/article/10.1007/s11149-025-09498-5
- **Confidence**: MEDIUM (Springer link verified, recent 2025 publication)
- **Relevance**: Empirical analysis of sunset legislation effectiveness. Provides academic grounding for the concept that government programs face termination or reduction when periodic reviews find insufficient performance.

---

## Summary Confidence Table

| # | Design Element | Refs | Highest Confidence | Key Anchor |
|---|---------------|------|--------------------|------------|
| 1 | CRS as reward | 5 | HIGH | CRS Coordinator's Manual (FEMA, 2017) |
| 2 | SOP reasoning template | 4 | HIGH | Heuer & Pherson (2019); USGS Decision Memo Template |
| 3 | Budget sustainability | 3 | HIGH | OMB Circular A-11; GPRA Modernization Act |
| 4 | Crisis vs. recurring | 4 | HIGH | FEMA HMA Guide v2.1; Birkland (2007) |
| 5 | CRS proportionality | 2 | HIGH | FEMA CRS Class Table (verified) |
| 6 | Fiscal responsibility | 5 | HIGH | GAO-21-404SP; GPRA; Evidence Act |

**Total references**: 23 (17 unique, 6 cross-referenced)
**Confidence distribution**: 21 HIGH, 2 MEDIUM, 0 LOW
