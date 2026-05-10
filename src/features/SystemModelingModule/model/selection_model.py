"""SelectionModel: data layer owner of current workspace selection state.

A dedicated `SelectionModel` (per `02 §21.3`) keeps selection state
out of the graphics items. The model emits `selectionChanged` whenever
the selection changes, and UI surfaces (workspace highlights,
component info panel, status area — `02 §21.3`) subscribe to that one
signal.

Multi-selection is supported from day one (`02 §21.2`): both component
and connection selection are sets, never single-valued. The signal
payload is a frozen `SelectionSnapshot`, which subscribers may hold
without defensive copies.

Selection of a component does not auto-select its connected wires
(`02 §21.4`); that policy is enforced by the *callers*. This model
faithfully tracks whatever selection state is set on it.

This module uses `PySide6.QtCore` only — no `QtWidgets`, no `QtGui`.
That keeps it on the data side of the UI/data boundary defined by
ADR-003 and verified by `tests/architecture/test_no_ui_in_model.py`.

References:
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `specs/02_workspace_requirements.md` §4.1 (`selectionChanged` signal)
* `specs/02_workspace_requirements.md` §21 (Selection System)
* `specs/02_workspace_requirements.md` §32.3 (Validation Indicators)
* `specs/09_coding_standards.md` §7.2.2 (Signal naming)
* `specs/09_coding_standards.md` §10 (PySide6 Conventions)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class SelectionSnapshot:
    """Immutable snapshot of the current workspace selection.

    Subscribers may hold references to a snapshot without copying;
    `frozenset` guarantees they cannot mutate it. The two id sets are
    disjoint by type (component IDs use the `cmp_` prefix; connection
    IDs use `con_`), but this class does not enforce the prefix —
    callers control what they put in.

    Attributes:
        component_ids: Internal ULIDs of currently selected
            components. Empty `frozenset` when nothing is selected.
        connection_ids: Internal ULIDs of currently selected
            connections. Empty `frozenset` when nothing is selected.
    """

    component_ids: frozenset[str] = frozenset()
    connection_ids: frozenset[str] = frozenset()

    @property
    def is_empty(self) -> bool:
        """Return True when nothing is selected."""
        return not self.component_ids and not self.connection_ids

    @property
    def total_count(self) -> int:
        """Total number of selected items across both types."""
        return len(self.component_ids) + len(self.connection_ids)


class SelectionModel(QObject):
    """Owns the current workspace selection state.

    Signals:
        selectionChanged(SelectionSnapshot): Emitted whenever the
            selection actually changes. Identical re-applications
            of the current selection are coalesced — see the
            "no-op suppression" notes on each mutation method.
            Payload is a `SelectionSnapshot`; signal is declared
            as `Signal(object)` for portability across PySide6
            versions.

    Selection of a component does not implicitly select its connected
    wires (`02 §21.4`). Callers must coordinate that policy; this
    model only tracks what it is told.
    """

    # Payload: SelectionSnapshot. `Signal(object)` is the portable
    # PySide6 declaration — `Signal(SelectionSnapshot)` works on 6.7+
    # but `object` works everywhere.
    selectionChanged = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize an empty selection.

        Args:
            parent: Qt parent for object-tree management. Defaults
                to `None` per `09 §10.1`.
        """
        super().__init__(parent)
        self._components: set[str] = set()
        self._connections: set[str] = set()

    # ------------------------------------------------------------------ #
    # Read-only API
    # ------------------------------------------------------------------ #

    def current(self) -> SelectionSnapshot:
        """Return an immutable snapshot of the current selection.

        Returns:
            A `SelectionSnapshot` with frozen views of the current
            component and connection selection.
        """
        return self._snapshot()

    def is_component_selected(self, component_id: str) -> bool:
        """Return True if the given component is currently selected."""
        return component_id in self._components

    def is_connection_selected(self, connection_id: str) -> bool:
        """Return True if the given connection is currently selected."""
        return connection_id in self._connections

    # ------------------------------------------------------------------ #
    # Mutation API
    # ------------------------------------------------------------------ #

    def select_only(
        self,
        *,
        components: Iterable[str] = (),
        connections: Iterable[str] = (),
    ) -> None:
        """Replace the current selection with the given items.

        This is the "click to select" operation: prior selection is
        discarded. Passing no arguments is equivalent to `clear()`.

        No-op suppression: if the resulting selection equals the
        current selection, no signal is emitted.

        Args:
            components: Iterable of component IDs to select.
            connections: Iterable of connection IDs to select.
        """
        new_components = set(components)
        new_connections = set(connections)
        if new_components == self._components and new_connections == self._connections:
            return
        self._components = new_components
        self._connections = new_connections
        self._emit_changed()

    def add(
        self,
        *,
        components: Iterable[str] = (),
        connections: Iterable[str] = (),
    ) -> None:
        """Extend the current selection with the given items.

        This is the "Shift-click" / "Shift-drag" operation: the
        existing selection is preserved and the new items are
        unioned in.

        No-op suppression: if all the requested items are already
        selected, no signal is emitted.

        Args:
            components: Iterable of component IDs to add.
            connections: Iterable of connection IDs to add.
        """
        new_components = set(components) - self._components
        new_connections = set(connections) - self._connections
        if not new_components and not new_connections:
            return
        self._components.update(new_components)
        self._connections.update(new_connections)
        self._emit_changed()

    def remove(
        self,
        *,
        components: Iterable[str] = (),
        connections: Iterable[str] = (),
    ) -> None:
        """Remove the given items from the current selection.

        IDs that are not currently selected are silently ignored.

        No-op suppression: if none of the requested items are
        actually present in the selection, no signal is emitted.

        Args:
            components: Iterable of component IDs to deselect.
            connections: Iterable of connection IDs to deselect.
        """
        removed_components = set(components) & self._components
        removed_connections = set(connections) & self._connections
        if not removed_components and not removed_connections:
            return
        self._components -= removed_components
        self._connections -= removed_connections
        self._emit_changed()

    def toggle(
        self,
        *,
        components: Iterable[str] = (),
        connections: Iterable[str] = (),
    ) -> None:
        """Flip the membership of the given items in the selection.

        For each ID, if it is currently selected it is deselected;
        otherwise it is added to the selection. This is the
        "Ctrl-click" / "Cmd-click" operation.

        No-op suppression: only triggered when both iterables are
        empty (toggling an item always changes its membership).

        Args:
            components: Iterable of component IDs to toggle.
            connections: Iterable of connection IDs to toggle.
        """
        components_set = set(components)
        connections_set = set(connections)
        if not components_set and not connections_set:
            return
        self._components ^= components_set
        self._connections ^= connections_set
        self._emit_changed()

    def clear(self) -> None:
        """Clear the selection.

        Equivalent to `select_only()` with no arguments. Same
        no-op suppression: if the selection is already empty, no
        signal is emitted.
        """
        if not self._components and not self._connections:
            return
        self._components.clear()
        self._connections.clear()
        self._emit_changed()

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _snapshot(self) -> SelectionSnapshot:
        """Build a frozen snapshot of the current state."""
        return SelectionSnapshot(
            component_ids=frozenset(self._components),
            connection_ids=frozenset(self._connections),
        )

    def _emit_changed(self) -> None:
        """Emit `selectionChanged` with a fresh immutable snapshot."""
        self.selectionChanged.emit(self._snapshot())


__all__ = [
    "SelectionModel",
    "SelectionSnapshot",
]
