"""Unit tests for the six S2.D.1 controller commands.

Each command gets a positive test (redo applies, undo reverts,
redo restores), plus relevant edge cases. Signal emission is
verified through `controllerSettingsChanged` (one fire per
transition) per the model's ADR-020 contract.
"""

from __future__ import annotations

import pytest

from features.ControllerDesignModule.commands import (
    AddControllerCommand,
    ChangeControllerTypeCommand,
    ConfigurationCommandStack,
    EditControllerParameterCommand,
    RemoveControllerCommand,
    SetControllerIOLinkageCommand,
    ToggleControllerEnabledCommand,
)
from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    ControllerSpec,
    IOSelection,
    PlotLayout,
    SimulationSettings,
    new_controller_id,
)


@pytest.fixture
def model() -> ConfigurationModel:
    return ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(),
        simulation_settings=SimulationSettings(),
        plot_layout=PlotLayout(),
    )


@pytest.fixture
def stack(model: ConfigurationModel) -> ConfigurationCommandStack:
    return ConfigurationCommandStack(model)


def _seed_controller(
    model: ConfigurationModel,
    *,
    controller_type: str = "PID",
    enabled: bool = False,
    parameters: dict[str, float] | None = None,
    input_ref: str | None = None,
    output_ref: str | None = None,
) -> str:
    """Seed a single controller in the model directly (no stack)."""
    cid = new_controller_id()
    spec = ControllerSpec(
        id=cid,
        controller_type=controller_type,
        enabled=enabled,
        parameters=dict(parameters or {}),
        input_ref=input_ref,
        output_ref=output_ref,
    )
    model.set_controller_settings(model.controller_settings.with_controller_added(spec))
    return cid


# ====================================================================== #
# AddControllerCommand
# ====================================================================== #


@pytest.mark.unit
def test_add_controller_appends_to_settings(
    stack: ConfigurationCommandStack,
) -> None:
    """`redo()` appends; `undo()` removes; `redo()` re-adds."""

    def controller_ids() -> list[str]:
        return [c.id for c in stack.model.controller_settings.controllers]

    spec = ControllerSpec(id=new_controller_id(), controller_type="PID")
    stack.push(AddControllerCommand(stack.model, spec))
    assert controller_ids() == [spec.id]
    stack.undo()
    assert controller_ids() == []
    stack.redo()
    assert controller_ids() == [spec.id]


@pytest.mark.unit
def test_add_controller_rejects_malformed_id() -> None:
    """A non-`ctrl_<ULID>` id fails fast in `__init__`."""
    model = ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(),
        simulation_settings=SimulationSettings(),
        plot_layout=PlotLayout(),
    )
    bad = ControllerSpec(id="not-a-ulid", controller_type="P")
    with pytest.raises(ValueError, match="ctrl_"):
        AddControllerCommand(model, bad)


@pytest.mark.unit
def test_add_controller_rejects_duplicate_id(
    stack: ConfigurationCommandStack,
) -> None:
    """Adding two controllers with the same id raises `KeyError`."""
    spec = ControllerSpec(id=new_controller_id(), controller_type="PID")
    stack.push(AddControllerCommand(stack.model, spec))
    with pytest.raises(KeyError):
        AddControllerCommand(stack.model, spec)


# ====================================================================== #
# RemoveControllerCommand
# ====================================================================== #


@pytest.mark.unit
def test_remove_controller_restores_position_on_undo(
    stack: ConfigurationCommandStack,
) -> None:
    """`undo()` restores the removed controller at its original index."""
    a = ControllerSpec(id=new_controller_id(), controller_type="P")
    b = ControllerSpec(id=new_controller_id(), controller_type="PI")
    c = ControllerSpec(id=new_controller_id(), controller_type="PID")
    for spec in (a, b, c):
        stack.push(AddControllerCommand(stack.model, spec))

    stack.push(RemoveControllerCommand(stack.model, b.id))
    assert [s.id for s in stack.model.controller_settings.controllers] == [a.id, c.id]

    stack.undo()
    assert [s.id for s in stack.model.controller_settings.controllers] == [
        a.id,
        b.id,
        c.id,
    ]


@pytest.mark.unit
def test_remove_controller_unknown_id_raises(
    stack: ConfigurationCommandStack,
) -> None:
    """`RemoveControllerCommand` rejects unknown id at `__init__`."""
    with pytest.raises(KeyError):
        RemoveControllerCommand(stack.model, "ctrl_does_not_exist")


# ====================================================================== #
# ChangeControllerTypeCommand
# ====================================================================== #


@pytest.mark.unit
def test_change_controller_type_round_trip(
    stack: ConfigurationCommandStack,
) -> None:
    """Type change is reversible."""
    cid = _seed_controller(stack.model, controller_type="PID")
    stack.push(ChangeControllerTypeCommand(stack.model, cid, "PI"))
    assert stack.model.controller_settings.controllers[0].controller_type == "PI"
    stack.undo()
    assert stack.model.controller_settings.controllers[0].controller_type == "PID"
    stack.redo()
    assert stack.model.controller_settings.controllers[0].controller_type == "PI"


@pytest.mark.unit
def test_change_controller_type_preserves_parameters_per_spec_5_6(
    stack: ConfigurationCommandStack,
) -> None:
    """Spec §5.6: changing type preserves unused parameter keys."""
    cid = _seed_controller(
        stack.model, controller_type="PID", parameters={"kp": 1.0, "ki": 0.5, "kd": 0.1}
    )
    stack.push(ChangeControllerTypeCommand(stack.model, cid, "PI"))
    params = stack.model.controller_settings.controllers[0].parameters
    # `kd` is unused for PI but preserved per spec §5.6.
    assert params == {"kp": 1.0, "ki": 0.5, "kd": 0.1}


@pytest.mark.unit
def test_change_controller_type_unknown_controller_raises(
    stack: ConfigurationCommandStack,
) -> None:
    """`__init__` rejects unknown controller id."""
    with pytest.raises(KeyError):
        ChangeControllerTypeCommand(stack.model, "ctrl_GHOST", "PI")


# ====================================================================== #
# EditControllerParameterCommand
# ====================================================================== #


@pytest.mark.unit
def test_edit_parameter_round_trip_replaces_value(
    stack: ConfigurationCommandStack,
) -> None:
    """Edit redo/undo restores the prior value exactly."""
    cid = _seed_controller(stack.model, parameters={"kp": 1.0})
    stack.push(EditControllerParameterCommand(stack.model, cid, "kp", 3.14))
    assert stack.model.controller_settings.controllers[0].parameters["kp"] == 3.14
    stack.undo()
    assert stack.model.controller_settings.controllers[0].parameters["kp"] == 1.0


@pytest.mark.unit
def test_edit_parameter_adds_then_removes_on_undo(
    stack: ConfigurationCommandStack,
) -> None:
    """Editing an absent key adds it; undo restores absence."""
    cid = _seed_controller(stack.model, parameters={})
    stack.push(EditControllerParameterCommand(stack.model, cid, "ki", 0.5))
    assert stack.model.controller_settings.controllers[0].parameters == {"ki": 0.5}
    stack.undo()
    assert "ki" not in stack.model.controller_settings.controllers[0].parameters


@pytest.mark.unit
def test_edit_parameter_unknown_controller_raises(
    stack: ConfigurationCommandStack,
) -> None:
    """`__init__` rejects unknown controller id."""
    with pytest.raises(KeyError):
        EditControllerParameterCommand(stack.model, "ctrl_GHOST", "kp", 1.0)


# ====================================================================== #
# ToggleControllerEnabledCommand
# ====================================================================== #


@pytest.mark.unit
def test_toggle_enabled_round_trip(stack: ConfigurationCommandStack) -> None:
    """Toggle is reversible."""
    cid = _seed_controller(stack.model, enabled=False)
    stack.push(ToggleControllerEnabledCommand(stack.model, cid, True))
    assert stack.model.controller_settings.controllers[0].enabled is True
    stack.undo()
    assert stack.model.controller_settings.controllers[0].enabled is False


@pytest.mark.unit
def test_toggle_enabled_idempotent_when_value_unchanged(
    stack: ConfigurationCommandStack,
) -> None:
    """Pushing a toggle to the value already-set: setter no-ops + still on stack."""
    cid = _seed_controller(stack.model, enabled=True)
    received: list[object] = []
    stack.model.controllerSettingsChanged.connect(received.append)

    stack.push(ToggleControllerEnabledCommand(stack.model, cid, True))

    # The command pushed onto the stack, but the setter saw an equal
    # value and emitted no signal (ADR-020 transition-only).
    assert received == []
    assert stack.count() == 1


# ====================================================================== #
# SetControllerIOLinkageCommand
# ====================================================================== #


@pytest.mark.unit
def test_set_linkage_round_trip(stack: ConfigurationCommandStack) -> None:
    """Linkage change reversible; both input_ref and output_ref restored."""
    cid = _seed_controller(stack.model, input_ref=None, output_ref=None)
    stack.push(SetControllerIOLinkageCommand(stack.model, cid, "ioin_X", "ioout_Y"))
    spec = stack.model.controller_settings.controllers[0]
    assert spec.input_ref == "ioin_X"
    assert spec.output_ref == "ioout_Y"

    stack.undo()
    spec = stack.model.controller_settings.controllers[0]
    assert spec.input_ref is None
    assert spec.output_ref is None


@pytest.mark.unit
def test_set_linkage_clears_with_none(
    stack: ConfigurationCommandStack,
) -> None:
    """Passing `None` clears the binding; undo restores."""
    cid = _seed_controller(stack.model, input_ref="ioin_old", output_ref="ioout_old")
    stack.push(SetControllerIOLinkageCommand(stack.model, cid, None, None))
    spec = stack.model.controller_settings.controllers[0]
    assert spec.input_ref is None
    assert spec.output_ref is None

    stack.undo()
    spec = stack.model.controller_settings.controllers[0]
    assert spec.input_ref == "ioin_old"
    assert spec.output_ref == "ioout_old"


# ====================================================================== #
# controllerSettingsChanged signal emission
# ====================================================================== #


@pytest.mark.unit
def test_controller_settings_changed_fires_on_each_push(
    stack: ConfigurationCommandStack,
) -> None:
    """Each command that produces a new ControllerSettings emits the signal."""
    received: list[ControllerSettings] = []
    stack.model.controllerSettingsChanged.connect(received.append)
    cid = _seed_controller(stack.model)  # seeded directly, emits once
    initial = len(received)

    stack.push(ChangeControllerTypeCommand(stack.model, cid, "PI"))
    stack.push(EditControllerParameterCommand(stack.model, cid, "kp", 2.0))

    assert len(received) == initial + 2


@pytest.mark.unit
def test_controller_settings_changed_payload_carries_full_new_value(
    stack: ConfigurationCommandStack,
) -> None:
    """ADR-018 self-contained payload: signal carries the new ControllerSettings."""
    cid = _seed_controller(stack.model, controller_type="PID")
    received: list[ControllerSettings] = []
    stack.model.controllerSettingsChanged.connect(received.append)

    stack.push(ChangeControllerTypeCommand(stack.model, cid, "PI"))

    assert isinstance(received[-1], ControllerSettings)
    assert received[-1].controllers[0].controller_type == "PI"
