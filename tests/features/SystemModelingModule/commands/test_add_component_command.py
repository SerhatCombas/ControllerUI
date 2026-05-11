"""Unit tests for `AddComponentCommand` (S1.7.1).

Covers the first concrete command in the workspace command stack:

* Construction pre-validates registry availability and definition
  id (a malformed command must not land on the undo stack).
* First `redo()` mints a new `cmp_<ULID>` instance via
  `WorkspaceModel.add_component_from_definition` (S1.B.1d).
* `undo()` removes the previously-added component.
* Subsequent `redo()` re-inserts the captured `ComponentInstance`
  verbatim via `WorkspaceModel.restore_component` (S1.7.1) — the
  id, position, parameters, timestamps, and physical_attributes
  are preserved across the undo/redo cycle (ADR-002 / `02 §8`).
* Signal contract: `componentAdded` fires on every redo,
  `componentRemoved` on undo. The dirty-bit transition follows
  ADR-020's transition-only rule.

Tests cover both the explicit-kwarg-free happy path (the typical
drag-from-library flow) and the parameter-override path (used by
project-load / copy-paste in later stages).

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `decisions/ADR-021-builtin-component-definitions.md`
* `specs/02_workspace_requirements.md` §8, §25
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    AddComponentCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #


@pytest.fixture
def registry() -> ComponentRegistry:
    """A `ComponentRegistry` populated with the Phase-1 MVP definitions."""
    return ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)


@pytest.fixture
def model(registry: ComponentRegistry) -> WorkspaceModel:
    """A registry-wired `WorkspaceModel`."""
    return WorkspaceModel(registry=registry)


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """A `WorkspaceCommandStack` bound to the registry-wired model."""
    return WorkspaceCommandStack(model)


# ---------------------------------------------------------------------- #
# Constructor pre-validation
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_construct_requires_registry_wired_model() -> None:
    """Pre-validation: model without a registry → `RuntimeError`.

    A command that cannot validate must not land on the stack
    (Qt's `QUndoStack` does not unwind a failed push gracefully).
    `__init__` raises before the command is ever pushable.
    """
    model = WorkspaceModel()  # no registry

    with pytest.raises(RuntimeError, match="registry-wired"):
        AddComponentCommand(model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))


@pytest.mark.unit
def test_construct_with_unknown_definition_id_raises_key_error(
    model: WorkspaceModel,
) -> None:
    """Pre-validation: unknown definition_id → `KeyError`."""
    with pytest.raises(KeyError):
        AddComponentCommand(model, "electrical.unknown.does_not_exist", QPointF(0.0, 0.0))


@pytest.mark.unit
def test_construct_sets_text_from_definition_display_name(
    model: WorkspaceModel,
) -> None:
    """The QUndoCommand text uses the definition's `display_name`."""
    command = AddComponentCommand(model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert command.text() == f"Add {RESISTOR_DEFINITION.display_name}"


@pytest.mark.unit
def test_construct_does_not_mutate_model(model: WorkspaceModel) -> None:
    """Constructing a command must not mutate the model.

    Per `WorkspaceCommand` contract: mutation happens in `redo()`
    (which `QUndoStack.push` invokes), not in `__init__`. This
    keeps construction side-effect-free so callers can probe
    `text` / etc. before deciding whether to push.
    """
    AddComponentCommand(model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert len(model.components) == 0
    assert model.is_dirty is False


# ---------------------------------------------------------------------- #
# Happy path — push, undo, redo
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_push_creates_component_and_captures_id(
    stack: WorkspaceCommandStack,
) -> None:
    """`stack.push(command)` mints a new component via the model.

    After push, the command's `component_id` accessor returns the
    minted id and `model.components` contains the new instance.
    """
    command = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(120.0, 80.0))

    stack.push(command)

    assert command.component_id is not None
    assert command.component_id.startswith("cmp_")
    assert command.component_id in stack.model.components
    instance = stack.model.components[command.component_id]
    assert instance.definition_id == RESISTOR_DEFINITION.id
    assert instance.position == (120.0, 80.0)


@pytest.mark.unit
def test_undo_removes_component(stack: WorkspaceCommandStack) -> None:
    """`stack.undo()` removes the previously-added component."""
    command = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    stack.push(command)
    component_id = command.component_id
    assert component_id is not None

    stack.undo()

    assert component_id not in stack.model.components
    assert len(stack.model.components) == 0


@pytest.mark.unit
def test_redo_after_undo_restores_same_component_id(
    stack: WorkspaceCommandStack,
) -> None:
    """Undo → redo cycle preserves the original `cmp_<ULID>` id.

    Identity stability is the core S1.7.1 contract (ADR-002 / `02
    §8`): without it, connection references and cross-feature
    links would dangle after every undo/redo. The captured
    `ComponentInstance` carries the original id; `restore_component`
    re-inserts it verbatim.
    """
    command = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    stack.push(command)
    first_id = command.component_id
    first_instance = stack.model.components[first_id]  # type: ignore[index]
    stack.undo()

    stack.redo()

    assert command.component_id == first_id
    restored = stack.model.components[first_id]  # type: ignore[index]
    # `restore_component` re-inserts the captured frozen instance
    # verbatim, so equality (full dataclass __eq__) holds.
    assert restored == first_instance


@pytest.mark.unit
def test_redo_after_undo_preserves_parameters_and_position(
    stack: WorkspaceCommandStack,
) -> None:
    """Undo → redo preserves parameter overrides and placement.

    Spot-checks specific fields beyond identity to confirm the
    captured-instance approach round-trips structural state too.
    """
    command = AddComponentCommand(
        stack.model,
        RESISTOR_DEFINITION.id,
        QPointF(50.0, 75.0),
        custom_label="R_load",
        rotation=90.0,
        parameters={"resistance": 2200.0},
    )
    stack.push(command)
    stack.undo()

    stack.redo()

    instance = stack.model.components[command.component_id]  # type: ignore[index]
    assert instance.position == (50.0, 75.0)
    assert instance.rotation == 90.0
    assert instance.custom_label == "R_load"
    assert instance.parameters == {"resistance": 2200.0}


# ---------------------------------------------------------------------- #
# Signal + dirty-bit contract
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_push_emits_component_added(stack: WorkspaceCommandStack) -> None:
    """A pushed `AddComponentCommand` fires `componentAdded` once."""
    captured: list[str] = []
    stack.model.componentAdded.connect(captured.append)
    command = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    stack.push(command)

    assert captured == [command.component_id]


@pytest.mark.unit
def test_undo_emits_component_removed(stack: WorkspaceCommandStack) -> None:
    """Undo fires a single `componentRemoved` with the original id."""
    command = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    stack.push(command)
    captured: list[str] = []
    stack.model.componentRemoved.connect(captured.append)

    stack.undo()

    assert captured == [command.component_id]


@pytest.mark.unit
def test_redo_after_undo_re_emits_component_added(
    stack: WorkspaceCommandStack,
) -> None:
    """Second redo also fires `componentAdded` (UI must re-render).

    Both code paths — first redo via
    `add_component_from_definition` and subsequent redos via
    `restore_component` — emit the same `componentAdded` signal so
    UI subscribers see one consistent event type per addition.
    """
    command = AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    stack.push(command)
    stack.undo()
    captured: list[str] = []
    stack.model.componentAdded.connect(captured.append)

    stack.redo()

    assert captured == [command.component_id]
