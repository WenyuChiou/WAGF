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

        # WARNING-level rule tracking (non-blocking observations)
        self.total_warnings = 0
        self.warning_hits = defaultdict(int)

        self._initialized = True

    def log_intervention(self, rule_id: str, success: bool, is_final: bool = False):
        """Record a validator intervention."""
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

    def save_summary(self, output_path: Path):
        """Save aggregated statistics to JSON."""
        # Calculate total extra LLM calls from retries
        total_extra_llm_calls = (
            self.empty_content_retries +
            self.invalid_label_retries +
            self.format_retry_attempts
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
        # Calculate total extra LLM calls
        total_extra_llm_calls = (
            self.empty_content_retries +
            self.invalid_label_retries +
            self.format_retry_attempts
        )

        print("\n" + "="*50)
        print("  GOVERNANCE AUDIT SUMMARY")
        print("="*50)
        print(f"  Total Interventions: {self.total_interventions}")
        print(f"  Parsing Failures:    {self.parse_errors}")
        print(f"  Successful Retries:  {self.retry_success_count}")
        print(f"  Final Fallouts:      {self.retry_failure_count}")
        print("-"*50)
        print("  Structural Faults (Format Issues):")
        print(f"  - Format Retry Attempts: {self.format_retry_attempts}")
        print(f"  - Faults Fixed:          {self.structural_faults_fixed}")
        print(f"  - Faults Terminal:       {self.structural_faults_terminal}")
        print("-"*50)
        print("  LLM-Level Retries (Extra LLM Calls):")
        print(f"  - Empty Content Retries:   {self.empty_content_retries}")
        print(f"  - Empty Content Failures:  {self.empty_content_failures}")
        print(f"  - Invalid Label Retries:   {self.invalid_label_retries}")
        print(f"  - Total Extra LLM Calls:   {total_extra_llm_calls}")
        print("-"*50)
        print("  Top Rule Violations (ERROR):")
        # Sort by frequency
        sorted_rules = sorted(self.rule_hits.items(), key=lambda x: x[1], reverse=True)
        for rule_id, count in sorted_rules[:5]:
            print(f"  - {rule_id}: {count} hits")
        if self.total_warnings > 0:
            print("-"*50)
            print(f"  Warnings (Non-Blocking): {self.total_warnings}")
            sorted_warnings = sorted(self.warning_hits.items(), key=lambda x: x[1], reverse=True)
            for rule_id, count in sorted_warnings[:5]:
                print(f"  - {rule_id}: {count} warnings")
        print("="*50 + "\n")
