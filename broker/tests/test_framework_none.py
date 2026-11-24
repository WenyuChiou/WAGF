"""Configuration and runtime coverage for agents without appraisal."""

import csv
import json
import logging
from pathlib import Path

import pytest
import yaml

from broker.agents import AgentConfig, BaseAgent, Skill
from broker.components.context.builder import TieredContextBuilder
from broker.components.governance.domain_validator_dispatch import build_domain_validators
from broker.components.governance.validator_registry import ValidatorRegistry
from broker.components.memory.engine import WindowMemoryEngine
from broker.config.agent_types.base import AgentTypeDefinition, PsychologicalFramework
from broker.core.experiment import ExperimentBuilder
from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry
from broker.interfaces.rating_scales import FrameworkType, RatingScaleRegistry
from broker.interfaces.skill_types import ExecutionResult
from broker.tools.validate_prompt import main as validate_prompt
from broker.utils import agent_config
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.llm_utils import LLMStats
from broker.validators.governance.thinking_validator import ThinkingValidator


PROMPT = "Review the operating state.\n{options_text}\n{response_format}"
CHOICE = {"key": "decision", "type": "choice", "required": True}
APPRAISAL = {
    "key": "budget_appraisal", "type": "appraisal", "scale": "utility",
    "construct": "BUDGET_UTIL", "required": True,
}


def write_yaml(tmp_path, config, name="agent_types.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def load_config(path):
    return AgentTypeConfig.load(str(path), force_reload=True)


@pytest.fixture
def clear_framework_warnings(monkeypatch):
    monkeypatch.setattr(agent_config, "_warned_missing_frameworks", set())


def test_missing_framework_warns_once_per_path_and_agent_type(
    tmp_path, caplog, clear_framework_warnings
):
    blocks = {
        "operator": {"psychological_framework": "none"},
        "observer": {"agent_type": "observer"},
        "recorder": {"agent_type": "recorder"},
        "explicit": {"psychological_framework": "pmt"},
        "blank": {"psychological_framework": None},
    }
    path = write_yaml(tmp_path, blocks)
    other_path = write_yaml(tmp_path, blocks, "other.yaml")
    cfg = load_config(path)
    caplog.clear()

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert cfg.get_framework_for_agent_type("operator") == "none"
            assert cfg.get_framework_for_agent_type("observer") == "pmt"
            assert cfg.get_framework_for_agent_type("recorder") == "pmt"
            assert cfg.get_framework_for_agent_type("explicit") == "pmt"
            assert cfg.get_framework_for_agent_type("blank") is None
        assert load_config(path).get_framework_for_agent_type("observer") == "pmt"
        assert load_config(other_path).get_framework_for_agent_type("observer") == "pmt"

    assert [record.getMessage() for record in caplog.records] == [
        f"[Config] agent type '{name}' in {yaml_path} declares no psychological_framework; "
        "falling back to pmt. Declare one explicitly "
        "(psychological_framework: none for an agent with no appraisal)."
        for yaml_path, name in ((path, "observer"), (path, "recorder"), (other_path, "observer"))
    ]


def test_none_has_no_rating_scale(tmp_path):
    cfg = load_config(write_yaml(tmp_path, {
        "shared": {
            "rating_scale": "Legacy scale",
            "rating_scales": {"none": {"template": "Unused scale", "levels": ["L", "H"]}},
        },
    }))
    pmt_scale = RatingScaleRegistry.get(FrameworkType.PMT)
    assert cfg.get_rating_scale("none") == cfg.get_rating_scale("NONE") == ""
    assert cfg.get_rating_scale_levels("none") == cfg.get_rating_scale_levels("NONE") == []
    assert cfg.get_rating_scale("pmt") == pmt_scale.template != ""
    assert cfg.get_rating_scale_levels("pmt") == pmt_scale.levels


def test_check_theory_free_accepts_clean_none_and_ignores_other_frameworks(tmp_path, caplog):
    cfg = load_config(write_yaml(tmp_path, {
        "metadata": {},
        "operator": {"psychological_framework": "none", "prompt_template": PROMPT},
        "disabled": False,
        "planner": {"psychological_framework": "pmt", "response_format": {"fields": [APPRAISAL]}},
        "observer": {"agent_type": "observer", "prompt_template": "{rating_scale}"},
    }))
    caplog.clear()
    assert cfg.agent_type_names() == ["operator", "planner", "observer"]
    for agent_type in cfg.agent_type_names():
        assert cfg.check_theory_free(agent_type) == []
    assert not caplog.records


@pytest.mark.parametrize(
    ("block", "shared", "problem"),
    [
        ({"inherit_shared": True}, {"response_format": {"fields": [APPRAISAL]}},
         "budget_appraisal"),
        ({"constructs": {"primary": ["X"]}}, {}, "constructs"),
        ({"parsing": {"constructs": {"X": {}}}}, {}, "parsing.constructs"),
        ({"prompt_template": "Use {rating_scale}."}, {}, "{rating_scale}"),
        ({"prompt_template": "Use Threat appraisal."}, {}, "threat appraisal"),
        ({"prompt_template": "Use threat_appraisal."}, {}, "threat_appraisal"),
        ({"prompt_template": "Use coping_appraisal."}, {}, "coping_appraisal"),
        ({"thinking_rules": [{"conditions": [{"construct": "X"}]}]}, {}, "'X'"),
        ({"governance": {"thinking_rules": [{"conditions": [{"construct": "X"}]}]}}, {}, "'X'"),
        ({"coherence_rules": [{"conditions": [{"construct": "X"}]}]}, {}, "'X'"),
        ({"rules": [{"conditions": [{"construct": "X"}]}]}, {}, "'X'"),
        ({"validation_rules": [{"conditions": [{"construct": "X"}]}]}, {}, "validation_rules"),
        ({"identity_rules": {"r1": {"construct": "X"}}}, {}, "identity_rules"),
    ],
)
def test_check_theory_free_reports_each_conflict(tmp_path, block, shared, problem):
    cfg = load_config(write_yaml(tmp_path, {
        "shared": shared,
        "operator": {"psychological_framework": " NoNe ", **block},
    }))
    (message,) = cfg.check_theory_free("operator")
    assert message.startswith("agent type 'operator' declares psychological_framework: none, but ")
    assert problem in message


@pytest.mark.parametrize("parsing", [None, {}, {"decision_keywords": ["decision"]}])
def test_check_theory_free_reports_parsing_constructs_inherited_from_default(tmp_path, parsing):
    operator = {"psychological_framework": "none", "prompt_template": PROMPT}
    if parsing is not None:
        operator["parsing"] = parsing
    cfg = load_config(write_yaml(tmp_path, {
        "default": {"parsing": {"constructs": {"TP_LABEL": {"keywords": ["threat"]}}}},
        "operator": operator,
    }))
    (message,) = cfg.check_theory_free("operator")
    assert "inherits parsing.constructs from the default block" in message
    # The check must not write the inherited block into the agent's config.
    assert cfg.get("operator").get("parsing") == parsing


def test_check_theory_free_own_parsing_constructs_override_default(tmp_path):
    cfg = load_config(write_yaml(tmp_path, {
        "default": {"parsing": {"constructs": {"TP_LABEL": {}}}},
        "operator": {
            "psychological_framework": "none", "prompt_template": PROMPT,
            "parsing": {"constructs": {}},
        },
    }))
    assert cfg.check_theory_free("operator") == []


@pytest.mark.parametrize(
    ("config", "problem"),
    [
        ({"operator": {"psychological_framework": "none", "prompt_template": ["a", "b"]}},
         "prompt template is not text"),
        ({"shared": None, "operator": {"psychological_framework": "none", "prompt_template": PROMPT}},
         None),
        ({"operator": {"psychological_framework": "none", "prompt_template": PROMPT,
                       "response_format": ["decision"]}},
         "its response_format is not a mapping"),
        ({"shared": {"response_format": "fields"},
          "operator": {"psychological_framework": "none", "prompt_template": PROMPT}},
         "its shared.response_format is not a mapping"),
        ({"operator": {"psychological_framework": "none", "prompt_template": PROMPT,
                       "response_format": {"fields": "decision"}}},
         "fields are not a list"),
    ],
)
def test_check_theory_free_reports_malformed_blocks_without_raising(tmp_path, config, problem):
    cfg = load_config(write_yaml(tmp_path, config))
    problems = cfg.check_theory_free("operator")
    if problem is None:
        assert problems == []
    else:
        (message,) = problems
        assert problem in message


def test_validate_prompt_reports_theory_free_errors(tmp_path, capsys):
    (tmp_path / "operator.txt").write_text(
        f"{PROMPT}\nUse Threat appraisal.", encoding="utf-8",
    )
    path = write_yaml(tmp_path, {
        "operator": {
            "psychological_framework": "none",
            "actions": [{"id": "hold"}],
            "prompt_template_file": "operator.txt",
            "response_format": {"fields": [CHOICE]},
        },
    })
    assert validate_prompt([str(path)]) == 1
    output = capsys.readouterr().out
    assert "ERROR yaml: operator: agent type 'operator' declares psychological_framework: none" in output
    assert "threat appraisal" in output


class SyntheticEnvironment:
    def __init__(self):
        self.current_year = 0

    def advance_step(self):
        self.current_year += 1
        return {"current_year": self.current_year, "domain_signal": 0.5}

    def execute_skill(self, approved_skill):
        return ExecutionResult(success=True, state_changes={})


def make_builder(tmp_path, blocks, global_config=None, shared=None):
    agent_types_path = write_yaml(tmp_path, {
        "global_config": global_config or {},
        "shared": shared or {},
        **blocks,
    })
    skill_registry = write_yaml(tmp_path, {
        "default_skill": "hold",
        "skills": [{"skill_id": "hold", "domain": "test", "eligible_agent_types": list(blocks)}],
    }, "skills.yaml")
    skill = Skill(skill_id="hold", description="Maintain current settings.",
                  affected_param=None, direction="none")
    agents = {
        name: BaseAgent(AgentConfig(
            name=name, agent_type=name, state_params=[], objectives=[], constraints=[], skills=[skill],
        ))
        for name in blocks
    }
    memory_engine = WindowMemoryEngine(window_size=3)
    context_builder = TieredContextBuilder(
        agents=agents,
        hub=None,
        prompt_templates={name: block["prompt_template"] for name, block in blocks.items()},
        yaml_path=str(agent_types_path),
        memory_engine=memory_engine,
    )
    return (
        ExperimentBuilder()
        .with_model("mock")
        .with_years(1)
        .with_agents(agents)
        .with_simulation(SyntheticEnvironment())
        .with_skill_registry(str(skill_registry))
        .with_memory_engine(memory_engine)
        .with_context_builder(context_builder)
        .with_governance("default", str(agent_types_path))
        .with_exact_output(str(tmp_path / "output"))
        .with_workers(1)
        .with_seed(42)
    )


def agent_block(fields):
    return {
        "actions": [{"id": "hold", "aliases": ["hold"]}],
        "prompt_template": PROMPT,
        "parsing": {"default_skill": "hold", "decision_keywords": ["decision"]},
        "response_format": {"fields": fields},
    }


@pytest.mark.parametrize("fields", [[CHOICE, APPRAISAL], [CHOICE]])
def test_experiment_builder_checks_theory_free_configs(tmp_path, fields):
    operator = {**agent_block(fields), "psychological_framework": "none"}
    builder = make_builder(tmp_path, {"operator": operator})
    if APPRAISAL in fields:
        with pytest.raises(ValueError, match=r"ExperimentBuilder: theory-free[\s\S]*'operator'"):
            builder.build()
    else:
        assert builder.build() is not None


def test_thinking_validator_and_dispatch_accept_none(monkeypatch, caplog):
    class TheoryFreePack(DefaultDomainPack):
        def framework_for_agent_type(self, agent_type):
            assert agent_type == "operator"
            return "none"

    domain = "theory_free_test"
    monkeypatch.setitem(DomainPackRegistry._packs, domain, TheoryFreePack())
    monkeypatch.setitem(ValidatorRegistry._registry, domain, {"personal": [lambda *_: []]})
    assert ThinkingValidator(framework="none").framework == "none"
    validators = build_domain_validators(domain, agent_type="operator")
    assert next(v for v in validators if isinstance(v, ThinkingValidator)).framework == "none"
    assert "Downgrading" not in caplog.text


def test_agent_type_definition_recognizes_none_and_keeps_pmt_default():
    assert PsychologicalFramework("none") is PsychologicalFramework.NONE
    assert AgentTypeDefinition.from_dict({
        "name": "operator", "psychological_framework": "none",
    }).psychological_framework is PsychologicalFramework.NONE
    assert AgentTypeDefinition.from_dict({"name": "observer"}).psychological_framework is (
        PsychologicalFramework.PMT
    )


def scripted_mock(decision):
    def invoke(prompt):
        return f"<<<DECISION_START>>>{json.dumps(decision)}<<<DECISION_END>>>", LLMStats()

    return invoke


def test_mixed_framework_run_keeps_operator_prompt_and_audit_theory_free(
    tmp_path, caplog, clear_framework_warnings
):
    planner = {**agent_block([APPRAISAL, CHOICE]), "psychological_framework": "utility"}
    planner["parsing"]["constructs"] = {
        "BUDGET_UTIL": {"keywords": ["budget_appraisal"], "regex": r"\b(L|M|H)\b"},
    }
    blocks = {
        "planner": planner,
        "operator": {**agent_block([CHOICE]), "psychological_framework": "none"},
        "observer": agent_block([CHOICE]),
    }
    shared_rating_scale = "RATING SCALE: VL = Very Low, VH = Very High"
    # Exercise framework resolution in the normal validator path.
    runner = make_builder(tmp_path, blocks, {
        "validators": {"framework_aware_labels": True},
    }, {"rating_scale": shared_rating_scale}).build()
    decision = {"decision": 1}
    runner._llm_cache["planner"] = scripted_mock({
        **decision, "budget_appraisal": {"label": "M", "reason": "Within budget."},
    })
    runner._llm_cache["operator"] = scripted_mock(decision)
    runner._llm_cache["observer"] = scripted_mock(decision)
    runner.run()

    output = tmp_path / "output"
    traces = {}
    for name in blocks:
        path = output / "raw" / f"{name}_traces.jsonl"
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        (trace,) = [record for record in records if "_metadata" not in record]
        assert trace["year"] == 1
        assert trace["approved_skill"]["status"] == "APPROVED"
        traces[name] = trace

    operator_prompt = traces["operator"]["input"].casefold()
    assert "<<<decision_start>>>" in operator_prompt
    assert not any(marker in operator_prompt for marker in agent_config.PMT_TEXT_MARKERS)
    assert "rating scale" not in operator_prompt and "vl/l/m/h/vh" not in operator_prompt
    assert '"budget_appraisal": {"label": "L/M/H"' in traces["planner"]["input"]

    with (output / "operator_governance_audit.csv").open(encoding="utf-8", newline="") as f:
        (row,) = csv.DictReader(f)
    assert row["status"] == "APPROVED"
    assert not {
        column: value for column, value in row.items()
        if value and any(marker in column.casefold() for marker in ("appraisal", "tp_", "cp_"))
    }
    warnings = [record.getMessage() for record in caplog.records
                if "declares no psychological_framework" in record.getMessage()]
    assert len(warnings) == 1 and "agent type 'observer'" in warnings[0]


FLOOD_CONFIG = Path(__file__).resolve().parents[2] / "examples/multi_agent/flood/config"
FLOOD_PMT_TYPES = (
    "floodabm_parameters", "household_owner", "household_renter", "nj_government",
    "government", "fema_nfip", "insurance", "memory_config", "retrieval_config",
    "social_memory_config",
)


@pytest.mark.parametrize(("suffix", "expected"), [
    ("", dict.fromkeys(FLOOD_PMT_TYPES, "pmt")),
    ("_mixed_population", dict.fromkeys(FLOOD_PMT_TYPES, "pmt")),
    ("_influencer", {"social_media_influencer": "narrative_diffusion"}),
    ("_influencer_experiment", {
        **dict.fromkeys(FLOOD_PMT_TYPES, "pmt"),
        "social_media_influencer": "narrative_diffusion",
    }),
])
def test_flood_configs_keep_framework_resolution(suffix, expected, clear_framework_warnings):
    cfg = load_config(FLOOD_CONFIG / f"ma_agent_types{suffix}.yaml")
    assert cfg.agent_type_names() == list(expected)
    for name, framework in expected.items():
        assert cfg.get_framework_for_agent_type(name) == framework
        assert cfg.check_theory_free(name) == []
