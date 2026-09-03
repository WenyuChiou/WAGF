"""
Unified Adapter — single adapter supporting all models and agent types.

Extracted from model_adapter.py (Phase 2.2 split).
Skills, decision keywords, and default settings are loaded from agent_types.yaml.
Model-specific quirks (like DeepSeek's <think> tags) are handled via preprocessor.
"""
from typing import Dict, Any, Optional, List, Callable
import re
import json
import threading

from ...interfaces.skill_types import SkillProposal
from ...utils.logging import logger
from ..preprocessors import GenericRegexPreprocessor, SmartRepairPreprocessor, get_preprocessor
from ..adapters.deepseek import deepseek_preprocessor
from ..normalization import _THINK_TAG_RE, FRAMEWORK_NORMALIZATION_MAP, normalize_construct_value
from ..parsing_audits import is_list_item, parse_numeric_value, audit_demographic_grounding
from ..agent_config import load_agent_config
from .base import ModelAdapter


#: PR-4 (D7). One warning per REASON per process, keyed on the reason token
#: alone. The earlier draft keyed on ``(f"the getter raised {exc}", type(config))``,
#: which defeats the purpose: a getter whose message carries anything variable
#: (an agent id, a path) mints a fresh key every call, so the set grows without
#: bound AND the "once" never holds. ``SkillBrokerEngine.__init__`` clears this,
#: so a second engine in the same process is still told once — a warning
#: silenced by an earlier run is a warning nobody sees.
_PARSING_FLAG_WARNED: set = set()


def _warn_once_parsing(reason: str, detail: str, config) -> None:
    if reason in _PARSING_FLAG_WARNED:
        return
    _PARSING_FLAG_WARNED.add(reason)
    logger.warning(
        "[Parsing] global_config.parsing.strict_layers is being read OFF: %s "
        "(config type %s). The parser will keep accepting a stray digit as the "
        "decision and keep labelling a parser-substituted default as a reasoned "
        "one. If you meant to enable the flag, this run did not.",
        detail, type(config).__name__,
    )


def resolve_strict_layers_flag(config) -> bool:
    """True iff this run opted into ``global_config.parsing.strict_layers``.

    PR-4 (D5). Same fail-closed-with-one-warning discipline the audit flags use
    (``broker/core/_audit_helpers.py::_corrected_status_flag``), and for the
    same reason: every way of failing to read the flag resolves it OFF, which
    is right for byte identity and wrong for whoever set it in YAML, so each
    such path says so once. A config predating the flag has no getter and
    resolves OFF in silence (correct — nothing to warn about); a getter that
    raises or returns a non-bool resolves OFF and warns.

    Never raises. Test doubles and ``MagicMock`` configs reach this, and
    ``bool(MagicMock())`` is True — a bare truth test would silently switch the
    hardened layers on in every mock-config run.
    """
    getter = getattr(config, "get_parsing_strict_layers", None)
    if not callable(getter):
        return False
    try:
        value = getter()
    except (AttributeError, TypeError, ValueError) as exc:
        # Narrow on purpose: a KeyboardInterrupt / SystemExit / genuine bug in
        # the config layer must propagate, not be recorded as "OFF".
        _warn_once_parsing(
            "getter_raised", f"the getter raised {type(exc).__name__}: {exc}", config
        )
        return False
    if isinstance(value, bool):
        return value
    _warn_once_parsing(
        "getter_non_bool",
        f"the getter returned {type(value).__name__} rather than a bool",
        config,
    )
    return False


def _sanitize_warning(text: str) -> str:
    """PR-4 (D6). ``trace_to_csv_row`` joins ``parsing_warnings`` with ``"|"``
    (``broker/components/analytics/audit.py``), so a literal pipe inside a
    warning silently splits one warning into two when an analyst splits the
    field back apart. Applied ONLY to the warnings this PR adds — rewriting the
    pre-existing ones would change flag-OFF bytes.
    """
    return text.replace("|", "/")


#: PR-4 (D2 i). The decision-line digit anchor, flag-ON. Module-level so the
#: tests and the docs point at ONE definition — a regex retyped as a literal in
#: a test asserts nothing about the code, and a regex retyped in a doc goes
#: stale the first time the code moves.
#:
#: Shape: optional wrapper characters, an optional separator or copula, more
#: optional wrappers, an optional short LEAD-IN, then the digit — and the digit
#: must end on a word boundary. The wrapper class is not decoration. This layer
#: sees PREPROCESSED text, and the decision line reaches it in shapes like
#: ``: "3",`` (SmartRepairPreprocessor's rewrite of ``Decision: 3``), ``": 3``
#: (a quote BEFORE the colon, from ``"decision": 3``), ``': 3,`` (single-quoted
#: JSON, the most common malformed-JSON shape from small models — and precisely
#: the case where the JSON layer fails and this route is what catches the
#: contract), ``: [3]``, ``: (3)``, ``: `3` ``, ``**3**`` and ``is 3``.
#:
#: PR-4 reviewer follow-up. The LEAD-IN is a closed whitelist —
#: ``option|choice|number|#|->|>+|is|my choice is`` — so ``Decision: Option 3``,
#: ``Decision: #3``, ``Decision: number 3``, ``Decision: -> 3``,
#: ``Decision: >>> 3`` and ``Decision: my choice is 3`` all resolve. What it
#: must still reject is PROSE between the keyword and the digit:
#: ``: i will revisit this in 2 or three years`` and ``: i will not relocate
#: this year (option 3 is too costly for the 2 of us)`` both fail — the second
#: one BECAUSE the anchor is not a search: ``option 3`` sits mid-string, not at
#: the position immediately after the separator, so ``.match`` never reaches it.
DECISION_VALUE_DIGIT_RE = re.compile(
    r"^[\s\"'`\[(*_]*(?:is\b|was\b|[:=-])?[\s\"'`\[(*_]*"
    r"(?:(?:option|choice|number)\b|#|->|>+|is\b|my\s+choice\s+is\b)?"
    r"[\s\"'`\[(*_]*(\d)\b",
    re.IGNORECASE,
)


class UnifiedAdapter(ModelAdapter):
    """
    Unified adapter supporting all models AND all agent types.

    Skills, decision keywords, and default settings are loaded from agent_types.yaml.
    Model-specific quirks (like DeepSeek's <think> tags) are handled via preprocessor.
    """

    #: PR-4 (D6). Per-THREAD storage for the warnings a ``return None`` parse
    #: would otherwise discard. NOT a plain instance attribute: with
    #: ``--workers > 1``, ``ExperimentRunner._run_agents_parallel`` submits one
    #: shared engine — and therefore one shared adapter — to a
    #: ThreadPoolExecutor, and an instance attribute there is a data race with
    #: two demonstrated failure modes. Agent A stashes, agent B (already past
    #: its own drain) reads A's stash and writes it onto B's audit row: a
    #: fabricated per-row fact inside the one feature whose entire purpose is
    #: per-row provenance. The mirror ordering is worse in a quieter way — B's
    #: drain clears A's stash before A can read it, so A's suppression reason
    #: reaches neither A's proposal nor A's ABORTED sentinel and the row simply
    #: says nothing.
    #:
    #: Thread-local removes both without a lock, because one step's parse and
    #: that step's drain always happen on one thread. Class-level rather than
    #: built in ``__init__`` so adapters created via ``__new__`` (the test
    #: doubles in ``test_corrected_status_columns_pr3.py``) work too.
    _parse_warning_stash = threading.local()

    @property
    def last_parse_warnings(self) -> List[str]:
        """Warnings stashed by the most recent ``return None`` ON THIS THREAD.

        Empty unless ``parsing.strict_layers`` is on — flag-OFF nothing ever
        writes here, so every consumer's truth test is False and no flag-OFF
        byte changes.
        """
        return list(getattr(UnifiedAdapter._parse_warning_stash, "warnings", None) or [])

    @last_parse_warnings.setter
    def last_parse_warnings(self, value) -> None:
        UnifiedAdapter._parse_warning_stash.warnings = list(value or [])

    def __init__(
        self,
        agent_type: str = "default",
        preprocessor: Optional[Callable[[str], str]] = None,
        valid_skills: Optional[set] = None,
        config_path: str = None
    ):
        """
        Initialize unified adapter.

        Args:
            agent_type: Type of agent (e.g., "trader", "manager", "consumer")
            preprocessor: Optional function to preprocess raw output
            valid_skills: Optional set of valid skill names (overrides agent_type config)
            config_path: Optional path to agent_types.yaml
        """
        self.agent_type = agent_type
        self.agent_config = load_agent_config(config_path)

        # Load parsing config and actual actions/aliases
        parsing_cfg = self.agent_config.get_parsing_config(agent_type)
        if not parsing_cfg:
            # Smart defaults if 'parsing' block is missing from YAML
            parsing_cfg = {
                "decision_keywords": ["final decision:", "decision:", "decide:"],
                "constructs": {}
            }

        actions = self.agent_config.get_valid_actions(agent_type)

        self.config = parsing_cfg

        # Determine preprocessor (Order: Explicit argument > YAML Config > Identity)
        # Phase 12/28: Ensure explicit or config preprocessors are not overwritten
        if preprocessor:
            self._preprocessor = preprocessor
        else:
            p_cfg = parsing_cfg.get("preprocessor", {})
            if p_cfg:
                self._preprocessor = get_preprocessor(p_cfg)
            else:
                self._preprocessor = lambda x: x

        # Load valid skills for the agent type to build alias map
        self.valid_skills = self.agent_config.get_valid_actions(agent_type)
        # Build alias map from config (e.g., "ACT1" -> "action_alpha", "ACT2" -> "action_beta")
        self.alias_map = self.agent_config.get_action_alias_map(agent_type)

    def _get_preprocessor_for_type(self, agent_type: str) -> Callable[[str], str]:
        """Get preprocessor for a specific agent type."""
        try:
            is_identity = (self._preprocessor.__name__ == "<lambda>" and self._preprocessor("") == "")
        except (AttributeError, TypeError):
            is_identity = False

        if not is_identity:
            return self._preprocessor

        p_cfg = self.agent_config.get_parsing_config(agent_type).get("preprocessor", {})
        if p_cfg:
            return get_preprocessor(p_cfg)
        return self._preprocessor

    def _get_authoritative_alias_map(self, agent_type: str, parsing_cfg: Dict[str, Any]) -> Dict[str, str]:
        """
        Build an exact alias map from YAML-declared actions.

        Some alias agent types (for example, ``government`` and ``insurance`` in the
        flood config) declare themselves as aliases for a base type in their
        description while omitting a subset of the base type's action aliases.
        For parser exact-match resolution, the YAML declaration is authoritative, so
        we merge the local actions with any aliased base agent actions before
        falling back to fuzzy matching.
        """
        authoritative_aliases: Dict[str, str] = {}
        canonical_aliases: Dict[str, str] = {}

        def add_actions(actions: List[Dict[str, Any]]) -> None:
            for action in actions or []:
                canonical = action.get("id")
                if not canonical:
                    continue
                for raw_alias in action.get("aliases", []):
                    alias = str(raw_alias).strip().lower()
                    if not alias:
                        continue
                    authoritative_aliases[alias] = canonical
                canonical_key = str(canonical).strip().lower()
                if canonical_key:
                    canonical_aliases.setdefault(canonical_key, canonical)

        add_actions(parsing_cfg.get("actions", []))

        agent_cfg = self.agent_config.get(agent_type) or {}
        description = str(agent_cfg.get("description", ""))
        alias_match = re.search(r"alias for ([a-zA-Z0-9_]+)", description, re.IGNORECASE)
        if alias_match:
            base_agent_type = alias_match.group(1)
            base_parsing_cfg = self.agent_config.get_parsing_config(base_agent_type) or {}
            add_actions(base_parsing_cfg.get("actions", []))

        return {**canonical_aliases, **authoritative_aliases}

    def _resolve_exact_text_decision(
        self,
        decision_val: str,
        agent_type: str,
        parsing_cfg: Dict[str, Any],
        alias_map: Dict[str, str],
    ) -> Optional[str]:
        """Resolve an exact text decision before attempting substring-based matching."""
        if not isinstance(decision_val, str):
            return None

        decision_clean = decision_val.strip().lower()
        if not decision_clean:
            return None

        authoritative_alias_map = self._get_authoritative_alias_map(agent_type, parsing_cfg)
        lookup_keys = [
            decision_clean,
            decision_clean.replace("-", "_").replace(" ", "_"),
            decision_clean.replace("-", " ").replace("_", " "),
        ]

        for key in lookup_keys:
            if key in authoritative_alias_map:
                return authoritative_alias_map[key]

        for key in lookup_keys:
            if key in alias_map:
                return alias_map[key]

        return None

    def parse_output(self, raw_output: str, context: Dict[str, Any]) -> Optional[SkillProposal]:
        """
        Parse LLM output into SkillProposal.
        Supports: Enclosure blocks (Phase 15), JSON, and Structured Text.
        """
        agent_id = context.get("agent_id", "unknown")
        agent_type = context.get("agent_type", self.agent_type)
        valid_skills = self.agent_config.get_valid_actions(agent_type)
        preprocessor = self._get_preprocessor_for_type(agent_type)
        parsing_cfg = self.agent_config.get_parsing_config(agent_type) or {}
        skill_map = self.agent_config.get_skill_map(agent_type, context)
        # Dynamic alias map per agent_type (not self.alias_map which may be stale)
        alias_map = self.agent_config.get_action_alias_map(agent_type)
        # PR-4: global_config.parsing.strict_layers (default OFF). Read once
        # per parse call, through the coercing resolver (never the raw getter:
        # a MagicMock config would otherwise read truthy), and threaded through
        # every gated branch below AND into _parse_keywords, so the parser is
        # the single place this flag is decided. Flag-OFF is byte-identical to
        # HEAD everywhere in this method.
        strict_layers = resolve_strict_layers_flag(self.agent_config)

        # 0. Initialize results
        skill_name = None
        reasoning = {}
        parsing_warnings = []
        # Phase 0.3: Retrieve agent-specific normalization map
        custom_mapping = parsing_cfg.get("normalization", {})
        proximity_window = parsing_cfg.get("proximity_window", 35)

        # Track which parsing method succeeded (enclosure/json/keyword/digit/default)
        parse_layer = ""
        parse_confidence = 0.0
        construct_completeness = 0.0
        parse_metadata = {
            "parse_layer": "",
            "parse_confidence": 0.0,
            "construct_completeness": 0.0,
        }

        # Phase 15: Early return for empty output
        if not raw_output:
            return None

        # Strip thinking tokens (<think>...</think>) based on global config
        from broker.utils.llm_utils import LLM_CONFIG
        if LLM_CONFIG.should_strip_thinking():
            raw_output = _THINK_TAG_RE.sub('', raw_output).strip()
            if not raw_output:
                return None  # Only thinking tokens, no actual response

        # 1. Phase 15: Enclosure Extraction (Priority)
        # Dynamic Delimiters (from YAML config) - Phase 23
        try:
            from broker.components.response_format import ResponseFormatBuilder
            cfg = self.agent_config
            agent_cfg = cfg.get(agent_type)
            shared_cfg = {"response_format": cfg._config.get("shared", {}).get("response_format", {})}
            rfb = ResponseFormatBuilder(agent_cfg, shared_cfg)
            d_start, d_end = rfb.get_delimiters()
            # Use non-greedy match to handle multiple blocks if present
            dynamic_pattern = rf"{re.escape(d_start)}\s*(.*?)\s*{re.escape(d_end)}"
        except (ImportError, AttributeError, Exception):
            dynamic_pattern = None

        patterns = [
            dynamic_pattern,
            r"<<<DECISION_START>>>\s*(.*?)\s*<<<DECISION_END>>>",
            r"<decision>\s*(.*?)\s*</decision>",
            r"(?:decision|choice|selected_action)[:\s]*({.*?})", # Find JSON-like block after keyword
            r"({.*})", # Final fallback: Find any JSON-like block
        ]

        target_content = raw_output
        is_enclosed = False
        for pattern in [p for p in patterns if p]:
            match = re.search(pattern, raw_output, re.DOTALL | re.IGNORECASE)
            if match:
                target_content = match.group(1)
                parse_layer = "enclosure"
                is_enclosed = True
                break

        # 2. Preprocess target
        cleaned_target = preprocessor(target_content)

        # 3. ATTEMPT JSON PARSING
        _magnitude_pct = None  # Optional magnitude for Group D experiments
        # 6W-B2: full extracted numeric dict. Initialised here (not only inside the
        # JSON-success block at ~:335) so it is always defined at the constructor,
        # including the JSON-parse-failed path. Routed to SkillProposal.parameters
        # only when the agent_type opts in (get_multi_param_enabled), else stays {}.
        _extracted_numerics = {}
        found_json = False
        data_lowered = None  # Will be set if JSON parsing succeeds
        try:
            json_text = cleaned_target.strip()

            # 3a. Strip markdown code blocks if present (common in Gemma/Llama responses)
            if "```" in json_text:
                # Prioritize json block but fallback to any block
                json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', json_text, re.DOTALL)
                if json_block_match:
                    json_text = json_block_match.group(1)
                else:
                    # If it's just opening ```json or similar, strip markers
                    json_text = re.sub(r'```(?:json)?', '', json_text)
                    json_text = json_text.replace('```', '')

            if "{" in json_text:
                json_text = json_text[json_text.find("{"):json_text.rfind("}")+1]

            # Preprocessor Failsafe: Handle double-braces mimicry from small models
            if json_text.startswith("{{") and json_text.endswith("}}"):
                json_text = json_text[1:-1]

            json_text = json_text.replace("{{", "{").replace("}}", "}")
            json_text = re.sub(r',\s*([\]}])', r'\1', json_text)

            data = json.loads(json_text)
            if isinstance(data, dict):
                found_json = True
                parse_layer = f"{parse_layer}+json" if is_enclosed else "json"
                # Robust case-insensitive key lookup
                data_lowered = {k.lower(): v for k, v in data.items()}

                # Extract decision (Generalized: Use keywords from config)
                decision_kws = parsing_cfg.get("decision_keywords", ["decision", "choice", "action"])
                decision_val = None
                for kw in decision_kws:
                    decision_val = data_lowered.get(kw.lower())
                    if decision_val is not None: break



                # Resolve decision
                if decision_val is not None:
                    # Case 0: Nested dict (some models output {"action": {"choice": 1}})


                    if isinstance(decision_val, dict):
                        decision_val = decision_val.get("choice") or decision_val.get("id") or decision_val.get("value")

                    # Case 0b: List/array (small models like gemma3:1b output [2, 3, 4])
                    # Take the first element as the primary decision
                    if isinstance(decision_val, list) and decision_val:
                        decision_val = decision_val[0]

                    if decision_val is not None:
                        # Case 1: Direct mapping (int or exact digit string)
                        if str(decision_val) in skill_map:
                            skill_name = skill_map[str(decision_val)]
                        # Case 2: String like "1. Buy Insurance" or "Option 1"
                        elif isinstance(decision_val, str):
                            digit_match = re.search(r'(\d+)', decision_val)
                            if digit_match and digit_match.group(1) in skill_map:
                                skill_name = skill_map[digit_match.group(1)]
                            else:
                                skill_name = self._resolve_exact_text_decision(
                                    decision_val,
                                    agent_type,
                                    parsing_cfg,
                                    alias_map,
                                )
                            if not skill_name:
                                # Search for skill names in string (Fuzzy match)
                                decision_norm = decision_val.lower().replace("_", " ").replace("-", " ")
                                for skill in valid_skills:
                                    skill_norm = skill.lower().replace("_", " ").replace("-", " ")
                                    if skill_norm in decision_norm:
                                        skill_name = skill
                                        break
                                # Also check alias map directly
                                # This handles "Buy Insurance" -> "buy_insurance" or "DN" -> "do_nothing"
                                for alias, canonical in skill_map.items():
                                    alias_norm = alias.lower().replace("_", " ").replace("-", " ")
                                    if alias_norm in decision_norm:
                                        skill_name = canonical
                                        break

                # Extract numeric fields (dynamic, config-driven)
                # For backward compatibility, we still expose _magnitude_pct as the primary numeric value
                numeric_fields = self.agent_config.get_numeric_fields(agent_type)
                _extracted_numerics = {}  # Will store all extracted numeric values

                if numeric_fields:
                    for nf in numeric_fields:
                        key = nf.get("key")
                        if not key:
                            continue

                        # Try to get from JSON with case-insensitive lookup
                        raw_val = data_lowered.get(key.lower())
                        if raw_val is None:
                            continue

                        # Parse the value
                        parsed_val = parse_numeric_value(raw_val, nf, parsing_warnings, self.config)
                        if parsed_val is not None:
                            _extracted_numerics[key] = parsed_val

                    # For backward compatibility: expose first numeric as _magnitude_pct
                    # Priority: magnitude_pct > magnitude > first defined numeric field
                    if "magnitude_pct" in _extracted_numerics:
                        _magnitude_pct = _extracted_numerics["magnitude_pct"]
                    elif "magnitude" in _extracted_numerics:
                        _magnitude_pct = _extracted_numerics["magnitude"]
                    elif _extracted_numerics:
                        _magnitude_pct = list(_extracted_numerics.values())[0]
                else:
                    # Legacy fallback: hardcoded magnitude/magnitude_pct lookup
                    magnitude_raw = data_lowered.get("magnitude") or data_lowered.get("magnitude_pct")
                    if magnitude_raw is not None:
                        try:
                            _magnitude_pct = float(magnitude_raw)
                        except (ValueError, TypeError):
                            if isinstance(magnitude_raw, str):
                                digit_match = re.search(r'(\d+)', magnitude_raw)
                                if digit_match:
                                    _magnitude_pct = float(digit_match.group(1))

                # RECOVERY: If JSON parsed but no decision found, look for "Naked Digit" after the JSON block
                # PR-4 (D1): the leading group is OPTIONAL, so this pattern is
                # not decision-scoped at all -- `(?:decision|choice|id|:)?\s*(\d)\b`
                # matches the bare "3" in "3 of my neighbours moved" exactly as
                # readily as the "3" in "Decision: 3". Under strict_layers the
                # digit is not taken: the decision stays unresolved and the row
                # falls through to the keyword / default layers, with one
                # warning naming the candidate that was suppressed so the
                # suppression is auditable rather than invisible.
                if not skill_name:
                    after_json = cleaned_target[cleaned_target.rfind("}")+1:].strip()
                    # Look for digits at start OR with some context (like "Decision: 4")
                    digit_match = re.search(r'(?:decision|choice|id|:)?\s*(\d)\b', after_json, re.IGNORECASE)
                    if digit_match and digit_match.group(1) in skill_map:
                        _cand = digit_match.group(1)
                        if strict_layers:
                            parsing_warnings.append(_sanitize_warning(
                                f"STRICT_LAYERS: suppressed candidate digit {_cand} -> "
                                f"{skill_map[_cand]} (json_plus_digit recovery)"
                            ))
                        else:
                            skill_name = skill_map[_cand]
                            parse_layer = "json_plus_digit"





                if skill_name:
                    # Reset warnings if JSON parsing succeeded (even with digit recovery)
                    parsing_warnings = [w for w in parsing_warnings if "STRICT_MODE" not in w]

                # Extract Reasoning & Constructs
                reasoning = {
                    "strategy": data.get("strategy", ""),
                    "confidence": data.get("confidence", 1.0)
                }
                # Get construct mapping from config for dynamic matching
                construct_mapping = parsing_cfg.get("constructs", {}) if parsing_cfg else {}

                # Synonym Mapping (Now purely config-driven)
                # If 'synonyms' is defined in YAML, use it. Otherwise, no synonym expansion.
                SYNONYM_MAP = parsing_cfg.get("synonyms", {})




                for k, v in data.items():
                    if k.lower() in ["decision", "choice", "action", "strategy", "confidence"]:
                        continue

                    # 1. Identify which constructs this JSON key 'k' might relate to
                    matched_names = []
                    k_normalized = k.lower().replace("_", " ").replace("-", " ")

                    for c_name, c_cfg in construct_mapping.items():
                        keywords = list(c_cfg.get("keywords", []))

                        # Add internal synonyms for standard constructs
                        # Check if any synonym base (e.g., 'tp', 'sp') is in the construct name
                        for base_name, synonyms in SYNONYM_MAP.items():
                            if base_name.lower() in c_name.lower():
                                keywords.extend(synonyms)

                        # Normalize keywords for matching
                        keywords_normalized = [kw.lower().replace("_", " ") for kw in keywords]

                        # Check if JSON key matches any keyword
                        if any(kw in k_normalized for kw in keywords_normalized):
                            matched_names.append(c_name)

                    # Also check if the key directly matches a construct name (case-insensitive)
                    for c_name in construct_mapping.keys():
                        c_name_norm = c_name.lower().replace("_", " ")
                        if c_name_norm in k_normalized or k_normalized in c_name_norm:
                            if c_name not in matched_names:
                                matched_names.append(c_name)


                    # 2. Extract values based on structure
                    if isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            sub_k_lower = sub_k.lower()
                            # Nested mapping: check if sub-key is a label or reason
                            if "label" in sub_k_lower:
                                for name in [n for n in matched_names if "_LABEL" in n]:
                                    reasoning[name] = normalize_construct_value(sub_v, custom_mapping=custom_mapping)
                            elif any(rk in sub_k_lower for rk in ["reason", "why", "explanation", "because"]):
                                for name in [n for n in matched_names if "_REASON" in n]:
                                    reasoning[name] = sub_v
                            else:
                                reasoning[f"{k}_{sub_k}"] = normalize_construct_value(sub_v, custom_mapping=custom_mapping)
                    elif isinstance(v, (str, int, float)):
                        # Flattened string or value: assign to matched constructs
                        if matched_names:
                            for name in matched_names:
                                # For labels, if it's a string, we might want to extract just the label part
                                if "_LABEL" in name and isinstance(v, str):
                                    # Robust extraction using regex from config if available
                                    regex = construct_mapping[name].get("regex")
                                    if regex:
                                        # 1. Try full regex match (prefix + label)
                                        match = re.search(regex, v, re.IGNORECASE)
                                        if match and match.groups():
                                            # Phase 6N-B (2026-05-23): the regex matches
                                            # case-insensitively via re.IGNORECASE but
                                            # match.group(1) preserves whatever case the
                                            # LLM emitted — a chatty model writes "m"
                                            # instead of "M" and the audit CSV ends up
                                            # with mixed case like ['M', 'm']. For
                                            # LABEL constructs the ordinal alphabet
                                            # (VL/L/M/H/VH) is canonical uppercase by
                                            # contract; upper-casing here closes the
                                            # silent-drift gap where downstream rule
                                            # conditions like in ['H','VH']
                                            # miss case variants.
                                            reasoning[name] = match.group(1).upper()
                                        else:
                                            # 2. Try to find any of the labels from the capture group alternatives
                                            # This handles cases where the key is already identified, but the value is a string containing the label
                                            # e.g. Regex: "(?:threat)[:\s]* (High|Low)" -> look for "High" or "Low" in v
                                            try:
                                                # Extract the alternatives from the first capture group if possible
                                                # Pattern usually looks like (A|B|C)
                                                inner_pattern = re.search(r'\(([^?].+?)\)', regex)
                                                if inner_pattern:
                                                    alternatives = [alt.strip() for alt in inner_pattern.group(1).split('|')]
                                                    # Sort by length descending to match "Very High" before "High"
                                                    alternatives.sort(key=len, reverse=True)

                                                    # First try direct match.
                                                    # Phase 6N-B reviewer W2: uppercase
                                                    # the assigned alt for LABEL
                                                    # constructs (this whole branch is
                                                    # already inside "_LABEL" in name).
                                                    # The current YAML patterns
                                                    # use canonical uppercase alternatives
                                                    # so .upper() is idempotent today,
                                                    # but a future regex with lowercase
                                                    # alternatives would otherwise drift
                                                    # apart from the primary-path
                                                    # .upper() at line ~474.
                                                    matched = False
                                                    for alt in alternatives:
                                                        if alt.lower() in v.lower():
                                                            reasoning[name] = alt.upper()
                                                            matched = True
                                                            break

                                                    # If not matched, try normalization.
                                                    # normalize_construct_value returns
                                                    # the canonical alternative (already
                                                    # uppercase for our LABEL patterns),
                                                    # but .upper() here matches the
                                                    # primary-path discipline so the same
                                                    # invariant holds across both branches.
                                                    if not matched:
                                                        normalized = normalize_construct_value(v, alternatives, custom_mapping=custom_mapping)
                                                        if normalized.upper() in [a.upper() for a in alternatives]:
                                                            reasoning[name] = normalized.upper()
                                                        # else: Leave empty, let CONSTRUCT EXTRACTION handle it
                                                else:
                                                    # No alternatives to match against, try normalization
                                                    reasoning[name] = normalize_construct_value(v, custom_mapping=custom_mapping)
                                            except Exception:
                                                reasoning[name] = normalize_construct_value(v, custom_mapping=custom_mapping)
                                    else:
                                        reasoning[name] = normalize_construct_value(v, custom_mapping=custom_mapping)
                                else:
                                    # Don't overwrite REASON if already populated with real text
                                    if "_REASON" in name and reasoning.get(name) and len(str(reasoning[name])) > 10:
                                        continue
                                    reasoning[name] = normalize_construct_value(v, custom_mapping=custom_mapping)
                        else:
                            # Fallback: direct name match
                            k_upper = k.upper()
                            if k_upper in construct_mapping:
                                reasoning[k_upper] = normalize_construct_value(v, custom_mapping=custom_mapping)
                            else:
                                reasoning[k] = normalize_construct_value(v, custom_mapping=custom_mapping)
        except (json.JSONDecodeError, AttributeError) as exc:
            # PR-4 (audit finding #5): this previously swallowed the failure
            # with no trace of it anywhere -- a row that fell all the way
            # through to keyword/digit/default parsing carried no record of
            # WHY the JSON attempt failed. Flag-OFF keeps the silent `pass`
            # byte-for-byte (parsing_warnings must not gain entries no
            # existing corpus has).
            if strict_layers:
                parsing_warnings.append(_sanitize_warning(
                    f"STRICT_LAYERS: JSON parse attempt failed "
                    f"({type(exc).__name__}: {exc}); falling through to "
                    f"keyword/default layers."
                ))

        # 4. KEYWORD SEARCH (Fallback if JSON resolution failed)
        if not skill_name:
            # PR-4 (D5): strict_layers is PASSED, not re-read from config here.
            # The parser resolves the flag once per parse call and is the single
            # source of truth for it; a second read is a second chance to
            # disagree with the first.
            kw_res = self._parse_keywords(
                cleaned_target, agent_type, context,
                strict_layers=strict_layers, warnings_sink=parsing_warnings,
            )
            if kw_res:
                skill_name = kw_res.get("skill_name")
                if _magnitude_pct is None:
                    _magnitude_pct = kw_res.get("magnitude_pct")
                # Merge keyword reasoning if json failed
                if not reasoning.get("strategy"):
                    reasoning.update(kw_res.get("reasoning", {}))
                # PR-4 (D2 ii / D3): the surviving keyword routes are still
                # decision-scoped, but two of them decide from a DIGIT and one
                # from a loose skill-name match, and flag-OFF all three land in
                # the audit as a flat "keyword" -- so `parse_layer_digit_share`
                # cannot see them and an analyst cannot tell a parsed
                # `Decision: 3` from a parsed `Decision: buy_insurance`. Under
                # the flag each keeps its own layer name. Flag-OFF the suffix
                # is unconditionally "keyword", exactly as before.
                _kw_mode = (kw_res.get("reasoning") or {}).get("parse_mode")
                if strict_layers and skill_name and _kw_mode == "keyword_digit":
                    _kw_suffix = "keyword+digit"
                elif strict_layers and skill_name and _kw_mode == "fuzzy_name":
                    _kw_suffix = "fuzzy_name"
                else:
                    _kw_suffix = "keyword"
                parse_layer = f"{parse_layer}+{_kw_suffix}" if is_enclosed else _kw_suffix

        # 5. NAKED DIGIT SEARCH (Last Resort)
        # PR-4 (D1): flag-OFF this takes the FIRST standalone single digit
        # ANYWHERE in cleaned_target as the decision -- entirely ungated by the
        # per-agent-type `parsing.strict_mode` YAML key (a digit inside an
        # unrelated JSON field like `"confidence": 3` is just as eligible as a
        # real choice). In a TAE submission run 343/3,276 rows (10.47%) were
        # decided this way. Gating it on strict_mode unconditionally would
        # change flag-OFF output for every strict_mode:true config that happens
        # to rely on it (a byte-identity violation), so the new gate is opt-in
        # via global_config.parsing.strict_layers: flag-OFF this branch is
        # untouched; flag-ON the layer is disabled outright and the row falls
        # through to the bracket/default layers below.
        #
        # The warning fires only when a digit would ACTUALLY have been taken.
        # An unconditional "this layer is disabled" line on every row that
        # reaches step 5 says nothing about that row -- it restates the config
        # -- and buries the rows where the flag genuinely changed the answer.
        if not skill_name:
            digit_match = re.search(r'\b(\d)\b', cleaned_target)
            if digit_match and digit_match.group(1) in skill_map:
                _cand = digit_match.group(1)
                if strict_layers:
                    parsing_warnings.append(_sanitize_warning(
                        f"STRICT_LAYERS: suppressed candidate digit {_cand} -> "
                        f"{skill_map[_cand]} (naked-digit layer)"
                    ))
                else:
                    skill_name = skill_map[_cand]
                    parse_layer = f"{parse_layer}+digit" if is_enclosed else "digit"

        # 6. CONSTRUCT EXTRACTION (Regex based, applied to cleaned_target)
        constructs_cfg = parsing_cfg.get("constructs", {})
        if constructs_cfg and cleaned_target:
            for key, cfg in constructs_cfg.items():
                if key not in reasoning or not reasoning[key]:
                    regex = cfg.get("regex")

                    keywords = cfg.get("keywords", [])
                    if regex and keywords:
                        # 1. Find all keywords and their positions
                        kw_pattern = "|".join([re.escape(kw) for kw in keywords])
                        # Look for keyword with word boundaries
                        kw_matches = list(re.finditer(rf"(?i)\b(?:{kw_pattern})\b", cleaned_target))

                        # Process keywords in reverse (prioritize mentions near the end)
                        found = False
                        for kw_match in reversed(kw_matches):
                            # 2. Look at text following the keyword (up to proximity_window chars gap)
                            start_search = kw_match.end()
                            end_search = min(start_search + proximity_window, len(cleaned_target))
                            gap_text = cleaned_target[start_search:end_search]

                            # 3. Check for values in this gap - pick the FIRST match which is most adjacent
                            # Attempt 1: Exact code match (VL, L, M, H, VH)
                            val_matches = list(re.finditer(regex, gap_text, re.IGNORECASE | re.DOTALL))
                            for val_match in val_matches:
                                temp_val = val_match.group(1).strip() if val_match.groups() else val_match.group(0).strip()
                                g_start = start_search + val_match.start()
                                g_end = start_search + val_match.end()

                                # Phase 6N-D-4 (2026-05-24): whitelist filter.
                                # The free-text fallback scans reasoning prose,
                                # and ``\b(VL|L|M|H|VH)\b`` matches the bare
                                # ``m`` between ``'`` and ``space`` inside
                                # contractions like ``I'm``. Smoke #6 of L3-1C
                                # caught a 1/45 leak; flood Group_C paper data
                                # has 2/8918. Reject any capture whose
                                # upper-cased form is not in the canonical
                                # ordinal alphabet so contraction-letter
                                # captures never reach the audit CSV.
                                if temp_val.upper() not in {"VL", "L", "M", "H", "VH"}:
                                    continue

                                # Only accept if it's NOT just an item in an echoed list
                                if not is_list_item(cleaned_target, g_start, g_end, self.config):
                                    reasoning[key] = normalize_construct_value(temp_val, custom_mapping=custom_mapping)
                                    found = True
                                    break

                            if not found:
                                # Attempt 2: Search for long-form names (e.g. "Medium") in this gap
                                # Collect all matches to pick the one closest to the keyword
                                word_matches = []
                                for word, code in custom_mapping.items():
                                    if len(word) > 2: # Stick to descriptive labels
                                        for m in re.finditer(rf"\b{re.escape(word)}\b", gap_text, re.IGNORECASE):
                                            word_matches.append((m.start(), m.end(), code))

                                if word_matches:
                                    # Sort by start index and pick the first one that passes the list guard
                                    word_matches.sort()
                                    for w_start, w_end, code in word_matches:
                                        g_start = start_search + w_start
                                        g_end = start_search + w_end
                                        if not is_list_item(cleaned_target, g_start, g_end, self.config):
                                            reasoning[key] = code
                                            found = True
                                            break

                            if found: break



        # 6. LAST RESORT: Search for bracketed numbers [1-7] in cleaned_target
        # STRICT MODE: If enabled, do NOT use digit extraction (prevents bias from reasoning text)
        # This forces the system to retry with clearer instructions instead of guessing.
        strict_mode = parsing_cfg.get("strict_mode", True)

        if not skill_name:
            bracket_matches = re.findall(r'\[(\d)\]', cleaned_target)
            digit_matches = re.findall(r'(\d)', cleaned_target)
            candidates = bracket_matches if bracket_matches else digit_matches

            # Allow digit extraction as last resort during retries even in strict mode
            is_retry = context.get("retry_attempt", 0) > 0

            # PR-4 (D1): BOTH arms of this gate are digit routes that are not
            # scoped to a decision line -- `digit_matches` is every digit in the
            # text, and `candidates[-1]` is simply the last one. The
            # strict_mode:false arm fires for any relaxed domain; the `is_retry`
            # arm fires for a strict_mode:true domain on every retry_attempt>0,
            # which is exactly the run where the model already failed to answer
            # cleanly once. Under strict_layers neither takes the digit.
            if candidates and (not strict_mode or is_retry):
                last_digit = candidates[-1]
                if last_digit in skill_map:
                    if strict_layers:
                        parsing_warnings.append(_sanitize_warning(
                            f"STRICT_LAYERS: suppressed candidate digit {last_digit} -> "
                            f"{skill_map[last_digit]} (bracket/digit last-resort layer, "
                            f"strict_mode={strict_mode}, retry={is_retry})"
                        ))
                    else:
                        skill_name = skill_name or skill_map[last_digit]
                        # PR-4 (D4): this `or` is a provenance bug, left as-is
                        # for byte identity -- when parse_layer is already
                        # "enclosure" the digit that actually decided the row is
                        # never recorded, so a digit-decided row is filed under
                        # "enclosure". See docs/AUDIT_SCHEMA.md known
                        # limitations: parse_layer_digit_share is a LOWER BOUND
                        # on any corpus produced without this flag. Under the
                        # flag this branch does not run at all.
                        parse_layer = parse_layer or "digit_fallback"
                        parsing_warnings.append(f"Retry-based extraction from digit: {last_digit}")
            elif candidates and strict_mode and not skill_name:
                # Log the failed parse attempt for audit but do NOT use the digit
                parsing_warnings.append(f"STRICT_MODE: Rejected digit extraction ({candidates[-1]}). Will trigger retry.")

        if not skill_name:
            if strict_mode:
                # Phase 6C-v4 Finding 3+5: surface diagnostic context so
                # new-domain users see WHY the parser failed, not just
                # the misleading "Empty/Null response" log downstream.
                # Three things matter for debugging:
                #   (a) raw_output excerpt — did LLM actually respond?
                #   (b) parse_layer reached — which extraction step ran?
                #   (c) parsing_warnings — what each step complained about
                raw_excerpt = (raw_output or "")[:300].replace("\n", "\\n")
                expected_keys = []
                try:
                    response_format = self.agent_config._config.get("shared", {}).get("response_format", {})
                    expected_keys = [f.get("key", "") for f in response_format.get("fields", []) if f.get("key")]
                except Exception:
                    pass
                msg = (
                    f"STRICT_MODE: Failed to parse any valid decision for agent "
                    f"'{agent_id}'. Default fallback disabled."
                )
                diag = (
                    f"\n   parse_layer reached: {parse_layer or '(none — no enclosure / JSON / keyword matched)'}"
                    f"\n   raw_output (300 chars): {raw_excerpt!r}"
                    f"\n   expected keys in response_format.fields: {expected_keys}"
                    f"\n   parsing_warnings: {parsing_warnings}"
                    f"\n   valid skills for this agent_type: {list(valid_skills)[:6]}"
                    f"\n   Common causes:"
                    f"\n     - YAML response_format.fields keys (e.g. 'X_assessment') don't match prompt JSON example keys (e.g. 'X_appraisal')"
                    f"\n     - Prompt's JSON example missing required 'decision' field or using non-numeric value"
                    f"\n     - LLM returned text but no enclosure delimiter / JSON block / skill keyword detected"
                )
                parsing_warnings.append(msg)
                logger.error(f" [Adapter:Error] {msg}{diag}")
                if strict_layers:
                    # PR-4 (D6): there is no proposal on this path, so the
                    # STRICT_LAYERS suppression lines that explain WHY the row
                    # failed have nowhere to go and are discarded. Stash them
                    # for the retry loop to fold into the next attempt's
                    # proposal, or for the ABORTED sentinel row to carry.
                    #
                    # ONLY the STRICT_LAYERS lines, and tagged with the attempt
                    # they came from. Stashing the whole list would prepend
                    # this attempt's "STRICT_MODE: Failed to parse any valid
                    # decision" diagnostic onto whichever LATER attempt
                    # succeeded, so any analyst counting rows whose
                    # parsing_warnings mention a failed parse would over-count
                    # exactly under the flag. The tag is what keeps a merged
                    # warning distinguishable from one this row produced.
                    attempt = context.get("retry_attempt", 0)
                    self.last_parse_warnings = [
                        _sanitize_warning(f"attempt {attempt}: {w}")
                        for w in parsing_warnings if w.startswith("STRICT_LAYERS:")
                    ]
                return None # Return None to trigger retry/abort in Broker
            else:
                skill_name = parsing_cfg.get("default_skill")
                if not skill_name:
                    raise ValueError(
                        f"Parse failure for agent_type '{agent_type}' has no "
                        "fallback skill. Add 'parsing.default_skill' to "
                        "agent_types.yaml."
                    )
                parse_layer = "default"
                parsing_warnings.append(f"Default skill '{skill_name}' used.")

        # Resolve to canonical ID via alias map (dynamic per agent_type)
        skill_name = alias_map.get(skill_name.lower(), skill_name)

        # 7. Semantic Correlation Audit (Phase 20)
        # Check both T1 and T2/T3 memory storage patterns
        retrieved_memories = context.get("retrieved_memories") or context.get("memory")
        if not retrieved_memories and "personal" in context:
            retrieved_memories = context["personal"].get("memory")

        combined_reasoning = str(reasoning) + cleaned_target

        # 6. Correlation Audit (Standard)
        # ... (Existing logic) ...

        # 7. Demographic Grounding Audit (Phase 21)
        # Checks if qualitative anchors (Persona/History) are cited in reasoning
        demo_audit = audit_demographic_grounding(reasoning, context, parsing_cfg, self.config)
        reasoning["demographic_audit"] = demo_audit


        correlation_score = 0.0
        details = []
        if retrieved_memories and isinstance(retrieved_memories, list):
            # Domain-agnostic audit keywords
            audit_kws = list(parsing_cfg.get("audit_keywords", []))
            # Fallback if empty
            if not audit_kws:
                audit_kws = ["choice", "decision", "action", "reason", "because"]

            kws_pattern = r'\b(' + '|'.join([re.escape(k) for k in audit_kws]) + r')\b'

            for i, mem in enumerate(retrieved_memories):
                mem_text = str(mem).lower()
                # Focus on configured keywords
                kws = re.findall(kws_pattern, mem_text, re.IGNORECASE)
                if kws:
                    hits = [kw for kw in set(kws) if kw.lower() in combined_reasoning.lower()]
                    if hits:
                        correlation_score += (len(hits) / len(set(kws))) * (1.0 / len(retrieved_memories))
                        details.append(f"Mem[{i}] hits: {hits}")


        reasoning["semantic_correlation_audit"] = {
            "score": round(correlation_score, 2),
            "details": details[:3]
        }

        # 6. Post-Parsing Robustness: Completeness Check
        missing_labels = []
        if parsing_cfg and "constructs" in parsing_cfg:
            expected = set(parsing_cfg["constructs"].keys())
            found = set(reasoning.keys())
            missing = expected - found
            if missing:
                msg = f"Missing constructs for '{agent_type}': {list(missing)}"
                parsing_warnings.append(msg)
                logger.warning(f" [Adapter:Diagnostic] Warning: {msg}")
                # Check if any critical LABEL fields are missing - these should trigger retry
                missing_labels = [m for m in missing if "_LABEL" in m]
                if missing_labels:
                    parsing_warnings.append(f"CRITICAL: Missing LABEL constructs {missing_labels}. Triggering retry.")
        if parse_layer:
            year = context.get("current_year", "?")
            logger.info(f" [Year {year}] [Adapter:Audit] Agent {agent_id} | Layer: {parse_layer} | Warnings: {len(parsing_warnings)}")
            # Show reasoning summary
            strat = reasoning.get("strategy", "") or reasoning.get("reason", "")
            if strat:
                logger.debug(f"  - Reasoning: {strat[:120]}...")

            # Show construct classification (Generic)
            construct_parts = []
            for k, v in reasoning.items():
                if "_LABEL" in k:
                    construct_parts.append(f"{k.split('_')[0]}={v}")
            if construct_parts:
                logger.info(f"  - Constructs: {' | '.join(construct_parts)}")

        # 7. Final Polish: Ensure all _LABEL values are normalized before returning
        for k in list(reasoning.keys()):
            if "_LABEL" in k:
                reasoning[k] = normalize_construct_value(str(reasoning[k]), custom_mapping=custom_mapping)

        # 8. Skill Name Normalization (Cross-Model Fix)
        # Convert aliases like "HE", "FI", "insurance" to canonical names
        if skill_name:
            normalized = alias_map.get(skill_name.lower())
            if normalized:
                if normalized != skill_name:
                    logger.debug(f" [Adapter:Normalize] {skill_name} -> {normalized}")
                skill_name = normalized

        # 9. Parse metadata (confidence + construct completeness)
        base_layer = "fallback"
        # PR-4 (audit finding #2): flag-OFF this checks "json" in parse_layer
        # BEFORE "digit", so a row parsed as e.g. "enclosure+json+digit"
        # (JSON present but unusable, decision recovered from a stray digit)
        # is stamped parse_confidence=0.95 -- the schema's highest -- even
        # though the actual decision came from the least reliable layer.
        # Flag-ON any parse_layer containing "digit" outranks "json"
        # regardless of order; flag-OFF the original ordering is unchanged.
        # "fuzzy_name" (PR-4 D3) is a flag-ON-only layer and gets the same 0.50
        # tier as a digit: a loose skill-name match inside a decision line is a
        # recovery, not a parse.
        if strict_layers and "digit" in parse_layer:
            base_layer = "digit"
            parse_confidence = 0.50
        elif strict_layers and "fuzzy_name" in parse_layer:
            base_layer = "fuzzy_name"
            parse_confidence = 0.50
        elif "json" in parse_layer:
            base_layer = "json"
            parse_confidence = 0.95
        elif "keyword" in parse_layer:
            base_layer = "keyword"
            parse_confidence = 0.70
        elif "digit" in parse_layer:
            base_layer = "digit"
            parse_confidence = 0.50
        elif parse_layer == "default":
            base_layer = "fallback"
            parse_confidence = 0.20

        required_constructs = [k for k in constructs_cfg if "_LABEL" in k] + ["decision"]
        found = 0
        for construct in required_constructs:
            if construct in reasoning:
                found += 1
                continue
            if construct == "decision" and skill_name:
                found += 1
                continue
        construct_completeness = found / len(required_constructs)

        parse_metadata["parse_layer"] = base_layer
        parse_metadata["parse_confidence"] = parse_confidence
        parse_metadata["construct_completeness"] = construct_completeness

        # ── Multi-skill: extract secondary_decision if multi_skill enabled ──
        _secondary_skill_name = None
        _secondary_magnitude_pct = None
        ms_cfg = self.agent_config.get_multi_skill_config(agent_type)
        if ms_cfg:
            sec_field = ms_cfg.get("secondary_field", "secondary_decision")
            sec_mag_field = ms_cfg.get("secondary_magnitude_field", "secondary_magnitude_pct")
            sec_val = data_lowered.get(sec_field.lower()) if data_lowered else None

            # Regex fallback for secondary
            if sec_val is None and raw_output:
                sec_pattern = rf'"{sec_field}"\s*:\s*"?(\d+)"?'
                sec_match = re.search(sec_pattern, raw_output, re.IGNORECASE)
                if sec_match:
                    sec_val = sec_match.group(1)

            if sec_val is not None:
                sec_id = None
                if isinstance(sec_val, (int, float)):
                    sec_id = str(int(sec_val))
                elif isinstance(sec_val, str):
                    sec_digit = re.search(r'(\d+)', sec_val)
                    if sec_digit:
                        sec_id = sec_digit.group(1)

                # 0 means "no secondary action"
                if sec_id and sec_id != "0" and sec_id in skill_map:
                    _secondary_skill_name = skill_map[sec_id]

                    # Extract secondary magnitude with bounds validation
                    sec_mag_raw = data_lowered.get(sec_mag_field.lower()) if data_lowered else None
                    if sec_mag_raw is not None:
                        try:
                            mag_val = float(re.search(r'(\d+)', str(sec_mag_raw)).group(1))
                            # Look up bounds from response_format numeric field definition
                            mag_min, mag_max = 1, 100  # safe defaults
                            for nf in self.agent_config.get_numeric_fields(agent_type):
                                if nf["key"] == sec_mag_field:
                                    mag_min = nf.get("min") or mag_min
                                    mag_max = nf.get("max") or mag_max
                                    break
                            if mag_min <= mag_val <= mag_max:
                                _secondary_magnitude_pct = mag_val
                            else:
                                logger.warning(
                                    f" [Multi-Skill] {agent_id} | Secondary magnitude "
                                    f"{mag_val}% out of bounds [{mag_min}, {mag_max}], ignoring"
                                )
                        except (AttributeError, ValueError, TypeError):
                            pass

        # Store secondary in reasoning for broker engine to access
        if _secondary_skill_name:
            reasoning["_secondary_skill_name"] = _secondary_skill_name
            if _secondary_magnitude_pct is not None:
                reasoning["_secondary_magnitude_pct"] = _secondary_magnitude_pct

        reasoning["_parse_metadata"] = parse_metadata

        proposal = SkillProposal(
            agent_id=agent_id,
            skill_name=skill_name,
            reasoning=reasoning,
            agent_type=agent_type,
            raw_output=raw_output,
            parsing_warnings=parsing_warnings,
            parse_layer=parse_layer,
            parse_confidence=parse_confidence,
            construct_completeness=construct_completeness,
            magnitude_pct=_magnitude_pct,
            # 6W-B2: stop discarding the multi-field numeric dict the parser already
            # built. Routed ONLY when this agent_type opts in; frozen domains return
            # False -> {} -> SkillProposal.to_dict omits the key -> byte-identical.
            parameters=(
                dict(_extracted_numerics)
                if self.agent_config.get_multi_param_enabled(agent_type)
                else {}
            ),
        )
        if strict_layers:
            # PR-4 (D5): the PARSER decides whether the hardened layers applied,
            # and the proposal carries that decision downstream. Before this,
            # the parser read the flag off the adapter's config and the audit
            # layer re-derived it from the ENGINE's config — two objects that
            # are the same in production and routinely different in tests and
            # in any embedding that builds them separately. A proposal parsed
            # under the flag could then be classified as though it had not
            # been. Set as a plain attribute rather than a dataclass field on
            # purpose: `SkillProposal.to_dict()` serialises an explicit key
            # list, so an absent attribute cannot leak into flag-OFF JSONL/CSV
            # bytes (pinned by a test), and a flag-ON row gains no key either.
            proposal.strict_layers_applied = True
        return proposal

    def _parse_keywords(
        self, text: str, agent_type: str, context: Dict[str, Any] = None,
        *, strict_layers: bool = False, warnings_sink: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback keyword/regex based parsing.

        ``strict_layers`` is PASSED IN (PR-4 D5), never re-read from config:
        ``parse_output`` resolves the flag once per parse call and this method
        must not be able to disagree with it. Default ``False`` so the direct
        callers in the test suite keep working unchanged.

        ``warnings_sink`` is ``parse_output``'s own ``parsing_warnings`` list.
        The flag-ON warnings raised in here have to reach it even on the paths
        that ``return None``, and a return value cannot carry them then — which
        is exactly the case that matters, because a decision-line digit
        REJECTED by the anchor is a suppression, and a suppression the audit
        cannot count is the one thing this flag exists to prevent. Only ever
        appended to under the flag.
        """
        def _warn(text_):
            if strict_layers and warnings_sink is not None:
                warnings_sink.append(_sanitize_warning(text_))
        parsing_cfg = self.agent_config.get_parsing_config(agent_type)
        if not parsing_cfg: return None

        decision_keywords = parsing_cfg.get("decision_keywords", ["decision", "choice", "action", "selected_action"])
        valid_skills = self.agent_config.get_valid_actions(agent_type)
        skill_map = self.agent_config.get_skill_map(agent_type, context)

        found_skill = None
        found_mag = None

        # 0. PRE-AUDIT: Look for numeric fields in the text (dynamic, config-driven)
        numeric_fields = self.agent_config.get_numeric_fields(agent_type)
        numeric_keys = [nf.get("key", "") for nf in numeric_fields] if numeric_fields else []

        # Build regex pattern from configured numeric field keys, plus legacy fallbacks
        search_keys = numeric_keys + ["magnitude", "pct", "percent", "amount"]
        unique_keys = list(set([k for k in search_keys if k]))  # dedupe

        if unique_keys:
            pattern = r'(?:' + '|'.join(re.escape(k) for k in unique_keys) + r')\b\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)'
            mag_match = re.search(pattern, text.lower())
            if mag_match:
                found_mag = float(mag_match.group(1))

        # 1. DECISION LINE SEARCH
        # PR-4 (D3): remember the FIRST decision line's value text. Under
        # strict_layers the skill-name recovery at step 2b is scoped to it
        # instead of scanning the whole response; None means the model never
        # emitted a decision line, and step 2b then cannot fire at all.
        decision_value_text = None
        lines = text.split('\n')
        for line in lines:
            line_lower = line.strip().lower()
            for kw in decision_keywords:
                # Look for kw followed by punctuation or space
                if re.search(rf"\b{re.escape(kw.lower())}\b", line_lower):
                    split_parts = re.split(rf"\b{re.escape(kw.lower())}\b", line_lower, maxsplit=1)
                    if len(split_parts) > 1:
                        raw_val = split_parts[1].strip()
                        if decision_value_text is None:
                            decision_value_text = raw_val
                        # 1a. Try Digit in keyword line.
                        # PR-4 (D2 i): this route is KEPT under strict_layers --
                        # `Decision: 3` is the documented prompt contract and the
                        # digit here IS decision-scoped. But `re.search(r'(\d)')`
                        # scopes it only to the line, not to the value: for
                        # "Decision: I will revisit this in 2 or three years" it
                        # returns 2, and skill 2 becomes the recorded decision.
                        # Under the flag the digit must be the value itself --
                        # optionally behind a separator -- and must end on a word
                        # boundary, so "in 2 or three years" no longer resolves.
                        # The anchor itself, and why its wrapper class is wide,
                        # is documented at DECISION_VALUE_DIGIT_RE.
                        if strict_layers:
                            digit_match = DECISION_VALUE_DIGIT_RE.match(raw_val)
                            # A digit the OLD path would have taken and this one
                            # does not is a SUPPRESSION, and every other
                            # suppression under this flag records itself. Left
                            # silent, an over-tight anchor would show up only as
                            # a mysterious rise in `default` / ABORTED rows with
                            # nothing in the audit to attribute it to.
                            if not digit_match:
                                loose = re.search(r'(\d)', raw_val)
                                if loose and loose.group(1) in skill_map:
                                    _warn(
                                        f"STRICT_LAYERS: decision-line digit "
                                        f"{loose.group(1)} -> {skill_map[loose.group(1)]} "
                                        f"rejected by the value anchor (the digit is not "
                                        f"the decision value): {raw_val[:80]!r}"
                                    )
                        else:
                            digit_match = re.search(r'(\d)', raw_val)
                        if digit_match and digit_match.group(1) in skill_map:
                            return {
                                "skill_name": skill_map[digit_match.group(1)],
                                "magnitude_pct": found_mag,
                                # PR-4 (D2 ii): flag-ON, tell parse_output this
                                # decision came from a digit so it can stamp
                                # parse_layer "keyword+digit" and
                                # parse_layer_digit_share can see it. Flag-OFF
                                # the reasoning dict stays exactly {}.
                                "reasoning": {"parse_mode": "keyword_digit"} if strict_layers else {},
                            }
                        # 1b. Try exact skill name match in this line
                        for s in valid_skills:
                            if re.search(rf"\b{re.escape(s.lower())}\b", raw_val):
                                return {"skill_name": s, "magnitude_pct": found_mag, "reasoning": {}}

        # 2. GLOBAL FUZZY SEARCH (Fallback if no decision line found)
        # Search for any mention of a skill ID or skill name in the entire text
        text_lower = text.lower()

        # 2a. Look for "I choose X", "Plan: X", etc. anywhere
        choice_patterns = [
            r"i (?:choose|select|decide on|will use) (?:choice|option|skill)?\s*[:]?\s*(\d)\b",
            r"selected (?:choice|option|skill)\s*[:]?\s*(\d)\b",
            r"\bchoice\s*(\d)\b",
            r"\bskill\s*(\d)\b"
        ]
        # PR-4 (D2): these patterns are KEPT under strict_layers. Unlike the
        # naked-digit layers they each require an explicit choice phrase
        # ("I choose 3", "choice 3", "skill 3"), which is decision-scoped by
        # construction. Flag-ON they report parse_mode "keyword_digit" like
        # route 1a, so the layer lands in the audit as "keyword+digit" and every
        # surviving digit route stays countable in parse_layer_digit_share
        # rather than hiding behind a flat "keyword".
        for pattern in choice_patterns:
            matches = list(re.finditer(pattern, text_lower))
            if matches:
                last_digit = matches[-1].group(1)
                if last_digit in skill_map:
                    return {
                        "skill_name": skill_map[last_digit],
                        "magnitude_pct": found_mag,
                        "reasoning": {
                            "parse_mode": "keyword_digit" if strict_layers else "fuzzy_regex"
                        },
                    }

        # 2b. Look for unique skill names.
        #
        # Flag-OFF this line is DEAD and is kept verbatim so it stays dead:
        # `rf"\b{...}\b" in text_lower` tests whether the model's own text
        # contains the regex SOURCE (the six characters `\b`, the skill name,
        # `\b`) as a literal substring. It can only fire if the model emits
        # that source text itself, which no corpus has. Turning it on for an
        # existing corpus would start matching skill names that corpus never
        # matched, so the working form is flag-ON only.
        #
        # Flag-ON (PR-4 D3) it does NOT simply become a whole-text `re.search`.
        # A whole-text search is a verified false positive generator: on
        # "...so I will not purchase insurance this year" it matches the single
        # skill "insurance" and returns buy_insurance -- the exact opposite of
        # what the agent said -- at parse_confidence 0.70, the keyword tier. So
        # under the flag it is scoped to the decision line only (the same
        # scoping route 1a uses), requires that line to exist at all, gets its
        # own parse_layer "fuzzy_name" at the 0.50 recovery tier rather than
        # hiding inside "keyword", and records a warning naming the match.
        found_skills = []
        if strict_layers:
            if decision_value_text is not None:
                for s in valid_skills:
                    for variant in (s.lower(), s.lower().replace("_", " ")):
                        if re.search(rf"\b{re.escape(variant)}\b", decision_value_text):
                            found_skills.append(s)
                            break
        else:
            for s in valid_skills:
                s_variants = [s.lower(), s.lower().replace("_", " ")]
                for variant in s_variants:
                    if rf"\b{re.escape(variant)}\b" in text_lower:  # dead on purpose, see above
                        found_skills.append(s)
                        break

        if len(set(found_skills)) == 1:
            # Truncated: this quotes MODEL-AUTHORED text into a CSV column, and
            # an unbounded quote turns one audit field into a paragraph of the
            # response the raw_output column already holds in full.
            _warn(
                f"STRICT_LAYERS: decision-line skill-name recovery resolved "
                f"'{(decision_value_text or '')[:80]}' -> {found_skills[0]} "
                f"(parse_layer fuzzy_name, confidence 0.50)"
            )
            return {"skill_name": found_skills[0], "magnitude_pct": found_mag,
                    "reasoning": {"parse_mode": "fuzzy_name"}}

        # If we found magnitude but no skill, we still return just magnitude in case it helps
        if found_mag:
            return {"skill_name": None, "magnitude_pct": found_mag, "reasoning": {}}

        return None


    def format_retry_prompt(self, original_prompt: str, errors: List[Any], max_reports: Optional[int] = None) -> str:
        """
        Format retry prompt with validation errors or InterventionReports.

        Supports both legacy List[str] errors and new List[InterventionReport] for XAI.

        P0-1c: thin delegation to :meth:`format_intervention_prompt` with the
        ``legacy`` framing, whose body is this method's original code verbatim.
        Kept as a separate name because it is the published arm-C entry point and
        a golden-string test pins its exact output.
        """
        text, _shown = self.format_intervention_prompt(
            original_prompt, errors, max_reports=max_reports, framing="legacy",
        )
        return text

    def format_intervention_prompt(
        self,
        original_prompt: str,
        errors: List[Any],
        *,
        max_reports: Optional[int] = None,
        framing: str = "legacy",
        header: Optional[str] = None,
        closer: Optional[str] = None,
        include_reports: bool = True,
    ) -> "tuple[str, int]":
        """P0-1c: shared renderer for retry AND advisory prompts.

        Returns ``(prompt_text, reports_shown)``. ``reports_shown`` is emitted to the
        audit trace so "truncation never bound" is a MEASURED fact per decision
        rather than an assumption in the Methods.

        ``framing="legacy"`` (default) reproduces the shipped retry prompt
        byte-for-byte -- same truncation warning, same ``[!NOTE]`` suffix, same
        f-string. ``framing="neutral"`` is opt-in and used by the new experiment
        arms: it states only that a rule was triggered, never that the action was
        blocked, and suppresses the optional Suggestion line so report SHAPE is
        constant across rule families (YAML thinking rules carry no suggestion;
        domain custom validators do). That constancy is what makes the
        enforce-minus-advise contrast pure enforcement.

        ``include_reports=False`` renders the wrapper alone (header + closer +
        original prompt) with no rules block -- the A'' wrapper-only control, which
        exists because otherwise the placebo-minus-resample term absorbs prompt
        restructuring and position shift alongside generic corrective pressure.
        """
        from ...interfaces.skill_types import InterventionReport

        if framing not in ("legacy", "neutral"):
            raise ValueError(f"framing {framing!r} not in ['legacy', 'neutral']")

        if framing == "neutral":
            verb, show_suggestion = "triggered a governance rule", False
            header = header if header is not None else (
                "Your previous response triggered the governance layer."
            )
            closer = closer if closer is not None else (
                "Please reconsider your decision in light of the information above."
            )
            section = "**Rules Triggered:**"
        else:
            verb, show_suggestion = "was BLOCKED", True
            header = header if header is not None else (
                "Your previous response was flagged by the governance layer."
            )
            closer = closer if closer is not None else (
                "Please reconsider your decision. Ensure your new response "
                "addresses the violations above."
            )
            section = "**Issues Detected:**"

        if not include_reports:
            # Wrapper-only (arm A''): identical scaffolding, zero rule content.
            return f"""{header}

{closer}

{original_prompt}""", 0

        if max_reports and len(errors) > max_reports:
            logger.warning(f" [Adapter] Truncating retry reports from {len(errors)} to {max_reports} to save context.")
            errors = errors[:max_reports]
            truncated = True
        else:
            truncated = False

        error_lines = []
        for e in errors:
            if isinstance(e, InterventionReport):
                error_lines.append(e.to_prompt_string(
                    verb=verb, show_suggestion=show_suggestion))
            elif isinstance(e, str):
                error_lines.append(f"- {e}")
            else:
                error_lines.append(f"- {str(e)}")

        if truncated:
            error_lines.append(f"\n[!NOTE] There were more issues detected, but only the top {max_reports} are shown for brevity. Please fix these first.")

        error_text = "\n".join(error_lines)
        return f"""{header}

{section}
{error_text}

{closer}

{original_prompt}""", len(errors)
