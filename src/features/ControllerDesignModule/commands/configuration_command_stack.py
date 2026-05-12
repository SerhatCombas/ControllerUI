"""ConfigurationCommandStack: per-document QUndoStack for ControllerDesignModule.

Direct parallel to `SystemModelingModule.WorkspaceCommandStack`
(S1.7), with the same architectural contract:

* The stack owns a `QUndoStack`. The model
  (`ConfigurationModel`) stays Qt-undo-agnostic per ADR-003.
* The stack binds `QUndoStack.cleanChanged` to the model's
  `_set_dirty` / `_clear_dirty` helpers so undo-to-clean and
  save-to-clean events drive the dirty bit (ADR-020).
* The base `ConfigurationCommand` is a thin `QUndoCommand`
  subclass carrying the target `ConfigurationModel` reference;
  concrete commands implement `redo()` / `undo()` in terms of
  model setters (`set_controller_settings`, `set_io_selection`,
  `set_simulation_settings`, `set_plot_layout`).

PD1 from the S2.D pre-scan: this stack is **separate** from
`WorkspaceCommandStack`. The application shell composes both
into a single `QUndoGroup` so "Edit → Undo" reaches the
appropriate stack without ad-hoc routing. The Qt-idiomatic
group dispatch preserves the architectural separation while
giving a single-timeline UX.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/07_implementation_order.md` §7.16 (S2.D — Configuration Commands)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand, QUndoStack

from shared.utils import logging_events as events

if TYPE_CHECKING:
    from PySide6.QtCore import QObject

    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )


logger = logging.getLogger(__name__)


class ConfigurationCommand(QUndoCommand):
    """Base class for every ControllerDesignModule edit command (ADR-005).

    Holds the target `ConfigurationModel` reference and forwards
    the user-facing label to `QUndoCommand`. Subclasses implement
    `redo()` and `undo()` in terms of `self._model` setters.

    Subclasses MUST:

    * call `super().__init__(model, text)` with a stable user-facing
      label;
    * capture pre-mutation state in `__init__` so `undo()` is
      reversible (the captured-state pattern from S1.7);
    * be idempotent under repeated `redo()` calls after
      undo→redo cycles;
    * leave validation in `__init__` (raise before the stack push)
      rather than mid-`redo()` — `QUndoStack` does not tolerate
      partial state.

    Subclasses MUST NOT:

    * mutate the model from `__init__` (mutation belongs in
      `redo()`, which `QUndoStack.push` invokes automatically);
    * import from `features.SystemModelingModule.*` — cross-feature
      data flows through `shared/types` only.
    """

    def __init__(self, model: ConfigurationModel, text: str = "") -> None:
        """Initialize the command with the target model and menu text."""
        super().__init__(text)
        self._model = model

    @property
    def model(self) -> ConfigurationModel:
        """Read-only access to the target model (test convenience)."""
        return self._model


class ConfigurationCommandStack:
    """Per-document `QUndoStack` wrapper bound to a `ConfigurationModel`.

    Construction-time state: a freshly-built `QUndoStack` reports
    `isClean() == True`; Qt does not emit `cleanChanged` on the
    initial state, so the model's `is_dirty` starting at `False`
    matches without a synchronization step.

    Args:
        model: The `ConfigurationModel` whose mutations this stack
            tracks.
        parent: Optional Qt parent for the underlying `QUndoStack`.
            Used by the shell to tie the stack's lifetime to a
            document window or to the model itself.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        parent: QObject | None = None,
    ) -> None:
        """Initialize with the target model and an optional Qt parent."""
        self._model = model
        self._stack = QUndoStack(parent) if parent is not None else QUndoStack()
        self._stack.cleanChanged.connect(self._on_clean_changed)

    def _on_clean_changed(self, clean: bool) -> None:
        """Sync the model's dirty bit with the stack's clean state.

        ADR-020 §"QUndoStack integration": stack reaches clean index
        → model becomes clean; stack diverges → model becomes dirty.
        The model's transition-only `_set_dirty` / `_clear_dirty`
        helpers make duplicate emissions harmless.
        """
        if clean:
            self._model._clear_dirty()
        else:
            self._model._set_dirty()

    @property
    def model(self) -> ConfigurationModel:
        """The bound `ConfigurationModel`."""
        return self._model

    @property
    def stack(self) -> QUndoStack:
        """The underlying `QUndoStack`.

        Exposed so the application shell can add this stack to a
        `QUndoGroup` (PD1 from the S2.D pre-scan — Qt-idiomatic
        undo dispatch across both feature stacks).
        """
        return self._stack

    def push(self, command: ConfigurationCommand) -> None:
        """Push a command onto the stack.

        `QUndoStack.push` invokes `command.redo()` synchronously
        before returning, so by the time this call completes the
        model has already been mutated and any signals have fired.
        """
        self._stack.push(command)

    def undo(self) -> None:
        """Undo the top command (no-op when `can_undo()` is False)."""
        if self._stack.canUndo():
            logger.info(
                "Command undone: %s",
                self._stack.undoText(),
                extra={
                    "event": events.COMMAND_UNDO,
                    "command_text": self._stack.undoText(),
                },
            )
        self._stack.undo()

    def redo(self) -> None:
        """Redo the next command (no-op when `can_redo()` is False)."""
        if self._stack.canRedo():
            logger.info(
                "Command redone: %s",
                self._stack.redoText(),
                extra={
                    "event": events.COMMAND_REDO,
                    "command_text": self._stack.redoText(),
                },
            )
        self._stack.redo()

    def can_undo(self) -> bool:
        """True when at least one command is undoable."""
        return self._stack.canUndo()

    def can_redo(self) -> bool:
        """True when at least one command is redoable."""
        return self._stack.canRedo()

    def index(self) -> int:
        """Current index in the stack (test convenience)."""
        return self._stack.index()

    def count(self) -> int:
        """Number of commands currently on the stack (test convenience)."""
        return self._stack.count()


__all__ = [
    "ConfigurationCommand",
    "ConfigurationCommandStack",
]
