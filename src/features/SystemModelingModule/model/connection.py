"""Connection: data layer dataclass for a wire between two component ports.

Identity follows the hybrid ULID model with the `con_` prefix (ADR-002,
`02 §8.6`). Endpoints are semantic `(component_id, port_id)` references —
index-only references are forbidden as canonical identity. The connection
schema follows `02 §14.2`; routing follows `02 §16`; future-proof style
fields follow `02 §39`.

This module is part of the data layer. It must not import any Qt UI classes.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `specs/02_workspace_requirements.md` §8.6 (Connection IDs)
* `specs/02_workspace_requirements.md` §14 (Connection System)
* `specs/02_workspace_requirements.md` §16 (Connection Routing)
* `specs/02_workspace_requirements.md` §39 (Visual Properties / Bond Graph
  Preparation)
* `specs/09_coding_standards.md` §5.6 (Pydantic and Dataclasses)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# Routing styles supported in Phase 1 per `02 §16.1`. `bezier` is reserved
# for a future phase and intentionally excluded from the type alias.
RoutingStyle = Literal["straight", "orthogonal"]

# A waypoint is an `(x, y)` point in scene coordinates. Connections may
# carry an ordered sequence of them per `02 §16.2`.
Waypoint = tuple[float, float]


@dataclass(frozen=True)
class PortRef:
    """Semantic reference to a port on a specific component instance.

    The `(component_id, port_id)` pair is the canonical identity per the
    S3 rule: index-only references are forbidden. `component_id` is the
    internal ULID of a `ComponentInstance` (e.g., `cmp_01HV...`);
    `port_id` is the port identifier defined in the component's
    `PortDefinition` set (e.g., `"p"`, `"flange_a"`).

    Attributes:
        component_id: Internal ULID of the referenced component.
        port_id: Port identifier as declared in the component
            definition.

    See Also:
        `02 §13` (Port System), `02 §14.2` (Connection schema).
    """

    component_id: str
    port_id: str


@dataclass(frozen=True)
class ConnectionRouting:
    """Routing description for a connection wire.

    Phase 1 accepts `straight` or `orthogonal` styles (`02 §16.1`).
    Waypoints are stored even when manual editing is not yet exposed,
    so future manual shaping can be added without a schema change
    (`02 §16.2`).

    Attributes:
        style: Routing style. Defaults to `"orthogonal"` per the
            engineering-diagram preference in `02 §16.1`.
        waypoints: Ordered tuple of `(x, y)` scene-coordinate
            waypoints. Empty tuple means "auto-route end-to-end."
            Tuple (not list) for frozen-correctness.
    """

    style: RoutingStyle = "orthogonal"
    waypoints: tuple[Waypoint, ...] = ()


@dataclass(frozen=True)
class Connection:
    """Wire between two component ports.

    The dataclass is frozen so that mutations go through the command
    stack (ADR-005): an edit (e.g., re-target an endpoint) produces a
    new `Connection` with the same `id` rather than mutating in place.
    Nested containers (`style`, `metadata`, `extensions`) remain
    mutable for pragmatic reasons; convention is to copy on edit.

    Attributes:
        id: Internal stable ULID with the `con_` prefix
            (e.g., `"con_01HV..."`). Generated at creation and never
            changed (`02 §8.2`, ADR-002).
        display_id: System-generated human-readable identifier
            (e.g., `"conn_12"`). Note the prefix asymmetry: internal
            IDs use `con_` while display IDs use `conn_` per the
            example in `02 §8.6`.
        source: Endpoint reference at the source side of the
            connection.
        target: Endpoint reference at the target side. Phase 1
            connections are conceptually undirected for physical
            domains; `source`/`target` is a draw-time convention.
        routing: Routing style and waypoints.
        label: Optional user-facing wire label. Empty string when
            unset.
        style: Optional visual overrides. Reserved fields per
            `02 §39`: `line_width`, `color_override`, `dash_pattern`,
            `arrow_style`, `causality_marker`. Phase 1 does not
            interpret these but must preserve them across save/load.
        metadata: Reserved for non-load-bearing supplementary data.
            Unknown fields preserved across save/load.
        extensions: Reserved for forward-compatible extension fields,
            including future Bond Graph metadata (`02 §39`).

    See Also:
        `02 §14`, `02 §16`, `02 §39`, ADR-002.
    """

    id: str
    display_id: str
    source: PortRef
    target: PortRef
    routing: ConnectionRouting = field(default_factory=ConnectionRouting)
    label: str = ""
    style: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "Connection",
    "ConnectionRouting",
    "PortRef",
    "RoutingStyle",
    "Waypoint",
]
