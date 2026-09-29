"""
Governance Auditor — Singleton for tracking governance interventions.

Extracted from agent_config.py for modularity.
Thread-safe singleton that tracks rule hits, retries, warnings,
and structural faults during broker-governed agent execution.
"""

import json
import threading
from collections import defaultdict
from pathlib import Path

from broker.utils.logging import setup_logger

logger = setup_logger(__name__)


class GovernanceAuditor:
    """
    Singleton for tracking and summarizing governance interventions.
    """
    _instance = None
    _lock = threading.Lock()
    # Per-thread mute switch for hypothetical validator runs (the retry
    # loop's feasible-set probes): a probe is not a rule hit, so it must not
    # move any count in governance_summary.json. Thread-local because the
    # decision phase can run on a worker pool.
    _mute = threading.local()

    @classmethod
    def muted(cls):
        """Context manager: rule-hit and warning logging from THIS thread is
        dropped while inside it."""
        import contextlib

        @contextlib.contextmanager
        def _cm():
            prev = getattr(cls._mute, "on", False)
            cls._mute.on = True
            try:
                yield
            finally:
                cls._mute.on = prev
        return _cm()

    @classmethod
    def _is_muted(cls) -> bool:
        return bool(getattr(cls._mute, "on", False))

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GovernanceAuditor, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.stats_lock = threading.Lock()
        self.rule_hits = defaultdict(int)
        self.retry_success_count = 0
        self.retry_failure_count = 0
        self.total_interventions = 0
        self.parse_errors = 0

        # Structural fault tracking (format/parsing issues during retry)
        self.structural_faults_fixed = 0      # Transient faults fixed by retry
        self.structural_faults_terminal = 0   # Faults that exhausted retries
        self.format_retry_attempts = 0        # Total format retry attempts

        # LLM-level retry tracking (these also count toward total LLM calls)
        self.empty_content_retries = 0        # LLM returned empty content, retry triggered
        self.empty_content_failures = 0       # LLM returned empty after all retries exhausted
        self.invalid_label_retries = 0        # Invalid _LABEL values triggered retry
        # Spec item 24 fix round (audit gap: reviewer measured 1,638 real HTTP
        # calls against 1,170 reported): backoff-layer retries
        # (broker/utils/llm_safeguard.py's wrap_llm_invoke_with_backoff), a
        # real extra network call per retry, distinct from the LLM's own
        # empty-content retry loop above.
        self.backoff_retries = 0

        # WARNING-level rule tracking (non-blocking observations)
        self.total_warnings = 0
        self.warning_hits = defaultdict(int)

        self._initialized = True

    def log_intervention(self, rule_id: str, success: bool, is_final: bool = False):
        """Record a validator intervention."""
        if self._is_muted():
            return
        with self.stats_lock:
            self.rule_hits[rule_id] += 1
            self.total_interventions += 1

            if is_final:
                if success:
                    self.retry_success_count += 1
                else:
                    self.retry_failure_count += 1

    def log_warning(self, rule_id: str):
        """Record a WARNING-level rule hit (non-blocking observation)."""
        if self._is_muted():
            return
        with self.stats_lock:
            self.warning_hits[rule_id] += 1
            self.total_warnings += 1

    def log_parse_error(self):
        """Record a parsing failure where LLM output could not be converted to SkillProposal."""
        with self.stats_lock:
            self.parse_errors += 1

    def log_format_retry(self):
        """Record a format/parsing retry attempt (structural fault encountered)."""
        with self.stats_lock:
            self.format_retry_attempts += 1

    def log_structural_fault_resolved(self, retry_count: int):
        """Record structural faults that were fixed after retry.

        Args:
            retry_count: Number of format retries before success
        """
        with self.stats_lock:
            self.structural_faults_fixed += retry_count

    def log_structural_fault_terminal(self, retry_count: int):
        """Record structural faults that could not be fixed (exhausted retries).

        Args:
            retry_count: Number of format retries attempted
        """
        with self.stats_lock:
            self.structural_faults_terminal += retry_count

    def log_empty_content_retry(self):
        """Record LLM returned empty content, triggering retry.

        This counts as an additional LLM call that returned no usable output.
        """
        with self.stats_lock:
            self.empty_content_retries += 1

    def log_empty_content_failure(self):
        """Record LLM returned empty content after all retries exhausted.

        This is a terminal failure where no valid output was obtained.
        """
        with self.stats_lock:
            self.empty_content_failures += 1

    def log_invalid_label_retry(self):
        """Record Invalid _LABEL value triggered retry.

        This occurs when a construct label field contains invalid values like
        'VL/L/M/H/VH' instead of a single valid label.
        """
        with self.stats_lock:
            self.invalid_label_retries += 1

    def log_backoff_retry(self):
        """Record one backoff-layer retry (spec item 24 fix round).

        A real extra network call the LLM safeguard's backoff wrapper made
        after a transport failure. Counts toward ``total_extra_llm_calls``
        the same way ``empty_content_retries`` / ``invalid_label_retries`` /
        ``format_retry_attempts`` already do.
        """
        with self.stats_lock:
            self.backoff_retries += 1

    def save_summary(self, output_path: Path):
        """Save aggregated statistics to JSON."""
        # Calculate total extra LLM calls from retries. backoff_retries
        # (spec item 24 fix round) folded in here, not just added as its own
        # sibling key, so total_extra_llm_calls stays what its name promises:
        # every extra LLM call this run made beyond one-per-decision.
        total_extra_llm_calls = (
            self.empty_content_retries +
            self.invalid_label_retries +
            self.format_retry_attempts +
            self.backoff_retries
        )

        summary = {
            "total_interventions": self.total_interventions,
            "rule_frequency": dict(self.rule_hits),
            "outcome_stats": {
                "retry_success": self.retry_success_count,
                "retry_exhausted": self.retry_failure_count,
                "parse_errors": self.parse_errors
            },
            "structural_faults": {
                "format_retry_attempts": self.format_retry_attempts,
                "faults_fixed": self.structural_faults_fixed,
                "faults_terminal": self.structural_faults_terminal
            },
            "llm_level_retries": {
                "empty_content_retries": self.empty_content_retries,
                "empty_content_failures": self.empty_content_failures,
                "invalid_label_retries": self.invalid_label_retries,
                "backoff_retries": self.backoff_retries,
                "total_extra_llm_calls": total_extra_llm_calls
            },
            "warnings": {
                "total_warnings": self.total_warnings,
                "warning_rule_frequency": dict(self.warning_hits)
            }
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=4)
        logger.info(f"[Governance:Auditor] Summary saved to {output_path}")

    def print_summary(self):
        """Print a human-readable summary to console."""
        # Calculate total extra LLM calls (backoff_retries folded in, same
        # reasoning as save_summary above).
        total_extra_llm_calls = (
            self.empty_content_retries +
            self.invalid_label_retries +
            self.format_retry_attempts +
            self.backoff_retries
        )

        lines = [
            "",
            "=" * 50,
            "  GOVERNANCE AUDIT SUMMARY",
            "=" * 50,
            f"  Total Interventions: {self.total_interventions}",
            f"  Parsing Failures:    {self.parse_errors}",
            f"  Successful Retries:  {self.retry_success_count}",
            f"  Final Fallouts:      {self.retry_failure_count}",
            "-" * 50,
            "  Structural Faults (Format Issues):",
            f"  - Format Retry Attempts: {self.format_retry_attempts}",
            f"  - Faults Fixed:          {self.structural_faults_fixed}",
            f"  - Faults Terminal:       {self.structural_faults_terminal}",
            "-" * 50,
            "  LLM-Level Retries (Extra LLM Calls):",
            f"  - Empty Content Retries:   {self.empty_content_retries}",
            f"  - Empty Content Failures:  {self.empty_content_failures}",
            f"  - Invalid Label Retries:   {self.invalid_label_retries}",
            f"  - Backoff Retries:         {self.backoff_retries}",
            f"  - Total Extra LLM Calls:   {total_extra_llm_calls}",
            "-" * 50,
            "  Top Rule Violations (ERROR):",
        ]
        sorted_rules = sorted(self.rule_hits.items(), key=lambda x: x[1], reverse=True)
        for rule_id, count in sorted_rules[:5]:
            lines.append(f"  - {rule_id}: {count} hits")
        if self.total_warnings > 0:
            lines.append("-" * 50)
            lines.append(f"  Warnings (Non-Blocking): {self.total_warnings}")
            sorted_warnings = sorted(self.warning_hits.items(), key=lambda x: x[1], reverse=True)
            for rule_id, count in sorted_warnings[:5]:
                lines.append(f"  - {rule_id}: {count} warnings")
        lines.append("=" * 50)
        logger.info("\n".join(lines))
