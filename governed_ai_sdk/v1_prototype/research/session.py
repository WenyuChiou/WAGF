"""Research session metadata for academic reproducibility."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
import json


@dataclass
class ResearchSession:
    """
    Metadata for entire research session.

    Captures all parameters needed to reproduce the study.
    """
    study_id: str
    domain: str
    protocol_version: str
    execution_date: datetime = field(default_factory=datetime.now)
    seed: int = 42
    treatment_groups: Dict[str, int] = field(default_factory=dict)
    sensor_schemas: Dict[str, Any] = field(default_factory=dict)
    total_agents: int = 0
    framework_version: str = "0.1.0"

    # Optional metadata
    researcher: Optional[str] = None
    institution: Optional[str] = None
    irb_number: Optional[str] = None
    notes: Optional[str] = None

    def to_methods_section(self) -> str:
        """
        Export formatted text for academic Methods section.

        Returns:
            Markdown-formatted methods section
        """
        groups_str = ", ".join(f"{k}={v}" for k, v in self.treatment_groups.items())

        return f"""## Methods

### Simulation Framework
- **Framework**: GovernedAI SDK v{self.framework_version}
- **Domain**: {self.domain}
- **Protocol Version**: {self.protocol_version}

### Participants
- **Total Agents**: N={self.total_agents}
- **Treatment Groups**: {groups_str}

### Reproducibility
- **Study ID**: {self.study_id}
- **Random Seed**: {self.seed}
- **Execution Date**: {self.execution_date.strftime('%Y-%m-%d %H:%M:%S')}

### Sensor Configuration
{self._format_sensors()}
"""

    def _format_sensors(self) -> str:
        """Format sensor schemas as markdown table."""
        if not self.sensor_schemas:
            return "No sensors configured."

        lines = ["| Sensor | Variable | Data Type | Units |", "|--------|----------|-----------|-------|"]
        for name, schema in self.sensor_schemas.items():
            var = schema.get("variable_name", "N/A")
            dtype = schema.get("data_type", "N/A")
            units = schema.get("units", "N/A")
            lines.append(f"| {name} | {var} | {dtype} | {units} |")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Export as dictionary for JSON serialization."""
        return {
            "study_id": self.study_id,
            "domain": self.domain,
            "protocol_version": self.protocol_version,
            "execution_date": self.execution_date.isoformat(),
            "seed": self.seed,
            "treatment_groups": self.treatment_groups,
            "sensor_schemas": self.sensor_schemas,
            "total_agents": self.total_agents,
            "framework_version": self.framework_version,
            "researcher": self.researcher,
            "institution": self.institution,
            "irb_number": self.irb_number,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchSession":
        """Create from dictionary."""
        data = data.copy()
        if isinstance(data.get("execution_date"), str):
            data["execution_date"] = datetime.fromisoformat(data["execution_date"])
        return cls(**data)

    def save(self, path: str) -> None:
        """Save session metadata to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "ResearchSession":
        """Load session metadata from JSON file."""
        with open(path, "r") as f:
            return cls.from_dict(json.load(f))
