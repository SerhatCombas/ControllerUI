"""Unit tests for `DeleteConnectionCommand` (S1.7.4).

Single-target counterpart to `DeleteComponentCommand` — no
cascade. Captures the full `Connection` on construction;
`redo()` removes, `undo()` re-inserts via
`WorkspaceModel.restore_connection` so the `con_<ULID>` id
survives the cycle.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `specs/02_workspace_requirements.md` §14, §25
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    DeleteConnectionCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def stack_with_connection() -> tuple[WorkspaceCommandStack, str]:
    """Stack + model with a pre-placed connection between two resistors."""
    model = WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))
    a = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    b = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(100.0, 0.0))
    conn_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="n"),
    )
    return WorkspaceCommandStack(model), conn_id


@pytest.mark.unit
def test_construct_raises_keyerror_for_unknown_connection() -> None:
    """Pre-validation: missing connection_id → `KeyError`."""
    model = WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))

    with pytest.raises(KeyError):
        DeleteConnectionCommand(model, "con_nonexistent")


@pytest.mark.unit
def test_push_removes_connection(
    stack_with_connection: tuple[WorkspaceCommandStack, str],
) -> None:
    """`stack.push` removes the captured connection."""
    stack, conn_id = stack_with_connection

    stack.push(DeleteConnectionCommand(stack.model, conn_id))

    assert conn_id not in stack.model.connections


@pytest.mark.unit
def test_undo_restores_same_connection(
    stack_with_connection: tuple[WorkspaceCommandStack, str],
) -> None:
    """`stack.undo` reinserts the connection verbatim (id + state preserved)."""
    stack, conn_id = stack_with_connection
    pre_connection = stack.model.connections[conn_id]
    stack.push(DeleteConnectionCommand(stack.model, conn_id))

    stack.undo()

    assert conn_id in stack.model.connections
    assert stack.model.connections[conn_id] == pre_connection


@pytest.mark.unit
def test_redo_after_undo_re_removes_connection(
    stack_with_connection: tuple[WorkspaceCommandStack, str],
) -> None:
    """Redo cycles the deletion back."""
    stack, conn_id = stack_with_connection
    stack.push(DeleteConnectionCommand(stack.model, conn_id))
    stack.undo()

    stack.redo()

    assert conn_id not in stack.model.connections
