"""
JSONL audit writer with replay support.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from governed_ai_sdk.v1_prototype.types import GovernanceTrace


class AuditWriter:
    """
    Writes governance audit logs in JSONL format.
    """

    def __init__(
        self,
        output_path: str = "audit.jsonl",
        buffer_size: int = 10,
        include_timestamp: bool = True,
    ):
        self.output_path = Path(output_path)
        self.buffer_size = buffer_size
        self.include_timestamp = include_timestamp
        self._buffer: list[Dict[str, Any]] = []
        self._sequence_num = 0
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any],
        trace: GovernanceTrace,
        modified_action: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._sequence_num += 1

        record: Dict[str, Any] = {
            "seq": self._sequence_num,
            "action": action,
            "state": state,
            "trace": {
                "valid": trace.valid,
                "rule_id": trace.rule_id,
                "rule_message": trace.rule_message,
                "state_delta": trace.state_delta,
                "entropy_friction": trace.entropy_friction,
            },
        }

        if self.include_timestamp:
            record["timestamp"] = datetime.now().isoformat()

        if modified_action:
            record["modified_action"] = modified_action
            record["was_modified"] = True

        if metadata:
            record["metadata"] = metadata

        self._buffer.append(record)

        if len(self._buffer) >= self.buffer_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return

        with open(self.output_path, "a", encoding="utf-8") as f:
            for record in self._buffer:
                f.write(json.dumps(record, default=str) + "\n")

        self._buffer.clear()

    def close(self) -> None:
        self.flush()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AuditReader:
    """
    Reads and filters audit logs.
    """

    def __init__(self, input_path: str):
        self.input_path = Path(input_path)

    def read_all(self) -> list[Dict[str, Any]]:
        records: list[Dict[str, Any]] = []
        with open(self.input_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def filter_blocked(self) -> list[Dict[str, Any]]:
        return [r for r in self.read_all() if not r["trace"]["valid"]]

    def filter_by_rule(self, rule_id: str) -> list[Dict[str, Any]]:
        return [r for r in self.read_all() if r["trace"]["rule_id"] == rule_id]
