"""Unit tests for `WorkspaceScene` drag-drop wiring (S1.9.3).

Covers the public `drop_component` entry point, the
`snap_to_grid` helper, the `_accepts_mime` predicate, and a
smoke test through `dropEvent` itself using a `QMimeData`
payload + a stubbed event object that satisfies the
`QGraphicsSceneDragDropEvent` interface the scene actually
exercises.

References:
----------
* `specs/02_workspace_requirements.md` §15 (Grid), §16
  (Drag / Drop)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from PySide6.QtCore import QByteArray, QMimeData, QPointF
from PySide6.QtCore import Qt as QtNamespace

from features.SystemModelingModule.commands import WorkspaceCommandStack
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    COMPONENT_MIME_TYPE,
    WorkspaceScene,
    snap_to_grid,
)
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)

# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #


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


class _StubDropEvent:
    """Minimal stand-in for `QGraphicsSceneDragDropEvent`.

    PySide6 does not expose a public constructor for
    `QGraphicsSceneDragDropEvent`, so end-to-end `dropEvent`
    tests use this stub. It implements the four methods the
    scene's `dropEvent` calls — `mimeData()`, `scenePos()`,
    `acceptProposedAction()`, `ignore()` — and records which
    accept / ignore path the scene took.
    """

    def __init__(self, mime: QMimeData, pos: QPointF) -> None:
        self._mime = mime
        self._pos = pos
        self.accepted: bool = False
        self.ignored: bool = False

    def mimeData(self) -> QMimeData:  # noqa: N802 — Qt API shape
        return self._mime

    def scenePos(self) -> QPointF:  # noqa: N802 — Qt API shape
        return self._pos

    def acceptProposedAction(self) -> None:  # noqa: N802 — Qt API shape
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


def _make_mime(definition_id: str | None = RESISTOR_DEFINITION.id) -> QMimeData:
    """Build a `QMimeData` carrying our drag payload.

    `definition_id=None` produces empty MIME — used to verify
    the predicate rejects unrelated drags.
    """
    mime = QMimeData()
    if definition_id is not None:
        mime.setData(COMPONENT_MIME_TYPE, QByteArray(definition_id.encode("utf-8")))
    return mime


# ---------------------------------------------------------------------- #
# snap_to_grid
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_snap_to_grid_rounds_to_nearest_multiple() -> None:
    """20.0 spacing: 31 → 40, 28 → 20, 30 → 20 (banker's)."""
    assert snap_to_grid(31.0, spacing=20.0) == 40.0
    assert snap_to_grid(28.0, spacing=20.0) == 20.0


@pytest.mark.unit
def test_snap_to_grid_at_origin() -> None:
    """0.0 snaps to 0.0 exactly."""
    assert snap_to_grid(0.0) == 0.0


@pytest.mark.unit
def test_snap_to_grid_negative_values() -> None:
    """Negative values snap symmetrically: -31 → -40."""
    assert snap_to_grid(-31.0, spacing=20.0) == -40.0


# ---------------------------------------------------------------------- #
# _accepts_mime predicate
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_scene_accepts_mime_with_component_payload(scene: WorkspaceScene) -> None:
    """A `QMimeData` carrying our MIME type is accepted."""
    mime = _make_mime(RESISTOR_DEFINITION.id)

    assert scene._accepts_mime(mime) is True


@pytest.mark.unit
def test_scene_rejects_mime_without_component_payload(
    scene: WorkspaceScene,
) -> None:
    """Empty `QMimeData` is rejected."""
    mime = _make_mime(definition_id=None)

    assert scene._accepts_mime(mime) is False


@pytest.mark.unit
def test_scene_rejects_non_qmimedata(scene: WorkspaceScene) -> None:
    """Objects without `hasFormat` are rejected (defensive)."""

    class _NotMime:
        pass

    assert scene._accepts_mime(_NotMime()) is False


# ---------------------------------------------------------------------- #
# drop_component public API
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_drop_component_without_stack_returns_none(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A scene without a command stack logs a warning and drops nothing."""
    no_stack_scene = WorkspaceScene(model)

    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        result = no_stack_scene.drop_component(RESISTOR_DEFINITION.id, QPointF(40.0, 60.0))

    assert result is None
    assert len(no_stack_scene.model.components) == 0
    assert any("without a command_stack" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_drop_component_pushes_command_onto_stack(
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
) -> None:
    """A successful drop pushes one `AddComponentCommand`."""
    pre_count = stack.count()

    new_id = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(40.0, 60.0))

    assert new_id is not None
    assert stack.count() == pre_count + 1
    assert new_id in scene.model.components


@pytest.mark.unit
def test_drop_component_snaps_position_to_grid(scene: WorkspaceScene) -> None:
    """The dropped component lands on the nearest grid intersection."""
    # Drop at (47, 71) — nearest multiples of 20 are (40, 80).
    new_id = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(47.0, 71.0))

    assert new_id is not None
    placed = scene.model.components[new_id]
    assert placed.position == (40.0, 80.0)


@pytest.mark.unit
def test_drop_component_unknown_definition_id_raises(
    scene: WorkspaceScene,
) -> None:
    """Unknown definition id propagates the registry's `KeyError`."""
    with pytest.raises(KeyError):
        scene.drop_component("electrical.unknown.does_not_exist", QPointF(0.0, 0.0))


@pytest.mark.unit
def test_drop_component_creates_visible_item_via_scene_subscription(
    scene: WorkspaceScene,
) -> None:
    """End-to-end: drop → command push → componentAdded signal →
    `ComponentGraphicsItem` lands in `scene._component_items`."""
    new_id = scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert new_id is not None
    assert new_id in scene._component_items
    item = scene._component_items[new_id]
    assert item.component_id == new_id


# ---------------------------------------------------------------------- #
# dropEvent integration (via stub event)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_dropEvent_with_valid_mime_pushes_command(  # noqa: N802 — match Qt API
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
) -> None:
    """A full `dropEvent` cycle with valid MIME mints a component."""
    mime = _make_mime(RESISTOR_DEFINITION.id)
    event: Any = _StubDropEvent(mime, QPointF(40.0, 60.0))
    pre_count = stack.count()

    scene.dropEvent(event)

    assert event.accepted is True
    assert event.ignored is False
    assert stack.count() == pre_count + 1


@pytest.mark.unit
def test_dropEvent_with_empty_mime_is_ignored(  # noqa: N802 — match Qt API
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
) -> None:
    """`dropEvent` with no payload ignores the event and no-ops the stack."""
    mime = _make_mime(definition_id=None)
    event: Any = _StubDropEvent(mime, QPointF(0.0, 0.0))
    pre_count = stack.count()

    scene.dropEvent(event)

    assert event.accepted is False
    assert event.ignored is True
    assert stack.count() == pre_count


@pytest.mark.unit
def test_dropEvent_with_unknown_definition_id_is_logged_and_ignored(  # noqa: N802
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unknown definition id surfaces as a warning, no stack push."""
    mime = _make_mime("electrical.unknown.does_not_exist")
    event: Any = _StubDropEvent(mime, QPointF(0.0, 0.0))
    pre_count = stack.count()

    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        scene.dropEvent(event)

    assert event.accepted is False
    assert event.ignored is True
    assert stack.count() == pre_count
    assert any("not in registry" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------- #
# dragEnterEvent / dragMoveEvent (via stub event)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_dragEnterEvent_accepts_valid_mime(  # noqa: N802 — match Qt API
    scene: WorkspaceScene,
) -> None:
    """`dragEnterEvent` accepts when MIME has our type."""
    mime = _make_mime(RESISTOR_DEFINITION.id)
    event: Any = _StubDropEvent(mime, QPointF(0.0, 0.0))

    scene.dragEnterEvent(event)

    assert event.accepted is True


@pytest.mark.unit
def test_dragEnterEvent_ignores_unknown_mime(  # noqa: N802 — match Qt API
    scene: WorkspaceScene,
) -> None:
    """`dragEnterEvent` ignores when MIME does not carry our type."""
    mime = _make_mime(definition_id=None)
    event: Any = _StubDropEvent(mime, QPointF(0.0, 0.0))

    scene.dragEnterEvent(event)

    assert event.ignored is True


# QtNamespace re-exported so the `from ... import Qt as QtNamespace` line
# has a non-empty consumer (used in the documented future drop-action
# checks); referenced here as a runtime no-op to keep the import live.
_ = QtNamespace
