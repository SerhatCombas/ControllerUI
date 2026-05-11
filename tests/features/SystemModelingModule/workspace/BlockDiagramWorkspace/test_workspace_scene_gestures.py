"""Unit tests for the S1.9.4 mouse-gesture wiring.

Covers:

* `ComponentGraphicsItem.commit_drag` — the post-drag commit
  path that snaps the end position to the grid and routes
  through the scene's command stack
* `WorkspaceScene.commit_component_move` — the scene-side
  bridge that pushes `MoveComponentCommand`
* `WorkspaceScene.rotate_selected_components` — the
  selection-aware rotation helper that pushes one
  `RotateComponentCommand` per selected item

Constructed events are sidestepped: the item's
`mousePressEvent` / `mouseReleaseEvent` are integration glue
that boil down to capturing `start_pos` and calling
`commit_drag`; we test `commit_drag` directly with synthesized
positions.

References:
----------
* `specs/02_workspace_requirements.md` §22 (Move), §23
  (Rotation), §16 (Drag interactions)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import WorkspaceCommandStack
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    WorkspaceScene,
)

if TYPE_CHECKING:
    from features.SystemModelingModule.workspace.BlockDiagramWorkspace import (
        component_graphics_item as _cgi,
    )

    ComponentGraphicsItem = _cgi.ComponentGraphicsItem
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """`WorkspaceCommandStack` bound to the model."""
    return WorkspaceCommandStack(model)


@pytest.fixture
def scene(model: WorkspaceModel, stack: WorkspaceCommandStack) -> WorkspaceScene:
    """A `WorkspaceScene` wired with both model and command stack."""
    return WorkspaceScene(model, command_stack=stack)


@pytest.fixture
def scene_with_resistor(
    scene: WorkspaceScene,
) -> tuple[WorkspaceScene, str, ComponentGraphicsItem]:
    """Scene + a pre-placed resistor + its graphics item.

    Drops the resistor at (40, 60) via the public scene API so
    every wiring layer (command → signal → scene slot) runs.
    """
    cid = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(40.0, 60.0))
    assert cid is not None
    item = scene._component_items[cid]
    return scene, cid, item


# ---------------------------------------------------------------------- #
# ComponentGraphicsItem.commit_drag
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_commit_drag_no_movement_returns_false(
    scene_with_resistor: tuple[WorkspaceScene, str, ComponentGraphicsItem],
    stack: WorkspaceCommandStack,
) -> None:
    """`start_pos == end_pos` → no command pushed, return False."""
    _, _, item = scene_with_resistor
    pre_count = stack.count()

    result = item.commit_drag(QPointF(40.0, 60.0), QPointF(40.0, 60.0))

    assert result is False
    assert stack.count() == pre_count


@pytest.mark.unit
def test_commit_drag_subgrid_movement_reverts_visual(
    scene_with_resistor: tuple[WorkspaceScene, str, ComponentGraphicsItem],
    stack: WorkspaceCommandStack,
) -> None:
    """A drag that snaps back to the start is a no-op + visual revert.

    Start at (40, 60); end at (43, 62). Snap of (43, 62) is
    (40, 60), so no command. Item should snap back to (40, 60).
    """
    _, _, item = scene_with_resistor
    pre_count = stack.count()

    # Simulate Qt-managed drag by setting item position to end:
    item.setPos(QPointF(43.0, 62.0))

    result = item.commit_drag(QPointF(40.0, 60.0), QPointF(43.0, 62.0))

    assert result is False
    assert stack.count() == pre_count
    assert item.pos() == QPointF(40.0, 60.0)


@pytest.mark.unit
def test_commit_drag_real_movement_pushes_move_command(
    scene_with_resistor: tuple[WorkspaceScene, str, ComponentGraphicsItem],
    stack: WorkspaceCommandStack,
) -> None:
    """A real drag pushes one `MoveComponentCommand`.

    Start at (40, 60); end at (95, 105). Snap of (95, 105) is
    (100, 100). One command pushed, model position updated to
    snapped value, item visual lands on snapped position.
    """
    s, cid, item = scene_with_resistor
    item.setPos(QPointF(95.0, 105.0))
    pre_count = stack.count()

    result = item.commit_drag(QPointF(40.0, 60.0), QPointF(95.0, 105.0))

    assert result is True
    assert stack.count() == pre_count + 1
    assert s.model.components[cid].position == (100.0, 100.0)
    # `_on_component_moved` slot drove the item to the snapped pos.
    assert item.pos() == QPointF(100.0, 100.0)


# ---------------------------------------------------------------------- #
# WorkspaceScene.commit_component_move
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_commit_component_move_pushes_command(
    scene_with_resistor: tuple[WorkspaceScene, str, ComponentGraphicsItem],
    stack: WorkspaceCommandStack,
) -> None:
    """Direct call to `commit_component_move` pushes a `MoveComponentCommand`."""
    s, cid, _ = scene_with_resistor
    pre_count = stack.count()

    result = s.commit_component_move(cid, QPointF(160.0, 80.0))

    assert result is True
    assert stack.count() == pre_count + 1
    assert s.model.components[cid].position == (160.0, 80.0)


@pytest.mark.unit
def test_scene_commit_component_move_without_stack_is_noop(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No command_stack → warning + return False, model untouched."""
    no_stack_scene = WorkspaceScene(model)
    # Place a component via direct model API since there's no stack
    # to push through.
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        result = no_stack_scene.commit_component_move(cid, QPointF(60.0, 40.0))

    assert result is False
    assert model.components[cid].position == (0.0, 0.0)
    assert any("without a command_stack" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_scene_commit_component_move_unknown_id_is_noop(
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An id that's not in the model is rejected with a warning, no command."""
    pre_count = stack.count()

    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        result = scene.commit_component_move("cmp_nonexistent", QPointF(0.0, 0.0))

    assert result is False
    assert stack.count() == pre_count
    assert any("unknown component_id" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------- #
# WorkspaceScene.rotate_selected_components
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_rotate_selected_pushes_command_per_selected_item(
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
) -> None:
    """Each selected `ComponentGraphicsItem` produces one rotation command."""
    cid_a = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(60.0, 0.0))
    assert cid_a is not None
    assert cid_b is not None
    scene._component_items[cid_a].setSelected(True)
    scene._component_items[cid_b].setSelected(True)
    pre_count = stack.count()

    pushed = scene.rotate_selected_components(angle_delta=90.0)

    assert pushed == 2
    assert stack.count() == pre_count + 2
    assert scene.model.components[cid_a].rotation == 90.0
    assert scene.model.components[cid_b].rotation == 90.0


@pytest.mark.unit
def test_scene_rotate_selected_skips_unselected_items(
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
) -> None:
    """Unselected items are untouched."""
    cid_selected = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_unselected = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(60.0, 0.0))
    assert cid_selected is not None
    assert cid_unselected is not None
    scene._component_items[cid_selected].setSelected(True)
    # cid_unselected left unselected.

    pushed = scene.rotate_selected_components(angle_delta=90.0)

    assert pushed == 1
    assert scene.model.components[cid_selected].rotation == 90.0
    assert scene.model.components[cid_unselected].rotation == 0.0


@pytest.mark.unit
def test_scene_rotate_selected_without_stack_returns_zero(
    model: WorkspaceModel,
) -> None:
    """No command_stack → no rotations, no exception."""
    no_stack_scene = WorkspaceScene(model)

    pushed = no_stack_scene.rotate_selected_components(angle_delta=90.0)

    assert pushed == 0


@pytest.mark.unit
def test_scene_rotate_selected_wraps_around_360(
    scene: WorkspaceScene,
) -> None:
    """A second 90° rotation from 270 wraps to 0 via `% 360.0`."""
    cid = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert cid is not None
    # Set initial rotation to 270 (Phase-1 valid value).
    scene.model.rotate_component(cid, 270.0)
    scene._component_items[cid].setSelected(True)

    scene.rotate_selected_components(angle_delta=90.0)

    # (270 + 90) % 360 = 0.0 — RotateComponentCommand accepts.
    assert scene.model.components[cid].rotation == 0.0
