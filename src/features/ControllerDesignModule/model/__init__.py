"""Data layer for ControllerDesignModule.

Re-exports the public API of the model subpackage. UI code imports
from this package, not from individual files.

Phase 1 contents (Stage S2.A scaffold):

* ControllerSettings / ControllerSpec — controller list + per-entry
  schema (spec/03 §5)
* IOSelection / IOEntry / IOSource / IOSourcePortRef — I/O list +
  tagged-union source variants (spec/03 §6)
* SimulationSettings / InitialConditions / InitialConditionOverride
  — duration, solver, initial-conditions schema (spec/03 §7)
* ULID identity helpers — `new_controller_id`, `new_io_input_id`,
  `new_io_output_id`, plus prefix predicates

Phase 1 contents (planned, populated during Stages S2.B-S2.F):

* validation helpers (S2.B)
* default_config bootstrap (S2.B)
* signal emitters (S2.D)
* persistence I/O (S2.E)
* PlotLayout / PlotSlotConfig / ChannelSelection (S2.C — see
  ADR-016 / ADR-017)

Phase 2 contents (planned, populated during Stage S5):

* StabilityAnalysisArtifact — A/B/C/D matrices, eigenvalues,
  frequency response

References:
----------
* ADR-006: Controller Owns Transfer-Function and State-Space Builders
* ADR-013: StabilityAnalysisArtifact
* ADR-016: channel_selection.kind Schema
* ADR-017: Mirror Sync Plot Dropdowns
* `specs/03_configuration_requirements.md`
* `specs/05_simulation_and_results_requirements.md` §16
"""

from .configuration_model import ConfigurationModel
from .configuration_validator import ConfigurationValidator
from .controller_settings import ControllerSettings, ControllerSpec
from .defaults import (
    DefaultConfiguration,
    load_default_configuration,
    load_default_controller_settings,
    load_default_io_selection,
    load_default_simulation_settings,
)
from .id_generator import (
    CONTROLLER_ID_PREFIX,
    IO_INPUT_ID_PREFIX,
    IO_OUTPUT_ID_PREFIX,
    is_controller_id,
    is_io_input_id,
    is_io_output_id,
    new_controller_id,
    new_io_input_id,
    new_io_output_id,
)
from .io_selection import (
    BondGraphVariable,
    IOEntry,
    IOEntryStatus,
    IOSelection,
    IOSource,
    IOSourcePortRef,
    io_source_from_dict,
)
from .simulation_settings import (
    InitialConditionOverride,
    InitialConditions,
    InitialConditionsSource,
    SimulationSettings,
)

__all__: list[str] = [
    "CONTROLLER_ID_PREFIX",
    "IO_INPUT_ID_PREFIX",
    "IO_OUTPUT_ID_PREFIX",
    "BondGraphVariable",
    "ConfigurationModel",
    "ConfigurationValidator",
    "ControllerSettings",
    "ControllerSpec",
    "DefaultConfiguration",
    "IOEntry",
    "IOEntryStatus",
    "IOSelection",
    "IOSource",
    "IOSourcePortRef",
    "InitialConditionOverride",
    "InitialConditions",
    "InitialConditionsSource",
    "SimulationSettings",
    "io_source_from_dict",
    "is_controller_id",
    "is_io_input_id",
    "is_io_output_id",
    "load_default_configuration",
    "load_default_controller_settings",
    "load_default_io_selection",
    "load_default_simulation_settings",
    "new_controller_id",
    "new_io_input_id",
    "new_io_output_id",
]
