"""
Feedback Provider — Config-driven environment feedback for LLM agents.

Provides three components:

1. **AgentMetricsTracker**: Lightweight per-agent metrics history storage.
   Records numerical state variables each year and computes temporal trends.

2. **SafeExpressionEvaluator**: AST-whitelisted expression evaluator for
   YAML-defined assertion conditions (e.g., ``supply / request < 0.95``).

3. **FeedbackDashboardProvider**: A :class:`ContextProvider` that renders
   a structured feedback dashboard and injects it into the agent prompt
   via the ``{feedback_dashboard}`` template placeholder.

Together these replace domain-specific hardcoded feedback patches with a
fully **config-driven** mechanism: domain authors declare tracked metrics
and assertions in ``agent_types.yaml``; the framework handles trend
analysis, assertion evaluation, and prompt injection automatically.

Configuration example (``agent_types.yaml``)::

    feedback:
      trend_window: 5
      dashboard_format: "table"       # table | summary | none
      tracked_metrics:
        - name: "request"
          source: "current_request"   # key in env_context
          unit: "AF"
          format: ",.0f"
        - name: "supply"
          source: "current_diversion"
          unit: "AF"
          format: ",.0f"
      assertions:
        - when: "supply / request < 0.95"
          severity: "warning"
          message: >-
            You requested {request_fmt} AF but only received {supply_fmt} AF
            ({unmet_pct:.0f}% unmet). Increasing your request further will
            NOT increase your actual water supply.

Architecture notes:
    * ``AgentMetricsTracker`` is intentionally **independent** of
      ``MemoryEngine``.  Memory stores narrative text for LLM consumption;
      the tracker stores numerical snapshots for trend computation.
    * ``FeedbackDashboardProvider`` follows the same ``ContextProvider``
      protocol used by ``MemoryProvider``, ``ObservableStateProvider``, etc.
    * The ``SafeExpressionEvaluator`` rejects any AST node not in a strict
      whitelist, preventing arbitrary code execution from YAML config.

References:
    Risko & Gilbert (2016). Cognitive Offloading. Trends in Cognitive Sciences.
"""

import ast
import logging
from typing import Any, Dict, List, Optional

from broker.components.context_providers import ContextProvider

logger = logging.getLogger(__name__)


# =========================================================================
# Metrics Tracker
# =========================================================================

class AgentMetricsTracker:
    """Lightweight per-agent metrics history for trend analysis.

    Domain-agnostic: tracked metric names are defined in YAML config and
    passed at construction time.  No dependency on ``MemoryEngine``.

    Parameters
    ----------
    metric_names : list[str]
        Names of metrics to track (must match ``name`` fields in config).
    window : int
        Default window size for trend computation.
    """

    def __init__(self, metric_names: List[str], window: int = 5):
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._metric_names = list(metric_names)
        self._window = window

    # -- public API -------------------------------------------------------

    def record(self, agent_id: str, year: int, metrics: Dict[str, float]) -> None:
        """Record a metrics snapshot for *agent_id* at *year*."""
        entry: Dict[str, Any] = {"year": year}
        for name in self._metric_names:
            entry[name] = metrics.get(name, 0.0)
        self._history.setdefault(agent_id, []).append(entry)

    def get_history(
        self, agent_id: str, window: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return the most recent *window* entries in chronological order."""
        w = window if window is not None else self._window
        return self._history.get(agent_id, [])[-w:]

    def compute_trends(self, agent_id: str) -> Dict[str, str]:
        """Compute trend direction for each metric.

        Returns a dict mapping metric name → one of
        ``"rising"``, ``"falling"``, ``"stable"``, or ``"insufficient_data"``.

        Trend is determined by comparing the average of the first half of
        the window to the average of the second half (±5 % tolerance).
        """
        history = self.get_history(agent_id)
        if len(history) < 2:
            return {m: "insufficient_data" for m in self._metric_names}

        trends: Dict[str, str] = {}
        for metric in self._metric_names:
            values = [h.get(metric, 0.0) for h in history]
            mid = len(values) // 2
            first_half = values[:mid] or values[:1]
            second_half = values[mid:]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            if first_avg == 0 and second_avg == 0:
                trends[metric] = "stable"
            elif first_avg == 0:
                trends[metric] = "rising"
            elif second_avg > first_avg * 1.05:
                trends[metric] = "rising"
            elif second_avg < first_avg * 0.95:
                trends[metric] = "falling"
            else:
                trends[metric] = "stable"
        return trends


# =========================================================================
# Safe Expression Evaluator
# =========================================================================

class SafeExpressionEvaluator:
    """Evaluate simple arithmetic / comparison expressions from YAML config.

    **Allowed**: variable names, numeric constants, ``+  -  *  /``,
    comparisons ``<  >  <=  >=  ==  !=``, boolean ``and  or``, unary ``-``.

    **Rejected**: function calls, imports, attribute access, subscripts,
    assignments, comprehensions — anything outside the whitelist.

    Uses :func:`ast.parse` for safety validation before :func:`eval`.
    """

    ALLOWED_NODES = frozenset({
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp,
        ast.Constant, ast.Name, ast.Load,
        # Binary ops
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
        # Comparisons
        ast.Lt, ast.Gt, ast.LtE, ast.GtE, ast.Eq, ast.NotEq,
        # Unary
        ast.USub, ast.UAdd,
        # Boolean
        ast.And, ast.Or,
    })

    @classmethod
    def is_safe(cls, expr: str) -> bool:
        """Return ``True`` if *expr* contains only whitelisted AST nodes."""
        try:
            tree = ast.parse(expr, mode="eval")
            return all(type(node) in cls.ALLOWED_NODES for node in ast.walk(tree))
        except SyntaxError:
            return False

    @classmethod
    def evaluate(cls, expr: str, variables: Dict[str, float]) -> Any:
        """Safely evaluate *expr* with the given variable bindings.

        Raises :class:`ValueError` if the expression is unsafe.
        """
        if not cls.is_safe(expr):
            raise ValueError(f"Unsafe expression rejected: {expr!r}")
        # Guard against division by zero: replace 0-valued vars with tiny ε
        safe_vars = {
            k: (v if v != 0 else 1e-10) for k, v in variables.items()
        }
        code = compile(ast.parse(expr, mode="eval"), "<assertion>", "eval")
        return eval(code, {"__builtins__": {}}, safe_vars)  # noqa: S307


# =========================================================================
# Feedback Dashboard Provider
# =========================================================================

_TREND_ARROWS = {
    "rising": "RISING",
    "falling": "FALLING",
    "stable": "STABLE",
    "insufficient_data": "N/A",
}


class FeedbackDashboardProvider(ContextProvider):
    """Config-driven feedback dashboard injected into the agent prompt.

    Reads tracked metrics from an :class:`AgentMetricsTracker`, evaluates
    YAML-defined assertions against the current environment context, and
    renders a structured dashboard string stored in
    ``context["feedback_dashboard"]``.

    The prompt template should include a ``{feedback_dashboard}`` placeholder
    (empty string when no feedback is configured → no visual impact).

    Parameters
    ----------
    tracker : AgentMetricsTracker
        Shared tracker instance that accumulates per-agent metrics.
    config : dict
        The ``feedback`` section from ``agent_types.yaml``.
    """

    def __init__(self, tracker: AgentMetricsTracker, config: Dict[str, Any]):
        self.tracker = tracker
        self._metrics_cfg: List[Dict[str, Any]] = config.get("tracked_metrics", [])
        self._assertions: List[Dict[str, Any]] = config.get("assertions", [])
        self._format = config.get("dashboard_format", "table")

    # -- ContextProvider interface ----------------------------------------

    def provide(
        self,
        agent_id: str,
        agents: Dict[str, Any],
        context: Dict[str, Any],
        **kwargs,
    ) -> None:
        env_context: Dict[str, Any] = kwargs.get("env_context", {})

        # Resolve current metric values.
        # Primary: use tracker's latest entry (per-agent, set by pre_year).
        # Fallback: env_context (may be global, not per-agent).
        current_raw = self._resolve_current(env_context, agent_id=agent_id)
        # Build formatted values for message templates
        current_fmt = self._build_format_dict(current_raw)

        sections: List[str] = []

        # 1. History table
        if self._format in ("table", "both"):
            table = self._render_table(agent_id, current_raw)
            if table:
                sections.append(table)

        # 2. Trend summary
        trends = self.tracker.compute_trends(agent_id)
        if any(v != "insufficient_data" for v in trends.values()):
            sections.append(self._render_trends(trends))

        # 3. Assertion alerts
        alerts = self._evaluate_assertions(current_raw, current_fmt)
        sections.extend(alerts)

        context["feedback_dashboard"] = "\n".join(sections) if sections else ""

    # -- internals --------------------------------------------------------

    def _resolve_current(
        self,
        env_context: Dict[str, Any],
        agent_id: Optional[str] = None,
    ) -> Dict[str, float]:
        """Resolve current metric values for the agent.

        Primary source: tracker's latest recorded entry (per-agent, set by
        the lifecycle ``pre_year`` hook before providers run).

        Fallback: *env_context* (which may be global, not per-agent).
        """
        # Primary: use per-agent data from tracker
        if agent_id:
            latest = self.tracker.get_history(agent_id, window=1)
            if latest:
                entry = latest[-1]
                return {
                    cfg["name"]: float(entry.get(cfg["name"], 0))
                    for cfg in self._metrics_cfg
                }

        # Fallback: resolve from env_context
        result: Dict[str, float] = {}
        for cfg in self._metrics_cfg:
            name = cfg["name"]
            source = cfg.get("source", name)
            result[name] = float(env_context.get(source, 0))
        return result

    def _build_format_dict(self, raw: Dict[str, float]) -> Dict[str, Any]:
        """Build a dict with both raw and formatted values for templates."""
        fmt_dict: Dict[str, Any] = {}
        for cfg in self._metrics_cfg:
            name = cfg["name"]
            val = raw.get(name, 0.0)
            fmt_dict[name] = val
            # Add formatted version (e.g. request_fmt = "150,000")
            fmt_spec = cfg.get("format", "")
            if fmt_spec:
                try:
                    fmt_dict[f"{name}_fmt"] = format(val, fmt_spec)
                except (ValueError, TypeError):
                    fmt_dict[f"{name}_fmt"] = str(val)
            else:
                fmt_dict[f"{name}_fmt"] = str(val)

        # Compute derived convenience variables for assertion messages
        request = raw.get("request", 0)
        supply = raw.get("supply", 0)
        if request > 0:
            fmt_dict["unmet_pct"] = (1.0 - supply / request) * 100.0
            fmt_dict["fulfillment_pct"] = supply / request * 100.0
        else:
            fmt_dict["unmet_pct"] = 0.0
            fmt_dict["fulfillment_pct"] = 100.0

        return fmt_dict

    def _render_table(self, agent_id: str, current: Dict[str, float]) -> str:
        """Render historical metrics as an aligned text table."""
        history = self.tracker.get_history(agent_id)
        if not history and not current:
            return ""

        # Column headers from config
        headers = ["Year"] + [
            f"{cfg['name']} ({cfg.get('unit', '')})" for cfg in self._metrics_cfg
        ]

        # Build rows from history
        rows: List[List[str]] = []
        for entry in history:
            row = [str(entry.get("year", "?"))]
            for cfg in self._metrics_cfg:
                val = entry.get(cfg["name"], 0)
                fmt_spec = cfg.get("format", "")
                try:
                    row.append(format(val, fmt_spec) if fmt_spec else str(val))
                except (ValueError, TypeError):
                    row.append(str(val))
            rows.append(row)

        if not rows:
            return ""

        # Compute column widths
        all_rows = [headers] + rows
        col_widths = [
            max(len(cell) for cell in col) for col in zip(*all_rows)
        ]

        # Render
        lines = ["PERFORMANCE HISTORY:"]
        header_line = " | ".join(
            h.ljust(w) for h, w in zip(headers, col_widths)
        )
        lines.append(header_line)
        lines.append("-" * len(header_line))
        for row in rows:
            lines.append(
                " | ".join(c.rjust(w) for c, w in zip(row, col_widths))
            )

        return "\n".join(lines)

    def _render_trends(self, trends: Dict[str, str]) -> str:
        """Render a one-line trend summary."""
        parts = []
        for cfg in self._metrics_cfg:
            name = cfg["name"]
            direction = trends.get(name, "N/A")
            arrow = _TREND_ARROWS.get(direction, direction)
            parts.append(f"{name} {arrow}")
        return "TREND: " + ", ".join(parts)

    def _evaluate_assertions(
        self,
        current_raw: Dict[str, float],
        current_fmt: Dict[str, Any],
    ) -> List[str]:
        """Evaluate YAML-defined assertions and return alert strings."""
        alerts: List[str] = []
        for assertion in self._assertions:
            expr = assertion.get("when", "")
            if not expr or not SafeExpressionEvaluator.is_safe(expr):
                if expr:
                    logger.warning("Skipping unsafe assertion: %s", expr)
                continue
            try:
                triggered = SafeExpressionEvaluator.evaluate(expr, current_raw)
            except Exception:
                logger.debug("Assertion eval failed: %s", expr, exc_info=True)
                continue

            if triggered:
                severity = assertion.get("severity", "warning").upper()
                msg_template = assertion.get("message", "")
                try:
                    msg = msg_template.format(**current_fmt)
                except (KeyError, IndexError, ValueError):
                    msg = msg_template  # fallback: raw template
                alerts.append(f"{severity}: {msg}")

        return alerts
