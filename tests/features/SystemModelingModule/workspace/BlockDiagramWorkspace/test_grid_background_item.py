"""Unit tests for `GridBackgroundItem` (S1.9.1).

Pure paint-item logic — no `QGraphicsScene` interaction required.
Tests cover construction parameters, the bounding rect, the
z-value invariant (grid stays beneath component items), and a
smoke test that `paint()` runs without raising for a non-trivial
viewport.

References:
----------
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QStyleOptionGraphicsItem

from features.SystemModelingModule.workspace.BlockDiagramWorkspace.grid_background_item import (
    DEFAULT_GRID_COLOR,
    DEFAULT_GRID_SPACING,
    GRID_Z_VALUE,
    GridBackgroundItem,
)


@pytest.mark.unit
def test_grid_item_default_spacing() -> None:
    """A no-arg construction uses `DEFAULT_GRID_SPACING`."""
    item = GridBackgroundItem()

    assert item.spacing == DEFAULT_GRID_SPACING


@pytest.mark.unit
def test_grid_item_default_color() -> None:
    """A no-arg construction uses `DEFAULT_GRID_COLOR`."""
    item = GridBackgroundItem()

    assert item.color == DEFAULT_GRID_COLOR


@pytest.mark.unit
def test_grid_item_custom_spacing_and_color() -> None:
    """Constructor args override the defaults."""
    custom_color = QColor(0, 128, 255)
    item = GridBackgroundItem(spacing=50.0, color=custom_color)

    assert item.spacing == 50.0
    assert item.color == custom_color


@pytest.mark.unit
def test_grid_item_z_value_below_component_default() -> None:
    """Z-value is `GRID_Z_VALUE` so the grid sits beneath components.

    Components default to z=0; the grid's negative z keeps it
    behind every component / connection item in the stacking
    order.
    """
    item = GridBackgroundItem()

    assert item.zValue() == GRID_Z_VALUE
    assert GRID_Z_VALUE < 0.0


@pytest.mark.unit
def test_grid_item_is_not_selectable_or_movable() -> None:
    """Grid never steals hit-tests from interactive items."""
    from PySide6.QtWidgets import QGraphicsItem

    item = GridBackgroundItem()

    assert (
        item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        == QGraphicsItem.GraphicsItemFlag(0)
    )
    assert (
        item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        == QGraphicsItem.GraphicsItemFlag(0)
    )


@pytest.mark.unit
def test_grid_bounding_rect_is_symmetric_around_origin() -> None:
    """`boundingRect()` returns a square centered at the origin."""
    item = GridBackgroundItem(bounds=500.0)

    rect = item.boundingRect()

    assert rect == QRectF(-500.0, -500.0, 1000.0, 1000.0)


@pytest.mark.unit
def test_grid_paint_runs_without_raising() -> None:
    """`paint()` on a real `QPainter` produces no error for a small viewport.

    Smoke test that the snap-to-spacing arithmetic and Qt API
    interactions are correct. Renders to an in-memory `QImage` so
    no display is required.
    """
    image = QImage(200, 200, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    item = GridBackgroundItem(spacing=20.0)
    option = QStyleOptionGraphicsItem()
    option.exposedRect = QRectF(0.0, 0.0, 200.0, 200.0)  # type: ignore[attr-defined]

    try:
        item.paint(painter, option, None)
    finally:
        painter.end()
