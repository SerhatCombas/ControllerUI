"""Unit tests for `WorkspaceCommandStack` and `WorkspaceCommand` (S1.7.1).

Covers the per-document QUndoStack wrapper (decision B per the
S1.7 planning thread: stack lives on the wrapper, not on the
model) and the `WorkspaceCommand` base class contract.

Specifically:

* Construction binds the wrapper to a `WorkspaceModel`.
* `push` invokes the command's `redo()` synchronously (Qt's
  `QUndoStack.push` contract).
* `undo` / `redo` round-trip applies and reverts the command.
* `can_undo` / `can_redo` reflect the stack index state.
* `count` and `index` expose the underlying stack diagnostics
  for tests.
* `WorkspaceCommand.model` exposes the bound model for tests and
  subclasses.

`AddComponentCommand`-specific behavior (the registry path, the
identity-stable redo→undo→redo cycle, etc.) is tested in the
sibling `test_add_component_command.py` module.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `specs/02_workspace_requirements.md` §25
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

import pytest

from features.SystemModelingModule.commands import (
    WorkspaceCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class _RecordingCommand(WorkspaceCommand):
    """Minimal `WorkspaceCommand` that records redo/undo invocations.

    Used by stack-mechanics tests so we can verify Qt's push/undo/
    redo contract without depending on actual model mutations. The
    real `AddComponentCommand` is tested separately.
    """

    def __init__(self, model: WorkspaceModel, log: list[str], text: str = "Test") -> None:
        super().__init__(model, text)
        self._log = log

    def redo(self) -> None:
        """Append `'redo'` to the shared log."""
        self._log.append("redo")

    def undo(self) -> None:
        """Append `'undo'` to the shared log."""
        self._log.append("undo")


# ---------------------------------------------------------------------- #
# Construction
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_stack_constructs_with_model_reference() -> None:
    """`WorkspaceCommandStack(model)` stores the model on the wrapper.

    Decision B: the stack lives on the wrapper, not the model. The
    `model` property is the explicit accessor for downstream
    bindings (UI, tests) to reach the bound model without
    duplicating the reference.
    """
    model = WorkspaceModel()
    stack = WorkspaceCommandStack(model)

    assert stack.model is model


@pytest.mark.unit
def test_stack_exposes_underlying_qundostack() -> None:
    """`stack.stack` returns the wrapped `QUndoStack`.

    Exposed for the S1.7.5 `cleanChanged` binding and for S1.9 UI
    menu wiring; tests can use it to assert deeper diagnostics
    when needed.
    """
    model = WorkspaceModel()
    stack = WorkspaceCommandStack(model)

    assert stack.stack is not None
    assert stack.count() == 0
    assert stack.index() == 0


@pytest.mark.unit
def test_stack_initial_can_undo_and_can_redo_are_false() -> None:
    """An empty stack reports neither undo nor redo is available."""
    stack = WorkspaceCommandStack(WorkspaceModel())

    assert stack.can_undo() is False
    assert stack.can_redo() is False


# ---------------------------------------------------------------------- #
# Push / undo / redo cycle
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_push_invokes_command_redo_synchronously() -> None:
    """`stack.push(command)` calls `command.redo()` before returning.

    Qt's `QUndoStack.push` contract: redo is invoked synchronously
    on push. Our wrapper preserves this so the model has already
    been mutated by the time `push` returns — which the UI relies
    on (the new component is in the model when the drag-drop
    handler finishes).
    """
    log: list[str] = []
    stack = WorkspaceCommandStack(WorkspaceModel())

    stack.push(_RecordingCommand(stack.model, log))

    assert log == ["redo"]


@pytest.mark.unit
def test_undo_after_push_invokes_command_undo() -> None:
    """`stack.undo()` invokes the top command's `undo()` method."""
    log: list[str] = []
    stack = WorkspaceCommandStack(WorkspaceModel())
    stack.push(_RecordingCommand(stack.model, log))

    stack.undo()

    assert log == ["redo", "undo"]


@pytest.mark.unit
def test_redo_after_undo_re_invokes_command_redo() -> None:
    """`stack.redo()` re-invokes the command's `redo()` after undo."""
    log: list[str] = []
    stack = WorkspaceCommandStack(WorkspaceModel())
    stack.push(_RecordingCommand(stack.model, log))
    stack.undo()

    stack.redo()

    assert log == ["redo", "undo", "redo"]


@pytest.mark.unit
def test_can_undo_reflects_index_state() -> None:
    """`can_undo()` toggles correctly across push and undo."""
    log: list[str] = []
    stack = WorkspaceCommandStack(WorkspaceModel())
    assert stack.can_undo() is False

    stack.push(_RecordingCommand(stack.model, log))
    assert stack.can_undo() is True

    stack.undo()
    assert stack.can_undo() is False


@pytest.mark.unit
def test_can_redo_reflects_index_state() -> None:
    """`can_redo()` toggles correctly across undo and redo."""
    log: list[str] = []
    stack = WorkspaceCommandStack(WorkspaceModel())
    stack.push(_RecordingCommand(stack.model, log))
    assert stack.can_redo() is False

    stack.undo()
    assert stack.can_redo() is True

    stack.redo()
    assert stack.can_redo() is False


@pytest.mark.unit
def test_count_increments_on_push() -> None:
    """`count()` reports the number of commands on the stack."""
    log: list[str] = []
    stack = WorkspaceCommandStack(WorkspaceModel())
    assert stack.count() == 0

    stack.push(_RecordingCommand(stack.model, log, "First"))
    assert stack.count() == 1

    stack.push(_RecordingCommand(stack.model, log, "Second"))
    assert stack.count() == 2


# ---------------------------------------------------------------------- #
# WorkspaceCommand base
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_workspace_command_exposes_model_via_property() -> None:
    """`WorkspaceCommand.model` returns the bound model.

    The base property is a test / subclass convenience so commands
    can access the model without poking at the `_model` private
    attribute.
    """
    model = WorkspaceModel()
    log: list[str] = []
    command = _RecordingCommand(model, log, "Probe")

    assert command.model is model


@pytest.mark.unit
def test_workspace_command_text_propagates_to_qundocommand() -> None:
    """The `text` arg lands on `QUndoCommand.text()` for menu display."""
    log: list[str] = []
    command = _RecordingCommand(WorkspaceModel(), log, text="Add Resistor")

    assert command.text() == "Add Resistor"
