"""Unit tests for S2.D.3 — simulation + plot commands + mirror sync.

Covers:

* `ChangeSimulationSettingCommand` — single-class delta wrapper for
  all 7+ SimulationSettings fields; per-field round-trips, mixed-field
  delta, no-op rejection, captured-state immutability.
* `ChangePlotTypeCommand` — spec §8.7 rule applied at command
  construction; same-kind preserves selection, kind change resets.
* `ChangePlotTitleCommand` — title round-trip.
* `ToggleFullscreenCommand` — set + clear, unknown slot rejection.
* Mirror sync — multiple subscribers to `plotLayoutChanged` all
  receive the same payload from one `set_plot_layout` call
  (ADR-017).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject

from features.ControllerDesignModule.commands import (
    ChangePlotTitleCommand,
    ChangePlotTypeCommand,
    ChangeSimulationSettingCommand,
    ConfigurationCommandStack,
    ToggleFullscreenCommand,
)
from features.ControllerDesignModule.model import (
    ConfigurationModel,
    PlotLayout,
    SimulationSettings,
    load_default_configuration,
)


@pytest.fixture
def model() -> ConfigurationModel:
    cfg = load_default_configuration()
    return ConfigurationModel(
        controller_settings=cfg.controller_settings,
        io_selection=cfg.io_selection,
        simulation_settings=cfg.simulation_settings,
        plot_layout=cfg.plot_layout,
    )


@pytest.fixture
def stack(model: ConfigurationModel) -> ConfigurationCommandStack:
    return ConfigurationCommandStack(model)


# ====================================================================== #
# ChangeSimulationSettingCommand — per-field round trip
# ====================================================================== #


@pytest.mark.unit
def test_change_simulation_start_time_round_trip(
    stack: ConfigurationCommandStack,
) -> None:
    """`start_time` change reverses cleanly."""
    new = stack.model.simulation_settings.with_updated(start_time=2.0)
    stack.push(ChangeSimulationSettingCommand(stack.model, new))
    assert stack.model.simulation_settings.start_time == 2.0
    stack.undo()
    assert stack.model.simulation_settings.start_time == 0.0


@pytest.mark.unit
def test_change_simulation_stop_time_round_trip(
    stack: ConfigurationCommandStack,
) -> None:
    """`stop_time` change reverses cleanly."""
    new = stack.model.simulation_settings.with_updated(stop_time=42.0)
    stack.push(ChangeSimulationSettingCommand(stack.model, new))
    assert stack.model.simulation_settings.stop_time == 42.0
    stack.undo()
    assert stack.model.simulation_settings.stop_time == 10.0


@pytest.mark.unit
def test_change_simulation_sample_time_round_trip(
    stack: ConfigurationCommandStack,
) -> None:
    """`sample_time` change reverses cleanly."""
    new = stack.model.simulation_settings.with_updated(sample_time=0.005)
    stack.push(ChangeSimulationSettingCommand(stack.model, new))
    assert stack.model.simulation_settings.sample_time == 0.005
    stack.undo()
    assert stack.model.simulation_settings.sample_time == 0.01


@pytest.mark.unit
def test_change_simulation_max_step_round_trip(
    stack: ConfigurationCommandStack,
) -> None:
    """`max_step` set / clear via the same command."""
    new = stack.model.simulation_settings.with_updated(max_step=0.001)
    stack.push(ChangeSimulationSettingCommand(stack.model, new))
    assert stack.model.simulation_settings.max_step == 0.001
    stack.undo()
    assert stack.model.simulation_settings.max_step is None


@pytest.mark.unit
def test_change_simulation_solver_round_trip(
    stack: ConfigurationCommandStack,
) -> None:
    """`solver` string field round-trips through the same command."""
    new = stack.model.simulation_settings.with_updated(solver="variable_step")
    stack.push(ChangeSimulationSettingCommand(stack.model, new))
    assert stack.model.simulation_settings.solver == "variable_step"
    stack.undo()
    assert stack.model.simulation_settings.solver == "auto"


@pytest.mark.unit
def test_change_simulation_use_controller_round_trip(
    stack: ConfigurationCommandStack,
) -> None:
    """Boolean `use_controller` flows through the same command (no toggle class)."""
    new = stack.model.simulation_settings.with_updated(use_controller=True)
    stack.push(ChangeSimulationSettingCommand(stack.model, new))
    assert stack.model.simulation_settings.use_controller is True
    stack.undo()
    assert stack.model.simulation_settings.use_controller is False


@pytest.mark.unit
def test_change_simulation_use_last_valid_model_round_trip(
    stack: ConfigurationCommandStack,
) -> None:
    """Boolean `use_last_valid_model` round-trips through the same command."""
    new = stack.model.simulation_settings.with_updated(use_last_valid_model=False)
    stack.push(ChangeSimulationSettingCommand(stack.model, new))
    assert stack.model.simulation_settings.use_last_valid_model is False
    stack.undo()
    assert stack.model.simulation_settings.use_last_valid_model is True


@pytest.mark.unit
def test_change_simulation_mixed_field_delta_one_command(
    stack: ConfigurationCommandStack,
) -> None:
    """Multi-field user action: one `with_updated` + one command + one undo."""
    new = stack.model.simulation_settings.with_updated(
        start_time=1.5, stop_time=20.0, solver="fixed_step", use_controller=True
    )
    stack.push(ChangeSimulationSettingCommand(stack.model, new))

    sim = stack.model.simulation_settings
    assert sim.start_time == 1.5
    assert sim.stop_time == 20.0
    assert sim.solver == "fixed_step"
    assert sim.use_controller is True

    stack.undo()
    sim = stack.model.simulation_settings
    assert sim.start_time == 0.0
    assert sim.solver == "auto"
    assert sim.use_controller is False


@pytest.mark.unit
def test_change_simulation_no_op_rejected_at_init(
    model: ConfigurationModel,
) -> None:
    """Value-equal command construction raises before stack push."""
    with pytest.raises(ValueError, match="nothing to apply"):
        ChangeSimulationSettingCommand(model, model.simulation_settings)


@pytest.mark.unit
def test_change_simulation_captured_state_survives_external_mutation(
    stack: ConfigurationCommandStack,
) -> None:
    """`_old_settings` is captured at __init__; later external edits don't leak."""
    cmd = ChangeSimulationSettingCommand(
        stack.model, stack.model.simulation_settings.with_updated(start_time=1.0)
    )
    # External mutation BEFORE command is pushed.
    stack.model.set_simulation_settings(
        stack.model.simulation_settings.with_updated(start_time=99.0)
    )
    # Push the original command — redo applies the captured new_settings,
    # undo restores the captured old_settings (start_time=0.0), NOT the
    # 99.0 we just installed externally.
    stack.push(cmd)
    assert stack.model.simulation_settings.start_time == 1.0
    stack.undo()
    assert stack.model.simulation_settings.start_time == 0.0


# ====================================================================== #
# ChangePlotTypeCommand — spec §8.7 rule applied
# ====================================================================== #


@pytest.mark.unit
def test_change_plot_type_same_kind_preserves_selection(
    stack: ConfigurationCommandStack,
) -> None:
    """time_response → state_variables (both `channels`) preserves selection."""
    # plot_1 is time_response/channels by default.
    stack.push(ChangePlotTypeCommand(stack.model, "plot_1", "state_variables"))
    slot = stack.model.plot_layout.slots[0]
    assert slot.plot_type == "state_variables"
    assert slot.channel_selection.kind == "channels"


@pytest.mark.unit
def test_change_plot_type_different_kind_resets_selection(
    stack: ConfigurationCommandStack,
) -> None:
    """time_response (channels) → bode (io_pair) resets the channel_selection."""
    stack.push(ChangePlotTypeCommand(stack.model, "plot_1", "bode"))
    slot = stack.model.plot_layout.slots[0]
    assert slot.plot_type == "bode"
    assert slot.channel_selection.kind == "io_pair"


@pytest.mark.unit
def test_change_plot_type_undo_restores_full_prior_slot(
    stack: ConfigurationCommandStack,
) -> None:
    """Undo restores the captured prior slot, including channel_selection."""
    stack.push(ChangePlotTypeCommand(stack.model, "plot_1", "bode"))
    stack.undo()
    slot = stack.model.plot_layout.slots[0]
    assert slot.plot_type == "time_response"
    assert slot.channel_selection.kind == "channels"


@pytest.mark.unit
def test_change_plot_type_unknown_slot_raises(model: ConfigurationModel) -> None:
    """Unknown `slot_id` raises `KeyError` at __init__."""
    with pytest.raises(KeyError):
        ChangePlotTypeCommand(model, "plot_GHOST", "bode")


@pytest.mark.unit
def test_change_plot_type_same_value_rejected(stack: ConfigurationCommandStack) -> None:
    """Setting plot_type to its current value is a no-op → rejected."""
    with pytest.raises(ValueError, match="already has"):
        ChangePlotTypeCommand(stack.model, "plot_1", "time_response")


# ====================================================================== #
# ChangePlotTitleCommand
# ====================================================================== #


@pytest.mark.unit
def test_change_plot_title_round_trip(stack: ConfigurationCommandStack) -> None:
    """Title rename + undo restores the prior title."""
    stack.push(ChangePlotTitleCommand(stack.model, "plot_2", "My Step Plot"))
    assert stack.model.plot_layout.slots[1].title == "My Step Plot"
    stack.undo()
    assert stack.model.plot_layout.slots[1].title == "Step Response"


@pytest.mark.unit
def test_change_plot_title_unknown_slot_raises(model: ConfigurationModel) -> None:
    """Unknown slot id raises `KeyError`."""
    with pytest.raises(KeyError):
        ChangePlotTitleCommand(model, "plot_GHOST", "X")


@pytest.mark.unit
def test_change_plot_title_same_value_rejected(stack: ConfigurationCommandStack) -> None:
    """Same-title push is a no-op → rejected at __init__."""
    current = stack.model.plot_layout.slots[1].title
    with pytest.raises(ValueError, match="already has"):
        ChangePlotTitleCommand(stack.model, "plot_2", current)


# ====================================================================== #
# ToggleFullscreenCommand
# ====================================================================== #


@pytest.mark.unit
def test_toggle_fullscreen_set_round_trip(stack: ConfigurationCommandStack) -> None:
    """Setting fullscreen + undo restores `None`."""
    stack.push(ToggleFullscreenCommand(stack.model, "plot_3"))
    assert stack.model.plot_layout.fullscreen_slot_id == "plot_3"
    stack.undo()
    assert stack.model.plot_layout.fullscreen_slot_id is None


@pytest.mark.unit
def test_toggle_fullscreen_clear_round_trip(stack: ConfigurationCommandStack) -> None:
    """Exit fullscreen from a fullscreened slot."""
    # First enter fullscreen on plot_2.
    stack.push(ToggleFullscreenCommand(stack.model, "plot_2"))
    # Now exit.
    stack.push(ToggleFullscreenCommand(stack.model, None))
    assert stack.model.plot_layout.fullscreen_slot_id is None
    stack.undo()  # restores plot_2 fullscreen
    assert stack.model.plot_layout.fullscreen_slot_id == "plot_2"


@pytest.mark.unit
def test_toggle_fullscreen_unknown_slot_raises(model: ConfigurationModel) -> None:
    """Targeting a non-existent slot raises `KeyError`."""
    with pytest.raises(KeyError):
        ToggleFullscreenCommand(model, "plot_GHOST")


@pytest.mark.unit
def test_toggle_fullscreen_no_op_rejected(stack: ConfigurationCommandStack) -> None:
    """Setting fullscreen to the current value is a no-op → rejected."""
    with pytest.raises(ValueError, match="already in"):
        ToggleFullscreenCommand(stack.model, None)  # current is already None


# ====================================================================== #
# simulationSettingsChanged signal + setter API surface
# ====================================================================== #


@pytest.mark.unit
def test_simulation_settings_changed_fires_once_per_push(
    stack: ConfigurationCommandStack,
) -> None:
    """Each command produces exactly one `simulationSettingsChanged` emission."""
    received: list[SimulationSettings] = []
    stack.model.simulationSettingsChanged.connect(received.append)
    stack.push(
        ChangeSimulationSettingCommand(
            stack.model,
            stack.model.simulation_settings.with_updated(start_time=1.0),
        )
    )
    assert len(received) == 1


@pytest.mark.unit
def test_simulation_settings_changed_payload_carries_full_new_value(
    stack: ConfigurationCommandStack,
) -> None:
    """ADR-018: payload is the full new SimulationSettings."""
    received: list[SimulationSettings] = []
    stack.model.simulationSettingsChanged.connect(received.append)
    new = stack.model.simulation_settings.with_updated(solver="fixed_step")
    stack.push(ChangeSimulationSettingCommand(stack.model, new))
    assert isinstance(received[-1], SimulationSettings)
    assert received[-1].solver == "fixed_step"


@pytest.mark.unit
def test_setter_api_complete_after_s2_d_3(model: ConfigurationModel) -> None:
    """All four spec/03 §9 setters are present after S2.D.3."""
    assert hasattr(model, "set_io_selection")
    assert hasattr(model, "set_plot_layout")
    assert hasattr(model, "set_controller_settings")
    assert hasattr(model, "set_simulation_settings")


# ====================================================================== #
# Mirror sync (ADR-017)
# ====================================================================== #


@pytest.mark.unit
def test_plot_layout_change_notifies_all_subscribers_per_adr_017(
    stack: ConfigurationCommandStack,
) -> None:
    """A single `set_plot_layout` call reaches every subscriber with the same payload.

    ADR-017 specifies that the Configuration panel dropdown and the
    per-plot header dropdown both subscribe to `plotLayoutChanged`
    so they share one source of truth. This test installs two stub
    subscribers (standing in for the two UI surfaces) and verifies
    that a single `ChangePlotTypeCommand.push()` fires both,
    delivering an identical payload object.
    """
    config_dropdown_received: list[PlotLayout] = []
    plot_header_received: list[PlotLayout] = []

    stack.model.plotLayoutChanged.connect(config_dropdown_received.append)
    stack.model.plotLayoutChanged.connect(plot_header_received.append)

    stack.push(ChangePlotTypeCommand(stack.model, "plot_1", "bode"))

    assert len(config_dropdown_received) == 1
    assert len(plot_header_received) == 1
    # ADR-018 self-contained payload: both subscribers see the same
    # PlotLayout instance.
    assert config_dropdown_received[0] is plot_header_received[0]
    assert config_dropdown_received[0].slots[0].plot_type == "bode"


@pytest.mark.unit
def test_multiple_subscribers_remain_in_sync_across_undo_redo(
    stack: ConfigurationCommandStack,
) -> None:
    """Mirror sync survives undo / redo cycles."""

    class _Stub(QObject):
        def __init__(self) -> None:
            super().__init__()
            self.received: list[PlotLayout] = []

    a = _Stub()
    b = _Stub()
    stack.model.plotLayoutChanged.connect(a.received.append)
    stack.model.plotLayoutChanged.connect(b.received.append)

    stack.push(ChangePlotTypeCommand(stack.model, "plot_1", "bode"))
    stack.undo()
    stack.redo()

    # 3 emissions (push, undo, redo); both subscribers received all 3.
    assert len(a.received) == 3
    assert len(b.received) == 3
    # Final state agrees between the two streams pairwise.
    assert [p.slots[0].plot_type for p in a.received] == [p.slots[0].plot_type for p in b.received]
