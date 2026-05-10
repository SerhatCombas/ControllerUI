"""PortDefinition: metadata-driven port declaration.

Per `02 §13`. A `PortDefinition` declares one port on a component
definition: identifier, display name, domain, kind, visual
anchor, and required flag. `ComponentInstance` references ports
by id through `PortRef(component_id, port_id)`; the graph layer
resolves the port to its definition via the registry lookup or
the supplied `port_lookup` callable in `GraphValidator` /
`GraphAssembler`.

Phase 1 accepts only `kind="bidirectional"` per `02 §13.1`;
other `PortKind` values are reserved for Phase 1.5+ and are
declared in the `PortKind` Literal but rejected by registry
validation in Phase 1.

References:
----------
* `specs/02_workspace_requirements.md` §13 (Port System),
  §13.1 (Port Kinds), §13.2 (Domain Rule)
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shared.types.domain import DomainId
    from shared.types.port_kind import PortKind


@dataclass(frozen=True, slots=True)
class PortDefinition:
    """Metadata-driven port declaration for a component definition.

    Attributes:
        id: Port identifier unique within the parent component
            (e.g., `"p"`, `"n"`, `"flange_a"`).
        display_name: User-facing port label
            (e.g., `"Positive"`, `"Flange A"`).
        domain: Physical domain of the port per `02 §13.2`. Must
            match the parent component's `domain` for
            single-domain components; cross-domain components
            (`02 §18.2`) declare per-port domains independently.
        kind: Port direction kind. Phase 1 accepts only
            `"bidirectional"`; future kinds are reserved in the
            `PortKind` Literal.
        relative_position: `(x, y)` of the port's visual anchor
            relative to the component bounding box, in `[0, 1]`
            unit coordinates (e.g., `(1.0, 0.5)` for right-edge
            middle).
        required: When `True`, a placed component must have this
            port connected (or dangling-required-port validation
            flags it, S1.6+).
        metadata: Forward-compatibility container per `02 §11.1`.
        extensions: Forward-compatibility container for
            domain-specific extension fields (e.g., future Bond
            Graph causality marker per `02 §39`).

    See Also:
        `02 §13`, `02 §18.2`.
    """

    id: str
    display_name: str
    domain: DomainId
    kind: PortKind = "bidirectional"
    relative_position: tuple[float, float] = (0.0, 0.0)
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)


__all__ = ["PortDefinition"]
