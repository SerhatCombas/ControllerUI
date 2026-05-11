"""WorkspaceScene: QGraphicsScene subscribed to a WorkspaceModel.

Per spec/07 §7.13. The scene is the view-layer mirror of the
workspace model: it subscribes to every model mutation signal
and translates each into create / update / remove operations on
graphics items.

S1.9.2 scope: component lifecycle wired through
`ComponentGraphicsItem`. `_on_component_added` mints an item
(short-name resolution via the model's registry when wired),
`_on_component_removed` cleans it up, `_on_component_moved` /
`_on_component_rotated` push position/rotation into the existing
item, `_on_component_changed` refreshes cached display fields.
`_on_model_changed` (batch path) replays all four operations
from the change_set in one pass.

Connection items remain placeholders — they land in S1.9.5.

Design rules (per ADR-003 + spec/07 §7.13):

* The scene **renders model state**; it does not store
  business state. Item lookup goes through the internal
  `_component_items` / `_connection_items` dicts that mirror
  the model's id → item mapping; the model remains the source
  of truth.
* All model-mutation responses live in slots connected to
  the model's 13 signals; the scene never calls model
  mutators directly. User-initiated mutations originate from
  view-layer events (drag-drop, mouse drag) and route through
  the command stack.
* Z-order is deterministic: grid at `GRID_Z_VALUE = -100`,
  components at z=0 (default), connections at z=10 (above
  components so wires draw over component edges), ports at
  z=20 (above their parent component for hit-testing).

References:
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `specs/02_workspace_requirements.md` §2 (Workspace), §4
  (Signals), §15 (Grid)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QGraphicsScene

from .component_graphics_item import ComponentGraphicsItem
from .grid_background_item import GridBackgroundItem

if TYPE_CHECKING:
    from PySide6.QtCore import QObject, QPointF

    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )
    from features.SystemModelingModule.model.workspace_change_set import (
        WorkspaceChangeSet,
    )
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


logger = logging.getLogger(__name__)


class WorkspaceScene(QGraphicsScene):
    """View-layer scene mirroring a `WorkspaceModel`.

    Args:
        model: The `WorkspaceModel` whose mutations drive this
            scene's contents. The scene holds a reference to the
            model and connects to every mutation signal during
            `__init__`.
        parent: Optional Qt parent for the scene.

    See Also:
        `WorkspaceView` — `QGraphicsView` host for this scene.
        `GridBackgroundItem` — the default-installed grid.
    """

    def __init__(
        self,
        model: WorkspaceModel,
        parent: QObject | None = None,
    ) -> None:
        """Construct, install the grid, and wire model signals."""
        super().__init__(parent)
        self._model: WorkspaceModel = model
        # Internal mirror dicts. `_component_items` is populated
        # by S1.9.2's signal slots; `_connection_items` lands in
        # S1.9.5.
        self._component_items: dict[str, ComponentGraphicsItem] = {}
        self._connection_items: dict[str, object] = {}
        # Install the grid first so it sits at the back of the
        # stacking order via its `GRID_Z_VALUE`.
        self._grid_item: GridBackgroundItem = GridBackgroundItem()
        self.addItem(self._grid_item)
        # Wire model signals.
        self._connect_model_signals()

    @property
    def model(self) -> WorkspaceModel:
        """Read-only access to the bound model (test convenience)."""
        return self._model

    @property
    def grid_item(self) -> GridBackgroundItem:
        """Read-only access to the grid background item."""
        return self._grid_item

    def _resolve_label(self, instance: ComponentInstance) -> str:
        """Resolve the on-canvas label for an instance.

        Prefers the `ComponentDefinition.short_name` from the
        wired registry; falls back to the empty string when the
        registry is not wired, the definition is missing, or the
        definition does not declare a `short_name`. The
        `ComponentGraphicsItem` constructor handles the empty
        case by deriving a placeholder from `display_name`.
        """
        registry = self._model.registry
        if registry is None or not registry.has(instance.definition_id):
            return ""
        return registry.get(instance.definition_id).short_name

    def _connect_model_signals(self) -> None:
        """Wire the 10 model signals the scene cares about.

        The scene ignores `selectionChanged` (info-panel concern),
        `validationChanged` (validation-panel concern), and
        `dirtyChanged` (title-bar concern). It listens to the 10
        mutation / structural signals from ADR-018 / ADR-019:

        * componentAdded / componentRemoved / componentChanged /
          componentMoved / componentRotated
        * connectionAdded / connectionRemoved / connectionChanged
        * modelReset
        * modelChanged (batch)
        """
        m = self._model
        m.componentAdded.connect(self._on_component_added)
        m.componentRemoved.connect(self._on_component_removed)
        m.componentChanged.connect(self._on_component_changed)
        m.componentMoved.connect(self._on_component_moved)
        m.componentRotated.connect(self._on_component_rotated)
        m.connectionAdded.connect(self._on_connection_added)
        m.connectionRemoved.connect(self._on_connection_removed)
        m.connectionChanged.connect(self._on_connection_changed)
        m.modelReset.connect(self._on_model_reset)
        m.modelChanged.connect(self._on_model_changed)

    # ------------------------------------------------------------------ #
    # Component-related slots (S1.9.2)
    # ------------------------------------------------------------------ #

    def _on_component_added(self, component_id: str) -> None:
        """Mint a `ComponentGraphicsItem` for the new component.

        Reads the fresh `ComponentInstance` from the model,
        resolves the on-canvas label via the registry (when
        wired), and registers the item in `_component_items`.
        If the id is already in the dict, this is a defensive
        no-op — the addition was already handled (e.g., by a
        replay of the same signal).
        """
        if component_id in self._component_items:
            return
        instance = self._model.components.get(component_id)
        if instance is None:
            logger.warning(
                "componentAdded fired for unknown id %s; ignoring", component_id
            )
            return
        label = self._resolve_label(instance)
        item = ComponentGraphicsItem(instance, label=label)
        self.addItem(item)
        self._component_items[component_id] = item

    def _on_component_removed(self, component_id: str) -> None:
        """Remove the `ComponentGraphicsItem` for a deleted component."""
        item = self._component_items.pop(component_id, None)
        if item is not None:
            self.removeItem(item)

    def _on_component_changed(self, component_id: str) -> None:
        """Refresh the item's cached display fields from the new instance."""
        item = self._component_items.get(component_id)
        if item is None:
            return
        instance = self._model.components.get(component_id)
        if instance is None:
            return
        # The label could change in principle (if a future
        # `componentChanged` payload carried a definition swap),
        # but in Phase 1 the short_name is fixed for a given
        # `definition_id`. Pass `None` to keep the existing label.
        item.update_from_instance(instance, label=None)

    def _on_component_moved(
        self,
        component_id: str,
        old_pos: QPointF,
        new_pos: QPointF,
    ) -> None:
        """Push the new position into the item."""
        item = self._component_items.get(component_id)
        if item is None:
            return
        item.setPos(new_pos)
        # `old_pos` is unused at the view layer — the item's
        # current position is the source of truth for any
        # forthcoming wire-endpoint updates (S1.9.5).
        _ = old_pos

    def _on_component_rotated(
        self,
        component_id: str,
        old_rotation: float,
        new_rotation: float,
    ) -> None:
        """Push the new rotation into the item."""
        item = self._component_items.get(component_id)
        if item is None:
            return
        item.setRotation(new_rotation)
        _ = old_rotation  # unused at the view layer

    # ------------------------------------------------------------------ #
    # Connection-related slots (S1.9.5 fills these in)
    # ------------------------------------------------------------------ #

    def _on_connection_added(self, connection_id: str) -> None:
        """Handle a new connection.

        S1.9.1: placeholder. S1.9.5 will mint a
        `ConnectionGraphicsItem` and register it in
        `_connection_items`.
        """
        logger.debug("connectionAdded (S1.9.5 will render): %s", connection_id)

    def _on_connection_removed(self, connection_id: str) -> None:
        """Handle a connection removal."""
        logger.debug("connectionRemoved (S1.9.5 will derender): %s", connection_id)

    def _on_connection_changed(self, connection_id: str) -> None:
        """Handle a connection property edit (label / routing / style)."""
        logger.debug("connectionChanged (S1.9.5 will update): %s", connection_id)

    # ------------------------------------------------------------------ #
    # Structural slots
    # ------------------------------------------------------------------ #

    def _on_model_reset(self) -> None:
        """Clear all component / connection items.

        Preserves the grid item — only model-derived items are
        removed. S1.9.2 onwards will populate the dicts; the
        loop iterates whatever is present at reset time.
        """
        for item in list(self._component_items.values()):
            self.removeItem(item)  # type: ignore[arg-type]
        self._component_items.clear()
        for item in list(self._connection_items.values()):
            self.removeItem(item)  # type: ignore[arg-type]
        self._connection_items.clear()
        logger.debug("modelReset handled: scene cleared (grid retained)")

    def _on_model_changed(self, change_set: WorkspaceChangeSet) -> None:
        """Handle a batched mutation (ADR-019).

        Per ADR-019 the fine-grained signals are suppressed
        inside a `model.batch()`; the scene must drive its
        component-item lifecycle from the change_set instead.
        Connection items (S1.9.5) will get the same treatment.

        Order within the batch:

        1. Remove items for `removed_components` (cleanup before
           additions so any id collision in a future
           remove-then-add-with-same-id flow is handled
           correctly).
        2. Add items for `added_components`.
        3. Update items for `changed_components` — both
           position/rotation (re-read from the instance) and
           cached display fields.
        """
        if change_set.reset_required:
            # The `modelReset` signal already fired the full
            # cleanup path inside the batch; nothing more to do.
            return
        for cid in change_set.removed_components:
            self._on_component_removed(cid)
        for cid in change_set.added_components:
            self._on_component_added(cid)
        for cid in change_set.changed_components:
            instance = self._model.components.get(cid)
            item = self._component_items.get(cid)
            if instance is None or item is None:
                continue
            # Re-sync position + rotation in case the change
            # batch combined move/rotate with other edits — the
            # fine-grained slots were suppressed, so the item
            # has not been told yet.
            item.setPos(instance.position[0], instance.position[1])
            item.setRotation(instance.rotation)
            item.update_from_instance(instance, label=None)


__all__ = ["WorkspaceScene"]
