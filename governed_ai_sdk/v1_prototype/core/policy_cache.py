"""LRU cache for compiled policy rules."""
from collections import OrderedDict
from typing import Dict, List, Any
from governed_ai_sdk.v1_prototype.types import PolicyRule


class PolicyCache:
    """LRU cache for compiled policy rules."""

    def __init__(self, max_size: int = 100):
        self._cache: OrderedDict[str, List[PolicyRule]] = OrderedDict()
        self._max_size = max_size

    def get_or_compile(self, policy: Dict[str, Any]) -> List[PolicyRule]:
        """Return cached rules or compile and cache."""
        policy_id = self._compute_hash(policy)
        if policy_id in self._cache:
            self._cache.move_to_end(policy_id)
            return self._cache[policy_id]

        rules = self._compile_rules(policy)
        self._cache[policy_id] = rules
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
        return rules

    def _compute_hash(self, policy: Dict[str, Any]) -> str:
        """Compute deterministic hash for policy dict."""
        import hashlib
        import json

        def default_serializer(obj):
            """Handle non-JSON-serializable objects."""
            if isinstance(obj, PolicyRule):
                return {"__type__": "PolicyRule", "id": obj.id, "param": obj.param}
            return str(obj)

        # Only hash the rules portion, ignore any internal keys
        rules_data = policy.get("rules", [])
        policy_str = json.dumps(rules_data, sort_keys=True, default=default_serializer)
        return hashlib.md5(policy_str.encode()).hexdigest()

    def _compile_rules(self, policy: Dict[str, Any]) -> List[PolicyRule]:
        """Compile and sort rules by severity (high-severity first)."""
        rules: List[PolicyRule] = []
        for r in policy.get("rules", []):
            if isinstance(r, PolicyRule):
                rule = r
            else:
                rule = PolicyRule(
                    id=r["id"],
                    param=r["param"],
                    operator=r["operator"],
                    value=r["value"],
                    message=r["message"],
                    level=r.get("level", "ERROR"),
                    xai_hint=r.get("xai_hint"),
                    domain=r.get("domain", "generic"),
                    param_type=r.get("param_type", "numeric"),
                    param_unit=r.get("param_unit"),
                    severity_score=r.get("severity_score", 1.0),
                    literature_ref=r.get("literature_ref"),
                    rationale=r.get("rationale"),
                )
            rules.append(rule)
        return sorted(rules, key=lambda rule: rule.severity_score, reverse=True)

    def clear(self):
        """Clear the cache."""
        self._cache.clear()

    def stats(self) -> Dict[str, int]:
        """Return cache statistics."""
        return {"size": len(self._cache), "max_size": self._max_size}
