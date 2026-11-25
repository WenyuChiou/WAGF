"""R1 slice 3: the ``expression:`` rule condition.

One condition string over world variables and the proposed number, checked the
same way by all three condition evaluators (AgentValidator, ThinkingValidator,
RuleCondition). Names in this file are generic on purpose (storage, capacity,
flag): the framework layer carries no domain vocabulary.
"""
from __future__ import annotations

import itertools
import math
import shutil
from types import SimpleNamespace

import pytest
import yaml

import broker.run
from broker.components.analytics.feedback import SafeExpressionEvaluator
from broker.config.schema import RuleCondition as PydanticRuleCondition
from broker.governance.expression_condition import (
    MISSING,
    ExpressionConditionError,
    ExpressionEvaluationError,
    compile_expression_condition,
    evaluate_expression_condition,
    is_expression_condition,
)
from broker.governance.rule_types import RuleCondition
from broker.utils.agent_config import AgentTypeConfig, resolve_rule_grounding
from broker.validators.agent.agent_validator import AgentValidator
from broker.validators.governance.thinking_validator import ThinkingValidator
from examples.reservoir_control import ops_case

OVERFLOW = "storage_now > 0.9 * capacity and proposed_magnitude < 100"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path, rules, *, kind="thinking_rules", extra_block=None):
    block = {
        "agent_type": "op",
        "psychological_framework": "generic",
        "actions": [{"id": "release", "aliases": ["release"], "description": "x"},
                    {"id": "hold", "aliases": ["hold"], "description": "y"}],
        "governance": {"default": {kind: rules}},
    }
    block.update(extra_block or {})
    path = tmp_path / "agent_types.yaml"
    path.write_text(yaml.safe_dump({"global_config": {}, "op": block}), encoding="utf-8")
    return str(path)


def _rule(expr, rule_id="r1", scope=None, level="ERROR"):
    cond = {"expression": expr}
    if scope:
        cond["scope"] = scope
    return {"id": rule_id, "conditions": [cond], "blocked_skills": ["release"],
            "level": level, "message": "blocked by " + rule_id}


def _validator(tmp_path, rules, **kw):
    AgentTypeConfig.clear_cache()
    return AgentValidator(config_path=_write_config(tmp_path, rules, **kw))


def _context(env=None, state=None, flat=None):
    """The broker's validation context shape: planes plus the flattened copy."""
    env, state, flat = dict(env or {}), dict(state or {}), dict(flat or {})
    return {"env_state": env, "state": state, "agent_type": "op",
            **state, **env, **flat}


def _thinking(v, ctx, decision="release"):
    return v.validate_thinking("op", "A1", decision, ctx["state"], {}, full_context=ctx)


def _fired(results, rule_id="r1"):
    return any(r.metadata.get("rule_id") == rule_id and not r.valid for r in results)


def _ids(results):
    return [r.metadata.get("rule_id") for r in results]


# ---------------------------------------------------------------------------
# 1. compile rejects
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expr", [
    "abs(x) > 1",                 # call
    "a.b > 1",                    # attribute
    "a[0] > 1",                   # subscript
    "a ** 2 > 1",                 # power
    "name == 'x'",                # string constant
    "x == None",                  # None constant
    "(lambda: 1)() > 0",          # lambda
    "a + 1",                      # not boolean at the top
    "a and b",                    # operands are not comparisons
    "1 < 2",                      # no variable
    "__x > 1",                    # underscore name
    "x > ",                       # syntax error
    "",                           # empty
    "   ",
    "x > 1e999",                  # not finite
    "x > 1j",                     # complex constant
])
def test_compile_rejects(expr):
    with pytest.raises(ExpressionConditionError):
        compile_expression_condition({"expression": expr}, where="rule 'x'")


@pytest.mark.parametrize("cond", [
    {"expression": 5},
    {"expression": None, "type": "expression"},
    {"expression": "a > 1", "variable": "a"},        # mixed keys
    {"expression": "a > 1", "construct": "TP"},
    {"expression": "a > 1", "field": "a"},
    {"expression": "a > 1", "operator": ">"},
    {"expression": "a > 1", "value": 1},
    {"expression": "a > 1", "values": [1]},
    {"expression": "a > 1", "type": "construct"},
    {"expression": "a > 1", "scope": "elsewhere"},
])
def test_compile_rejects_bad_condition_shape(cond):
    with pytest.raises(ExpressionConditionError):
        compile_expression_condition(cond)


def test_compile_error_names_the_rule():
    with pytest.raises(ExpressionConditionError, match="rule 'flood' in cfg.yaml"):
        compile_expression_condition({"expression": "abs(x) > 1"},
                                     where="rule 'flood' in cfg.yaml")


def test_compile_accepts_and_collects_names():
    c = compile_expression_condition({"expression": OVERFLOW, "scope": "ENV "})
    assert c.names == ("storage_now", "capacity", "proposed_magnitude")
    assert c.scope == "env"
    assert compile_expression_condition(OVERFLOW).scope == "auto"
    compile_expression_condition("a // 2 % 3 >= -b or c != True")
    assert compile_expression_condition({"expression": OVERFLOW}) is not None


def test_is_expression_condition():
    assert is_expression_condition({"expression": "a > 1"})
    assert not is_expression_condition({"construct": "TP"})
    assert not is_expression_condition({"type": "expression", "field": "a", "operator": ">", "value": 1})
    assert is_expression_condition(SimpleNamespace(expression="a > 1"))
    assert not is_expression_condition(SimpleNamespace(expression=None))
    assert not is_expression_condition(SimpleNamespace())


# ---------------------------------------------------------------------------
# 2. evaluate (through AgentValidator, the production path)
# ---------------------------------------------------------------------------

def test_fires_and_does_not_fire(tmp_path):
    v = _validator(tmp_path, [_rule(OVERFLOW)])
    env = {"storage_now": 9.5, "capacity": 10.0}
    assert _fired(_thinking(v, _context(env, flat={"proposed_magnitude": 50})))
    assert not _fired(_thinking(v, _context(env, flat={"proposed_magnitude": 100})))
    assert not _fired(_thinking(v, _context({"storage_now": 5, "capacity": 10},
                                            flat={"proposed_magnitude": 50})))
    # other skills are not blocked
    assert not _fired(_thinking(v, _context(env, flat={"proposed_magnitude": 50}), "hold"))


def test_guarded_divisor_does_not_raise(tmp_path):
    v = _validator(tmp_path, [_rule("capacity > 0 and storage_now / capacity > 0.9")])
    res = _thinking(v, _context({"storage_now": 3, "capacity": 0}))
    assert not _fired(res) and res == []
    assert _fired(_thinking(v, _context({"storage_now": 9.5, "capacity": 10})))


def test_unguarded_zero_divisor_stops_the_run_naming_the_rule(tmp_path):
    v = _validator(tmp_path, [_rule("storage_now / capacity > 0.9", rule_id="ratio_rule")])
    ctx = _context({"storage_now": 3, "capacity": 0})
    with pytest.raises(ExpressionEvaluationError, match="ratio_rule") as exc:
        v.validate("op", "A1", "release", ctx["state"], None, {"x": "y"}, "",
                   full_validation_context=ctx)
    assert "capacity=0.0" in str(exc.value)
    # empty reasoning takes the same road
    with pytest.raises(ExpressionEvaluationError, match="ratio_rule"):
        v.validate("op", "A1", "release", ctx["state"], None, {}, "",
                   full_validation_context=ctx)


def test_expression_is_not_evaluated_for_a_skill_the_rule_does_not_block(tmp_path):
    # PR #111 review: the rule blocks only `release`; proposing `hold` with a
    # zero divisor (or a missing variable) must neither stop the run nor
    # record a warning, as in ThinkingValidator.
    v = _validator(tmp_path, [_rule("storage_now / capacity > 0.9", rule_id="ratio_rule")])
    ctx = _context({"storage_now": 3, "capacity": 0})
    assert v.validate("op", "A1", "hold", ctx["state"], None, {"x": "y"}, "",
                      full_validation_context=ctx) == []
    assert _thinking(v, ctx, "hold") == []
    assert _thinking(v, _context({"capacity": 10}), "hold") == []
    with pytest.raises(ExpressionEvaluationError, match="ratio_rule"):
        _thinking(v, ctx, "release")


def test_guard_in_a_separate_condition_stops_a_later_expression(tmp_path):
    # PR #111 review: conditions [capacity > 0, storage_now / capacity > 0.9]
    # with capacity 0 must not evaluate the second one, in every evaluator.
    conds = [{"expression": "capacity > 0"},
             {"expression": "storage_now / capacity > 0.9"}]
    rule = {"id": "r1", "conditions": conds, "blocked_skills": ["release"],
            "level": "ERROR", "message": "blocked by r1"}
    v = _validator(tmp_path, [rule])
    zero = _context({"storage_now": 3, "capacity": 0})
    assert not _fired(_thinking(v, zero))
    assert _fired(_thinking(v, _context({"storage_now": 9.5, "capacity": 10})))
    tv = ThinkingValidator(framework="", builtin_checks=[])
    assert tv._evaluate_conditions(conds, {}, zero, "", [], rule_id="r1") is False


def test_zero_value_is_not_swapped_for_epsilon(tmp_path):
    """Regression for the 1e-10 swap: `storage_now == 0` must fire on 0."""
    v = _validator(tmp_path, [_rule("storage_now == 0")])
    assert _fired(_thinking(v, _context({"storage_now": 0})))
    assert not _fired(_thinking(v, _context({"storage_now": 1e-10})))


def test_missing_variable_does_not_fire_and_is_audited_once(tmp_path):
    v = _validator(tmp_path, [_rule(OVERFLOW)])
    res = _thinking(v, _context({"capacity": 10}, flat={"proposed_magnitude": 50}))
    assert not _fired(res)
    missing = [r for r in res if r.metadata.get("rule_id") == "world_variable_missing"]
    assert len(missing) == 1
    assert missing[0].metadata["field"] == "storage_now"
    assert missing[0].metadata["source_rule_id"] == "r1"
    assert missing[0].valid and missing[0].metadata["grounding"] == "world"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "abc", None, [1], {"a": 1}])
def test_unusable_value_does_not_fire_and_is_audited(tmp_path, bad):
    v = _validator(tmp_path, [_rule(OVERFLOW)])
    env = {"storage_now": bad, "capacity": 10}
    res = _thinking(v, _context(env, flat={"proposed_magnitude": 50}))
    assert not _fired(res)
    unusable = [r for r in res if r.metadata.get("rule_id") == "world_variable_unusable"]
    assert len(unusable) == 1
    meta = unusable[0].metadata
    assert meta["field"] == "storage_now" and meta["source_rule_id"] == "r1"
    assert meta["value_repr"] == repr(bad)
    assert meta["grounding"] == "world" and meta["world_rules_unreadable"] == 1
    assert unusable[0].validator_name == "AgentValidator:thinking_world_variable_unusable"
    assert unusable[0].valid and "not a finite number" in unusable[0].warnings[0]
    assert not [r for r in res if r.metadata.get("rule_id") == "world_variable_missing"]


def test_numeric_string_is_coerced_and_bool_is_usable(tmp_path):
    v = _validator(tmp_path, [_rule(OVERFLOW), _rule("flag == True and n > 1", "r2")])
    res = _thinking(v, _context({"storage_now": "9.5", "capacity": 10, "flag": True},
                                flat={"proposed_magnitude": "50", "n": 2}))
    assert _fired(res) and _fired(res, "r2")
    assert not [r for r in res if "world_variable" in str(r.metadata.get("rule_id"))]
    res = _thinking(v, _context({"storage_now": 1, "capacity": 10, "flag": False},
                                flat={"proposed_magnitude": 50, "n": 2}))
    assert not _fired(res, "r2")


def test_numpy_scalars_convert():
    np = pytest.importorskip("numpy")
    c = compile_expression_condition("x > 1 and y == True")
    out = evaluate_expression_condition(c, {}, {"x": np.float64(2.0), "y": np.True_})
    assert out.matched and out.readable


# ---------------------------------------------------------------------------
# 3. same behaviour in all three evaluators
# ---------------------------------------------------------------------------

CASES = [
    # (id, env, state, flat, expression, expected)
    ("fires", {"storage_now": 9.5, "capacity": 10}, {}, {"proposed_magnitude": 50}, OVERFLOW, True),
    ("below", {"storage_now": 5, "capacity": 10}, {}, {"proposed_magnitude": 50}, OVERFLOW, False),
    ("proposal_high", {"storage_now": 9.5, "capacity": 10}, {}, {"proposed_magnitude": 100}, OVERFLOW, False),
    ("missing", {"capacity": 10}, {}, {"proposed_magnitude": 50}, OVERFLOW, False),
    ("none", {"storage_now": None, "capacity": 10}, {}, {"proposed_magnitude": 50}, OVERFLOW, False),
    ("nan", {"storage_now": float("nan"), "capacity": 10}, {}, {"proposed_magnitude": 50}, OVERFLOW, False),
    ("str_num", {"storage_now": "9.5", "capacity": 10}, {}, {"proposed_magnitude": 50}, OVERFLOW, True),
    ("zero_eq", {"storage_now": 0}, {}, {}, "storage_now == 0", True),
    ("guard", {"storage_now": 3, "capacity": 0}, {}, {}, "capacity > 0 and storage_now / capacity > 0.9", False),
    ("state_only", {}, {"budget": 7}, {}, "budget >= 7", True),
    ("bool_var", {"flag": True}, {}, {}, "flag == True", True),
    ("or_chain", {"a": 1, "b": 5}, {}, {}, "a > 3 or b > 3", True),
    ("chained", {"a": 2}, {}, {}, "1 < a < 3", True),
    ("floor_mod", {"a": 7}, {}, {}, "a // 2 == 3 and a % 2 == 1", True),
]
ZERO_DIV = ("zero_div", {"storage_now": 3, "capacity": 0}, {}, {}, "storage_now / capacity > 1")


def _evaluators(tmp_path, expr, ctx):
    """Yield (name, callable -> matched bool) for every evaluator + shape."""
    v = _validator(tmp_path, [_rule(expr)])
    tv = ThinkingValidator(framework="", builtin_checks=[])
    dict_cond = {"expression": expr}
    pyd_cond = PydanticRuleCondition(expression=expr)
    dc_cond = RuleCondition.from_dict({"expression": expr})

    def agent():
        return _fired(_thinking(v, ctx))

    def thinking(cond):
        return lambda: tv._evaluate_conditions([cond], {}, ctx, "", [], rule_id="r1")

    yield "agent_validator", agent
    yield "thinking_dict", thinking(dict_cond)
    yield "thinking_pydantic", thinking(pyd_cond)
    yield "thinking_dataclass", thinking(dc_cond)
    yield "rule_condition", lambda: dc_cond.evaluate(ctx)


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_all_evaluators_agree(tmp_path, case):
    _id, env, state, flat, expr, expected = case
    ctx = _context(env, state, flat)
    got = {name: fn() for name, fn in _evaluators(tmp_path, expr, ctx)}
    assert got == {name: expected for name in got}, got


def test_all_evaluators_raise_on_zero_divisor(tmp_path):
    _id, env, state, flat, expr = ZERO_DIV
    ctx = _context(env, state, flat)
    for name, fn in _evaluators(tmp_path, expr, ctx):
        with pytest.raises(ExpressionEvaluationError):
            fn()


def test_thinking_validator_warns_once_and_records_the_expression(caplog):
    import logging
    from broker.validators.governance import thinking_validator as tvm

    tv = ThinkingValidator(framework="", builtin_checks=[])
    tvm._WARNED_MISSING_WORLD_VARIABLE.discard(("warn_rule", "storage_now"))
    tvm._WARNED_UNUSABLE_WORLD_VARIABLE.discard(("warn_rule", "capacity"))
    ctx = _context({"capacity": "abc"}, flat={"proposed_magnitude": 1})
    with caplog.at_level(logging.WARNING, logger=tvm.__name__):
        for _ in range(2):
            assert tv._evaluate_conditions(
                [{"expression": OVERFLOW}], {}, ctx, "", [], rule_id="warn_rule") is False
    msgs = [r.getMessage() for r in caplog.records]
    assert sum("storage_now" in m for m in msgs) == 1
    assert sum("capacity" in m for m in msgs) == 1
    matched = []
    ok = {"storage_now": 9.5, "capacity": 10}
    assert tv._evaluate_conditions([{"expression": OVERFLOW}], {},
                                   _context(ok, flat={"proposed_magnitude": 1}),
                                   "", matched, rule_id="warn_rule")
    assert matched == [OVERFLOW]


def test_thinking_validator_yaml_rule_end_to_end():
    tv = ThinkingValidator(framework="", builtin_checks=[])
    rule = SimpleNamespace(
        id="r1", blocked_skills=["release"], level="ERROR", message="no",
        conditions=[{"expression": OVERFLOW}], category="thinking", framework=None)
    ctx = {**_context({"storage_now": 9.5, "capacity": 10}, flat={"proposed_magnitude": 1}),
           "reasoning": {}}
    out = tv._validate_yaml_rules("release", [rule], ctx, "")
    assert [r.metadata["rule_id"] for r in out] == ["r1"]
    assert out[0].metadata["grounding"] == "world"
    assert out[0].metadata["conditions_matched"] == [OVERFLOW]


# ---------------------------------------------------------------------------
# 4. scope
# ---------------------------------------------------------------------------

def test_scope_state_reads_agent_value_when_env_has_the_same_name(tmp_path):
    ctx = _context(env={"x": 100}, state={"x": 1})
    # the flattened copy resolves to env (the key-collision trap) ...
    assert ctx["x"] == 100
    v = _validator(tmp_path, [_rule("x > 50", "auto_r"),
                              _rule("x > 50", "state_r", scope="state"),
                              _rule("x > 50", "env_r", scope="env"),
                              _rule("x > 50", "ctx_r", scope="context")])
    res = _thinking(v, ctx)
    assert _fired(res, "auto_r") and _fired(res, "env_r") and _fired(res, "ctx_r")
    assert not _fired(res, "state_r")          # reads the agent's 1


def test_scope_auto_order_env_then_state_then_context():
    c = compile_expression_condition("x == 1")
    ctx = {"env_state": {}, "x": 3}
    assert evaluate_expression_condition(c, {"x": 2}, ctx).matched is False   # state wins over ctx
    assert evaluate_expression_condition(c, {}, {"env_state": {"x": 1}, "x": 3}).matched
    c3 = compile_expression_condition("x == 3")
    assert evaluate_expression_condition(c3, {}, ctx).matched                  # ctx last


def test_scope_social_and_proposed_magnitude_from_context():
    c = compile_expression_condition({"expression": "adoption > 0.5", "scope": "social"})
    assert evaluate_expression_condition(
        c, {}, {"social_context": {"adoption": 0.7}}).matched
    pm = compile_expression_condition("proposed_magnitude < 100")
    assert evaluate_expression_condition(pm, {}, {"proposed_magnitude": 50}).matched
    out = evaluate_expression_condition(pm, {}, {})
    assert out.missing == ("proposed_magnitude",) and not out.readable


# ---------------------------------------------------------------------------
# 5. build time
# ---------------------------------------------------------------------------

def test_bad_expression_fails_at_config_load_naming_the_rule(tmp_path):
    AgentTypeConfig.clear_cache()
    path = _write_config(tmp_path, [_rule("abs(x) > 1", rule_id="typo_rule")])
    with pytest.raises(ExpressionConditionError, match="typo_rule"):
        AgentTypeConfig.load(path, force_reload=True)


def test_bad_expression_in_top_level_governance_shape(tmp_path):
    AgentTypeConfig.clear_cache()
    cfg = {"global_config": {}, "op": {"agent_type": "op"},
           "governance": {"strict": {"op": {"thinking_rules": {
               "dict_rule": {"conditions": [{"expression": "a +"}],
                             "blocked_skills": ["release"]}}}}}}
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(ExpressionConditionError, match="dict_rule"):
        AgentTypeConfig.load(str(p), force_reload=True)


def test_expression_in_identity_rules_raises(tmp_path):
    AgentTypeConfig.clear_cache()
    path = _write_config(tmp_path, [_rule(OVERFLOW, rule_id="id_rule")], kind="identity_rules")
    with pytest.raises(ExpressionConditionError, match="thinking_rules"):
        AgentTypeConfig.load(path, force_reload=True)


def test_good_expression_loads(tmp_path):
    AgentTypeConfig.clear_cache()
    cfg = AgentTypeConfig.load(_write_config(tmp_path, [_rule(OVERFLOW)]), force_reload=True)
    rules = cfg.get_thinking_rules("op")
    assert [r.id for r in rules] == ["r1"] and rules[0].grounding == "world"


# ---------------------------------------------------------------------------
# 6. empty reasoning
# ---------------------------------------------------------------------------

def test_expression_rule_fires_with_empty_reasoning(tmp_path):
    v = _validator(tmp_path, [_rule(OVERFLOW)])
    ctx = _context({"storage_now": 9.5, "capacity": 10}, flat={"proposed_magnitude": 50})
    for reasoning in ({}, None):
        res = v.validate("op", "A1", "release", ctx["state"], None, reasoning, "",
                         full_validation_context=ctx)
        assert _fired(res), reasoning


def test_construct_only_thinking_rule_still_skipped_with_empty_reasoning(tmp_path):
    construct_rule = {"id": "c1", "conditions": [{"construct": "TP", "values": ["H"]}],
                      "blocked_skills": ["release"], "level": "ERROR", "message": "m"}
    v = _validator(tmp_path, [construct_rule])
    ctx = _context()
    # no reasoning: nothing from the thinking tier (today's behaviour)
    baseline = v.validate("op", "A1", "release", {}, None, {}, "", full_validation_context=ctx)
    assert "c1" not in _ids(baseline)
    assert not [r for r in baseline if str(r.validator_name).startswith("AgentValidator:thinking")]
    # and the flag-path itself returns nothing for a construct-only config
    assert v.validate_thinking("op", "A1", "release", {}, {}, full_context=ctx,
                               expression_rules_only=True) == []
    # with reasoning it still fires, so the rule is live
    fired = v.validate("op", "A1", "release", {}, None, {"TP": "H"}, "", full_validation_context=ctx)
    assert "c1" in _ids(fired)


def test_mixed_config_empty_reasoning_runs_only_expression_rules(tmp_path):
    construct_rule = {"id": "c1", "conditions": [{"construct": "TP", "values": ["M"]}],
                      "blocked_skills": ["release"], "level": "ERROR", "message": "m"}
    v = _validator(tmp_path, [construct_rule, _rule(OVERFLOW)])
    ctx = _context({"storage_now": 9.5, "capacity": 10}, flat={"proposed_magnitude": 50})
    res = v.validate("op", "A1", "release", {}, None, {}, "", full_validation_context=ctx)
    assert _fired(res, "r1") and "c1" not in _ids(res)


# ---------------------------------------------------------------------------
# 7. grounding
# ---------------------------------------------------------------------------

def test_grounding_is_world():
    rule = {"id": "r", "conditions": [{"expression": OVERFLOW}]}
    assert resolve_rule_grounding(rule) == "world"
    assert resolve_rule_grounding({"id": "r", "conditions": [{"construct": "TP"}]}) == "self_report"
    cond_rule = SimpleNamespace(grounding="", conditions=[{"expression": OVERFLOW}])
    assert ThinkingValidator._rule_grounding(cond_rule) == "world"
    assert ThinkingValidator._rule_grounding(
        SimpleNamespace(grounding="", conditions=[PydanticRuleCondition(expression=OVERFLOW)])) == "world"
    assert ThinkingValidator._rule_grounding(
        SimpleNamespace(grounding="", conditions=[RuleCondition.from_dict({"expression": OVERFLOW})])) == "world"


def test_agent_validator_stamps_world_grounding_on_the_firing(tmp_path):
    v = _validator(tmp_path, [_rule(OVERFLOW)])
    res = _thinking(v, _context({"storage_now": 9.5, "capacity": 10},
                                flat={"proposed_magnitude": 1}))
    assert [r.metadata["grounding"] for r in res if r.metadata.get("rule_id") == "r1"] == ["world"]


# ---------------------------------------------------------------------------
# 8. SafeExpressionEvaluator
# ---------------------------------------------------------------------------

def test_default_evaluator_still_swaps_zero_for_epsilon():
    assert SafeExpressionEvaluator.evaluate("x / y > 1", {"x": 1.0, "y": 0}) is True
    assert SafeExpressionEvaluator.evaluate("y == 0", {"y": 0}) is False   # swapped: the old quirk


def test_zero_guard_off_raises_and_compares_real_values():
    with pytest.raises(ZeroDivisionError):
        SafeExpressionEvaluator.evaluate("x / y > 1", {"x": 1.0, "y": 0}, zero_guard=False)
    assert SafeExpressionEvaluator.evaluate("y == 0", {"y": 0}, zero_guard=False) is True


# ---------------------------------------------------------------------------
# 9. reservoir
# ---------------------------------------------------------------------------

def _old_overflow(storage_now, capacity, proposed):
    """The retired Python check, copied here as the reference."""
    return float(storage_now) > 0.9 * float(capacity) and float(proposed) < 100.0


def test_reservoir_yaml_rule_matches_the_old_formula_on_a_grid(tmp_path):
    from examples.reservoir_control.ops_modules import ToyMassBalanceReservoir
    cap = ToyMassBalanceReservoir.CAPACITY
    v = _validator(tmp_path, [_rule(OVERFLOW)])
    storages = [0.0, 0.5 * cap, 0.9 * cap - 1e-9, 0.9 * cap, 0.9 * cap + 1e-9, cap]
    proposals = [0, 50, 99.9, 100, 120]
    for s, p in itertools.product(storages, proposals):
        res = _thinking(v, _context({"storage_now": s, "capacity": cap},
                                    flat={"proposed_magnitude": p}))
        assert _fired(res) == _old_overflow(s, cap, p), (s, p)


def test_real_reservoir_config_blocks_set_release_when_nearly_full():
    import examples.reservoir_control  # noqa: F401
    from examples.reservoir_control.ops_modules import ToyMassBalanceReservoir
    from pathlib import Path
    import examples.reservoir_control as pkg

    path = Path(pkg.__file__).parent / "config" / "reservoir_agent_types.yaml"
    AgentTypeConfig.clear_cache()
    import os
    old = os.environ.get("GOVERNANCE_PROFILE")
    os.environ["GOVERNANCE_PROFILE"] = "strict"
    try:
        v = AgentValidator(config_path=str(path))
        cap = ToyMassBalanceReservoir.CAPACITY
        ctx = _context({"storage_now": 0.95 * cap, "capacity": cap},
                       flat={"proposed_magnitude": 50})
        ctx["agent_type"] = "operator"
        res = v.validate("operator", "OPERATOR", "set_release", ctx["state"], None, {}, "",
                         full_validation_context=ctx)
        blocked = [r for r in res if r.metadata.get("rule_id") == "flood_control_overflow"]
        assert len(blocked) == 1 and not blocked[0].valid
        assert "flood control" in blocked[0].errors[0]
        ctx["proposed_magnitude"] = 100
        res = v.validate("operator", "OPERATOR", "set_release", ctx["state"], None, {}, "",
                         full_validation_context=ctx)
        assert "flood_control_overflow" not in _ids(res)
    finally:
        AgentTypeConfig.clear_cache()
        if old is None:
            os.environ.pop("GOVERNANCE_PROFILE", None)
        else:
            os.environ["GOVERNANCE_PROFILE"] = old


# ---------------------------------------------------------------------------
# 10. RuleCondition round trip
# ---------------------------------------------------------------------------

def test_rule_condition_round_trip_with_expression():
    cond = RuleCondition.from_dict({"expression": OVERFLOW, "scope": "env"})
    assert cond.type == "expression" and cond.expression == OVERFLOW and cond.scope == "env"
    out = cond.to_dict()
    assert out["expression"] == OVERFLOW and out["scope"] == "env"
    again = RuleCondition.from_dict(out)
    assert (again.expression, again.scope, again.type) == (OVERFLOW, "env", "expression")


def test_rule_condition_bad_expression_fails_at_build():
    with pytest.raises(ExpressionConditionError):
        RuleCondition.from_dict({"expression": "abs(x) > 1"})
    with pytest.raises(ExpressionConditionError):
        RuleCondition.from_dict({"expression": "a > 1", "field": "a"})
    with pytest.raises(ExpressionConditionError):
        RuleCondition(type="expression", field="", expression="x +")


def test_old_style_rule_condition_to_dict_is_unchanged():
    cond = RuleCondition.from_dict({"type": "construct", "field": "TP", "operator": "in",
                                    "values": ["H"]})
    assert cond.to_dict() == {"type": "construct", "field": "TP", "operator": "in",
                              "values": ["H"]}
    assert cond.expression is None and cond.scope == "auto"
    old_expr_type = RuleCondition(type="expression", field="budget", operator=">=", values=[5])
    assert old_expr_type.evaluate({"state": {"budget": 6}}) is True   # field form unchanged
    assert "expression" not in old_expr_type.to_dict()


def test_missing_sentinel_is_stable():
    from broker.validators.agent import agent_validator as av
    assert av._MISSING is MISSING
    assert av._lookup_world_variable("x", "auto", {}, {}) is MISSING
    assert not MISSING and repr(MISSING) == "MISSING"
    assert math.isfinite(1.0)


# ---------------------------------------------------------------------------
# review round 1 (opus): the three must-fix findings, each pinned
# ---------------------------------------------------------------------------

def test_scope_state_agrees_on_the_broker_shaped_context(tmp_path):
    """The broker puts the agent's state under ``agent_state`` and has no
    top-level ``state`` key; every plane must still read it for scope: state."""
    expr = "budget >= 7"
    ctx = {"env_state": {"budget": 1}, "agent_state": {"state": {"budget": 9}},
           "agent_type": "op", "budget": 1}
    v = _validator(tmp_path, [_rule(expr, scope="state")])
    proposal = SimpleNamespace(skill_name="release", agent_id="A1",
                               reasoning={}, parse_layer="")
    assert _fired(v.validate(proposal, ctx, None))
    tv = ThinkingValidator(framework="", builtin_checks=[])
    for cond in ({"expression": expr, "scope": "state"},
                 PydanticRuleCondition(expression=expr, scope="state"),
                 RuleCondition.from_dict({"expression": expr, "scope": "state"})):
        assert tv._evaluate_conditions([cond], {}, ctx, "", [], rule_id="r1") is True
    assert RuleCondition.from_dict({"expression": expr, "scope": "state"}).evaluate(ctx) is True


def test_validate_prompt_accepts_an_expression_condition():
    from broker.tools.validate_prompt import check_rule_shapes
    cfg = {"op": {"thinking_rules": [_rule("storage_now > 0.9 * capacity", scope="env")]}}
    msgs = [i.message for i in check_rule_shapes(cfg)]
    assert not any("ignored key" in m for m in msgs), msgs


@pytest.fixture
def zero_divisor_run_args(tmp_path):
    cfg_dir = tmp_path / "cfg"
    shutil.copytree(ops_case.CONFIG_PATH.parent, cfg_dir)
    yml = cfg_dir / ops_case.CONFIG_PATH.name
    text = yml.read_text(encoding="utf-8")
    assert OVERFLOW in text
    yml.write_text(text.replace(
        OVERFLOW, "storage_now / (capacity - capacity) > 0.9 and proposed_magnitude < 100"),
        encoding="utf-8")
    module = ops_case.__name__
    return [
        str(yml), "--years", "2", "--output", str(tmp_path / "out"),
        "--slot", f"world={module}:build_world",
        "--slot", f"agents={module}:build_agents",
        "--slot", f"hooks={module}:build_hooks",
        "--slot", f"mock={module}:operator_mock",
    ]


def test_zero_divisor_stops_a_real_run(zero_divisor_run_args):
    """Through ExperimentRunner: the step handler must not turn it into an
    ABORTED row and keep going."""
    AgentTypeConfig.clear_cache()
    try:
        with pytest.raises(ExpressionEvaluationError, match="flood_control_overflow"):
            broker.run.main(zero_divisor_run_args)
    finally:
        AgentTypeConfig.clear_cache()


def test_zero_divisor_stops_a_parallel_run(zero_divisor_run_args, monkeypatch):
    """Same as above on the parallel step handler (workers=2)."""
    import dataclasses
    from broker.core.experiment_runner import ExperimentRunner

    # The builder refuses workers>1 for a contract with feasibility bounds
    # (R1 slice 2); this test is about the expression path, so drop them.
    orig_contract = ops_case.build_contract
    monkeypatch.setattr(ops_case, "build_contract",
                        lambda: dataclasses.replace(orig_contract(), feasibility=()))
    calls = []
    orig_parallel = ExperimentRunner._run_agents_parallel

    def spy(self, *a, **k):
        calls.append(self.config.workers)
        return orig_parallel(self, *a, **k)

    monkeypatch.setattr(ExperimentRunner, "_run_agents_parallel", spy)
    AgentTypeConfig.clear_cache()
    try:
        with pytest.raises(ExpressionEvaluationError, match="flood_control_overflow"):
            broker.run.main([*zero_divisor_run_args, "--workers", "2"])
    finally:
        AgentTypeConfig.clear_cache()
    assert calls, "the parallel step handler was not used"


def test_parse_error_message_is_bounded():
    deep = " + ".join(["x"] * 30000) + " > 1"
    with pytest.raises(ExpressionConditionError) as info:
        compile_expression_condition({"expression": deep}, where="rule 'deep'")
    assert len(str(info.value)) < 400


def test_too_deep_expression_fails_at_load_not_mid_run():
    deep = " + ".join(["x"] * 30000) + " > 1"
    with pytest.raises(ExpressionConditionError):
        compile_expression_condition({"expression": deep}, where="rule 'deep'")


def test_bytes_value_is_unusable_and_repr_is_bounded():
    compiled = compile_expression_condition({"expression": "x > 1"})
    out = evaluate_expression_condition(compiled, {}, {"env_state": {"x": b"5"}})
    assert out.readable is False and out.unusable[0][0] == "x"
    out = evaluate_expression_condition(compiled, {}, {"env_state": {"x": list(range(10000))}})
    assert out.readable is False and len(out.unusable[0][1]) < 200
