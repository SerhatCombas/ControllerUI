"""PortRef: vertex reference value type for graph structures.

`(component_id, port_id)` pair used as:

* `Connection.source` / `Connection.target` (workspace storage,
  owned by `features/SystemModelingModule/model/connection.py`)
* `ImplicitNode.port_refs` (graph layer, derived)
* `GraphValidator` API arguments (validator surface)

Located in `shared/graph/` per `06 §5.3` so that cross-feature
consumers (e.g., future `ControllerDesignModule` graph readers)
can use it without crossing the architecture boundary into
`features/SystemModelingModule/`.
`features/SystemModelingModule/model/connection.py` re-exports
`PortRef` for backwards compatibility with existing import sites.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `specs/02_workspace_requirements.md` §13 (Port System), §14.2
  (Connection Data Model)
* `specs/06_data_flow_and_architecture.md` §5.3 (shared/graph)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortRef:
    """Semantic reference to a port on a specific component instance.

    The `(component_id, port_id)` pair is the canonical identity per
    the S3 rule: index-only references are forbidden. `component_id`
    is the internal ULID of a `ComponentInstance` (e.g.,
    `"cmp_01HV..."`); `port_id` is the port identifier defined in
    the component's `PortDefinition` set (e.g., `"p"`,
    `"flange_a"`).

    Frozen + slots: hashable for use as `set` / `dict` keys (e.g.,
    BFS visited sets in `GraphAssembler`).

    Attributes:
        component_id: Internal ULID of the referenced component.
        port_id: Port identifier as declared in the component
            definition.

    See Also:
        `02 §13` (Port System), `02 §14.2` (Connection schema),
        `02 §18` (Implicit Node Assembly).
    """

    component_id: str
    port_id: str


__all__ = ["PortRef"]
