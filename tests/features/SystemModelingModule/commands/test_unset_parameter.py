"""Unit tests for `WorkspaceModel.unset_parameter` (S1.7.2).

The `unset_parameter` method is the model-side counterpart to
`set_parameter`, introduced in S1.7.2 to support
`ChangeParameterCommand`'s undo path when the first redo inserted
a parameter that was absent before. Removing the entry returns the
instance to the "use definition default at runtime" semantic per
`02 §11.3` / `ComponentInstance.parameters`.

References:
----------
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §11.3, §11.4
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
    """Registry-wired model for the unset_parameter tests."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.mark.unit
def test_unset_parameter_removes_existing_entry(model: WorkspaceModel) -> None:
    """The named parameter entry disappears from the instance dict."""
    cid = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": 1000.0},
    )

    model.unset_parameter(cid, "resistance")

    assert model.components[cid].parameters == {}


@pytest.mark.unit
def test_unset_parameter_no_op_when_absent(model: WorkspaceModel) -> None:
    """No-op suppression: removing an absent parameter fires no signal
    and does not mark the model dirty."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    model._clear_dirty()  # reset to clean for the transition check
    received: list[str] = []
    model.componentChanged.connect(received.append)
    dirty_emits: list[bool] = []
    model.dirtyChanged.connect(dirty_emits.append)

    model.unset_parameter(cid, "resistance")  # parameter is not present

    assert received == []
    assert dirty_emits == []
    assert model.is_dirty is False


@pytest.mark.unit
def test_unset_parameter_emits_component_changed(model: WorkspaceModel) -> None:
    """Successful removal fires `componentChanged` per the parameter-edit
    signal contract (same as `set_parameter`)."""
    cid = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": 1000.0},
    )
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.unset_parameter(cid, "resistance")

    assert received == [cid]


@pytest.mark.unit
def test_unset_parameter_drives_dirty_transition(model: WorkspaceModel) -> None:
    """`unset_parameter` follows ADR-020 transition-only dirty tracking."""
    cid = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": 1000.0},
    )
    model._clear_dirty()  # reset for the transition check
    dirty_emits: list[bool] = []
    model.dirtyChanged.connect(dirty_emits.append)

    model.unset_parameter(cid, "resistance")

    assert dirty_emits == [True]
    assert model.is_dirty is True


@pytest.mark.unit
def test_unset_parameter_raises_keyerror_for_unknown_component(
    model: WorkspaceModel,
) -> None:
    """Unknown component_id → `KeyError` (existence check is first)."""
    with pytest.raises(KeyError) as exc_info:
        model.unset_parameter("cmp_nonexistent", "resistance")

    assert "cmp_nonexistent" in str(exc_info.value)


@pytest.mark.unit
def test_unset_parameter_inside_batch_records_via_change_set(
    model: WorkspaceModel,
) -> None:
    """Inside `model.batch()`, removal suppresses `componentChanged` and
    records the edit into the cumulative `WorkspaceChangeSet`."""
    cid = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": 1000.0},
    )
    fine_grained: list[str] = []
    change_sets: list[object] = []
    model.componentChanged.connect(fine_grained.append)
    model.modelChanged.connect(change_sets.append)

    with model.batch():
        model.unset_parameter(cid, "resistance")

    assert fine_grained == []
    assert len(change_sets) == 1
    assert change_sets[0].changed_components == (cid,)  # type: ignore[attr-defined]
