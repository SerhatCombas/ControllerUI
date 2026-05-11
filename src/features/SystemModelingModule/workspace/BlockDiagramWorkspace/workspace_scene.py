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

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene

from features.SystemModelingModule.commands import (
    AddComponentCommand,
    AddConnectionCommand,
    ConnectionValidationError,
    MoveComponentCommand,
    RotateComponentCommand,
)
from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.validation_report import ValidationReport

from .component_graphics_item import ComponentGraphicsItem
from .connection_graphics_item import CONNECTION_Z_VALUE, ConnectionGraphicsItem
from .grid_background_item import DEFAULT_GRID_SPACING, GridBackgroundItem
from .port_graphics_item import PortGraphicsItem

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import (
        QGraphicsSceneDragDropEvent,
        QGraphicsSceneMouseEvent,
    )

    from features.SystemModelingModule.commands import WorkspaceCommandStack
    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )
    from features.SystemModelingModule.model.workspace_change_set import (
        WorkspaceChangeSet,
    )
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel
    from shared.registry import PortDefinition


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

    # Emitted when `commit_connection_draw` catches a
    # `ConnectionValidationError`. Carries the full
    # `ValidationReport` so consumers can render any subset of
    # issues (first error in S1.10.1; multi-issue dialog or
    # inline panel possible in S1.11 polish without changing the
    # signal contract — follows ADR-018's "extensible payload"
    # principle).
    connectionRejected = Signal(ValidationReport)  # noqa: N815 — PySide6 signal naming (spec/09 §7.2.2)

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
        # by S1.9.2's signal slots; `_connection_items` is
        # populated by S1.9.5a's slots.
        self._component_items: dict[str, ComponentGraphicsItem] = {}
        self._connection_items: dict[str, ConnectionGraphicsItem] = {}
        # S1.9.5b connection-draw drag state. `_pending_source`
        # holds the originating `PortRef` between `mousePress` on
        # a port and the eventual `mouseRelease` that either
        # commits the connection or cancels the draw. The line
        # item is a temporary rubber-band visual rendered above
        # connection items but below port items.
        self._pending_source: PortRef | None = None
        self._pending_line_item: QGraphicsLineItem | None = None
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

    # ------------------------------------------------------------------ #
    # Connection-draw drag (S1.9.5b)
    # ------------------------------------------------------------------ #

    @property
    def pending_connection_source(self) -> PortRef | None:
        """The in-flight connection-draw source, or `None` if idle.

        Test convenience — production callers go through the
        `start_connection_draw` / `commit_connection_draw` API.
        """
        return self._pending_source

    def port_at(self, scene_pos: QPointF) -> PortRef | None:
        """Find a `PortGraphicsItem` at `scene_pos` and return its `PortRef`.

        Walks the scene's items under the position in z-order
        (highest first). Returns the `(component_id, port_id)`
        of the first `PortGraphicsItem` whose parent is a
        `ComponentGraphicsItem`. Returns `None` when no port
        sits under the cursor.

        Used by `mousePressEvent` to detect connection-draw
        candidates and by `mouseReleaseEvent` to resolve the
        drop target.
        """
        for item in self.items(scene_pos):
            if not isinstance(item, PortGraphicsItem):
                continue
            parent = item.parentItem()
            if isinstance(parent, ComponentGraphicsItem):
                return PortRef(
                    component_id=parent.component_id,
                    port_id=item.port_id,
                )
        return None

    def start_connection_draw(self, source_ref: PortRef) -> bool:
        """Begin a connection-draw drag from a source port.

        Initializes `_pending_source`, mints the rubber-band
        line item rooted at the port's `scenePos()`, and
        registers everything for the subsequent
        `update_connection_draw` / `commit_connection_draw`
        cycle.

        Args:
            source_ref: Source endpoint as a `(component_id,
                port_id)` pair.

        Returns:
            True when the draw started successfully; False if
            the source port cannot be resolved (component
            removed, port id unknown) or another draw is
            already in flight.
        """
        if self._pending_source is not None:
            return False
        source_port = self._resolve_port_item(source_ref)
        if source_port is None:
            return False
        self._pending_source = source_ref
        start = source_port.scenePos()
        line = QGraphicsLineItem(start.x(), start.y(), start.x(), start.y())
        # Place the rubber-band just above wires; ports stay on
        # top so the user can still aim at a target port through
        # the line.
        line.setZValue(CONNECTION_Z_VALUE + 0.5)
        pen = QPen(QColor(74, 144, 226))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(2)
        line.setPen(pen)
        self.addItem(line)
        self._pending_line_item = line
        return True

    def update_connection_draw(self, cursor_pos: QPointF) -> None:
        """Extend the rubber-band line to the current cursor position.

        No-op when no draw is in flight. If the source port has
        disappeared mid-drag (e.g., its component was deleted by
        an undo arriving from a different thread), cancels the
        draw cleanly.
        """
        if self._pending_source is None or self._pending_line_item is None:
            return
        source_port = self._resolve_port_item(self._pending_source)
        if source_port is None:
            self.cancel_connection_draw()
            return
        start = source_port.scenePos()
        self._pending_line_item.setLine(start.x(), start.y(), cursor_pos.x(), cursor_pos.y())

    def commit_connection_draw(self, target_ref: PortRef) -> str | None:
        """Finalize the connection-draw drag with the resolved target port.

        Tears down the rubber-band, then attempts to push an
        `AddConnectionCommand`. The command's `__init__` runs
        `GraphValidator` and raises `ConnectionValidationError`
        on error-severity issues; this method catches the
        exception, logs a warning, and returns `None` — the
        connection is silently rejected at the visual layer,
        leaving model and stack unchanged.

        Args:
            target_ref: Target endpoint as a `(component_id,
                port_id)` pair.

        Returns:
            The new connection's `con_<ULID>` on success, or
            `None` when no draw was in flight, the source
            equals the target (self-connection), the validator
            rejected the candidate, or no command stack is wired.
        """
        if self._pending_source is None:
            return None
        source_ref = self._pending_source
        self._teardown_pending_draw()
        if source_ref == target_ref:
            return None  # self-connection — validator would reject anyway
        if self._command_stack is None:
            logger.warning("commit_connection_draw called without a command_stack; ignoring")
            return None
        try:
            command = AddConnectionCommand(self._model, source_ref, target_ref)
        except ConnectionValidationError as exc:
            logger.warning(
                "Connection from %s/%s to %s/%s rejected by validator: %s",
                source_ref.component_id,
                source_ref.port_id,
                target_ref.component_id,
                target_ref.port_id,
                exc,
            )
            # Surface the rejection to UI subscribers (S1.10.1).
            # The full report travels with the signal so future
            # multi-issue presentation can extend the slot
            # without renegotiating the contract.
            self.connectionRejected.emit(exc.report)
            return None
        self._command_stack.push(command)
        return command.connection_id

    def cancel_connection_draw(self) -> None:
        """Abort the in-flight connection-draw drag (idempotent)."""
        self._teardown_pending_draw()

    def _teardown_pending_draw(self) -> None:
        """Remove the rubber-band item and clear pending state."""
        if self._pending_line_item is not None:
            self.removeItem(self._pending_line_item)
            self._pending_line_item = None
        self._pending_source = None

    # ------------------------------------------------------------------ #
    # Mouse event overrides for connection-draw intercept (S1.9.5b)
    # ------------------------------------------------------------------ #

    def mousePressEvent(  # noqa: N802 — Qt API override
        self,
        event: QGraphicsSceneMouseEvent,
    ) -> None:
        """Intercept left-clicks on ports to start a connection draw.

        When the click hits a `PortGraphicsItem`, the scene
        starts a connection draw and consumes the event so the
        underlying component does not begin a drag. Otherwise
        the event flows through `super().mousePressEvent` to
        the standard scene → item dispatch.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            port_ref = self.port_at(event.scenePos())
            if port_ref is not None and self.start_connection_draw(port_ref):
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(  # noqa: N802 — Qt API override
        self,
        event: QGraphicsSceneMouseEvent,
    ) -> None:
        """Forward to the connection-draw update path when one is in flight."""
        if self._pending_source is not None:
            self.update_connection_draw(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(  # noqa: N802 — Qt API override
        self,
        event: QGraphicsSceneMouseEvent,
    ) -> None:
        """Resolve the drop target and commit or cancel the draw."""
        if self._pending_source is not None:
            target_ref = self.port_at(event.scenePos())
            if target_ref is not None:
                self.commit_connection_draw(target_ref)
            else:
                self.cancel_connection_draw()
            event.accept()
            return
        super().mouseReleaseEvent(event)

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

    def _resolve_ports(
        self,
        instance: ComponentInstance,
    ) -> tuple[PortDefinition, ...]:
        """Resolve the `PortDefinition` tuple for a component instance.

        Returns the empty tuple when the registry is not wired
        or when the instance's `definition_id` is not
        registered. The `ComponentGraphicsItem` treats an
        empty / None ports argument as "render the body only,
        no port circles" — useful for legacy / migration paths
        where definitions may be missing.
        """
        registry = self._model.registry
        if registry is None or not registry.has(instance.definition_id):
            return ()
        return registry.get(instance.definition_id).ports

    def _resolve_port_item(self, port_ref: PortRef) -> PortGraphicsItem | None:
        """Resolve a `PortRef` to the matching `PortGraphicsItem`.

        Looks up the parent component item in
        `_component_items` and asks it for the port child by
        port id. Returns `None` if either the component item
        or the port child is missing.
        """
        component_item = self._component_items.get(port_ref.component_id)
        if component_item is None:
            return None
        return component_item.port_item(port_ref.port_id)

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
        resolves the on-canvas label via the registry, looks up
        the `PortDefinition` records via `_resolve_ports`, and
        constructs the item with port children. The item is
        registered in `_component_items`. If the id is already
        in the dict, this is a defensive no-op.
        """
        if component_id in self._component_items:
            return
        instance = self._model.components.get(component_id)
        if instance is None:
            logger.warning("componentAdded fired for unknown id %s; ignoring", component_id)
            return
        label = self._resolve_label(instance)
        ports = self._resolve_ports(instance)
        item = ComponentGraphicsItem(instance, label=label, ports=ports)
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
        """Push the new position into the item and refresh attached wires."""
        item = self._component_items.get(component_id)
        if item is None:
            return
        item.setPos(new_pos)
        self._refresh_connections_for_component(component_id)
        _ = old_pos  # unused at the view layer

    def _on_component_rotated(
        self,
        component_id: str,
        old_rotation: float,
        new_rotation: float,
    ) -> None:
        """Push the new rotation into the item and refresh attached wires."""
        item = self._component_items.get(component_id)
        if item is None:
            return
        item.setRotation(new_rotation)
        self._refresh_connections_for_component(component_id)
        _ = old_rotation  # unused at the view layer

    def _refresh_connections_for_component(self, component_id: str) -> None:
        """Trigger `update_geometry()` on every connection touching `component_id`.

        Called from `_on_component_moved` / `_on_component_rotated`
        so wires follow their endpoints. Uses
        `WorkspaceModel.connections_for_component` (S1.7.3) to
        find the affected connections.
        """
        for conn in self._model.connections_for_component(component_id):
            item = self._connection_items.get(conn.id)
            if item is not None:
                item.update_geometry()

    # ------------------------------------------------------------------ #
    # Connection-related slots (S1.9.5a)
    # ------------------------------------------------------------------ #

    def _on_connection_added(self, connection_id: str) -> None:
        """Mint a `ConnectionGraphicsItem` for the new connection.

        Looks up the source and target port items via the
        component-item registry; if either endpoint is missing
        (defensive guard — shouldn't happen in normal flow
        because the model rejects connections with unknown
        component / port references), the slot logs and skips.
        """
        if connection_id in self._connection_items:
            return
        connection = self._model.connections.get(connection_id)
        if connection is None:
            logger.warning("connectionAdded fired for unknown id %s; ignoring", connection_id)
            return
        source_port = self._resolve_port_item(connection.source)
        target_port = self._resolve_port_item(connection.target)
        if source_port is None or target_port is None:
            logger.warning(
                "connectionAdded for %s: missing port item " "(source=%s target=%s); ignoring",
                connection_id,
                "ok" if source_port else "missing",
                "ok" if target_port else "missing",
            )
            return
        item = ConnectionGraphicsItem(
            connection_id=connection_id,
            source_port=source_port,
            target_port=target_port,
        )
        self.addItem(item)
        self._connection_items[connection_id] = item

    def _on_connection_removed(self, connection_id: str) -> None:
        """Remove the `ConnectionGraphicsItem` for a deleted connection."""
        item = self._connection_items.pop(connection_id, None)
        if item is not None:
            self.removeItem(item)

    def _on_connection_changed(self, connection_id: str) -> None:
        """Refresh the connection's geometry on routing / label edits.

        Phase 1 routing is a straight line, so geometry refresh
        is the only visible side-effect. Routing-aware drawing
        will add more behavior here when the schema gains
        waypoints.
        """
        item = self._connection_items.get(connection_id)
        if item is not None:
            item.update_geometry()

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
            self.removeItem(connection_item)
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
        # Order within the batch (per ADR-019 §"Diff aggregation"):
        # remove first (clean up before re-adds), then add
        # components (so connection items can resolve their
        # ports), then add connections, then refresh changed
        # entities. Removed connections also come before added
        # ones so a stale wire never lingers across a re-add
        # cycle inside the same batch.
        for conn_id in change_set.removed_connections:
            self._on_connection_removed(conn_id)
        for cid in change_set.removed_components:
            self._on_component_removed(cid)
        for cid in change_set.added_components:
            self._on_component_added(cid)
        for conn_id in change_set.added_connections:
            self._on_connection_added(conn_id)
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
            # Component move/rotate inside the batch needs the
            # connection geometry refresh that the fine-grained
            # slots would normally trigger.
            self._refresh_connections_for_component(cid)
        for conn_id in change_set.changed_connections:
            self._on_connection_changed(conn_id)


__all__ = ["WorkspaceScene"]
