"""WorkspaceView: QGraphicsView with zoom + pan over a WorkspaceScene.

Per spec/07 §7.13. The view is the host widget for the
`WorkspaceScene`. It owns the zoom (Ctrl + wheel) and pan
(middle-mouse drag) interactions per `02 §16`. Zoom and pan are
view-only — they do NOT mutate the model.

Zoom is implemented by scaling the view's transform; pan is the
built-in `ScrollHandDrag` behavior bound to the middle mouse
button. Phase 1 zoom range is `[ZOOM_MIN, ZOOM_MAX]`; outside
this range wheel events are ignored.

References:
----------
* `specs/02_workspace_requirements.md` §16 (Zoom / Pan)
* `specs/07_implementation_order.md` §7.13 (Workspace UI)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView

if TYPE_CHECKING:
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QGraphicsScene, QWidget


# Phase-1 zoom range per `02 §16`. Tight enough that the view
# never collapses to invisibility or expands beyond useful scale.
ZOOM_MIN: Final[float] = 0.25
ZOOM_MAX: Final[float] = 4.0
ZOOM_STEP: Final[float] = 1.15  # ratio per wheel notch


class WorkspaceView(QGraphicsView):
    """QGraphicsView with zoom + pan over a workspace scene.

    Args:
        scene: The `QGraphicsScene` to display (typically a
            `WorkspaceScene`). Stored via `setScene`.
        parent: Optional Qt parent.

    Notes:
        * Render hints include `Antialiasing` and
          `SmoothPixmapTransform` so the SVG-based component
          items (S1.9.2) render cleanly at any zoom.
        * `setTransformationAnchor(AnchorUnderMouse)` makes the
          mouse cursor the pivot for wheel-zoom — the user's
          focus point stays under the cursor as zoom changes.
        * `setDragMode(ScrollHandDrag)` is intentionally NOT set
          at construction — that mode would steal click events
          from component / port items. Pan is handled via the
          middle mouse button in mouse event overrides (added
          in S1.9.4).
    """

    def __init__(
        self,
        scene: QGraphicsScene,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the view with a scene and configure render hints."""
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # Default drag mode: rubber-band selection. Pan via middle
        # mouse comes later (S1.9.4); zoom via wheel works on top
        # of any drag mode.
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def current_zoom(self) -> float:
        """Return the current uniform zoom factor.

        Reads `transform().m11()` (x-scale). The view applies
        uniform scaling, so x-scale equals y-scale.
        """
        return float(self.transform().m11())

    def zoom_in(self) -> None:
        """Apply one zoom-in step, respecting `ZOOM_MAX`."""
        self._apply_zoom(ZOOM_STEP)

    def zoom_out(self) -> None:
        """Apply one zoom-out step, respecting `ZOOM_MIN`."""
        self._apply_zoom(1.0 / ZOOM_STEP)

    def reset_zoom(self) -> None:
        """Reset the view transform to identity (zoom = 1.0)."""
        self.resetTransform()

    def _apply_zoom(self, factor: float) -> None:
        """Scale by `factor` if the result stays in `[ZOOM_MIN, ZOOM_MAX]`."""
        new_zoom = self.current_zoom() * factor
        if new_zoom < ZOOM_MIN or new_zoom > ZOOM_MAX:
            return
        self.scale(factor, factor)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 — Qt API
        """Handle Ctrl + wheel for zoom; pass other wheel events through.

        Wheel without Ctrl: default `QGraphicsView` behavior
        (vertical scroll).
        Wheel + Ctrl: zoom in/out by `ZOOM_STEP` per notch.
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)


__all__ = ["ZOOM_MAX", "ZOOM_MIN", "ZOOM_STEP", "WorkspaceView"]
