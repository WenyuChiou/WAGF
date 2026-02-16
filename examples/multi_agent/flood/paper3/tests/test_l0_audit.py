"""Tests for L0 documentation audit (P2.1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import pytest
from validation.metrics.l0_audit import (
    run_l0_audit,
    L0AuditReport,
    CHECKLIST_ITEMS,
    _scan_text_for_keywords,
)


class TestKeywordScanning:
    def test_finds_keywords(self):
        text = "The purpose of this model is to simulate flood adaptation."
        matched = _scan_text_for_keywords(text, ["purpose", "flood", "missing"])
        assert "purpose" in matched
        assert "flood" in matched
        assert "missing" not in matched

    def test_case_insensitive(self):
        text = "LLM-based Agent simulation using GEMMA model"
        matched = _scan_text_for_keywords(text, ["llm", "gemma"])
        assert len(matched) == 2

    def test_empty_text(self):
        matched = _scan_text_for_keywords("", ["purpose"])
        assert matched == []


class TestL0Audit:
    def test_full_doc_passes(self):
        """A comprehensive doc should pass most checklist items."""
        full_doc = """
        # Model Description

        ## Purpose
        This agent-based model simulates household flood adaptation decisions.
        The objective is to reproduce empirical patterns of insurance uptake.

        ## Entities and State Variables
        Agents represent households with attributes: income, flood_zone, tenure.
        Temporal scale: annual decisions over 13 years.
        Spatial scale: Passaic River Basin census tracts.

        ## Process Overview and Scheduling
        Each year proceeds in three phases: government, insurance, household.
        The lifecycle schedule runs sequentially.

        ## Design Concepts
        Emergence arises from individual adaptation decisions.
        Agents interact through social networks. Stochasticity in LLM sampling.

        ## Initialization
        Agents are initialized from NJ household survey data (N=400).

        ## Input Data
        External data includes FEMA flood maps, census tract GIS data,
        and survey datasets.

        ## Submodels
        Decision rules follow Protection Motivation Theory (PMT).
        The behavioral theory maps TP×CP constructs to coherent actions.
        Equations for premium calculation use CRS discount formulas.

        ## LLM Configuration
        Uses Gemma 3 4B (gemma3:4b) via Ollama. Temperature=0.7, top_p=0.9.

        ## Prompt Template
        System prompt defines persona with demographic attributes.

        ## Governance
        Semantic governance validates proposals against PMT rules.
        Invalid actions are rejected and retried.

        ## Hallucination Mitigation
        Impossible actions (elevate when already elevated) are detected
        and blocked by the hallucination checker.

        ## Reproducibility
        Random seed=42 for all experiments. Code available on GitHub.
        Data availability statement included.
        """
        report = run_l0_audit(extra_text=full_doc)
        assert report.passes
        assert report.score >= 0.80
        assert report.passed_items >= 12

    def test_empty_doc_fails(self):
        report = run_l0_audit(extra_text="")
        assert not report.passes
        assert report.score == 0.0
        assert report.passed_items == 0

    def test_partial_doc(self):
        """Doc with only ODD items but no LLM items."""
        partial = """
        Purpose: simulate flood decisions.
        Agents with state variables at annual scale.
        Sequential process scheduling.
        Emergence and interaction observed.
        Initialization from survey data.
        Input data from census.
        Submodel equations for damage calculation.
        Seed=42 for reproducibility.
        """
        report = run_l0_audit(extra_text=partial)
        odd_cat = report.by_category.get("ODD", {})
        assert odd_cat.get("passed", 0) >= 5
        llm_cat = report.by_category.get("LLM", {})
        assert llm_cat.get("passed", 0) <= 1

    def test_from_file(self, tmp_path):
        """Test loading from actual file."""
        doc = tmp_path / "model_description.md"
        doc.write_text("# Purpose\nThe purpose is to simulate agents.", encoding="utf-8")
        report = run_l0_audit(doc_path=doc)
        assert report.passed_items >= 1
        assert str(doc) in report.sources_checked

    def test_multiple_config_files(self, tmp_path):
        doc = tmp_path / "readme.md"
        doc.write_text("Agent-based model with LLM decisions.", encoding="utf-8")
        cfg = tmp_path / "config.yaml"
        cfg.write_text("temperature: 0.7\ntop_p: 0.9\nmodel: gemma3:4b", encoding="utf-8")
        report = run_l0_audit(doc_path=doc, config_paths=[cfg])
        assert len(report.sources_checked) == 2

    def test_custom_checklist(self):
        custom = [
            {"id": "C1", "category": "Custom", "name": "Test item",
             "description": "test", "keywords": ["unicorn"]},
        ]
        report = run_l0_audit(extra_text="no match here", checklist=custom)
        assert report.total_items == 1
        assert report.passed_items == 0

        report2 = run_l0_audit(extra_text="unicorn spotted!", checklist=custom)
        assert report2.passed_items == 1

    def test_report_structure(self):
        report = run_l0_audit(extra_text="purpose and seed")
        assert isinstance(report.items, list)
        assert isinstance(report.by_category, dict)
        assert isinstance(report.sources_checked, list)
        assert 0.0 <= report.score <= 1.0

    def test_default_checklist_count(self):
        """Default checklist has 15 items across 3 categories."""
        assert len(CHECKLIST_ITEMS) == 15
        cats = set(item["category"] for item in CHECKLIST_ITEMS)
        assert cats == {"ODD", "LLM", "Reproducibility"}
