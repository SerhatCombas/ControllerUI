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

from shared.graph.port_ref import PortRef

# Routing styles supported in Phase 1 per `02 §16.1`. `bezier` is reserved
# for a future phase and intentionally excluded from the type alias.
RoutingStyle = Literal["straight", "orthogonal"]

# A waypoint is an `(x, y)` point in scene coordinates. Connections may
# carry an ordered sequence of them per `02 §16.2`.
Waypoint = tuple[float, float]

# PortRef is re-exported here for backwards compatibility with existing
# import sites (`from features.SystemModelingModule.model.connection import
# PortRef`). The canonical definition lives in `shared/graph/port_ref.py`
# per `06 §5.3` so cross-feature readers can use it without crossing the
# architecture boundary into `features/SystemModelingModule/`.


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a 2-key dict (S2.E).

        Waypoints become JSON-friendly nested lists `[[x, y], ...]`.
        Unknown future style values pass through verbatim.
        """
        return {
            "style": self.style,
            "waypoints": [[w[0], w[1]] for w in self.waypoints],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectionRouting:
        """Inverse of `to_dict`. Missing fields fall back to defaults."""
        style_raw = payload.get("style", "orthogonal")
        waypoints_raw = payload.get("waypoints", []) or []
        waypoints: tuple[Waypoint, ...] = tuple(
            (float(w[0]), float(w[1]))
            for w in waypoints_raw
            if isinstance(w, list | tuple) and len(w) == 2
        )
        return cls(style=style_raw, waypoints=waypoints)


# Known top-level fields recognized by `Connection.from_dict`; anything
# else is routed into `extensions` per spec/02 §29.4.
_CONNECTION_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "display_id",
        "source",
        "target",
        "routing",
        "label",
        "style",
        "metadata",
        "extensions",
    }
)


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a project-file dict (S2.E).

        Nested value types (`source`, `target`, `routing`) recurse via
        their own `to_dict`. Mutable container fields (`style`,
        `metadata`, `extensions`) are deep-copied so callers cannot
        mutate the value type through the returned payload.
        """
        return {
            "id": self.id,
            "display_id": self.display_id,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "routing": self.routing.to_dict(),
            "label": self.label,
            "style": dict(self.style),
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Connection:
        """Inverse of `to_dict`. Required identity fields raise on absence."""
        for required in ("id", "display_id", "source", "target"):
            if required not in payload:
                raise KeyError(f"Connection payload missing '{required}'")
        source_payload = payload["source"]
        target_payload = payload["target"]
        if not isinstance(source_payload, dict):
            raise ValueError("Connection.source must be a JSON object")
        if not isinstance(target_payload, dict):
            raise ValueError("Connection.target must be a JSON object")
        routing_payload = payload.get("routing", {}) or {}
        if not isinstance(routing_payload, dict):
            routing_payload = {}
        carry = {k: v for k, v in payload.items() if k not in _CONNECTION_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            id=str(payload["id"]),
            display_id=str(payload["display_id"]),
            source=PortRef.from_dict(source_payload),
            target=PortRef.from_dict(target_payload),
            routing=ConnectionRouting.from_dict(routing_payload),
            label=str(payload.get("label", "")),
            style=dict(payload.get("style", {}) or {}),
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


__all__ = [
    "Connection",
    "ConnectionRouting",
    "PortRef",
    "RoutingStyle",
    "Waypoint",
]
