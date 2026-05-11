"""MoveComponentCommand: undoable component position change.

Per ADR-005 and spec/07 §7.12. Captures the old position from the
model at construction time, applies the new position via
`WorkspaceModel.move_component` on `redo()`, and restores the
captured old position on `undo()`.

The model's `move_component` already enforces ε-tolerance no-op
suppression (`02 §22`, ADR-020), so constructing a command with
`new_pos` within ε of the current position is harmless — the
redo / undo cycle no-ops at the model layer. UI flows should
nevertheless avoid pushing zero-effect commands to keep the
undo stack readable.

TODO(S1.7.future): Override `QUndoCommand.id()` and `mergeWith()`
to coalesce consecutive moves of the same component into one
undoable command. Per ADR-005 §"Command merging" — a multi-frame
drag should leave one entry on the stack, not N. The current
implementation produces one command per release; mergeWith()
becomes meaningful once the UI (S1.9) emits intermediate move
commands during a drag. Same TODO applies to
`RotateComponentCommand` and `ChangeParameterCommand`.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
  §"Command merging"
* `decisions/ADR-020-dirty-tracking-semantics.md`
  (ε-tolerance no-op rule)
* `specs/02_workspace_requirements.md` §22 (Move/Delete)
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class MoveComponentCommand(WorkspaceCommand):
    """Undoable component position change.

    Args:
        model: Target `WorkspaceModel`.
        component_id: `cmp_<ULID>` of the component to move. Must
            exist in the model at construction time.
        new_pos: Target scene-coordinate position.

    Raises:
        KeyError: `component_id` is not in the model.

    See Also:
        `WorkspaceModel.move_component`.
    """

    def __init__(
        self,
        model: WorkspaceModel,
        component_id: str,
        new_pos: QPointF,
    ) -> None:
        """Construct and capture the pre-move position."""
        # Pre-validate existence so a failing command never lands on
        # the undo stack. Raising here propagates synchronously to
        # the caller; pushing would invoke redo() which would itself
        # raise mid-stack-mutation, leaving the stack inconsistent.
        if component_id not in model.components:
            raise KeyError(component_id)
        current = model.components[component_id]
        # Resolve the user-facing menu text from the component's
        # display name (fallback to "component" if missing).
        label = current.display_name or "component"
        super().__init__(model, f"Move {label}")
        self._component_id = component_id
        # Capture the pre-move position from the immutable instance.
        # Position is stored as tuple[float, float] on the dataclass;
        # convert to QPointF for symmetry with `new_pos`.
        self._old_pos = QPointF(current.position[0], current.position[1])
        self._new_pos = QPointF(new_pos)

    @property
    def component_id(self) -> str:
        """Target component id (test convenience)."""
        return self._component_id

    @property
    def old_pos(self) -> QPointF:
        """Pre-move position captured at construction (test convenience)."""
        return QPointF(self._old_pos)

    @property
    def new_pos(self) -> QPointF:
        """Target position (test convenience)."""
        return QPointF(self._new_pos)

    def redo(self) -> None:
        """Apply the move to `new_pos`."""
        self._model.move_component(self._component_id, self._new_pos)

    def undo(self) -> None:
        """Restore the captured `old_pos`."""
        self._model.move_component(self._component_id, self._old_pos)


__all__ = ["MoveComponentCommand"]
