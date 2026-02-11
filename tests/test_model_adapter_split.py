import importlib


def test_model_adapter_split_modules_exist():
    importlib.import_module('broker.utils.preprocessors')
    importlib.import_module('broker.utils.adapters.deepseek')
