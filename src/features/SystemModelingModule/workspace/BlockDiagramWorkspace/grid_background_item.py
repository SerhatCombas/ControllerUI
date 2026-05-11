"""GridBackgroundItem: grid lines drawn as a scene-coordinate item.

Per spec/07 §7.13. The grid is rendered as a `QGraphicsItem`
positioned beneath all component / connection items so that zoom
and pan transformations applied to the view scale the grid with
the workspace content. `paint()` clips to the exposed rect for
performance — only lines intersecting the viewport are emitted.

Phase 1 grid is purely visual: snap-to-grid logic lives in the
command layer (S1.9.4 / `MoveComponentCommand`), not here. This
item only draws.

References:
----------
* `specs/07_implementation_order.md` §7.13 (Workspace UI)
* `specs/02_workspace_requirements.md` §15 (Grid)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget


# Z-value places the grid beneath any component / connection items.
# Components default to z=0, so a negative value puts the grid at
# the back of the scene's stacking order.
GRID_Z_VALUE: Final[float] = -100.0

# Default grid spacing in scene units. 20 px matches the legacy
# workspace's snap step and the values in `02 §15`.
DEFAULT_GRID_SPACING: Final[float] = 20.0

# Default grid color — light gray, low contrast so the grid does
# not compete visually with components.
DEFAULT_GRID_COLOR: Final[QColor] = QColor(220, 220, 220)


class GridBackgroundItem(QGraphicsItem):
    """Scene-coordinate grid background.

    Args:
        spacing: Grid line spacing in scene units. Defaults to 20.
        color: Grid line color. Defaults to a light gray.
        bounds: Half-extent of the grid in scene units. The grid
            spans `[-bounds, +bounds]` on both axes. Defaults to
            a large value so the grid covers any reasonable
            workspace viewport.

    Notes:
        * Z-value is set to `GRID_Z_VALUE` at construction so the
          grid stays below all other items.
        * The item is non-interactive: `ItemIsSelectable` and
          `ItemIsMovable` are not set, so it does not steal hit
          tests from component / port items above it.
        * `paint()` clips to the exposed rect (the `option->exposedRect`
          passed by Qt) so only visible grid lines are emitted —
          rendering cost stays proportional to viewport size, not
          to the `bounds` extent.
    """

    def __init__(
        self,
        spacing: float = DEFAULT_GRID_SPACING,
        color: QColor | None = None,
        bounds: float = 10000.0,
    ) -> None:
        """Initialize the grid item with the given spacing and bounds."""
        super().__init__()
        self._spacing: float = spacing
        self._color: QColor = QColor(color) if color is not None else QColor(DEFAULT_GRID_COLOR)
        self._half_extent: float = bounds
        self.setZValue(GRID_Z_VALUE)
        # Mark the item as not accepting hover or selection — pure
        # background.
        self.setAcceptHoverEvents(False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, enabled=False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, enabled=False)

    @property
    def spacing(self) -> float:
        """Current grid spacing in scene units (test convenience)."""
        return self._spacing

    @property
    def color(self) -> QColor:
        """Current grid line color (test convenience)."""
        return QColor(self._color)

    def boundingRect(self) -> QRectF:  # noqa: N802 — Qt API override
        """Return the full grid extent.

        The extent is symmetric around the origin so panning the
        view in any direction reveals more grid. `paint()` clips
        per draw call so the actual rendered area scales with
        viewport size, not with this rectangle.
        """
        extent = self._half_extent
        return QRectF(-extent, -extent, 2.0 * extent, 2.0 * extent)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """Draw the grid lines visible in the exposed rect.

        Iterates over only the grid lines that intersect
        `option.exposedRect` so rendering cost stays O(viewport
        area / spacing²) rather than O(bounds² / spacing²).
        """
        # PySide6 stubs do not expose `exposedRect`; cast through Any.
        exposed = option.exposedRect  # type: ignore[attr-defined]
        spacing = self._spacing
        pen = QPen(self._color)
        pen.setWidth(0)  # cosmetic 1-pixel pen at any zoom
        painter.setPen(pen)
        painter.setRenderHint(painter.RenderHint.Antialiasing, on=False)

        # Vertical lines.
        left = _snap_floor(exposed.left(), spacing)
        right = exposed.right()
        x = left
        while x <= right:
            painter.drawLine(
                int(x),
                int(exposed.top()),
                int(x),
                int(exposed.bottom()),
            )
            x += spacing

        # Horizontal lines.
        top = _snap_floor(exposed.top(), spacing)
        bottom = exposed.bottom()
        y = top
        while y <= bottom:
            painter.drawLine(
                int(exposed.left()),
                int(y),
                int(exposed.right()),
                int(y),
            )
            y += spacing


def _snap_floor(value: float, spacing: float) -> float:
    """Snap `value` down to the nearest multiple of `spacing`."""
    return (value // spacing) * spacing


__all__ = [
    "DEFAULT_GRID_COLOR",
    "DEFAULT_GRID_SPACING",
    "GRID_Z_VALUE",
    "GridBackgroundItem",
]
