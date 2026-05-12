"""Unit tests for SimulationSettings dataclass family (S2.A scaffold)."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from features.ControllerDesignModule.model import (
    InitialConditionOverride,
    InitialConditions,
    SimulationSettings,
)

# ---------------------------------------------------------------------- #
# Defaults
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_simulation_settings_defaults_match_spec_03_section_13() -> None:
    """`SimulationSettings()` matches the Phase-1 default block from spec §13."""
    s = SimulationSettings()
    assert s.start_time == 0.0
    assert s.stop_time == 10.0
    assert s.sample_time == 0.01
    assert s.max_step is None
    assert s.solver == "auto"
    assert s.use_controller is False
    assert s.use_last_valid_model is True
    assert s.initial_conditions == InitialConditions()
    assert s.metadata == {}
    assert s.extensions == {}


@pytest.mark.unit
def test_initial_conditions_defaults_match_spec_section_7_4() -> None:
    """`InitialConditions()` defaults to component_parameters + empty overrides."""
    ic = InitialConditions()
    assert ic.source == "component_parameters"
    assert ic.overrides == ()


# ---------------------------------------------------------------------- #
# Round-trip (to_dict / from_dict)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_simulation_settings_default_round_trip() -> None:
    """Default settings survive JSON round-trip unchanged."""
    s = SimulationSettings()
    s_back = SimulationSettings.from_dict(json.loads(json.dumps(s.to_dict())))
    assert s == s_back


@pytest.mark.unit
def test_simulation_settings_round_trip_preserves_max_step_value() -> None:
    """A non-None `max_step` survives round-trip as `float`."""
    s = SimulationSettings(max_step=0.005)
    s_back = SimulationSettings.from_dict(s.to_dict())
    assert s_back.max_step == 0.005


@pytest.mark.unit
def test_simulation_settings_round_trip_preserves_overrides() -> None:
    """`InitialConditionOverride` entries survive round-trip."""
    overrides = (
        InitialConditionOverride(component_id="cmp_X", parameter_id="v0", value=1.5),
        InitialConditionOverride(component_id="cmp_Y", parameter_id="x0", value=-0.25),
    )
    s = SimulationSettings(
        initial_conditions=InitialConditions(source="explicit_overrides", overrides=overrides)
    )
    s_back = SimulationSettings.from_dict(s.to_dict())
    assert s_back.initial_conditions.source == "explicit_overrides"
    assert s_back.initial_conditions.overrides == overrides


# ---------------------------------------------------------------------- #
# Forward-compat: unknown solver + unknown top-level keys
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_unknown_solver_string_is_preserved_per_spec_section_7_5() -> None:
    """An unknown solver id round-trips verbatim (validation is S2.B)."""
    s = SimulationSettings(solver="quantum_radau")
    s_back = SimulationSettings.from_dict(s.to_dict())
    assert s_back.solver == "quantum_radau"


@pytest.mark.unit
def test_unknown_top_level_keys_are_routed_into_extensions() -> None:
    """Per spec §11.3 + §12.2 — forward-compat keys survive load."""
    payload = SimulationSettings().to_dict()
    payload["future_field"] = {"adaptive_step": True}
    s_back = SimulationSettings.from_dict(payload)
    assert s_back.extensions["future_field"] == {"adaptive_step": True}


@pytest.mark.unit
def test_explicit_extensions_value_survives_with_unknown_keys() -> None:
    """`extensions` from the payload merges with carryover unknowns."""
    payload = SimulationSettings(extensions={"my_flag": 1}).to_dict()
    payload["future_field"] = "x"
    s_back = SimulationSettings.from_dict(payload)
    assert s_back.extensions == {"my_flag": 1, "future_field": "x"}


# ---------------------------------------------------------------------- #
# Immutability + update helper
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_simulation_settings_is_frozen() -> None:
    """Direct field assignment on a frozen instance raises."""
    s = SimulationSettings()
    with pytest.raises(FrozenInstanceError):
        s.start_time = 1.0  # type: ignore[misc]


@pytest.mark.unit
def test_with_updated_returns_modified_copy_leaves_original_unchanged() -> None:
    """`with_updated()` produces a new value; original stays intact."""
    s = SimulationSettings(start_time=0.0)
    s2 = s.with_updated(start_time=2.5, stop_time=20.0)
    assert s.start_time == 0.0
    assert s.stop_time == 10.0
    assert s2.start_time == 2.5
    assert s2.stop_time == 20.0


# ---------------------------------------------------------------------- #
# InitialConditionOverride strict mode
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_initial_condition_override_from_dict_round_trip() -> None:
    """Override entry round-trips verbatim."""
    o = InitialConditionOverride(component_id="cmp_Z", parameter_id="omega0", value=3.14)
    o_back = InitialConditionOverride.from_dict(o.to_dict())
    assert o == o_back


@pytest.mark.unit
def test_initial_condition_override_missing_field_raises_key_error() -> None:
    """`from_dict` requires every field; missing one raises `KeyError`."""
    with pytest.raises(KeyError):
        InitialConditionOverride.from_dict({"component_id": "cmp_X", "value": 1.0})
