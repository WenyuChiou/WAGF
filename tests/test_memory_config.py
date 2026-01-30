import pytest

from cognitive_governance.memory import UnifiedCognitiveEngine
from cognitive_governance.memory.config import GlobalMemoryConfig, FloodDomainConfig, DomainMemoryConfig
from cognitive_governance.memory.strategies import SymbolicSurpriseStrategy, EMASurpriseStrategy


def test_unified_engine_accepts_config_objects():
    global_cfg = GlobalMemoryConfig(arousal_threshold=0.6)
    domain_cfg = FloodDomainConfig(stimulus_key="flood_depth")
    engine = UnifiedCognitiveEngine(global_config=global_cfg, domain_config=domain_cfg)

    assert engine.global_config.arousal_threshold == 0.6
    assert engine.domain_config.stimulus_key == "flood_depth"


def test_symbolic_strategy_uses_config_sensors():
    global_cfg = GlobalMemoryConfig(arousal_threshold=0.6)
    domain_cfg = DomainMemoryConfig(sensory_cortex=[
        {
            "path": "flood_depth",
            "name": "FLOOD",
            "bins": [
                {"label": "SAFE", "max": 0.1},
                {"label": "MAJOR", "max": 99.9},
            ],
        }
    ])
    engine = UnifiedCognitiveEngine(global_config=global_cfg, domain_config=domain_cfg)

    assert isinstance(engine.surprise_strategy, SymbolicSurpriseStrategy)
    assert getattr(engine.surprise_strategy, "_sensors", None) is not None
    assert len(engine.surprise_strategy._sensors) == 1


def test_ema_strategy_uses_domain_stimulus_key():
    global_cfg = GlobalMemoryConfig(arousal_threshold=0.6, ema_alpha=0.2)
    domain_cfg = FloodDomainConfig(stimulus_key="flood_depth")
    engine = UnifiedCognitiveEngine(global_config=global_cfg, domain_config=domain_cfg)

    assert isinstance(engine.surprise_strategy, EMASurpriseStrategy)
    assert engine.surprise_strategy.stimulus_key == "flood_depth"
    assert engine.surprise_strategy.alpha == pytest.approx(0.2)
