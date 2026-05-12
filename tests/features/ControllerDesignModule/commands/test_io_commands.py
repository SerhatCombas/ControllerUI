"""Unit tests for the five S2.D.2 I/O selection commands.

`set_io_selection` setter + `ioSelectionChanged` signal already
landed in S2.B.3; this commit only adds command wrappers on top.
Each test pushes through the stack to exercise the dirty binding
end-to-end.
"""

from __future__ import annotations

import pytest

from features.ControllerDesignModule.commands import (
    AddIOInputCommand,
    AddIOOutputCommand,
    ConfigurationCommandStack,
    EditIOEntryCommand,
    RemoveIOInputCommand,
    RemoveIOOutputCommand,
)
from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    IOEntry,
    IOSelection,
    IOSourcePortRef,
    PlotLayout,
    SimulationSettings,
    new_io_input_id,
    new_io_output_id,
)
from shared.graph.port_ref import PortRef


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


def _make_input(component_id: str = "cmp_R") -> IOEntry:
    return IOEntry(
        id=new_io_input_id(),
        source=IOSourcePortRef(
            port_ref=PortRef(component_id=component_id, port_id="p"),
            variable="across",
        ),
        display_name="Vin",
        quantity="voltage",
        unit="V",
    )


def _make_output(component_id: str = "cmp_M") -> IOEntry:
    return IOEntry(
        id=new_io_output_id(),
        source=IOSourcePortRef(
            port_ref=PortRef(component_id=component_id, port_id="flange"),
            variable="across",
        ),
        display_name="Xout",
        quantity="displacement",
        unit="m",
    )


def _seed_input(model: ConfigurationModel, entry: IOEntry | None = None) -> IOEntry:
    """Seed one input directly (no stack)."""
    entry = entry or _make_input()
    model.set_io_selection(model.io_selection.with_input_added(entry))
    return entry


def _seed_output(model: ConfigurationModel, entry: IOEntry | None = None) -> IOEntry:
    entry = entry or _make_output()
    model.set_io_selection(model.io_selection.with_output_added(entry))
    return entry


# ====================================================================== #
# AddIOInputCommand
# ====================================================================== #


@pytest.mark.unit
def test_add_io_input_round_trip(stack: ConfigurationCommandStack) -> None:
    """redo/undo/redo cycle on AddIOInputCommand."""
    entry = _make_input()
    stack.push(AddIOInputCommand(stack.model, entry))
    assert [e.id for e in stack.model.io_selection.inputs] == [entry.id]
    stack.undo()
    assert list(stack.model.io_selection.inputs) == []
    stack.redo()
    assert [e.id for e in stack.model.io_selection.inputs] == [entry.id]


@pytest.mark.unit
def test_add_io_input_rejects_malformed_id(model: ConfigurationModel) -> None:
    """A non-`ioin_<ULID>` id fails fast in `__init__`."""
    bad = IOEntry(
        id="not-a-ulid",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_X", port_id="p"),
            variable="across",
        ),
    )
    with pytest.raises(ValueError, match="ioin_"):
        AddIOInputCommand(model, bad)


@pytest.mark.unit
def test_add_io_input_rejects_duplicate_id(
    stack: ConfigurationCommandStack,
) -> None:
    """A second add with the same id raises `KeyError`."""
    entry = _make_input()
    stack.push(AddIOInputCommand(stack.model, entry))
    with pytest.raises(KeyError):
        AddIOInputCommand(stack.model, entry)


# ====================================================================== #
# AddIOOutputCommand (symmetric)
# ====================================================================== #


@pytest.mark.unit
def test_add_io_output_round_trip(stack: ConfigurationCommandStack) -> None:
    """redo/undo on AddIOOutputCommand."""
    entry = _make_output()
    stack.push(AddIOOutputCommand(stack.model, entry))
    assert [e.id for e in stack.model.io_selection.outputs] == [entry.id]
    stack.undo()
    assert list(stack.model.io_selection.outputs) == []


@pytest.mark.unit
def test_add_io_output_rejects_malformed_id(model: ConfigurationModel) -> None:
    """A non-`ioout_<ULID>` id (e.g., an ioin_*) fails fast."""
    wrong_prefix = IOEntry(
        id=new_io_input_id(),  # ioin_*, not ioout_*
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_X", port_id="p"),
            variable="across",
        ),
    )
    with pytest.raises(ValueError, match="ioout_"):
        AddIOOutputCommand(model, wrong_prefix)


# ====================================================================== #
# RemoveIOInputCommand
# ====================================================================== #


@pytest.mark.unit
def test_remove_io_input_restores_position_on_undo(
    stack: ConfigurationCommandStack,
) -> None:
    """undo() restores the removed input at its original index."""
    a = _make_input("cmp_A")
    b = _make_input("cmp_B")
    c = _make_input("cmp_C")
    for e in (a, b, c):
        stack.push(AddIOInputCommand(stack.model, e))

    stack.push(RemoveIOInputCommand(stack.model, b.id))
    assert [e.id for e in stack.model.io_selection.inputs] == [a.id, c.id]
    stack.undo()
    assert [e.id for e in stack.model.io_selection.inputs] == [a.id, b.id, c.id]


@pytest.mark.unit
def test_remove_io_input_unknown_id_raises(model: ConfigurationModel) -> None:
    """RemoveIOInputCommand rejects unknown id at __init__."""
    with pytest.raises(KeyError):
        RemoveIOInputCommand(model, "ioin_does_not_exist")


# ====================================================================== #
# RemoveIOOutputCommand
# ====================================================================== #


@pytest.mark.unit
def test_remove_io_output_round_trip(stack: ConfigurationCommandStack) -> None:
    """Output remove + undo round-trip."""
    entry = _make_output()
    stack.push(AddIOOutputCommand(stack.model, entry))
    stack.push(RemoveIOOutputCommand(stack.model, entry.id))
    assert list(stack.model.io_selection.outputs) == []
    stack.undo()
    assert [e.id for e in stack.model.io_selection.outputs] == [entry.id]


@pytest.mark.unit
def test_remove_io_output_unknown_id_raises(model: ConfigurationModel) -> None:
    """RemoveIOOutputCommand rejects unknown id."""
    with pytest.raises(KeyError):
        RemoveIOOutputCommand(model, "ioout_does_not_exist")


# ====================================================================== #
# EditIOEntryCommand
# ====================================================================== #


@pytest.mark.unit
def test_edit_io_entry_field_round_trip(stack: ConfigurationCommandStack) -> None:
    """Single-field edit reverts exactly on undo."""
    seeded = _seed_input(stack.model)
    edited = seeded.with_updated(display_name="Renamed Vin")
    stack.push(EditIOEntryCommand(stack.model, edited))
    assert stack.model.io_selection.inputs[0].display_name == "Renamed Vin"
    stack.undo()
    assert stack.model.io_selection.inputs[0].display_name == "Vin"


@pytest.mark.unit
def test_edit_io_entry_works_for_outputs(stack: ConfigurationCommandStack) -> None:
    """The single edit command auto-detects the output bucket."""
    seeded = _seed_output(stack.model)
    edited = seeded.with_updated(unit="mm")
    stack.push(EditIOEntryCommand(stack.model, edited))
    assert stack.model.io_selection.outputs[0].unit == "mm"
    stack.undo()
    assert stack.model.io_selection.outputs[0].unit == "m"


@pytest.mark.unit
def test_edit_io_entry_source_swap(stack: ConfigurationCommandStack) -> None:
    """Replacing the IOSourcePortRef works through the same command."""
    seeded = _seed_input(stack.model)
    new_source = IOSourcePortRef(
        port_ref=PortRef(component_id="cmp_OTHER", port_id="n"),
        variable="through",
    )
    edited = seeded.with_updated(source=new_source)
    stack.push(EditIOEntryCommand(stack.model, edited))

    # Helpers wrap reads so mypy does not narrow Literal across
    # the stack-mutation side-effects.
    def first_input_component_id() -> str:
        return stack.model.io_selection.inputs[0].source.port_ref.component_id

    def first_input_variable() -> str:
        return stack.model.io_selection.inputs[0].source.variable

    assert first_input_component_id() == "cmp_OTHER"
    assert first_input_variable() == "through"
    stack.undo()
    assert first_input_component_id() == "cmp_R"
    assert first_input_variable() == "across"


@pytest.mark.unit
def test_edit_io_entry_preserves_list_position(
    stack: ConfigurationCommandStack,
) -> None:
    """Editing an entry in the middle of the list keeps its index."""
    a = _seed_input(stack.model, _make_input("cmp_A"))
    b = _seed_input(stack.model, _make_input("cmp_B"))
    c = _seed_input(stack.model, _make_input("cmp_C"))
    edited = b.with_updated(display_name="B_RENAMED")
    stack.push(EditIOEntryCommand(stack.model, edited))
    ids = [e.id for e in stack.model.io_selection.inputs]
    assert ids == [a.id, b.id, c.id]
    assert stack.model.io_selection.inputs[1].display_name == "B_RENAMED"


@pytest.mark.unit
def test_edit_io_entry_unknown_id_raises(model: ConfigurationModel) -> None:
    """EditIOEntryCommand rejects an id absent from both buckets."""
    ghost = IOEntry(
        id="ioin_GHOST",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_X", port_id="p"),
            variable="across",
        ),
    )
    with pytest.raises(KeyError):
        EditIOEntryCommand(model, ghost)


@pytest.mark.unit
def test_edit_io_entry_bucket_property_for_test_introspection(
    stack: ConfigurationCommandStack,
) -> None:
    """The bucket property exposes which list the entry came from."""
    in_entry = _seed_input(stack.model)
    out_entry = _seed_output(stack.model)

    in_edit = EditIOEntryCommand(stack.model, in_entry.with_updated(display_name="X"))
    out_edit = EditIOEntryCommand(stack.model, out_entry.with_updated(display_name="Y"))

    assert in_edit.bucket == "inputs"
    assert out_edit.bucket == "outputs"


# ====================================================================== #
# ioSelectionChanged signal emission
# ====================================================================== #


@pytest.mark.unit
def test_io_selection_changed_fires_once_per_push(
    stack: ConfigurationCommandStack,
) -> None:
    """Each command produces exactly one ioSelectionChanged emission."""
    received: list[IOSelection] = []
    stack.model.ioSelectionChanged.connect(received.append)

    stack.push(AddIOInputCommand(stack.model, _make_input()))
    stack.push(AddIOOutputCommand(stack.model, _make_output()))
    stack.push(
        EditIOEntryCommand(
            stack.model,
            stack.model.io_selection.inputs[0].with_updated(unit="kV"),
        )
    )

    assert len(received) == 3


@pytest.mark.unit
def test_io_selection_changed_payload_carries_full_new_value(
    stack: ConfigurationCommandStack,
) -> None:
    """ADR-018: signal payload is the new IOSelection in full."""
    seeded = _seed_input(stack.model)
    received: list[IOSelection] = []
    stack.model.ioSelectionChanged.connect(received.append)

    stack.push(EditIOEntryCommand(stack.model, seeded.with_updated(display_name="V_after")))
    assert isinstance(received[-1], IOSelection)
    assert received[-1].inputs[0].display_name == "V_after"
