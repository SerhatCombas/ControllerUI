"""Unit tests for `ConfigurationCommandStack` + dirty binding (S2.D.1)."""

from __future__ import annotations

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
    new_controller_id,
)


@pytest.fixture
def model() -> ConfigurationModel:
    """Empty `ConfigurationModel` for stack-level tests."""
    return ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(),
        simulation_settings=SimulationSettings(),
        plot_layout=PlotLayout(),
    )


@pytest.fixture
def stack(model: ConfigurationModel) -> ConfigurationCommandStack:
    """Stack bound to the model."""
    return ConfigurationCommandStack(model)


def _make_spec(controller_type: str = "PID") -> ControllerSpec:
    return ControllerSpec(id=new_controller_id(), controller_type=controller_type)


# ====================================================================== #
# Construction + accessors
# ====================================================================== #


@pytest.mark.unit
def test_stack_initial_state_is_clean_and_empty(
    stack: ConfigurationCommandStack,
) -> None:
    """A fresh stack reports zero count, clean index, model not dirty."""
    assert stack.count() == 0
    assert stack.index() == 0
    assert stack.model.is_dirty is False


@pytest.mark.unit
def test_stack_exposes_underlying_qundo_stack(
    stack: ConfigurationCommandStack,
) -> None:
    """`stack` property returns the QUndoStack the shell will add to QUndoGroup."""
    from PySide6.QtGui import QUndoStack

    assert isinstance(stack.stack, QUndoStack)


# ====================================================================== #
# Dirty binding (ADR-020)
# ====================================================================== #


@pytest.mark.unit
def test_pushing_command_marks_model_dirty(
    stack: ConfigurationCommandStack,
) -> None:
    """`QUndoStack.cleanChanged(False)` → `model._set_dirty`."""
    stack.push(AddControllerCommand(stack.model, _make_spec()))
    assert stack.model.is_dirty is True


@pytest.mark.unit
def test_undo_back_to_clean_index_clears_dirty(
    stack: ConfigurationCommandStack,
) -> None:
    """`cleanChanged(True)` clears the dirty bit when the stack returns to clean."""
    stack.push(AddControllerCommand(stack.model, _make_spec()))
    assert stack.model.is_dirty is True
    stack.undo()
    assert stack.model.is_dirty is False


@pytest.mark.unit
def test_dirty_changed_signal_fires_on_transition_only(
    stack: ConfigurationCommandStack,
) -> None:
    """ADR-020: dirty-bit transitions emit; redundant pushes do not."""
    received: list[bool] = []
    stack.model.dirtyChanged.connect(received.append)

    stack.push(AddControllerCommand(stack.model, _make_spec()))
    stack.push(AddControllerCommand(stack.model, _make_spec()))
    stack.push(AddControllerCommand(stack.model, _make_spec()))

    # Only ONE False→True transition across three pushes.
    assert received == [True]


@pytest.mark.unit
def test_undo_redo_cycles_produce_one_transition_pair(
    stack: ConfigurationCommandStack,
) -> None:
    """Push → undo → redo → undo gives [True, False, True, False]."""
    received: list[bool] = []
    stack.model.dirtyChanged.connect(received.append)

    stack.push(AddControllerCommand(stack.model, _make_spec()))
    stack.undo()
    stack.redo()
    stack.undo()

    assert received == [True, False, True, False]


@pytest.mark.unit
def test_count_and_index_track_push_undo_redo(
    stack: ConfigurationCommandStack,
) -> None:
    """Convenience accessors mirror QUndoStack semantics."""
    stack.push(AddControllerCommand(stack.model, _make_spec()))
    stack.push(AddControllerCommand(stack.model, _make_spec()))
    assert stack.count() == 2
    assert stack.index() == 2
    stack.undo()
    assert stack.index() == 1
    assert stack.can_undo() is True
    assert stack.can_redo() is True


@pytest.mark.unit
def test_undo_on_empty_stack_is_no_op(stack: ConfigurationCommandStack) -> None:
    """`undo()` on an empty stack does nothing (no exception)."""
    received: list[bool] = []
    stack.model.dirtyChanged.connect(received.append)
    stack.undo()
    assert received == []
    assert stack.model.is_dirty is False


@pytest.mark.unit
def test_redo_when_no_redo_pending_is_no_op(
    stack: ConfigurationCommandStack,
) -> None:
    """`redo()` with nothing pending → no exception, no state change."""
    stack.redo()
    assert stack.model.is_dirty is False
