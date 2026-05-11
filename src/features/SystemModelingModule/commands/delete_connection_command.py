"""DeleteConnectionCommand: undoable single-connection deletion.

Per ADR-005 and spec/07 §7.12. Single-target counterpart to
`DeleteComponentCommand` — connections are independent entities
in `02 §14`, so deletion has no cascade. The command captures
the full `Connection` on construction and toggles between
`remove_connection` (redo) and `restore_connection` (undo).

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `specs/02_workspace_requirements.md` §14, §25
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from features.SystemModelingModule.model.connection import Connection
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class DeleteConnectionCommand(WorkspaceCommand):
    """Undoable connection deletion (no cascade).

    Args:
        model: Target `WorkspaceModel`.
        connection_id: `con_<ULID>` of the connection to delete.
            Must exist in the model at construction time.

    Raises:
        KeyError: `connection_id` is not in the model.

    See Also:
        `WorkspaceModel.remove_connection`,
        `WorkspaceModel.restore_connection` (S1.7.3).
    """

    def __init__(self, model: WorkspaceModel, connection_id: str) -> None:
        """Construct and capture the full Connection for undo."""
        if connection_id not in model.connections:
            raise KeyError(connection_id)
        super().__init__(model, "Delete connection")
        # Capture the full frozen Connection for restore_connection
        # on undo — preserves the original con_<ULID> id and all
        # routing / label / style state across delete/undo cycles.
        self._captured_connection: Connection = model.connections[connection_id]

    @property
    def connection_id(self) -> str:
        """Target connection id (test convenience)."""
        return self._captured_connection.id

    def redo(self) -> None:
        """Remove the captured connection."""
        self._model.remove_connection(self._captured_connection.id)

    def undo(self) -> None:
        """Restore the captured connection verbatim."""
        self._model.restore_connection(self._captured_connection)


__all__ = ["DeleteConnectionCommand"]
