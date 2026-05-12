"""Unit tests for value-type to_dict/from_dict (S2.E.1).

Covers the sub-types touched by `WorkspaceModel.to_dict`:

* `PortRef` — 2-key dict.
* `VisualSpec` — svg_id + variant.
* `PhysicalAttributes` — 5-field enum/bool bundle.
* `ConnectionRouting` — style + waypoints (nested list-of-list).
* `ComponentInstance` — 19-field full round-trip + unknown-field
  forward-compat.
* `Connection` — id + endpoints + routing + style/metadata/extensions.
"""

from __future__ import annotations

import json

import pytest

from features.SystemModelingModule.model.component_instance import (
    ComponentInstance,
    VisualSpec,
)
from features.SystemModelingModule.model.connection import (
    Connection,
    ConnectionRouting,
)
from shared.graph.port_ref import PortRef
from shared.types import PhysicalAttributes

# ====================================================================== #
# PortRef
# ====================================================================== #


@pytest.mark.unit
def test_port_ref_round_trip() -> None:
    """`PortRef.to_dict / from_dict` round-trips both fields."""
    p = PortRef(component_id="cmp_X", port_id="p")
    assert PortRef.from_dict(p.to_dict()) == p


@pytest.mark.unit
def test_port_ref_from_dict_missing_field_raises() -> None:
    """Both `component_id` and `port_id` are required."""
    with pytest.raises(KeyError, match="component_id"):
        PortRef.from_dict({"port_id": "p"})
    with pytest.raises(KeyError, match="port_id"):
        PortRef.from_dict({"component_id": "cmp_X"})


# ====================================================================== #
# VisualSpec
# ====================================================================== #


@pytest.mark.unit
def test_visual_spec_round_trip() -> None:
    v = VisualSpec(svg_id="resistor_default", variant="selected")
    assert VisualSpec.from_dict(v.to_dict()) == v


@pytest.mark.unit
def test_visual_spec_default_variant() -> None:
    """Missing `variant` defaults to `"default"`."""
    v = VisualSpec.from_dict({"svg_id": "resistor_default"})
    assert v.variant == "default"


@pytest.mark.unit
def test_visual_spec_from_dict_missing_svg_id_raises() -> None:
    with pytest.raises(KeyError, match="svg_id"):
        VisualSpec.from_dict({"variant": "default"})


# ====================================================================== #
# PhysicalAttributes
# ====================================================================== #


@pytest.mark.unit
def test_physical_attributes_round_trip_default() -> None:
    """Default-everything bundle survives round-trip."""
    p = PhysicalAttributes()
    assert PhysicalAttributes.from_dict(p.to_dict()) == p


@pytest.mark.unit
def test_physical_attributes_round_trip_populated() -> None:
    """A fully populated bundle round-trips with every field set."""
    p = PhysicalAttributes(
        boundary="fixed",
        motion="translational",
        directional=True,
        source=True,
        source_type="ramp",
    )
    assert PhysicalAttributes.from_dict(p.to_dict()) == p


@pytest.mark.unit
def test_physical_attributes_preserves_unknown_enum_value_for_forward_compat() -> None:
    """An unknown future `boundary` enum loads verbatim per spec §29.4."""
    payload = {
        "boundary": "future_boundary_kind",
        "motion": None,
        "directional": False,
        "source": False,
        "source_type": None,
    }
    p = PhysicalAttributes.from_dict(payload)
    # `boundary` is typed `BoundaryKind | None`; mypy narrows on the
    # closed set, so wrap the literal in `cast` to keep the
    # forward-compat assertion legible.
    from typing import cast

    assert cast(str, p.boundary) == "future_boundary_kind"


# ====================================================================== #
# ConnectionRouting
# ====================================================================== #


@pytest.mark.unit
def test_connection_routing_round_trip_default() -> None:
    r = ConnectionRouting()
    assert ConnectionRouting.from_dict(r.to_dict()) == r


@pytest.mark.unit
def test_connection_routing_waypoints_round_trip() -> None:
    """Waypoints survive the tuple ↔ list-of-list JSON encoding."""
    r = ConnectionRouting(
        style="orthogonal",
        waypoints=((10.0, 20.0), (30.5, 40.5)),
    )
    payload = r.to_dict()
    assert payload["waypoints"] == [[10.0, 20.0], [30.5, 40.5]]
    r_back = ConnectionRouting.from_dict(payload)
    assert r_back.waypoints == ((10.0, 20.0), (30.5, 40.5))


# ====================================================================== #
# ComponentInstance
# ====================================================================== #


def _populated_component() -> ComponentInstance:
    """A maximally-populated ComponentInstance for round-trip tests."""
    return ComponentInstance(
        id="cmp_X",
        display_id="resistor_1",
        definition_id="electrical.analog.components.resistor",
        type="Resistor",
        display_name="R1",
        domain="electrical_analog",
        category="component",
        position=(10.0, 20.0),
        visual=VisualSpec(svg_id="resistor_default"),
        physical_attributes=PhysicalAttributes(directional=False),
        custom_label="Vbias_resistor",
        rotation=90.0,
        parameters={"R": 1000.0},
        locked=False,
        tags=("test", "phase1"),
        annotations={"note": "important"},
        metadata={"author": "test"},
        extensions={"future_field": True},
        created_at="2026-05-12T12:00:00Z",
        modified_at="2026-05-12T12:30:00Z",
    )


@pytest.mark.unit
def test_component_instance_full_round_trip() -> None:
    """Every field of `ComponentInstance` survives JSON round-trip."""
    original = _populated_component()
    payload = json.loads(json.dumps(original.to_dict()))
    restored = ComponentInstance.from_dict(payload)
    assert restored == original


@pytest.mark.unit
def test_component_instance_from_dict_unknown_top_level_keys_into_extensions() -> None:
    """Forward-compat: unknown component-level keys land in `extensions`."""
    payload = _populated_component().to_dict()
    payload["future_setting"] = {"phase2": True}
    restored = ComponentInstance.from_dict(payload)
    assert restored.extensions["future_setting"] == {"phase2": True}


@pytest.mark.unit
def test_component_instance_from_dict_missing_required_field_raises() -> None:
    """Each identity field is required; absent → `KeyError`."""
    base = _populated_component().to_dict()
    for required in (
        "id",
        "display_id",
        "definition_id",
        "type",
        "domain",
        "category",
        "position",
        "visual",
        "physical_attributes",
    ):
        payload = {k: v for k, v in base.items() if k != required}
        with pytest.raises(KeyError):
            ComponentInstance.from_dict(payload)


@pytest.mark.unit
def test_component_instance_from_dict_malformed_position_raises() -> None:
    """`position` must be a 2-element list/tuple."""
    base = _populated_component().to_dict()
    base["position"] = [10.0]  # too few elements
    with pytest.raises(ValueError, match="position"):
        ComponentInstance.from_dict(base)


# ====================================================================== #
# Connection
# ====================================================================== #


def _populated_connection() -> Connection:
    return Connection(
        id="con_X",
        display_id="conn_1",
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_B", port_id="n"),
        routing=ConnectionRouting(
            style="orthogonal",
            waypoints=((5.0, 10.0),),
        ),
        label="signal",
        style={"line_width": 2.0},
        metadata={"created_by": "test"},
        extensions={"phase2_bond": False},
    )


@pytest.mark.unit
def test_connection_full_round_trip() -> None:
    """Every field of `Connection` survives JSON round-trip."""
    original = _populated_connection()
    payload = json.loads(json.dumps(original.to_dict()))
    restored = Connection.from_dict(payload)
    assert restored == original


@pytest.mark.unit
def test_connection_from_dict_missing_required_field_raises() -> None:
    """Each identity field is required."""
    base = _populated_connection().to_dict()
    for required in ("id", "display_id", "source", "target"):
        payload = {k: v for k, v in base.items() if k != required}
        with pytest.raises(KeyError):
            Connection.from_dict(payload)


@pytest.mark.unit
def test_connection_from_dict_routing_missing_falls_back_to_default() -> None:
    """An absent `routing` field falls back to the default routing."""
    base = _populated_connection().to_dict()
    del base["routing"]
    restored = Connection.from_dict(base)
    assert restored.routing == ConnectionRouting()


@pytest.mark.unit
def test_connection_unknown_top_level_keys_into_extensions() -> None:
    """Forward-compat: unknown connection-level keys land in `extensions`."""
    payload = _populated_connection().to_dict()
    payload["future_marker"] = "phase2"
    restored = Connection.from_dict(payload)
    assert restored.extensions["future_marker"] == "phase2"
