"""Data layer for SystemModelingModule.

Re-exports the public API of the model subpackage. UI code imports
from this package, not from individual files.

The `model/` subfolder is the data-layer source of truth for this
module. It must not import Qt UI modules; it may use `QObject` and
`Signal` from `PySide6.QtCore` for change notification but must
remain testable without instantiating any QWidget.

Phase 1 contents (populated incrementally during Stage S1):

* ComponentInstance — placed-component dataclass (S1.1)
* Connection — wire dataclass between component ports (S1.1)
* WorkspaceIdGenerator — ULID + display ID generation (S1.1)
* ValidationReport — structured validation issues (S1.2)
* SelectionModel — current selection state (S1.2)
* WorkspaceModel — source of truth (planned, S1.3)
* migrations/ — schema migration registry (planned)

References:
----------
* ADR-003: Workspace UI/Data Separation (`decisions/ADR-003-workspace-ui-data-separation.md`)
* `specs/02_workspace_requirements.md`
* `specs/06_data_flow_and_architecture.md` §4.2
"""

from .component_instance import (
    BoundaryKind,
    ComponentInstance,
    MotionKind,
    PhysicalAttributes,
    SourceKind,
    VisualSpec,
)
from .connection import (
    Connection,
    ConnectionRouting,
    PortRef,
    RoutingStyle,
    Waypoint,
)
from .id_generator import WorkspaceIdGenerator
from .selection_model import SelectionModel, SelectionSnapshot
from .validation_report import (
    SubjectKind,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from .workspace_model import WorkspaceModel

__all__ = [
    "BoundaryKind",
    "ComponentInstance",
    "Connection",
    "ConnectionRouting",
    "MotionKind",
    "PhysicalAttributes",
    "PortRef",
    "RoutingStyle",
    "SelectionModel",
    "SelectionSnapshot",
    "SourceKind",
    "SubjectKind",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
    "VisualSpec",
    "Waypoint",
    "WorkspaceIdGenerator",
    "WorkspaceModel",
]
