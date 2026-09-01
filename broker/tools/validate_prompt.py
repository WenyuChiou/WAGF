"""Static validator for agent prompt templates vs YAML config (Phase 6C-v4 G3).

Catches the 6 BLOCKERs surfaced by the vaccination_demo PoC (see
``.ai/vaccination_poc_findings_2026-05-10.md``) at config-time instead of
runtime. Examples:

* Prompt placeholder ``{response_format}`` referenced but YAML has no
  ``shared.response_format.fields`` block.
* Inline JSON example in the prompt uses key ``susceptibility_appraisal``
  but ``response_format.fields`` declares ``susceptibility_assessment``.
* ``response_format.fields[*].construct`` declared but ``parsing.constructs``
  missing the matching entry — parser cannot extract appraisal labels.
* ``actions:`` block missing — parser's ``get_valid_actions`` returns ``[]``
  and the LLM's skill choice is silently rejected.
* A governance profile declares thinking/identity rules constraining only a
  subset of available skills — the agent may converge on the unconstrained
  subset while governance silently looks effective elsewhere (harness-
  engineering flaw 5 — Requisite Variety). Warn when per-profile skill
  coverage is below 80%.

Usage::

    python -m broker.tools.validate_prompt \\
        examples/vaccination_demo/config/agent_types.yaml \\
        --agent-type individual

The CLI exits 0 if no issues, 1 if any ERROR-level issue, 2 if only WARN
issues are present. Issues are printed in ``severity: file:line message``
order so editors can navigate them.

Reference:
- ``docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`` — full schema reference
- ``broker/components/context/builder.py:SafeFormatter`` — runtime behavior
  this CLI tries to anticipate

Added: 2026-05-10.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Phase 6R-B-3 (audit cluster E #16): the registry lookup happens at
# validate-time to union the CLI's base placeholder allowlist with
# domain-specific extensions. Module-level import because
# ``broker.domains.registry`` is a first-party broker module — if it
# ever can't be imported, the CLI was broken at startup, not here.
from broker.domains.registry import DomainPackRegistry


# ---------------------------------------------------------------------------
# Known broker-filled placeholders (auto-injected by TieredContextBuilder
# at runtime — see broker/components/context/tiered.py:format_prompt).
# Keeping this list current is a maintenance burden but the only way to
# distinguish "user-domain placeholder" (which YAML should declare) from
# "broker placeholder" (which is always filled). When adding a new
# template_vars[key] = ... in tiered.py, append the key here.
# ---------------------------------------------------------------------------
BROKER_FILLED_PLACEHOLDERS: Set[str] = {
    # Identity / system
    "system_prompt",
    "agent_id",
    "agent_name",
    "agent_type",
    "narrative_persona",
    "step",
    "year",
    # Memory / context blocks
    "memory",
    "relevant_memories",
    "personal_section",
    "local_section",
    "global_section",
    "institutional_section",
    "priority_section",
    "state",
    "perception",
    "objectives",
    "skills",
    "skills_text",
    # Options / choices
    "options_text",
    "valid_choices_text",
    "response_format",
    "rating_scale",
    # Social
    "social_gossip",
    "neighbor_action_summary",
    "global_news",
    # Phase 6R-B-3 (2026-05-26): the 3 water-domain placeholder names
    # (``insurance_cost_text`` / ``mg_barrier_text`` /
    # ``renewal_fatigue_text``) that previously lived here have moved to
    # ``FloodDomainPack.prompt_placeholder_extensions()``. The CLI
    # unions this base set with the registered DomainPack's extensions
    # at validate-time (see ``_resolve_domain_extensions`` below). This
    # closes the asymmetric coverage flagged by Phase 6Q-K-3 (Layer 3
    # audit finding #16).
}


# ---------------------------------------------------------------------------
# Domain-specific placeholder extensions (Phase 6R-B-3)
# ---------------------------------------------------------------------------

def _resolve_domain_extensions(cfg: Dict[str, Any]) -> Set[str]:
    """Return the placeholder extensions for the YAML's declared domain.

    Reads ``global_config.governance.domain`` from the agent-types YAML
    (e.g. ``"flood"``, ``"traffic"``, ``"irrigation"``). Looks the name
    up in :class:`DomainPackRegistry`; if registered, returns
    ``pack.prompt_placeholder_extensions()``. If absent (e.g. the
    relevant example package wasn't imported, or the YAML has no
    ``domain:`` field), returns ``set()`` — flood YAMLs will get a
    spurious WARN for the 3 water names UNLESS the user imports
    ``examples.governed_flood`` before invoking the CLI.

    Auto-importing every example package would couple the validator
    to the example tree (and bloat startup). Document the import
    convention instead: callers wanting flood-extension coverage
    invoke ``python -m examples.governed_flood`` first (which has
    the same registration side-effect), OR run the CLI from a
    Python module that has already imported the relevant example.
    """
    domain = (
        cfg.get("global_config", {})
        .get("governance", {})
        .get("domain")
    )
    if not domain:
        return set()
    pack = DomainPackRegistry.get(domain)
    if pack is None:
        # Pack not registered — likely the relevant example package
        # wasn't imported. Return empty set; the WARN that fires is
        # the correct behaviour ("you reference {insurance_cost_text}
        # but didn't import the FloodDomainPack").
        return set()
    try:
        ext = pack.prompt_placeholder_extensions()
    except Exception:
        # Defensive: a broken pack must not crash the validator.
        # Most likely real failures are AttributeError (pack missing
        # the method) and TypeError (method returns a non-iterable).
        # Phase 6Q-D-4 graceful-degradation pattern.
        return set()
    return set(ext) if ext else set()


@dataclass
class Issue:
    severity: str  # "ERROR" or "WARN"
    location: str  # short location hint (file, "yaml: <agent_type>", etc.)
    message: str

    def format(self) -> str:
        return f"{self.severity:5} {self.location}: {self.message}"


# ---------------------------------------------------------------------------
# Canonical global_config key registry (2026-06-09 architecture review P0-4)
# ---------------------------------------------------------------------------
# THE canonical list of recognized ``global_config`` keys. Every feature flag
# in this repo is read via ``dict.get(key, <default-OFF>)``, so a typo'd key
# (e.g. ``dispatch_domain_physcial``) silently resolves to feature-OFF with
# zero warnings — the worst failure class for a default-OFF flag system.
# This registry + ``check_global_config_keys`` is the config-time net.
#
# When ADDING a new global_config consumer anywhere in broker/, add its key
# here in the same commit. Keys ending in ``_system`` are domain blobs
# (vaccination_system / water_system convention) and are exempt.

KNOWN_GLOBAL_CONFIG_KEYS: Set[str] = {
    "llm",          # LLM sampling config (model, num_ctx, num_predict, ...)
    "memory",       # memory-engine tuning
    "reflection",   # reflection cadence/questions
    "governance",   # see KNOWN_GOVERNANCE_KEYS
    "social_feeds", # see KNOWN_SOCIAL_FEEDS_KEYS (two-layer flag, Phase 6T-E.B)
    "coupling",     # see KNOWN_COUPLING_KEYS (two-layer flag, Phase 6V)
    "audit",        # see KNOWN_AUDIT_KEYS (opt-in column flags, all default OFF)
}

KNOWN_GOVERNANCE_KEYS: Set[str] = {
    "max_retries",               # agent_config.get_governance_max_retries
    "max_reports_per_retry",     # agent_config.get_governance_max_reports
    "domain",                    # ValidatorRegistry / DomainPack resolution
    "dispatch_domain_physical",  # opt-in engine PHYSICAL dispatch (d1cf7c3)
    "shuffle_options",           # broker/core/_skill_filtering.py positional-bias mitigation
    "retrieval",                 # agent_config.get_retrieval_config
    "drift",                     # agent_config.get_drift_config
    "population",                # agent_config.get_population_governance_config
    "policy_event_tiers",        # agent_config.get_policy_event_tiers_config
    # NOTE: governance.memory (bridge-importance / resolution_importance_policy
    # sub-block) is DISTINCT from the top-level global_config.memory block —
    # both are intentionally listed, one per level.
    "memory",                    # agent_config.get_bridge_importance_config
    # P0-1c/P0-1d arm-sweep keys. These were consumed before they were registered
    # here, so every config using them tripped a spurious "unknown key" WARN —
    # exactly the noise that trains operators to ignore this check.
    "advise",                    # agent_config.get_governance_advise
    "intervention_framing",      # agent_config.get_governance_intervention_framing
    "require_profile",           # agent_config.get_governance_require_profile
    "on_retry_exhausted",        # agent_config.get_governance_on_retry_exhausted
}

KNOWN_SOCIAL_FEEDS_KEYS: Set[str] = {
    "enable",           # broker/components/social/feed_flag.py
    "top_k",            # run_unified_experiment social-feed knobs
    "half_life_years",
}

KNOWN_COUPLING_KEYS: Set[str] = {
    "enable",  # broker/coupling/flag.py
}

# Every opt-in audit column flag, all default-OFF and all read through
# ``AgentTypeConfig``. Registered here because these flags fail CLOSED: a
# typo'd key resolves to its default, the run produces the UNCORRECTED columns,
# and nothing in the artifacts says the flag was ever requested — you find out
# when the analysis is already written. This check is the only config-time net.
KNOWN_AUDIT_KEYS: Set[str] = {
    "corrected_status_columns",  # agent_config.get_audit_corrected_status_columns (PR-3)
    "executed_skill_columns",    # agent_config.get_audit_executed_columns (F3)
    "initial_proposal_columns",  # agent_config.get_audit_initial_proposal_columns (P0-1a)
    "advise_columns",            # agent_config.get_audit_advise_columns (P0-1c)
    "param_columns",             # agent_config.get_audit_param_columns (6W-B6)
}


def check_global_config_keys(cfg: Dict[str, Any]) -> List[Issue]:
    """Validate ``global_config`` against the canonical key registry.

    WARN on unrecognized keys (a typo'd flag key silently resolves to its
    default — usually feature-OFF — so the warning is the only net).
    ERROR when ``governance.dispatch_domain_physical`` is truthy but
    ``governance.domain`` is absent: the accessor returns None in that case
    and the explicitly-requested dispatch silently no-ops.
    """
    issues: List[Issue] = []
    gc = cfg.get("global_config")
    if not isinstance(gc, dict):
        return issues

    loc = "yaml: global_config"
    for key in gc:
        if key in KNOWN_GLOBAL_CONFIG_KEYS or str(key).endswith("_system"):
            continue
        issues.append(Issue(
            "WARN", loc,
            f"unrecognized key '{key}' — no broker code reads it (typo'd "
            f"feature flags silently resolve default-OFF). Known keys: "
            f"{sorted(KNOWN_GLOBAL_CONFIG_KEYS)}; '<domain>_system' blobs are exempt.",
        ))

    def _check_block(name: str, known: Set[str]) -> Dict[str, Any]:
        block = gc.get(name)
        if block is not None and not isinstance(block, dict):
            # governance: true (scalar) would silently skip BOTH the sub-key
            # checks and the dispatch-without-domain ERROR — surface it.
            issues.append(Issue(
                "WARN", f"{loc}.{name}",
                f"expected a mapping, got {type(block).__name__} — the block "
                f"is ignored and none of its checks run.",
            ))
            return {}
        if not isinstance(block, dict):
            return {}
        for key in block:
            if key not in known:
                issues.append(Issue(
                    "WARN", f"{loc}.{name}",
                    f"unrecognized key '{key}' — known {name} keys: {sorted(known)}.",
                ))
        return block

    gov = _check_block("governance", KNOWN_GOVERNANCE_KEYS)
    _check_block("social_feeds", KNOWN_SOCIAL_FEEDS_KEYS)
    _check_block("coupling", KNOWN_COUPLING_KEYS)
    _check_block("audit", KNOWN_AUDIT_KEYS)

    dispatch = gov.get("dispatch_domain_physical")
    if isinstance(dispatch, dict):
        # Mapping form ({agent_type: domain}, Wave 3 P1-2): self-contained —
        # governance.domain not required. Empty domain values are config bugs.
        for atype, dom in dispatch.items():
            if not (isinstance(dom, str) and dom.strip()):
                issues.append(Issue(
                    "ERROR", f"{loc}.governance",
                    f"dispatch_domain_physical mapping entry {atype!r} has an "
                    f"empty/non-string domain ({dom!r}) — the accessor raises on this.",
                ))
    elif dispatch and not gov.get("domain"):
        issues.append(Issue(
            "ERROR", f"{loc}.governance",
            "dispatch_domain_physical is set but 'domain' is absent — the "
            "dispatch accessor raises on this (an explicitly-requested "
            "PHYSICAL dispatch must never silently no-op). Add "
            "'domain: <your_domain>' next to the flag, or use the "
            "{agent_type: domain} mapping form.",
        ))
    return issues


# ---------------------------------------------------------------------------
# Rule-shape lint (G4, 2026-06-10 audit review — the 6N-E class killer)
# ---------------------------------------------------------------------------
# The thinking-rule loader (broker/utils/agent_config.py get_thinking_rules)
# consumes EXACTLY these keys; anything else loads silently and is IGNORED —
# the Phase 6N-E failure class (a rule the author believes in, evaluating
# never). Verified dead siblings found 2026-06-10: precondition (dropped by
# the loader), expected_values/levels (only when_above/when_true are read),
# state_field/state_fields/aggregation/threshold/trigger_phrases (CoherenceRule
# fields with no loader and no evaluator), string conditions.
_THINKING_RULE_CONSUMED_KEYS: Set[str] = {
    "id", "construct", "conditions", "when_above", "when_true",
    "blocked_skills", "level", "message",
}
# Condition dicts: canonical short shape {construct, values}; the verbose
# 6N-E shape evaluates via the `field` fallback but `type`/`operator` are
# IGNORED (membership-in-values is the only semantic).
# `field` is consumed at EVALUATION time, not load time:
# broker/validators/agent/agent_validator.py:455
# (`cond.get("construct") or cond.get("field")`) — do not remove it from this
# set on a loader-only audit. NOTE these sets are thinking/coherence-rule
# specific; `identity_rules` has a DIFFERENT loader that reads `precondition`
# as live — extending this lint to identity_rules needs its own key set.
_CONDITION_CONSUMED_KEYS: Set[str] = {"construct", "values", "field"}


def check_rule_shapes(cfg: Dict[str, Any]) -> List[Issue]:
    """ERROR on accepted-but-ignored rule keys (silently-dead YAML).

    Scans ``thinking_rules`` / ``coherence_rules`` in agent-type blocks AND
    the top-level ``governance.<profile>.<agent_type>.thinking_rules`` form.
    Zero in-tree configs carry dead keys (scanned 2026-06-10), so ERROR
    severity is safe for the frozen regression net.
    """
    issues: List[Issue] = []

    def _lint_rules(rules: Any, loc: str) -> None:
        if not isinstance(rules, list):
            return
        for rule in rules:
            if not isinstance(rule, dict):
                issues.append(Issue(
                    "ERROR", loc,
                    f"rule entry is {type(rule).__name__}, not a mapping — "
                    f"string/scalar rules silently never evaluate.",
                ))
                continue
            rid = rule.get("id", rule.get("construct", "?"))
            extra = set(rule) - _THINKING_RULE_CONSUMED_KEYS
            if extra:
                issues.append(Issue(
                    "ERROR", loc,
                    f"rule {rid!r} carries key(s) the loader IGNORES "
                    f"{sorted(extra)} — the rule will not do what those keys "
                    f"promise (6N-E class). Consumed keys: "
                    f"{sorted(_THINKING_RULE_CONSUMED_KEYS)}.",
                ))
            conds = rule.get("conditions")
            if isinstance(conds, str):
                issues.append(Issue(
                    "ERROR", loc,
                    f"rule {rid!r}: conditions is a STRING — string conditions "
                    f"silently never trigger. Use a list of "
                    f"{{construct: X, values: [...]}} mappings.",
                ))
            elif isinstance(conds, list):
                for c in conds:
                    if not isinstance(c, dict):
                        continue
                    ce = set(c) - _CONDITION_CONSUMED_KEYS
                    if ce:
                        issues.append(Issue(
                            "ERROR", loc,
                            f"rule {rid!r}: condition carries ignored key(s) "
                            f"{sorted(ce)} — e.g. 'operator' has NO semantics "
                            f"(matching is always membership-in-values). Use "
                            f"the canonical short shape "
                            f"{{construct: X, values: [...]}}.",
                        ))

    for atype, block in cfg.items():
        if not isinstance(block, dict):
            continue
        if str(atype) == "governance":
            # top-level governance.<profile>.<agent_type>.thinking_rules form
            for profile, types in block.items():
                if not isinstance(types, dict):
                    continue
                for at, sub in types.items():
                    if isinstance(sub, dict):
                        _lint_rules(sub.get("thinking_rules"),
                                    f"yaml: governance.{profile}.{at}.thinking_rules")
            continue
        _lint_rules(block.get("thinking_rules"), f"yaml: {atype}.thinking_rules")
        _lint_rules(block.get("coherence_rules"), f"yaml: {atype}.coherence_rules")

    return issues


# ---------------------------------------------------------------------------
# Placeholder extraction
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][\w]*)\}")
_DOUBLE_BRACE_RE = re.compile(r"\{\{[^{}]+\}\}")


def extract_placeholders(template: str) -> Set[str]:
    """Return the set of single-brace ``{placeholder}`` names in the template.

    Skips escaped double braces ``{{...}}`` (literal braces in inline JSON).
    """
    # Mask double-brace blocks first so they don't pollute extraction.
    masked = _DOUBLE_BRACE_RE.sub("", template)
    return set(_PLACEHOLDER_RE.findall(masked))


def collect_template_vars(value: Any) -> Set[str]:
    """Return YAML-declared lifecycle/context template variable names.

    Domains can declare ``template_vars`` as either a list of names or a
    mapping of name -> description/default. The validator treats those names as
    intentionally supplied by lifecycle hooks, context providers, or agent
    state rather than response_format fields.
    """
    if isinstance(value, list):
        return {v for v in value if isinstance(v, str)}
    if isinstance(value, dict):
        return {k for k in value if isinstance(k, str)}
    return set()


# ---------------------------------------------------------------------------
# Inline JSON key extraction (best-effort)
# ---------------------------------------------------------------------------

def extract_inline_json_keys(template: str) -> Set[str]:
    """Pull TOP-LEVEL JSON-object keys from inline JSON examples in the prompt.

    These are the keys an LLM is shown as the response shape; they MUST
    match ``response_format.fields[].key`` from the YAML or the parser will
    reject the response.

    Python ``str.format`` requires literal braces escaped as ``{{`` / ``}}``,
    so the prompt's JSON example is double-braced. We:
        1. Remove single-brace ``{placeholder}`` substitutions so they don't
           interfere with brace-depth tracking.
        2. Convert ``{{`` / ``}}`` → ``{`` / ``}`` (what the LLM actually sees
           after format substitution).
        3. Walk the result tracking JSON object depth, collecting only keys
           at depth 1 (= the outer response object), skipping nested
           ``{"label": ..., "reason": ...}`` sub-objects whose keys are
           intentionally not declared in YAML.
    """
    # 1. Strip {placeholder} substitutions
    masked = _PLACEHOLDER_RE.sub("", template)
    # 2. Render literal-brace escapes
    literal = masked.replace("{{", "{").replace("}}", "}")
    keys: Set[str] = set()
    depth = 0
    i = 0
    n = len(literal)
    while i < n:
        ch = literal[i]
        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            i += 1
            continue
        if ch == '"' and depth == 1:
            end = literal.find('"', i + 1)
            if end < 0:
                break
            key_candidate = literal[i + 1:end]
            # Look ahead for ":" (with optional whitespace) — this
            # distinguishes a JSON key from a quoted value.
            j = end + 1
            while j < n and literal[j] in " \t\n":
                j += 1
            if j < n and literal[j] == ":" and re.fullmatch(
                r"[a-zA-Z_]\w*", key_candidate
            ):
                keys.add(key_candidate)
            i = end + 1
            continue
        i += 1
    return keys


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> Dict[str, Any]:
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_prompt_path(yaml_path: Path, template_ref: str) -> Path:
    """Resolve a prompt_template_file reference.

    Two conventions coexist in the codebase:
      * vaccination_demo / new domains: path relative to YAML directory,
        e.g. ``prompts/individual.txt`` in
        ``examples/vaccination_demo/config/agent_types.yaml``.
      * irrigation / older flood: path relative to the EXAMPLE root, e.g.
        ``config/prompts/irrigation_farmer.txt`` in
        ``examples/irrigation_abm/config/agent_types.yaml`` (resolves to
        ``examples/irrigation_abm/config/prompts/...`` after walking up).

    We try yaml_dir first, then walk up the parent directory tree (max 4
    levels) looking for a match. Returns the first existing match, or the
    yaml_dir candidate if no match (so the caller can report the expected
    location).
    """
    template_path = Path(template_ref)
    if template_path.is_absolute():
        return template_path

    primary = (yaml_path.parent / template_ref).resolve()
    if primary.exists():
        return primary

    current = yaml_path.parent
    for _ in range(4):
        current = current.parent
        candidate = (current / template_ref).resolve()
        if candidate.exists():
            return candidate

    return primary


# ---------------------------------------------------------------------------
# Skill->rule coverage (Phase 6G flaw 5 — Requisite Variety)
# ---------------------------------------------------------------------------

COVERAGE_THRESHOLD = 0.80


def check_skill_rule_coverage(
    cfg: Dict[str, Any], agent_type: str
) -> List[Issue]:
    """Compute per-profile skill->rule coverage; warn on requisite-variety gaps.

    Closes harness-engineering flaw 5 (audit 2026-05-14): a DomainPack with
    N skills but rules constraining only M < N skills lets agents converge
    on the unconstrained subset while governance silently looks effective
    on the constrained subset. The check warns when an actively-deployed
    profile constrains fewer than ``COVERAGE_THRESHOLD`` (80%) of available
    skill ids via ``thinking_rules`` + ``identity_rules`` ``blocked_skills``
    lists. Profiles with zero rules (the disabled / no-governance baseline
    used as an ablation control) are intentionally skipped.

    Also flags ghost-skill references: ``blocked_skills`` entries pointing
    at skill ids absent from the actions list (typo / stale rule that will
    never fire at runtime).
    """
    issues: List[Issue] = []
    block = cfg.get(agent_type)
    if not isinstance(block, dict):
        return issues

    # Mirror the actions lookup in validate_agent_type so both top-level and
    # parsing.actions conventions are supported.
    actions = block.get("actions")
    if not actions:
        parsing_block = block.get("parsing", {})
        if isinstance(parsing_block, dict):
            actions = parsing_block.get("actions")
    if not isinstance(actions, list):
        return issues  # malformed actions already errored upstream

    skill_ids: Set[str] = set()
    for a in actions:
        if isinstance(a, dict) and isinstance(a.get("id"), str):
            skill_ids.add(a["id"])
    if not skill_ids:
        return issues

    governance = block.get("governance", {})
    if not isinstance(governance, dict):
        return issues

    for profile_name, profile in governance.items():
        if not isinstance(profile, dict):
            continue
        thinking = profile.get("thinking_rules") or []
        identity = profile.get("identity_rules") or []
        all_rules = (
            list(thinking) if isinstance(thinking, list) else []
        ) + (
            list(identity) if isinstance(identity, list) else []
        )
        if not all_rules:
            # Intentional disabled / baseline profile — skip coverage check
            continue

        constrained: Set[str] = set()
        for rule in all_rules:
            if not isinstance(rule, dict):
                continue
            blocked = rule.get("blocked_skills") or []
            if isinstance(blocked, list):
                for s in blocked:
                    if isinstance(s, str):
                        constrained.add(s)

        # Ghost-skill check: blocked_skills referencing ids not in actions
        ghost = sorted(constrained - skill_ids)
        if ghost:
            issues.append(Issue(
                "WARN",
                f"yaml: {agent_type}.governance.{profile_name}",
                f"rules reference skill id(s) not in actions list: {ghost}. "
                "Possible typo or stale rule — these blocks will never fire "
                "at runtime.",
            ))

        documented_unconstrained = profile.get("documented_unconstrained_skills") or []
        if not isinstance(documented_unconstrained, list):
            documented_unconstrained = []
        documented: Set[str] = {
            s for s in documented_unconstrained if isinstance(s, str)
        }
        documented_ghost = sorted(documented - skill_ids)
        if documented_ghost:
            issues.append(Issue(
                "WARN",
                f"yaml: {agent_type}.governance.{profile_name}",
                f"documented_unconstrained_skills reference skill id(s) "
                f"not in actions list: {documented_ghost}. Possible typo "
                "or stale documentation.",
            ))

        # Coverage check — skill_ids guaranteed non-empty by earlier guard
        enforceable_skill_ids = skill_ids - documented
        if not enforceable_skill_ids:
            continue
        covered = constrained & enforceable_skill_ids
        coverage = len(covered) / len(enforceable_skill_ids)
        if coverage < COVERAGE_THRESHOLD:
            uncovered = sorted(enforceable_skill_ids - constrained)
            issues.append(Issue(
                "WARN",
                f"yaml: {agent_type}.governance.{profile_name}",
                f"skill->rule coverage {coverage * 100:.0f}% (< "
                f"{int(COVERAGE_THRESHOLD * 100)}% requisite-variety "
                f"threshold); {len(uncovered)} skill(s) unconstrained by "
                f"any thinking_rule or identity_rule: {uncovered}. Agents "
                "may converge on the unconstrained subset while governance "
                "looks effective on the constrained subset. Add rules "
                "covering these skills or document the deliberate omission. "
                "(harness-engineering flaw 5 — Requisite Variety)",
            ))

    return issues


# ---------------------------------------------------------------------------
# Per-agent-type validation
# ---------------------------------------------------------------------------

def validate_agent_type(
    cfg: Dict[str, Any],
    agent_type: str,
    yaml_path: Path,
    domain_extensions: Optional[Set[str]] = None,
) -> List[Issue]:
    """Validate one agent type's prompt + YAML cross-references.

    Args:
        cfg: parsed YAML dict.
        agent_type: which top-level key to validate.
        yaml_path: path of the YAML (for error-message locations).
        domain_extensions: extra placeholder names accepted as broker-
            filled (in addition to ``BROKER_FILLED_PLACEHOLDERS``).
            Typically supplied by ``_resolve_domain_extensions`` from
            the YAML's ``global_config.governance.domain`` field +
            the registered DomainPack's
            ``prompt_placeholder_extensions()`` hook. Phase 6R-B-3.
    """
    if domain_extensions is None:
        domain_extensions = set()
    issues: List[Issue] = []
    block = cfg.get(agent_type)
    if not isinstance(block, dict):
        issues.append(Issue(
            "ERROR", f"yaml: {agent_type}",
            f"agent_type '{agent_type}' not found at YAML top level",
        ))
        return issues

    # ---- ACTIONS block (Finding 5 root cause A) --------------------------
    # Two valid locations exist in the wild:
    #   * top-of-block: vaccination_demo, irrigation_abm — block["actions"]
    #   * nested under parsing: multi_agent flood — block["parsing"]["actions"]
    actions = block.get("actions")
    actions_location = "actions"
    if not actions:
        parsing_block = block.get("parsing", {})
        if isinstance(parsing_block, dict):
            actions = parsing_block.get("actions")
            if actions:
                actions_location = "parsing.actions"
    if not actions:
        issues.append(Issue(
            "ERROR", f"yaml: {agent_type}.actions",
            "missing 'actions:' block — parser.get_valid_actions() will "
            "return [] and every LLM response will be rejected. Declare "
            "each skill with id + aliases. Allowed locations: "
            "agent_type.actions OR agent_type.parsing.actions.",
        ))
    elif not isinstance(actions, list):
        issues.append(Issue(
            "ERROR", f"yaml: {agent_type}.{actions_location}",
            f"actions must be a list, got {type(actions).__name__}",
        ))
    else:
        for i, a in enumerate(actions):
            if not isinstance(a, dict) or "id" not in a:
                issues.append(Issue(
                    "ERROR", f"yaml: {agent_type}.{actions_location}[{i}]",
                    "each action entry needs an 'id:' field",
                ))

    # ---- response_format -------------------------------------------------
    # Prefer agent-block-level response_format (overrides shared); fall back
    # to shared.response_format (vaccination_demo / irrigation pattern).
    shared = cfg.get("shared", {})
    response_format = block.get("response_format") or shared.get("response_format", {})
    fields = response_format.get("fields", []) if isinstance(response_format, dict) else []
    field_keys: Set[str] = set()
    construct_to_key: Dict[str, str] = {}
    for f in fields:
        if not isinstance(f, dict):
            continue
        key = f.get("key")
        if key:
            field_keys.add(key)
        construct = f.get("construct")
        if construct and key:
            construct_to_key[construct] = key

    if not fields:
        issues.append(Issue(
            "WARN", "yaml: shared.response_format.fields",
            "no response_format.fields declared — runtime will skip "
            "auto-injecting {response_format} into prompts",
        ))

    # ---- parsing.constructs vs response_format.fields[].construct ---------
    parsing = block.get("parsing", {})
    parsing_constructs = parsing.get("constructs", {}) if isinstance(parsing, dict) else {}
    missing_constructs = [
        c for c in construct_to_key if c not in parsing_constructs
    ]
    if missing_constructs:
        issues.append(Issue(
            "ERROR", f"yaml: {agent_type}.parsing.constructs",
            "response_format.fields declare construct labels "
            f"{missing_constructs} but parsing.constructs has no matching "
            "entries — the parser cannot extract appraisal labels and "
            "every response will fail required-fields check",
        ))

    # ---- prompt template -------------------------------------------------
    # Two equivalent forms: external file (prompt_template_file) or inline
    # string (prompt_template, used by older flood institutional agents).
    template_ref = block.get("prompt_template_file")
    inline_template = block.get("prompt_template")
    template: Optional[str] = None
    template_location = ""

    if template_ref:
        prompt_path = resolve_prompt_path(yaml_path, template_ref)
        if not prompt_path.exists():
            issues.append(Issue(
                "ERROR", str(prompt_path),
                "prompt_template_file does not exist (tried yaml_dir + "
                "up to 4 parent levels)",
            ))
            return issues
        template = prompt_path.read_text(encoding="utf-8")
        template_location = str(prompt_path)
    elif inline_template:
        template = inline_template
        template_location = f"yaml: {agent_type}.prompt_template (inline)"
    else:
        issues.append(Issue(
            "WARN", f"yaml: {agent_type}",
            "no 'prompt_template_file' or inline 'prompt_template' set — "
            "agent will use the broker default template",
        ))
        return issues

    # ---- placeholder coverage -------------------------------------------
    placeholders = extract_placeholders(template)
    template_var_keys = (
        collect_template_vars(shared.get("template_vars"))
        | collect_template_vars(block.get("template_vars"))
    )
    # Phase 6R-B-3 (audit cluster E #16): union the base broker-filled
    # set with the DomainPack's domain-specific extensions (e.g.
    # FloodDomainPack.prompt_placeholder_extensions() supplies
    # ``insurance_cost_text`` etc.). Pre-fix these names lived in
    # BROKER_FILLED_PLACEHOLDERS directly, leaking flood-domain vocab
    # into generic CLI code.
    known_keys = (
        BROKER_FILLED_PLACEHOLDERS
        | domain_extensions
        | field_keys
        | template_var_keys
    )
    unknown = sorted(p for p in placeholders if p not in known_keys)
    if unknown:
        issues.append(Issue(
            "WARN", template_location,
            f"placeholders not in broker-filled or YAML-declared set: "
            f"{unknown}. At runtime SafeFormatter will silently render "
            f"these as '[N/A]'. Either add to response_format.fields or "
            f"ensure a domain lifecycle hook fills them via "
            f"template_vars.",
        ))

    # ---- inline JSON key sync (Finding 4) --------------------------------
    # Keys the parser looks for via parsing.decision_keywords are also
    # legitimate top-level JSON keys, even though they aren't in
    # response_format.fields (the decision is matched by parser pipeline,
    # not by required-fields check).
    decision_keywords = set(parsing.get("decision_keywords", []) or [])
    inline_keys = extract_inline_json_keys(template)
    if inline_keys and field_keys:
        only_in_prompt = inline_keys - field_keys - decision_keywords
        if only_in_prompt:
            issues.append(Issue(
                "ERROR", template_location,
                f"inline JSON example uses keys {sorted(only_in_prompt)} "
                f"not in YAML response_format.fields[].key "
                f"({sorted(field_keys)}) and not in "
                f"parsing.decision_keywords ({sorted(decision_keywords)}). "
                f"LLM will produce these keys but the parser will reject "
                f"them as 'missing required fields'.",
            ))

    # ---- Phase 6G flaw 5: skill->rule coverage (Requisite Variety) -------
    issues.extend(check_skill_rule_coverage(cfg, agent_type))

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Static validator: agent prompt template vs YAML config.\n\n"
            "Phase 6R-B-3 (audit cluster E #16): the CLI's placeholder "
            "allowlist is the union of BROKER_FILLED_PLACEHOLDERS and "
            "the registered DomainPack's prompt_placeholder_extensions() "
            "hook. To validate a flood YAML (which references "
            "{insurance_cost_text} / {mg_barrier_text} / {renewal_fatigue_text}) "
            "without spurious WARNs, ensure FloodDomainPack is registered "
            "BEFORE invoking this CLI — e.g. run from a Python entry "
            "point that imports examples.governed_flood, or use "
            "`python -m examples.governed_flood validate_prompt ...`."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "yaml_file",
        type=Path,
        help="Path to agent_types.yaml",
    )
    parser.add_argument(
        "--agent-type",
        action="append",
        help=(
            "Agent type key to validate. Repeat for multiple. Default: "
            "every top-level key in the YAML that has 'agent_type' set."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARN as ERROR (exit 1 on any issue)",
    )
    args = parser.parse_args(argv)

    if not args.yaml_file.exists():
        print(f"ERROR: YAML file not found: {args.yaml_file}", file=sys.stderr)
        return 1

    cfg = load_yaml(args.yaml_file)

    if args.agent_type:
        agent_types: List[str] = args.agent_type
    else:
        # Auto-discover: any top-level dict that looks like an agent-type
        # config block. Two conventions are seen in the wild:
        #   - vaccination_demo style: explicit `agent_type:` key inside
        #   - irrigation / flood style: the dict's KEY name is the agent
        #     type and the block has prompt_template_file / parsing / etc.
        AGENT_KEY_INDICATORS = (
            "agent_type",
            "prompt_template_file",
            "psychological_framework",
            "parsing",
        )
        RESERVED = {"global_config", "shared", "personas", "skill_magnitude",
                    "metadata",
                    # Top-level governance block (governance.strict.<agent_type>
                    # .thinking_rules) — never an agent type itself. Excluded so
                    # a future governance dict that happens to nest an
                    # AGENT_KEY_INDICATOR (e.g. parsing:) is not misclassified
                    # as an agent type (6T-F.3 was the first standalone config
                    # to carry a scanned top-level governance block).
                    "governance"}
        agent_types = [
            k for k, v in cfg.items()
            if isinstance(v, dict)
            and k not in RESERVED
            and any(ind in v for ind in AGENT_KEY_INDICATORS)
        ]
        if not agent_types:
            print(
                "ERROR: no agent_type blocks found in YAML. Each agent "
                "type block must contain at least one of: "
                f"{AGENT_KEY_INDICATORS}",
                file=sys.stderr,
            )
            return 1

    all_issues: List[Issue] = []
    # 2026-06-09: config-time unknown-key net (canonical registry above).
    all_issues.extend(check_global_config_keys(cfg))
    # 2026-06-10 (G4): silently-dead rule-shape lint (the 6N-E class).
    all_issues.extend(check_rule_shapes(cfg))
    # Phase 6R-B-3: resolve domain-specific placeholder extensions once
    # per CLI invocation. The hook is keyed on
    # ``global_config.governance.domain``.
    domain_extensions = _resolve_domain_extensions(cfg)
    for at in agent_types:
        all_issues.extend(
            validate_agent_type(
                cfg, at, args.yaml_file,
                domain_extensions=domain_extensions,
            )
        )

    if not all_issues:
        print(f"OK: {args.yaml_file} — {len(agent_types)} agent type(s) clean")
        return 0

    n_err = sum(1 for i in all_issues if i.severity == "ERROR")
    n_warn = sum(1 for i in all_issues if i.severity == "WARN")
    for issue in all_issues:
        print(issue.format())
    print(f"\n{n_err} error(s), {n_warn} warning(s)")

    if n_err > 0:
        return 1
    if args.strict and n_warn > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
