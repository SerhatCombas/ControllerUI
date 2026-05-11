"""ComponentGraphicsItem: view-layer item for a placed component.

Per spec/07 §7.13. One `ComponentGraphicsItem` per
`ComponentInstance` on the workspace; the item caches a small
set of display-only fields and routes all canonical state
queries back to the model.

Phase 1 visual:

* Body: a fixed-size rectangle (50 x 30 scene units) centered on
  the item's local origin.
* Label: a short identifier string supplied at construction
  (typically the `ComponentDefinition.short_name`, resolved by
  the scene via the wired registry; falls back to the first
  three characters of `display_name` when the definition has
  no `short_name`).
* Selection: a 2-pixel outline drawn when Qt reports
  `State_Selected` in the paint option's state flags.
* Locked: a dashed border replaces the solid one when the
  underlying `ComponentInstance.locked` is True.

The SVG-based rendering described in `02 §12` lands when the
SvgRegistry asset pipeline is wired in a later S1.9.x sub-commit.
Until then this placeholder visual gives every component a
deterministic, hit-testable footprint suitable for S1.9.3 drag-
drop integration and S1.9.4 selection / move gestures.

References:
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `specs/02_workspace_requirements.md` §11 (Component Data
  Model), §12 (SVG Usage), §15 (Grid), §16 (Zoom / Pan)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyle

from .port_graphics_item import PortGraphicsItem

if TYPE_CHECKING:
    from collections.abc import Sequence

    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import (
        QGraphicsSceneMouseEvent,
        QStyleOptionGraphicsItem,
        QWidget,
    )

    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )
    from shared.registry import PortDefinition


# Z-value for placed components — sits above the grid (z = -100)
# and below connections (z = 10, defined in S1.9.5). Default Qt
# z is 0 but we set it explicitly so future code doesn't depend
# on an implicit value.
COMPONENT_Z_VALUE: Final[float] = 0.0

# Phase-1 placeholder footprint. The rect is centered on the
# item's local origin so rotations pivot around the visual
# center (matches `02 §23` rotation semantics).
_BODY_HALF_WIDTH: Final[float] = 25.0
_BODY_HALF_HEIGHT: Final[float] = 15.0
_BODY_RECT: Final[QRectF] = QRectF(
    -_BODY_HALF_WIDTH,
    -_BODY_HALF_HEIGHT,
    2.0 * _BODY_HALF_WIDTH,
    2.0 * _BODY_HALF_HEIGHT,
)

# Visual palette — neutral defaults; final theming lands when
# the design system commits actual tokens.
_FILL_COLOR: Final[QColor] = QColor(245, 245, 245)
_BORDER_COLOR: Final[QColor] = QColor(80, 80, 80)
_BORDER_WIDTH: Final[int] = 1
_SELECTED_BORDER_COLOR: Final[QColor] = QColor(74, 144, 226)
_SELECTED_BORDER_WIDTH: Final[int] = 2
_LABEL_COLOR: Final[QColor] = QColor(40, 40, 40)
_LABEL_FONT_POINT_SIZE: Final[int] = 9


class ComponentGraphicsItem(QGraphicsItem):
    """View-layer item for one placed component.

    Args:
        instance: The `ComponentInstance` to render. The item
            captures the id once (immutable) plus a small set of
            display fields it re-reads via `update_from_instance`
            when `componentChanged` fires.
        label: Short on-canvas label, typically resolved from the
            component's `ComponentDefinition.short_name` by the
            scene. Defaults to the first three characters of the
            instance's `display_name` when omitted, so the item
            stays usable in tests that construct it without a
            registry.

    Notes:
        * `ItemIsSelectable` is enabled so the rubber-band /
          click selection paths from `QGraphicsView` work.
        * `ItemIsMovable` is enabled so S1.9.4 mouse-drag
          gestures translate the item directly; on release the
          gesture will commit a `MoveComponentCommand` via the
          stack.
        * `ItemSendsGeometryChanges` is enabled so item-position
          changes propagate through `itemChange` — S1.9.4 will
          override `itemChange` to capture intermediate drag
          positions for snap-to-grid arithmetic and to publish
          the final position into a `MoveComponentCommand`.
        * Z-value is set to `COMPONENT_Z_VALUE = 0.0` explicitly.
    """

    def __init__(
        self,
        instance: ComponentInstance,
        label: str = "",
        ports: Sequence[PortDefinition] | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        """Construct from a `ComponentInstance` snapshot.

        Args:
            instance: The `ComponentInstance` to render.
            label: Short on-canvas label (see class docstring).
            ports: Optional sequence of `PortDefinition` records
                from the component's registered
                `ComponentDefinition`. When supplied, the item
                mints one `PortGraphicsItem` per port at the
                `relative_position` mapped into the placeholder
                body's local coordinate system. When `None` (the
                default), no ports are drawn — useful for tests
                that exercise only the component-level visual.
            parent: Optional parent graphics item.
        """
        super().__init__(parent)
        self._component_id: str = instance.id
        # Cache display fields. Position / rotation flow through
        # Qt's own `setPos` / `setRotation` and do not need to be
        # cached separately.
        self._label: str = label or _default_label(instance.display_name)
        self._display_name: str = instance.display_name
        self._locked: bool = instance.locked
        # Drag tracking — `mousePressEvent` captures the pre-drag
        # position so `mouseReleaseEvent` can compute the delta
        # and route through `commit_drag` (S1.9.4). `None` between
        # drags.
        self._drag_start_pos: QPointF | None = None
        # Port children registry — populated below when `ports`
        # is supplied so `port_item(id)` can resolve by id.
        self._port_items: dict[str, PortGraphicsItem] = {}
        # Apply position + rotation from the instance.
        self.setPos(instance.position[0], instance.position[1])
        self.setRotation(instance.rotation)
        # Flags.
        self.setZValue(COMPONENT_Z_VALUE)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, enabled=True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, enabled=True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
            enabled=True,
        )
        # Create port children at their relative-position offsets.
        if ports is not None:
            for port_def in ports:
                self._add_port_child(port_def)

    def _add_port_child(self, port_def: PortDefinition) -> None:
        """Mint and position a `PortGraphicsItem` child for the port.

        Maps `relative_position` (0..1 normalized within the
        body rect) into item-local coordinates centered on the
        component origin.
        """
        rx, ry = port_def.relative_position
        local_x = (rx * (2.0 * _BODY_HALF_WIDTH)) - _BODY_HALF_WIDTH
        local_y = (ry * (2.0 * _BODY_HALF_HEIGHT)) - _BODY_HALF_HEIGHT
        port_item = PortGraphicsItem(
            port_id=port_def.id,
            domain=port_def.domain,
            parent=self,
        )
        port_item.setPos(local_x, local_y)
        self._port_items[port_def.id] = port_item

    @property
    def component_id(self) -> str:
        """The bound `cmp_<ULID>`; immutable for the item's lifetime."""
        return self._component_id

    @property
    def label(self) -> str:
        """Current on-canvas label (test convenience)."""
        return self._label

    @property
    def display_name(self) -> str:
        """Current cached `display_name` (test convenience)."""
        return self._display_name

    @property
    def locked(self) -> bool:
        """Current cached locked flag (test convenience)."""
        return self._locked

    @property
    def port_items(self) -> dict[str, PortGraphicsItem]:
        """Mapping of `port_id` → `PortGraphicsItem` (test convenience).

        Read-only view; mutating the returned dict does not
        re-parent the items. Tests rely on this to assert that
        ports were minted and positioned correctly.
        """
        return dict(self._port_items)

    def port_item(self, port_id: str) -> PortGraphicsItem | None:
        """Resolve a port-id to its `PortGraphicsItem`, or `None`."""
        return self._port_items.get(port_id)

    # ------------------------------------------------------------------ #
    # Mouse-drag → MoveComponentCommand (S1.9.4)
    # ------------------------------------------------------------------ #

    def mousePressEvent(  # noqa: N802 — Qt API override
        self,
        event: QGraphicsSceneMouseEvent,
    ) -> None:
        """Capture the pre-drag position so release can compute the delta."""
        self._drag_start_pos = QPointF(self.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(  # noqa: N802 — Qt API override
        self,
        event: QGraphicsSceneMouseEvent,
    ) -> None:
        """Forward Qt's release; then route the drag through `commit_drag`."""
        super().mouseReleaseEvent(event)
        if self._drag_start_pos is not None:
            self.commit_drag(self._drag_start_pos, QPointF(self.pos()))
            self._drag_start_pos = None

    def commit_drag(self, start_pos: QPointF, end_pos: QPointF) -> bool:
        """Snap `end_pos` to the grid and route through the scene's command stack.

        Public so tests can exercise the drag-commit logic
        without constructing `QGraphicsSceneMouseEvent` (PySide6
        does not expose a public constructor for that class).

        The pipeline:

        1. If `end_pos == start_pos`, no drag occurred — return
           False, no command pushed, item visual stays as-is
           (Qt may have set the position to `end_pos == start_pos`
           via the built-in drag, which is a no-op).
        2. Snap `end_pos` to the grid. If the snapped position
           equals `start_pos` (drag was sub-grid), revert the
           item visually to `start_pos` and return False — no
           command needed.
        3. Otherwise revert the item visually to `start_pos` and
           ask the scene to commit a `MoveComponentCommand` to
           `snapped_pos`. The command's `componentMoved` signal
           then drives the final visual update through the
           scene's `_on_component_moved` slot, so the item
           reaches the snapped position exactly once via the
           model-canonical path.

        Args:
            start_pos: Pre-drag scene position (captured in
                `mousePressEvent`).
            end_pos: Post-drag scene position (Qt's drag-end
                position after the built-in `ItemIsMovable`
                handler ran).

        Returns:
            True if a `MoveComponentCommand` was pushed onto the
            scene's command stack; False otherwise (no drag,
            sub-grid drag, or no command_stack wired).
        """
        # Avoid the snap import cycle by importing inside the
        # function — `workspace_scene` imports this item, so a
        # top-level import would deadlock at module-load time.
        from .workspace_scene import snap_to_grid

        if end_pos == start_pos:
            return False
        snapped = QPointF(snap_to_grid(end_pos.x()), snap_to_grid(end_pos.y()))
        if snapped == start_pos:
            # Sub-grid drag — bounce back to start without a command.
            self.setPos(start_pos)
            return False
        # Revert the item visually so the command pipeline is the
        # single source of position update.
        self.setPos(start_pos)
        # `self.scene()` is typed as non-None in PySide6 stubs but can
        # return None at runtime when the item is detached.
        scene: object | None = self.scene()
        if scene is None:
            return False
        # Duck-typed call: `WorkspaceScene` exposes
        # `commit_component_move`; using `getattr` avoids a
        # circular import with the scene module.
        commit = getattr(scene, "commit_component_move", None)
        if not callable(commit):
            return False
        commit(self._component_id, snapped)
        return True

    def update_from_instance(
        self,
        instance: ComponentInstance,
        label: str | None = None,
    ) -> None:
        """Refresh cached display fields and request a repaint.

        Called by the scene's `_on_component_changed` slot when
        the model emits `componentChanged(id)` (e.g., on
        `set_custom_label`, `set_locked`, or `set_tags`).
        Position and rotation are NOT touched here — those have
        dedicated signal slots (`_on_component_moved`,
        `_on_component_rotated`) so `componentChanged` payloads
        do not duplicate move / rotate work.

        Args:
            instance: Fresh `ComponentInstance` snapshot to read
                from. Its id must match the item's bound id.
            label: Optional updated on-canvas label. The scene
                supplies the registry-resolved
                `ComponentDefinition.short_name`; passing `None`
                keeps the existing label (since `short_name` is
                a definition-level property that does not change
                via `componentChanged`).

        Raises:
            ValueError: `instance.id` does not match the item's
                bound id (caller bug).
        """
        if instance.id != self._component_id:
            raise ValueError(
                f"update_from_instance id mismatch: item={self._component_id}, "
                f"instance={instance.id}"
            )
        if label is not None:
            self._label = label or _default_label(instance.display_name)
        self._display_name = instance.display_name
        self._locked = instance.locked
        self.update()  # request repaint

    def boundingRect(self) -> QRectF:  # noqa: N802 — Qt API override
        """Return the Phase-1 placeholder footprint."""
        return QRectF(_BODY_RECT)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """Draw the placeholder body + short-name label."""
        # Body fill.
        painter.setBrush(_FILL_COLOR)
        # Border — solid by default, dashed when locked.
        pen = QPen(_BORDER_COLOR, _BORDER_WIDTH)
        if self._locked:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(_BODY_RECT)
        # Selection overlay — drawn after the body so the
        # selection color is the topmost border. `option.state`
        # is a `QStyle.State` flag set; `State_Selected` lives on
        # `QStyle.StateFlag`. PySide6 stubs do not expose `state`
        # on `QStyleOptionGraphicsItem`.
        if option.state & QStyle.StateFlag.State_Selected:  # type: ignore[attr-defined]
            painter.setPen(QPen(_SELECTED_BORDER_COLOR, _SELECTED_BORDER_WIDTH))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(_BODY_RECT)
        # Label.
        label_font = QFont()
        label_font.setPointSize(_LABEL_FONT_POINT_SIZE)
        painter.setFont(label_font)
        painter.setPen(QPen(_LABEL_COLOR))
        painter.drawText(_BODY_RECT, Qt.AlignmentFlag.AlignCenter, self._label)


def _default_label(display_name: str) -> str:
    """Fallback on-canvas label when the scene did not supply one.

    First three characters of `display_name` keep every component
    showing something visible without requiring registry access
    in tests that construct the item directly.
    """
    return display_name[:3] if display_name else "?"


__all__ = [
    "COMPONENT_Z_VALUE",
    "ComponentGraphicsItem",
]
