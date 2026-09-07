"""SkillFilterMixin — skill filtering and option injection for LLM prompts.

Extracted from SkillBrokerEngine to reduce file size.  These methods
access ``self.*`` attributes defined on SkillBrokerEngine; this is the
standard Python mixin pattern where the mixin is always combined with
the host class via multiple inheritance.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logging import logger

# Options-text parity guard (2026-09, hardened after silent-failure review):
# a placeholder LLM answer's numeric digit is decoded against
# ``dynamic_skill_map`` — if that map's install order ever diverges from
# what the model was actually shown, the decode is silently wrong. See
# ``check_options_text_parity`` below for the fail-CLOSED contract: every
# branch that cannot PROVE the install is safe must raise, never return.


def check_options_text_parity(
    *,
    agent_type: str,
    installed_order: List[str],
    registry_ids: List[str],
    template: Optional[str],
    template_path: str,
    decision_field_is_numeric_choice: bool,
) -> None:
    """The one real choke point for the options-text parity check.

    Both places this broker ever installs a ``dynamic_skill_map`` call
    into this function so they can never drift apart:

    1. ``SkillFilterMixin._inject_options_text`` (below), reached from the
       RAG re-rank path (``skill_broker_engine.py``'s "Phase 28" block)
       and the plain registry-order path (``_inject_filtered_skills``).
    2. ``TieredContextBuilder.format_prompt``'s own fallback map-builder
       (``broker/components/context/tiered.py``, the ``if not options_text
       and agent:`` branch) — a SEPARATE ``dynamic_skill_map`` construction
       (different source: ``agent.get_available_skills()``, different
       shuffle: ``context["_shuffle_skills"]``) that a 2026-09 silent-
       failure review found installed a map with NO parity check at all.

    Callers own resolving ``agent_type`` / ``registry_ids`` / ``template``
    / ``decision_field_is_numeric_choice``; this function owns only the
    comparison and the fail-closed decision.

    FAIL-CLOSED CONTRACT (post-review): a branch that cannot verify parity
    must RAISE, not return. A false BLOCK costs a clear error message and
    a rerun; a missed block silently corrupts ``proposed_skill`` with no
    signal anywhere. Every early-exit below is provably safe (the order
    genuinely matches, or the template genuinely shows the live list, or
    the model is genuinely never asked for a digit) — not a "couldn't
    tell, so let it through."

    KNOWN LIMITATION (silent-failure hunter finding NEW-3, documented not
    fixed): every check here scans the RAW, un-rendered ``template``
    string for a literal placeholder or spelled-out name. A legend that
    only becomes visible AFTER another placeholder is filled in — e.g. a
    numbered list or digit legend built dynamically and injected via
    ``{system_prompt}``, ``{institutional_section}``, or an arbitrary
    ``template_vars`` entry, rather than appearing literally in the
    template file — is invisible to this scan in BOTH directions: a
    dynamically-injected legend that WOULD make an otherwise-bare
    template safe is not credited (a false BLOCK — annoying but safe),
    and, more importantly, a dynamically-injected DIGIT legend hidden
    inside one of those other placeholders is not seen either, so this
    guard cannot detect that specific shape of the original bug. No
    known instance of the latter exists in this repo as of this PR (every
    production template's options text flows through
    ``{options_text}``/``{skills_text}``/``{skills}``, which the scan
    does check), but a future domain that builds its numbered options
    list into ``system_prompt`` (or any other filled placeholder) instead
    would not be caught here.
    """
    if not registry_ids:
        # A single-skill map has no ordering that could mis-decode,
        # registry or not — safe regardless of what follows.
        if len(installed_order) <= 1:
            return
        # No registry (actions:) list resolvable for this agent_type at
        # all — e.g. skills sourced from AgentConfig.skills / passed
        # directly from the skill registry rather than a YAML actions:
        # block (older/programmatic usage predating this config path —
        # see tests/test_skill_retrieval.py::test_skill_broker_integration,
        # tests/test_v3_2_features.py::test_v3_2_full_integration, both
        # of which run with no agent_types.yaml at all). There is no
        # registry-declared order to have diverged FROM, so "order drift
        # from the registry" is not a meaningful failure here. Fall
        # through to the SAME template-safety checks used below —
        # {options_text}/{skills_text} live legend, or a safe name-based
        # decision — instead of raising unconditionally. Failure
        # direction stays fail-safe: a genuinely misconfigured YAML
        # domain (multi-skill, no registry, no legend anywhere in its
        # template) still raises below.
        if template and ("{options_text}" in template or "{skills_text}" in template):
            return
        # {skills} is NOT accepted unconditionally here (round 4
        # reviewer + hunter finding): under TieredContextBuilder it is
        # not a template var at all (renders "[N/A]" -- see the
        # not-template branch's docstring above), and even under
        # BaseAgentContextBuilder, which DOES fill it, it renders an
        # UNNUMBERED list ("- id: description", no "1."/"2." prefix) --
        # safe for a name-based decision (the model answers by name, no
        # digit involved) but NOT safe on its own if the template ALSO
        # invites a digit answer some other way (a re-rankable numeric
        # menu with no visible number-to-name mapping is exactly the
        # vaccination_demo bug shape). So {skills} only counts as a live
        # legend when the template does not otherwise invite a digit.
        if template and "{skills}" in template and not _invites_digit(
            template, decision_field_is_numeric_choice,
        ):
            return
        if template and _is_name_based_and_safe(template, installed_order, decision_field_is_numeric_choice):
            return
        raise RuntimeError(
            f"Options-text parity guard cannot verify agent_type={agent_type!r}: "
            f"no resolvable registry (actions:) list for a dynamic_skill_map "
            f"installed in order {list(installed_order)}, AND prompt template "
            f"{template_path!r} shows no live legend ({{options_text}}, "
            f"{{skills_text}}, or {{skills}}) and does not safely spell out "
            f"every skill by name. An unknown or misconfigured agent_type "
            f"must not be silently exempt while RAG can still re-rank it — "
            f"add an 'actions:' block (top-level or under 'parsing:'), fix "
            f"the config lookup, or render one of those placeholders."
        )
    expected_order = [s for s in registry_ids if s in installed_order]
    if expected_order == list(installed_order):
        return  # order matches the registry — a static legend would still be correct

    if not template:
        raise RuntimeError(
            f"Options-text parity guard cannot verify agent_type={agent_type!r}: "
            f"the dynamic skill map was installed in order {list(installed_order)} "
            f"(registry order {expected_order}) but NO template text is "
            f"reachable for this agent type at {template_path!r}. This is not "
            f"safe to skip: BaseAgentContextBuilder's real fallback is "
            f"DEFAULT_PROMPT_TEMPLATE ('ACT:{{skills}}' — the exact "
            f"vaccination_demo shape, {{skills}} is never filled by "
            f"TieredContextBuilder), and TieredContextBuilder's own default "
            f"already carries {{options_text}}; a caller that cannot tell "
            f"which will render must not assume the safe one. Likely cause: "
            f"load_prompt_templates() silently dropped this agent_type's file "
            f"(a '[PromptLoader] Template file not found' warning at load "
            f"time) or context_builder.prompt_templates was never populated."
        )

    if "{options_text}" in template or "{skills_text}" in template:
        return  # template renders the live, re-ranked list — order-safe

    if _is_name_based_and_safe(template, installed_order, decision_field_is_numeric_choice):
        return  # every skill name is spelled out live AND no digit is ever requested

    raise RuntimeError(
        f"Options-text parity violation for agent_type={agent_type!r}: "
        f"the dynamic skill map was installed in order {list(installed_order)} "
        f"which differs from the registry (actions:) order {expected_order}, "
        f"but prompt template {template_path!r} renders neither "
        f"{{options_text}} nor {{skills_text}}, and does not (safely) spell "
        f"out every skill name as a name-based decision — the model cannot "
        f"see the actual numbered list, so its digit answer will decode "
        f"against the wrong skill. Fix: render {{options_text}} in the "
        f"prompt template, or set parsing.full_disclosure: true in "
        f"agent_types.yaml to keep the registry order stable."
    )


# A skill id containing a digit is disqualifying on its own: unified_adapter.py
# Case 2 (``re.search(r'(\d+)', decision_val)``) extracts the FIRST digit
# ANYWHERE in the model's answer string and, if that digit is a key in
# ``dynamic_skill_map``, decodes POSITIONALLY before ever trying name/alias
# resolution. A digit-bearing id (e.g. a hypothetical "phase_2_skill") could
# get silently mis-decoded via that digit even though the template shows
# every name in full — so a name-based exemption must refuse to apply
# whenever any id itself contains a digit, independent of everything else.
_NAME_LIKE_ID = re.compile(r"^[A-Za-z_]+$")

# A literal example value in an inline JSON decision field, e.g.
# ``"decision": 1`` or ``"decision": "2"`` — a template can legitimately
# spell out every skill's name AND still show a numbered-example decision
# value; that combination still invites a digit answer.
_NUMBERED_DECISION_EXAMPLE = re.compile(r'"decision"\s*:\s*"?\d')


# ResponseFormatBuilder.build() (broker/components/response_format.py) is
# the ONLY broker code that turns a declared ``type: "choice"`` into a
# numeric-ID instruction, and it does so ONLY inside the block assigned to
# ``template_vars["response_format"]`` -- i.e. only if the template
# actually renders ``{response_format}``. A YAML declaring ``type:
# "choice"`` for a template that never references ``{response_format}``
# (e.g. MA flood's government.txt/insurance.txt, which hand-write their
# own JSON example) can NEVER actually show that numeric instruction to
# the model -- the declared type is inert. So the declared type is
# consulted ONLY conditional on {response_format} being present.
_RESPONSE_FORMAT_PLACEHOLDER = "{response_format}"

# {valid_choices_text} is different: it is built directly in
# _inject_options_text as an unconditional digit-count string ("1, 2, or
# 3"), independent of any response_format field type. Its mere presence
# in a template invites a digit answer regardless of declared type.
_VALID_CHOICES_TEXT_PLACEHOLDER = "{valid_choices_text}"

# A fully hand-rolled numeric prompt needs neither broker placeholder --
# two or more lines starting "<digit>. " is the same numbered-list shape
# _inject_options_text's own {options_text} renders, just typed by hand.
_NUMBERED_OPTION_LIST = re.compile(r"^\s*\d+\.\s", re.MULTILINE)


def _has_numbered_option_list(template: str) -> bool:
    return len(_NUMBERED_OPTION_LIST.findall(template)) >= 2


def _invites_digit(template: str, decision_field_is_numeric_choice: bool) -> bool:
    """True iff ``template`` itself invites (or could render) a DIGIT
    answer, through any of the four independent mechanisms this guard
    knows about. Shared by ``_is_name_based_and_safe`` (a name-based
    TEMPLATE must not ALSO invite a digit) and the no-registry
    fall-through's ``{skills}`` acceptance (round 4 reviewer/hunter
    finding: ``{skills}`` was being accepted unconditionally there, but
    it is not a safe legend on its own -- see the caller for the two
    concrete ways it fails).

    1. A literal ``{valid_choices_text}`` placeholder -- unconditionally
       a digit-count string ("1, 2, or 3") built by
       ``_inject_options_text``, independent of any declared field type.
    2. A literal ``{response_format}`` placeholder WHILE the decision
       field is declared ``type: "choice"`` (or ``"secondary_choice"``)
       -- ``ResponseFormatBuilder.build()`` is the only code that turns
       that declared type into a numeric-ID instruction, and only inside
       the block it renders there.
    3. A literal numbered-example decision value (``"decision": 1``
       -style) directly in the raw text.
    4. A hand-written numbered option list (``1. .../2. ...``) directly
       in the raw text, needing no broker placeholder at all.

    KNOWN LIMITATION (silent-failure hunter finding P2, round 7,
    documented not fixed -- see CHANGELOG.md known issues): this function
    is TEMPLATE-oriented -- all four checks look for UNRENDERED
    placeholder tokens or hand-written patterns. A round-7 attempt to
    also cover the literal RENDERED text ``ResponseFormatBuilder.build()``
    produces ("Numeric ID, choose ONE from: ...") false-blocked the cat
    MA / reservoir domains, which inject a static hand-written menu via
    ``dynamic_state["options_text"]`` while separately rendering
    ``{response_format}`` for an unrelated field -- a shape this function
    cannot distinguish from the genuinely vulnerable one without also
    consulting the rendered ``personal['options_text']``. Reverted; see
    ``assert_rendered_prompt_shows_options``'s name-based branch for the
    residual gap this leaves open.
    """
    if _VALID_CHOICES_TEXT_PLACEHOLDER in template:
        return True
    if _RESPONSE_FORMAT_PLACEHOLDER in template and decision_field_is_numeric_choice:
        return True
    if _NUMBERED_DECISION_EXAMPLE.search(template):
        return True
    if _has_numbered_option_list(template):
        return True
    return False


def _is_name_based_and_safe(
    template: str, installed_order: List[str], decision_field_is_numeric_choice: bool,
) -> bool:
    """True only when the model is being shown skill NAMES, never a digit,
    AND nothing about this agent's shape lets a digit sneak into the
    decode path anyway. ALL conditions are required (hardened post
    silent-failure review, precision pass 2026-09):

    1. Every installed skill id matches ``^[A-Za-z_]+$`` — no digits in
       the id itself (see ``_NAME_LIKE_ID`` above for why a digit-bearing
       id is disqualifying regardless of the template).
    2. Every installed skill's literal id appears in the template as a
       whole token (word-boundary regex, not a bare substring test — a
       bare ``sid in template`` is satisfiable by prose, or by a shorter
       id that happens to be a substring of a longer one, e.g. "insurance"
       inside "reinsurance_program").
    3. No literal ``{valid_choices_text}`` placeholder (unconditionally a
       digit-count string — see above).
    4. No ``{response_format}`` placeholder WHILE the decision field is
       declared ``type: "choice"`` — that combination is what actually
       renders a numeric-ID instruction; ``{response_format}`` with any
       OTHER declared type, or a declared ``type: "choice"`` the template
       never renders via ``{response_format}``, is inert and must not
       disqualify the exemption (this is precisely MA flood's
       government/insurance shape: ``type: "choice"`` declared but never
       rendered).
    5. No literal numbered-example decision value (``"decision": 1``
       -style) or hand-written numbered option list (``1. ...
2. ...``)
       directly in the raw text — catches a fully hand-rolled numeric
       prompt that uses no broker placeholder at all.
    """
    if not installed_order:
        return False
    for sid in installed_order:
        if not _NAME_LIKE_ID.match(sid):
            return False
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(sid)}(?![A-Za-z0-9_])"
        if not re.search(pattern, template):
            return False
    if _invites_digit(template, decision_field_is_numeric_choice):
        return False
    return True


def resolve_registry_ids(cfg: Any, agent_type: str) -> List[str]:
    """Duck-typed registry (``actions:``) id resolver — accepts any config
    object exposing ``.get_base_type`` (optional) and ``.get(agent_type)``
    (an ``AgentTypeConfig`` real instance, or a plain dict). Shared by
    ``SkillFilterMixin._get_action_ids`` and
    ``TieredContextBuilder.format_prompt``'s render-time check so both
    call sites resolve the SAME way — the class of drift a 2026-09 review
    flagged when the two used separately hand-rolled lookups.
    """
    base_type = cfg.get_base_type(agent_type) if hasattr(cfg, "get_base_type") else agent_type
    block = cfg.get(base_type) if cfg else {}
    actions = block.get("actions", block.get("parsing", {}).get("actions", [])) if block else []
    return [a["id"] for a in actions if isinstance(a, dict) and a.get("id")]


_NUMERIC_CHOICE_FIELD_TYPES = ("choice", "secondary_choice")


def resolve_decision_field_is_numeric_choice(cfg: Any, agent_type: str) -> bool:
    """True iff the config declares ANY response_format field as
    ``type: "choice"`` or ``type: "secondary_choice"`` — BOTH render a
    numeric-ID instruction (see ``ResponseFormatBuilder.build()``'s
    ``elif ftype == "choice":`` at response_format.py:143 AND
    ``elif ftype == "secondary_choice":`` at response_format.py:150-153 —
    a silent-failure hunter finding: the first version of this function
    only checked ``type == "choice"``, missing ``secondary_choice``
    entirely).

    Checked across ALL fields, not filtered to ones whose ``key`` matches
    a guessed decision-keyword set: this function used to require
    ``f.get("key") in decision_keywords`` with a hardcoded default of
    ``{"decision"}`` — but ``unified_adapter.py``'s OWN default
    (``parsing_cfg.get("decision_keywords", ["decision", "choice",
    "action"])``, unified_adapter.py:427) is wider, and a YAML need not
    declare ``decision_keywords`` explicitly to use it. Re-deriving that
    default here risks drifting from the real one; a numeric-choice field
    under ANY key is itself a live signal the model is being primed to
    answer in digits, so checking all fields is both simpler and more
    conservative (fail-closed) than trying to match keys.

    Fails CLOSED (True) when this can't be determined — see
    ``_is_name_based_and_safe``.
    """
    try:
        base_type = cfg.get_base_type(agent_type) if hasattr(cfg, "get_base_type") else agent_type
        block = cfg.get(base_type) if cfg else {}
        if not isinstance(block, dict):
            return True
        shared_rf = {}
        get_shared = getattr(cfg, "get_shared", None)
        if callable(get_shared):
            shared_rf = get_shared("response_format", {}) or {}
        rf = block.get("response_format") or shared_rf or {}
        fields = rf.get("fields", []) if isinstance(rf, dict) else []
        for f in fields:
            if isinstance(f, dict) and f.get("type") in _NUMERIC_CHOICE_FIELD_TYPES:
                return True
        return False
    except Exception:  # noqa: BLE001 — fail closed, not open
        return True


def resolve_template_path(cfg: Any, agent_type: str) -> str:
    """Best-effort ``prompt_template_file`` lookup, for error messages only."""
    try:
        base_type = cfg.get_base_type(agent_type) if hasattr(cfg, "get_base_type") else agent_type
        block = cfg.get(base_type) if cfg else {}
        path = block.get("prompt_template_file") if isinstance(block, dict) else None
        return path or "<inline or unknown>"
    except Exception:  # noqa: BLE001 — best-effort message enrichment only
        return "<inline or unknown>"


def assert_rendered_prompt_shows_options(
    agent_type: str,
    rendered_prompt: str,
    dynamic_skill_map: Optional[Dict[str, str]],
    options_text: Optional[str],
) -> None:
    """Close the residual gap every earlier check in this module leaves
    open (silent-failure review NEW-3, round 4): ``check_options_text_parity``
    and friends verify the un-rendered TEMPLATE STRING is shaped safely
    (a ``{options_text}`` placeholder is present, or every skill name is
    spelled out). None of that proves the FINAL string actually handed to
    the LLM still carries that legend -- a legend delivered through
    ANOTHER filled placeholder (``{system_prompt}``,
    ``{institutional_section}``, an unrecognized ``template_vars`` entry)
    is invisible to a template-only scan in either direction. This
    function is the one check that looks at what the model actually
    received, called once per LLM call right after
    ``context_builder.format_prompt()`` produces the final string
    (``broker/core/skill_broker_engine.py``, immediately before
    ``llm_invoke``) -- the single point every rendered prompt in this
    broker passes through.

    Cheap by design (a handful of substring/regex checks per decision,
    only when there is more than one option to mis-decode): fires only
    when ``dynamic_skill_map`` has more than one entry (a single-skill or
    empty map has no ordering to mis-decode). Passes when EITHER:

    1. every line ``_inject_options_text`` produced (``"<n>. <label>"``,
       read back verbatim from ``options_text``) appears in the rendered
       prompt as a literal substring -- the exact legend the model needs
       to resolve a digit answer correctly against the CURRENT map order;
       OR
    2. every installed skill id appears in the rendered prompt as a
       whole word -- a name-based agent needs no numbered legend at all.

    KNOWN LIMITATION (silent-failure hunter finding P2, round 7,
    documented not fixed -- see CHANGELOG.md known issues): path 2 above
    accepts "every id present" unconditionally, even when the rendered
    prompt ALSO separately asks for a numeric ID with no visible
    number->name mapping (a prompt that spells out every name in prose
    AND says "Numeric ID, choose ONE from: 1, 2, or 3" is exactly the
    vulnerable shape -- the model may still answer with a bare digit,
    which decodes POSITIONALLY against ``dynamic_skill_map``
    (``unified_adapter.py`` Case 2), not by the name it saw in prose). A
    round-7 fix closing this gap by requiring
    ``not _invites_digit(rendered_prompt, decision_field_is_numeric_choice)``
    here too was reverted: it false-blocked the cat MA / reservoir
    domains, which inject a static hand-written menu via
    ``dynamic_state["options_text"]`` (missed by path 1's exact-line
    match, since that menu is written directly rather than produced by
    ``_inject_options_text``) while separately rendering
    ``{response_format}`` for an unrelated field. No shipped template
    exercises the actual vulnerable shape today. Fix direction: compare
    against the RENDERED ``personal['options_text']`` (which, unlike the
    template-time ``_invites_digit`` check, would see the real static
    override from ``dynamic_state`` and not misfire on it) rather than
    re-deriving "is this numeric" from the template's declared field
    type.

    Raises, naming the agent_type and what was expected, when NEITHER
    holds -- that is exactly the vaccination_demo/cat_model shape: the
    model saw no menu (or the wrong one), and every later decision would
    decode against the wrong skill, so stopping the run is the correct
    call.

    NOT a third path (round 6, silent-failure hunter finding NEW-9,
    removed here): an earlier round 5 fix accepted ANY numbered list
    whose count matched ``len(dynamic_skill_map)``, regardless of what
    the list's lines actually said -- meant to tolerate
    ``broker/experiments/replay.py`` replaying a historically-recorded
    prompt whose label wording no longer matches what the engine
    generates today. That shape/arity check was too permissive: an
    UNRELATED numbered list of the same length (a "1. Review your
    situation / 2. Assess the threat / 3. Answer in JSON" instruction
    block for a 3-skill menu, or irrigation's 1-5 rating-scale legend for
    its 5-skill menu) would satisfy it just as well as a real menu,
    silently masking a genuinely missing ``[N/A]`` options list. Replay
    is instead handled the other way round: ``SkillBrokerEngine.process_step``'s
    ``render_check=False`` parameter (round 5) makes this whole function
    a documented no-op for replay's call site
    (``broker/experiments/replay.py``), so a replayed decision never
    needs this check to tolerate stale wording in the first place.
    """
    if not dynamic_skill_map or len(dynamic_skill_map) <= 1:
        return
    installed_order = [
        dynamic_skill_map[k]
        for k in sorted(dynamic_skill_map, key=lambda x: int(x) if str(x).isdigit() else 0)
    ]

    option_lines = [line for line in (options_text or "").split(chr(10)) if line.strip()]
    if option_lines and all(line in rendered_prompt for line in option_lines):
        return

    def _name_present(sid: str) -> bool:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(sid)}(?![A-Za-z0-9_])"
        return re.search(pattern, rendered_prompt) is not None

    if installed_order and all(_name_present(sid) for sid in installed_order):
        return

    first_missing = next((line for line in option_lines if line not in rendered_prompt), None)
    if first_missing is None:
        first_missing = next((sid for sid in installed_order if not _name_present(sid)), installed_order[0])

    raise RuntimeError(
        f"Options-text parity violation (POST-RENDER) for agent_type={agent_type!r}: "
        f"the FINAL rendered prompt shows neither the expected option lines "
        f"(e.g. {first_missing!r}) nor a safe name-based shape (every skill "
        f"name by word boundary), for a "
        f"dynamic_skill_map installed in order {installed_order}. "
        f"Every earlier check in this module only verifies the un-rendered "
        f"template STRING is shaped safely; this is what the model "
        f"actually received. A legend delivered through another filled "
        f"placeholder ({{system_prompt}}, {{institutional_section}}, or an "
        f"unrecognized template_vars entry) evidently did not carry "
        f"through, or the render pipeline dropped it some other way. "
        f"Digit answers will decode against the wrong skill. If this is a "
        f"replayed decision, pass render_check=False to "
        f"SkillBrokerEngine.process_step instead of relying on this check "
        f"to tolerate a historically-recorded prompt."
    )


class SkillFilterMixin:
    """Mixin providing skill filtering and option injection for LLM prompts."""

    def _get_action_ids(self, agent_type: str) -> List[str]:
        return resolve_registry_ids(self.config, agent_type)

    def _filter_identity_skills(self, agent_type: str, skills: List[str], state: Dict[str, Any]) -> List[str]:
        base_type = self.config.get_base_type(agent_type) if hasattr(self.config, "get_base_type") else agent_type
        blocked = set()
        for rule in self.config.get_identity_rules(base_type):
            pre = rule.metadata.get("precondition")
            if pre and state.get(pre) is True:
                for s in rule.blocked_skills or []:
                    blocked.add(s)
        return [s for s in skills if s not in blocked]

    def _inject_filtered_skills(self, context: Dict[str, Any], agent_type: str) -> None:
        state = context.get("state", {})
        action_ids = self._get_action_ids(agent_type)
        if not action_ids:
            return
        # Respect pre-filtered available_skills from context builder
        # (e.g. a domain removes an already-completed one-way skill).
        # Only keep action_ids that the context builder left in place.
        pre_filtered = context.get("available_skills")
        if pre_filtered:
            pre_ids = {
                (s.get("skill_name") if isinstance(s, dict) else s)
                for s in pre_filtered
            }
            action_ids = [a for a in action_ids if a in pre_ids]
        filtered = self._filter_identity_skills(agent_type, action_ids, state)
        context["available_skills"] = filtered
        self._inject_options_text(context, filtered, agent_type=agent_type)

    def _inject_options_text(
        self, context: Dict[str, Any], skills: List[str], agent_type: str = None,
    ) -> None:
        if not skills:
            return
        # Optionally shuffle option order to mitigate positional bias
        # (controlled by global_config.governance.shuffle_options in YAML)
        shuffle = False
        if self.config:
            try:
                # AgentConfig wraps _config dict; also accept plain dict
                cfg = getattr(self.config, "_config", self.config)
                if isinstance(cfg, dict):
                    shuffle = cfg.get("global_config", {}).get(
                        "governance", {}
                    ).get("shuffle_options", False)
            except (TypeError, AttributeError):
                pass
        if shuffle:
            import random as _rng_mod
            skills = list(skills)  # Don't mutate the original
            # Use a deterministic per-call RNG so results are reproducible
            # but each agent/step gets a different ordering.
            seed_material = f"{context.get('agent_id', '')}_" \
                            f"{context.get('step_id', '')}_" \
                            f"{context.get('year', '')}"
            _rng = _rng_mod.Random(seed_material)
            _rng.shuffle(skills)

        options = []
        dynamic_skill_map = {}
        for i, skill_id in enumerate(skills, 1):
            skill_def = self.skill_registry.get(skill_id) if self.skill_registry else None
            desc = skill_def.description if skill_def else skill_id
            options.append(f"{i}. {desc}")
            dynamic_skill_map[str(i)] = skill_id
        personal = context.setdefault("personal", {})
        if len(skills) > 1:
            valid_choices = ", ".join([str(i) for i in range(1, len(skills))]) + f", or {len(skills)}"
        else:
            valid_choices = "1"
        personal["options_text"] = "\n".join(options)
        personal["valid_choices_text"] = valid_choices
        personal["dynamic_skill_map"] = dynamic_skill_map

        if agent_type is not None:
            self._assert_options_text_parity(agent_type, skills)

    def _resolve_template_for_parity_check(self, agent_type: str) -> Tuple[Optional[str], str]:
        """Return (template_text, template_path_for_message).

        ``template_text`` is the ACTUAL text that will render for this
        agent type — including the correct per-builder-class fallback
        when no custom template is registered (the P0 hole a 2026-09
        review found: a missing lookup used to ``return`` silently
        instead of evaluating what would really be rendered).
        """
        template_path = "<inline or unknown>"
        try:
            base_type = (
                self.config.get_base_type(agent_type)
                if hasattr(self.config, "get_base_type") else agent_type
            )
            cfg_block = self.config.get(base_type) if self.config else {}
            template_path = cfg_block.get("prompt_template_file") or template_path
        except Exception:  # noqa: BLE001 — best-effort message enrichment only
            pass

        cb = getattr(self, "context_builder", None)
        if cb is None:
            return None, template_path
        templates = getattr(cb, "prompt_templates", None)
        if templates is None:
            return None, template_path
        template = templates.get(agent_type)
        if template:
            return template, template_path

        # Lookup missed — evaluate against the REAL fallback this builder
        # class renders, not silence. Import deferred (not at module load)
        # to avoid any import-order coupling between broker.core and
        # broker.components.context. Import the ACTUAL constants (not a
        # hand-typed copy of either string) — a 2026-09 silent-failure
        # hunter finding (NEW-4): a re-typed literal here could silently
        # drift from the real template and exempt against a stale copy.
        from broker.components.context.builder import (
            BaseAgentContextBuilder, TieredContextBuilder,
            DEFAULT_PROMPT_TEMPLATE, TIERED_DEFAULT_PROMPT_TEMPLATE,
        )
        if isinstance(cb, TieredContextBuilder):
            return (
                TIERED_DEFAULT_PROMPT_TEMPLATE,
                f"<no registered template for {agent_type!r} — TieredContextBuilder's built-in default>",
            )
        if isinstance(cb, BaseAgentContextBuilder):
            return (
                DEFAULT_PROMPT_TEMPLATE,
                f"<no registered template for {agent_type!r} — "
                f"BaseAgentContextBuilder.DEFAULT_PROMPT_TEMPLATE ('ACT:{{skills}}')>",
            )
        # Unknown builder class — cannot determine what will actually
        # render. Fail closed: return None so the caller raises rather
        # than guessing.
        return None, (
            f"<no registered template for {agent_type!r}; unrecognized "
            f"context_builder class {type(cb).__name__} — cannot determine "
            f"the real fallback>"
        )

    def _assert_options_text_parity(self, agent_type: str, installed_order: List[str]) -> None:
        """Fail loud when a re-ranked skill menu is invisible to the model.

        Thin wrapper: resolves this instance's registry ids / rendered
        template / decision-field type, then delegates the actual
        comparison to the module-level ``check_options_text_parity`` — the
        single shared choke point also called from
        ``TieredContextBuilder.format_prompt``'s own map-builder (see that
        function's docstring for the full contract and the class of bug
        this closes: ``individual.txt`` used to render ``{skills}`` instead
        of ``{options_text}``, caught on 3 runs, 57-63% mismatch from year
        2 on).

        No bare ``except Exception: return`` anywhere in this path
        (post-review): a lookup failure raises with the agent_type named,
        it does not silently exempt an agent_type this check cannot see.
        """
        try:
            registry_ids = self._get_action_ids(agent_type)
        except Exception as exc:  # noqa: BLE001 — re-raised with context, never swallowed
            raise RuntimeError(
                f"Options-text parity guard cannot verify agent_type={agent_type!r}: "
                f"_get_action_ids raised {exc!r} while a dynamic_skill_map was "
                f"being installed in order {list(installed_order)}. Refusing to "
                f"silently exempt an agent_type this check cannot resolve."
            ) from exc

        template, template_path = self._resolve_template_for_parity_check(agent_type)
        decision_is_numeric = resolve_decision_field_is_numeric_choice(self.config, agent_type)
        check_options_text_parity(
            agent_type=agent_type,
            installed_order=installed_order,
            registry_ids=registry_ids,
            template=template,
            template_path=template_path,
            decision_field_is_numeric_choice=decision_is_numeric,
        )
