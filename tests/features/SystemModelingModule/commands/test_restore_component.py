"""Unit tests for `WorkspaceModel.restore_component` (S1.7.1).

The `restore_component` method is the model-side counterpart to
the captured-instance pattern used by `AddComponentCommand` (and
`DeleteComponentCommand` in S1.7.3): it re-inserts a previously-
removed `ComponentInstance` verbatim with its original
`cmp_<ULID>` id, so undo/redo cycles preserve identity per
ADR-002 / `02 §8`.

Tests live alongside the commands test suite (rather than in
`tests/features/.../model/`) because the method exists for the
command stack and is exercised in concert with commands.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §8, §11.4
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def model() -> WorkspaceModel:
    """A registry-wired `WorkspaceModel` for the restore-cycle tests."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.mark.unit
def test_restore_component_reinserts_with_original_id(
    model: WorkspaceModel,
) -> None:
    """Round-trip add → remove → restore yields the same id and instance."""
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    captured = model.components[new_id]
    model.remove_component(new_id)
    assert new_id not in model.components

    model.restore_component(captured)

    assert new_id in model.components
    assert model.components[new_id] == captured


@pytest.mark.unit
def test_restore_component_raises_on_id_collision(
    model: WorkspaceModel,
) -> None:
    """Re-inserting on top of an existing id raises `ValueError`.

    A collision indicates a logic bug in the command sequencing
    (e.g., a missing `undo()` between two `redo()` calls); raising
    early surfaces the bug rather than silently overwriting state.
    """
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    captured = model.components[new_id]
    # The component is still in the model; restore must reject.

    with pytest.raises(ValueError, match=r"id collision"):
        model.restore_component(captured)


@pytest.mark.unit
def test_restore_component_emits_component_added(
    model: WorkspaceModel,
) -> None:
    """`restore_component` fires the same `componentAdded` signal as
    a fresh add — UI subscribers do not need to distinguish.
    """
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    captured = model.components[new_id]
    model.remove_component(new_id)
    received: list[str] = []
    model.componentAdded.connect(received.append)

    model.restore_component(captured)

    assert received == [new_id]


@pytest.mark.unit
def test_restore_component_drives_dirty_transition(
    model: WorkspaceModel,
) -> None:
    """`restore_component` follows the ADR-020 transition-only rule.

    Restoring a component into a clean model transitions
    `False → True` and fires one `dirtyChanged(True)` emission.
    Restoring again (after another remove+restore) on an already-
    dirty model does not re-emit.
    """
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    captured = model.components[new_id]
    model.remove_component(new_id)
    model._clear_dirty()  # reset to clean for the transition check
    dirty_emits: list[bool] = []
    model.dirtyChanged.connect(dirty_emits.append)

    model.restore_component(captured)

    assert dirty_emits == [True]
    assert model.is_dirty is True


@pytest.mark.unit
def test_restore_component_inside_batch_records_via_change_set(
    model: WorkspaceModel,
) -> None:
    """Inside `model.batch()`, restore_component suppresses the
    `componentAdded` signal and records the addition into the
    cumulative `WorkspaceChangeSet` instead (same plumbing as
    `add_component_from_definition`)."""
    new_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    captured = model.components[new_id]
    model.remove_component(new_id)
    fine_grained: list[str] = []
    change_sets: list[object] = []
    model.componentAdded.connect(fine_grained.append)
    model.modelChanged.connect(change_sets.append)

    with model.batch():
        model.restore_component(captured)

    assert fine_grained == []  # suppressed inside batch
    assert len(change_sets) == 1
    assert change_sets[0].added_components == (new_id,)  # type: ignore[attr-defined]
