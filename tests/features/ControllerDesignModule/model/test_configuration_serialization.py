"""Unit tests for `ConfigurationModel.to_dict` / `from_dict` (S2.E.1).

Spec/02 §29.3.1 + spec/03 §11.1 contract:

* Round-trip: empty model, defaults, populated model.
* Atomicity: any sub-section parse failure leaves the model
  untouched.
* `loaded` signal fires once at the end of a successful load.
* `ConfigurationCommandStack` subscribes to `loaded` and clears
  its QUndoStack.
* Per-section signals fire during apply (one each, transition-only
  per ADR-020).
"""

from __future__ import annotations

import json

import pytest

from features.ControllerDesignModule.commands import (
    AddControllerCommand,
    ConfigurationCommandStack,
)
from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    ControllerSpec,
    IOSelection,
    PlotLayout,
    SimulationSettings,
    load_default_configuration,
    new_controller_id,
)


@pytest.fixture
def empty_model() -> ConfigurationModel:
    return ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(),
        simulation_settings=SimulationSettings(),
        plot_layout=PlotLayout(),
    )


@pytest.fixture
def default_model() -> ConfigurationModel:
    cfg = load_default_configuration()
    return ConfigurationModel(
        controller_settings=cfg.controller_settings,
        io_selection=cfg.io_selection,
        simulation_settings=cfg.simulation_settings,
        plot_layout=cfg.plot_layout,
    )


# ====================================================================== #
# Round-trip
# ====================================================================== #


@pytest.mark.unit
def test_empty_configuration_round_trip(empty_model: ConfigurationModel) -> None:
    """Empty `ConfigurationModel` round-trips through JSON unchanged."""
    payload = json.loads(json.dumps(empty_model.to_dict()))
    empty_model.from_dict(payload)
    assert empty_model.controller_settings == ControllerSettings()
    assert empty_model.io_selection == IOSelection()
    assert empty_model.simulation_settings == SimulationSettings()
    assert empty_model.plot_layout == PlotLayout()


@pytest.mark.unit
def test_default_configuration_round_trip(default_model: ConfigurationModel) -> None:
    """Phase-1 defaults survive round-trip with all four sections intact."""
    original_controllers = default_model.controller_settings.controllers
    original_plot_types = [s.plot_type for s in default_model.plot_layout.slots]
    payload = json.loads(json.dumps(default_model.to_dict()))
    default_model.from_dict(payload)
    assert default_model.controller_settings.controllers == original_controllers
    assert [s.plot_type for s in default_model.plot_layout.slots] == original_plot_types


@pytest.mark.unit
def test_round_trip_through_a_fresh_model(default_model: ConfigurationModel) -> None:
    """Serializing one model and loading into another transfers all sections."""
    payload = json.loads(json.dumps(default_model.to_dict()))
    fresh = ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(),
        simulation_settings=SimulationSettings(),
        plot_layout=PlotLayout(),
    )
    fresh.from_dict(payload)
    assert fresh.controller_settings == default_model.controller_settings
    assert fresh.io_selection == default_model.io_selection
    assert fresh.simulation_settings == default_model.simulation_settings
    assert fresh.plot_layout == default_model.plot_layout


@pytest.mark.unit
def test_to_dict_layout_matches_spec_top_level_keys(
    default_model: ConfigurationModel,
) -> None:
    """Output dict carries the four top-level configuration sections."""
    payload = default_model.to_dict()
    assert set(payload.keys()) == {
        "controller_settings",
        "io_selection",
        "simulation_settings",
        "plot_layout",
    }


# ====================================================================== #
# Atomicity (spec §29.3.1)
# ====================================================================== #


@pytest.mark.unit
def test_from_dict_atomicity_on_section_parse_failure(
    default_model: ConfigurationModel,
) -> None:
    """A malformed section payload leaves every section untouched."""
    pre_controllers = default_model.controller_settings.controllers
    pre_simulation = default_model.simulation_settings

    bad_payload = default_model.to_dict()
    # Inject a malformed controller_settings (missing `controller_type`
    # on a controller entry) — `ControllerSpec.from_dict` raises.
    bad_payload["controller_settings"] = {
        "controllers": [
            {"id": "ctrl_X"}  # missing controller_type
        ],
        "metadata": {},
        "extensions": {},
    }
    with pytest.raises(KeyError):
        default_model.from_dict(bad_payload)
    # Atomicity: nothing should have changed.
    assert default_model.controller_settings.controllers == pre_controllers
    assert default_model.simulation_settings == pre_simulation


# ====================================================================== #
# `loaded` signal + command stack subscription
# ====================================================================== #


@pytest.mark.unit
def test_loaded_signal_fires_once_on_successful_load(
    empty_model: ConfigurationModel,
) -> None:
    """`loaded` emits exactly once after `from_dict` completes."""
    received: list[None] = []
    empty_model.loaded.connect(lambda: received.append(None))
    empty_model.from_dict(empty_model.to_dict())
    assert len(received) == 1


@pytest.mark.unit
def test_loaded_signal_does_not_fire_on_parse_failure(
    empty_model: ConfigurationModel,
) -> None:
    """`loaded` stays silent when load aborts in the parse phase."""
    received: list[None] = []
    empty_model.loaded.connect(lambda: received.append(None))
    with pytest.raises(KeyError):
        empty_model.from_dict(
            {
                "controller_settings": {
                    "controllers": [{"id": "ctrl_X"}],  # missing controller_type
                }
            }
        )
    assert received == []


@pytest.mark.unit
def test_configuration_command_stack_clears_on_load(
    empty_model: ConfigurationModel,
) -> None:
    """`ConfigurationCommandStack` subscribes to `loaded` and clears its stack.

    The binding installs automatically at stack construction; the
    shell does not have to wire it.
    """
    stack = ConfigurationCommandStack(empty_model)
    # Push history.
    stack.push(
        AddControllerCommand(
            empty_model,
            ControllerSpec(id=new_controller_id(), controller_type="PID"),
        )
    )
    assert stack.count() == 1
    assert empty_model.is_dirty is True

    # Load same payload back; stack should clear.
    empty_model.from_dict(empty_model.to_dict())
    assert stack.count() == 0
    assert empty_model.is_dirty is False


# ====================================================================== #
# Per-section signals fire during apply
# ====================================================================== #


@pytest.mark.unit
def test_per_section_signals_fire_on_load_only_on_value_change(
    empty_model: ConfigurationModel,
) -> None:
    """ADR-020 transition-only: setters fire only when value differs.

    Sections that differ from the current state emit their signal
    once during apply; sections that are value-equal stay silent.
    This test loads the Phase-1 defaults into an empty model:
    `controller_settings` (one PID) and `plot_layout` (four slots)
    differ from empty; `io_selection` (empty list) and
    `simulation_settings` (already at default values) match and
    stay silent.
    """
    controller_received: list[object] = []
    io_received: list[object] = []
    sim_received: list[object] = []
    plot_received: list[object] = []
    empty_model.controllerSettingsChanged.connect(controller_received.append)
    empty_model.ioSelectionChanged.connect(io_received.append)
    empty_model.simulationSettingsChanged.connect(sim_received.append)
    empty_model.plotLayoutChanged.connect(plot_received.append)

    cfg = load_default_configuration()
    target_model = ConfigurationModel(
        controller_settings=cfg.controller_settings,
        io_selection=cfg.io_selection,
        simulation_settings=cfg.simulation_settings,
        plot_layout=cfg.plot_layout,
    )
    empty_model.from_dict(target_model.to_dict())

    # Defaults differ from empty in two of the four sections.
    assert len(controller_received) == 1  # one PID added
    assert len(io_received) == 0  # empty matches empty
    assert len(sim_received) == 0  # defaults match SimulationSettings()
    assert len(plot_received) == 1  # four slots added


# ====================================================================== #
# Missing-section fallback (spec/03 §11.4)
# ====================================================================== #


@pytest.mark.unit
def test_missing_section_falls_back_to_default(
    empty_model: ConfigurationModel,
) -> None:
    """Spec/03 §11.4: missing top-level section uses the empty value type."""
    # Provide only one section; the other three should default.
    payload = {
        "simulation_settings": {"stop_time": 50.0, "start_time": 0.0, "sample_time": 0.01},
    }
    empty_model.from_dict(payload)
    assert empty_model.simulation_settings.stop_time == 50.0
    assert empty_model.controller_settings == ControllerSettings()
    assert empty_model.io_selection == IOSelection()
    assert empty_model.plot_layout == PlotLayout()
