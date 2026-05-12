"""shared/types: cross-feature common type aliases and enums.

Per `06 §5.5`. Phase 1 surface:

* `DomainId` — physical domain identifier (Literal)
* `PortKind` — port-direction enumeration (Literal)
* `PhysicalAttributes` — component physical-attribute flags
  (`02 §11.2`) with `BoundaryKind`, `MotionKind`, `SourceKind`
  closed-set enums
* `ValidationReport` family — structured validation result types
  shared across `SystemModelingModule.GraphValidator` and
  `ControllerDesignModule.ConfigurationValidator`
* `ComponentInstanceLike` — read-only Protocol view of a workspace
  component instance for cross-feature consumers
"""

from .component_protocols import ComponentInstanceLike
from .domain import DomainId
from .physical_attributes import (
    BoundaryKind,
    MotionKind,
    PhysicalAttributes,
    SourceKind,
)
from .port_kind import PortKind
from .validation_report import (
    SubjectKind,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)

__all__ = [
    "BoundaryKind",
    "ComponentInstanceLike",
    "DomainId",
    "MotionKind",
    "PhysicalAttributes",
    "PortKind",
    "SourceKind",
    "SubjectKind",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
]
