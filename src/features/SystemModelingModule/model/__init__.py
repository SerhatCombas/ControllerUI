"""Data layer for SystemModelingModule.

Re-exports the public API of the model subpackage. UI code imports
from this package, not from individual files.

The `model/` subfolder is the data-layer source of truth for this
module. It must not import Qt UI modules; it may use `QObject` and
`Signal` from `PySide6.QtCore` for change notification but must
remain testable without instantiating any QWidget.

Phase 1 contents (planned, populated during Stage S1):

* WorkspaceModel — source of truth for components, connections, validation
* ComponentInstance — component placement dataclass
* Connection — connection between component ports
* SelectionModel — current selection state
* WorkspaceIdGenerator — ULID + display ID generation
* ValidationReport — structured validation issues
* migrations/ — schema migration registry

References
----------
* ADR-003: Workspace UI/Data Separation (`decisions/ADR-003-workspace-ui-data-separation.md`)
* `specs/02_workspace_requirements.md`
* `specs/06_data_flow_and_architecture.md` §4.2
"""

# Public API will be re-exported here as the package is populated:
# from .workspace_model import WorkspaceModel
# from .component_instance import ComponentInstance
# from .connection import Connection
# from .selection_model import SelectionModel
# from .id_generator import WorkspaceIdGenerator
# from .validation_report import ValidationReport, ValidationSeverity

__all__: list[str] = []
