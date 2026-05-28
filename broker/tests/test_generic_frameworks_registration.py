"""
Phase 6T-F prep regression tests for the generic-framework
registry extraction.

Closes a Phase-6P-A-class genericity leak: pre-this-commit the
``utility`` and ``financial`` framework METADATA lived in
``broker/domains/water/thinking_checks.py``. Now they live in
``broker/validators/governance/frameworks/``, alongside the NEW
``narrative_diffusion`` framework.

What these tests pin
====================

1. Generic-framework metadata IS in ``FRAMEWORK_LABEL_ORDERS`` /
   ``FRAMEWORK_CONSTRUCTS`` after importing
   ``broker.validators.governance``. The new
   ``narrative_diffusion`` framework is among them. Pre-fix
   ``utility`` + ``financial`` ONLY appeared after importing
   ``broker.domains.water``.
2. ``NarrativeDiffusionFramework`` class is registered in the
   psychometric ``_FRAMEWORK_REGISTRY`` via
   ``broker.core.psychometric.get_framework("narrative_diffusion")``.
3. The new module file ``frameworks/__init__.py`` does NOT import
   from ``broker.domains.water`` (AST-scan); the genericity
   contract is enforced at the source level.

Test isolation
==============

These tests do NOT manipulate ``sys.modules`` or reload broker
modules — doing so would wipe the ``FRAMEWORK_LABEL_ORDERS`` dict
that other tests in the same pytest session depend on. Instead
we inspect the live registry + verify source-level genericity
via AST scan. The "registers on import" claim is verified by the
test simply running successfully — pytest's session-wide import
of broker.* modules already triggers the registration.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────
# Class 1 — Generic frameworks present in the live registry
# ─────────────────────────────────────────────────────────────────────


class TestGenericFrameworksPresent:
    """Verify the live state of ``FRAMEWORK_LABEL_ORDERS`` +
    ``FRAMEWORK_CONSTRUCTS`` includes the three generic frameworks
    after a normal broker.validators.governance import path. Test
    file uses normal imports — assertion is on the in-memory dicts
    populated by the import-time registration in
    ``broker/validators/governance/frameworks/__init__.py``."""

    def test_utility_metadata_registered(self):
        import broker.validators.governance  # noqa: F401
        from broker.validators.governance.thinking_validator import (
            FRAMEWORK_LABEL_ORDERS,
            FRAMEWORK_CONSTRUCTS,
        )
        assert "utility" in FRAMEWORK_LABEL_ORDERS
        assert FRAMEWORK_LABEL_ORDERS["utility"] == {"L": 0, "M": 1, "H": 2}
        assert FRAMEWORK_CONSTRUCTS["utility"]["primary"] == "BUDGET_UTIL"

    def test_financial_metadata_registered(self):
        import broker.validators.governance  # noqa: F401
        from broker.validators.governance.thinking_validator import (
            FRAMEWORK_LABEL_ORDERS,
            FRAMEWORK_CONSTRUCTS,
        )
        assert "financial" in FRAMEWORK_LABEL_ORDERS
        assert FRAMEWORK_LABEL_ORDERS["financial"] == {"C": 0, "M": 1, "A": 2}
        assert FRAMEWORK_CONSTRUCTS["financial"]["primary"] == "RISK_APPETITE"

    def test_narrative_diffusion_metadata_registered(self):
        import broker.validators.governance  # noqa: F401
        from broker.validators.governance.thinking_validator import (
            FRAMEWORK_LABEL_ORDERS,
            FRAMEWORK_CONSTRUCTS,
        )
        assert "narrative_diffusion" in FRAMEWORK_LABEL_ORDERS
        assert FRAMEWORK_LABEL_ORDERS["narrative_diffusion"] == {
            "VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4,
        }
        assert FRAMEWORK_CONSTRUCTS["narrative_diffusion"]["primary"] == "SALIENCE"
        assert set(FRAMEWORK_CONSTRUCTS["narrative_diffusion"]["all"]) == {
            "SALIENCE", "VIRALITY", "AUDIENCE_FIT", "NARRATIVE_CONSISTENCY",
        }


# ─────────────────────────────────────────────────────────────────────
# Class 2 — Generic frameworks registered in source live in the
#            generic broker home, NOT water-domain
# ─────────────────────────────────────────────────────────────────────


class TestSourceLocationProvesExtraction:
    """The extraction was performed at the SOURCE level — verify
    that water-domain thinking_checks.py no longer carries the
    utility / financial metadata entries (the pre-Phase-6T-F-prep
    leak point), and that the generic frameworks/ home DOES carry
    them."""

    def test_water_thinking_checks_does_not_register_utility(self):
        """Source-level check: water/thinking_checks.py's
        ``WATER_FRAMEWORK_LABEL_ORDERS`` constant must NOT include the
        generic frameworks (Phase 6T-F-prep moved utility/financial;
        Phase 6U-F (2026-05-28) moved pmt for the same reason — PMT
        is a cross-domain behavioural framework, not water-specific)."""
        from broker.domains.water.thinking_checks import (
            WATER_FRAMEWORK_LABEL_ORDERS,
            WATER_FRAMEWORK_CONSTRUCTS,
            WATER_LABEL_MAPPINGS,
        )
        # Water-specific stays (irrigation-domain frameworks):
        assert "dual_appraisal" in WATER_FRAMEWORK_LABEL_ORDERS
        assert "cognitive_appraisal" in WATER_FRAMEWORK_LABEL_ORDERS
        # Generic moved out:
        assert "pmt" not in WATER_FRAMEWORK_LABEL_ORDERS
        assert "utility" not in WATER_FRAMEWORK_LABEL_ORDERS
        assert "financial" not in WATER_FRAMEWORK_LABEL_ORDERS
        assert "pmt" not in WATER_FRAMEWORK_CONSTRUCTS
        assert "utility" not in WATER_FRAMEWORK_CONSTRUCTS
        assert "financial" not in WATER_FRAMEWORK_CONSTRUCTS
        assert "pmt" not in WATER_LABEL_MAPPINGS
        assert "utility" not in WATER_LABEL_MAPPINGS
        assert "financial" not in WATER_LABEL_MAPPINGS

    def test_pmt_registered_via_generic_home(self):
        """Phase 6U-F regression: PMT is registered when only the
        generic frameworks package is imported — no water domain
        import required. This is the WIN of moving PMT metadata to
        the generic home: callers that only need PMT metadata don't
        have to pull in the water-domain skill modules."""
        import subprocess
        import sys
        from pathlib import Path

        gate_script = r"""
import sys
from broker.validators.governance.frameworks import list_registered_frameworks
assert "pmt" in list_registered_frameworks(), \
    f"PMT not registered after generic-frameworks import: {sorted(list_registered_frameworks())}"
# Water must NOT be loaded
water_modules = sorted(m for m in sys.modules if m.startswith("broker.domains.water"))
assert not water_modules, f"water modules leaked into PMT-only path: {water_modules}"
print("OK")
"""
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-c", gate_script],
            capture_output=True,
            text=True,
            cwd=str(repo),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"PMT-via-generic regression failed:\nSTDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    def test_generic_frameworks_module_carries_constants(self):
        """The new frameworks/ module exports the three metadata
        bundles as module-level constants."""
        from broker.validators.governance.frameworks import (
            UTILITY_LABEL_ORDER,
            UTILITY_CONSTRUCTS,
            FINANCIAL_LABEL_ORDER,
            FINANCIAL_CONSTRUCTS,
            NARRATIVE_DIFFUSION_LABEL_ORDER,
            NARRATIVE_DIFFUSION_CONSTRUCTS,
        )
        assert UTILITY_LABEL_ORDER == {"L": 0, "M": 1, "H": 2}
        assert FINANCIAL_LABEL_ORDER == {"C": 0, "M": 1, "A": 2}
        assert NARRATIVE_DIFFUSION_LABEL_ORDER == {
            "VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4,
        }


# ─────────────────────────────────────────────────────────────────────
# Class 3 — NarrativeDiffusionFramework class
# ─────────────────────────────────────────────────────────────────────


class TestNarrativeDiffusionFrameworkClass:
    """The NEW ``NarrativeDiffusionFramework`` lives in the generic
    home (not water) — verify its construct + behavior surface."""

    @pytest.fixture
    def framework(self):
        import broker.validators.governance  # noqa: F401
        from broker.core.psychometric import get_framework
        # get_framework returns an INSTANCE (calls the class) not a class.
        instance = get_framework("narrative_diffusion")
        assert instance is not None, (
            "NarrativeDiffusionFramework not in psychometric registry. "
            "Did broker.validators.governance.frameworks.__init__.py "
            "register the class via register_framework()?"
        )
        return instance

    def test_framework_class_name(self, framework):
        assert framework.name == "Narrative Diffusion"

    def test_constructs_have_canonical_four(self, framework):
        constructs = framework.get_constructs()
        assert set(constructs.keys()) == {
            "SALIENCE",
            "VIRALITY",
            "AUDIENCE_FIT",
            "NARRATIVE_CONSISTENCY",
        }

    def test_label_values_5_point_likert(self, framework):
        constructs = framework.get_constructs()
        assert constructs["SALIENCE"].values == ["VL", "L", "M", "H", "VH"]

    def test_validate_coherence_warns_on_clickbait_signature(self, framework):
        """High virality + low salience = unusual combination → warn."""
        result = framework.validate_coherence({
            "SALIENCE": "VL",
            "VIRALITY": "VH",
        })
        assert result.valid is True
        assert any("clickbait" in w.lower() for w in result.warnings)

    def test_expected_behavior_returns_generic_verbs(self, framework):
        """High salience + high virality → ``amplify`` + ``share``
        (generic verbs, NOT domain-specific skill names)."""
        actions = framework.get_expected_behavior({
            "SALIENCE": "H",
            "VIRALITY": "H",
        })
        assert "amplify" in actions

        actions_quiet = framework.get_expected_behavior({
            "SALIENCE": "VL",
            "VIRALITY": "VL",
        })
        assert "stay_silent" in actions_quiet


# ─────────────────────────────────────────────────────────────────────
# Class 4 — Source-level genericity (AST scan)
# ─────────────────────────────────────────────────────────────────────


class TestFrameworksModuleGenericity:
    """The new ``broker/validators/governance/frameworks/`` module
    MUST NOT import from ``broker.domains.water`` or any
    ``examples.*`` package."""

    GUARDED_FILES = [
        "broker/validators/governance/frameworks/__init__.py",
        "broker/validators/governance/frameworks/narrative_diffusion.py",
        # Phase 6U-F (2026-05-28): pmt.py is the new PMT-metadata home;
        # it must remain water-import-free for the same reason as the
        # other framework metadata modules.
        "broker/validators/governance/frameworks/pmt.py",
    ]

    FORBIDDEN_PREFIXES = (
        "broker.domains.water",
        "examples.",
    )

    @pytest.mark.parametrize("rel_path", GUARDED_FILES)
    def test_module_imports_no_domain_specific_code(self, rel_path):
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / rel_path
        assert path.exists(), f"Guarded file missing: {rel_path}"
        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(self.FORBIDDEN_PREFIXES), (
                        f"{rel_path} imports forbidden module "
                        f"{alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith(self.FORBIDDEN_PREFIXES), (
                    f"{rel_path} imports from forbidden module "
                    f"{mod!r}"
                )
