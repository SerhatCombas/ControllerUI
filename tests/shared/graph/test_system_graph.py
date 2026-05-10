"""Unit tests for `shared.graph.SystemGraph` (S1.5).

Covers:

* default construction yields an empty graph
* `is_empty()` True for default, False for any populated field
* frozen mutability guard
* explicit construction round-trips all fields

References
----------
* `specs/02_workspace_requirements.md` §19 (Graph Assembly)
* `specs/06_data_flow_and_architecture.md` §5.3 (shared/graph)
"""

from __future__ import annotations

import dataclasses

import pytest

from shared.graph.implicit_node import ImplicitNode
from shared.graph.port_ref import PortRef
from shared.graph.system_graph import SystemGraph


@pytest.mark.unit
def test_default_construction_yields_empty_graph() -> None:
    """A default `SystemGraph()` is structurally empty."""
    graph = SystemGraph()

    assert graph.component_ids == ()
    assert graph.connection_ids == ()
    assert graph.implicit_nodes == ()


@pytest.mark.unit
def test_is_empty_returns_true_for_default() -> None:
    """The default graph is empty per `is_empty()`."""
    assert SystemGraph().is_empty() is True


@pytest.mark.unit
def test_is_empty_returns_false_when_component_ids_present() -> None:
    """Any populated field makes the graph non-empty."""
    graph = SystemGraph(component_ids=("cmp_A",))
    assert graph.is_empty() is False


@pytest.mark.unit
def test_is_empty_returns_false_when_implicit_nodes_present() -> None:
    """Implicit nodes alone make the graph non-empty."""
    node = ImplicitNode(
        id="node_1",
        port_refs=(PortRef(component_id="cmp_A", port_id="p"),),
        domain="electrical_analog",
    )
    graph = SystemGraph(implicit_nodes=(node,))
    assert graph.is_empty() is False


@pytest.mark.unit
def test_frozen_dataclass_cannot_be_mutated() -> None:
    """Frozen + slots guards against direct field assignment."""
    graph = SystemGraph()
    with pytest.raises(dataclasses.FrozenInstanceError):
        graph.component_ids = ("cmp_X",)  # type: ignore[misc]


@pytest.mark.unit
def test_explicit_construction_round_trips_all_fields() -> None:
    """All explicit fields read back unchanged."""
    node = ImplicitNode(
        id="node_1",
        port_refs=(PortRef(component_id="cmp_A", port_id="p"),),
        domain="electrical_analog",
    )
    graph = SystemGraph(
        component_ids=("cmp_A", "cmp_B"),
        connection_ids=("con_1",),
        implicit_nodes=(node,),
    )

    assert graph.component_ids == ("cmp_A", "cmp_B")
    assert graph.connection_ids == ("con_1",)
    assert graph.implicit_nodes == (node,)
    assert graph.is_empty() is False
