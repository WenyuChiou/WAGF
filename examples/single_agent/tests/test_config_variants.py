"""The ``nonudge`` --config-root variant must be byte-identical to the base
``examples/single_agent/`` config, except the one "Do Nothing" nudge line
removed from ``config/prompts/household.txt`` (flood design record PI
decisions 2026-09-29 item 3 and 2026-10-06 item 5: the no-nudge arm).

This is a CONTENT check only. It does not need to catch a separate
``.gitignore``-exclusion hazard this directory used to carry: ``*.csv`` is
gitignored repo-wide, which used to silently drop the two CSV files below
from an ordinary ``git add`` of this directory. That is now fixed at the
root cause -- ``.gitignore`` carries
``!examples/single_agent/config_variants/**/*.csv`` next to irrigation's own
data-file negations, so both CSVs are picked up automatically; see
``examples/single_agent/config_variants/nonudge/NOTES.md`` ("Commit note")
for the verification. No commit-time step is needed any more.
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
VARIANT = BASE / "config_variants" / "nonudge"

NUDGE_NOTE = (
    'Note: If no flood occurred this year, since no immediate threat, '
    'most people would choose "Do Nothing."'
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_variant_directory_exists():
    assert VARIANT.is_dir(), VARIANT


def test_agent_types_yaml_is_byte_identical_to_base():
    assert _read(VARIANT / "agent_types.yaml") == _read(BASE / "agent_types.yaml")


def test_skill_registry_yaml_is_byte_identical_to_base():
    assert _read(VARIANT / "skill_registry.yaml") == _read(BASE / "skill_registry.yaml")


def test_agent_initial_profiles_csv_is_byte_identical_to_base():
    assert _read(VARIANT / "agent_initial_profiles.csv") == _read(BASE / "agent_initial_profiles.csv")


def test_flood_years_csv_is_byte_identical_to_base():
    assert _read(VARIANT / "flood_years.csv") == _read(BASE / "flood_years.csv")


def test_household_txt_differs_from_base_by_exactly_the_nudge_note_line():
    base_text = _read(BASE / "config" / "prompts" / "household.txt")
    variant_text = _read(VARIANT / "config" / "prompts" / "household.txt")

    assert NUDGE_NOTE in base_text, "fixture assumption: the base template still has the note"
    assert NUDGE_NOTE not in variant_text, "the no-nudge variant must not carry the note"

    # Removing the note line (and the blank line that followed it, per the
    # variant's own construction -- see NOTES.md "The removed line") from the
    # base text must reproduce the variant text exactly: no OTHER difference.
    base_lines = base_text.splitlines()
    note_idx = next(i for i, line in enumerate(base_lines) if line == NUDGE_NOTE)
    reconstructed = base_lines[:note_idx] + base_lines[note_idx + 1:]
    variant_lines = variant_text.splitlines()
    assert reconstructed == variant_lines, (
        "the nonudge variant differs from the base template by more than "
        "just the nudge-note line; re-sync it (see NOTES.md resync history)"
    )


def test_variant_agent_types_yaml_carries_the_flags_the_ibr_analysis_needs():
    """Regression guard for a drift class this variant has hit twice (see
    NOTES.md "Resync history"): the variant's own copy of agent_types.yaml
    must carry every global_config.audit / global_config.governance flag
    the base does, not a stale copy taken before one was added.
    Content-equality above already proves this for the WHOLE file; this
    test names the specific keys so a future stale-copy bug fails with a
    clear message instead of a generic diff."""
    import yaml

    with open(VARIANT / "agent_types.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    governance = cfg["global_config"]["governance"]
    audit = cfg["global_config"]["audit"]
    assert governance["appraisal_freeze"] is True
    assert governance["rule_id_prefix"] is False
    assert governance["plain_action_names"] is True
    assert audit["retry_prompt_columns"] is True
    assert audit["initial_proposal_columns"] is True
    assert audit["corrected_status_columns"] is True
    assert audit["attempt_columns"] is True
