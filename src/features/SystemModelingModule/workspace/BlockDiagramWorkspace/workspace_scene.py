"""WorkspaceScene: QGraphicsScene subscribed to a WorkspaceModel.

Per spec/07 §7.13. The scene is the view-layer mirror of the
workspace model: it subscribes to every model mutation signal
and translates each into create / update / remove operations on
graphics items.

S1.9.1 scope: scene skeleton + grid. All model-mutation slots
are present and connected but render no items beyond the grid.
S1.9.2 will fill in `_on_component_added` /
`_on_component_removed` / `_on_component_moved` /
`_on_component_rotated` with `ComponentGraphicsItem` creation
and synchronization. S1.9.5 will add connection items.

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

from .grid_background_item import GridBackgroundItem

if TYPE_CHECKING:
    from PySide6.QtCore import QObject, QPointF

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
        # Internal mirror dicts. Populated by signal slots in
        # later S1.9.x sub-commits; declared here so the contract
        # is stable from the start.
        self._component_items: dict[str, object] = {}
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
    # Component-related slots (S1.9.2 fills these in)
    # ------------------------------------------------------------------ #

    def _on_component_added(self, component_id: str) -> None:
        """Handle a new component placement.

        S1.9.1: placeholder — logs the event. S1.9.2 will mint a
        `ComponentGraphicsItem` for the new component, position
        it from `model.components[component_id].position`, and
        register it in `_component_items`.
        """
        logger.debug("componentAdded (S1.9.2 will render): %s", component_id)

    def _on_component_removed(self, component_id: str) -> None:
        """Handle a component removal.

        S1.9.1: placeholder. S1.9.2 will look up the item in
        `_component_items`, remove it from the scene, and drop
        the dict entry.
        """
        logger.debug("componentRemoved (S1.9.2 will derender): %s", component_id)

    def _on_component_changed(self, component_id: str) -> None:
        """Handle a component property edit.

        S1.9.1: placeholder. S1.9.2 will re-read the instance and
        update the corresponding `ComponentGraphicsItem` (label,
        visual variant, locked state, etc.).
        """
        logger.debug("componentChanged (S1.9.2 will update): %s", component_id)

    def _on_component_moved(
        self,
        component_id: str,
        old_pos: QPointF,
        new_pos: QPointF,
    ) -> None:
        """Handle a component position change.

        S1.9.1: placeholder. S1.9.2 will move the corresponding
        `ComponentGraphicsItem` to `new_pos` and S1.9.5 will
        update any connected wire endpoints.
        """
        logger.debug(
            "componentMoved (S1.9.2 will reposition): %s %s -> %s",
            component_id,
            old_pos,
            new_pos,
        )

    def _on_component_rotated(
        self,
        component_id: str,
        old_rotation: float,
        new_rotation: float,
    ) -> None:
        """Handle a component rotation change.

        S1.9.1: placeholder. S1.9.2 will set the item's rotation
        and S1.9.5 will update port visual positions.
        """
        logger.debug(
            "componentRotated (S1.9.2 will reorient): %s %s -> %s",
            component_id,
            old_rotation,
            new_rotation,
        )

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

        S1.9.1: placeholder — logs the diff summary. Later
        sub-commits may choose to override fine-grained slot
        dispatch inside a batch and re-render directly from the
        change_set for performance.
        """
        logger.debug(
            "modelChanged (S1.9.x batch render): "
            "added_components=%d removed_components=%d "
            "added_connections=%d removed_connections=%d "
            "reset=%s",
            len(change_set.added_components),
            len(change_set.removed_components),
            len(change_set.added_connections),
            len(change_set.removed_connections),
            change_set.reset_required,
        )


__all__ = ["WorkspaceScene"]
