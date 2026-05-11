"""PasteSelectionCommand: undoable multi-entity paste.

Per ADR-005 and spec/07 §7.12 ("paste compound command
undo/redo"). Single QUndoStack entry that atomically inserts a
group of captured components and connections — typically the
output of a copy operation on a multi-selection.

Identity semantics (per the S1.7.5 planning thread):

* Pasted entities receive **new** `cmp_<ULID>` /
  `con_<ULID>` ids — paste is a blank-slate insertion, not a
  restoration. The captured instances' original ids are used
  only as a key for the source-set lookup; the new ids are
  freshly minted by `add_component_from_definition` and
  `add_connection`.
* `created_at` / `modified_at` / `display_id` are likewise
  fresh — the pasted entities are new entities, not copies of
  the originals.
* User-editable fields are preserved: `position`,
  `custom_label`, `rotation`, `parameters`, `tags`,
  `annotations` (for components); `routing`, `label`, `style`
  (for connections).

Connection remapping:

* Each captured connection's `source.component_id` /
  `target.component_id` is looked up in the old→new id map
  built during the component insertion phase.
* Half-orphan connections (one endpoint in the paste set, the
  other outside) are silently skipped at construction time.
  The S1.9 UI is expected to filter to "both endpoints in
  selection" before constructing the command; the silent skip
  here is a defensive backstop. The
  `skipped_connection_count` property exposes the count for
  diagnostic UI surfacing.

Undo / redo round-trip:

* First `redo()` mints new ids (the blank-slate semantic).
* `undo()` removes everything the first redo inserted.
* Subsequent `redo()` calls re-insert the previously-minted
  instances verbatim via `restore_component` /
  `restore_connection` (the captured-state pattern from
  S1.7.1 / S1.7.3) so ids and full record state survive
  cycles.

Atomicity: both `redo()` and `undo()` wrap their work in
`model.batch()` so subscribers see exactly one `modelChanged`
per direction carrying the cumulative diff.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `specs/02_workspace_requirements.md` §8, §14, §25
* `specs/07_implementation_order.md` §7.12 ("paste compound
  command undo/redo")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.connection import PortRef

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from collections.abc import Sequence

    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )
    from features.SystemModelingModule.model.connection import Connection
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class PasteSelectionCommand(WorkspaceCommand):
    """Multi-entity paste command (compound, single undo entry).

    Args:
        model: Target `WorkspaceModel`. MUST have a registry
            wired (`add_component_from_definition` requires it).
        components: Captured `ComponentInstance` records — the
            source-set of components to paste. Order is preserved
            in the new model.
        connections: Captured `Connection` records. Connections
            whose endpoints are not both inside the source-set
            are silently filtered out at construction time; the
            count is exposed via `skipped_connection_count`.

    Raises:
        RuntimeError: model has no registry wired (would block
            the first `redo()` from minting components).

    See Also:
        `WorkspaceModel.add_component_from_definition` (S1.B.1d),
        `WorkspaceModel.add_connection`,
        `WorkspaceModel.restore_component` (S1.7.1),
        `WorkspaceModel.restore_connection` (S1.7.3).
    """

    def __init__(
        self,
        model: WorkspaceModel,
        components: Sequence[ComponentInstance],
        connections: Sequence[Connection],
    ) -> None:
        """Construct, filter half-orphan connections, capture inputs."""
        if model.registry is None:
            raise RuntimeError(
                "PasteSelectionCommand requires a registry-wired WorkspaceModel; "
                "construct WorkspaceModel(registry=...)."
            )
        super().__init__(model, f"Paste {len(components)} component(s)")
        # Preserve component order for deterministic id-map traversal
        # and modelChanged diff order.
        self._source_components: tuple[ComponentInstance, ...] = tuple(components)
        source_ids = {c.id for c in self._source_components}
        input_connections = tuple(connections)
        # Silently filter half-orphan connections per the S1.7.5
        # planning thread. The S1.9 UI is expected to filter at the
        # selection layer; this is a defensive backstop so the
        # command never raises mid-redo.
        self._source_connections: tuple[Connection, ...] = tuple(
            conn
            for conn in input_connections
            if conn.source.component_id in source_ids and conn.target.component_id in source_ids
        )
        # Track the count of dropped connections for diagnostic UI.
        self._skipped_count: int = len(input_connections) - len(self._source_connections)
        # Filled on first redo; replayed on subsequent redos.
        self._new_components: list[ComponentInstance] = []
        self._new_connections: list[Connection] = []

    @property
    def new_component_ids(self) -> tuple[str, ...]:
        """Tuple of new component ids minted by the most recent redo.

        Empty before the first `redo()`. UI / tests use this to
        e.g. set the new selection to the pasted entities.
        """
        return tuple(c.id for c in self._new_components)

    @property
    def new_connection_ids(self) -> tuple[str, ...]:
        """Tuple of new connection ids minted by the most recent redo."""
        return tuple(c.id for c in self._new_connections)

    @property
    def skipped_connection_count(self) -> int:
        """Number of input connections dropped as half-orphan at construction.

        S1.9 UI may use this to surface a non-blocking warning
        ("3 connections not pasted — both endpoints required in
        the selection").
        """
        return self._skipped_count

    def _had_first_redo(self) -> bool:
        """True when the first redo has run and captured new ids."""
        return bool(self._new_components) or bool(self._new_connections)

    def redo(self) -> None:
        """Insert all pasted entities atomically.

        First execution mints new ids (blank-slate paste). Later
        executions after undo replay via `restore_component` /
        `restore_connection` to preserve identity across cycles.
        """
        if not self._had_first_redo():
            self._first_redo()
        else:
            self._restore_redo()

    def _first_redo(self) -> None:
        """First-pass mint: build the id-map, insert via add_*."""
        with self._model.batch():
            id_map: dict[str, str] = {}
            for captured in self._source_components:
                new_id = self._model.add_component_from_definition(
                    captured.definition_id,
                    QPointF(captured.position[0], captured.position[1]),
                    custom_label=captured.custom_label,
                    rotation=captured.rotation,
                    parameters=captured.parameters,
                    locked=captured.locked,
                    tags=captured.tags,
                    annotations=captured.annotations,
                )
                id_map[captured.id] = new_id
                self._new_components.append(self._model.components[new_id])
            for captured_conn in self._source_connections:
                remapped_source = PortRef(
                    component_id=id_map[captured_conn.source.component_id],
                    port_id=captured_conn.source.port_id,
                )
                remapped_target = PortRef(
                    component_id=id_map[captured_conn.target.component_id],
                    port_id=captured_conn.target.port_id,
                )
                new_conn_id = self._model.add_connection(
                    source=remapped_source,
                    target=remapped_target,
                    routing=captured_conn.routing,
                    label=captured_conn.label,
                    style=captured_conn.style,
                )
                self._new_connections.append(self._model.connections[new_conn_id])

    def _restore_redo(self) -> None:
        """Replay path: restore captured-on-first-redo records verbatim."""
        with self._model.batch():
            for instance in self._new_components:
                self._model.restore_component(instance)
            for conn in self._new_connections:
                self._model.restore_connection(conn)

    def undo(self) -> None:
        """Remove everything the most recent redo inserted (atomic).

        Order: connections first, then components — inverse of
        the redo order so any intermediate-state observer always
        sees connections referencing live components.
        """
        if not self._had_first_redo():
            return
        with self._model.batch():
            for conn in self._new_connections:
                self._model.remove_connection(conn.id)
            for instance in self._new_components:
                self._model.remove_component(instance.id)


__all__ = ["PasteSelectionCommand"]
