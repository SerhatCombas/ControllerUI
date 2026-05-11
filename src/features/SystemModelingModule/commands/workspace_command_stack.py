"""WorkspaceCommandStack: per-document QUndoStack + WorkspaceCommand base.

Per ADR-005 (command stack) and `02 §25`. The command stack is the
canonical edit pathway for the workspace: every user-initiated
mutation enters through a `WorkspaceCommand` subclass that the UI
pushes onto a `WorkspaceCommandStack`. Direct calls to
`WorkspaceModel` mutation methods are reserved for project load,
migration, and command-internal use (the command itself calls the
model).

Design (decision B + A2 per the S1.B / S1.7 thread):

* **Stack ownership (B)**: The stack lives on `WorkspaceCommandStack`,
  not on `WorkspaceModel`. The model stays Qt-undo-agnostic — same
  rationale as ADR-003's UI / data separation: the source of truth
  does not know about the editing machinery. The shell (S1.9)
  instantiates one stack per open document.
* **Dirty-bit binding (A2)**: This module does NOT replace the
  model's `_set_dirty` / `_clear_dirty` helpers. Commands call
  model mutators which call `_set_dirty` as before. The
  `QUndoStack.cleanChanged` binding (S1.7.5) is additive — it
  lets the model react to undo-to-clean and save-to-clean
  transitions without rewriting the S1.3 mutation API.

The base `WorkspaceCommand` is a thin `QUndoCommand` subclass that
carries a reference to the target `WorkspaceModel`. Concrete
commands (AddComponentCommand, etc.) implement `redo()` and `undo()`
in terms of model methods.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
  (§"QUndoStack integration" — the cleanChanged binding is
  scheduled for S1.7.5; this module leaves the existing
  transition-only helpers in place per decision A2)
* `specs/02_workspace_requirements.md` §25 (Command Stack)
* `specs/07_implementation_order.md` §7.12 (Implementation Step
  Group G — Command System)
* `specs/09_coding_standards.md` §7.2.4 (Command naming)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand, QUndoStack

if TYPE_CHECKING:
    from PySide6.QtCore import QObject

    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class WorkspaceCommand(QUndoCommand):
    """Base class for every workspace-editing command (ADR-005).

    Holds the target `WorkspaceModel` reference and forwards the
    user-facing menu text to `QUndoCommand`. Subclasses implement
    `redo()` and `undo()` in terms of `self._model` mutators.

    Lifetime contract: a `WorkspaceCommand` must not outlive its
    model. In practice the `WorkspaceCommandStack` is destroyed
    before the model (Qt parent-child ownership when the stack is
    parented to the model, or explicit shutdown in S1.9).

    Subclasses MUST:

    * call `super().__init__(model, text)` with a stable
      user-facing label;
    * be idempotent under repeated `redo()` calls following
      undo→redo cycles (typically by capturing the post-redo
      state on first execution);
    * leave the model in its pre-`redo` state on `undo()` (the
      mutation must be reversible via documented `WorkspaceModel`
      API — `remove_component`, `restore_component`, etc.).

    Subclasses MUST NOT:

    * mutate the model from `__init__` — construction is
      side-effect-free; mutation happens in `redo()` (which
      `QUndoStack.push` invokes automatically per Qt's contract);
    * raise from `redo()` or `undo()` mid-execution — Qt's undo
      stack does not tolerate partial state. Validate inputs in
      `__init__` instead.
    """

    def __init__(self, model: WorkspaceModel, text: str = "") -> None:
        """Initialize the command with a target model and menu text."""
        super().__init__(text)
        self._model = model

    @property
    def model(self) -> WorkspaceModel:
        """Read-only access to the target model (test convenience)."""
        return self._model


class WorkspaceCommandStack:
    """Per-document `QUndoStack` wrapper bound to a `WorkspaceModel`.

    Owns the `QUndoStack` and holds a reference to the model so
    every pushed command can route through it. The wrapper is
    intentionally minimal: it forwards `push` / `undo` / `redo` /
    `can_undo` / `can_redo` to the underlying stack, plus exposes
    the stack itself for advanced bindings (S1.7.5 attaches the
    `cleanChanged` signal here).

    Phase 1 lifetime:

    * One stack per open document; the shell (S1.9) instantiates a
      stack when a project opens and destroys it when the project
      closes.
    * The stack does not own the model — it only references it.
      Model lifetime is managed by the shell.

    Tests construct the stack and the model directly without a
    `QApplication` (the data layer is testable headless per
    ADR-003); a `QUndoStack` does not require a running event loop
    for `push` / `undo` / `redo` invocations because those call the
    command methods synchronously.
    """

    def __init__(
        self,
        model: WorkspaceModel,
        parent: QObject | None = None,
    ) -> None:
        """Initialize with the target model and an optional Qt parent.

        Args:
            model: The `WorkspaceModel` whose mutations are
                undo/redo-tracked.
            parent: Optional Qt parent for the underlying
                `QUndoStack`. When the parent is destroyed, Qt
                destroys the stack — useful for tying the stack's
                lifetime to a document or shell window.
        """
        self._model = model
        self._stack = QUndoStack(parent) if parent is not None else QUndoStack()

    @property
    def model(self) -> WorkspaceModel:
        """The bound `WorkspaceModel`."""
        return self._model

    @property
    def stack(self) -> QUndoStack:
        """The underlying `QUndoStack`.

        Exposed for downstream bindings (e.g., the S1.7.5
        `cleanChanged` connection and S1.9 UI menu wiring). Tests
        should prefer the convenience methods on this wrapper.
        """
        return self._stack

    def push(self, command: WorkspaceCommand) -> None:
        """Push a command onto the stack.

        `QUndoStack.push` invokes `command.redo()` synchronously
        before returning, so by the time this call completes the
        model has already been mutated.
        """
        self._stack.push(command)

    def undo(self) -> None:
        """Undo the top command (no-op when `can_undo()` is False)."""
        self._stack.undo()

    def redo(self) -> None:
        """Redo the next command (no-op when `can_redo()` is False)."""
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
    "WorkspaceCommand",
    "WorkspaceCommandStack",
]
