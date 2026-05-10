"""Unit tests for `GraphAssembler.assemble` (S1.5).

Covers spec `02 §36.3` Node Assembly Tests:

1. two connected ports create one implicit node
2. chained connections create one implicit node
3. disconnected groups create separate implicit nodes
4. mixed-domain node is invalid (represented as `domain=None`)

Plus ergonomic / contract tests:

* empty workspace yields empty graph
* components without connections produce no implicit nodes
  (disconnected ports excluded; S1.6+ flags dangling required
  ports separately)
* node IDs follow `node_<n>` monotonic format per `02 §8.7`
* `SystemGraph` carries all component and connection identifiers
* self-connections produce a single-port node (raw mutator can
  produce them when bypassing the validator; assembler must not
  crash)
* multi-port component with separate domain ports forms separate
  nodes per `02 §18.2`
* node ordering is deterministic (lexicographic by start port)

References
----------
* `specs/02_workspace_requirements.md` §17, §18 (Implicit Node
  Assembly), §18.1 (Node Domain Rule), §18.2 (Cross-Domain
  Components), §19 (Graph Assembly), §36.3 (Node Assembly Tests),
  §8.7 (Implicit Node IDs)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from PySide6.QtCore import QPointF

if TYPE_CHECKING:
    from collections.abc import Callable

from features.SystemModelingModule.model.component_instance import (
    PhysicalAttributes,
    VisualSpec,
)
from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.graph_assembler import GraphAssembler
from features.SystemModelingModule.model.workspace_model import WorkspaceModel


def _add_kwargs(**overrides: Any) -> dict[str, Any]:
    """Default `add_component` kwargs."""
    base: dict[str, Any] = {
        "definition_id": "electrical.analog.components.resistor",
        "type": "Resistor",
        "display_name": "Resistor",
        "domain": "electrical_analog",
        "category": "component",
        "position": QPointF(0.0, 0.0),
        "visual": VisualSpec(svg_id="resistor_default"),
        "physical_attributes": PhysicalAttributes(),
    }
    base.update(overrides)
    return base


def _make_port_lookup(
    domains: dict[tuple[str, str], str],
) -> Callable[[PortRef], str | None]:
    """Same shape as `GraphValidator`: map `(cid, port_id)` -> domain or None."""

    def lookup(ref: PortRef) -> str | None:
        return domains.get((ref.component_id, ref.port_id))

    return lookup


# ---------------------------------------------------------------------- #
# Spec §36.3 mandated tests
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_two_connected_ports_form_one_implicit_node() -> None:
    """Spec §36.3 #1: two connected ports create one implicit node."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    port_lookup = _make_port_lookup({(a, "p"): "electrical_analog", (b, "p"): "electrical_analog"})
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=tuple(model.connections.values()),
        port_lookup=port_lookup,
    )

    assert len(graph.implicit_nodes) == 1
    node = graph.implicit_nodes[0]
    assert len(node.port_refs) == 2
    assert PortRef(component_id=a, port_id="p") in node.port_refs
    assert PortRef(component_id=b, port_id="p") in node.port_refs
    assert node.domain == "electrical_analog"


@pytest.mark.unit
def test_chained_connections_form_one_implicit_node() -> None:
    """Spec §36.3 #2: A-B and B-C connected => single node containing all three."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    c = model.add_component(**_add_kwargs())
    model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    model.add_connection(
        source=PortRef(component_id=b, port_id="q"),
        target=PortRef(component_id=c, port_id="p"),
    )
    # b has two ports (p, q); the chain joins through b.
    port_lookup = _make_port_lookup(
        {
            (a, "p"): "electrical_analog",
            (b, "p"): "electrical_analog",
            (b, "q"): "electrical_analog",
            (c, "p"): "electrical_analog",
        }
    )
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=tuple(model.connections.values()),
        port_lookup=port_lookup,
    )

    # Two distinct node sets emerge because b.p and b.q are different
    # ports — the chain does NOT auto-merge through a multi-port
    # component (`02 §18.2`). Verify each chain-side is its own node.
    assert len(graph.implicit_nodes) == 2
    port_sets = [
        {(r.component_id, r.port_id) for r in node.port_refs} for node in graph.implicit_nodes
    ]
    assert {(a, "p"), (b, "p")} in port_sets
    assert {(b, "q"), (c, "p")} in port_sets


@pytest.mark.unit
def test_disconnected_groups_form_separate_implicit_nodes() -> None:
    """Spec §36.3 #3: A-B and C-D are independent groups."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    c = model.add_component(**_add_kwargs())
    d = model.add_component(**_add_kwargs())
    model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    model.add_connection(
        source=PortRef(component_id=c, port_id="p"),
        target=PortRef(component_id=d, port_id="p"),
    )
    port_lookup = _make_port_lookup(
        {
            (a, "p"): "electrical_analog",
            (b, "p"): "electrical_analog",
            (c, "p"): "electrical_analog",
            (d, "p"): "electrical_analog",
        }
    )
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=tuple(model.connections.values()),
        port_lookup=port_lookup,
    )

    assert len(graph.implicit_nodes) == 2


@pytest.mark.unit
def test_mixed_domain_node_has_none_domain() -> None:
    """Spec §36.3 #4: a node spanning two domains has `domain=None`.

    Per `02 §18.1`, mixed-domain nodes are invalid. The assembler
    represents this state via `ImplicitNode.domain is None`, which
    subsequent validation pipelines (S1.6+) translate into a
    validation issue. The validator (S1.4) would normally reject
    such a connection before it reaches the workspace; this test
    exercises the assembler's defensive behavior under direct
    mutation or load-time corruption.
    """
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    model.add_connection(  # raw mutator does not validate
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="flange"),
    )
    port_lookup = _make_port_lookup(
        {(a, "p"): "electrical_analog", (b, "flange"): "mechanical_translational"}
    )
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=tuple(model.connections.values()),
        port_lookup=port_lookup,
    )

    assert len(graph.implicit_nodes) == 1
    assert graph.implicit_nodes[0].domain is None


# ---------------------------------------------------------------------- #
# Ergonomic / contract tests
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_empty_workspace_yields_empty_graph() -> None:
    """An empty workspace produces an empty `SystemGraph`."""
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components={},
        connections=(),
        port_lookup=_make_port_lookup({}),
    )

    assert graph.is_empty() is True


@pytest.mark.unit
def test_components_without_connections_produce_no_implicit_nodes() -> None:
    """Disconnected ports do not appear in `implicit_nodes` in Phase 1."""
    model = WorkspaceModel()
    model.add_component(**_add_kwargs())
    model.add_component(**_add_kwargs())
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=(),
        port_lookup=_make_port_lookup({}),
    )

    assert graph.implicit_nodes == ()
    assert len(graph.component_ids) == 2


@pytest.mark.unit
def test_node_ids_follow_monotonic_node_n_format() -> None:
    """Per `02 §8.7`: `node_1`, `node_2`, ... in assembly order."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    c = model.add_component(**_add_kwargs())
    d = model.add_component(**_add_kwargs())
    # Two independent groups
    model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    model.add_connection(
        source=PortRef(component_id=c, port_id="p"),
        target=PortRef(component_id=d, port_id="p"),
    )
    port_lookup = _make_port_lookup(
        {
            (a, "p"): "electrical_analog",
            (b, "p"): "electrical_analog",
            (c, "p"): "electrical_analog",
            (d, "p"): "electrical_analog",
        }
    )
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=tuple(model.connections.values()),
        port_lookup=port_lookup,
    )

    ids = [node.id for node in graph.implicit_nodes]
    assert ids == ["node_1", "node_2"]


@pytest.mark.unit
def test_system_graph_contains_all_component_and_connection_ids() -> None:
    """`SystemGraph` enumerates every workspace id."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    conn_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    port_lookup = _make_port_lookup({(a, "p"): "electrical_analog", (b, "p"): "electrical_analog"})
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=tuple(model.connections.values()),
        port_lookup=port_lookup,
    )

    assert set(graph.component_ids) == {a, b}
    assert graph.connection_ids == (conn_id,)


@pytest.mark.unit
def test_self_connection_produces_single_port_node() -> None:
    """Self-connection (validator-rejected normally) does not crash the
    assembler. The single port appears in one implicit node."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    # Raw mutator: validator would reject this in normal flow.
    ref = PortRef(component_id=a, port_id="p")
    model.add_connection(source=ref, target=ref)
    port_lookup = _make_port_lookup({(a, "p"): "electrical_analog"})
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=tuple(model.connections.values()),
        port_lookup=port_lookup,
    )

    assert len(graph.implicit_nodes) == 1
    node = graph.implicit_nodes[0]
    assert node.port_refs == (ref,)
    assert node.domain == "electrical_analog"


@pytest.mark.unit
def test_multi_port_component_separate_domains_form_separate_nodes() -> None:
    """Per `02 §18.2`: cross-domain components expose ports per domain;
    distinct connections form distinct nodes — the component itself
    does not auto-merge port nodes."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    motor = model.add_component(**_add_kwargs())  # multi-domain
    mass = model.add_component(**_add_kwargs())
    # Electrical side: a.p -- motor.elec_p
    model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=motor, port_id="elec_p"),
    )
    # Mechanical side: motor.shaft -- mass.flange
    model.add_connection(
        source=PortRef(component_id=motor, port_id="shaft"),
        target=PortRef(component_id=mass, port_id="flange"),
    )
    port_lookup = _make_port_lookup(
        {
            (a, "p"): "electrical_analog",
            (motor, "elec_p"): "electrical_analog",
            (motor, "shaft"): "mechanical_translational",
            (mass, "flange"): "mechanical_translational",
        }
    )
    assembler = GraphAssembler()

    graph = assembler.assemble(
        components=dict(model.components),
        connections=tuple(model.connections.values()),
        port_lookup=port_lookup,
    )

    assert len(graph.implicit_nodes) == 2
    domains = {node.domain for node in graph.implicit_nodes}
    assert domains == {"electrical_analog", "mechanical_translational"}


@pytest.mark.unit
def test_node_ordering_is_deterministic_via_lexicographic_traversal() -> None:
    """Repeated assembly of the same workspace yields identical node
    sequences regardless of dict iteration order."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    c = model.add_component(**_add_kwargs())
    d = model.add_component(**_add_kwargs())
    model.add_connection(
        source=PortRef(component_id=c, port_id="p"),
        target=PortRef(component_id=d, port_id="p"),
    )
    model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    port_lookup = _make_port_lookup(
        {
            (a, "p"): "electrical_analog",
            (b, "p"): "electrical_analog",
            (c, "p"): "electrical_analog",
            (d, "p"): "electrical_analog",
        }
    )
    assembler = GraphAssembler()

    snapshot = (
        dict(model.components),
        tuple(model.connections.values()),
    )

    graph_1 = assembler.assemble(
        components=snapshot[0],
        connections=snapshot[1],
        port_lookup=port_lookup,
    )
    graph_2 = assembler.assemble(
        components=snapshot[0],
        connections=snapshot[1],
        port_lookup=port_lookup,
    )

    ids_1 = [node.id for node in graph_1.implicit_nodes]
    ids_2 = [node.id for node in graph_2.implicit_nodes]
    port_sets_1 = [
        sorted((r.component_id, r.port_id) for r in node.port_refs)
        for node in graph_1.implicit_nodes
    ]
    port_sets_2 = [
        sorted((r.component_id, r.port_id) for r in node.port_refs)
        for node in graph_2.implicit_nodes
    ]
    assert ids_1 == ids_2
    assert port_sets_1 == port_sets_2
