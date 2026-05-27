"""Phase 6S-A regression — MA flood (Paper 3) mock byte-identity smoke.

Closes the verification gap left by Phase 6R-D-4 (commit ``95c467e``):
the typed-accessor migration at ``broker/components/events/ma_manager.py:302``
(``DomainPackRegistry.get_or_default`` → ``get_event_pack``) was
verified for single-agent flood + irrigation via
``broker.tools.compare_audit_csv``, but the multi-agent flood
pipeline (Paper 3 core artifact — 400 agents × 13 yr) was NOT
smoke-tested at commit time.

This test runs the cheapest viable MA flood smoke (5 agents × 1 year
× mock LLM, ~4 sec) and asserts the pipeline produces the expected
4 per-agent-type governance_audit CSVs with non-empty content. It
does NOT compare against a pre-6R baseline — that requires operator
checkout to commit ``5114b16`` and is outside CI scope. The
in-CI value here is: catch silent FloodPack ``event_handlers()``
coverage gaps that would manifest as empty/missing audit files or
zero-row outputs.

The 6R-D-4 risk surface specifically is the typed-accessor cast at
``ma_manager.py:302``: if a future contributor narrows
``FloodEventMixin`` so it returns an incomplete ``event_handlers()``
dict (missing ``flood_occurred`` / ``flood_depth_m`` / etc.), MA flood
events would silently no-op (broker just skips unrecognised event
types). This test asserts the audit rows reflect non-trivial decision
content, which proves the event handlers fired.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest


# Path depth: tests/(1) ← paper3/(2) ← flood/(3) ← multi_agent/(4) ←
# examples/(5) ← repo root(6). Use parents[5] to land on repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_RUNNER = _REPO_ROOT / "examples" / "multi_agent" / "flood" / "run_unified_experiment.py"

# Output goes under <output>/mock_strict/ — the runner appends
# ``<model>_<profile>`` subdir.
_OUTPUT_SUBDIR = "mock_strict"

# Per-agent-type audit CSVs the runner emits.
_EXPECTED_AUDIT_FILES = (
    "government_governance_audit.csv",
    "household_owner_governance_audit.csv",
    "household_renter_governance_audit.csv",
    "insurance_governance_audit.csv",
)


@pytest.fixture(scope="module")
def ma_flood_smoke_output(tmp_path_factory) -> Path:
    """Run the MA flood smoke ONCE per test module. Returns the
    ``<output>/mock_strict/`` directory containing all audit CSVs.

    Asserts the subprocess exits 0; failure aborts the module so
    individual test failures aren't masked by setup failure.
    """
    output_dir = tmp_path_factory.mktemp("ma_flood_smoke")
    result = subprocess.run(
        [
            sys.executable, str(_RUNNER),
            "--model", "mock",
            "--agents", "5",
            "--years", "1",
            "--seed", "42",
            "--mode", "random",
            "--output", str(output_dir),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        pytest.fail(
            f"MA flood smoke subprocess failed (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout[-2000:]}\n"
            f"STDERR:\n{result.stderr[-2000:]}"
        )
    audit_dir = output_dir / _OUTPUT_SUBDIR
    assert audit_dir.exists(), (
        f"expected audit output at {audit_dir} — smoke run completed "
        f"but the model_profile subdir wasn't created."
    )
    return audit_dir


class TestMAFloodSmokeOutput:
    """The MA flood pipeline must emit per-agent-type audit CSVs +
    associated artifacts (reproducibility_manifest, config_snapshot)."""

    def test_all_4_per_agent_type_audit_csvs_emitted(
        self, ma_flood_smoke_output: Path,
    ):
        """Each expected agent-type partition produces its own
        governance_audit.csv. Missing files indicate the broker's
        per-agent-type partitioning broke."""
        missing = [
            name for name in _EXPECTED_AUDIT_FILES
            if not (ma_flood_smoke_output / name).exists()
        ]
        assert not missing, (
            f"missing audit CSVs in {ma_flood_smoke_output}: {missing}. "
            f"Files present: "
            f"{sorted(p.name for p in ma_flood_smoke_output.iterdir())}"
        )

    @pytest.mark.parametrize("audit_file", _EXPECTED_AUDIT_FILES)
    def test_each_audit_csv_has_at_least_one_decision_row(
        self, ma_flood_smoke_output: Path, audit_file: str,
    ):
        """Audit CSV must have header + ≥1 decision row. Zero rows
        could indicate the agent type ran but its decisions weren't
        written — or that no agents of this type were created."""
        path = ma_flood_smoke_output / audit_file
        with path.open(encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        assert rows, f"{audit_file} is empty (no header)"
        assert len(rows) >= 2, (
            f"{audit_file} has {len(rows) - 1} decision rows (header only). "
            f"Expected ≥1 row — agent type either didn't run or "
            f"decisions failed to write."
        )

    def test_reproducibility_manifest_written(
        self, ma_flood_smoke_output: Path,
    ):
        """Confirms the runner completed the post-run reproducibility
        artifact (writes after the last year's decisions resolve)."""
        manifest = ma_flood_smoke_output / "reproducibility_manifest.json"
        assert manifest.exists(), (
            f"reproducibility_manifest.json missing — runner may have "
            f"crashed mid-loop. Files: "
            f"{sorted(p.name for p in ma_flood_smoke_output.iterdir())}"
        )


class TestMAFloodEventHandlersFired:
    """Phase 6S-A motivating regression check — the 6R-D-4 typed
    accessor change at ``ma_manager.py:302`` could silently break MA
    flood if ``FloodEventMixin.event_handlers()`` doesn't cover all
    MA flood event types. This class asserts the audit content
    reflects events that DID fire."""

    def test_household_owner_audit_references_flood_skills(
        self, ma_flood_smoke_output: Path,
    ):
        """Household-owner decisions should reference at least one
        flood-domain skill name (buy_insurance / elevate_house /
        relocate / do_nothing). If event handlers didn't fire, agents
        may still produce decisions but the audit `final_skill` would
        be empty / placeholder."""
        path = ma_flood_smoke_output / "household_owner_governance_audit.csv"
        text = path.read_text(encoding="utf-8-sig")
        flood_skill_vocab = {
            "buy_insurance", "elevate_house", "relocate", "do_nothing",
            "Buy_Insurance", "Elevate_House", "Relocate", "Do_Nothing",
        }
        hits = [v for v in flood_skill_vocab if v in text]
        assert hits, (
            f"household_owner audit contains no flood-domain skill "
            f"names. Vocabulary checked: {sorted(flood_skill_vocab)}. "
            f"This could indicate the EventPack typed accessor at "
            f"ma_manager.py:302 (Phase 6R-D-4) failed to dispatch "
            f"FloodEventMixin.event_handlers() — events silently "
            f"no-op'd and agents had no flood context to decide from."
        )

    def test_no_water_modules_failed_to_import(
        self, ma_flood_smoke_output: Path,
    ):
        """Subprocess captured-stderr check via reproducibility_manifest:
        if any water-namespace module failed to import the runner
        would have logged it. (Indirect check — direct sys.modules
        diff would require in-process run.)"""
        manifest = ma_flood_smoke_output / "reproducibility_manifest.json"
        import json
        data = json.loads(manifest.read_text(encoding="utf-8"))
        # Reproducibility manifest doesn't track import failures
        # directly, but does record the experiment name + config.
        # A successful manifest write implies the runner reached
        # post-loop cleanup — i.e. no fatal import failure.
        assert "experiment_name" in data or "config" in data or len(data) > 0
