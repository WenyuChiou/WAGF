import importlib


def test_context_builder_split_modules_exist():
    importlib.import_module('broker.components.context.builder')
    importlib.import_module('broker.components.context.providers')
    importlib.import_module('broker.components.context.tiered')
