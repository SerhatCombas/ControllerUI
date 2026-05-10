"""ImplicitNode: graph-layer value type for connected port groups.

An implicit node groups ports that share the same physical
potential / across variable per `02 §17`. Computed by
`GraphAssembler` (owned by `features/SystemModelingModule/model/`
per `06 §4.2`) from the workspace's connection edges.

Implicit nodes are runtime-derived and not persisted as primary
project data per `02 §8.7`; their IDs (`node_<n>`) are valid only
for the assembled graph instance carrying them and must not be
stored as stable project references.

References:
----------
* `specs/02_workspace_requirements.md` §17 (Junction and Implicit
  Node Behavior), §18 (Implicit Node Assembly), §8.7 (Implicit
  Node IDs)
* `specs/06_data_flow_and_architecture.md` §5.3 (shared/graph)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .port_ref import PortRef


@dataclass(frozen=True, slots=True)
class ImplicitNode:
    """A connected group of ports sharing one physical potential.

    Produced by `GraphAssembler.assemble()` from the workspace's
    connection edges. Each node carries a runtime-only ID and the
    tuple of `PortRef` instances it includes (insertion order from
    BFS traversal in the assembler).

    The `domain` field is the resolved domain string when all ports
    in the node agree (e.g., `"electrical_analog"`), or `None` when
    the node has a mixed-domain violation per `02 §18.1`.
    Subsequent validation pipelines (S1.6+) check `domain is None`
    to flag invalid mixed-domain nodes.

    Multi-domain components (`02 §18.2`) expose separate ports per
    domain; each port joins a single-domain node. The mixed-domain
    case (`domain is None`) only arises when distinct domains are
    merged by a connection, which is a workspace-validation error
    that should not survive the connection validator (S1.4) under
    normal flow.

    Attributes:
        id: Runtime identifier (`node_<n>`, e.g., `"node_1"`).
            Stable only for the graph instance carrying it; never
            persisted (`02 §8.7`).
        port_refs: Tuple of `PortRef` instances in this node,
            in BFS-traversal order.
        domain: Resolved domain string when all ports agree, or
            `None` if the node has a mixed-domain violation per
            `02 §18.1`.

    See Also:
        `02 §17`, `02 §18`, `02 §8.7`.
    """

    id: str
    port_refs: tuple[PortRef, ...]
    domain: str | None


__all__ = ["ImplicitNode"]
