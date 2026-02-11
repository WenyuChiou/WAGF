import importlib


def test_memory_engine_split_modules_exist():
    importlib.import_module('broker.components.memory.engine')
    importlib.import_module('broker.components.memory.engines.window')
    importlib.import_module('broker.components.memory.engines.importance')
    importlib.import_module('broker.components.memory.engines.humancentric')
    importlib.import_module('broker.components.memory.engines.hierarchical')
    importlib.import_module('broker.components.memory.seeding')
