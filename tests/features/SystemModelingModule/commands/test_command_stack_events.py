"""Unit tests for command-stack event emission (S1.8c).

Verifies that `WorkspaceCommandStack.undo()` / `redo()` emit
`command.undo` / `command.redo` events per `specs/10` §8.4.
`push()` does NOT emit a command event — the underlying
command's own mutation log (workspace.component_added etc.)
already covers initial execution; the command-level events
are reserved for explicit undo / redo invocations after the
first push.

`command.merged` is reserved for a future stage that
implements `QUndoCommand.mergeWith` (TODO(S1.7.future) noted in
move / rotate / change_parameter command files).

References:
----------
* `specs/10_logging_conventions.md` §8.4
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    AddComponentCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)
from shared.utils import logging_events as events

_STACK_LOGGER = "features.SystemModelingModule.commands.workspace_command_stack"


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """Command stack bound to the model."""
    return WorkspaceCommandStack(model)


def _events_with(
    records: list[logging.LogRecord],
    event_name: str,
) -> list[logging.LogRecord]:
    """Filter `records` to those carrying `extra={"event": event_name}`."""
    return [r for r in records if getattr(r, "event", None) == event_name]


@pytest.mark.unit
def test_push_does_not_emit_command_event(
    stack: WorkspaceCommandStack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Initial `push` emits the command's own mutation event but
    no `command.redo` (reserved for explicit redo after undo)."""
    cmd = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_STACK_LOGGER):
        stack.push(cmd)

    assert _events_with(caplog.records, events.COMMAND_REDO) == []
    assert _events_with(caplog.records, events.COMMAND_UNDO) == []


@pytest.mark.unit
def test_undo_emits_command_undo_event(
    stack: WorkspaceCommandStack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`undo()` emits `command.undo` with the command's text."""
    cmd = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    stack.push(cmd)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_STACK_LOGGER):
        stack.undo()

    matches = _events_with(caplog.records, events.COMMAND_UNDO)
    assert len(matches) == 1
    # The undo text reflects the command that was just undone.
    assert "Resistor" in matches[0].command_text  # type: ignore[attr-defined]


@pytest.mark.unit
def test_redo_after_undo_emits_command_redo_event(
    stack: WorkspaceCommandStack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit `redo()` after undo emits `command.redo`."""
    cmd = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    stack.push(cmd)
    stack.undo()

    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_STACK_LOGGER):
        stack.redo()

    matches = _events_with(caplog.records, events.COMMAND_REDO)
    assert len(matches) == 1
    assert "Resistor" in matches[0].command_text  # type: ignore[attr-defined]


@pytest.mark.unit
def test_undo_when_empty_emits_nothing(
    stack: WorkspaceCommandStack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Calling `undo()` on an empty stack is a no-op + no log."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_STACK_LOGGER):
        stack.undo()

    assert _events_with(caplog.records, events.COMMAND_UNDO) == []


@pytest.mark.unit
def test_redo_when_no_redo_pending_emits_nothing(
    stack: WorkspaceCommandStack,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Calling `redo()` with no pending redo is a no-op + no log."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_STACK_LOGGER):
        stack.redo()

    assert _events_with(caplog.records, events.COMMAND_REDO) == []
