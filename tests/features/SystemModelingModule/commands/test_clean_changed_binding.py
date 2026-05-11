"""Unit tests for the `WorkspaceCommandStack.cleanChanged` binding (S1.7.5).

Closes the TODO(S1.7) markers in `WorkspaceModel._set_dirty` /
`_clear_dirty` per ADR-020 §"QUndoStack integration" (decision A2
from the S1.7.5 planning thread): the stack's `cleanChanged`
signal drives the model's dirty bit via the existing transition-
only helpers, augmenting (not replacing) the mutation-path
sources.

Tests cover:

* `cleanChanged(True)` → model becomes clean
* `cleanChanged(False)` → model becomes dirty
* The transition-only rule keeps redundant fires idempotent
  (push triggers both mutation-path `_set_dirty` AND
  cleanChanged → at most one `dirtyChanged(True)` emission).
* Full save-clean lifecycle: push → dirty → `setClean()` →
  clean again.
* Full undo-to-clean lifecycle: push → dirty → undo → clean.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
  (§"QUndoStack integration")
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


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model — required for AddComponentCommand."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """`WorkspaceCommandStack` bound to the model."""
    return WorkspaceCommandStack(model)


@pytest.mark.unit
def test_initial_state_matches_stack(stack: WorkspaceCommandStack) -> None:
    """Freshly constructed stack + model are both in the clean state."""
    assert stack.model.is_dirty is False
    assert stack.stack.isClean() is True


@pytest.mark.unit
def test_push_drives_dirty_via_mutation_and_clean_changed(
    stack: WorkspaceCommandStack,
) -> None:
    """A push transitions the model to dirty exactly once.

    Two sources fire on push:
      1. The mutation-path `_set_dirty` (from
         `add_component_from_definition`).
      2. The `cleanChanged(False)` slot (the stack left the
         clean index).

    The transition-only rule collapses these into a single
    effective transition — subscribers see exactly one
    `dirtyChanged(True)` emission.
    """
    dirty_emits: list[bool] = []
    stack.model.dirtyChanged.connect(dirty_emits.append)

    stack.push(AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0)))

    assert stack.model.is_dirty is True
    assert dirty_emits == [True]


@pytest.mark.unit
def test_undo_to_clean_index_clears_dirty(stack: WorkspaceCommandStack) -> None:
    """Undo that returns the stack to its clean index clears the model dirty bit.

    After push, the model is dirty and the stack has diverged
    from clean. After undo, the stack is back at the clean
    index → `cleanChanged(True)` → model becomes clean.
    """
    stack.push(AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0)))
    assert stack.model.is_dirty is True
    dirty_emits: list[bool] = []
    stack.model.dirtyChanged.connect(dirty_emits.append)

    stack.undo()

    assert stack.stack.isClean() is True
    assert stack.model.is_dirty is False
    assert dirty_emits == [False]


@pytest.mark.unit
def test_set_clean_after_save_clears_dirty(stack: WorkspaceCommandStack) -> None:
    """`stack.setClean()` simulates the post-save lifecycle.

    Future S2 save path will call `stack.setClean()` after
    persisting; the binding closes the loop so the model's
    dirty bit follows.
    """
    stack.push(AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0)))
    stack.push(AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(50.0, 0.0)))
    assert stack.model.is_dirty is True
    dirty_emits: list[bool] = []
    stack.model.dirtyChanged.connect(dirty_emits.append)

    stack.stack.setClean()

    assert stack.stack.isClean() is True
    assert stack.model.is_dirty is False
    assert dirty_emits == [False]


@pytest.mark.unit
def test_push_after_set_clean_re_dirties(stack: WorkspaceCommandStack) -> None:
    """After `setClean` + a new push, the model is dirty again.

    Validates the full save-clean-edit lifecycle: push → dirty →
    save (setClean) → clean → push (new edit) → dirty again.
    """
    stack.push(AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0)))
    stack.stack.setClean()
    assert stack.model.is_dirty is False

    stack.push(AddComponentCommand(stack.model, RESISTOR_DEFINITION.id, QPointF(50.0, 0.0)))

    assert stack.model.is_dirty is True
