"""Unit tests for `RotateComponentCommand` (S1.7.2).

Covers the rotation-specific variant of the captured-state pattern,
including the Phase-1 rotation quantization rule.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `specs/02_workspace_requirements.md` §22, §23 (Rotation)
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    RotateComponentCommand,
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
    """A pre-placed resistor at rotation 0.0."""
    return model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))


@pytest.mark.unit
def test_construct_captures_old_rotation_from_model(
    model: WorkspaceModel,
    component_id: str,
) -> None:
    """`old_rotation` snapshots the model's current angle."""
    command = RotateComponentCommand(model, component_id, 90.0)

    assert command.old_rotation == 0.0
    assert command.new_rotation == 90.0


@pytest.mark.unit
def test_construct_raises_keyerror_for_unknown_component(
    model: WorkspaceModel,
) -> None:
    """Missing component_id → `KeyError`."""
    with pytest.raises(KeyError):
        RotateComponentCommand(model, "cmp_nonexistent", 90.0)


@pytest.mark.unit
def test_construct_raises_value_error_for_off_grid_rotation(
    model: WorkspaceModel,
    component_id: str,
) -> None:
    """Phase-1 angles are restricted to `{0, 90, 180, 270}` per
    `02 §22` / `§23`. Off-grid values are rejected at construction
    so the command never lands on the stack.
    """
    with pytest.raises(ValueError, match=r"rotation must be one of"):
        RotateComponentCommand(model, component_id, 45.0)


@pytest.mark.unit
def test_push_applies_new_rotation(
    stack: WorkspaceCommandStack,
    component_id: str,
) -> None:
    """`push` rotates the component to the target angle."""
    stack.push(RotateComponentCommand(stack.model, component_id, 180.0))

    assert stack.model.components[component_id].rotation == 180.0


@pytest.mark.unit
def test_undo_restores_old_rotation(
    stack: WorkspaceCommandStack,
    component_id: str,
) -> None:
    """`undo` restores the captured pre-rotation angle."""
    stack.push(RotateComponentCommand(stack.model, component_id, 270.0))

    stack.undo()

    assert stack.model.components[component_id].rotation == 0.0


@pytest.mark.unit
def test_redo_after_undo_re_applies_new_rotation(
    stack: WorkspaceCommandStack,
    component_id: str,
) -> None:
    """Redo cycles the rotation back to the target angle."""
    stack.push(RotateComponentCommand(stack.model, component_id, 90.0))
    stack.undo()

    stack.redo()

    assert stack.model.components[component_id].rotation == 90.0
