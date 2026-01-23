import importlib


def test_context_builder_split_modules_exist():
    importlib.import_module('broker.components.context_builder')
    importlib.import_module('broker.components.context_providers')
    importlib.import_module('broker.components.tiered_builder')
    importlib.import_module('broker.components.neighbor_utils')
