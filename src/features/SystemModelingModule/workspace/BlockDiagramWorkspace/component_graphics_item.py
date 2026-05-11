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

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyle

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )


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
        parent: QGraphicsItem | None = None,
    ) -> None:
        """Construct from a `ComponentInstance` snapshot."""
        super().__init__(parent)
        self._component_id: str = instance.id
        # Cache display fields. Position / rotation flow through
        # Qt's own `setPos` / `setRotation` and do not need to be
        # cached separately.
        self._label: str = label or _default_label(instance.display_name)
        self._display_name: str = instance.display_name
        self._locked: bool = instance.locked
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
