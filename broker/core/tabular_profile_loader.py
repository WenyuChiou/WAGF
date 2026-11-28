"""Domain-agnostic tabular profile loader for populating BaseAgent instances."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from broker.agents import AgentConfig, BaseAgent, Skill, StateParam

_RESERVED_AGENT_ATTRS = frozenset(
    {
        "config",
        "name",
        "id",
        "agent_type",
        "memory",
        "memory_config",
        "fixed_attributes",
        "dynamic_state",
        "custom_attributes",
    }
)


def _to_python_scalar(value: Any) -> Any:
    """Convert numpy/pandas scalar objects to native JSON-safe Python values."""
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _is_missing_cell(value: Any) -> bool:
    if value is None:
        return True
    try:
        res = pd.isna(value)
        return bool(res) if isinstance(res, (bool,)) or hasattr(res, "item") else False
    except Exception:
        return False


def apply_agent_attributes(agent: BaseAgent, attrs: Mapping[str, Any]) -> None:
    """Attach mapped static attributes consistently across BaseAgent storage layers."""
    for raw_key, raw_val in attrs.items():
        key = str(raw_key)
        if not key or _is_missing_cell(raw_val):
            continue
        val = _to_python_scalar(raw_val)
        agent.custom_attributes[key] = val
        if isinstance(getattr(agent, "fixed_attributes", None), dict):
            agent.fixed_attributes[key] = val
        if (
            not key.startswith("_")
            and key not in _RESERVED_AGENT_ATTRS
            and not hasattr(type(agent), key)
        ):
            setattr(agent, key, val)


def append_seed_memories(agent: BaseAgent, contents: Sequence[str]) -> None:
    """Append domain-neutral seed memory dicts compatible with OriginGate."""
    mem_list = list(getattr(agent, "memory", None) or [])
    for text in contents:
        cleaned = str(text).strip()
        if not cleaned:
            continue
        mem_list.append(
            {
                "content": cleaned,
                "metadata": {"origin": "seed", "source": "personal", "period": 0},
            }
        )
    agent.memory = mem_list


def read_tabular_dataframe(path: Path) -> Tuple[pd.DataFrame, str]:
    """Load CSV, TSV, or Excel table into a DataFrame alongside its file SHA-256."""
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"Tabular profile file not found: {resolved}")
    sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
    suffix = resolved.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(resolved)
    elif suffix in (".tsv", ".tab"):
        df = pd.read_csv(resolved, sep="\t")
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(resolved)
    else:
        raise ValueError(
            f"Unsupported tabular profile format {suffix!r} for {resolved}; "
            f"expected .csv, .tsv, .tab, .xlsx, or .xls."
        )
    return df, sha256


@dataclass(frozen=True)
class TabularLoadResult:
    """Loaded agents and source provenance returned by :class:`TabularProfileLoader`."""

    agents: Dict[str, BaseAgent]
    source_path: Path
    sha256: str
    rows_loaded: int


class TabularProfileLoader:
    """Schema-driven loader mapping tabular columns to BaseAgent state and attributes."""

    def __init__(
        self,
        *,
        id_col: Optional[str] = None,
        columns: Optional[Union[Mapping[str, str], Sequence[str]]] = None,
        state_columns: Optional[Union[Mapping[str, Any], Sequence[str]]] = None,
        memory_cols: Optional[Sequence[str]] = None,
        memory_template: Optional[str] = None,
    ) -> None:
        self.id_col = id_col
        if columns is None:
            self.columns = {}
        elif isinstance(columns, Mapping):
            self.columns = {str(k): str(v) for k, v in columns.items()}
        elif isinstance(columns, Sequence) and not isinstance(columns, (str, bytes)):
            self.columns = {str(c): str(c) for c in columns}
        else:
            raise ValueError(f"columns must be a mapping or sequence of column names, got {columns!r}")

        if state_columns is None:
            self.state_columns = {}
        elif isinstance(state_columns, Mapping):
            self.state_columns = dict(state_columns)
        elif isinstance(state_columns, Sequence) and not isinstance(state_columns, (str, bytes)):
            self.state_columns = {str(c): str(c) for c in state_columns}
        else:
            raise ValueError(
                f"state_columns must be a mapping or sequence of column names, got {state_columns!r}"
            )
        self.memory_cols: Tuple[str, ...] = tuple(str(c) for c in (memory_cols or ()))
        self.memory_template = memory_template

    def load_agents(
        self,
        path: Path,
        *,
        agent_type: str,
        skills: Optional[Sequence[Skill]] = None,
        limit: Optional[int] = None,
        persona: str = "",
        role_description: str = "",
    ) -> TabularLoadResult:
        """Instantiate ``BaseAgent`` objects from ``path`` according to configured mappings."""
        df, sha256 = read_tabular_dataframe(path)
        if limit is not None:
            if limit < 0:
                raise ValueError(f"limit must be >= 0, got {limit!r}")
            if limit > len(df):
                raise ValueError(
                    f"Requested {limit} agent(s) for {agent_type!r} from {path}, "
                    f"but table contains only {len(df)} row(s)."
                )
            df = df.iloc[:limit]

        missing_cols: List[str] = []
        if self.id_col is not None and self.id_col not in df.columns:
            missing_cols.append(self.id_col)
        for col in self.columns.values():
            if col not in df.columns:
                missing_cols.append(col)
        for col in self.memory_cols:
            if col not in df.columns:
                missing_cols.append(col)
        state_specs: List[Tuple[str, str, Optional[Tuple[float, float]]]] = []
        for state_name, spec in self.state_columns.items():
            if isinstance(spec, str):
                col_name, bounds = spec, None
            elif isinstance(spec, Mapping) and isinstance(spec.get("col"), str):
                col_name = spec["col"]
                raw_range = spec.get("raw_range")
                if raw_range is not None:
                    if not isinstance(raw_range, Sequence) or len(raw_range) != 2:
                        raise ValueError(
                            f"state_columns[{state_name!r}].raw_range must be a 2-element sequence"
                        )
                    bounds = (float(raw_range[0]), float(raw_range[1]))
                else:
                    bounds = None
            else:
                raise ValueError(
                    f"state_columns[{state_name!r}] must be a column name string or "
                    f"{{'col': ..., 'raw_range': [min, max]}}, got {spec!r}"
                )
            if col_name not in df.columns:
                missing_cols.append(col_name)
            state_specs.append((str(state_name), col_name, bounds))

        if missing_cols:
            raise ValueError(
                f"Tabular profile {path} for {agent_type!r} is missing column(s): "
                f"{sorted(set(missing_cols))}"
            )

        skill_list = list(skills or ())
        agents: Dict[str, BaseAgent] = {}
        for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
            if self.id_col is not None:
                raw_id = row[self.id_col]
                if _is_missing_cell(raw_id) or not str(raw_id).strip():
                    raise ValueError(
                        f"Tabular profile {path} has empty id_col {self.id_col!r} at row {row_idx}"
                    )
                agent_id = str(_to_python_scalar(raw_id)).strip()
            else:
                agent_id = f"{agent_type}_{row_idx}"

            if agent_id in agents:
                raise ValueError(f"Duplicate agent_id {agent_id!r} in tabular profile {path}")

            state_params: List[StateParam] = []
            for state_name, col_name, bounds in state_specs:
                raw_val = row[col_name]
                if _is_missing_cell(raw_val):
                    raise ValueError(
                        f"Missing numeric value in state column {col_name!r} for agent {agent_id!r}"
                    )
                numeric_val = float(_to_python_scalar(raw_val))
                resolved_bounds = bounds or (
                    min(0.0, numeric_val),
                    max(1.0, numeric_val),
                )
                state_params.append(
                    StateParam(
                        name=state_name,
                        raw_range=resolved_bounds,
                        initial_raw=numeric_val,
                    )
                )

            cfg = AgentConfig(
                name=agent_id,
                agent_type=agent_type,
                state_params=state_params,
                objectives=[],
                constraints=[],
                skills=[s for s in skill_list],
                persona=persona,
                role_description=role_description,
            )
            agent = BaseAgent(cfg)

            mapped_attrs = {
                attr_name: row[col_name]
                for attr_name, col_name in self.columns.items()
                if not _is_missing_cell(row[col_name])
            }
            apply_agent_attributes(agent, mapped_attrs)

            seed_lines: List[str] = []
            for mem_col in self.memory_cols:
                raw_mem = row[mem_col]
                if not _is_missing_cell(raw_mem):
                    for part in str(_to_python_scalar(raw_mem)).split("|"):
                        if part.strip():
                            seed_lines.append(part.strip())
            if self.memory_template:
                fmt_context: Dict[str, Any] = {
                    str(k): _to_python_scalar(v)
                    for k, v in row.items()
                    if not _is_missing_cell(v)
                }
                fmt_context.update(
                    {k: _to_python_scalar(v) for k, v in mapped_attrs.items()}
                )
                fmt_context.setdefault("agent_id", agent_id)
                fmt_context.setdefault("agent_type", agent_type)
                rendered = self.memory_template.format_map(fmt_context).strip()
                if rendered:
                    seed_lines.append(rendered)
            if seed_lines:
                append_seed_memories(agent, seed_lines)

            agents[agent_id] = agent

        return TabularLoadResult(
            agents=agents,
            source_path=Path(path),
            sha256=sha256,
            rows_loaded=len(agents),
        )


__all__ = [
    "TabularLoadResult",
    "TabularProfileLoader",
    "append_seed_memories",
    "apply_agent_attributes",
    "read_tabular_dataframe",
]
