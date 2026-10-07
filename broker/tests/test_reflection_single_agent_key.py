"""Batch reflection parsing when a batch holds one agent and the model
answers under a key other than the exact agent id."""

from broker.components.cognitive.reflection import ReflectionEngine


def _parse(text, ids):
    return ReflectionEngine().parse_batch_reflection_response(text, ids, 3)


def test_single_agent_generic_key_is_read():
    out = _parse('{"Agent_1": "Supply was short, so I kept my request."}', ["UnitBIDD"])
    assert out["UnitBIDD"] is not None
    assert out["UnitBIDD"].summary == "Supply was short, so I kept my request."


def test_single_agent_truncated_compound_key_is_read():
    out = _parse('{"NMAgFruitland": "The river ran low this year."}',
                 ["NewMexicoAgFarmToShip_NMAgFruitland"])
    assert out["NewMexicoAgFarmToShip_NMAgFruitland"].summary == "The river ran low this year."


def test_single_agent_exact_key_unchanged():
    out = _parse('{"UnitBIDD": "Exact key."}', ["UnitBIDD"])
    assert out["UnitBIDD"].summary == "Exact key."


def test_single_agent_two_keys_not_guessed():
    out = _parse('{"A": "first", "B": "second"}', ["UnitBIDD"])
    assert out["UnitBIDD"] is None


def test_single_agent_non_string_value_not_read():
    out = _parse('{"Agent_1": {"text": "nested"}}', ["UnitBIDD"])
    assert out["UnitBIDD"] is None


def test_multi_agent_batch_never_assigns_a_foreign_key():
    out = _parse('{"Agent_9": "someone else"}', ["A1", "A2"])
    assert out == {"A1": None, "A2": None}


def test_single_agent_mock_decision_reply_not_read():
    # broker.utils.llm_utils mock answers every prompt {"decision": N}
    assert _parse('{"decision": 1}', ["A1"]) == {"A1": None}


def test_single_agent_blank_value_not_read():
    assert _parse('{"Agent_1": "   "}', ["UnitBIDD"]) == {"UnitBIDD": None}


def test_single_agent_fenced_reply_with_surrounding_text():
    text = ('Here is my reflection:\n```json\n{"BIDD": "I kept my request after '
            'a short year."}\n```\nThat is all.')
    out = _parse(text, ["UnitBIDD"])
    assert out["UnitBIDD"].summary == "I kept my request after a short year."


def test_multi_agent_partial_match_leaves_unmatched_none():
    out = _parse('{"A1": "mine", "Agent_2": "other"}', ["A1", "A2"])
    assert out["A1"].summary == "mine" and out["A2"] is None
