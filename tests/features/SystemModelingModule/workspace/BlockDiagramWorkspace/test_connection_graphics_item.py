"""Unit tests for `ConnectionGraphicsItem` (S1.9.5a)."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QStyleOptionGraphicsItem

from features.SystemModelingModule.workspace.BlockDiagramWorkspace.connection_graphics_item import (
    CONNECTION_Z_VALUE,
    ConnectionGraphicsItem,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.port_graphics_item import (
    PortGraphicsItem,
)


@pytest.fixture
def two_ports_in_scene() -> tuple[QGraphicsScene, PortGraphicsItem, PortGraphicsItem]:
    """Two ports parked in a scene at distinct positions."""
    scene = QGraphicsScene()
    source = PortGraphicsItem(port_id="p", domain="electrical_analog")
    target = PortGraphicsItem(port_id="n", domain="electrical_analog")
    scene.addItem(source)
    scene.addItem(target)
    source.setPos(0.0, 0.0)
    target.setPos(100.0, 50.0)
    return scene, source, target


@pytest.mark.unit
def test_connection_item_constructs_with_id_and_ports(
    two_ports_in_scene: tuple[QGraphicsScene, PortGraphicsItem, PortGraphicsItem],
) -> None:
    """Constructor stores the connection id and endpoint port items."""
    _, source, target = two_ports_in_scene

    item = ConnectionGraphicsItem("con_test", source, target)

    assert item.connection_id == "con_test"
    assert item.source_port is source
    assert item.target_port is target


@pytest.mark.unit
def test_connection_item_z_value_between_components_and_ports(
    two_ports_in_scene: tuple[QGraphicsScene, PortGraphicsItem, PortGraphicsItem],
) -> None:
    """Z=10 sits between components (0) and ports (20)."""
    _, source, target = two_ports_in_scene

    item = ConnectionGraphicsItem("con_test", source, target)

    assert item.zValue() == CONNECTION_Z_VALUE


@pytest.mark.unit
def test_connection_item_is_not_selectable_in_phase1(
    two_ports_in_scene: tuple[QGraphicsScene, PortGraphicsItem, PortGraphicsItem],
) -> None:
    """Connections do not steal hit-tests in Phase 1; ports + components do."""
    _, source, target = two_ports_in_scene

    item = ConnectionGraphicsItem("con_test", source, target)

    assert not (item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)


@pytest.mark.unit
def test_connection_item_bounding_rect_covers_both_endpoints(
    two_ports_in_scene: tuple[QGraphicsScene, PortGraphicsItem, PortGraphicsItem],
) -> None:
    """Bounding rect spans both endpoints with a small padding."""
    _, source, target = two_ports_in_scene

    item = ConnectionGraphicsItem("con_test", source, target)
    rect = item.boundingRect()

    # Source at (0, 0), target at (100, 50). Rect should at least
    # cover that range (padded by a few pixels on each side).
    assert rect.left() <= 0.0
    assert rect.top() <= 0.0
    assert rect.right() >= 100.0
    assert rect.bottom() >= 50.0


@pytest.mark.unit
def test_connection_item_bounding_rect_tracks_moved_endpoint(
    two_ports_in_scene: tuple[QGraphicsScene, PortGraphicsItem, PortGraphicsItem],
) -> None:
    """Moving an endpoint changes the bounding rect (dynamic geometry)."""
    _, source, target = two_ports_in_scene
    item = ConnectionGraphicsItem("con_test", source, target)
    pre_rect = item.boundingRect()

    target.setPos(200.0, 200.0)
    post_rect = item.boundingRect()

    assert post_rect.right() > pre_rect.right()
    assert post_rect.bottom() > pre_rect.bottom()


@pytest.mark.unit
def test_connection_item_paint_runs_without_raising(
    two_ports_in_scene: tuple[QGraphicsScene, PortGraphicsItem, PortGraphicsItem],
) -> None:
    """Paint smoke test against an in-memory image."""
    _, source, target = two_ports_in_scene
    item = ConnectionGraphicsItem("con_test", source, target)
    image = QImage(200, 100, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    option = QStyleOptionGraphicsItem()
    try:
        item.paint(painter, option, None)
    finally:
        painter.end()


@pytest.mark.unit
def test_connection_item_update_geometry_does_not_raise(
    two_ports_in_scene: tuple[QGraphicsScene, PortGraphicsItem, PortGraphicsItem],
) -> None:
    """`update_geometry` triggers `prepareGeometryChange` + `update`."""
    _, source, target = two_ports_in_scene
    item = ConnectionGraphicsItem("con_test", source, target)

    item.update_geometry()  # smoke — no exception
