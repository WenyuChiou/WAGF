"""Water-domain phase layouts."""
from typing import List

from broker.interfaces.coordination import ExecutionPhase, PhaseConfig


def water_default_phases() -> List[PhaseConfig]:
    """Return the four-phase water MAS execution order."""
    # Phase 6J-C (2026-05-22): relocated from PhaseOrchestrator.
    return [
        PhaseConfig(
            phase=ExecutionPhase.INSTITUTIONAL,
            agent_types=["government", "insurance"],
            ordering="sequential",
        ),
        PhaseConfig(
            phase=ExecutionPhase.HOUSEHOLD,
            agent_types=[
                "household_owner", "household_renter",
                "household_nmg_owner", "household_nmg_renter",
                "household_mg_owner", "household_mg_renter",
            ],
            ordering="sequential",
        ),
        PhaseConfig(
            phase=ExecutionPhase.RESOLUTION,
            agent_types=[],
            depends_on=[ExecutionPhase.INSTITUTIONAL, ExecutionPhase.HOUSEHOLD],
        ),
        PhaseConfig(
            phase=ExecutionPhase.OBSERVATION,
            agent_types=[],
            depends_on=[ExecutionPhase.RESOLUTION],
        ),
    ]
