"""Unit tests for `PortGraphicsItem` (S1.9.5a)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem

from features.SystemModelingModule.workspace.BlockDiagramWorkspace.port_graphics_item import (
    PORT_Z_VALUE,
    PortGraphicsItem,
)


@pytest.mark.unit
def test_port_item_constructs_with_id_and_domain() -> None:
    """Constructor stores port_id and domain."""
    item = PortGraphicsItem(port_id="p", domain="electrical_analog")

    assert item.port_id == "p"
    assert item.domain == "electrical_analog"


@pytest.mark.unit
def test_port_item_z_value_above_components_and_connections() -> None:
    """`PORT_Z_VALUE = 20.0` puts ports above wires (10) and components (0)."""
    item = PortGraphicsItem(port_id="p", domain="electrical_analog")

    assert item.zValue() == PORT_Z_VALUE
    assert PORT_Z_VALUE > 10.0


@pytest.mark.unit
def test_port_item_is_not_selectable_or_movable() -> None:
    """Ports defer selection / movement to the parent component."""
    item = PortGraphicsItem(port_id="p", domain="electrical_analog")

    assert not (item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
    assert not (item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)


@pytest.mark.unit
def test_port_item_bounding_rect_is_centered_circle() -> None:
    """Bounding rect is a square centered on the port anchor."""
    item = PortGraphicsItem(port_id="p", domain="electrical_analog")

    assert item.boundingRect() == QRectF(-4.0, -4.0, 8.0, 8.0)


@pytest.mark.unit
def test_port_item_paint_runs_without_raising() -> None:
    """Paint smoke test."""
    image = QImage(40, 40, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    item = PortGraphicsItem(port_id="p", domain="electrical_analog")
    option = QStyleOptionGraphicsItem()
    try:
        item.paint(painter, option, None)
    finally:
        painter.end()
