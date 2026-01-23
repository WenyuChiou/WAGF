import importlib


def test_memory_engine_split_modules_exist():
    importlib.import_module('broker.components.memory_engine')
    importlib.import_module('broker.components.engines.window_engine')
    importlib.import_module('broker.components.engines.importance_engine')
    importlib.import_module('broker.components.engines.humancentric_engine')
    importlib.import_module('broker.components.engines.hierarchical_engine')
    importlib.import_module('broker.components.memory_seeding')
