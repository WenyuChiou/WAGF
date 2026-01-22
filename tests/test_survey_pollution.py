
import inspect
import importlib


def test_broker_survey_no_mg_exports():
    survey = importlib.import_module("broker.modules.survey")
    assert not hasattr(survey, "MGClassifier"), "broker.modules.survey should not export MGClassifier"


def test_mg_classifier_import_from_examples():
    mod = importlib.import_module("examples.multi_agent.survey.mg_classifier")
    assert hasattr(mod, "MGClassifier"), "MGClassifier should live under examples.multi_agent.survey"


def test_agent_initializer_has_no_mg_classifier_param():
    from broker.modules.survey.agent_initializer import AgentInitializer
    sig = inspect.signature(AgentInitializer.__init__)
    assert "mg_classifier" not in sig.parameters
