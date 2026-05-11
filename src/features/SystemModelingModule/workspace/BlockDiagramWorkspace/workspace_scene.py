"""WorkspaceScene: QGraphicsScene subscribed to a WorkspaceModel.

Per spec/07 §7.13. The scene is the view-layer mirror of the
workspace model: it subscribes to every model mutation signal
and translates each into create / update / remove operations on
graphics items.

S1.9.3 scope: scene-level drag-drop entry points wired to the
command stack so a library-panel drop on the canvas pushes an
`AddComponentCommand`. The load-bearing logic lives in the
public `drop_component(definition_id, scene_pos)` method; the
Qt event overrides (`dragEnterEvent` / `dragMoveEvent` /
`dropEvent`) thin-wrap it. Drop positions are snapped to the
grid via `snap_to_grid` before being passed to the command, so
placement always aligns with the visual grid.

Earlier sub-commits:

* S1.9.1 — scene skeleton, grid item, signal wiring.
* S1.9.2 — component lifecycle: `_on_component_added` mints a
  `ComponentGraphicsItem`, the rest of the component slots
  synchronize position / rotation / cached fields, and the
  batch path replays the change_set.

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
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from features.SystemModelingModule.commands import (
    AddComponentCommand,
    MoveComponentCommand,
    RotateComponentCommand,
)

from .component_graphics_item import ComponentGraphicsItem
from .grid_background_item import DEFAULT_GRID_SPACING, GridBackgroundItem

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QGraphicsSceneDragDropEvent

    from features.SystemModelingModule.commands import WorkspaceCommandStack
    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )
    from features.SystemModelingModule.model.workspace_change_set import (
        WorkspaceChangeSet,
    )
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


# MIME type for drag-and-drop payloads originating from the
# library panel. The payload body is the dotted-namespace
# definition id of the dragged component (e.g.,
# `"electrical.analog.components.resistor"`). The constant is
# exported so both ends of the drag interaction (library panel
# producer, workspace scene consumer) can reference the same
# string without drift.
COMPONENT_MIME_TYPE: Final[str] = "application/x-system-model-component"


def snap_to_grid(value: float, spacing: float = DEFAULT_GRID_SPACING) -> float:
    """Snap a scene-coordinate value to the nearest grid multiple.

    Per `02 §15`: placement always aligns to the grid. The scene
    uses this helper on drop positions so components land on
    grid intersections; the same helper will serve S1.9.4 move
    gestures.

    Uses standard rounding (half-up via `round`), so values
    exactly on the midpoint between two grid lines round to the
    nearest even multiple per Python's banker's rounding rule —
    acceptable for placement (drift is at most spacing/2).
    """
    return round(value / spacing) * spacing


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
        command_stack: WorkspaceCommandStack | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Construct, install the grid, and wire model signals.

        Args:
            model: The `WorkspaceModel` the scene mirrors.
            command_stack: Optional `WorkspaceCommandStack` used
                by drag-drop / mouse-gesture flows to push
                `AddComponentCommand` / move / rotate commands.
                When `None`, drops are ignored with a warning
                log and S1.9.4 gestures will likewise no-op —
                the scene stays usable in tests that exercise
                only the signal pathway.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._model: WorkspaceModel = model
        self._command_stack: WorkspaceCommandStack | None = command_stack
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

    @property
    def command_stack(self) -> WorkspaceCommandStack | None:
        """The bound `WorkspaceCommandStack`, or `None` when unwired."""
        return self._command_stack

    # ------------------------------------------------------------------ #
    # Public drag-drop entry point (S1.9.3)
    # ------------------------------------------------------------------ #

    def drop_component(
        self,
        definition_id: str,
        scene_pos: QPointF,
    ) -> str | None:
        """Place a component at `scene_pos` via the command stack.

        Snaps `scene_pos` to the nearest grid intersection,
        constructs an `AddComponentCommand`, and pushes it onto
        the bound `WorkspaceCommandStack`. The command's
        `__init__` pre-validates the registry and definition id;
        a `KeyError` from the registry propagates to the caller
        so the drop handler can surface it.

        Args:
            definition_id: Dotted-namespace identifier of a
                registered `ComponentDefinition`.
            scene_pos: Scene-coordinate drop position
                (typically `event.scenePos()` from a Qt drop
                event).

        Returns:
            The new component's `cmp_<ULID>` id when the
            command pushed successfully, or `None` when no
            command stack is wired (in which case a warning is
            logged and the drop is dropped on the floor).

        Raises:
            KeyError: `definition_id` is not in the registry.
            RuntimeError: model has no registry wired (surfaced
                from `AddComponentCommand.__init__`).
        """
        if self._command_stack is None:
            logger.warning(
                "drop_component called without a command_stack; "
                "ignoring drop of '%s' at (%.1f, %.1f)",
                definition_id,
                scene_pos.x(),
                scene_pos.y(),
            )
            return None
        snapped = QPointF(snap_to_grid(scene_pos.x()), snap_to_grid(scene_pos.y()))
        command = AddComponentCommand(self._model, definition_id, snapped)
        self._command_stack.push(command)
        return command.component_id

    # ------------------------------------------------------------------ #
    # Mouse-gesture command bridges (S1.9.4)
    # ------------------------------------------------------------------ #

    def commit_component_move(
        self,
        component_id: str,
        new_pos: QPointF,
    ) -> bool:
        """Push a `MoveComponentCommand` for a finished drag.

        Called by `ComponentGraphicsItem.commit_drag` on mouse
        release. `new_pos` is the snapped target position; the
        item has already been reverted to its pre-drag position
        so the model-canonical move signal drives the final
        visual update.

        Args:
            component_id: Target component id.
            new_pos: Scene-coordinate target position (already
                grid-snapped by the caller).

        Returns:
            True if a command was pushed; False when no
            `command_stack` is wired or the component is no
            longer in the model.
        """
        if self._command_stack is None:
            logger.warning(
                "commit_component_move called without a command_stack; "
                "ignoring move of '%s' to (%.1f, %.1f)",
                component_id,
                new_pos.x(),
                new_pos.y(),
            )
            return False
        if component_id not in self._model.components:
            logger.warning(
                "commit_component_move for unknown component_id '%s'; ignoring",
                component_id,
            )
            return False
        command = MoveComponentCommand(self._model, component_id, new_pos)
        self._command_stack.push(command)
        return True

    def rotate_selected_components(self, angle_delta: float = 90.0) -> int:
        """Rotate each selected component by `angle_delta` degrees.

        Pushes one `RotateComponentCommand` per selected
        `ComponentGraphicsItem`. The target rotation is
        `(current + angle_delta) % 360.0`, snapped to the Phase-1
        grid `{0, 90, 180, 270}` by `RotateComponentCommand`'s
        own pre-validation.

        Multi-select rotation produces N separate commands on the
        stack. Callers that want to coalesce them into a single
        undo entry should wrap the call in `model.batch()` (which
        suppresses individual signals but the stack still pushes
        N entries — true single-entry coalescing waits for
        QUndoStack macro support in a future stage).

        Args:
            angle_delta: Rotation step in degrees. Phase 1 callers
                pass 90.0 or -90.0; other values will likely
                fail the rotation command's grid pre-validation.

        Returns:
            Number of commands pushed.
        """
        if self._command_stack is None:
            return 0
        pushed = 0
        for item in self.selectedItems():
            if not isinstance(item, ComponentGraphicsItem):
                continue
            instance = self._model.components.get(item.component_id)
            if instance is None:
                continue
            new_rotation = (instance.rotation + angle_delta) % 360.0
            command = RotateComponentCommand(self._model, item.component_id, new_rotation)
            self._command_stack.push(command)
            pushed += 1
        return pushed

    def _accepts_mime(self, mime_data: object) -> bool:
        """Return True if `mime_data` carries our component drag payload.

        Extracted so tests can verify the predicate without
        constructing a full `QGraphicsSceneDragDropEvent` (which
        PySide6 does not expose a public constructor for).
        """
        # `mime_data` is typed as `object` because the same
        # predicate is called from `dragEnterEvent` /
        # `dragMoveEvent` / `dropEvent` overrides where Qt
        # passes a `QMimeData` subclass; the only attribute we
        # need is `hasFormat(str) -> bool`.
        has_format = getattr(mime_data, "hasFormat", None)
        if not callable(has_format):
            return False
        return bool(has_format(COMPONENT_MIME_TYPE))

    # ------------------------------------------------------------------ #
    # Qt drag-drop event overrides
    # ------------------------------------------------------------------ #

    def dragEnterEvent(  # noqa: N802 — Qt API override
        self,
        event: QGraphicsSceneDragDropEvent,
    ) -> None:
        """Accept the drag iff the payload carries our MIME type."""
        if self._accepts_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(  # noqa: N802 — Qt API override
        self,
        event: QGraphicsSceneDragDropEvent,
    ) -> None:
        """Accept the drag-move so the subsequent `dropEvent` fires."""
        if self._accepts_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(  # noqa: N802 — Qt API override
        self,
        event: QGraphicsSceneDragDropEvent,
    ) -> None:
        """Extract the definition id and route through `drop_component`."""
        mime = event.mimeData()
        if not self._accepts_mime(mime):
            event.ignore()
            return
        try:
            # `mime.data(...)` returns `QByteArray` at runtime;
            # `bytes(QByteArray)` is valid but mypy's stubs do not
            # cover the overload, hence the explicit cast.
            payload: bytes = bytes(mime.data(COMPONENT_MIME_TYPE))  # type: ignore[call-overload]
            definition_id = payload.decode("utf-8")
        except (UnicodeDecodeError, TypeError):
            logger.warning("dropEvent: undecodable MIME payload; ignoring")
            event.ignore()
            return
        try:
            self.drop_component(definition_id, event.scenePos())
        except KeyError:
            # Registry rejected the id — log and let the drop
            # quietly fail. Phase 1 has no visual feedback for
            # rejected drops; S1.6 validation work may surface
            # this through the validation panel later.
            logger.warning(
                "dropEvent: definition '%s' not in registry; drop ignored",
                definition_id,
            )
            event.ignore()
            return
        event.acceptProposedAction()

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
            logger.warning("componentAdded fired for unknown id %s; ignoring", component_id)
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
        for component_item in list(self._component_items.values()):
            self.removeItem(component_item)
        self._component_items.clear()
        for connection_item in list(self._connection_items.values()):
            # `_connection_items` is dict[str, object] until S1.9.5
            # introduces `ConnectionGraphicsItem`. The cast is safe
            # because the only thing the scene stores in this dict
            # is `QGraphicsItem` instances supplied by future
            # slot implementations.
            self.removeItem(connection_item)  # type: ignore[arg-type]
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
