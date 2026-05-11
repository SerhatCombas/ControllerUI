"""DeleteComponentCommand: undoable component deletion with cascade.

Per ADR-005 and spec/07 §7.12. Deleting a component also removes
every connection that references it on either endpoint — leaving
orphaned connections would violate the connection model's
identity invariant (`02 §14`, ADR-002: a `PortRef` always names a
live component).

The cascade set is captured at construction time so the undo path
can restore both the component and all cascaded connections with
their original `cmp_<ULID>` / `con_<ULID>` ids. This preserves
referential identity across delete / undo cycles, which is the
load-bearing semantic for connection routing, validation reports,
and any future graph caches.

Atomicity: redo and undo both wrap their mutations in
`model.batch()` per ADR-019 so subscribers see exactly one
`modelChanged(change_set)` per direction rather than N+1
fine-grained signals (one per connection plus one for the
component). The change_set's `removed_components` /
`removed_connections` (or `added_*` on undo) lists carry the full
cascade so UI can re-render in one pass.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `specs/02_workspace_requirements.md` §8, §14, §22, §25
* `specs/07_implementation_order.md` §7.12 ("delete component
  with attached connections undo/redo")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )
    from features.SystemModelingModule.model.connection import Connection
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class DeleteComponentCommand(WorkspaceCommand):
    """Undoable component deletion with connection cascade.

    Args:
        model: Target `WorkspaceModel`.
        component_id: `cmp_<ULID>` of the component to delete. Must
            exist in the model at construction time.

    Raises:
        KeyError: `component_id` is not in the model.

    See Also:
        `WorkspaceModel.connections_for_component`,
        `WorkspaceModel.restore_component`,
        `WorkspaceModel.restore_connection`.
    """

    def __init__(self, model: WorkspaceModel, component_id: str) -> None:
        """Construct and capture the cascade set."""
        if component_id not in model.components:
            raise KeyError(component_id)
        instance = model.components[component_id]
        label = instance.display_name or "component"
        super().__init__(model, f"Delete {label}")
        # Capture the full instance for restore_component on undo.
        self._captured_instance: ComponentInstance = instance
        # Capture all cascaded connections in insertion order. The
        # tuple is frozen-by-default and the Connection dataclass is
        # frozen too, so the capture is safe to keep across cycles.
        self._captured_connections: tuple[Connection, ...] = model.connections_for_component(
            component_id
        )

    @property
    def component_id(self) -> str:
        """Target component id (test convenience)."""
        return self._captured_instance.id

    @property
    def cascaded_connections(self) -> tuple[Connection, ...]:
        """Tuple of connections deleted alongside the component."""
        return self._captured_connections

    def redo(self) -> None:
        """Delete cascaded connections then the component, atomically.

        The model's batch context coalesces the fine-grained signals
        into a single `modelChanged(change_set)` per ADR-019. Order
        within the batch: connections first, then the component
        (so any future invariants that rely on no-orphan-connection
        ordering are satisfied at each intermediate step).
        """
        with self._model.batch():
            for conn in self._captured_connections:
                self._model.remove_connection(conn.id)
            self._model.remove_component(self._captured_instance.id)

    def undo(self) -> None:
        """Restore the component then the cascaded connections, atomically.

        Order within the batch: component first, then connections
        (so connections always reference a live component when
        re-inserted — the inverse of the delete order).
        """
        with self._model.batch():
            self._model.restore_component(self._captured_instance)
            for conn in self._captured_connections:
                self._model.restore_connection(conn)


__all__ = ["DeleteComponentCommand"]
