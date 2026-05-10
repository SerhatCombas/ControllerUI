"""shared/types: cross-feature common type aliases and enums.

Per `06 §5.5`. Phase 1 surface:

* `DomainId` — physical domain identifier (Literal)
* `PortKind` — port-direction enumeration (Literal)

Additional Phase 1+ types (`ComponentCategory`, `ValidationSeverity`,
`PlotType`, `ControllerType`) land in their owning stages and are
added to this package as they become needed.
"""

from .domain import DomainId
from .port_kind import PortKind

__all__ = [
    "DomainId",
    "PortKind",
]
