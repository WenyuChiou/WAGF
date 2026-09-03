"""Decider registry — WHO decides an agent's action, per agent type.

``SkillBrokerEngine.process_step(llm_invoke=...)`` has always been
decider-agnostic: it hands a prompt to a callable and takes back
whatever that callable produces, then runs the SAME context build,
the SAME parse, the SAME validators, the SAME retry loop and writes
the SAME audit row regardless of what produced the answer. Nothing in
that path requires a language model. What was missing was a way to
SAY so in configuration: until this module, pointing an agent type at
something other than an LLM meant reaching into a live runner and
replacing its invoke function from an example script.

This module turns that seam into a named, registered, config-declared
choice, so a run can hold rule-based agents, hybrid agents and
LLM agents at once and compare them without an asterisk — same
validators, same audit columns, same retry loop.

THE CONTRACT A DECIDER MUST MEET
--------------------------------
A decider is a callable with the signature the retry loop already
calls (``broker/core/_retry_loop.py``)::

    decide(prompt: str, **kwargs) -> raw_output

``raw_output`` may be any of the three shapes the loop already
accepts:

* a ``str`` — parsed by the domain's ``ModelAdapter``, exactly like a
  model reply. This is what ``create_llm_invoke`` returns.
* a :class:`~broker.interfaces.skill_types.SkillProposal` — used as-is,
  skipping the parser. Validation and audit are NOT skipped.
* a ``(str | SkillProposal, LLMStats)`` tuple — the same, plus the
  per-call statistics the audit row records.

The built-in non-LLM deciders return the tuple form with a
``SkillProposal``: a rule table has no text to parse, and fabricating
model-shaped text just so the parser can re-extract the answer would
put a fictional parse layer in the audit trail.

WHAT HAPPENS IF A DECIDER IS DECLARED WRONG
-------------------------------------------
An unregistered name is refused at BOTH ends: ``validate_prompt``
reports it as a BLOCKER at config time, and :meth:`DeciderRegistry.build`
raises at run time. Neither falls back to ``llm``. A silent fallback
would mean a run whose config asked for a rule-based arm quietly
produced an all-LLM one, and nothing in the artifacts would say so —
the arm would simply be the wrong experiment, discovered after the
analysis was written.

THE DEFAULT IS ``llm`` AND IT IS THE SAME OBJECT
------------------------------------------------
When an agent type declares no ``decider:``, the resolved callable is
the very object ``ExperimentRunner.get_llm_invoke(agent_type)``
returns — not a wrapper around it. Wrapping would be invisible in
every test that checks behaviour and still risked a byte difference
in a frozen corpus; identity is checkable, so identity is what the
default guarantees.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# The name an agent type gets when it declares no ``decider:`` key.
DEFAULT_DECIDER_NAME = "llm"

# A decider callable: prompt in, raw output out (see module docstring).
DeciderCallable = Callable[..., Any]

# A factory: (agent_type_config, runtime) -> DeciderCallable.
#
# ``agent_type_config`` is the agent type's own YAML block (the dict
# ``AgentTypeConfig.get(agent_type)`` returns) so a factory can read
# whatever else that type declares. ``runtime`` is what only the
# running experiment knows — see ``DeciderRegistry.build``.
DeciderFactory = Callable[[Dict[str, Any], Dict[str, Any]], DeciderCallable]


# =============================================================================
# The declared choice
# =============================================================================

@dataclass(frozen=True)
class DeciderSpec:
    """One agent type's declared decider: a registered name plus params."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_default(self) -> bool:
        """True when this is the plain ``llm`` default with no params."""
        return self.name == DEFAULT_DECIDER_NAME and not self.params


DEFAULT_DECIDER_SPEC = DeciderSpec(DEFAULT_DECIDER_NAME)


def parse_decider_spec(value: Any, *, where: str = "decider") -> DeciderSpec:
    """Read the ``decider:`` YAML value into a :class:`DeciderSpec`.

    Accepted forms::

        decider: llm                       # a bare name
        decider: {name: rule_based, params: {...}}

    ``None`` / absent gives :data:`DEFAULT_DECIDER_SPEC`. Anything else
    raises ``ValueError`` naming ``where``, because the alternative —
    reading an unusable value as the default — produces an all-LLM run
    from a config that asked for something else.

    ``{name: llm, params: {...}}`` is REFUSED (review C2). ``llm``
    resolves to the agent type's own callable and reads no params at
    all, so params on it are silently dead config. Worse, they used to
    make two definitions of "is this the default" disagree:
    :attr:`DeciderSpec.is_default` said no (params are present), while
    ``AgentTypeConfig.has_non_default_deciders`` said yes (the name is
    ``llm``) — so the audit columns stayed OFF for a run whose
    ``process_step`` call had gained a ``decider=`` keyword. Refusing
    the shape makes the two definitions coincide by construction.
    """
    if value is None:
        return DEFAULT_DECIDER_SPEC
    if isinstance(value, str):
        name = value.strip()
        if not name:
            raise ValueError(f"{where}: empty decider name")
        return DeciderSpec(name)
    if isinstance(value, Mapping):
        name = value.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"{where}: mapping form needs a non-empty 'name' "
                f"(got {value!r}). Write `decider: {{name: rule_based, "
                f"params: {{...}}}}`."
            )
        params = value.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, Mapping):
            raise ValueError(
                f"{where}: 'params' must be a mapping, got "
                f"{type(params).__name__}."
            )
        clean_name = name.strip()
        if clean_name == DEFAULT_DECIDER_NAME and params:
            raise ValueError(
                f"{where}: '{DEFAULT_DECIDER_NAME}' takes no params — it "
                f"resolves to the agent type's own LLM callable and reads "
                f"none of {sorted(params)}. Configure the model under "
                f"`llm_params:`, or name a decider that does take params "
                f"(rule_based / hybrid / parametric)."
            )
        return DeciderSpec(clean_name, dict(params))
    raise ValueError(
        f"{where}: expected a string name or a {{name, params}} mapping, "
        f"got {type(value).__name__} ({value!r})."
    )


# =============================================================================
# Which path produced THIS decision (thread-local, one slot per call)
# =============================================================================
#
# A hybrid decider answers some decisions from its rule table and sends
# the rest to the model, and the audit row has to say which — otherwise
# a hybrid arm reads as one uniform thing in the CSV and the whole
# point of running it is lost. The engine cannot ask the callable
# afterwards: with ``workers > 1`` the same callable serves several
# agents at once, so an attribute on the function would be overwritten
# by whichever thread ran last. A thread-local is written and read on
# the SAME thread inside one ``process_step``, so it cannot cross
# agents.

_CALL_STATE = threading.local()


def note_decider_path(path: str) -> None:
    """Record which path this decider call took (``rule`` / ``llm``)."""
    _CALL_STATE.path = str(path)


def take_decider_path(default: str = "") -> str:
    """Pop the path recorded by the last decider call on this thread.

    Popping (rather than peeking) is deliberate: a stale value left by
    an earlier agent would be attributed to this row, which is exactly
    the kind of quietly-wrong provenance this column exists to prevent.
    """
    path = getattr(_CALL_STATE, "path", None)
    _CALL_STATE.path = None
    return path if path else default


def clear_decider_path() -> None:
    """Clear this thread's recorded path (used by the engine and tests)."""
    _CALL_STATE.path = None


# =============================================================================
# Registry
# =============================================================================

class DeciderRegistry:
    """Name -> factory. Built-ins are registered at import time."""

    _factories: Dict[str, DeciderFactory] = {}
    _builtins: Dict[str, DeciderFactory] = {}
    # name -> the domain label whose pack replaced a BUILT-IN under that
    # name. Read by :meth:`audit_label` so the audit column can say which
    # ``rule_based`` a row came from; see ``_register_pack_deciders``.
    _overridden_builtins: Dict[str, str] = {}

    # -- registration ---------------------------------------------------

    @classmethod
    def register(
        cls,
        name: str,
        factory: DeciderFactory,
        *,
        replace: bool = False,
    ) -> None:
        """Register ``factory`` under ``name``.

        Re-registering an existing name raises unless ``replace=True``.
        Silently replacing would let a domain package shadow a built-in
        on import order alone, so two runs of the same config could use
        different deciders depending on which module happened to load
        first.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("decider name must be a non-empty string")
        key = name.strip()
        if not callable(factory):
            raise TypeError(
                f"decider factory for '{key}' is not callable "
                f"(got {type(factory).__name__})"
            )
        existing = cls._factories.get(key)
        if existing is not None and existing is not factory and not replace:
            raise ValueError(
                f"decider '{key}' is already registered. Pass replace=True "
                f"if you mean to override it, or pick another name — "
                f"registered: {cls.names()}."
            )
        cls._factories[key] = factory

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove ``name`` if present. Built-ins can be removed too (tests)."""
        cls._factories.pop(str(name).strip(), None)

    @classmethod
    def has(cls, name: str) -> bool:
        return str(name).strip() in cls._factories

    @classmethod
    def names(cls) -> List[str]:
        return sorted(cls._factories)

    @classmethod
    def get(cls, name: str) -> DeciderFactory:
        key = str(name).strip()
        try:
            return cls._factories[key]
        except KeyError:
            raise KeyError(
                f"no decider registered under '{key}'. Registered: "
                f"{cls.names()}. Domains ship their own via the DomainPack "
                f"hook `decider_factories()`; nothing falls back to "
                f"'{DEFAULT_DECIDER_NAME}'."
            ) from None

    @classmethod
    def is_builtin(cls, name: str) -> bool:
        return str(name).strip() in cls._builtins

    @classmethod
    def note_builtin_override(cls, name: str, domain: str) -> None:
        """Record that ``domain``'s pack replaced the built-in ``name``."""
        cls._overridden_builtins[str(name).strip()] = str(domain)

    @classmethod
    def audit_label(cls, name: str) -> str:
        """What the ``decider`` audit column should read for ``name``.

        Normally the name itself. When a domain has deliberately replaced
        a BUILT-IN under that name, ``<name>@<domain>`` — because the two
        are different code answering to one word, and a CSV that calls
        both ``rule_based`` cannot be read afterwards.
        """
        key = str(name).strip()
        domain = cls._overridden_builtins.get(key)
        return f"{key}@{domain}" if domain else key

    @classmethod
    def reset_to_builtins(cls) -> None:
        """Drop every domain registration. For test teardown."""
        cls._factories = dict(cls._builtins)
        cls._overridden_builtins = {}

    # -- resolution -----------------------------------------------------

    @classmethod
    def build(
        cls,
        spec: DeciderSpec,
        agent_type_config: Optional[Dict[str, Any]] = None,
        runtime: Optional[Dict[str, Any]] = None,
        factory: Optional[DeciderFactory] = None,
    ) -> DeciderCallable:
        """Build the callable for ``spec``.

        ``factory`` short-circuits the registry lookup for a caller that
        already resolved it — ``ExperimentRunner`` caches the factory per
        agent type and rebinds per step, and having it re-do the lookup
        (and the domain-pack sweep behind it) once per agent per step was
        pure repetition. Passing it changes nothing else about the build.

        ``runtime`` carries what only the running experiment knows:

        ============  ====================================================
        ``llm_invoke``  the agent type's LLM callable — the ``llm``
                        decider returns it unchanged, and ``hybrid``
                        falls through to it
        ``agent``       the agent object being decided for (rule tables
                        read its state)
        ``agent_id``    the agent's id
        ``agent_type``  the agent type name
        ``env``         this period's environment dict
        ``seed``        the run seed, for deciders that sample
        ============  ====================================================
        """
        factory = factory if factory is not None else cls.get(spec.name)
        params = dict(spec.params)
        rt = dict(runtime or {})
        rt["decider_name"] = spec.name
        rt["decider_params"] = params
        fn = factory(dict(agent_type_config or {}), rt)
        if not callable(fn):
            raise TypeError(
                f"decider factory '{spec.name}' returned "
                f"{type(fn).__name__}, not a callable. A factory must "
                f"return the decide(prompt) function itself, not its result."
            )
        return fn


def _unpack_factory_entry(name: str, entry: Any, *, label: str):
    """Read one ``decider_factories()`` value into ``(factory, override)``.

    Two accepted shapes::

        {"my_decider": factory}                              # the usual one
        {"rule_based": {"factory": fn, "override_builtins": True}}

    The second exists only so replacing a BUILT-IN is something a pack
    author has to write down (review P1-d). It is not a convenience.
    """
    if isinstance(entry, Mapping):
        factory = entry.get("factory")
        override = bool(entry.get("override_builtins", False))
        if not callable(factory):
            raise TypeError(
                f"decider '{name}' offered by domain '{label}' uses the "
                f"mapping form but its 'factory' is "
                f"{type(factory).__name__}, not a callable."
            )
        return factory, override
    return entry, False


def _register_pack_deciders(
    pack: Any, label: str, *, replace: bool,
) -> List[str]:
    hook = getattr(pack, "decider_factories", None)
    if not callable(hook):
        return []
    try:
        factories = hook() or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[Decider] %s.decider_factories() raised %s: %r — no deciders "
            "registered for '%s'.",
            type(pack).__name__, type(exc).__name__, exc, label,
        )
        return []
    registered: List[str] = []
    for name, entry in dict(factories).items():
        factory, override_builtins = _unpack_factory_entry(
            name, entry, label=label)
        if DeciderRegistry.is_builtin(name):
            # P1-d: `replace=True` is set for the domain the CONFIG named,
            # so before this guard a pack could shadow `rule_based` for
            # every config in the process just by being the named domain.
            # Two runs of the same YAML would then mean different things
            # depending on which module imported first, and the audit CSV
            # would call both of them `rule_based`.
            if not override_builtins:
                raise ValueError(
                    f"domain '{label}' offers a decider named '{name}', "
                    f"which is a BUILT-IN. Replacing it would silently "
                    f"change what every config in this process means by "
                    f"'{name}'. Pick another name, or — if replacing it "
                    f"is genuinely the intent — declare it: "
                    f"`{{'{name}': {{'factory': fn, "
                    f"'override_builtins': True}}}}`. Built-ins: "
                    f"{sorted(DeciderRegistry._builtins)}."
                )
            logger.warning(
                "[Decider] domain '%s' REPLACES the built-in '%s'. Audit "
                "rows produced by it read '%s@%s', not '%s', so a CSV "
                "cannot conflate the two.",
                label, name, name, label, name,
            )
            DeciderRegistry.register(name, factory, replace=True)
            DeciderRegistry.note_builtin_override(name, label)
            registered.append(name)
            continue
        if not replace and DeciderRegistry.has(name):
            logger.debug(
                "[Decider] '%s' already registered; the copy offered by "
                "domain '%s' is ignored.", name, label,
            )
            continue
        DeciderRegistry.register(name, factory, replace=replace)
        registered.append(name)
    return registered


def register_domain_deciders(domain: Optional[str]) -> List[str]:
    """Register the deciders DomainPacks ship, via ``decider_factories()``.

    With a ``domain`` name, that pack's factories are registered and
    take precedence — the config named the domain, so the config gets
    what it asked for.

    With ``None``, every pack currently in
    :class:`~broker.domains.registry.DomainPackRegistry` is swept, and
    a name already registered is left alone. Sweeping matters because
    ``global_config.governance.domain`` is optional and several shipped
    configs omit it while their runner still imports the example
    package: without the sweep, a decider the domain does ship would be
    reported as unregistered, and the run would die on a name that is
    sitting right there in the registry.

    Idempotent, so calling it once per decider resolution is cheap.
    Returns the names registered (for logging and tests).
    """
    try:  # lazy: broker.domains imports broker.agents indirectly
        from broker.domains.registry import DomainPackRegistry
    except Exception as exc:  # noqa: BLE001 — never break a run over this
        logger.debug("[Decider] DomainPackRegistry unavailable: %s", exc)
        return []
    if domain:
        pack = DomainPackRegistry.get(domain)
        if pack is None:
            return []
        return _register_pack_deciders(pack, domain, replace=True)
    registered: List[str] = []
    for name in DomainPackRegistry.domains():
        pack = DomainPackRegistry.get(name)
        if pack is not None:
            registered.extend(_register_pack_deciders(pack, name, replace=False))
    return registered


# =============================================================================
# Decision context: what a non-LLM decider reads instead of a prompt
# =============================================================================

_MISSING = object()

# Which plane a rule field is read from. Mirrors PR-6's world-variable
# ``scope:`` on thinking-rule conditions, deliberately: a model builder
# who has learned one should not have to learn a second vocabulary.
RULE_FIELD_SCOPES = frozenset({"auto", "agent", "env"})
DEFAULT_RULE_FIELD_SCOPE = "auto"

# The three dicts an agent hangs its state on, in the order
# ``InteractionHub.build_tiered_context`` composes them. The middle one is
# where a domain loader puts an agent's PROFILE — the demographic and
# asset fields read from CSV, which is most of what a behavioural rule is
# written about — and leaving it out of this tuple was review finding
# P0-A: every rule naming a profile field was permanently false, so the
# first shipped rule-based arm answered every row with its default action.
_AGENT_STATE_HOLDERS = ("custom_attributes", "fixed_attributes", "dynamic_state")


class DecisionContext:
    """Field lookup over one agent plus the period's environment.

    Resolution order for ``scope: auto`` (the default), first hit wins:

    1. identity — ``agent_id`` and ``agent_type``, so a rule can name a
       specific subset of agents (``agent_id: {in: [...]}``) without the
       domain having to invent a marker attribute for it
    2. the environment dict for this period
    3. the agent's ``custom_attributes`` / ``fixed_attributes`` /
       ``dynamic_state`` (profile fields and the values skills mutate)
    4. the agent's raw state params
    5. a plain attribute on the agent (``agent.tenure`` and friends)

    **The environment comes before the agent** (review P2). It did not,
    and the first shipped rule showed why: an institutional agent kept
    its own copy of a world variable, refreshed only AFTER the decision,
    so an agent-first lookup answered a rule about this period with last
    period's value — zero, in period one — while the environment the
    same step published the live one, and the rule never fired. A stale
    agent copy of a world variable is the common case; a per-agent value
    that genuinely shadows a world one is the rare one, and it now has
    to say so:

    ``scope: agent`` searches the agent only — for a per-agent value
    that shares a name with a region-wide one (an agent's own exposure
    against the aggregate figure). ``scope: env`` searches the
    environment only, so a rule about a world variable cannot be
    answered by an agent's stale copy of it.
    """

    def __init__(
        self,
        agent: Any = None,
        env: Optional[Mapping[str, Any]] = None,
        agent_id: Optional[str] = None,
        agent_type: Optional[str] = None,
    ):
        self.agent = agent
        self.env = dict(env or {})
        self.identity: Dict[str, Any] = {}
        if agent_id is not None:
            self.identity["agent_id"] = agent_id
        if agent_type is not None:
            self.identity["agent_type"] = agent_type

    def _resolve_agent(self, field_name: str) -> Any:
        agent = self.agent
        if agent is None:
            return _MISSING
        for holder_name in _AGENT_STATE_HOLDERS:
            holder = getattr(agent, holder_name, None)
            if isinstance(holder, Mapping) and field_name in holder:
                return holder[field_name]
        getter = getattr(agent, "get_all_state_raw", None)
        if callable(getter):
            try:
                raw = getter()
            except Exception:  # noqa: BLE001
                raw = None
            if isinstance(raw, Mapping) and field_name in raw:
                return raw[field_name]
        sentinel = object()
        value = getattr(agent, field_name, sentinel)
        return _MISSING if value is sentinel else value

    def resolve(self, field_name: str, scope: str = DEFAULT_RULE_FIELD_SCOPE) -> Any:
        """Return the field's value, or ``_MISSING`` if the scope has none.

        A ``NaN`` — a blank cell in a per-agent CSV column, most often —
        resolves to ``_MISSING`` too, not to itself (review P1, paired
        with a domain decider's own NaN guard). Left unguarded, a
        ``not_in`` condition is trivially SATISFIED by NaN: nothing
        equals NaN, so ``NaN not in [SOME_VALUE]`` evaluates True, and a
        blank zone-code cell would read as "definitely not that zone" —
        the opposite of "this field could not be read". Coercing it to
        ``_MISSING`` here routes it through the SAME unresolved-field
        reporting an absent field already gets (`_note_unresolved_field`,
        below) instead of letting it silently satisfy a negative rule.
        """
        key = str(scope or DEFAULT_RULE_FIELD_SCOPE).strip().lower()
        if key not in RULE_FIELD_SCOPES:
            # Unreachable through YAML: build_rule_table refuses an
            # unknown scope rather than coercing it, precisely so a typo
            # cannot read a different plane than the one it names.
            raise ValueError(
                f"rule field '{field_name}': unknown scope {scope!r}. "
                f"Supported: {sorted(RULE_FIELD_SCOPES)}."
            )
        if key != "env" and field_name in self.identity:
            value = self.identity[field_name]
        elif key != "agent" and field_name in self.env:
            value = self.env[field_name]
        elif key != "env":
            value = self._resolve_agent(field_name)
        else:
            value = _MISSING
        if isinstance(value, float) and math.isnan(value):
            return _MISSING
        return value

    def as_dict(self, fields: Sequence[str]) -> Dict[str, Any]:
        """Resolve a named set of fields, omitting the ones nothing has."""
        out: Dict[str, Any] = {}
        for name in fields:
            value = self.resolve(name)
            if value is not _MISSING:
                out[name] = value
        return out


# =============================================================================
# Rule table
# =============================================================================

_COMPARISONS: Dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}

_MEMBERSHIPS = {"in", "not_in"}

SUPPORTED_RULE_OPERATORS = tuple(sorted(set(_COMPARISONS) | _MEMBERSHIPS))


# (agent_type, field) pairs already reported. A rule field that resolves
# to nothing is reported ONCE — it is a property of the config, not of
# the row, and 400 agents x 13 years of the same line is a log nobody
# reads. The COUNT still goes to run_integrity, per row.
#
# `_note_unresolved_field` runs per audit row, and audit rows are built
# concurrently when a run sets `workers > 1` — the same rationale as
# `_UNCATEGORISED_LOCK` in broker/validators/governance/__init__.py, this
# module's sibling for the paired "no breakdown bucket" census (review
# P3). Without a lock, `key not in _WARNED_UNRESOLVED_FIELD` and the
# `.add()` that follows it are two separate operations: two threads can
# both see "not yet warned" before either records it, so the "reported
# ONCE" promise above is not guaranteed by the code as written. The
# per-row COUNT is unaffected either way — `note_rule_field_unresolved`
# is independently lock-protected inside run_integrity.py — this lock
# only protects the warn-once memo from a duplicate log line.
_WARNED_UNRESOLVED_FIELD_LOCK = threading.Lock()
_WARNED_UNRESOLVED_FIELD: set = set()


def _note_unresolved_field(agent_type: str, field_name: str, where: str) -> None:
    """Report + count a rule field nothing in scope carries (review P1-a).

    Silence here was the failure: an unresolvable field makes its rule
    never fire, which is indistinguishable in every artifact from a rule
    that was evaluated and did not match. A whole arm can be a constant
    and the CSV looks entirely normal.
    """
    key = (str(agent_type or "?"), str(field_name))
    with _WARNED_UNRESOLVED_FIELD_LOCK:
        first_report = key not in _WARNED_UNRESOLVED_FIELD
        if first_report:
            _WARNED_UNRESOLVED_FIELD.add(key)
    if first_report:
        logger.warning(
            "[Decider] %s: field '%s' resolves to nothing for agent type "
            "'%s' — neither the environment nor the agent's "
            "custom_attributes / fixed_attributes / dynamic_state / state "
            "params / attributes carry it, so this condition NEVER holds "
            "and the rule cannot fire. Counted per row in "
            "run_integrity.json -> rule_field_unresolved.",
            where, field_name, key[0],
        )
    try:
        from broker.core.run_integrity import note_rule_field_unresolved

        note_rule_field_unresolved(key[0], key[1])
    except Exception as exc:  # noqa: BLE001 — side-artifact census only
        logger.debug("[Decider] unresolved-field census skipped: %s", exc)


def reset_unresolved_field_warnings() -> None:
    """Clear the warn-once memo. For tests and for a second run in-process."""
    with _WARNED_UNRESOLVED_FIELD_LOCK:
        _WARNED_UNRESOLVED_FIELD.clear()


def _match_one(observed: Any, expected: Any, *, where: str) -> bool:
    """Does ``observed`` satisfy one field condition?"""
    if observed is _MISSING:
        # A field the agent does not carry cannot satisfy a condition
        # about it. Treating absence as a match would make a rule fire
        # on every agent of a type that never had the field at all.
        # The CALLER reports it — see DecisionRule.matches.
        return False
    if isinstance(expected, Mapping):
        for op, operand in expected.items():
            key = str(op).strip().lower()
            if key in _COMPARISONS:
                try:
                    if not _COMPARISONS[key](observed, operand):
                        return False
                except TypeError:
                    # e.g. "HIGH" >= 2. A rule that cannot be evaluated
                    # does not fire, and says why once.
                    logger.warning(
                        "[Decider] %s: cannot compare %r %s %r — condition "
                        "treated as not matching.", where, observed, key, operand,
                    )
                    return False
            elif key == "in":
                if observed not in (operand or []):
                    return False
            elif key == "not_in":
                if observed in (operand or []):
                    return False
            else:
                raise ValueError(
                    f"{where}: unknown operator '{op}'. Supported: "
                    f"{list(SUPPORTED_RULE_OPERATORS)}."
                )
        return True
    if isinstance(expected, (list, tuple, set)):
        return observed in expected
    return observed == expected


@dataclass
class DecisionRule:
    """One row of a rule table: a set of conditions and the action."""

    action: str
    when: Dict[str, Any] = field(default_factory=dict)
    rule_id: str = ""
    reasoning: Dict[str, Any] = field(default_factory=dict)
    # field name -> "auto" | "agent" | "env"; absent means "auto".
    scopes: Dict[str, str] = field(default_factory=dict)

    def matches(self, ctx: DecisionContext) -> bool:
        where = f"rule '{self.rule_id or self.action}'"
        agent_type = str(ctx.identity.get("agent_type") or "?")
        for field_name, expected in self.when.items():
            scope = self.scopes.get(field_name, DEFAULT_RULE_FIELD_SCOPE)
            observed = ctx.resolve(field_name, scope)
            if observed is _MISSING:
                _note_unresolved_field(agent_type, field_name, where)
                return False
            if not _match_one(observed, expected, where=where):
                return False
        return True


def build_rule_table(params: Mapping[str, Any], *, where: str) -> List[DecisionRule]:
    """Read ``params['rules']`` into an ordered list of :class:`DecisionRule`.

    Order is significant: the FIRST matching rule wins, so a table is
    read the way a person reads it top to bottom. A rule with no
    ``when:`` matches everything and is the table's own catch-all.

    A condition mapping may carry ``scope:`` alongside its operators
    (``{gte: 1.2, scope: env}``); it names which plane the field is read
    from and is NOT an operator. An unrecognised scope raises here
    rather than being coerced, because a coerced scope reads a plane the
    config did not name and keeps looking like it works.
    """
    raw_rules = params.get("rules")
    if raw_rules is None:
        raise ValueError(
            f"{where}: no 'rules' declared. A rule-based decider with no "
            f"rules would answer every decision with its default action, "
            f"which is a constant, not a model."
        )
    if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes)):
        raise ValueError(
            f"{where}: 'rules' must be a list, got {type(raw_rules).__name__}."
        )
    table: List[DecisionRule] = []
    for index, entry in enumerate(raw_rules):
        loc = f"{where}.rules[{index}]"
        if not isinstance(entry, Mapping):
            raise ValueError(f"{loc}: expected a mapping, got {type(entry).__name__}.")
        action = entry.get("action")
        if not isinstance(action, str) or not action.strip():
            raise ValueError(f"{loc}: needs a non-empty 'action' (a skill id).")
        when = entry.get("when", {}) or {}
        if not isinstance(when, Mapping):
            raise ValueError(f"{loc}: 'when' must be a mapping, got {type(when).__name__}.")
        reasoning = entry.get("reasoning", {}) or {}
        if not isinstance(reasoning, Mapping):
            raise ValueError(
                f"{loc}: 'reasoning' must be a mapping of construct labels, "
                f"got {type(reasoning).__name__}."
            )
        conditions: Dict[str, Any] = {}
        scopes: Dict[str, str] = {}
        for field_name, expected in dict(when).items():
            if isinstance(expected, Mapping) and "scope" in expected:
                raw_scope = expected.get("scope")
                scope = str(raw_scope or "").strip().lower()
                if scope not in RULE_FIELD_SCOPES:
                    raise ValueError(
                        f"{loc}: field '{field_name}' declares scope "
                        f"{raw_scope!r}, which is not one of "
                        f"{sorted(RULE_FIELD_SCOPES)}. 'env' reads only the "
                        f"period's environment, 'agent' only the agent, "
                        f"'auto' the environment then the agent."
                    )
                scopes[str(field_name)] = scope
                expected = {k: v for k, v in expected.items() if k != "scope"}
                if not expected:
                    raise ValueError(
                        f"{loc}: field '{field_name}' declares only a scope "
                        f"and no condition, so it can neither hold nor fail. "
                        f"Add an operator, or drop the field."
                    )
            conditions[str(field_name)] = expected
        table.append(DecisionRule(
            action=action.strip(),
            when=conditions,
            rule_id=str(entry.get("id", "") or f"rule_{index}"),
            reasoning={str(k): v for k, v in reasoning.items()},
            scopes=scopes,
        ))
    return table


# =============================================================================
# Building the thing a decider hands back
# =============================================================================

def make_proposal(
    *,
    skill_name: str,
    agent_id: str,
    agent_type: str,
    decider: str,
    path: str,
    rule_id: str = "",
    reasoning: Optional[Mapping[str, Any]] = None,
    payload_extra: Optional[Mapping[str, Any]] = None,
) -> Tuple[Any, Any]:
    """Package a decided action as ``(SkillProposal, LLMStats)``.

    ``raw_output`` is a small JSON object rather than an empty string:
    the audit CSV's ``raw_output`` column is where a reader looks to
    see what the agent produced, and for a rule-based row the honest
    answer is the rule that fired, not a blank.

    The ``LLMStats`` records zero retries and success — no call was
    made, so nothing failed. What DID happen is in the ``decider``
    column; see ``docs/guides/mixed_populations.md`` for how to read
    the LLM columns on a row no model produced.
    """
    from broker.interfaces.skill_types import SkillProposal
    from broker.utils.llm_utils import LLMStats

    payload: Dict[str, Any] = {
        "decision": skill_name,
        "decider": decider,
        "path": path,
    }
    if rule_id:
        payload["rule"] = rule_id
    # `payload_extra` is how a decider says something about THIS decision
    # that a reader of the CSV needs and no column carries — the fields it
    # had to fall back to a default for, above all. raw_output is the one
    # column a reader already opens to see what the agent produced.
    for key, value in dict(payload_extra or {}).items():
        payload[str(key)] = value
    proposal = SkillProposal(
        skill_name=skill_name,
        agent_id=agent_id,
        reasoning={str(k): v for k, v in (reasoning or {}).items()},
        agent_type=agent_type,
        confidence=1.0,
        raw_output=json.dumps(payload, sort_keys=True),
        parse_layer=f"decider:{decider}",
        parse_confidence=1.0,
        construct_completeness=0.0,
    )
    return proposal, LLMStats(retries=0, success=True)


# =============================================================================
# Built-in deciders
# =============================================================================

# The path a rule table reports when NO rule matched and it fell back to
# its declared `default_action`. A documented enum value of its own,
# separate from "rule": a table that answers every decision with its
# default is a constant wearing a rule table's name, and "rule" hides
# that in the one column a reader would check.
RULE_DEFAULT_PATH = "rule_default"


def _note_rule_firing(agent_type: str, rule_id: str) -> None:
    """Count one firing of one rule id. Never raises (side artifact only)."""
    try:
        from broker.core.run_integrity import note_rule_firing

        note_rule_firing(agent_type, rule_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[Decider] rule-firing census skipped: %s", exc)


def _require_llm_invoke(runtime: Mapping[str, Any], *, name: str) -> DeciderCallable:
    fn = runtime.get("llm_invoke")
    if not callable(fn):
        raise ValueError(
            f"decider '{name}' needs an LLM callable in runtime['llm_invoke'] "
            f"and did not get one. ExperimentRunner supplies it; a direct "
            f"caller of DeciderRegistry.build must too."
        )
    return fn


def llm_decider_factory(
    agent_type_config: Dict[str, Any],
    runtime: Dict[str, Any],
) -> DeciderCallable:
    """The default. Returns the agent type's LLM callable UNCHANGED.

    Not a wrapper: ``get_decider`` on an all-default config must return
    the identical object ``get_llm_invoke`` returns, so that a frozen
    corpus cannot drift on the introduction of this registry.
    """
    return _require_llm_invoke(runtime, name=DEFAULT_DECIDER_NAME)


def _rule_decider_preamble(
    runtime: Dict[str, Any],
    where: str,
    *,
    need_rules: bool = True,
) -> Tuple[Dict[str, Any], str, str, Optional[List[DecisionRule]],
           Dict[str, Any], Any, str, DecisionContext]:
    """The setup ``rule_based``, ``hybrid`` and ``parametric`` all repeat
    (review suggestion, code-reviewer): read ``decider_params``, resolve
    ``agent_type`` and fold it into ``where``, read the agent and its id,
    and build the :class:`DecisionContext` all three evaluate against.

    ``rule_based`` and ``hybrid`` also need the rule table and the
    declared ``reasoning`` default — pass ``need_rules=True`` (the
    default) for those. ``parametric`` has no rule table: its own
    ``params`` schema does not declare ``rules`` at all, and calling
    :func:`build_rule_table` on it would raise "no 'rules' declared" for
    a decider that was never supposed to have one. It passes
    ``need_rules=False`` and gets ``table=None`` / ``default_reasoning={}``
    back instead of the two rule-table steps.

    ``where`` in is the decider's bare label (``"decider rule_based"``);
    ``where`` out has the resolved ``agent_type`` folded in
    (``"decider rule_based [household_owner]"``), matching exactly what
    every error message downstream already read before this helper
    existed — a no-behaviour-change refactor, not a new naming scheme.

    Returns ``(params, agent_type, where, table, default_reasoning,
    agent, agent_id, ctx)``.
    """
    params = dict(runtime.get("decider_params") or {})
    agent_type = str(runtime.get("agent_type") or "default")
    where = f"{where} [{agent_type}]"
    table: Optional[List[DecisionRule]] = None
    default_reasoning: Dict[str, Any] = {}
    if need_rules:
        table = build_rule_table(params, where=where)
        default_reasoning = dict(params.get("reasoning") or {})
    agent = runtime.get("agent")
    agent_id = str(runtime.get("agent_id") or getattr(agent, "id", "unknown"))
    ctx = DecisionContext(agent, runtime.get("env"), agent_id, agent_type)
    return params, agent_type, where, table, default_reasoning, agent, agent_id, ctx


def rule_based_decider_factory(
    agent_type_config: Dict[str, Any],
    runtime: Dict[str, Any],
) -> DeciderCallable:
    """A deterministic decider that maps a rule table over the context.

    Domain-neutral by construction: every field name, comparison and
    action id comes from the caller's table, so the same code serves a
    clinic deciding whether to restock and a driver deciding whether to
    reroute.
    """
    (params, agent_type, where, table, default_reasoning, agent, agent_id,
     ctx) = _rule_decider_preamble(runtime, "decider rule_based")
    default_action = params.get("default_action")
    if not isinstance(default_action, str) or not default_action.strip():
        raise ValueError(
            f"{where}: needs a 'default_action' — the skill to propose when "
            f"no rule matches. Without one an unmatched agent has no action "
            f"to propose and the step aborts, silently shrinking the row "
            f"count for this arm."
        )
    default_action = default_action.strip()

    def decide(prompt: str = "", **_kwargs: Any) -> Tuple[Any, Any]:
        for rule in table:
            if rule.matches(ctx):
                note_decider_path("rule")
                _note_rule_firing(agent_type, rule.rule_id)
                return make_proposal(
                    skill_name=rule.action,
                    agent_id=agent_id,
                    agent_type=agent_type,
                    decider="rule_based",
                    path="rule",
                    rule_id=rule.rule_id,
                    reasoning={**default_reasoning, **rule.reasoning},
                )
        # P1-a: a default_action firing is NOT a rule firing, and saying
        # "rule" for both hid the case this distinction exists to catch —
        # a table whose every field was unresolvable answers every row
        # with its default and reads, in the CSV, exactly like a table
        # that was evaluated and did not match.
        note_decider_path(RULE_DEFAULT_PATH)
        _note_rule_firing(agent_type, RULE_DEFAULT_PATH)
        return make_proposal(
            skill_name=default_action,
            agent_id=agent_id,
            agent_type=agent_type,
            decider="rule_based",
            path=RULE_DEFAULT_PATH,
            rule_id="default_action",
            reasoning=default_reasoning,
        )

    return decide


def hybrid_decider_factory(
    agent_type_config: Dict[str, Any],
    runtime: Dict[str, Any],
) -> DeciderCallable:
    """Rule table first; whatever it has no rule for goes to the model.

    The point of the arrangement is that the routine cases are handled
    by something auditable and free, and the model is spent on the
    cases nobody wrote a rule for. Which of the two answered is
    recorded per row in ``decider_path`` — without it a hybrid arm is
    indistinguishable in the CSV from either pure arm.
    """
    (params, agent_type, where, table, default_reasoning, agent, agent_id,
     ctx) = _rule_decider_preamble(runtime, "decider hybrid")
    if params.get("default_action"):
        raise ValueError(
            f"{where}: 'default_action' is meaningless for a hybrid decider — "
            f"the model IS the fallback. Remove it, or use 'rule_based' if "
            f"you want a constant instead of a model call."
        )
    llm_invoke = _require_llm_invoke(runtime, name="hybrid")

    def decide(prompt: str = "", **kwargs: Any) -> Any:
        for rule in table:
            if rule.matches(ctx):
                note_decider_path("rule")
                _note_rule_firing(agent_type, rule.rule_id)
                return make_proposal(
                    skill_name=rule.action,
                    agent_id=agent_id,
                    agent_type=agent_type,
                    decider="hybrid",
                    path="rule",
                    rule_id=rule.rule_id,
                    reasoning={**default_reasoning, **rule.reasoning},
                )
        note_decider_path("llm")
        return llm_invoke(prompt, **kwargs) if kwargs else llm_invoke(prompt)

    return decide


def parametric_decider_factory(
    agent_type_config: Dict[str, Any],
    runtime: Dict[str, Any],
) -> DeciderCallable:
    """Adapt a domain's own deterministic decision object to this seam.

    A calibrated behavioural model — a logistic adoption surface, a
    threshold rule fitted to survey data, a discrete-choice utility —
    is domain code and belongs in the domain's example package, not in
    ``broker/``. This built-in is the adapter: name the object in
    config and it runs through the same governance and audit as every
    LLM agent beside it.

    ::

        decider:
          name: parametric
          params:
            target: examples.my_domain.decider:AdoptionCurveDecider
            init: {seed: 42}           # constructor kwargs, optional
            method: decide             # default "decide"
            fields: [tenure, exposure] # context fields to pass, optional

    The named object may be a class (constructed once per resolution
    with ``init``) or a plain callable. It is invoked as
    ``obj.decide(agent=..., env=..., context=..., agent_id=...,
    agent_type=...)`` and may return either a skill id (``str``), a
    ``SkillProposal``, or a ``(skill_id, reasoning_dict)`` pair.
    """
    (params, agent_type, where, _table, _default_reasoning, agent, agent_id,
     ctx) = _rule_decider_preamble(runtime, "decider parametric", need_rules=False)
    target = params.get("target")
    if not isinstance(target, str) or ":" not in target:
        raise ValueError(
            f"{where}: needs `target: <module.path>:<attribute>` naming the "
            f"domain object that decides. Got {target!r}."
        )
    module_path, _, attr = target.partition(":")
    import importlib

    module = importlib.import_module(module_path.strip())
    try:
        obj = getattr(module, attr.strip())
    except AttributeError:
        raise ValueError(
            f"{where}: module '{module_path}' has no attribute '{attr}'."
        ) from None
    init = dict(params.get("init") or {})
    if isinstance(obj, type):
        obj = obj(**init)
    elif init:
        raise ValueError(
            f"{where}: 'init' was given but target '{target}' is not a class, "
            f"so there is no constructor to pass it to."
        )
    method_name = str(params.get("method") or "decide")
    decide_fn = getattr(obj, method_name, None) if not callable(obj) else (
        getattr(obj, method_name, obj)
    )
    if not callable(decide_fn):
        raise ValueError(
            f"{where}: '{target}' has no callable '{method_name}'."
        )
    fields = list(params.get("fields") or [])
    env = runtime.get("env")

    def decide(prompt: str = "", **_kwargs: Any) -> Any:
        note_decider_path("parametric")
        result = decide_fn(
            agent=agent,
            env=env,
            context=ctx.as_dict(fields) if fields else {},
            agent_id=agent_id,
            agent_type=agent_type,
        )
        reasoning: Dict[str, Any] = {}
        if isinstance(result, tuple) and len(result) == 2:
            result, reasoning = result[0], dict(result[1] or {})
        if isinstance(result, str):
            return make_proposal(
                skill_name=result,
                agent_id=agent_id,
                agent_type=agent_type,
                decider="parametric",
                path="parametric",
                rule_id="",
                reasoning=reasoning,
            )
        # A SkillProposal (or anything else) is passed through untouched —
        # the retry loop already knows both shapes.
        return result

    return decide


_BUILTIN_FACTORIES: Dict[str, DeciderFactory] = {
    DEFAULT_DECIDER_NAME: llm_decider_factory,
    "rule_based": rule_based_decider_factory,
    "hybrid": hybrid_decider_factory,
    "parametric": parametric_decider_factory,
}

# The path each built-in reports when it does not record one itself.
BUILTIN_DEFAULT_PATHS: Dict[str, str] = {
    DEFAULT_DECIDER_NAME: "llm",
    "rule_based": "rule",
    "hybrid": "llm",
    "parametric": "parametric",
}

DeciderRegistry._builtins = dict(_BUILTIN_FACTORIES)
DeciderRegistry._factories = dict(_BUILTIN_FACTORIES)


__all__ = [
    "DEFAULT_DECIDER_NAME",
    "DEFAULT_DECIDER_SPEC",
    "DEFAULT_RULE_FIELD_SCOPE",
    "BUILTIN_DEFAULT_PATHS",
    "RULE_DEFAULT_PATH",
    "RULE_FIELD_SCOPES",
    "SUPPORTED_RULE_OPERATORS",
    "DeciderCallable",
    "DeciderFactory",
    "DeciderSpec",
    "DeciderRegistry",
    "DecisionContext",
    "DecisionRule",
    "build_rule_table",
    "clear_decider_path",
    "make_proposal",
    "note_decider_path",
    "parse_decider_spec",
    "register_domain_deciders",
    "reset_unresolved_field_warnings",
    "take_decider_path",
]
