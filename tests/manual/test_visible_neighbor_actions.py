import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from broker.components.analytics.interaction import InteractionHub
from broker.components.social.graph import RandomGraph

class MockAgent:
    def __init__(self, aid, elevated=False, relocated=False, insured=False):
        self.agent_id = aid
        self.elevated = elevated
        self.relocated = relocated
        self.has_flood_insurance = insured

agents = {
    'A1': MockAgent('A1'),
    'A2': MockAgent('A2', elevated=True),
    'A3': MockAgent('A3', relocated=True),
    'A4': MockAgent('A4', insured=True),
}

graph = RandomGraph(list(agents.keys()), p=1.0)
hub = InteractionHub(graph=graph)
ctx = hub.get_social_context('A1', agents)

actions = ctx.get("visible_actions", [])
assert any(a["action"] == "elevated_house" for a in actions)
assert any(a["action"] == "relocated" for a in actions)
assert any(a["action"] == "insured" for a in actions)
assert ctx.get("neighbor_count") == 3
print("OK")
