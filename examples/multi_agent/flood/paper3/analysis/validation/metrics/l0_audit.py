"""
L0 Documentation Audit — Automated checklist for LLM-ABM documentation.

Checks whether a model's documentation meets minimum standards based on
the ODD (Overview, Design concepts, Details) protocol and LLM-specific
requirements. Returns a structured audit report with pass/fail per item.

Usage:
    from validation.metrics.l0_audit import run_l0_audit, L0AuditReport

    report = run_l0_audit(
        doc_path=Path("paper/model_description.md"),
        config_paths=[Path("config/agents.yaml"), Path("config/skills.yaml")],
    )
    print(f"Score: {report.score:.0%}, Pass: {report.passes}")
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# =============================================================================
# ODD + LLM-ABM Checklist Items
# =============================================================================

CHECKLIST_ITEMS = [
    # ODD Protocol (Grimm et al., 2006; 2010; 2020)
    {
        "id": "ODD1",
        "category": "ODD",
        "name": "Purpose and patterns",
        "description": "States the model's purpose and the patterns it aims to reproduce",
        "keywords": ["purpose", "objective", "goal", "pattern", "reproduce", "replicate"],
    },
    {
        "id": "ODD2",
        "category": "ODD",
        "name": "Entities, state variables, scales",
        "description": "Lists agent types, their state variables, and spatial/temporal scales",
        "keywords": ["agent", "entity", "state variable", "attribute", "scale", "temporal", "spatial"],
    },
    {
        "id": "ODD3",
        "category": "ODD",
        "name": "Process overview and scheduling",
        "description": "Describes the sequence of processes and their scheduling",
        "keywords": ["process", "schedule", "sequence", "step", "phase", "lifecycle", "tick", "year"],
    },
    {
        "id": "ODD4",
        "category": "ODD",
        "name": "Design concepts",
        "description": "Covers emergence, adaptation, objectives, learning, prediction, sensing, interaction, stochasticity, observation",
        "keywords": ["emergence", "adaptation", "learning", "interaction", "stochastic", "observation", "sensing"],
    },
    {
        "id": "ODD5",
        "category": "ODD",
        "name": "Initialization",
        "description": "Describes how the model is initialized (agent attributes, environment state)",
        "keywords": ["initial", "initialization", "setup", "configure", "starting condition"],
    },
    {
        "id": "ODD6",
        "category": "ODD",
        "name": "Input data",
        "description": "Lists external data inputs used to drive the model",
        "keywords": ["input data", "external data", "dataset", "census", "survey", "GIS", "raster"],
    },
    {
        "id": "ODD7",
        "category": "ODD",
        "name": "Submodels",
        "description": "Details each submodel/process with equations or rules",
        "keywords": ["submodel", "equation", "rule", "formula", "algorithm", "decision"],
    },
    # LLM-specific requirements
    {
        "id": "LLM1",
        "category": "LLM",
        "name": "LLM model specification",
        "description": "States the LLM model used (name, version, parameters, provider)",
        "keywords": ["llm", "language model", "gpt", "gemma", "llama", "claude", "model version", "parameter"],
    },
    {
        "id": "LLM2",
        "category": "LLM",
        "name": "Prompt template documentation",
        "description": "Documents the prompt template(s) used for agent decision-making",
        "keywords": ["prompt", "template", "system prompt", "instruction", "persona"],
    },
    {
        "id": "LLM3",
        "category": "LLM",
        "name": "Temperature and sampling",
        "description": "Reports temperature, top-p, and other sampling parameters",
        "keywords": ["temperature", "top_p", "top-p", "sampling", "top_k", "top-k"],
    },
    {
        "id": "LLM4",
        "category": "LLM",
        "name": "Governance/guardrail documentation",
        "description": "Documents validation rules, governance constraints, or guardrails",
        "keywords": ["governance", "guardrail", "validator", "constraint", "rule", "filter", "rejection"],
    },
    {
        "id": "LLM5",
        "category": "LLM",
        "name": "Behavioral theory grounding",
        "description": "Identifies the behavioral theory linking constructs to actions",
        "keywords": ["behavioral theory", "pmt", "protection motivation", "tpb", "theory of planned",
                     "prospect theory", "bounded rationality", "construct"],
    },
    {
        "id": "LLM6",
        "category": "LLM",
        "name": "Hallucination mitigation",
        "description": "Describes how impossible/invalid LLM outputs are detected and handled",
        "keywords": ["hallucination", "impossible", "invalid", "sanity check", "output validation"],
    },
    # Reproducibility requirements
    {
        "id": "REP1",
        "category": "Reproducibility",
        "name": "Random seed reporting",
        "description": "Reports random seeds used for experiment reproducibility",
        "keywords": ["seed", "random seed", "reproducib", "replicate"],
    },
    {
        "id": "REP2",
        "category": "Reproducibility",
        "name": "Code/data availability",
        "description": "States code repository and data availability",
        "keywords": ["code availab", "data availab", "repository", "github", "zenodo", "open source"],
    },
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class L0CheckItem:
    """Result for a single checklist item."""
    id: str
    category: str
    name: str
    found: bool
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class L0AuditReport:
    """L0 documentation audit report."""
    items: List[L0CheckItem]
    score: float
    total_items: int
    passed_items: int
    by_category: Dict[str, Dict[str, int]]
    sources_checked: List[str]

    @property
    def passes(self) -> bool:
        """Pass if >= 80% of items found."""
        return self.score >= 0.80


# =============================================================================
# Audit Functions
# =============================================================================

def _scan_text_for_keywords(text: str, keywords: List[str]) -> List[str]:
    """Find which keywords appear in text (case-insensitive)."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _load_text_sources(
    doc_path: Optional[Path] = None,
    config_paths: Optional[List[Path]] = None,
    extra_text: Optional[str] = None,
) -> tuple:
    """Load and combine text from documentation and config sources.

    Returns:
        Tuple of (combined_text, source_names).
    """
    texts = []
    sources = []

    if doc_path is not None and doc_path.exists():
        text = doc_path.read_text(encoding="utf-8")
        texts.append(text)
        sources.append(str(doc_path))

    if config_paths:
        for cp in config_paths:
            if cp.exists():
                text = cp.read_text(encoding="utf-8")
                texts.append(text)
                sources.append(str(cp))

    if extra_text:
        texts.append(extra_text)
        sources.append("<extra_text>")

    return "\n".join(texts), sources


def run_l0_audit(
    doc_path: Optional[Path] = None,
    config_paths: Optional[List[Path]] = None,
    extra_text: Optional[str] = None,
    checklist: Optional[List[Dict]] = None,
) -> L0AuditReport:
    """Run L0 documentation audit against checklist.

    Scans documentation files and config files for keywords associated
    with each checklist item. Reports which items are found/missing.

    Args:
        doc_path: Path to main model documentation (MD, TXT, etc.).
        config_paths: Additional config/documentation files to scan.
        extra_text: Optional raw text to include in the scan.
        checklist: Custom checklist items. Defaults to CHECKLIST_ITEMS.

    Returns:
        L0AuditReport with per-item results and overall score.
    """
    if checklist is None:
        checklist = CHECKLIST_ITEMS

    combined_text, sources = _load_text_sources(doc_path, config_paths, extra_text)

    items = []
    category_counts: Dict[str, Dict[str, int]] = {}

    for check in checklist:
        matched = _scan_text_for_keywords(combined_text, check["keywords"])
        found = len(matched) > 0

        items.append(L0CheckItem(
            id=check["id"],
            category=check["category"],
            name=check["name"],
            found=found,
            matched_keywords=matched,
        ))

        cat = check["category"]
        if cat not in category_counts:
            category_counts[cat] = {"total": 0, "passed": 0}
        category_counts[cat]["total"] += 1
        if found:
            category_counts[cat]["passed"] += 1

    total = len(items)
    passed = sum(1 for i in items if i.found)
    score = passed / total if total > 0 else 0.0

    return L0AuditReport(
        items=items,
        score=round(score, 4),
        total_items=total,
        passed_items=passed,
        by_category=category_counts,
        sources_checked=sources,
    )
