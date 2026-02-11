"""SkillFilterMixin — skill filtering and option injection for LLM prompts.

Extracted from SkillBrokerEngine to reduce file size.  These methods
access ``self.*`` attributes defined on SkillBrokerEngine; this is the
standard Python mixin pattern where the mixin is always combined with
the host class via multiple inheritance.
"""
from typing import Any, Dict, List

from ..utils.logging import logger


class SkillFilterMixin:
    """Mixin providing skill filtering and option injection for LLM prompts."""

    def _get_action_ids(self, agent_type: str) -> List[str]:
        base_type = self.config.get_base_type(agent_type) if hasattr(self.config, "get_base_type") else agent_type
        cfg = self.config.get(base_type) if self.config else {}
        actions = cfg.get("actions", cfg.get("parsing", {}).get("actions", [])) if cfg else []
        ids = []
        for action in actions:
            if isinstance(action, dict) and action.get("id"):
                ids.append(action["id"])
        return ids

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
        filtered = self._filter_identity_skills(agent_type, action_ids, state)
        context["available_skills"] = filtered
        self._inject_options_text(context, filtered)

    def _inject_options_text(self, context: Dict[str, Any], skills: List[str]) -> None:
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
