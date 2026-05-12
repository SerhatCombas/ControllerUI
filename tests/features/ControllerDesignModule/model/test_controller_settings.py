"""Unit tests for ControllerSettings dataclass family (S2.A scaffold)."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from features.ControllerDesignModule.model import (
    ControllerSettings,
    ControllerSpec,
    new_controller_id,
    new_io_input_id,
    new_io_output_id,
)


def _make_pid() -> ControllerSpec:
    """Construct a representative PID controller spec for round-trip tests."""
    return ControllerSpec(
        id=new_controller_id(),
        controller_type="PID",
        display_name="Main PID",
        enabled=True,
        parameters={"kp": 2.0, "ki": 0.5, "kd": 0.1},
        input_ref=new_io_input_id(),
        output_ref=new_io_output_id(),
        metadata={"author": "test"},
    )


# ---------------------------------------------------------------------- #
# Defaults + construction
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_controller_settings_default_is_empty_list() -> None:
    """A fresh `ControllerSettings()` has no controllers."""
    cs = ControllerSettings()
    assert cs.controllers == ()
    assert cs.metadata == {}
    assert cs.extensions == {}


@pytest.mark.unit
def test_controller_spec_required_fields() -> None:
    """`id` and `controller_type` are positional required fields."""
    spec = ControllerSpec(id="ctrl_X", controller_type="P")
    assert spec.id == "ctrl_X"
    assert spec.controller_type == "P"
    assert spec.display_name == ""
    assert spec.enabled is False
    assert spec.parameters == {}
    assert spec.input_ref is None
    assert spec.output_ref is None


# ---------------------------------------------------------------------- #
# Round-trip
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_controller_settings_round_trip_single_controller() -> None:
    """A populated single-controller settings survives JSON round-trip."""
    cs = ControllerSettings(controllers=(_make_pid(),))
    cs_back = ControllerSettings.from_dict(json.loads(json.dumps(cs.to_dict())))
    assert cs == cs_back


@pytest.mark.unit
def test_controller_settings_round_trip_multiple_controllers() -> None:
    """Multiple controllers preserve order on round-trip."""
    a = ControllerSpec(id="ctrl_A", controller_type="P")
    b = ControllerSpec(id="ctrl_B", controller_type="PI")
    c = ControllerSpec(id="ctrl_C", controller_type="PID")
    cs = ControllerSettings(controllers=(a, b, c))
    cs_back = ControllerSettings.from_dict(cs.to_dict())
    assert [c.id for c in cs_back.controllers] == ["ctrl_A", "ctrl_B", "ctrl_C"]


# ---------------------------------------------------------------------- #
# Forward-compat: unknown controller_type + unknown fields
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_unknown_controller_type_is_preserved_per_spec_section_12_2() -> None:
    """An unknown controller_type round-trips verbatim."""
    spec = ControllerSpec(id="ctrl_X", controller_type="LQR")
    spec_back = ControllerSpec.from_dict(spec.to_dict())
    assert spec_back.controller_type == "LQR"


@pytest.mark.unit
def test_unknown_top_level_keys_route_into_extensions() -> None:
    """ControllerSpec unknown fields land in `extensions`."""
    payload = ControllerSpec(id="ctrl_X", controller_type="PID").to_dict()
    payload["future_gain_scheduling"] = [1.0, 2.0, 3.0]
    spec_back = ControllerSpec.from_dict(payload)
    assert spec_back.extensions["future_gain_scheduling"] == [1.0, 2.0, 3.0]


# ---------------------------------------------------------------------- #
# Required-field enforcement
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_controller_spec_from_dict_missing_id_raises() -> None:
    """`id` is required; missing it raises `KeyError`."""
    with pytest.raises(KeyError):
        ControllerSpec.from_dict({"controller_type": "PID"})


@pytest.mark.unit
def test_controller_spec_from_dict_missing_controller_type_raises() -> None:
    """`controller_type` is required; missing it raises `KeyError`."""
    with pytest.raises(KeyError):
        ControllerSpec.from_dict({"id": "ctrl_X"})


# ---------------------------------------------------------------------- #
# Immutable update helpers
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_with_controller_added_appends_new_entry() -> None:
    """`with_controller_added()` returns a new instance with the entry appended."""
    cs = ControllerSettings()
    spec = ControllerSpec(id="ctrl_X", controller_type="P")
    cs2 = cs.with_controller_added(spec)
    assert cs.controllers == ()
    assert cs2.controllers == (spec,)


@pytest.mark.unit
def test_with_controller_removed_filters_by_id() -> None:
    """`with_controller_removed()` drops the matching entry only."""
    a = ControllerSpec(id="ctrl_A", controller_type="P")
    b = ControllerSpec(id="ctrl_B", controller_type="PI")
    cs = ControllerSettings(controllers=(a, b))
    cs2 = cs.with_controller_removed("ctrl_A")
    assert cs2.controllers == (b,)


@pytest.mark.unit
def test_with_controller_replaced_swaps_matching_id() -> None:
    """`with_controller_replaced()` swaps the matching entry in place."""
    a = ControllerSpec(id="ctrl_A", controller_type="P")
    a_new = ControllerSpec(id="ctrl_A", controller_type="PID", parameters={"kp": 3})
    cs = ControllerSettings(controllers=(a,))
    cs2 = cs.with_controller_replaced(a_new)
    assert cs2.controllers == (a_new,)


@pytest.mark.unit
def test_with_controller_replaced_unknown_id_raises() -> None:
    """`with_controller_replaced()` raises when no entry matches."""
    cs = ControllerSettings()
    spec = ControllerSpec(id="ctrl_X", controller_type="P")
    with pytest.raises(KeyError):
        cs.with_controller_replaced(spec)


@pytest.mark.unit
def test_controller_spec_is_frozen() -> None:
    """`ControllerSpec` is a frozen dataclass."""
    spec = ControllerSpec(id="ctrl_X", controller_type="P")
    with pytest.raises(FrozenInstanceError):
        spec.enabled = True  # type: ignore[misc]


# ---------------------------------------------------------------------- #
# Spec §5.6 — unused parameters survive controller_type changes
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_unused_parameters_survive_controller_type_change_via_with_updated() -> None:
    """`kd` is preserved when changing PID → PI per spec §5.6."""
    pid = ControllerSpec(
        id="ctrl_X",
        controller_type="PID",
        parameters={"kp": 1.0, "ki": 0.1, "kd": 0.5},
    )
    pi = pid.with_updated(controller_type="PI")
    # Phase 1 keeps unused keys; UI hides them. S2.B validators may
    # later flag this as informational; the dataclass does not strip.
    assert pi.parameters == {"kp": 1.0, "ki": 0.1, "kd": 0.5}
