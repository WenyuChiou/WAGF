# 4. Follow the two-way irrigation coupling

The irrigation example couples decisions and the river system in both
directions. The agents' requests enter the annual water balance. The resulting
Lake Mead level sets the next year's Lower Basin shortage tier, delivery limits,
and water-situation text shown to each agent.

Use the built-in mock with the 78 bundled CRSS profiles. This two-year setting
is the smallest stock-data run used here that crosses a Lake Mead tier without
editing a configuration:

```bash
python examples/irrigation_abm/run_experiment.py --model mock --years 2 --real --workers 1 --seed 42 --governance-mode strict --coupling --output .tmp/tutorial-irrigation-tier
```

Summarize one copy of the shared river state per year, then count the reasons
for individual delivery gaps:

```bash
python -c "import csv,collections; from pathlib import Path; rows=list(csv.DictReader(Path('.tmp/tutorial-irrigation-tier/simulation_log.csv').open(encoding='utf-8-sig'))); one={}; [one.setdefault(r['year'],r) for r in rows]; print([(y,one[y]['shortage_tier'],round(float(one[y]['lake_mead_level']),2),round(sum(float(r['request']) for r in rows if r['year']==y)),round(sum(float(r['delivered']) for r in rows if r['year']==y)),dict(collections.Counter(r['gap_reason'] for r in rows if r['year']==y))) for y in one])"
```

The executed run prints (the second row is wrapped here for readability):

```text
[('1', '0', 1081.46, 5735690, 5735690, {'none': 78}),
 ('2', '1', 1071.29, 5735690, 5669074, {'none': 65, 'lb_junior_tier_cut': 2, 'ub_subbasin_supply': 11})]
```

The first year's requests help lower Mead from its opening level. Year 2 then
opens in Tier 1 and delivers less water. The two Lower Basin junior cuts total
2,884 acre-feet; the Upper Basin gaps come from sub-basin supply, not the Lake
Mead tier.

The runner does not save decision prompts verbatim, so this run does not provide
a byte-for-byte prompt record. The runtime evidence above observes the state and
deliveries. The static pipeline shows where that state goes next:
[`run_experiment.py` (`pre_year`)](../../examples/irrigation_abm/run_experiment.py)
reads each agent's environment context, builds `water_situation_text`, and
assigns it before the decision; the
[`irrigation_farmer.txt` decision prompt](../../examples/irrigation_abm/config/prompts/irrigation_farmer.txt)
inserts that text. The
[`irrigation_personas.py` (`_lower_basin_tier_text`)](../../examples/irrigation_abm/irrigation_personas.py)
says that a Tier 1 Lower Basin shortage applies because Lake Mead was below
1,075 feet on 1 January, then explains any entitlement ceiling that applies to
that agent. Together, the runtime record and this source path establish that the
observed year-2 tier enters the next decision prompt; they do not claim to have
captured the prompt bytes.

The mock always returns an incomplete response and never supplies the required
scarcity and capacity appraisals. Governance retries three times and executes
the configured `maintain_demand` default. This run demonstrates the physical
feedback path and audit wiring, not realistic agent adaptation.

Next: [resume from an irrigation journal](05-resume.md).
