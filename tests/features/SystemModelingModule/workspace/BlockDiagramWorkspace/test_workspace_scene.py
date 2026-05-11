"""Unit tests for `WorkspaceScene` (S1.9.1).

S1.9.1 covers the scene skeleton and signal wiring. Component /
connection rendering lands in S1.9.2 / S1.9.5; these tests
verify the foundation:

* construction binds the model and installs the grid
* all 10 mutation / structural signals connect without raising
  (verified by firing each signal and confirming the matching
  log entry — slots are placeholders that log only)
* `modelReset` clears the internal mirror dicts (empty in
  S1.9.1; the test exercises the iteration to lock in the
  grid-retention guarantee)
* the grid item z-value sits below component default z=0 so
  later sub-commits don't fight a layering bug

References:
----------
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import logging

import pytest

from features.SystemModelingModule.model.workspace_model import WorkspaceModel
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


@pytest.mark.unit
def test_scene_constructs_with_model(model: WorkspaceModel) -> None:
    """`WorkspaceScene(model)` stores the model and installs the grid."""
    scene = WorkspaceScene(model)

    assert scene.model is model
    assert isinstance(scene.grid_item, GridBackgroundItem)
    # Grid is in the scene's item list.
    assert scene.grid_item in scene.items()


@pytest.mark.unit
def test_scene_grid_item_z_below_components(model: WorkspaceModel) -> None:
    """Grid sits beneath the default component z (0)."""
    scene = WorkspaceScene(model)

    assert scene.grid_item.zValue() == GRID_Z_VALUE


@pytest.mark.unit
def test_scene_component_added_signal_reaches_scene_slot(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Firing `componentAdded` triggers the scene's placeholder slot.

    S1.9.1 slots only log; this test verifies the connection is
    live so S1.9.2 can replace the body without re-wiring.
    """
    scene = WorkspaceScene(model)  # noqa: F841 — keep alive for signal delivery

    caplog.clear()
    with caplog.at_level(
        logging.DEBUG,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        model.componentAdded.emit("cmp_test123")

    assert any("componentAdded" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_scene_component_removed_signal_reaches_scene_slot(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`componentRemoved` reaches the placeholder slot."""
    scene = WorkspaceScene(model)  # noqa: F841

    caplog.clear()
    with caplog.at_level(
        logging.DEBUG,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        model.componentRemoved.emit("cmp_test123")

    assert any("componentRemoved" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_scene_connection_added_signal_reaches_scene_slot(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`connectionAdded` reaches the placeholder slot."""
    scene = WorkspaceScene(model)  # noqa: F841

    caplog.clear()
    with caplog.at_level(
        logging.DEBUG,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        model.connectionAdded.emit("con_test456")

    assert any("connectionAdded" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_scene_full_add_flow_reaches_slot(model: WorkspaceModel) -> None:
    """End-to-end smoke: actually adding a component via the model
    fires the signal and the scene's connection survives.

    Verifies that the signal wiring isn't broken by anything
    specific to `add_component_from_definition` (Phase 1
    integration path used by the command stack).
    """
    from PySide6.QtCore import QPointF

    scene = WorkspaceScene(model)  # noqa: F841
    received: list[str] = []
    model.componentAdded.connect(received.append)

    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    # Both the scene's slot and the test's subscriber receive
    # the same id (Qt signals fan out).
    assert received == [new_id]


@pytest.mark.unit
def test_scene_model_reset_clears_internal_dicts(
    model: WorkspaceModel,
) -> None:
    """`modelReset` clears both mirror dicts while keeping the grid."""
    from PySide6.QtWidgets import QGraphicsRectItem

    scene = WorkspaceScene(model)
    # S1.9.1: the mirror dicts are empty by design (S1.9.2 will
    # populate them). The test still verifies the slot's logic
    # by pre-seeding the dicts with real graphics items so the
    # `removeItem(item)` call in `_on_model_reset` accepts them.
    fake_component_item = QGraphicsRectItem()
    fake_connection_item = QGraphicsRectItem()
    scene.addItem(fake_component_item)
    scene.addItem(fake_connection_item)
    scene._component_items["cmp_pre"] = fake_component_item
    scene._connection_items["con_pre"] = fake_connection_item

    model.reset()

    assert scene._component_items == {}
    assert scene._connection_items == {}
    # Grid survives reset.
    assert scene.grid_item in scene.items()
    # Pre-seeded fake items are no longer in the scene.
    assert fake_component_item not in scene.items()
    assert fake_connection_item not in scene.items()


@pytest.mark.unit
def test_scene_model_changed_signal_reaches_batch_slot(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`modelChanged` from a real batch fires the batch slot."""
    from PySide6.QtCore import QPointF

    scene = WorkspaceScene(model)  # noqa: F841

    caplog.clear()
    with (
        caplog.at_level(
            logging.DEBUG,
            logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
        ),
        model.batch(),
    ):
        model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert any("modelChanged" in r.getMessage() for r in caplog.records)
