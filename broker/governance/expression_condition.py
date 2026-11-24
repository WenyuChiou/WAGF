"""One shared implementation of the ``expression:`` rule condition.

A governance rule condition written as a free arithmetic/comparison string over
world variables and the proposed number::

    thinking_rules:
      - id: flood_control_overflow
        conditions:
          - expression: "storage_now > 0.9 * capacity and proposed_magnitude < 100"
            scope: auto          # optional: auto | env | state | social | context
        blocked_skills: [set_release]
        level: ERROR

Three condition evaluators call this module, so they cannot disagree:
``AgentValidator._run_rule_set`` (the production path),
``ThinkingValidator._evaluate_conditions`` and ``RuleCondition.evaluate``.

Rules this module enforces
--------------------------
* Build time (``compile_expression_condition``): the string must parse, use only
  the ``SafeExpressionEvaluator`` whitelist (numbers, names, ``+ - * / // %``,
  comparisons, ``and``/``or``), contain at least one variable name, and have a
  comparison or ``and``/``or`` of comparisons at the top, so the answer is always
  true/false. A bad condition raises ``ExpressionConditionError``.
* Run time (``evaluate_expression_condition``): every name is looked up with
  ``lookup_world_variable``. A name that is absent is *missing*; a value that is
  not a finite number (None, a list, "abc", NaN, inf) is *unusable*. Either one
  means the rule does not fire and the outcome says which (``readable=False``).
  No value is ever assumed.
* A zero divisor is NOT guarded: it raises ``ExpressionEvaluationError`` and the
  run stops with the expression and the values named. The guard is yours to
  write, and ``and`` / ``or`` really short-circuit::

      capacity > 0 and storage_now / capacity > 0.9

  with ``capacity`` equal to 0 never divides.
"""
from __future__ import annotations

import ast
import math
import reprlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple


class _Missing:
    """Sentinel type: a world variable that is not present anywhere searched.

    A plain ``None`` cannot be the sentinel: a domain may legitimately store
    ``None`` in state, and treating that as "absent" would make a rule silently
    not fire on exactly the rows where the world state is unknown.
    """

    _instance: Optional["_Missing"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()


class ExpressionConditionError(ValueError):
    """The condition itself is bad (config / build time)."""


class ExpressionEvaluationError(ValueError):
    """The condition could not be evaluated on these values (run time)."""


def lookup_world_variable(name, scope, state, full_context):
    """Resolve a world variable, returning ``MISSING`` when it is not present.

    Lookup order for ``scope: auto`` is env_state -> agent state -> flattened
    context, and it is DOCUMENTED rather than incidental. The broker builds its
    validation context as ``{"env_state": env, **agent_state, **env}``, so a name
    carried by both planes resolves to the env copy and the agent's own value is
    unreachable — the key-collision trap. ``scope: state`` / ``scope: env`` name
    the plane explicitly and are the recommended form for any new rule.
    """
    ctx = full_context if isinstance(full_context, dict) else {}
    env = ctx.get("env_state")
    env = env if isinstance(env, dict) else {}
    social = ctx.get("social_context")
    social = social if isinstance(social, dict) else {}
    st = state if isinstance(state, dict) else {}

    if scope == "env":
        planes = (env,)
    elif scope == "state":
        planes = (st,)
    elif scope == "social":
        planes = (social,)
    elif scope == "context":
        planes = (ctx,)
    else:  # auto
        planes = (env, st, ctx)

    for plane in planes:
        if name in plane:
            return plane[name]
    return MISSING


def agent_state_from_context(context: Any) -> Dict[str, Any]:
    """The agent's own state from a validation context, unwrapped exactly as
    ``AgentValidator.validate`` unwraps it.

    The broker's context carries the agent's state under ``agent_state`` (its
    ``state`` or ``personal`` block) and usually has no top-level ``state`` key,
    so reading ``context.get("state")`` alone would make ``scope: state`` find
    nothing on one plane and the value on another.
    """
    ctx = context if isinstance(context, dict) else {}
    state = ctx.get("state", {})
    if not state:
        agent_state = ctx.get("agent_state", {})
        if isinstance(agent_state, dict):
            state = agent_state.get("state", agent_state.get("personal", agent_state))
    return state if isinstance(state, dict) else {}


# Keys that belong to the other condition shapes. An ``expression`` condition
# carrying one of them is ambiguous (which one wins?) so it is refused.
_FOREIGN_KEYS = ("construct", "variable", "field", "operator", "value", "values")


@dataclass(frozen=True)
class CompiledExpression:
    source: str
    names: Tuple[str, ...]
    scope: str = "auto"


@dataclass(frozen=True)
class ExpressionOutcome:
    matched: bool
    readable: bool
    missing: Tuple[str, ...] = ()
    unusable: Tuple[Tuple[str, str], ...] = ()


def is_expression_condition(cond: Any) -> bool:
    """True for a dict with an ``expression`` key, or an object whose
    ``expression`` attribute is not None."""
    if isinstance(cond, dict):
        return "expression" in cond
    return getattr(cond, "expression", None) is not None


def _allowed_nodes():
    # Imported lazily: feedback.py pulls in the context-provider package, which
    # must not load just because a rule type module was imported.
    from broker.components.analytics.feedback import SafeExpressionEvaluator
    return SafeExpressionEvaluator


def _bool_operands_ok(node: ast.AST) -> bool:
    if isinstance(node, ast.Compare):
        return True
    if isinstance(node, ast.BoolOp):
        return all(_bool_operands_ok(v) for v in node.values)
    return False


def _check_source(source: str, *, numeric: bool) -> Tuple[ast.AST, list]:
    """The checks both compile paths share: parses, only the
    ``SafeExpressionEvaluator`` whitelist, finite number constants, no
    underscore names. Returns ``(tree, names)`` with names in order of first
    appearance. ``numeric=True`` is for an expression that must be a number
    (a relation residual): no comparison or and/or anywhere, and no bool
    constant. Raises ``ExpressionConditionError`` with a message that does not
    name the rule (the caller prefixes that)."""
    evaluator = _allowed_nodes()
    try:
        tree = ast.parse(source, mode="eval")
        # Compile here too, so an expression too deep for the compiler fails
        # at load with this message, not mid-run as a bare RecursionError.
        compile(tree, "<expression>", "eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        raise ExpressionConditionError(
            f"expression {_short_repr(source)} does not parse "
            f"({type(exc).__name__}: {_short_repr(str(exc))})"
        ) from exc

    for node in ast.walk(tree):
        if type(node) not in evaluator.ALLOWED_NODES:
            raise ExpressionConditionError(
                f"expression {source!r} uses {type(node).__name__}, which is not "
                "allowed. Allowed: numbers, variable names, + - * / // %, "
                "comparisons, and/or. No calls, powers, subscripts, attributes "
                "or strings."
            )
        if numeric and isinstance(node, (ast.Compare, ast.BoolOp)):
            raise ExpressionConditionError(
                f"expression {source!r} uses a comparison or and/or; it must be "
                "a number (arithmetic on variables and numbers only), not a test."
            )
    if not evaluator.is_safe(source):  # belt and braces: same whitelist
        raise ExpressionConditionError(f"expression {source!r} is not safe")

    names: list = []
    positions: Dict[str, int] = {}   # first appearance, so names read left to right
    allowed_constants = (int, float) if numeric else (int, float, bool)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            value = node.value
            if type(value) not in allowed_constants:
                raise ExpressionConditionError(
                    f"expression {source!r} contains the constant {value!r}; only "
                    + ("numbers" if numeric else "numbers and true/false")
                    + " are allowed."
                )
            try:
                finite = math.isfinite(float(value))
            except OverflowError:
                finite = False
            if not finite:
                raise ExpressionConditionError(
                    f"expression {source!r} contains a number that is not finite."
                )
        elif isinstance(node, ast.Name):
            if node.id.startswith("_"):
                raise ExpressionConditionError(
                    f"expression {source!r} uses the name {node.id!r}; names may "
                    "not start with an underscore."
                )
            if node.id not in names:
                names.append(node.id)
            positions[node.id] = min(positions.get(node.id, node.col_offset), node.col_offset)
    names.sort(key=lambda n: positions[n])
    return tree, names


def _require_names(source: str, names: list) -> None:
    if not names:
        raise ExpressionConditionError(
            f"expression {source!r} reads no variable; it would always give the "
            "same answer."
        )


@lru_cache(maxsize=1024)
def _compile_source(source: str, scope: str) -> CompiledExpression:
    """Validate ``source`` and return its compiled form. Raises
    ``ExpressionConditionError`` with a message that does not name the rule
    (the caller prefixes that). Failures are not cached by ``lru_cache``."""
    tree, names = _check_source(source, numeric=False)
    if not _bool_operands_ok(tree.body):
        raise ExpressionConditionError(
            f"expression {source!r} must be a comparison, or and/or of "
            "comparisons, so that it answers true or false."
        )
    _require_names(source, names)
    return CompiledExpression(source=source, names=tuple(names), scope=scope)


@lru_cache(maxsize=1024)
def _compile_numeric_source(source: str) -> CompiledExpression:
    _tree, names = _check_source(source, numeric=True)
    _require_names(source, names)
    return CompiledExpression(source=source, names=tuple(names), scope="auto")


def compile_numeric_expression(expr: Any, *, where: str = "") -> CompiledExpression:
    """Validate an arithmetic expression that must give a NUMBER (a coupling
    relation's residual), with the same whitelist, constant and name checks as
    the boolean condition: numbers, names, ``+ - * / // %``, unary minus. No
    comparison, ``and``/``or``, bool or string constant, call, or name starting
    with an underscore; at least one name. Raises ``ExpressionConditionError``
    (message starts with ``where``)."""
    prefix = f"{where}: " if where else ""
    try:
        if not isinstance(expr, str) or not expr.strip():
            raise ExpressionConditionError(
                f"expression must be a non-empty string, got {expr!r}."
            )
        return _compile_numeric_source(expr.strip())
    except ExpressionConditionError as exc:
        if prefix and not str(exc).startswith(prefix):
            raise ExpressionConditionError(prefix + str(exc)) from exc.__cause__
        raise


def _read(cond: Any, key: str) -> Any:
    if isinstance(cond, dict):
        return cond.get(key)
    return getattr(cond, key, None)


def compile_expression_condition(cond_or_expr: Any, *, where: str = "") -> CompiledExpression:
    """Validate and compile an ``expression:`` condition (dict, object or str).

    Raises ``ExpressionConditionError`` (message starts with ``where``) when the
    condition is bad. Compiled results are cached by (source, scope).
    """
    prefix = f"{where}: " if where else ""
    try:
        if isinstance(cond_or_expr, str):
            source, scope = cond_or_expr, "auto"
        else:
            source = _read(cond_or_expr, "expression")
            raw_scope = _read(cond_or_expr, "scope")
            scope = "auto" if raw_scope is None else str(raw_scope).strip().lower()
            is_dict = isinstance(cond_or_expr, dict)
            for key in _FOREIGN_KEYS:
                present = _read(cond_or_expr, key)
                if is_dict:
                    clash = key in cond_or_expr
                else:
                    # Dataclass / pydantic shapes carry defaults for these; only
                    # a real value counts as a clash, and `operator` always has a
                    # default there so it cannot be told apart.
                    clash = key != "operator" and present not in (None, "", [], ())
                if clash:
                    raise ExpressionConditionError(
                        f"an expression condition may not also carry {key!r}; "
                        "write the whole test in the expression."
                    )
            cond_type = _read(cond_or_expr, "type")
            if cond_type not in (None, "") and str(cond_type).strip().lower() != "expression":
                raise ExpressionConditionError(
                    f"an expression condition has type {cond_type!r}; leave "
                    "`type` out or write `expression`."
                )
            from broker.utils.agent_config import WORLD_CONDITION_SCOPES
            if scope not in WORLD_CONDITION_SCOPES:
                raise ExpressionConditionError(
                    f"scope {_read(cond_or_expr, 'scope')!r} is not one of "
                    f"{sorted(WORLD_CONDITION_SCOPES)}."
                )
        if not isinstance(source, str) or not source.strip():
            raise ExpressionConditionError(
                f"expression must be a non-empty string, got {source!r}."
            )
        return _compile_source(source.strip(), scope)
    except ExpressionConditionError as exc:
        if prefix and not str(exc).startswith(prefix):
            raise ExpressionConditionError(prefix + str(exc)) from exc.__cause__
        raise


_REPR = reprlib.Repr()
_REPR.maxstring = 80
_REPR.maxother = 80
_REPR.maxlong = 40


def _short_repr(value: Any) -> str:
    """A bounded repr for warning text and audit metadata (a 400-digit int or
    a long list must not land in the audit row in full)."""
    return _REPR.repr(value)


def evaluate_expression_condition(
    compiled: CompiledExpression, state: Any, full_context: Any
) -> ExpressionOutcome:
    """Evaluate a compiled condition against the agent state and the validation
    context. Missing or unusable variables give ``matched=False,
    readable=False`` without evaluating; a zero divisor raises
    ``ExpressionEvaluationError``."""
    values: Dict[str, Any] = {}
    missing = []
    unusable = []
    for name in compiled.names:
        raw = lookup_world_variable(name, compiled.scope, state, full_context)
        if raw is MISSING:
            missing.append(name)
            continue
        if isinstance(raw, bool):
            values[name] = raw
            continue
        if isinstance(raw, (bytes, bytearray, memoryview)):
            unusable.append((name, _short_repr(raw)))
            continue
        try:
            number = float(raw)
        except (TypeError, ValueError, OverflowError):
            unusable.append((name, _short_repr(raw)))
            continue
        if not math.isfinite(number):
            unusable.append((name, _short_repr(raw)))
            continue
        values[name] = number
    if missing or unusable:
        return ExpressionOutcome(
            matched=False, readable=False,
            missing=tuple(missing), unusable=tuple(unusable),
        )

    evaluator = _allowed_nodes()
    try:
        result = evaluator.evaluate(compiled.source, values, zero_guard=False)
    except (ZeroDivisionError, OverflowError) as exc:
        shown = ", ".join(f"{k}={v!r}" for k, v in values.items())
        raise ExpressionEvaluationError(
            f"expression {compiled.source!r} could not be evaluated "
            f"({type(exc).__name__}: {exc}) with {shown}. Guard a divisor with "
            "`and`, e.g. `capacity > 0 and storage_now / capacity > 0.9`."
        ) from exc
    if not isinstance(result, bool):
        raise ExpressionEvaluationError(
            f"expression {compiled.source!r} gave {result!r}, not true/false."
        )
    return ExpressionOutcome(matched=result, readable=True)


__all__ = [
    "MISSING",
    "agent_state_from_context",
    "CompiledExpression",
    "ExpressionConditionError",
    "ExpressionEvaluationError",
    "ExpressionOutcome",
    "compile_expression_condition",
    "compile_numeric_expression",
    "evaluate_expression_condition",
    "is_expression_condition",
    "lookup_world_variable",
]
