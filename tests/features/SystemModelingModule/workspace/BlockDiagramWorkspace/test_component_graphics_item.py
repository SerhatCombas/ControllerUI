"""Unit tests for `ComponentGraphicsItem` (S1.9.2).

Item-level logic — no scene integration. Scene-side behavior
(slot wiring, model→item synchronization) is covered in
`test_workspace_scene.py`.

References:
----------
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem

from features.SystemModelingModule.model.component_instance import (
    ComponentInstance,
    PhysicalAttributes,
    VisualSpec,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.component_graphics_item import (
    COMPONENT_Z_VALUE,
    ComponentGraphicsItem,
)


def _make_instance(
    *,
    id: str = "cmp_test123",
    display_name: str = "Resistor",
    position: tuple[float, float] = (10.0, 20.0),
    rotation: float = 0.0,
    locked: bool = False,
) -> ComponentInstance:
    """Build a `ComponentInstance` with sensible defaults for item tests.

    The item only reads a handful of fields — id, display_name,
    position, rotation, locked — so the helper fills the rest
    with neutral placeholders matching the dataclass contract.
    """
    return ComponentInstance(
        id=id,
        display_id="resistor_1",
        definition_id="electrical.analog.components.resistor",
        type="Resistor",
        display_name=display_name,
        domain="electrical_analog",
        category="component",
        position=position,
        visual=VisualSpec(svg_id="electrical_resistor_default"),
        physical_attributes=PhysicalAttributes(),
        custom_label="",
        rotation=rotation,
        parameters={},
        locked=locked,
        tags=(),
        annotations={},
        metadata={},
        extensions={},
        created_at="2026-05-11T00:00:00.000000+00:00",
        modified_at="2026-05-11T00:00:00.000000+00:00",
    )


# ---------------------------------------------------------------------- #
# Construction + cached fields
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_item_constructs_from_instance() -> None:
    """Item captures the component id and basic display fields."""
    instance = _make_instance()

    item = ComponentGraphicsItem(instance, label="R")

    assert item.component_id == instance.id
    assert item.display_name == "Resistor"
    assert item.label == "R"
    assert item.locked is False


@pytest.mark.unit
def test_item_position_matches_instance() -> None:
    """Constructor applies `instance.position` via `setPos`."""
    instance = _make_instance(position=(120.0, 80.0))

    item = ComponentGraphicsItem(instance)

    assert item.pos() == QPointF(120.0, 80.0)


@pytest.mark.unit
def test_item_rotation_matches_instance() -> None:
    """Constructor applies `instance.rotation` via `setRotation`."""
    instance = _make_instance(rotation=90.0)

    item = ComponentGraphicsItem(instance)

    assert item.rotation() == 90.0


@pytest.mark.unit
def test_item_uses_provided_label() -> None:
    """The `label` constructor arg becomes the on-canvas label."""
    instance = _make_instance(display_name="Resistor")

    item = ComponentGraphicsItem(instance, label="R")

    assert item.label == "R"


@pytest.mark.unit
def test_item_label_fallback_uses_first_three_chars_of_display_name() -> None:
    """Without an explicit label, the first 3 chars of `display_name` are used."""
    instance = _make_instance(display_name="Resistor")

    item = ComponentGraphicsItem(instance)

    assert item.label == "Res"


@pytest.mark.unit
def test_item_label_fallback_handles_empty_display_name() -> None:
    """Empty display_name → `?` placeholder so the item always renders something."""
    instance = _make_instance(display_name="")

    item = ComponentGraphicsItem(instance)

    assert item.label == "?"


# ---------------------------------------------------------------------- #
# Flags + z-value
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_item_z_value_is_component_default() -> None:
    """Z-value is set to `COMPONENT_Z_VALUE = 0.0` explicitly."""
    instance = _make_instance()

    item = ComponentGraphicsItem(instance)

    assert item.zValue() == COMPONENT_Z_VALUE


@pytest.mark.unit
def test_item_is_selectable_and_movable() -> None:
    """Required for selection (S1.9.4) and drag-gestures (S1.9.4)."""
    instance = _make_instance()

    item = ComponentGraphicsItem(instance)

    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges


# ---------------------------------------------------------------------- #
# boundingRect + paint
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_item_bounding_rect_is_centered() -> None:
    """The placeholder rect is symmetric around the item origin."""
    instance = _make_instance()

    item = ComponentGraphicsItem(instance)
    rect = item.boundingRect()

    assert rect == QRectF(-25.0, -15.0, 50.0, 30.0)


@pytest.mark.unit
def test_item_paint_runs_without_raising() -> None:
    """Paint smoke test against an in-memory `QImage`."""
    instance = _make_instance()
    item = ComponentGraphicsItem(instance, label="R")
    image = QImage(100, 60, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    option = QStyleOptionGraphicsItem()

    try:
        item.paint(painter, option, None)
    finally:
        painter.end()


# ---------------------------------------------------------------------- #
# update_from_instance
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_update_from_instance_refreshes_locked_flag() -> None:
    """`update_from_instance` re-reads `locked` from the new snapshot."""
    instance = _make_instance(locked=False)
    item = ComponentGraphicsItem(instance)
    assert item.locked is False

    new_instance = _make_instance(locked=True)
    item.update_from_instance(new_instance)

    assert item.locked is True


@pytest.mark.unit
def test_update_from_instance_keeps_label_when_label_is_none() -> None:
    """Passing `label=None` to `update_from_instance` preserves the prior label.

    `short_name` is a definition-level property that does not
    change via `componentChanged`; the scene passes `None` so
    the label stays stable across instance refreshes.
    """
    instance = _make_instance()
    item = ComponentGraphicsItem(instance, label="R")
    assert item.label == "R"

    item.update_from_instance(_make_instance(display_name="Resistor"), label=None)

    assert item.label == "R"


@pytest.mark.unit
def test_update_from_instance_can_replace_label_when_provided() -> None:
    """Passing an explicit label replaces the cached one."""
    instance = _make_instance()
    item = ComponentGraphicsItem(instance, label="R")

    item.update_from_instance(instance, label="R'")

    assert item.label == "R'"


@pytest.mark.unit
def test_update_from_instance_rejects_id_mismatch() -> None:
    """Passing an instance with a different id raises `ValueError`."""
    item = ComponentGraphicsItem(_make_instance(id="cmp_a"))

    with pytest.raises(ValueError, match=r"id mismatch"):
        item.update_from_instance(_make_instance(id="cmp_b"))
