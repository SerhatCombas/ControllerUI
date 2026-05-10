"""SystemGraph: frozen snapshot of assembled workspace graph (Phase 1).

Read-only derived structure produced by
`GraphAssembler.assemble()` (owned by
`features/SystemModelingModule/model/` per `06 §4.2`). The graph
is intended for cross-feature read-only consumption (e.g.,
`ControllerDesignModule` reads `SystemGraph` for state-space
preparation in Phase 2+).

Phase 1 scope: `SystemGraph` carries identifier sets and the
derived `implicit_nodes`. Component and connection **bodies** are
NOT included in Phase 1: `ComponentInstance` and `Connection`
live in `features/SystemModelingModule/model/`, and `shared/`
cannot import `features/` (per the architecture boundary
enforced by `tests/architecture/test_module_boundaries.py`).

`02 §19` lists "component instances" and "connections" as graph
contents — Phase 1 partially honors this via the `component_ids`
and `connection_ids` tuples (identifier references). Phase 2+
will widen the schema either through:

* a `Protocol`-typed snapshot pair (`ComponentLike`,
  `ConnectionLike`) declared in `shared/types/`, supplied by the
  caller; or
* the artifact-passing pattern, where component / connection
  bodies travel alongside `SystemGraph` as separate cross-feature
  payloads.

Phase 1 cross-feature consumers (none yet exist; the contract is
forward-looking) can resolve component / connection bodies by
holding a reference to `WorkspaceModel.components` /
`.connections` mappings; identifiers in `SystemGraph` are keys
into those mappings.

References:
----------
* `specs/02_workspace_requirements.md` §19 (Graph Assembly)
* `specs/06_data_flow_and_architecture.md` §5.3 (shared/graph),
  §4.2 (SystemModelingModule responsibilities)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .implicit_node import ImplicitNode


@dataclass(frozen=True, slots=True)
class SystemGraph:
    """Frozen snapshot of an assembled workspace graph.

    Phase 1 carries identifier sets and computed implicit nodes;
    component / connection bodies are referenced by ID (the caller
    resolves bodies via its own `WorkspaceModel` snapshot or a
    parallel mapping).

    The empty graph is the default (`SystemGraph()`); it is
    structurally valid and represents an empty workspace.

    Attributes:
        component_ids: Tuple of `cmp_<ULID>` identifiers present
            in the source workspace at assembly time. Order is
            caller-provided (typically `Mapping.keys()` order from
            `WorkspaceModel.components`).
        connection_ids: Tuple of `con_<ULID>` identifiers present
            in the source workspace at assembly time. Order is
            caller-provided.
        implicit_nodes: Tuple of `ImplicitNode` instances computed
            from the connection edges. Order is assembly-defined
            (BFS traversal starting from the lexicographically
            smallest `PortRef` in each connected component, for
            determinism). Disconnected ports do not produce nodes
            in Phase 1 (only connected port groups are
            represented).

    See Also:
        `02 §19`, `02 §17`, `02 §18`, `06 §5.3`.
    """

    component_ids: tuple[str, ...] = ()
    connection_ids: tuple[str, ...] = ()
    implicit_nodes: tuple[ImplicitNode, ...] = ()

    def is_empty(self) -> bool:
        """True if the graph carries no components, connections, or nodes."""
        return not self.component_ids and not self.connection_ids and not self.implicit_nodes


__all__ = ["SystemGraph"]
