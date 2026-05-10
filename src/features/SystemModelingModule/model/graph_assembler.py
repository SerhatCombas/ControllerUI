"""GraphAssembler: converts workspace state into a `SystemGraph` snapshot.

Owned by `SystemModelingModule` per `06 §4.2` ("assemble
SystemGraph from workspace data"). The assembler is the producer
of the `shared/graph/SystemGraph` artifact; cross-feature readers
(Phase 2+) consume the resulting `SystemGraph` directly.

Phase 1 scope (S1.5, Step Group E):

* Build the connection adjacency graph from workspace edges.
* Compute implicit nodes via BFS over the adjacency graph
  (`02 §18`). Phase 1 uses a naïve BFS rather than a union-find /
  disjoint-set structure; the scale (`~100` components, `~300`
  connections per `02 §31`) does not require the asymptotically
  faster algorithm, and BFS is easier to reason about during
  initial reviews. Phase 2+ can swap in union-find without
  changing the public API.
* Resolve each node's domain via the supplied `port_lookup`
  callable (same shape as `GraphValidator` for consistency).
* Mark mixed-domain nodes with `domain=None` per `02 §18.1`.

Phase 1 does NOT:

* persist implicit nodes (`02 §8.7`, `02 §29.2`)
* re-validate the workspace (validator runs at the command layer,
  S1.7, before the raw mutator runs; assembly is post-mutation)
* iterate `connections` more than once (the input iterable is
  materialized into a list so disconnected-port detection and
  identifier collection can both run from the same snapshot)

The assembler is **state-free**: the class exists for future
extension (configuration, caching, profiling hooks) without
forcing call-site changes. Per `02 §19`, graph assembly must be
independent from UI; this class imports no Qt classes.

References:
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `specs/02_workspace_requirements.md` §17 (Implicit Node
  Behavior), §18 (Implicit Node Assembly), §18.1 (Node Domain
  Rule), §18.2 (Cross-Domain Components), §19 (Graph Assembly),
  §31 (Performance Targets)
* `specs/06_data_flow_and_architecture.md` §4.2
  (SystemModelingModule responsibilities), §5.3 (shared/graph)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.graph.implicit_node import ImplicitNode
from shared.graph.system_graph import SystemGraph

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from shared.graph.port_ref import PortRef

    from .component_instance import ComponentInstance
    from .connection import Connection


class GraphAssembler:
    """Assembles a `SystemGraph` snapshot from workspace state.

    Stateless in Phase 1; the class exists for future extension
    without forcing call-site changes. The single public method
    `assemble` returns a frozen `SystemGraph`.

    The assembler does NOT mutate the input. Callers supply
    snapshots; the assembler reads them and produces a new
    `SystemGraph`.
    """

    def assemble(
        self,
        *,
        components: Mapping[str, ComponentInstance],
        connections: Iterable[Connection],
        port_lookup: Callable[[PortRef], str | None],
    ) -> SystemGraph:
        """Compute the `SystemGraph` for a workspace snapshot.

        Algorithm (`02 §18`):

        1. Materialize `connections` into a list so it can be
           iterated twice (adjacency build + identifier
           collection).
        2. Build an undirected adjacency mapping: each `PortRef`
           maps to the set of `PortRef`s it is connected to.
        3. Iterate `PortRef` keys in lexicographic order
           (`(component_id, port_id)`) for deterministic node
           ordering. For each unvisited key, BFS the connected
           component and emit one `ImplicitNode`.
        4. Resolve each node's domain via `port_lookup`. If all
           non-`None` port-lookup results agree, that is the
           node's domain. Otherwise `domain=None` (mixed per
           `02 §18.1`, or undeterminable due to a missing port).

        Self-connections (a connection whose source and target
        ports are identical) produce a single-port node — the BFS
        visits the port once and emits a node containing it.
        Validator (S1.4) rejects self-connections before they
        reach the workspace under normal flow; this branch
        handles direct mutation or load-time corruption per
        `02 §29.5` (partial load failure tolerance).

        Disconnected ports (no incident edge) are NOT represented
        as nodes in Phase 1. They do not appear in the adjacency
        mapping and therefore not in `implicit_nodes`. Subsequent
        validation pipelines (S1.6+) flag dangling required ports
        via separate checks.

        Args:
            components: Snapshot of `component_id` →
                `ComponentInstance`. Identifier list is taken from
                `components.keys()` in mapping order. Component
                bodies are not inspected here; the mapping serves
                as the identifier source.
            connections: Snapshot of connection records. Iterated
                once (materialized into a list internally to
                support both adjacency build and identifier
                collection).
            port_lookup: Callable that maps a `PortRef` to the
                port's domain string, or `None` if the port does
                not exist on its component. Same contract as
                `GraphValidator.validate_connection_candidate`.

        Returns:
            Frozen `SystemGraph` carrying:
                - `component_ids` from `components.keys()`
                - `connection_ids` from each connection's `id`
                - `implicit_nodes` computed by BFS
        """
        connection_list = list(connections)

        # Build adjacency. Self-connections register a self-loop;
        # set-of-neighbors deduplicates duplicate edges defensively.
        adjacency: dict[PortRef, set[PortRef]] = {}
        for connection in connection_list:
            adjacency.setdefault(connection.source, set()).add(connection.target)
            adjacency.setdefault(connection.target, set()).add(connection.source)

        # BFS over the adjacency graph. Sort keys for deterministic
        # node ordering across runs and platforms.
        visited: set[PortRef] = set()
        nodes: list[ImplicitNode] = []
        node_counter = 0

        for start in sorted(
            adjacency.keys(),
            key=lambda ref: (ref.component_id, ref.port_id),
        ):
            if start in visited:
                continue
            node_counter += 1
            port_refs = _bfs_connected_ports(start, adjacency, visited)
            domain = _resolve_node_domain(port_refs, port_lookup)
            nodes.append(
                ImplicitNode(
                    id=f"node_{node_counter}",
                    port_refs=tuple(port_refs),
                    domain=domain,
                )
            )

        return SystemGraph(
            component_ids=tuple(components.keys()),
            connection_ids=tuple(connection.id for connection in connection_list),
            implicit_nodes=tuple(nodes),
        )


def _bfs_connected_ports(
    start: PortRef,
    adjacency: dict[PortRef, set[PortRef]],
    visited: set[PortRef],
) -> list[PortRef]:
    """BFS the connected component containing `start`.

    `visited` is updated in place; the returned list carries the
    BFS-traversal-order port refs for the connected component.
    """
    component_ports: list[PortRef] = []
    queue: list[PortRef] = [start]
    while queue:
        ref = queue.pop(0)
        if ref in visited:
            continue
        visited.add(ref)
        component_ports.append(ref)
        # Sort neighbors for deterministic traversal order. set()
        # iteration order is insertion-order in CPython but the
        # public BFS contract should not rely on that.
        for neighbor in sorted(
            adjacency.get(ref, ()),
            key=lambda r: (r.component_id, r.port_id),
        ):
            if neighbor not in visited:
                queue.append(neighbor)
    return component_ports


def _resolve_node_domain(
    port_refs: list[PortRef],
    port_lookup: Callable[[PortRef], str | None],
) -> str | None:
    """Return the consensus domain of `port_refs`, or `None` if mixed.

    Mixed means at least two distinct non-`None` domains appear in
    the port set per `02 §18.1`. If `port_lookup` returns `None`
    for every port (no ports resolvable), the result is also
    `None` — there is no positive evidence of a consistent
    domain, which subsequent validation treats as a violation.

    Args:
        port_refs: Ports in the implicit node.
        port_lookup: Callable mapping `PortRef` to domain string
            or `None`.

    Returns:
        The single agreed domain, or `None` for mixed / undeterminable.
    """
    seen_domains: set[str] = set()
    for ref in port_refs:
        domain = port_lookup(ref)
        if domain is not None:
            seen_domains.add(domain)
    if len(seen_domains) == 1:
        return next(iter(seen_domains))
    return None


__all__ = ["GraphAssembler"]
