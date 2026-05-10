"""shared/types: cross-feature common type aliases and enums.

Per `06 §5.5`. Phase 1 surface:

* `DomainId` — physical domain identifier (Literal)
* `PortKind` — port-direction enumeration (Literal)
* `PhysicalAttributes` — component physical-attribute flags
  (`02 §11.2`) with `BoundaryKind`, `MotionKind`, `SourceKind`
  closed-set enums

Additional Phase 1+ types (`ComponentCategory`, `ValidationSeverity`,
`PlotType`, `ControllerType`) land in their owning stages and are
added to this package as they become needed.
"""

from .domain import DomainId
from .physical_attributes import (
    BoundaryKind,
    MotionKind,
    PhysicalAttributes,
    SourceKind,
)
from .port_kind import PortKind

__all__ = [
    "BoundaryKind",
    "DomainId",
    "MotionKind",
    "PhysicalAttributes",
    "PortKind",
    "SourceKind",
]
