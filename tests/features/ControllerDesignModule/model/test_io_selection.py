"""Unit tests for IOSelection dataclass family (S2.A scaffold)."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from features.ControllerDesignModule.model import (
    IOEntry,
    IOSelection,
    IOSourcePortRef,
    io_source_from_dict,
    new_io_input_id,
    new_io_output_id,
)
from shared.graph.port_ref import PortRef


def _make_voltage_input() -> IOEntry:
    return IOEntry(
        id=new_io_input_id(),
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_R1", port_id="p"),
            variable="across",
        ),
        display_name="Vin",
        quantity="voltage",
        unit="V",
    )


def _make_position_output() -> IOEntry:
    return IOEntry(
        id=new_io_output_id(),
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_M1", port_id="flange"),
            variable="across",
        ),
        display_name="x_out",
        quantity="displacement",
        unit="m",
    )


# ---------------------------------------------------------------------- #
# Defaults + construction
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_io_selection_default_is_empty_lists() -> None:
    """`IOSelection()` has no inputs and no outputs."""
    s = IOSelection()
    assert s.inputs == ()
    assert s.outputs == ()


# ---------------------------------------------------------------------- #
# IOSourcePortRef — flat-sibling JSON form per spec §6.2
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_io_source_port_ref_to_dict_flattens_port_ref_into_siblings() -> None:
    """Spec §6.2 JSON has flat siblings — to_dict flattens PortRef."""
    src = IOSourcePortRef(
        port_ref=PortRef(component_id="cmp_X", port_id="p"),
        variable="across",
    )
    payload = src.to_dict()
    assert payload == {
        "kind": "port_ref",
        "component_id": "cmp_X",
        "port_id": "p",
        "variable": "across",
    }


@pytest.mark.unit
def test_io_source_port_ref_round_trip_recomposes_port_ref() -> None:
    """`from_dict` reconstructs `PortRef` from the flat siblings."""
    src = IOSourcePortRef(
        port_ref=PortRef(component_id="cmp_X", port_id="p"),
        variable="through",
    )
    src_back = IOSourcePortRef.from_dict(src.to_dict())
    assert src_back == src
    assert src_back.port_ref == PortRef(component_id="cmp_X", port_id="p")


@pytest.mark.unit
def test_io_source_port_ref_rejects_invalid_variable() -> None:
    """`variable` outside {across, through, derived} raises `ValueError`."""
    payload = {
        "kind": "port_ref",
        "component_id": "cmp_X",
        "port_id": "p",
        "variable": "energy",  # not in the closed set
    }
    with pytest.raises(ValueError, match="variable"):
        IOSourcePortRef.from_dict(payload)


@pytest.mark.unit
def test_io_source_port_ref_rejects_wrong_kind() -> None:
    """`from_dict` on a non-`port_ref` kind raises `ValueError`."""
    payload = {
        "kind": "probe_ref",  # Phase 2 variant
        "component_id": "cmp_X",
        "port_id": "p",
        "variable": "across",
    }
    with pytest.raises(ValueError, match="port_ref"):
        IOSourcePortRef.from_dict(payload)


@pytest.mark.unit
def test_io_source_from_dict_dispatches_on_kind() -> None:
    """The tagged-union dispatcher routes by `kind`."""
    payload = {
        "kind": "port_ref",
        "component_id": "cmp_X",
        "port_id": "p",
        "variable": "across",
    }
    source = io_source_from_dict(payload)
    assert isinstance(source, IOSourcePortRef)


@pytest.mark.unit
def test_io_source_from_dict_unknown_kind_raises() -> None:
    """Phase 1 supports `port_ref` only; unknown kinds raise."""
    with pytest.raises(ValueError, match="Phase 1 supports 'port_ref'"):
        io_source_from_dict({"kind": "probe_ref"})


# ---------------------------------------------------------------------- #
# IOEntry round-trip + forward-compat
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_io_entry_round_trip() -> None:
    """`IOEntry.to_dict / from_dict` round-trips a populated entry."""
    e = _make_voltage_input()
    e_back = IOEntry.from_dict(json.loads(json.dumps(e.to_dict())))
    assert e == e_back


@pytest.mark.unit
def test_io_entry_defaults_status_valid() -> None:
    """An entry with no status defaults to `valid`."""
    e = _make_voltage_input()
    assert e.status == "valid"


@pytest.mark.unit
def test_io_entry_from_dict_rejects_invalid_status() -> None:
    """An out-of-set `status` value raises `ValueError`."""
    payload = _make_voltage_input().to_dict()
    payload["status"] = "unknown_status_value"
    with pytest.raises(ValueError, match="status"):
        IOEntry.from_dict(payload)


@pytest.mark.unit
def test_io_entry_missing_id_raises() -> None:
    """`from_dict` requires `id`."""
    payload = _make_voltage_input().to_dict()
    del payload["id"]
    with pytest.raises(KeyError):
        IOEntry.from_dict(payload)


@pytest.mark.unit
def test_io_entry_missing_source_raises() -> None:
    """`from_dict` requires `source`."""
    payload = _make_voltage_input().to_dict()
    del payload["source"]
    with pytest.raises(KeyError):
        IOEntry.from_dict(payload)


@pytest.mark.unit
def test_io_entry_unknown_top_level_keys_route_into_extensions() -> None:
    """Forward-compat: unknown keys survive load via `extensions`."""
    payload = _make_voltage_input().to_dict()
    payload["future_normalization"] = {"db": True}
    e_back = IOEntry.from_dict(payload)
    assert e_back.extensions["future_normalization"] == {"db": True}


# ---------------------------------------------------------------------- #
# IOSelection round-trip + helpers
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_io_selection_round_trip_with_inputs_and_outputs() -> None:
    """A populated `IOSelection` round-trips through JSON cleanly."""
    s = IOSelection(
        inputs=(_make_voltage_input(),),
        outputs=(_make_position_output(),),
    )
    s_back = IOSelection.from_dict(json.loads(json.dumps(s.to_dict())))
    assert s == s_back


@pytest.mark.unit
def test_with_input_added_appends_to_inputs_only() -> None:
    """`with_input_added` extends inputs and leaves outputs alone."""
    s = IOSelection()
    entry = _make_voltage_input()
    s2 = s.with_input_added(entry)
    assert s2.inputs == (entry,)
    assert s2.outputs == ()


@pytest.mark.unit
def test_with_output_added_appends_to_outputs_only() -> None:
    """`with_output_added` extends outputs and leaves inputs alone."""
    s = IOSelection()
    entry = _make_position_output()
    s2 = s.with_output_added(entry)
    assert s2.inputs == ()
    assert s2.outputs == (entry,)


@pytest.mark.unit
def test_with_input_removed_filters_by_id() -> None:
    """Removing one input by id leaves the others intact."""
    a = _make_voltage_input()
    b = _make_voltage_input()
    s = IOSelection(inputs=(a, b))
    s2 = s.with_input_removed(a.id)
    assert s2.inputs == (b,)


# ---------------------------------------------------------------------- #
# Stale references survive persistence per spec §6.7
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_stale_status_is_preserved_on_round_trip() -> None:
    """Stale entries persist with their `status="stale"` (spec §6.7)."""
    e = _make_voltage_input().with_updated(status="stale")
    s = IOSelection(inputs=(e,))
    s_back = IOSelection.from_dict(s.to_dict())
    assert s_back.inputs[0].status == "stale"


# ---------------------------------------------------------------------- #
# Frozen
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_io_source_port_ref_is_frozen() -> None:
    """`IOSourcePortRef` is immutable."""
    src = IOSourcePortRef(
        port_ref=PortRef(component_id="cmp_X", port_id="p"),
        variable="across",
    )
    with pytest.raises(FrozenInstanceError):
        src.variable = "through"  # type: ignore[misc]


@pytest.mark.unit
def test_io_entry_is_frozen() -> None:
    """`IOEntry` is immutable."""
    e = _make_voltage_input()
    with pytest.raises(FrozenInstanceError):
        e.unit = "kV"  # type: ignore[misc]
