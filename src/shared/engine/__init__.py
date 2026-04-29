"""shared.engine — Phase 2 numerical simulation backend.

This package is **closed for import** during Phase 1.

The numerical simulation engine (CasADi-based solvers, HDF5 result
storage, controller runtime adapters) is implemented in Phase 2 (Stages
S4 through S7). Phase 1 source code must not import any submodule
under `shared.engine`.

This barrier is enforced at import time by the `ImportError` raised
below. The barrier is removed at Stage S4 entry (per
`specs/07_implementation_order.md` §10) by replacing this file with
the normal package initializer that exports `SimulationRequest`,
`SimulationResultArtifact`, `SolverRegistry`, and friends.

References
----------
* ADR-001: Phase 1 Engine Isolation (`decisions/ADR-001-phase1-engine-isolation.md`)
* `specs/06_data_flow_and_architecture.md` §5.7
* `specs/07_implementation_order.md` §10 (Stage S4)
* `specs/08_codex_execution_rules.md` §6.1 (Forbidden Phase 1 imports)
* `tests/architecture/test_engine_isolation.py` (verifies this barrier)
"""

raise ImportError(
    "shared.engine is not available in Phase 1. "
    "It will be activated in Stage S4 of Phase 2 implementation. "
    "See decisions/ADR-001-phase1-engine-isolation.md, "
    "specs/06_data_flow_and_architecture.md §5.7, and "
    "specs/07_implementation_order.md §10."
)
