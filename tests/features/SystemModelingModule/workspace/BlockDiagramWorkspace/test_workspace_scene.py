"""Unit tests for `WorkspaceScene` after S1.9.2.

S1.9.1 wired the model signals to placeholder slots; S1.9.2 fills
them in with real `ComponentGraphicsItem` lifecycle. Tests cover:

* construction binds the model and installs the grid
* `componentAdded` mints an item; `componentRemoved` cleans it up
* `componentMoved` / `componentRotated` push the new transform
  into the existing item
* `componentChanged` refreshes cached display fields
* `modelChanged` (batch) replays the diff in one pass
* `modelReset` clears all component / connection items but keeps
  the grid

Connection-related slots remain placeholders until S1.9.5;
`test_scene_connection_added_signal_reaches_scene_slot` exercises
the wiring without expecting real items.

References:
----------
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.component_graphics_item import (
    ComponentGraphicsItem,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.grid_background_item import (
    GRID_Z_VALUE,
    GridBackgroundItem,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    WorkspaceScene,
)
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model for scene tests."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


# ---------------------------------------------------------------------- #
# Construction (unchanged from S1.9.1)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_constructs_with_model(model: WorkspaceModel) -> None:
    """`WorkspaceScene(model)` stores the model and installs the grid."""
    scene = WorkspaceScene(model)

    assert scene.model is model
    assert isinstance(scene.grid_item, GridBackgroundItem)
    assert scene.grid_item in scene.items()


@pytest.mark.unit
def test_scene_grid_item_z_below_components(model: WorkspaceModel) -> None:
    """Grid sits beneath the default component z (0)."""
    scene = WorkspaceScene(model)

    assert scene.grid_item.zValue() == GRID_Z_VALUE


# ---------------------------------------------------------------------- #
# componentAdded / componentRemoved lifecycle (S1.9.2)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_creates_component_item_on_add(model: WorkspaceModel) -> None:
    """Adding a component to the model mints a `ComponentGraphicsItem`."""
    scene = WorkspaceScene(model)

    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert new_id in scene._component_items
    item = scene._component_items[new_id]
    assert isinstance(item, ComponentGraphicsItem)
    assert item.component_id == new_id
    assert item in scene.items()


@pytest.mark.unit
def test_scene_removes_component_item_on_remove(
    model: WorkspaceModel,
) -> None:
    """Removing a component cleans up the corresponding item."""
    scene = WorkspaceScene(model)
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    item = scene._component_items[new_id]

    model.remove_component(new_id)

    assert new_id not in scene._component_items
    assert item not in scene.items()


@pytest.mark.unit
def test_scene_handles_component_removed_for_unknown_id(
    model: WorkspaceModel,
) -> None:
    """An unknown id on `componentRemoved` is a safe no-op."""
    scene = WorkspaceScene(model)

    # Should not raise. (Direct signal emit because the model
    # itself would have raised KeyError on remove_component.)
    model.componentRemoved.emit("cmp_nonexistent")

    assert scene._component_items == {}


@pytest.mark.unit
def test_scene_resolves_label_via_registry(model: WorkspaceModel) -> None:
    """Item label uses the definition's `short_name` from the registry.

    `RESISTOR_DEFINITION.short_name == "R"`, so the item should
    render with "R" as its on-canvas label rather than the
    fallback "Res" derived from `display_name[:3]`.
    """
    scene = WorkspaceScene(model)
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    item = scene._component_items[new_id]
    assert item.label == RESISTOR_DEFINITION.short_name == "R"


# ---------------------------------------------------------------------- #
# componentMoved / componentRotated propagate to the item (S1.9.2)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_moves_item_when_component_moved(
    model: WorkspaceModel,
) -> None:
    """A `move_component` call updates the item's position."""
    scene = WorkspaceScene(model)
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    item = scene._component_items[new_id]

    model.move_component(new_id, QPointF(120.0, 80.0))

    assert item.pos() == QPointF(120.0, 80.0)


@pytest.mark.unit
def test_scene_rotates_item_when_component_rotated(
    model: WorkspaceModel,
) -> None:
    """A `rotate_component` call updates the item's rotation."""
    scene = WorkspaceScene(model)
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    item = scene._component_items[new_id]

    model.rotate_component(new_id, 90.0)

    assert item.rotation() == 90.0


# ---------------------------------------------------------------------- #
# componentChanged refreshes cached fields (S1.9.2)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_refreshes_locked_flag_on_component_changed(
    model: WorkspaceModel,
) -> None:
    """`set_locked(True)` propagates to `item.locked`."""
    scene = WorkspaceScene(model)
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    item = scene._component_items[new_id]
    assert item.locked is False

    model.set_locked(new_id, True)

    assert item.locked is True


# ---------------------------------------------------------------------- #
# Connection signal wiring (still placeholder — S1.9.5)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_connection_added_signal_reaches_scene_slot(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`connectionAdded` reaches the placeholder slot (still S1.9.5 work)."""
    scene = WorkspaceScene(model)
    assert scene is not None  # keep alive for the duration of the test

    caplog.clear()
    with caplog.at_level(
        logging.DEBUG,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        model.connectionAdded.emit("con_test456")

    assert any("connectionAdded" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------- #
# Batch (modelChanged) path (S1.9.2)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_batch_modelchanged_adds_items(model: WorkspaceModel) -> None:
    """A batched mutation adds component items via the change_set."""
    scene = WorkspaceScene(model)

    with model.batch():
        first = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
        second = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(50.0, 0.0))

    assert first in scene._component_items
    assert second in scene._component_items
    assert scene._component_items[first].pos() == QPointF(0.0, 0.0)
    assert scene._component_items[second].pos() == QPointF(50.0, 0.0)


@pytest.mark.unit
def test_scene_batch_modelchanged_removes_items(model: WorkspaceModel) -> None:
    """A batched removal cleans up items via the change_set."""
    scene = WorkspaceScene(model)
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert new_id in scene._component_items

    with model.batch():
        model.remove_component(new_id)

    assert new_id not in scene._component_items


# ---------------------------------------------------------------------- #
# modelReset (cleanup)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_model_reset_clears_component_items(model: WorkspaceModel) -> None:
    """`reset()` removes all component items but keeps the grid."""
    scene = WorkspaceScene(model)
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(50.0, 0.0))
    assert len(scene._component_items) == 2

    model.reset()

    assert scene._component_items == {}
    assert scene._connection_items == {}
    assert scene.grid_item in scene.items()
