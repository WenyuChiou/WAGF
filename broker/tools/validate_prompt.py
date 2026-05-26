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
    # Phase 6Q-K-3 (2026-05-26): asymmetric placeholder coverage. The
    # 3 entries below are water/flood-domain provider names — they
    # suppress WARN for flood prompts that reference them, but a
    # non-water domain that defines its own placeholder vocabulary
    # (e.g. ``{congestion_advisory_text}`` for traffic) would get
    # spurious WARNs because validate_prompt has no per-domain
    # extension mechanism. Documented as Layer 3 audit finding #16
    # (Phase 6P-E follow-up). Proper fix: add a
    # ``DomainPack.prompt_placeholder_extensions() -> Set[str]`` hook
    # and union with this base set at validate-time — deferred to
    # Phase 6R alongside the broader sub-protocol split (Layer 4
    # audit). For now the entries stay so flood prompt validation
    # keeps working byte-identically; non-water domains can avoid
    # the spurious WARN by naming their placeholders to NOT collide
    # with these reserved water-domain names (which they already
    # do, since traffic / vaccination don't reference insurance /
    # mg / renewal vocabulary).
    "insurance_cost_text",   # water-domain (FloodDomainPack)
    "mg_barrier_text",       # water-domain (FloodDomainPack)
    "renewal_fatigue_text",  # water-domain (FloodDomainPack)
}


@dataclass
class Issue:
    severity: str  # "ERROR" or "WARN"
    location: str  # short location hint (file, "yaml: <agent_type>", etc.)
    message: str

    def format(self) -> str:
        return f"{self.severity:5} {self.location}: {self.message}"


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
) -> List[Issue]:
    """Validate one agent type's prompt + YAML cross-references."""
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
    known_keys = BROKER_FILLED_PLACEHOLDERS | field_keys | template_var_keys
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
        description="Static validator: agent prompt template vs YAML config",
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
                    "metadata"}
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
    for at in agent_types:
        all_issues.extend(validate_agent_type(cfg, at, args.yaml_file))

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
