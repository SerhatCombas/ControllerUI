"""Data layer for ControllerDesignModule.

Re-exports the public API of the model subpackage. UI code imports
from this package, not from individual files.

Phase 1 contents (planned, populated during Stage S2):

* ControllerSettings — controller type, gains, output limits
* IOSelection — input/output selection state
* SimulationSettings — duration, dt, solver preferences
* PlotLayout — 4-slot plot configuration with channel_selection.kind
* PlotSlotConfig — per-slot plot type and reference

Phase 2 contents (planned, populated during Stage S5):

* StabilityAnalysisArtifact — A/B/C/D matrices, eigenvalues, frequency response

References
----------
* ADR-006: Controller Owns Transfer-Function and State-Space Builders
* ADR-013: StabilityAnalysisArtifact
* ADR-016: channel_selection.kind Schema
* `specs/03_configuration_requirements.md`
* `specs/05_simulation_and_results_requirements.md` §16
"""

__all__: list[str] = []
