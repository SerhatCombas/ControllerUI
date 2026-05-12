"""Unit tests for `ConfigurationModel` (S2.B.3).

Covers the QObject host for the Phase-1 configuration sections:
construction with three frozen dataclasses, read-only accessors,
and the `set_io_selection` mutation + `ioSelectionChanged` signal
contract (transition-only emission per ADR-020).
"""

from __future__ import annotations

import pytest

from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    ControllerSpec,
    IOEntry,
    IOSelection,
    IOSourcePortRef,
    SimulationSettings,
    load_default_configuration,
)
from shared.graph.port_ref import PortRef


@pytest.fixture
def default_io_entry() -> IOEntry:
    return IOEntry(
        id="ioin_X",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_R", port_id="p"),
            variable="across",
        ),
    )


@pytest.fixture
def configuration() -> ConfigurationModel:
    cfg = load_default_configuration()
    return ConfigurationModel(
        controller_settings=cfg.controller_settings,
        io_selection=cfg.io_selection,
        simulation_settings=cfg.simulation_settings,
    )


# ====================================================================== #
# Construction + accessors
# ====================================================================== #


@pytest.mark.unit
def test_configuration_model_construction_exposes_each_section(
    configuration: ConfigurationModel,
) -> None:
    """All three sections are reachable through read-only properties."""
    assert isinstance(configuration.controller_settings, ControllerSettings)
    assert isinstance(configuration.io_selection, IOSelection)
    assert isinstance(configuration.simulation_settings, SimulationSettings)


@pytest.mark.unit
def test_configuration_model_holds_initial_values_by_reference() -> None:
    """The constructor stores the exact dataclass instances passed in."""
    cs = ControllerSettings(controllers=(ControllerSpec(id="ctrl_X", controller_type="P"),))
    ios = IOSelection()
    sim = SimulationSettings(stop_time=42.0)
    model = ConfigurationModel(
        controller_settings=cs,
        io_selection=ios,
        simulation_settings=sim,
    )
    assert model.controller_settings is cs
    assert model.io_selection is ios
    assert model.simulation_settings is sim


# ====================================================================== #
# `set_io_selection` + `ioSelectionChanged` signal
# ====================================================================== #


@pytest.mark.unit
def test_set_io_selection_with_new_value_emits_signal(
    configuration: ConfigurationModel,
    default_io_entry: IOEntry,
) -> None:
    """A genuinely-new IOSelection fires the signal exactly once."""
    received: list[IOSelection] = []
    configuration.ioSelectionChanged.connect(received.append)

    new_selection = IOSelection(inputs=(default_io_entry,))
    configuration.set_io_selection(new_selection)

    assert len(received) == 1
    assert received[0] is new_selection
    assert configuration.io_selection is new_selection


@pytest.mark.unit
def test_set_io_selection_with_equal_value_does_not_emit(
    configuration: ConfigurationModel,
) -> None:
    """ADR-020 transition-only rule: equal value → no signal emission.

    The frozen-dataclass equality (`==`) compares structurally, so an
    independently-constructed IOSelection with identical contents is
    treated as the same value.
    """
    starting = configuration.io_selection
    duplicate = IOSelection(
        inputs=starting.inputs,
        outputs=starting.outputs,
        metadata=dict(starting.metadata),
        extensions=dict(starting.extensions),
    )
    received: list[IOSelection] = []
    configuration.ioSelectionChanged.connect(received.append)

    configuration.set_io_selection(duplicate)

    assert received == []


@pytest.mark.unit
def test_set_io_selection_updates_property_in_place(
    configuration: ConfigurationModel,
    default_io_entry: IOEntry,
) -> None:
    """After mutation, the property returns the new value."""
    new_selection = IOSelection(inputs=(default_io_entry,))
    configuration.set_io_selection(new_selection)
    assert configuration.io_selection == new_selection


@pytest.mark.unit
def test_set_io_selection_payload_carries_full_new_value(
    configuration: ConfigurationModel,
    default_io_entry: IOEntry,
) -> None:
    """ADR-018: payload is the full new selection, not just a delta."""
    new_selection = IOSelection(
        inputs=(default_io_entry,),
        outputs=(),
        metadata={"note": "test"},
    )
    received: list[IOSelection] = []
    configuration.ioSelectionChanged.connect(received.append)

    configuration.set_io_selection(new_selection)

    assert received[0].metadata == {"note": "test"}
    assert received[0].inputs == (default_io_entry,)


# ====================================================================== #
# Sections other than IOSelection — read-only in Phase 1 (S2.B.3 scope)
# ====================================================================== #


@pytest.mark.unit
def test_no_public_setter_for_controller_settings_at_s2_b3(
    configuration: ConfigurationModel,
) -> None:
    """Setter API for controller/sim/plot lands in S2.D, not S2.B.3."""
    assert not hasattr(configuration, "set_controller_settings")
    assert not hasattr(configuration, "set_simulation_settings")
