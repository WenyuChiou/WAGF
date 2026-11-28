"""The flood year-end reflection prompt: the one-agent layout, rendered from the
real flood config text, the real year and fact lines and the real persona code."""
import re
from pathlib import Path

import yaml

from broker.components.cognitive.reflection import ReflectionEngine, first_sentence
from broker.modules.survey.agent_initializer import AgentProfile
from examples.single_agent.flood_reflection import FloodYear, fact_line, year_line

SA = Path(__file__).resolve().parents[1]


def test_flood_reflection_prompt_has_the_one_agent_layout_and_no_simulation_words():
    cfg = yaml.safe_load((SA / "agent_types.yaml").read_text(encoding="utf-8"))
    refl = cfg["global_config"]["reflection"]
    profile = AgentProfile(
        agent_id="Agent_1", record_id="r1", family_size=1, generations="1",
        income_bracket="50k", income_midpoint=50000.0, housing_status="mortgage", house_type="single")
    persona = profile.generate_narrative_persona()
    identity = first_sentence(persona)
    assert identity == "You are a homeowner with a mortgage."
    years = [FloodYear(2, True, True, False, False, "Year 2: a flood damaged my house."),
             FloodYear(3, False, False, False, True, "Year 3: no flood this year.")]
    items = [{"content": year_line(fy), "year": fy.year} for fy in years]
    prompt = ReflectionEngine().generate_reflection_prompt_one_agent(
        identity, items, "year 3",  # run_flood passes f"year {year}"
        topic=refl["topic"], persona_instruction=refl["persona_instruction"],
        record_lines=[fact_line(years[0])], year_lines=True)
    assert prompt.startswith(identity + "\nIt is the end of year 3. Look back on your recent years.\n"
                             "Question: " + "What do your recent years tell you about " + refl["topic"] + "?" + "\n\nYour recent years:\n- ")
    assert "\n\nWhat happened this year (kept with your answer; do not repeat it):\n- " in prompt
    assert prompt.endswith('\n\nAnswer with this JSON object only: {"answer": "<your answer>"}')
    body = prompt[len(identity):]
    for word in ("simulation", "Reflection Assistant", "agent", "Agent IDs", "Task Data", "###", "Agent_1"):
        assert word not in body, word
