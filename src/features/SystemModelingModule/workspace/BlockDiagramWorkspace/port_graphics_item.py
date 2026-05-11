"""PortGraphicsItem: view-layer item for a component port.

Per spec/07 §7.13 and `02 §13`. One `PortGraphicsItem` per
`PortDefinition` declared on the parent component's definition.
The port is a child of the `ComponentGraphicsItem`, so it moves,
rotates, and renders together with its parent.

Phase 1 visual:

* Body: a small filled circle (radius 4 scene units) centered
  on the port's anchor point.
* Color: a fixed dark-gray default for Phase 1; S1.9.5b will
  introduce hover / validation-error tinting.

The port's local position is computed by the parent component
from its `relative_position` tuple (where `(0,0)` is the
top-left corner of the body and `(1,1)` is the bottom-right).
The mapping into the parent's local coordinate system is:

    local_x = (rx * body_width) - body_half_width
    local_y = (ry * body_height) - body_half_height

References:
----------
* `specs/02_workspace_requirements.md` §13 (Port System)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget


# Z-value for ports — above components and connections so the
# hit-test in S1.9.5b connection-draw drag picks ports first.
PORT_Z_VALUE: Final[float] = 20.0

# Phase-1 visual footprint.
_PORT_RADIUS: Final[float] = 4.0
_PORT_DIAMETER: Final[float] = 2.0 * _PORT_RADIUS

# Visual palette.
_PORT_FILL_COLOR: Final[QColor] = QColor(80, 80, 80)
_PORT_BORDER_COLOR: Final[QColor] = QColor(40, 40, 40)
_PORT_BORDER_WIDTH: Final[int] = 1


class PortGraphicsItem(QGraphicsItem):
    """View-layer item for a single port.

    Args:
        port_id: The owning component's `PortDefinition.id`.
            Stable for the item's lifetime.
        domain: The port's declared `DomainId`. Phase 1 stores
            it for future cross-domain validation surfacing
            (S1.9.5b will color cross-domain candidates).
        parent: Optional Qt parent — typically the owning
            `ComponentGraphicsItem`.

    Notes:
        * Z-value is `PORT_Z_VALUE = 20.0` (above components and
          connections).
        * Not independently selectable or movable — selection
          and dragging are properties of the parent component.
          A future S1.9.5b connection-draw gesture will treat
          port hits specially without enabling these flags.
    """

    def __init__(
        self,
        port_id: str,
        domain: str,
        parent: QGraphicsItem | None = None,
    ) -> None:
        """Construct as a child of the supplied parent item."""
        super().__init__(parent)
        self._port_id: str = port_id
        self._domain: str = domain
        self.setZValue(PORT_Z_VALUE)
        # Ports do not steal selection / movement from the
        # parent component. The parent handles drag, the port
        # only renders + (in S1.9.5b) accepts press-to-draw.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, enabled=False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, enabled=False)

    @property
    def port_id(self) -> str:
        """The bound port id (test convenience)."""
        return self._port_id

    @property
    def domain(self) -> str:
        """The port's declared domain (test convenience)."""
        return self._domain

    def boundingRect(self) -> QRectF:  # noqa: N802 — Qt API override
        """Square bounding box around the circular port body."""
        return QRectF(-_PORT_RADIUS, -_PORT_RADIUS, _PORT_DIAMETER, _PORT_DIAMETER)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """Draw the port as a filled circle with a 1-px border."""
        painter.setBrush(QBrush(_PORT_FILL_COLOR))
        painter.setPen(QPen(_PORT_BORDER_COLOR, _PORT_BORDER_WIDTH))
        painter.setRenderHint(painter.RenderHint.Antialiasing, on=True)
        painter.drawEllipse(self.boundingRect())


__all__ = [
    "PORT_Z_VALUE",
    "PortGraphicsItem",
]
