"""Unit tests for the S1.9.5b connection-draw gesture.

Covers the public API on `WorkspaceScene`:

* `port_at(scene_pos)` — hit-tests a `PortGraphicsItem` and
  returns its `PortRef`
* `start_connection_draw(source)` — begins a draw, installs
  the rubber-band line
* `update_connection_draw(cursor_pos)` — extends the
  rubber-band as the cursor moves
* `commit_connection_draw(target)` — finalizes the draw,
  pushes `AddConnectionCommand` (or silent-skips on validator
  rejection)
* `cancel_connection_draw()` — tears down the in-flight draw
* `pending_connection_source` accessor

References:
----------
* `specs/02_workspace_requirements.md` §14, §20.1
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import WorkspaceCommandStack
from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
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
    """Command stack for the draw tests."""
    return WorkspaceCommandStack(model)


@pytest.fixture
def scene(model: WorkspaceModel, stack: WorkspaceCommandStack) -> WorkspaceScene:
    """Scene wired with model + stack."""
    return WorkspaceScene(model, command_stack=stack)


@pytest.fixture
def two_components_in_scene(
    scene: WorkspaceScene,
) -> tuple[WorkspaceScene, str, str]:
    """Place a resistor + ground in the scene at distinct positions.

    Returns `(scene, resistor_id, ground_id)`. Resistor at (0, 0)
    with port `p` at local (-25, 0); ground at (100, 50) with
    port `p` at local (0, -15) (top-center).
    """
    resistor_id = scene.model.add_component_from_definition(
        RESISTOR_DEFINITION.id, QPointF(0.0, 0.0)
    )
    ground_id = scene.model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 50.0)
    )
    return scene, resistor_id, ground_id


# ---------------------------------------------------------------------- #
# port_at
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_port_at_finds_port_under_cursor(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
) -> None:
    """`port_at` returns the `PortRef` of the port under the position.

    Resistor at (0, 0); port `p` sits at local (-25, 0), i.e.
    scene (-25, 0). Asking `port_at(QPointF(-25, 0))` should
    return that port.
    """
    s, rid, _ = two_components_in_scene

    ref = s.port_at(QPointF(-25.0, 0.0))

    assert ref is not None
    assert ref.component_id == rid
    assert ref.port_id == "p"


@pytest.mark.unit
def test_port_at_returns_none_in_empty_area(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
) -> None:
    """No port under the cursor → returns `None`."""
    s, _, _ = two_components_in_scene

    assert s.port_at(QPointF(500.0, 500.0)) is None


# ---------------------------------------------------------------------- #
# start_connection_draw
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_start_connection_draw_initiates_state(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
) -> None:
    """`start_connection_draw` records source and adds rubber-band line."""
    s, rid, _ = two_components_in_scene
    source_ref = PortRef(component_id=rid, port_id="p")

    started = s.start_connection_draw(source_ref)

    assert started is True
    assert s.pending_connection_source == source_ref
    assert s._pending_line_item is not None
    assert s._pending_line_item in s.items()


@pytest.mark.unit
def test_start_connection_draw_unknown_source_returns_false(
    scene: WorkspaceScene,
) -> None:
    """Source `PortRef` not resolvable → False, no state change."""
    started = scene.start_connection_draw(PortRef(component_id="cmp_nonexistent", port_id="p"))

    assert started is False
    assert scene.pending_connection_source is None


@pytest.mark.unit
def test_start_connection_draw_rejected_when_already_in_flight(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
) -> None:
    """A second draw while one is in flight is rejected."""
    s, rid, _ = two_components_in_scene
    source_ref = PortRef(component_id=rid, port_id="p")
    s.start_connection_draw(source_ref)

    second = s.start_connection_draw(PortRef(component_id=rid, port_id="n"))

    assert second is False
    # Source still matches the first call.
    assert s.pending_connection_source == source_ref


# ---------------------------------------------------------------------- #
# update_connection_draw
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_update_connection_draw_extends_line_to_cursor(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
) -> None:
    """The rubber-band line tracks the cursor position."""
    s, rid, _ = two_components_in_scene
    s.start_connection_draw(PortRef(component_id=rid, port_id="p"))

    s.update_connection_draw(QPointF(80.0, 60.0))

    assert s._pending_line_item is not None
    line = s._pending_line_item.line()
    assert line.x2() == 80.0
    assert line.y2() == 60.0


@pytest.mark.unit
def test_update_connection_draw_no_op_when_idle(scene: WorkspaceScene) -> None:
    """No in-flight draw → `update_connection_draw` is a quiet no-op."""
    scene.update_connection_draw(QPointF(100.0, 100.0))

    assert scene.pending_connection_source is None
    assert scene._pending_line_item is None


# ---------------------------------------------------------------------- #
# commit_connection_draw
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_commit_connection_draw_pushes_add_connection_command(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
    stack: WorkspaceCommandStack,
) -> None:
    """A valid commit pushes one `AddConnectionCommand` and creates a wire item."""
    s, rid, gid = two_components_in_scene
    source_ref = PortRef(component_id=rid, port_id="p")
    target_ref = PortRef(component_id=gid, port_id="p")
    s.start_connection_draw(source_ref)
    pre_count = stack.count()

    conn_id = s.commit_connection_draw(target_ref)

    assert conn_id is not None
    assert stack.count() == pre_count + 1
    assert conn_id in s.model.connections
    assert conn_id in s._connection_items
    # Rubber-band torn down.
    assert s.pending_connection_source is None
    assert s._pending_line_item is None


@pytest.mark.unit
def test_commit_connection_draw_self_connection_is_rejected(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
    stack: WorkspaceCommandStack,
) -> None:
    """Source equal to target → no command, draw torn down."""
    s, rid, _ = two_components_in_scene
    source_ref = PortRef(component_id=rid, port_id="p")
    s.start_connection_draw(source_ref)
    pre_count = stack.count()

    result = s.commit_connection_draw(source_ref)

    assert result is None
    assert stack.count() == pre_count
    assert s.pending_connection_source is None


@pytest.mark.unit
def test_commit_connection_draw_validator_rejection_is_logged(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
    stack: WorkspaceCommandStack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A validator-rejected candidate logs + returns None.

    Resistor port `p` to its own port `n` (same component, two
    distinct ports) — this is NOT a self-connection per
    `GraphValidator`'s `02 §14.3` rule, which forbids
    `source == target` (same id pair). However connecting a
    resistor's two ports to each other DOES get rejected by
    another rule (here we exercise the duplicate / equivalent
    path). To make this test robust we instead use a
    pre-existing connection and try to make a duplicate.
    """
    s, rid, gid = two_components_in_scene
    # Seed an existing connection from the resistor's `p` to
    # ground's `p`.
    s.model.add_connection(
        source=PortRef(component_id=rid, port_id="p"),
        target=PortRef(component_id=gid, port_id="p"),
    )
    # Now attempt to draw the same connection again — the
    # duplicate rule should reject it.
    s.start_connection_draw(PortRef(component_id=rid, port_id="p"))
    pre_count = stack.count()

    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        result = s.commit_connection_draw(PortRef(component_id=gid, port_id="p"))

    assert result is None
    assert stack.count() == pre_count
    assert any("rejected by validator" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_commit_connection_draw_without_stack_returns_none(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No command_stack wired → warning + return None."""
    no_stack_scene = WorkspaceScene(model)
    rid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    gid = model.add_component_from_definition(GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0))
    no_stack_scene.start_connection_draw(PortRef(component_id=rid, port_id="p"))

    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene",
    ):
        result = no_stack_scene.commit_connection_draw(PortRef(component_id=gid, port_id="p"))

    assert result is None
    assert any("without a command_stack" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_commit_connection_draw_when_idle_returns_none(
    scene: WorkspaceScene,
) -> None:
    """No in-flight draw → commit is a no-op returning None."""
    result = scene.commit_connection_draw(PortRef(component_id="cmp_x", port_id="p"))

    assert result is None


# ---------------------------------------------------------------------- #
# cancel_connection_draw
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_cancel_connection_draw_clears_pending_state(
    two_components_in_scene: tuple[WorkspaceScene, str, str],
) -> None:
    """Cancel tears down the rubber-band and clears the source."""
    s, rid, _ = two_components_in_scene
    s.start_connection_draw(PortRef(component_id=rid, port_id="p"))
    line_item = s._pending_line_item
    assert line_item is not None

    s.cancel_connection_draw()

    assert s.pending_connection_source is None
    assert s._pending_line_item is None
    assert line_item not in s.items()


@pytest.mark.unit
def test_cancel_connection_draw_is_idempotent(scene: WorkspaceScene) -> None:
    """Calling cancel without an in-flight draw is a quiet no-op."""
    scene.cancel_connection_draw()  # smoke

    assert scene.pending_connection_source is None
