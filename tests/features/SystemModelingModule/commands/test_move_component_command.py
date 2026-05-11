"""Unit tests for `MoveComponentCommand` (S1.7.2).

Covers the single-target captured-state pattern for component
position changes:

* `__init__` captures the pre-move position from the model.
* `__init__` raises `KeyError` for unknown component_id (so a
  malformed command never lands on the undo stack).
* `redo()` applies the new position; `undo()` restores the
  captured old position; subsequent `redo()` re-applies.
* `componentMoved` signal fires on each model mutation per
  ADR-018.
* The ε-tolerance no-op suppression at the model layer applies
  here too — a move to the current position is a no-op at redo
  time and undo time.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §22 (Move/Delete)
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    MoveComponentCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model with one pre-placed resistor."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """`WorkspaceCommandStack` bound to the model."""
    return WorkspaceCommandStack(model)


@pytest.fixture
def component_id(model: WorkspaceModel) -> str:
    """A pre-placed resistor at (10.0, 20.0)."""
    return model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(10.0, 20.0))


@pytest.mark.unit
def test_construct_captures_old_position_from_model(
    model: WorkspaceModel,
    component_id: str,
) -> None:
    """`old_pos` snapshots the model's current position at construction."""
    command = MoveComponentCommand(model, component_id, QPointF(100.0, 200.0))

    assert command.old_pos == QPointF(10.0, 20.0)
    assert command.new_pos == QPointF(100.0, 200.0)


@pytest.mark.unit
def test_construct_raises_keyerror_for_unknown_component(
    model: WorkspaceModel,
) -> None:
    """Pre-validation: missing component → `KeyError`.

    A malformed command never lands on the undo stack — Qt does not
    unwind a failed push gracefully.
    """
    with pytest.raises(KeyError):
        MoveComponentCommand(model, "cmp_nonexistent", QPointF(0.0, 0.0))


@pytest.mark.unit
def test_push_applies_new_position(
    stack: WorkspaceCommandStack,
    component_id: str,
) -> None:
    """`stack.push(command)` mutates the model to `new_pos`."""
    command = MoveComponentCommand(stack.model, component_id, QPointF(100.0, 200.0))

    stack.push(command)

    assert stack.model.components[component_id].position == (100.0, 200.0)


@pytest.mark.unit
def test_undo_restores_old_position(
    stack: WorkspaceCommandStack,
    component_id: str,
) -> None:
    """`stack.undo()` restores the captured pre-move position."""
    stack.push(MoveComponentCommand(stack.model, component_id, QPointF(100.0, 200.0)))

    stack.undo()

    assert stack.model.components[component_id].position == (10.0, 20.0)


@pytest.mark.unit
def test_redo_after_undo_re_applies_new_position(
    stack: WorkspaceCommandStack,
    component_id: str,
) -> None:
    """Redo after undo returns the component to the target position."""
    stack.push(MoveComponentCommand(stack.model, component_id, QPointF(100.0, 200.0)))
    stack.undo()

    stack.redo()

    assert stack.model.components[component_id].position == (100.0, 200.0)


@pytest.mark.unit
def test_push_emits_component_moved(
    stack: WorkspaceCommandStack,
    component_id: str,
) -> None:
    """The model's `componentMoved` signal fires with the move payload."""
    received: list[tuple[str, QPointF, QPointF]] = []
    stack.model.componentMoved.connect(
        lambda cid, old, new: received.append((cid, QPointF(old), QPointF(new)))
    )

    stack.push(MoveComponentCommand(stack.model, component_id, QPointF(50.0, 60.0)))

    assert len(received) == 1
    cid, old, new = received[0]
    assert cid == component_id
    assert old == QPointF(10.0, 20.0)
    assert new == QPointF(50.0, 60.0)
