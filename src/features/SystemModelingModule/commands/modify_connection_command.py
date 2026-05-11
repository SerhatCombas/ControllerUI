"""ModifyConnectionCommand: undoable connection label / routing / style change.

Per ADR-005 and spec/07 §7.12. Wraps `WorkspaceModel.update_connection`
(the combo-updater with all-None no-op suppression) with the
captured-state pattern: `__init__` snapshots the pre-edit value of
every field actually being changed, `redo()` applies the new values,
`undo()` restores the captured prior values.

Args follow the combo-update pattern: pass only the fields you want
to change; pass `None` for fields to leave untouched. Per the S1.7.4
planning thread, an all-None invocation (no field actually being
changed) raises `ValueError` at construction — pushing an empty
command would pollute the undo stack with a no-op entry.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `specs/02_workspace_requirements.md` §14
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from collections.abc import Mapping

    from features.SystemModelingModule.model.connection import ConnectionRouting
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class ModifyConnectionCommand(WorkspaceCommand):
    """Undoable connection field update.

    Args:
        model: Target `WorkspaceModel`.
        connection_id: `con_<ULID>` of the target connection.
            Must exist in the model at construction time.
        label: New label, or `None` to leave unchanged.
        routing: New `ConnectionRouting`, or `None` to leave
            unchanged.
        style: New style mapping, or `None` to leave unchanged.

    Raises:
        KeyError: `connection_id` is not in the model.
        ValueError: all of `label` / `routing` / `style` are
            `None` (no field is being changed; the command would
            be a no-op on the undo stack).

    See Also:
        `WorkspaceModel.update_connection`.
    """

    def __init__(
        self,
        model: WorkspaceModel,
        connection_id: str,
        *,
        label: str | None = None,
        routing: ConnectionRouting | None = None,
        style: Mapping[str, Any] | None = None,
    ) -> None:
        """Construct and capture the prior state of the changed fields."""
        if connection_id not in model.connections:
            raise KeyError(connection_id)
        if label is None and routing is None and style is None:
            raise ValueError(
                "ModifyConnectionCommand requires at least one of "
                "label / routing / style to be set"
            )
        current = model.connections[connection_id]
        super().__init__(model, "Modify connection")
        self._connection_id = connection_id
        # Capture the new values for redo.
        self._new_label: str | None = label
        self._new_routing: ConnectionRouting | None = routing
        # Defensive copy of the supplied style mapping so subsequent
        # caller mutations do not bleed into redo replays.
        self._new_style: dict[str, Any] | None = dict(style) if style is not None else None
        # Capture the OLD values only for the fields actually being
        # changed — leaving unchanged fields' "old" slots as None
        # lets undo() route through update_connection with the
        # same combo-update semantics as redo().
        self._old_label: str | None = current.label if label is not None else None
        self._old_routing: ConnectionRouting | None = (
            current.routing if routing is not None else None
        )
        self._old_style: dict[str, Any] | None = dict(current.style) if style is not None else None

    @property
    def connection_id(self) -> str:
        """Target connection id (test convenience)."""
        return self._connection_id

    def redo(self) -> None:
        """Apply the new field values."""
        self._model.update_connection(
            self._connection_id,
            label=self._new_label,
            routing=self._new_routing,
            style=self._new_style,
        )

    def undo(self) -> None:
        """Restore the captured prior field values."""
        self._model.update_connection(
            self._connection_id,
            label=self._old_label,
            routing=self._old_routing,
            style=self._old_style,
        )


__all__ = ["ModifyConnectionCommand"]
