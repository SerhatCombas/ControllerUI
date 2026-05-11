"""Unit tests for `ModifyConnectionCommand` (S1.7.4).

Wraps `WorkspaceModel.update_connection` (combo-updater) with the
captured-state pattern. Tests cover:

* the happy path (one or more fields change, undo restores the
  captured prior value)
* `KeyError` for unknown connection_id
* `ValueError` for all-None invocations (per the S1.7.4 planning
  thread — no-op commands must not land on the undo stack)
* partial captures: when only one of `(label, routing, style)` is
  set, undo restores only that field; the other two stay as they
  are (combo-updater's `None` = "leave unchanged")

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `specs/02_workspace_requirements.md` §14
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    ModifyConnectionCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.connection import (
    ConnectionRouting,
    PortRef,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def stack_with_connection() -> tuple[WorkspaceCommandStack, str]:
    """Stack + model + a pre-placed connection.

    The connection starts with `label=""`, default routing,
    `style={}` so the tests have a known baseline.
    """
    model = WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))
    a = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    b = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(100.0, 0.0))
    conn_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="n"),
        label="initial",
    )
    return WorkspaceCommandStack(model), conn_id


@pytest.mark.unit
def test_construct_raises_keyerror_for_unknown_connection() -> None:
    """Pre-validation: missing connection_id → `KeyError`."""
    model = WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))

    with pytest.raises(KeyError):
        ModifyConnectionCommand(model, "con_nonexistent", label="new")


@pytest.mark.unit
def test_construct_raises_value_error_when_all_none(
    stack_with_connection: tuple[WorkspaceCommandStack, str],
) -> None:
    """All-None invocation → `ValueError` (no-op command refused).

    Per the S1.7.4 planning thread: pushing an empty modify
    command would pollute the undo stack with a no-op entry.
    The constructor refuses early.
    """
    stack, conn_id = stack_with_connection

    with pytest.raises(ValueError, match=r"at least one"):
        ModifyConnectionCommand(stack.model, conn_id)


@pytest.mark.unit
def test_push_updates_label_only(
    stack_with_connection: tuple[WorkspaceCommandStack, str],
) -> None:
    """A label-only edit changes only the label; routing and style untouched."""
    stack, conn_id = stack_with_connection
    pre_routing = stack.model.connections[conn_id].routing
    pre_style = dict(stack.model.connections[conn_id].style)

    stack.push(ModifyConnectionCommand(stack.model, conn_id, label="renamed"))

    after = stack.model.connections[conn_id]
    assert after.label == "renamed"
    assert after.routing == pre_routing
    assert dict(after.style) == pre_style


@pytest.mark.unit
def test_undo_restores_captured_old_label(
    stack_with_connection: tuple[WorkspaceCommandStack, str],
) -> None:
    """Undo restores the pre-edit label captured at construction."""
    stack, conn_id = stack_with_connection
    stack.push(ModifyConnectionCommand(stack.model, conn_id, label="renamed"))

    stack.undo()

    assert stack.model.connections[conn_id].label == "initial"


@pytest.mark.unit
def test_undo_restores_captured_old_routing_and_style(
    stack_with_connection: tuple[WorkspaceCommandStack, str],
) -> None:
    """Undo restores routing and style when those are the edited fields."""
    stack, conn_id = stack_with_connection
    pre_routing = stack.model.connections[conn_id].routing
    pre_style = dict(stack.model.connections[conn_id].style)
    new_routing = ConnectionRouting(waypoints=((10.0, 10.0), (20.0, 20.0)))
    new_style: dict[str, object] = {"color": "blue"}
    stack.push(
        ModifyConnectionCommand(
            stack.model,
            conn_id,
            routing=new_routing,
            style=new_style,
        )
    )

    stack.undo()

    after = stack.model.connections[conn_id]
    assert after.routing == pre_routing
    assert dict(after.style) == pre_style


@pytest.mark.unit
def test_redo_after_undo_re_applies_new_values(
    stack_with_connection: tuple[WorkspaceCommandStack, str],
) -> None:
    """Redo cycles the connection back to the post-edit state."""
    stack, conn_id = stack_with_connection
    stack.push(ModifyConnectionCommand(stack.model, conn_id, label="renamed"))
    stack.undo()

    stack.redo()

    assert stack.model.connections[conn_id].label == "renamed"
