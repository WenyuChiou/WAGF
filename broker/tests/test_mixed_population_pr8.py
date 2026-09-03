"""PR-8 integration: one run, four deciders, one governance pipeline.

The paper claim this pins is a claim about COMPARABILITY, so a unit
test cannot carry it. It needs a real run in which a calibrated
non-LLM decider, a rule table, a rule-table-with-model-fallback and a
plain model agent all decide inside the same ``ExperimentRunner``, and
all four land in audit CSVs a reader can put side by side.

What the run must show, and why each one matters:

* every agent type reaches the audit CSV. A mixed-population config
  that silently produces rows for only one of its arms looks exactly
  like a correct one until someone groups by ``decider``;
* the ``decider`` column tells the four apart, and ``decider_path``
  splits the hybrid's rule-answered rows from its model-answered ones;
* the two household types — the actual apples-to-apples pair — carry
  the SAME columns apart from the ``reason_*`` ones each decider's own
  reasoning dict produces, which is the same way an LLM agent's
  reasoning keys produce its columns;
* ``run_integrity.json`` carries the per-decider row census, so the
  composition claim is checkable against the artifact rather than
  against the config that was supposed to produce it;
* the DEFAULT path is untouched: the same runner with no
  ``--mixed-population`` writes no decider columns at all, which is
  what keeps every frozen corpus reproducible.

Falsification: pre-PR-8 the ``--mixed-population`` flag does not exist
and the runner refuses the argument, so every assertion here fails.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _REPO_ROOT / "examples" / "multi_agent" / "flood" / "run_unified_experiment.py"
_OUTPUT_SUBDIR = "mock_strict"

_EXPECTED = {
    "government": "llm",
    "household_owner": "flood_household_parametric",
    "household_renter": "rule_based",
    "insurance": "hybrid",
}


# Seed 7 rather than 42, and 12 agents rather than 4, for one reason: at
# seed 42 the random population contains no HIGH-zone renter at all, so
# two of the three shipped renter rules cannot fire whatever the code
# does — and a run in which the rules cannot fire cannot tell a working
# rule arm from the constant this file exists to catch (review P0-A).
def _run(tmp_path, *extra_args):
    out = tmp_path / "run"
    result = subprocess.run(
        [sys.executable, str(_RUNNER),
         "--model", "mock", "--agents", "12", "--years", "3",
         "--seed", "7", "--mode", "random",
         "--flood-years", "2:0.8",
         "--output", str(out), *extra_args],
        cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=900,
    )
    if result.returncode != 0:
        pytest.fail(
            f"runner failed (rc={result.returncode}) for args {extra_args}:\n"
            f"STDOUT:\n{result.stdout[-3000:]}\nSTDERR:\n{result.stderr[-3000:]}"
        )
    audit_dir = out / _OUTPUT_SUBDIR
    assert audit_dir.exists(), f"no audit output at {audit_dir}"
    return audit_dir


def _read(audit_dir: Path, agent_type: str):
    path = audit_dir / f"{agent_type}_governance_audit.csv"
    assert path.exists(), f"missing audit CSV for {agent_type}: {path}"
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


@pytest.fixture(scope="module")
def mixed_run(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("pr8_mixed"), "--mixed-population")


@pytest.fixture(scope="module")
def default_run(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("pr8_default"))


class TestMixedPopulation:
    @pytest.mark.parametrize("agent_type,decider", sorted(_EXPECTED.items()))
    def test_every_agent_type_reaches_the_audit_with_its_decider(
            self, mixed_run, agent_type, decider):
        fields, rows = _read(mixed_run, agent_type)
        assert rows, f"{agent_type} produced no decision rows"
        assert {"decider", "decider_path"} <= set(fields)
        assert {r["decider"] for r in rows} == {decider}

    def test_four_distinct_deciders_in_one_run(self, mixed_run):
        seen = set()
        for agent_type in _EXPECTED:
            seen.update(r["decider"] for r in _read(mixed_run, agent_type)[1])
        assert seen == set(_EXPECTED.values())

    def test_hybrid_records_which_path_answered_each_row(self, mixed_run):
        _, rows = _read(mixed_run, "insurance")
        paths = [r["decider_path"] for r in rows]
        # Year 1 has no loss history, so the table answers it; the later
        # year has no matching rule and goes to the model. Without this
        # column the two rows are indistinguishable in the CSV.
        assert "rule" in paths and "llm" in paths

    def test_non_hybrid_rows_report_their_own_single_path(self, mixed_run):
        # `rule` and `rule_default` are both the rule table answering; a
        # table that never matched is still not a model (review P1-a).
        assert {r["decider_path"] for r in _read(mixed_run, "household_renter")[1]} <= {
            "rule", "rule_default"}
        assert {r["decider_path"] for r in _read(mixed_run, "government")[1]} == {"llm"}
        assert {r["decider_path"] for r in _read(mixed_run, "household_owner")[1]} == {
            "parametric"}

    def test_every_path_is_a_documented_value(self, mixed_run):
        documented = {"llm", "rule", "rule_default", "parametric", "aborted"}
        for agent_type in _EXPECTED:
            paths = {r["decider_path"] for r in _read(mixed_run, agent_type)[1]}
            assert paths <= documented, f"{agent_type}: undocumented {paths - documented}"

    def test_the_rule_arm_actually_ran_its_rules(self, mixed_run):
        """Review P0-A/P1-a: the shipped rule arm must not be a constant.

        Before the resolver looked in ``fixed_attributes``, every rule
        reading a profile field was permanently false, so this arm
        answered every row with its ``default_action`` — a constant with
        a rule table's name, and nothing in the CSV said so.
        """
        record = json.loads((mixed_run / "run_integrity.json").read_text(encoding="utf-8"))
        rows = len(_read(mixed_run, "household_renter")[1])
        defaults = (record.get("rule_default_rows") or {}).get("rule_based", 0)
        assert defaults < rows, (
            f"all {rows} household_renter rows fell through to "
            f"default_action — the table's fields are not resolving. "
            f"rule_field_unresolved={record.get('rule_field_unresolved')}"
        )

    def test_no_rule_field_is_unresolvable(self, mixed_run):
        record = json.loads((mixed_run / "run_integrity.json").read_text(encoding="utf-8"))
        assert record.get("rule_field_unresolved", {}) == {}, (
            "a shipped rule names a field the agents do not carry, so the "
            "condition can never hold and the rule can never fire"
        )

    def test_no_declared_arm_produced_zero_rows(self, mixed_run):
        record = json.loads((mixed_run / "run_integrity.json").read_text(encoding="utf-8"))
        assert record.get("decider_arms_with_zero_rows") == []
        assert record["decider_rows_total"] == sum(record["decider_rows"].values())

    def test_the_owner_arm_reports_more_than_one_appraisal(self, mixed_run):
        """The parametric arm must vary with its inputs, not saturate.

        The logistic reads tp_score / cp_score as its OWN inputs and bands
        them back onto the five-level scale. A single value across the
        whole population means it is not reading them (P0-A) or is
        reading them on the wrong scale — a 1-5 Likert against 0-1
        anchors saturates the sigmoid and reports VH for everyone.
        """
        _, rows = _read(mixed_run, "household_owner")
        labels = {r["construct_TP_LABEL"] for r in rows if r.get("construct_TP_LABEL")}
        assert len(labels) > 1, (
            f"every owner reported TP_LABEL={labels} — the appraisal "
            f"inputs are not reaching the logistic, or not on its scale"
        )

    def test_the_two_household_types_are_column_comparable(self, mixed_run):
        owner, _ = _read(mixed_run, "household_owner")
        renter, _ = _read(mixed_run, "household_renter")
        # Everything but the reasoning-derived columns must match: those
        # come from each decider's own reasoning dict, exactly as an LLM
        # agent's reasoning keys produce its own reason_* columns.
        strip = lambda f: {c for c in f if not c.startswith("reason_")}  # noqa: E731
        assert strip(owner) == strip(renter)

    def test_a_rule_based_row_carries_the_governance_columns_too(self, mixed_run):
        _, rows = _read(mixed_run, "household_renter")
        row = rows[0]
        # Same validators ran: the row has a status, a validated flag and
        # the rule-hit counters, not a hole where governance would be.
        assert row["status"]
        assert row["validated"] in ("True", "False")
        assert row["rules_evaluated_count"] != ""
        assert row["construct_TP_LABEL"]

    def test_run_integrity_carries_the_per_decider_census(self, mixed_run):
        record = json.loads((mixed_run / "run_integrity.json").read_text(encoding="utf-8"))
        census = record.get("decider_rows")
        assert census, "run_integrity.json has no decider_rows census"
        assert set(census) == set(_EXPECTED.values())
        for agent_type, decider in _EXPECTED.items():
            assert census[decider] == len(_read(mixed_run, agent_type)[1])


class TestDefaultPathUnaffected:
    def test_no_decider_columns_without_the_flag(self, default_run):
        # The property every frozen corpus depends on: an all-`llm`
        # config emits no key, so no CSV fieldname appears, so a rerun
        # is byte-identical.
        for agent_type in _EXPECTED:
            fields, _ = _read(default_run, agent_type)
            assert "decider" not in fields
            assert "decider_path" not in fields

    def test_no_census_in_run_integrity_without_the_flag(self, default_run):
        record = json.loads((default_run / "run_integrity.json").read_text(encoding="utf-8"))
        assert "decider_rows" not in record

    def test_the_frozen_config_declares_no_decider(self):
        import yaml
        frozen = (_REPO_ROOT / "examples" / "multi_agent" / "flood" /
                  "config" / "ma_agent_types.yaml")
        cfg = yaml.safe_load(frozen.read_text(encoding="utf-8"))
        offenders = [k for k, v in cfg.items()
                     if isinstance(v, dict) and "decider" in v]
        assert offenders == [], (
            f"the frozen paper-3 config gained a decider: key on {offenders} — "
            f"mixed-population work belongs in "
            f"ma_agent_types_mixed_population.yaml"
        )


class TestMixedConfigIsTheFrozenOnePlusDeciders:
    """Review C3: a drift guard on the mixed config's OTHER 1,200 lines.

    The mixed config's whole claim is that it is the frozen paper-3 file
    plus a ``decider:`` key on three agent types — that is what makes the
    two runs comparable at all. Nothing enforced it. A prompt tweaked
    here, a skill alias added there, and the mixed arm is measuring a
    different experiment while still being described as the same one, and
    a 1,200-line diff is not something a reviewer re-reads.

    Compared as parsed YAML, so comments and formatting are free to
    differ (they must — the mixed file explains itself) and only meaning
    is pinned.
    """

    CONFIG_DIR = _REPO_ROOT / "examples" / "multi_agent" / "flood" / "config"

    def _load(self, name):
        import yaml
        return yaml.safe_load((self.CONFIG_DIR / name).read_text(encoding="utf-8"))

    def test_stripping_decider_reproduces_the_frozen_config_exactly(self):
        frozen = self._load("ma_agent_types.yaml")
        mixed = self._load("ma_agent_types_mixed_population.yaml")
        stripped = {
            k: ({kk: vv for kk, vv in v.items() if kk != "decider"}
                if isinstance(v, dict) else v)
            for k, v in mixed.items()
        }
        assert set(stripped) == set(frozen), (
            "the mixed config gained or lost a top-level block: "
            f"only in mixed={sorted(set(stripped) - set(frozen))}, "
            f"only in frozen={sorted(set(frozen) - set(stripped))}"
        )
        drifted = [k for k in frozen if stripped[k] != frozen[k]]
        assert drifted == [], (
            f"the mixed config differs from the frozen one OUTSIDE its "
            f"decider: keys, on {drifted}. The two arms are then not "
            f"running the same experiment, and the comparison the mixed "
            f"config exists to support is not the one it describes."
        )

    def test_the_declared_deciders_are_the_documented_three(self):
        mixed = self._load("ma_agent_types_mixed_population.yaml")
        declared = {k: v["decider"] for k, v in mixed.items()
                    if isinstance(v, dict) and "decider" in v}
        assert set(declared) == {"household_owner", "household_renter", "insurance"}
        assert declared["household_owner"]["name"] == "flood_household_parametric"
        assert declared["household_renter"]["name"] == "rule_based"
        assert declared["insurance"]["name"] == "hybrid"

    def test_no_rule_reads_a_zone_the_domain_never_emits(self):
        # Review P2. `generate_agents` draws flood_zone from
        # HIGH / MEDIUM / LOW; a value in an `in:` list that cannot occur
        # is dead config that reads as a wider rule than it is.
        emitted = {"HIGH", "MEDIUM", "LOW"}
        mixed = self._load("ma_agent_types_mixed_population.yaml")
        for atype, block in mixed.items():
            if not isinstance(block, dict) or "decider" not in block:
                continue
            for rule in (block["decider"].get("params") or {}).get("rules", []):
                cond = (rule.get("when") or {}).get("flood_zone")
                if not isinstance(cond, dict):
                    continue
                for op in ("in", "not_in"):
                    unknown = set(cond.get(op) or []) - emitted
                    assert not unknown, (
                        f"{atype} rule {rule.get('id')!r} names flood "
                        f"zone(s) {sorted(unknown)} that nothing emits"
                    )
