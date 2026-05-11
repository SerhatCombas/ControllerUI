"""Unit tests for `ChangeParameterCommand` (S1.7.2).

Covers the two-branch undo strategy:

* Param was PRESENT before the edit → undo restores the captured
  prior value via `WorkspaceModel.set_parameter`.
* Param was ABSENT before the edit → undo removes the inserted
  entry via `WorkspaceModel.unset_parameter`, so the instance
  reverts to "use definition default at runtime" per `02 §11.3`.

Also verifies the parameter-id presence flag (`existed_before`),
which the command uses to dispatch the undo branch.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `decisions/ADR-021-builtin-component-definitions.md`
* `specs/02_workspace_requirements.md` §11.3, §11.4
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    ChangeParameterCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model with one pre-placed resistor."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """`WorkspaceCommandStack` bound to the model."""
    return WorkspaceCommandStack(model)


@pytest.fixture
def component_with_param(model: WorkspaceModel) -> str:
    """A resistor with an explicit `resistance` parameter."""
    return model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": 1000.0},
    )


@pytest.fixture
def component_without_params(model: WorkspaceModel) -> str:
    """A resistor with an empty parameters dict (use definition defaults)."""
    return model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))


# ---------------------------------------------------------------------- #
# Construction
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_construct_raises_keyerror_for_unknown_component(
    model: WorkspaceModel,
) -> None:
    """Pre-validation: missing component → `KeyError`."""
    with pytest.raises(KeyError):
        ChangeParameterCommand(model, "cmp_nonexistent", "resistance", 1000.0)


@pytest.mark.unit
def test_construct_captures_existed_before_when_param_present(
    model: WorkspaceModel,
    component_with_param: str,
) -> None:
    """`existed_before` is True when the param is in the instance dict."""
    command = ChangeParameterCommand(model, component_with_param, "resistance", 2200.0)

    assert command.existed_before is True


@pytest.mark.unit
def test_construct_captures_existed_before_when_param_absent(
    model: WorkspaceModel,
    component_without_params: str,
) -> None:
    """`existed_before` is False when the param is not yet set."""
    command = ChangeParameterCommand(model, component_without_params, "resistance", 2200.0)

    assert command.existed_before is False


# ---------------------------------------------------------------------- #
# Push + undo + redo — param was PRESENT before
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_push_updates_existing_parameter(
    stack: WorkspaceCommandStack,
    component_with_param: str,
) -> None:
    """`push` writes the new value to an already-present parameter."""
    stack.push(ChangeParameterCommand(stack.model, component_with_param, "resistance", 2200.0))

    assert stack.model.components[component_with_param].parameters == {"resistance": 2200.0}


@pytest.mark.unit
def test_undo_restores_previous_value_when_param_existed_before(
    stack: WorkspaceCommandStack,
    component_with_param: str,
) -> None:
    """When the param existed before, undo restores the captured prior value."""
    stack.push(ChangeParameterCommand(stack.model, component_with_param, "resistance", 2200.0))

    stack.undo()

    assert stack.model.components[component_with_param].parameters == {"resistance": 1000.0}


@pytest.mark.unit
def test_redo_after_undo_reapplies_new_value(
    stack: WorkspaceCommandStack,
    component_with_param: str,
) -> None:
    """Redo cycles the parameter back to `new_value`."""
    stack.push(ChangeParameterCommand(stack.model, component_with_param, "resistance", 2200.0))
    stack.undo()

    stack.redo()

    assert stack.model.components[component_with_param].parameters == {"resistance": 2200.0}


# ---------------------------------------------------------------------- #
# Push + undo + redo — param was ABSENT before
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_push_inserts_new_parameter_when_absent(
    stack: WorkspaceCommandStack,
    component_without_params: str,
) -> None:
    """`push` inserts a parameter entry that was absent before."""
    stack.push(ChangeParameterCommand(stack.model, component_without_params, "resistance", 2200.0))

    assert stack.model.components[component_without_params].parameters == {"resistance": 2200.0}


@pytest.mark.unit
def test_undo_removes_entry_when_param_was_absent(
    stack: WorkspaceCommandStack,
    component_without_params: str,
) -> None:
    """When the param was absent before, undo REMOVES the inserted entry.

    Returning to the empty-parameters state is the load-bearing
    semantic: per `02 §11.3` an empty entry means "use the
    definition default at runtime", which is the correct
    pre-edit baseline.
    """
    stack.push(ChangeParameterCommand(stack.model, component_without_params, "resistance", 2200.0))

    stack.undo()

    assert stack.model.components[component_without_params].parameters == {}


@pytest.mark.unit
def test_redo_after_undo_reinserts_when_param_was_absent(
    stack: WorkspaceCommandStack,
    component_without_params: str,
) -> None:
    """Redo after undo re-inserts the parameter entry."""
    stack.push(ChangeParameterCommand(stack.model, component_without_params, "resistance", 2200.0))
    stack.undo()

    stack.redo()

    assert stack.model.components[component_without_params].parameters == {"resistance": 2200.0}


# ---------------------------------------------------------------------- #
# Signal contract
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_push_emits_component_changed(
    stack: WorkspaceCommandStack,
    component_with_param: str,
) -> None:
    """The model's `componentChanged` signal fires on the parameter edit."""
    captured: list[str] = []
    stack.model.componentChanged.connect(captured.append)

    stack.push(ChangeParameterCommand(stack.model, component_with_param, "resistance", 2200.0))

    assert captured == [component_with_param]
