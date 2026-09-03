"""PR-8: the decider registry — heterogeneous populations, one pipeline.

The audit finding behind this file: ``process_step(llm_invoke=...)`` was
already a decider-agnostic seam, and a non-LLM agent already flowed
through identical validation and audit — but the only way to USE that
was to reach into a live runner from an example script and replace its
invoke function. A monkeypatch is not a capability. It cannot be
declared, cannot be reviewed in a config diff, leaves no trace in the
audit CSV saying which agents it touched, and cannot be reproduced by
anyone who did not read the script.

What is pinned here:

* the default is byte-safe by IDENTITY, not by behaviour. An agent type
  with no ``decider:`` resolves to the very object ``get_llm_invoke``
  returns, so every frozen corpus reruns unchanged;
* every built-in decider produces something the governance pipeline
  accepts, and the audit row records WHICH decider produced it;
* a hybrid records which of its two paths answered, per row — without
  that column a hybrid arm is indistinguishable in the CSV from either
  pure arm, and the run cannot be read;
* an unregistered decider name is refused at config time AND at run
  time, and never falls back to ``llm``. A silent fallback would turn
  a mixed-population config into an all-LLM run with nothing in the
  artifacts saying so.

Falsification: every ON test here fails against pre-PR-8 code, which
has no ``broker.agents.deciders`` module at all.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from broker.agents.deciders import (
    BUILTIN_DEFAULT_PATHS,
    DEFAULT_DECIDER_NAME,
    DEFAULT_DECIDER_SPEC,
    DeciderRegistry,
    DeciderSpec,
    DecisionContext,
    build_rule_table,
    clear_decider_path,
    note_decider_path,
    parse_decider_spec,
    register_domain_deciders,
    take_decider_path,
)
from broker.core.run_integrity import (
    get_decider_row_counts,
    note_decider_row,
    reset_decider_row_counts,
)
from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry
from broker.interfaces.skill_types import SkillProposal
from broker.tools.validate_prompt import (
    KNOWN_AUDIT_KEYS,
    check_decider_declarations,
)
from broker.utils.agent_config import AgentTypeConfig


# ---------------------------------------------------------------------------
# Fixtures — hand-built configs and agents, no YAML on disk
# ---------------------------------------------------------------------------

def _config(agent_types: dict, global_config: dict | None = None) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = dict(agent_types)
    if global_config is not None:
        cfg._config["global_config"] = global_config
    cfg._non_default_deciders = None
    return cfg


def _agent(agent_id="A1", agent_type="worker", **attrs):
    return SimpleNamespace(
        id=agent_id, agent_type=agent_type,
        custom_attributes=dict(attrs), fixed_attributes={}, dynamic_state={},
    )


def _profile_agent(agent_id="A1", agent_type="worker", **profile):
    """An agent whose PROFILE fields sit where a real domain puts them.

    ``fixed_attributes`` is where ``wrap_household`` and every loader
    like it put flood_zone / tenure / tp_score / property_value. Review
    P0-A: the resolver did not look there, so a rule about any profile
    field was permanently false — and the fixture above, which puts
    everything in ``custom_attributes``, could not see that. Both shapes
    are now pinned.
    """
    return SimpleNamespace(
        id=agent_id, agent_type=agent_type,
        custom_attributes={}, fixed_attributes=dict(profile), dynamic_state={},
    )


def _llm(reply="LLM SAID SO"):
    calls = []

    def invoke(prompt, **kw):
        calls.append(prompt)
        return reply

    invoke.calls = calls
    return invoke


@pytest.fixture(autouse=True)
def _clean_registry():
    """Every test starts from the built-ins and a clear path slot.

    The DomainPack registry is restored too: it is class-level state,
    and a probe pack left behind here would show up in whichever
    unrelated test enumerates registered domains next.
    """
    packs = dict(DomainPackRegistry._packs)
    DeciderRegistry.reset_to_builtins()
    clear_decider_path()
    reset_decider_row_counts()
    yield
    DomainPackRegistry._packs = packs
    DeciderRegistry.reset_to_builtins()
    clear_decider_path()
    reset_decider_row_counts()


# ---------------------------------------------------------------------------
# Declaration parsing
# ---------------------------------------------------------------------------

class TestDeciderSpecParsing:
    def test_absent_is_the_llm_default(self):
        assert parse_decider_spec(None) is DEFAULT_DECIDER_SPEC
        assert DEFAULT_DECIDER_SPEC.is_default

    def test_bare_name_and_mapping_forms(self):
        assert parse_decider_spec("rule_based") == DeciderSpec("rule_based", {})
        spec = parse_decider_spec({"name": "hybrid", "params": {"rules": []}})
        assert spec.name == "hybrid" and spec.params == {"rules": []}

    def test_llm_with_params_is_refused(self):
        # Review C2. `llm` reads no params, so params on it are dead
        # config — and they used to make two definitions of "is this the
        # default" disagree: DeciderSpec.is_default said no (params are
        # present) while has_non_default_deciders said yes (the name is
        # llm), so the audit columns stayed OFF for a run whose
        # process_step call had gained a `decider=` keyword. Refusing the
        # shape makes the two coincide by construction.
        with pytest.raises(ValueError, match="takes no params"):
            parse_decider_spec({"name": "llm", "params": {"x": 1}}, where="worker")
        assert parse_decider_spec({"name": "llm", "params": {}}).is_default

    def test_the_two_default_definitions_cannot_disagree(self):
        from broker.agents.deciders import DEFAULT_DECIDER_NAME
        for value in ("llm", {"name": "llm"}, {"name": "llm", "params": {}}, None):
            spec = parse_decider_spec(value)
            assert spec.is_default is (spec.name == DEFAULT_DECIDER_NAME)

    @pytest.mark.parametrize("bad", ["", "   ", 7, [], {"params": {}}, {"name": ""},
                                     {"name": "x", "params": 3}])
    def test_malformed_raises_instead_of_defaulting(self, bad):
        # Reading an unusable value as `llm` is the failure this rejects:
        # the run would start, finish, and produce an all-LLM corpus from
        # a config that asked for a mixed one.
        with pytest.raises(ValueError):
            parse_decider_spec(bad, where="worker")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_builtins_are_registered(self):
        assert set(DeciderRegistry.names()) == {
            "llm", "rule_based", "hybrid", "parametric"}

    def test_register_and_unregister(self):
        DeciderRegistry.register("stub", lambda cfg, rt: (lambda p: "x"))
        assert DeciderRegistry.has("stub")
        DeciderRegistry.unregister("stub")
        assert not DeciderRegistry.has("stub")

    def test_duplicate_name_needs_explicit_replace(self):
        DeciderRegistry.register("stub", lambda cfg, rt: (lambda p: "x"))
        with pytest.raises(ValueError, match="already registered"):
            DeciderRegistry.register("stub", lambda cfg, rt: (lambda p: "y"))
        DeciderRegistry.register("stub", lambda cfg, rt: (lambda p: "y"), replace=True)

    def test_unknown_name_raises_and_names_what_is_available(self):
        with pytest.raises(KeyError) as exc:
            DeciderRegistry.get("nope")
        message = str(exc.value)
        assert "nope" in message and "rule_based" in message
        assert "nothing falls back" in message

    def test_factory_returning_a_non_callable_is_caught_at_build(self):
        DeciderRegistry.register("broken", lambda cfg, rt: "not a function")
        with pytest.raises(TypeError, match="not a callable"):
            DeciderRegistry.build(DeciderSpec("broken"), {}, {})


class TestLlmDefaultIsTheSameObject:
    def test_build_returns_the_identical_callable(self):
        invoke = _llm()
        built = DeciderRegistry.build(DEFAULT_DECIDER_SPEC, {}, {"llm_invoke": invoke})
        # `is`, not `==`: a wrapper would pass every behavioural test and
        # still be a new object in the hot path of every frozen corpus.
        assert built is invoke

    def test_missing_llm_invoke_is_an_error_not_a_stub(self):
        with pytest.raises(ValueError, match="llm_invoke"):
            DeciderRegistry.build(DEFAULT_DECIDER_SPEC, {}, {})


# ---------------------------------------------------------------------------
# Rule tables
# ---------------------------------------------------------------------------

class TestRuleTable:
    def test_first_match_wins_in_declaration_order(self):
        table = build_rule_table({"rules": [
            {"id": "a", "action": "act_a", "when": {"zone": "HIGH"}},
            {"id": "b", "action": "act_b", "when": {"zone": "HIGH"}},
        ]}, where="t")
        ctx = DecisionContext(_agent(zone="HIGH"))
        assert [r.rule_id for r in table if r.matches(ctx)][0] == "a"

    @pytest.mark.parametrize("cond,value,expected", [
        ({"gte": 2}, 2, True), ({"gte": 2}, 1, False),
        ({"gt": 2}, 2, False), ({"lte": 1}, 1, True), ({"lt": 1}, 1, False),
        ({"in": ["A", "B"]}, "A", True), ({"in": ["A"]}, "C", False),
        ({"not_in": ["A"]}, "C", True), ({"not_in": ["A"]}, "A", False),
        ({"ne": 3}, 4, True), ("HIGH", "HIGH", True), ("HIGH", "LOW", False),
        (["A", "B"], "B", True),
    ])
    def test_operators(self, cond, value, expected):
        table = build_rule_table(
            {"rules": [{"action": "x", "when": {"f": cond}}]}, where="t")
        assert table[0].matches(DecisionContext(_agent(f=value))) is expected

    def test_a_field_the_agent_does_not_carry_never_matches(self):
        # Absence must not read as a match. Treating a missing field as
        # satisfied would fire the rule on every agent of a type that
        # never had the field, which looks like a working rule.
        table = build_rule_table(
            {"rules": [{"action": "x", "when": {"absent_field": {"gte": 1}}}]},
            where="t")
        assert table[0].matches(DecisionContext(_agent())) is False

    def test_an_uncomparable_condition_does_not_fire(self, caplog):
        table = build_rule_table(
            {"rules": [{"action": "x", "when": {"f": {"gte": 2}}}]}, where="t")
        assert table[0].matches(DecisionContext(_agent(f="HIGH"))) is False

    def test_unknown_operator_is_refused_at_evaluation(self):
        table = build_rule_table(
            {"rules": [{"action": "x", "when": {"f": {"approximately": 2}}}]},
            where="t")
        with pytest.raises(ValueError, match="unknown operator"):
            table[0].matches(DecisionContext(_agent(f=2)))

    @pytest.mark.parametrize("params,match", [
        ({}, "no 'rules' declared"),
        ({"rules": "not a list"}, "must be a list"),
        ({"rules": [{"when": {}}]}, "non-empty 'action'"),
        ({"rules": [{"action": "x", "when": 3}]}, "'when' must be a mapping"),
    ])
    def test_malformed_tables_are_refused_at_build(self, params, match):
        with pytest.raises(ValueError, match=match):
            build_rule_table(params, where="t")


class TestDecisionContext:
    def test_identity_then_environment_then_agent(self):
        agent = _agent("A9", "worker", zone="HIGH")
        agent.dynamic_state["stock"] = 4
        agent.tenure = "Owner"
        ctx = DecisionContext(agent, {"season": "dry", "zone": "GLOBAL"},
                              "A9", "worker")
        assert ctx.resolve("agent_id") == "A9"
        assert ctx.resolve("agent_type") == "worker"
        # Review P2: the ENVIRONMENT wins a shared name under `auto`. The
        # agent's copy of a world variable is typically refreshed at the
        # END of the period, so an agent-first read answers a rule about
        # this period with last period's number.
        assert ctx.resolve("zone") == "GLOBAL"
        assert ctx.resolve("zone", "agent") == "HIGH"
        assert ctx.resolve("zone", "env") == "GLOBAL"
        assert ctx.resolve("stock") == 4
        assert ctx.resolve("tenure") == "Owner"   # a plain attribute
        assert ctx.resolve("season") == "dry"

    def test_profile_fields_in_fixed_attributes_resolve(self):
        # Review P0-A. This is where every real domain loader puts the
        # profile — `wrap_household` puts flood_zone / tenure / tp_score /
        # property_value there — and the resolver did not look, so every
        # rule written against a profile field was permanently false and
        # the shipped rule-based arm answered every row with its default.
        agent = _profile_agent("H0001", "household_renter",
                               flood_zone="HIGH", tenure="Renter",
                               tp_score=3.5, property_value=250_000)
        ctx = DecisionContext(agent, {}, "H0001", "household_renter")
        assert ctx.resolve("flood_zone") == "HIGH"
        assert ctx.resolve("tenure") == "Renter"
        assert ctx.resolve("tp_score") == 3.5
        assert ctx.resolve("property_value") == 250_000

    def test_holder_order_matches_the_context_builder(self):
        from broker.agents.deciders import _AGENT_STATE_HOLDERS
        # The order InteractionHub.build_tiered_context composes them in.
        assert _AGENT_STATE_HOLDERS == (
            "custom_attributes", "fixed_attributes", "dynamic_state")

    def test_an_unknown_scope_is_refused(self):
        ctx = DecisionContext(_agent(), {}, "A1", "worker")
        with pytest.raises(ValueError, match="unknown scope"):
            ctx.resolve("stock", "environment")

    def test_a_nan_field_resolves_as_missing(self):
        """P1 (silent-failure hunter): a NaN value — a blank cell in a
        per-agent CSV column, most often — must resolve to _MISSING, not
        to itself. Left unguarded, `not_in` is trivially SATISFIED by
        NaN: nothing equals NaN, so `NaN not in [LOW]` is True, and a
        blank `flood_zone` cell would read as "definitely not LOW"."""
        agent = _agent(zone=float("nan"))
        ctx = DecisionContext(agent, {}, "A1", "worker")
        from broker.agents.deciders import _MISSING
        assert ctx.resolve("zone") is _MISSING

    def test_falsification_a_not_in_rule_used_to_be_satisfied_by_nan(self):
        """Falsify against the pre-fix code path directly: without the
        NaN coercion, `resolve()` would have returned the raw NaN float,
        and `_match_one` — which only special-cases the `_MISSING`
        sentinel, never NaN — would have matched a `not_in: [LOW]`
        condition on it. Recreated inline (the old `resolve()` body no
        longer exists) rather than imported, and then checked against
        the REAL, current `DecisionRule.matches`."""
        from broker.agents.deciders import _MISSING

        def _resolve_pre_fix(ctx, field_name):
            # The exact body `resolve()` had before this fix: whatever
            # the identity/env/agent lookup found, returned as-is.
            if field_name in ctx.identity:
                return ctx.identity[field_name]
            if field_name in ctx.env:
                return ctx.env[field_name]
            return ctx._resolve_agent(field_name)

        agent = _agent(flood_zone=float("nan"))
        ctx = DecisionContext(agent, {}, "H0001", "household_renter")
        pre_fix_value = _resolve_pre_fix(ctx, "flood_zone")
        assert isinstance(pre_fix_value, float) and pre_fix_value != pre_fix_value  # NaN
        pre_fix_matches = pre_fix_value is not _MISSING and pre_fix_value not in ["LOW"]
        assert pre_fix_matches is True, (
            "pre-fix, a NaN flood_zone DOES satisfy not_in: [LOW] — that "
            "is the bug this test falsifies against"
        )

        # POST-FIX: the same rule, through the real (current) resolver
        # and the real DecisionRule.matches — does NOT fire, because the
        # field now resolves to _MISSING and _note_unresolved_field's
        # caller (DecisionRule.matches) treats an unresolved field as a
        # non-match rather than as satisfying `not_in`.
        table = build_rule_table({"rules": [
            {"id": "repeat_loss_relocate", "action": "relocate",
             "when": {"flood_zone": {"not_in": ["LOW"]}}},
        ]}, where="t")
        assert table[0].matches(ctx) is False


class TestRuleFieldScopes:
    ENV_RULE = {"rules": [{"id": "crisis", "action": "tighten",
                           "when": {"loss_ratio": {"gte": 1.2, "scope": "env"}}}],
                "default_action": "hold"}

    def test_scope_env_ignores_a_stale_agent_copy(self):
        # The shipped insurance rule (review P2): the insurer carries its
        # own loss_ratio, refreshed AFTER the decision, so a rule about
        # the world's number read 0.0 and never fired.
        agent = _agent("INS", "insurance")
        agent.dynamic_state["loss_ratio"] = 0.0
        decide = _build("rule_based", self.ENV_RULE, agent=agent,
                        env={"loss_ratio": 2.4}, agent_id="INS",
                        agent_type="insurance")
        assert decide("")[0].skill_name == "tighten"

    def test_scope_agent_ignores_the_environment(self):
        agent = _agent("INS", "insurance")
        agent.dynamic_state["loss_ratio"] = 0.0
        params = {"rules": [{"id": "crisis", "action": "tighten",
                             "when": {"loss_ratio": {"gte": 1.2, "scope": "agent"}}}],
                  "default_action": "hold"}
        decide = _build("rule_based", params, agent=agent,
                        env={"loss_ratio": 2.4}, agent_id="INS",
                        agent_type="insurance")
        assert decide("")[0].skill_name == "hold"

    def test_an_unknown_scope_is_refused_when_the_table_is_built(self):
        # Raised, not coerced: a coerced scope reads a plane the config
        # did not name and keeps looking like it works.
        with pytest.raises(ValueError, match="declares scope"):
            build_rule_table(
                {"rules": [{"action": "x",
                            "when": {"f": {"gte": 1, "scope": "environment"}}}]},
                where="t")

    def test_a_scope_with_no_condition_is_refused(self):
        with pytest.raises(ValueError, match="only a scope"):
            build_rule_table(
                {"rules": [{"action": "x", "when": {"f": {"scope": "env"}}}]},
                where="t")

    def test_scope_is_not_treated_as_an_operator(self):
        table = build_rule_table(
            {"rules": [{"action": "x",
                        "when": {"f": {"gte": 1, "scope": "agent"}}}]},
            where="t")
        assert table[0].when == {"f": {"gte": 1}}
        assert table[0].scopes == {"f": "agent"}


# ---------------------------------------------------------------------------
# Built-in deciders through the pipeline's own contract
# ---------------------------------------------------------------------------

def _build(name, params, *, agent=None, env=None, llm=None, agent_id="A1",
           agent_type="worker"):
    return DeciderRegistry.build(DeciderSpec(name, params), {}, {
        "llm_invoke": llm, "agent": agent, "agent_id": agent_id,
        "agent_type": agent_type, "env": env, "seed": 42,
    })


class TestRuleBasedDecider:
    PARAMS = {
        "default_action": "do_nothing",
        "reasoning": {"TP_LABEL": "M"},
        "rules": [
            {"id": "stocked", "action": "restock",
             "when": {"stock": {"lte": 2}},
             "reasoning": {"TP_LABEL": "H"}},
        ],
    }

    def test_matched_rule_yields_a_governable_proposal(self):
        decide = _build("rule_based", self.PARAMS, agent=_agent(stock=1))
        payload, stats = decide("ignored prompt")
        # The retry loop accepts a SkillProposal directly; validation and
        # audit still run on it, which is the whole claim.
        assert isinstance(payload, SkillProposal)
        assert payload.skill_name == "restock"
        assert payload.agent_id == "A1" and payload.agent_type == "worker"
        assert payload.reasoning == {"TP_LABEL": "H"}
        assert payload.parse_layer == "decider:rule_based"
        assert stats.retries == 0 and stats.success is True
        # raw_output is the rule that fired, not a blank: the CSV column
        # is where a reader looks to see what the agent produced.
        assert '"rule": "stocked"' in payload.raw_output

    def test_unmatched_falls_to_the_declared_default_action(self):
        decide = _build("rule_based", self.PARAMS, agent=_agent(stock=9))
        payload, _ = decide("")
        assert payload.skill_name == "do_nothing"
        assert payload.reasoning == {"TP_LABEL": "M"}

    def test_default_action_is_mandatory(self):
        # Without it an unmatched agent has no action, the step aborts,
        # and this arm's row count silently shrinks.
        with pytest.raises(ValueError, match="default_action"):
            _build("rule_based", {"rules": [{"action": "x"}]}, agent=_agent())

    def test_records_the_rule_path(self):
        decide = _build("rule_based", self.PARAMS, agent=_agent(stock=1))
        decide("")
        assert take_decider_path() == "rule"

    def test_the_default_action_reports_its_OWN_path(self):
        # Review P1-a. Folded into "rule", a table whose fields never
        # resolve answers every row with its default and reads in the CSV
        # exactly like a table that was evaluated and did not match — an
        # arm that is a constant with a rule table's name.
        from broker.agents.deciders import RULE_DEFAULT_PATH
        decide = _build("rule_based", self.PARAMS, agent=_agent(stock=9))
        payload, _ = decide("")
        assert payload.skill_name == "do_nothing"
        assert take_decider_path() == RULE_DEFAULT_PATH == "rule_default"

    def test_an_unresolvable_field_is_reported_and_counted(self, caplog):
        from broker.core.run_integrity import get_rule_field_unresolved
        params = {"default_action": "do_nothing",
                  "rules": [{"id": "r", "action": "act",
                             "when": {"flood_zone": {"in": ["HIGH"]}}}]}
        decide = _build("rule_based", params, agent=_agent(stock=1),
                        agent_type="household_renter")
        with caplog.at_level("WARNING"):
            decide("")
            decide("")
        # Warned ONCE per (agent type, field) — 400 agents x 13 years of
        # the same line is a log nobody reads.
        assert sum("resolves to nothing" in r.message for r in caplog.records) == 1
        # ...but counted EVERY time, so the artifact carries the scale.
        assert get_rule_field_unresolved() == {
            "household_renter": {"flood_zone": 2}}

    def test_a_rule_reading_a_profile_field_fires(self):
        # The end-to-end shape of P0-A, at unit scale.
        params = {"default_action": "do_nothing",
                  "rules": [{"id": "exposed", "action": "buy_contents_insurance",
                             "when": {"flood_zone": {"in": ["HIGH"]}}}]}
        agent = _profile_agent("H0002", "household_renter", flood_zone="HIGH")
        decide = _build("rule_based", params, agent=agent, agent_id="H0002",
                        agent_type="household_renter")
        assert decide("")[0].skill_name == "buy_contents_insurance"
        assert take_decider_path() == "rule"

    def test_rule_firings_are_counted_per_rule_id(self):
        from broker.core.run_integrity import get_rule_firings
        decide = _build("rule_based", self.PARAMS, agent=_agent(stock=1),
                        agent_type="worker")
        decide("")
        decide("")
        assert get_rule_firings() == {"worker": {"stocked": 2}}

    def test_reads_current_agent_state_not_a_snapshot(self):
        agent = _agent(stock=9)
        decide = _build("rule_based", self.PARAMS, agent=agent)
        assert decide("")[0].skill_name == "do_nothing"
        agent.custom_attributes["stock"] = 1
        assert decide("")[0].skill_name == "restock"


class TestHybridDecider:
    PARAMS = {"rules": [{"id": "obvious", "action": "restock",
                         "when": {"stock": {"lte": 2}}}]}

    def test_rule_path_answers_without_calling_the_model(self):
        llm = _llm()
        decide = _build("hybrid", self.PARAMS, agent=_agent(stock=1), llm=llm)
        payload, _ = decide("prompt")
        assert payload.skill_name == "restock"
        assert llm.calls == []
        assert take_decider_path() == "rule"

    def test_unmatched_falls_through_to_the_model(self):
        llm = _llm("MODEL REPLY")
        decide = _build("hybrid", self.PARAMS, agent=_agent(stock=9), llm=llm)
        assert decide("prompt") == "MODEL REPLY"
        assert llm.calls == ["prompt"]
        assert take_decider_path() == "llm"

    def test_default_action_is_refused_because_the_model_is_the_fallback(self):
        with pytest.raises(ValueError, match="default_action.*meaningless"):
            _build("hybrid", {**self.PARAMS, "default_action": "x"},
                   agent=_agent(), llm=_llm())

    def test_a_matched_then_REJECTED_row_never_reaches_the_model(self):
        """Review W4: governance retry re-walks the table, it does not escalate.

        The retry loop calls the same callable again. The same rule
        matches the same state, so the identical proposal comes back and
        the model is never consulted — a hybrid row that was blocked
        stays ``decider_path: rule`` and exhausts its retries against a
        constant, exactly like a ``rule_based`` one. The semantics are
        deliberate (``hybrid`` means "the model handles what no rule
        COVERS", not "what governance REJECTED"), so this pins them
        rather than changing them.
        """
        llm = _llm("MODEL REPLY")
        agent = _agent(stock=1)
        decide = _build("hybrid", self.PARAMS, agent=agent, llm=llm)
        first, _ = decide("prompt")
        assert take_decider_path() == "rule"
        # ...governance REJECTS it; the retry loop calls the callable again.
        second, _ = decide("retry prompt with intervention")
        assert second.skill_name == first.skill_name == "restock"
        assert take_decider_path() == "rule"
        assert llm.calls == [], (
            "the model was consulted on a governance retry — a hybrid "
            "would then answer a rejection with a different decider than "
            "the one the first attempt used, and decider_path would "
            "describe neither"
        )


class StubParametric:
    """A domain's own decision object, for the `parametric` adapter."""

    def __init__(self, bias="restock"):
        self.bias = bias

    def decide(self, *, agent=None, env=None, context=None, agent_id="",
               agent_type="", **_kw):
        return self.bias, {"TP_LABEL": "H", "source": "stub"}


def stub_parametric_callable(*, agent=None, env=None, context=None,
                             agent_id="", agent_type="", **_kw):
    return "do_nothing"


class TestParametricAdapter:
    TARGET = "broker.tests.test_decider_registry_pr8:StubParametric"

    def test_wraps_a_domain_object_named_by_dotted_path(self):
        decide = _build("parametric", {"target": self.TARGET,
                                       "init": {"bias": "restock"}},
                        agent=_agent())
        payload, stats = decide("")
        assert isinstance(payload, SkillProposal)
        assert payload.skill_name == "restock"
        assert payload.reasoning["source"] == "stub"
        assert payload.parse_layer == "decider:parametric"
        assert take_decider_path() == "parametric"

    def test_a_plain_callable_target_works_too(self):
        decide = _build("parametric", {
            "target": "broker.tests.test_decider_registry_pr8:"
                      "stub_parametric_callable"}, agent=_agent())
        assert decide("")[0].skill_name == "do_nothing"

    @pytest.mark.parametrize("params,match", [
        ({}, "needs `target:"),
        ({"target": "no_colon"}, "needs `target:"),
        ({"target": "broker.tests.test_decider_registry_pr8:Nope"},
         "has no attribute"),
        ({"target": "broker.tests.test_decider_registry_pr8:"
                    "stub_parametric_callable", "init": {"x": 1}},
         "not a class"),
    ])
    def test_misconfiguration_is_refused_at_build(self, params, match):
        with pytest.raises(ValueError, match=match):
            _build("parametric", params, agent=_agent())


class TestPathIsolation:
    def test_taking_the_path_pops_it(self):
        note_decider_path("rule")
        assert take_decider_path() == "rule"
        # A stale value must not be attributed to the NEXT row.
        assert take_decider_path("fallback") == "fallback"

    def test_builtin_default_paths_cover_every_builtin(self):
        assert set(BUILTIN_DEFAULT_PATHS) == set(DeciderRegistry.names())


# ---------------------------------------------------------------------------
# Config surface
# ---------------------------------------------------------------------------

class TestAgentTypeConfigSurface:
    def test_absent_key_is_the_llm_default(self):
        cfg = _config({"worker": {"description": "x"}})
        assert cfg.get_decider("worker").is_default
        assert cfg.has_non_default_deciders() is False
        assert cfg.get_audit_decider_columns() is False

    def test_explicit_llm_is_still_the_default(self):
        cfg = _config({"worker": {"decider": "llm"}})
        assert cfg.get_decider("worker").name == DEFAULT_DECIDER_NAME
        assert cfg.get_audit_decider_columns() is False

    def test_one_non_llm_type_turns_the_columns_on_for_the_whole_run(self):
        cfg = _config({
            "worker": {"description": "x"},
            "robot": {"decider": {"name": "rule_based", "params": {}}},
        })
        assert cfg.get_decider("robot").name == "rule_based"
        assert cfg.has_non_default_deciders() is True
        assert cfg.get_audit_decider_columns() is True

    def test_operator_can_force_the_columns_on(self):
        cfg = _config({"worker": {}}, {"audit": {"decider_columns": True}})
        assert cfg.get_audit_decider_columns() is True

    def test_a_malformed_declaration_raises_rather_than_defaulting(self):
        cfg = _config({"worker": {"decider": 7}})
        with pytest.raises(ValueError):
            cfg.get_decider("worker")
        # ...and the columns come on anyway, so the failure stays legible.
        assert cfg.has_non_default_deciders() is True

    def test_decider_columns_is_a_registered_audit_key(self):
        # A typo'd flag key resolves default-OFF with no other warning.
        assert "decider_columns" in KNOWN_AUDIT_KEYS

    @pytest.mark.parametrize("reserved", ["shared", "global_config", "metadata"])
    def test_a_decider_under_a_NON_AGENT_block_does_not_arm_the_columns(
            self, reserved):
        # Review C1. Nothing reads `decider:` there, so the run is
        # all-LLM — and switching the columns on would give that corpus a
        # provenance column reading `llm` on every row, from a config
        # that looks mixed. `shared:` is the one people reach for: it is
        # where the response format and rating scale live.
        cfg = _config({"worker": {"description": "x"},
                       reserved: {"decider": "rule_based"}})
        assert cfg.has_non_default_deciders() is False
        assert cfg.get_audit_decider_columns() is False

    def test_declared_names_cover_every_agent_type_including_defaults(self):
        cfg = _config({
            "worker": {"description": "x"},              # -> llm
            "robot": {"decider": "rule_based"},
            "shared": {"decider": "hybrid"},             # not an agent type
        })
        # `llm` is in the list because the government-style arm WILL
        # produce rows saying `llm`, and the census has to know to expect
        # them. `hybrid` is not, because nothing reads it.
        assert cfg.declared_decider_names() == ["llm", "rule_based"]


# ---------------------------------------------------------------------------
# Config-time check
# ---------------------------------------------------------------------------

class TestValidatePromptCheck:
    def test_unknown_decider_name_is_a_blocker(self):
        DomainPackRegistry.register("_pr8_probe", DefaultDomainPack())
        issues = check_decider_declarations({
            "worker": {"decider": "handwavy"},
        })
        errors = [i for i in issues if i.severity == "ERROR"]
        assert errors and "handwavy" in errors[0].message
        assert "rule_based" in errors[0].message

    def test_registered_names_pass(self):
        DomainPackRegistry.register("_pr8_probe", DefaultDomainPack())
        issues = check_decider_declarations({"worker": {"decider": {
            "name": "rule_based",
            "params": {"default_action": "do_nothing",
                       "rules": [{"id": "r", "action": "act"}]},
        }}})
        assert [i for i in issues if i.severity == "ERROR"] == []

    def test_a_rule_based_decider_with_no_table_is_a_blocker(self):
        # A registered NAME is not enough: `decider: rule_based` with no
        # params answers every decision with a default it also does not
        # have. The run raises at start; saying so here costs one line.
        DomainPackRegistry.register("_pr8_probe", DefaultDomainPack())
        errors = [i for i in check_decider_declarations(
            {"worker": {"decider": "rule_based"}}) if i.severity == "ERROR"]
        assert errors and "no 'rules' declared" in errors[0].message

    def test_decider_under_global_config_is_warned_about(self):
        # The dangerous one: read by nothing, the run starts fine, and
        # every agent silently uses the LLM default.
        issues = check_decider_declarations({
            "global_config": {"decider": "rule_based"},
            "worker": {},
        })
        warns = [i for i in issues if i.severity == "WARN"]
        assert warns and "read by nothing" in warns[0].message

    def test_malformed_declaration_is_a_blocker(self):
        DomainPackRegistry.register("_pr8_probe", DefaultDomainPack())
        issues = check_decider_declarations({"worker": {"decider": []}})
        assert [i for i in issues if i.severity == "ERROR"]

    def test_decider_under_shared_is_warned_about_too(self):
        # Review C1: `shared:` was not on the skip list, so the key was
        # read as a declaration there and armed the audit columns.
        issues = check_decider_declarations({
            "shared": {"decider": "rule_based"}, "worker": {},
        })
        warns = [i for i in issues if i.severity == "WARN"]
        assert warns and "read by nothing" in warns[0].message
        assert "shared" in warns[0].location

    def test_a_PARTIAL_reasoning_report_is_a_blocker(self):
        """Review W5. A rule reporting SOME required labels loops to ABORTED.

        `_retry_loop` requires every `*_LABEL` in `parsing.constructs`
        once a proposal reports anything at all; a rule table answers the
        retry identically, so every row that rule produces exhausts its
        retries. Reporting nothing is fine — the loop skips the check.
        """
        DomainPackRegistry.register("_pr8_probe", DefaultDomainPack())
        block = {
            "parsing": {"constructs": {"TP_LABEL": {}, "CP_LABEL": {},
                                       "TP_REASON": {}}},
            "decider": {"name": "rule_based", "params": {
                "default_action": "do_nothing",
                "rules": [{"id": "partial", "action": "act",
                           "reasoning": {"TP_LABEL": "H"}}],
            }},
        }
        errors = [i for i in check_decider_declarations({"renter": block})
                  if i.severity == "ERROR"]
        assert errors and "CP_LABEL" in errors[0].message
        # *_REASON is not required by the retry loop, so it is not demanded.
        assert "TP_REASON" not in errors[0].message

    def test_a_COMPLETE_or_EMPTY_reasoning_report_passes(self):
        DomainPackRegistry.register("_pr8_probe", DefaultDomainPack())
        constructs = {"parsing": {"constructs": {"TP_LABEL": {}, "CP_LABEL": {}}}}
        complete = {**constructs, "decider": {"name": "rule_based", "params": {
            "default_action": "do_nothing",
            # the shared `reasoning:` counts toward the rule's own report
            "reasoning": {"TP_LABEL": "M", "CP_LABEL": "M"},
            "rules": [{"id": "r", "action": "act", "reasoning": {"TP_LABEL": "H"}}],
        }}}
        empty = {**constructs, "decider": {"name": "rule_based", "params": {
            "default_action": "do_nothing",
            "rules": [{"id": "r", "action": "act"}],
        }}}
        for block in (complete, empty):
            assert [i for i in check_decider_declarations({"renter": block})
                    if i.severity == "ERROR"] == []

    def test_an_unbuildable_rule_table_is_a_blocker(self):
        DomainPackRegistry.register("_pr8_probe", DefaultDomainPack())
        block = {"decider": {"name": "rule_based", "params": {
            "default_action": "x",
            "rules": [{"action": "a", "when": {"f": {"gte": 1, "scope": "nope"}}}],
        }}}
        errors = [i for i in check_decider_declarations({"renter": block})
                  if i.severity == "ERROR"]
        assert errors and "declares scope" in errors[0].message


# ---------------------------------------------------------------------------
# DomainPack hook
# ---------------------------------------------------------------------------

class _PackWithDecider(DefaultDomainPack):
    name = "_pr8_domain"

    def decider_factories(self):
        def factory(cfg, runtime):
            from broker.agents.deciders import make_proposal
            return lambda prompt="", **kw: make_proposal(
                skill_name="domain_action",
                agent_id=str(runtime.get("agent_id")),
                agent_type=str(runtime.get("agent_type")),
                decider="domain_special", path="domain",
            )
        return {"domain_special": factory}


class TestDomainPackHook:
    def test_default_pack_ships_no_deciders(self):
        assert DefaultDomainPack().decider_factories() == {}

    def test_a_domain_factory_registers_and_resolves(self):
        DomainPackRegistry.register("_pr8_domain", _PackWithDecider())
        assert register_domain_deciders("_pr8_domain") == ["domain_special"]
        decide = _build("domain_special", {}, agent=_agent())
        payload, _ = decide("")
        assert payload.skill_name == "domain_action"

    def test_a_pack_may_not_silently_shadow_a_builtin(self):
        """Review P1-d: `replace=True` let the named domain shadow `rule_based`.

        Two runs of the same YAML would then mean different things
        depending on which module imported first, and both would be
        called ``rule_based`` in the CSV.
        """
        class _Shadow(DefaultDomainPack):
            name = "_pr8_shadow"

            def decider_factories(self):
                return {"rule_based": lambda cfg, rt: (lambda p="", **kw: "x")}

        DomainPackRegistry.register("_pr8_shadow", _Shadow())
        with pytest.raises(ValueError, match="is a BUILT-IN"):
            register_domain_deciders("_pr8_shadow")
        # ...and the built-in is untouched.
        assert DeciderRegistry.get("rule_based").__name__ == \
            "rule_based_decider_factory"

    def test_an_EXPLICIT_override_is_allowed_and_relabelled(self):
        class _Override(DefaultDomainPack):
            name = "_pr8_override"

            def decider_factories(self):
                from broker.agents.deciders import make_proposal
                def factory(cfg, runtime):
                    return lambda prompt="", **kw: make_proposal(
                        skill_name="domain_rule", agent_id="A1",
                        agent_type="worker", decider="rule_based",
                        path="rule")
                return {"rule_based": {"factory": factory,
                                       "override_builtins": True}}

        DomainPackRegistry.register("_pr8_override", _Override())
        assert register_domain_deciders("_pr8_override") == ["rule_based"]
        assert _build("rule_based", {}, agent=_agent())("")[0].skill_name == \
            "domain_rule"
        # The audit column keeps the two apart; the CSV cannot conflate them.
        assert DeciderRegistry.audit_label("rule_based") == \
            "rule_based@_pr8_override"
        assert DeciderRegistry.audit_label("hybrid") == "hybrid"

    def test_sweep_registers_from_every_pack_when_no_domain_is_declared(self):
        # `global_config.governance.domain` is optional and several
        # shipped configs omit it. Without the sweep a decider the
        # domain does ship reads as unregistered and the run dies on a
        # name sitting in the registry.
        DomainPackRegistry.register("_pr8_domain", _PackWithDecider())
        assert "domain_special" in register_domain_deciders(None)


# ---------------------------------------------------------------------------
# Audit columns + the run_integrity census
# ---------------------------------------------------------------------------

class _AuditHost:
    from broker.core._audit_helpers import AuditMixin as _Mixin
    _decider_audit_extra = _Mixin._decider_audit_extra

    def __init__(self, config):
        self.config = config


class TestAuditColumns:
    def test_flag_off_emits_no_keys(self):
        host = _AuditHost(_config({"worker": {}}))
        assert host._decider_audit_extra("llm") == {}
        # No key -> no CSV fieldname -> frozen corpora unchanged.

    def test_flag_on_emits_name_and_path(self):
        host = _AuditHost(_config({"worker": {"decider": "rule_based"}}))
        note_decider_path("rule")
        assert host._decider_audit_extra("rule_based") == {
            "decider": "rule_based", "decider_path": "rule"}

    def test_path_defaults_per_decider_when_none_was_recorded(self):
        host = _AuditHost(_config({"worker": {"decider": "rule_based"}}))
        assert host._decider_audit_extra("llm")["decider_path"] == "llm"
        assert host._decider_audit_extra("hybrid")["decider_path"] == "llm"
        assert host._decider_audit_extra("mine")["decider_path"] == "mine"

    def test_each_emitted_row_is_counted_once_per_decider(self):
        host = _AuditHost(_config({"worker": {"decider": "rule_based"}}))
        for _ in range(3):
            host._decider_audit_extra("rule_based")
        host._decider_audit_extra("llm")
        assert get_decider_row_counts() == {"llm": 1, "rule_based": 3}

    def test_the_census_stays_empty_when_the_columns_are_off(self):
        host = _AuditHost(_config({"worker": {}}))
        host._decider_audit_extra("llm")
        assert get_decider_row_counts() == {}

    def test_census_reset_clears_a_previous_run(self):
        note_decider_row("rule_based")
        reset_decider_row_counts()
        assert get_decider_row_counts() == {}

    def test_a_forced_path_overrides_what_the_decider_recorded(self):
        # The aborted sentinels pass path="aborted": the step crashed or
        # never parsed, so there is no completed decision path, and
        # letting the row inherit a decider's default path would put it
        # in the census as though it had decided something.
        from broker.core.run_integrity import get_decider_aborted_row_counts
        host = _AuditHost(_config({"worker": {"decider": "rule_based"}}))
        note_decider_path("rule")
        assert host._decider_audit_extra("rule_based", path="aborted") == {
            "decider": "rule_based", "decider_path": "aborted"}
        assert get_decider_aborted_row_counts() == {"rule_based": 1}
        # The slot was POPPED, so the stale "rule" cannot reach the next row.
        assert take_decider_path("fallback") == "fallback"

    def test_rule_default_rows_are_counted_separately(self):
        from broker.core.run_integrity import get_rule_default_row_counts
        host = _AuditHost(_config({"worker": {"decider": "rule_based"}}))
        note_decider_path("rule_default")
        host._decider_audit_extra("rule_based")
        note_decider_path("rule")
        host._decider_audit_extra("rule_based")
        assert get_decider_row_counts() == {"rule_based": 2}
        assert get_rule_default_row_counts() == {"rule_based": 1}

    def test_an_overridden_builtin_keeps_the_builtin_default_path(self):
        # `<name>@<domain>` is not in BUILTIN_DEFAULT_PATHS; the bare name is.
        host = _AuditHost(_config({"worker": {"decider": "rule_based"}}))
        assert host._decider_audit_extra("rule_based@flood") == {
            "decider": "rule_based@flood", "decider_path": "rule"}


class TestZeroRowArmIsNamed:
    """Review P1-b: an arm that produced NO rows.

    The pre-fix warning fired only when EXACTLY ONE arm produced rows, so
    a config with three declared arms and one silently empty passed it —
    and a CSV missing one `decider` category looks exactly like a correct
    one until somebody groups by it.
    """

    def test_the_declared_set_is_compared_against_what_produced_rows(self, tmp_path):
        from broker.core.run_integrity import (
            record_run_integrity, set_declared_deciders,
        )
        set_declared_deciders(["llm", "rule_based", "hybrid"])
        note_decider_row("llm", "llm")
        note_decider_row("rule_based", "rule")
        record = record_run_integrity(tmp_path, verbose=False)
        assert record["decider_arms_with_zero_rows"] == ["hybrid"]
        assert record["decider_rows_total"] == 2
        assert record["decider_declared"] == ["hybrid", "llm", "rule_based"]

    def test_the_prefix_predicate_would_have_stayed_silent(self, tmp_path):
        # The falsification, inline: the old condition is
        # `len(seen) == 1 and seen[0] != "llm"`, which is False here.
        seen = sorted({"llm", "rule_based"})
        assert not (len(seen) == 1 and seen[0] != "llm")

    def test_an_overridden_name_is_matched_on_its_bare_name(self, tmp_path):
        from broker.core.run_integrity import (
            record_run_integrity, set_declared_deciders,
        )
        set_declared_deciders(["rule_based"])
        note_decider_row("rule_based@flood", "rule")
        record = record_run_integrity(tmp_path, verbose=False)
        assert record["decider_arms_with_zero_rows"] == []


class TestCensusArithmeticAgainstCsvTotals:
    """Code-reviewer focus 3: the completed-row comparison at
    ``run_integrity.py`` ~554 false-positives with
    ``audit.corrected_status_columns`` OFF, and the fix compares TOTALS
    (``decider_rows_total`` vs ``audit_rows``) instead.

    With the flag OFF, the F1 exception sentinel's CSV ``status`` cell
    reads ``UNKNOWN`` — ``approved_skill`` (what ``trace_to_csv_row``
    reads ``status`` off) is only populated for that sentinel under the
    flag (``ExperimentRunner._write_aborted_trace``). So
    ``audit_aborted_rows`` (read from that CSV column) MISSES the row,
    while ``decider_aborted_rows`` (recorded at write time, gated on the
    decider-columns flag only) still counts it — the old
    subtract-then-compare arithmetic then disagreed by exactly one row,
    on a run where every row genuinely went through the decider column
    builder.
    """

    def _write_csv(self, tmp_path, rows):
        import csv as csv_module
        csv_path = tmp_path / "household_governance_audit.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv_module.DictWriter(fh, fieldnames=["agent_id", "year", "status"])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return csv_path

    def test_flag_off_no_longer_false_positives(self, tmp_path, caplog):
        from broker.core.run_integrity import record_run_integrity

        # 2 ordinary rows + 1 crash sentinel whose CSV status reads
        # UNKNOWN (the corrected_status_columns-OFF shape) even though
        # the decider census — recorded at write time, not from the CSV
        # — saw and counted all three rows, one of them "aborted".
        self._write_csv(tmp_path, [
            {"agent_id": "H0000", "year": 1, "status": "APPROVED"},
            {"agent_id": "H0001", "year": 1, "status": "APPROVED"},
            {"agent_id": "H0002", "year": 1, "status": "UNKNOWN"},
        ])
        note_decider_row("llm", "llm")
        note_decider_row("llm", "llm")
        note_decider_row("llm", "aborted")

        with caplog.at_level("WARNING"):
            record = record_run_integrity(tmp_path, verbose=False)

        assert record["audit_rows"] == 3
        assert record["audit_aborted_rows"] == 0, (
            "the UNKNOWN-status sentinel must NOT be counted from the CSV "
            "column — that blind spot is the premise of this test"
        )
        assert record["decider_rows_total"] == 3
        assert record["decider_aborted_rows"] == {"llm": 1}

        # Falsification: the OLD arithmetic, recreated inline, DOES
        # disagree on this exact data — proving the warning below is
        # gone because of the fix, not because nothing was ever wrong.
        _pre_fix_census_completed = (
            record["decider_rows_total"] - sum(record["decider_aborted_rows"].values())
        )
        _pre_fix_csv_completed = record["audit_rows"] - record["audit_aborted_rows"]
        assert _pre_fix_census_completed != _pre_fix_csv_completed, (
            "this data must reproduce the pre-fix disagreement (2 != 3) "
            "or the test is not exercising the bug"
        )

        hits = [r for r in caplog.records if "census counted" in r.getMessage()]
        assert hits == [], (
            f"false 'wrote a row without the decider builder' warning: "
            f"{[r.getMessage() for r in hits]}"
        )

    def test_flag_on_still_agrees(self, tmp_path, caplog):
        """The paired state: with the flag ON the sentinel's status cell
        correctly reads ABORTED_EXCEPTION, so audit_aborted_rows already
        counted it pre-fix too — this must stay silent under the new
        arithmetic exactly as it did under the old one."""
        from broker.core.run_integrity import record_run_integrity

        self._write_csv(tmp_path, [
            {"agent_id": "H0000", "year": 1, "status": "APPROVED"},
            {"agent_id": "H0001", "year": 1, "status": "APPROVED"},
            {"agent_id": "H0002", "year": 1, "status": "ABORTED_EXCEPTION"},
        ])
        note_decider_row("llm", "llm")
        note_decider_row("llm", "llm")
        note_decider_row("llm", "aborted")

        with caplog.at_level("WARNING"):
            record = record_run_integrity(tmp_path, verbose=False)

        assert record["audit_rows"] == 3
        assert record["audit_aborted_rows"] == 1
        assert record["decider_rows_total"] == 3

        hits = [r for r in caplog.records if "census counted" in r.getMessage()]
        assert hits == []

    def test_a_genuine_coverage_hole_still_warns(self, tmp_path, caplog):
        """The fix must not have traded a false positive for a false
        negative: a row the CSV holds that the decider census never saw
        at all — the actual defect this warning exists to catch — still
        fires it."""
        from broker.core.run_integrity import record_run_integrity

        self._write_csv(tmp_path, [
            {"agent_id": "H0000", "year": 1, "status": "APPROVED"},
            {"agent_id": "H0001", "year": 1, "status": "APPROVED"},
        ])
        note_decider_row("llm", "llm")  # only ONE row censused; CSV holds two

        with caplog.at_level("WARNING"):
            record = record_run_integrity(tmp_path, verbose=False)

        assert record["audit_rows"] == 2
        assert record["decider_rows_total"] == 1
        hits = [r for r in caplog.records if "census counted" in r.getMessage()]
        assert len(hits) == 1
