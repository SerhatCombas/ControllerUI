"""ConnectionGraphicsItem: view-layer item for a connection.

Per spec/07 §7.13 and `02 §14`. One `ConnectionGraphicsItem`
per `Connection` in the model. Phase 1 renders a straight line
between two `PortGraphicsItem` endpoints; routing-aware drawing
(orthogonal / Manhattan / spline) lands when the
`ConnectionRouting` schema gains waypoints in a later stage.

The connection is positioned at scene origin and draws in scene
coordinates: `paint()` reads each endpoint's `scenePos()` every
repaint, so a component move automatically translates into a
fresh line endpoint — the scene's `_on_component_moved` slot
just needs to call `update_geometry()` on each affected
connection to schedule the repaint.

References:
----------
* `specs/02_workspace_requirements.md` §14 (Connection System)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

    from .port_graphics_item import PortGraphicsItem


# Z-value for connections — above components (z=0) so wires draw
# over component bodies, below ports (z=20) so port hit-tests
# still win when the user clicks where a port meets a wire.
CONNECTION_Z_VALUE: Final[float] = 10.0

# Visual palette.
_LINE_COLOR: Final[QColor] = QColor(60, 60, 60)
_LINE_WIDTH: Final[int] = 2
# Padding around the line's bounding rect so the connection
# repaints cleanly when scene-coordinate antialiasing extends a
# pixel or two outside the strict line geometry.
_BOUNDING_PADDING: Final[float] = 4.0


class ConnectionGraphicsItem(QGraphicsItem):
    """View-layer item for one `Connection`.

    Args:
        connection_id: The bound `con_<ULID>`; immutable for the
            item's lifetime.
        source_port: The `PortGraphicsItem` at the source
            endpoint. The item holds a direct reference and
            reads its `scenePos()` each paint call.
        target_port: The `PortGraphicsItem` at the target
            endpoint.

    Notes:
        * Z-value is `CONNECTION_Z_VALUE = 10.0` (above
          components at 0, below ports at 20).
        * Not selectable / movable in Phase 1. S1.9.5b may flip
          `ItemIsSelectable` so users can click wires for
          deletion / routing tweaks.
        * `paint()` reads `scenePos()` of both endpoints
          dynamically, so component moves are reflected
          automatically once `update_geometry()` schedules a
          repaint.
    """

    def __init__(
        self,
        connection_id: str,
        source_port: PortGraphicsItem,
        target_port: PortGraphicsItem,
    ) -> None:
        """Construct with the bound id and endpoint port items."""
        super().__init__()
        self._connection_id: str = connection_id
        self._source_port: PortGraphicsItem = source_port
        self._target_port: PortGraphicsItem = target_port
        self.setZValue(CONNECTION_Z_VALUE)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, enabled=False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, enabled=False)

    @property
    def connection_id(self) -> str:
        """The bound `con_<ULID>` (test convenience)."""
        return self._connection_id

    @property
    def source_port(self) -> PortGraphicsItem:
        """The source endpoint's port item (test convenience)."""
        return self._source_port

    @property
    def target_port(self) -> PortGraphicsItem:
        """The target endpoint's port item (test convenience)."""
        return self._target_port

    def update_geometry(self) -> None:
        """Schedule a geometry refresh + repaint.

        Called by the scene when an endpoint may have moved
        (component drag, rotate, batch change). Wrapping the
        repaint in `prepareGeometryChange` notifies Qt that
        the bounding rect may change so the scene's index is
        updated before the next paint pass.
        """
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802 — Qt API override
        """Return the bounding rect of the two endpoints in scene coords.

        `QGraphicsItem` reports bounding rect in the item's
        own local coordinate space. Since this item is parked
        at scene origin (no `setPos` ever called), scene and
        local coordinates coincide here.
        """
        p1 = self._source_port.scenePos()
        p2 = self._target_port.scenePos()
        return (
            QRectF(p1, p2)
            .normalized()
            .adjusted(
                -_BOUNDING_PADDING,
                -_BOUNDING_PADDING,
                _BOUNDING_PADDING,
                _BOUNDING_PADDING,
            )
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """Draw a straight line between the two endpoint scene positions."""
        p1 = self._source_port.scenePos()
        p2 = self._target_port.scenePos()
        painter.setPen(QPen(_LINE_COLOR, _LINE_WIDTH))
        painter.setRenderHint(painter.RenderHint.Antialiasing, on=True)
        painter.drawLine(p1, p2)


__all__ = [
    "CONNECTION_Z_VALUE",
    "ConnectionGraphicsItem",
]
