"""Unit tests for `WorkspaceScene` connection-lifecycle wiring (S1.9.5a).

Covers:

* `_on_component_added` mints port children on the component item
  via `_resolve_ports` (registry lookup).
* `_on_connection_added` mints a `ConnectionGraphicsItem` and
  resolves both endpoint port items through the component-item
  registry.
* `_on_connection_removed` cleans up the item.
* `_on_component_moved` / `_on_component_rotated` trigger
  `update_geometry` on connections touching the moved component.
* Defensive paths: missing component, missing port, batch
  delete-then-recreate.

References:
----------
* `specs/02_workspace_requirements.md` §14 (Connection System)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import WorkspaceCommandStack
from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.connection_graphics_item import (
    ConnectionGraphicsItem,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.port_graphics_item import (
    PortGraphicsItem,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    WorkspaceScene,
)
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    GROUND_ELECTRIC_DEFINITION,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """Command stack for tests that exercise drop pipelines."""
    return WorkspaceCommandStack(model)


@pytest.fixture
def scene(model: WorkspaceModel, stack: WorkspaceCommandStack) -> WorkspaceScene:
    """Scene wired with model + stack."""
    return WorkspaceScene(model, command_stack=stack)


# ---------------------------------------------------------------------- #
# Component item gains port children via registry resolution
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_component_item_has_port_children_after_add(scene: WorkspaceScene) -> None:
    """A resistor placement mints `PortGraphicsItem` children matching its definition.

    `RESISTOR_DEFINITION.ports` declares ids `p` (positive) and
    `n` (negative); the component item should expose both via
    `port_items`.
    """
    cid = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    item = scene._component_items[cid]
    assert set(item.port_items.keys()) == {"p", "n"}
    for port_item in item.port_items.values():
        assert isinstance(port_item, PortGraphicsItem)
        # Port is a child of the component item.
        assert port_item.parentItem() is item


@pytest.mark.unit
def test_component_port_local_position_matches_relative_definition(
    scene: WorkspaceScene,
) -> None:
    """`relative_position=(0.0, 0.5)` for `p` maps to local (-25, 0).

    The placeholder body is 50x30 centered on origin, so the
    left-middle anchor (rx=0, ry=0.5) sits at x=-25, y=0.
    """
    cid = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    item = scene._component_items[cid]
    port_p = item.port_item("p")
    assert port_p is not None
    assert port_p.pos() == QPointF(-25.0, 0.0)


@pytest.mark.unit
def test_component_without_registered_definition_has_no_ports() -> None:
    """A no-registry model produces components with no port children.

    `_resolve_ports` returns the empty tuple when the registry
    is unwired; the component item receives `ports=()` and
    creates no children.
    """
    no_registry_model = WorkspaceModel()
    scene = WorkspaceScene(no_registry_model)
    cid = no_registry_model.add_component(
        definition_id="electrical.analog.components.resistor",
        type="Resistor",
        display_name="Resistor",
        domain="electrical_analog",
        category="component",
        position=QPointF(0.0, 0.0),
        visual=__import__(
            "features.SystemModelingModule.model.component_instance",
            fromlist=["VisualSpec"],
        ).VisualSpec(svg_id="x"),
        physical_attributes=__import__(
            "features.SystemModelingModule.model.component_instance",
            fromlist=["PhysicalAttributes"],
        ).PhysicalAttributes(),
    )

    item = scene._component_items[cid]
    assert item.port_items == {}


# ---------------------------------------------------------------------- #
# Connection lifecycle (connectionAdded / connectionRemoved / changed)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_creates_connection_item_on_add(scene: WorkspaceScene) -> None:
    """Adding a connection mints a `ConnectionGraphicsItem`."""
    cid_a = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = scene.model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0)
    )

    conn_id = scene.model.add_connection(
        source=PortRef(component_id=cid_a, port_id="p"),
        target=PortRef(component_id=cid_b, port_id="p"),
    )

    assert conn_id in scene._connection_items
    item = scene._connection_items[conn_id]
    assert isinstance(item, ConnectionGraphicsItem)
    assert item in scene.items()
    # Endpoint port items are wired correctly.
    assert item.source_port is scene._component_items[cid_a].port_item("p")
    assert item.target_port is scene._component_items[cid_b].port_item("p")


@pytest.mark.unit
def test_scene_removes_connection_item_on_remove(scene: WorkspaceScene) -> None:
    """Removing a connection drops the corresponding item."""
    cid_a = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = scene.model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0)
    )
    conn_id = scene.model.add_connection(
        source=PortRef(component_id=cid_a, port_id="p"),
        target=PortRef(component_id=cid_b, port_id="p"),
    )
    pre_item = scene._connection_items[conn_id]

    scene.model.remove_connection(conn_id)

    assert conn_id not in scene._connection_items
    assert pre_item not in scene.items()


@pytest.mark.unit
def test_scene_component_delete_cascades_to_connection_items(
    scene: WorkspaceScene,
) -> None:
    """A cascade delete via DeleteComponentCommand drops the wire item too.

    `DeleteComponentCommand` removes attached connections inside
    a `model.batch()`. The scene's batch path should clean up
    both the component and the connection items in one pass.
    """
    from features.SystemModelingModule.commands import DeleteComponentCommand

    cid_a = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = scene.model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0)
    )
    conn_id = scene.model.add_connection(
        source=PortRef(component_id=cid_a, port_id="p"),
        target=PortRef(component_id=cid_b, port_id="p"),
    )
    assert conn_id in scene._connection_items

    stack = scene.command_stack
    assert stack is not None
    stack.push(DeleteComponentCommand(scene.model, cid_a))

    assert cid_a not in scene._component_items
    assert conn_id not in scene._connection_items


@pytest.mark.unit
def test_scene_component_moved_refreshes_connection_geometry(
    scene: WorkspaceScene,
) -> None:
    """A `move_component` call triggers `update_geometry` on touching wires.

    Verified indirectly: after the move, the connection item's
    bounding rect should reflect the new endpoint position
    (the source port's `scenePos` moves with its parent).
    """
    cid_a = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = scene.model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0)
    )
    conn_id = scene.model.add_connection(
        source=PortRef(component_id=cid_a, port_id="p"),
        target=PortRef(component_id=cid_b, port_id="p"),
    )
    conn_item = scene._connection_items[conn_id]
    pre_rect = conn_item.boundingRect()

    scene.model.move_component(cid_a, QPointF(400.0, 300.0))

    post_rect = conn_item.boundingRect()
    # The bounding rect now spans the new source position.
    assert post_rect != pre_rect


# ---------------------------------------------------------------------- #
# modelReset cleanup
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_model_reset_clears_connection_items(scene: WorkspaceScene) -> None:
    """`model.reset()` clears connection items alongside components."""
    cid_a = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = scene.model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0)
    )
    conn_id = scene.model.add_connection(
        source=PortRef(component_id=cid_a, port_id="p"),
        target=PortRef(component_id=cid_b, port_id="p"),
    )
    assert conn_id in scene._connection_items

    scene.model.reset()

    assert scene._connection_items == {}
    assert scene._component_items == {}
