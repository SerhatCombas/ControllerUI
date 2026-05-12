"""Unit tests for `WorkspaceModel.to_dict` / `from_dict` (S2.E.1).

Covers spec/02 §29.3.1 contract:

* Round-trip: empty model, populated model, model carrying
  workspace-level metadata / extensions.
* Atomicity: failure mid-parse leaves the model untouched.
* `loaded` signal fires once at the end of a successful load.
* `WorkspaceCommandStack` subscribes to `loaded` and clears its
  QUndoStack — covered through end-to-end push → load → undo cycle.
* ID counter rebuild — display ids continue at the right
  high-water mark after load.
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import WorkspaceCommandStack
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def registry() -> ComponentRegistry:
    return ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)


@pytest.fixture
def model(registry: ComponentRegistry) -> WorkspaceModel:
    return WorkspaceModel(registry=registry)


# ====================================================================== #
# Round-trip: empty model
# ====================================================================== #


@pytest.mark.unit
def test_empty_workspace_round_trip(model: WorkspaceModel) -> None:
    """Empty model serializes to empty lists and round-trips cleanly."""
    payload = model.to_dict()
    assert payload["components"] == []
    assert payload["connections"] == []
    model.from_dict(json.loads(json.dumps(payload)))
    assert len(model.components) == 0
    assert len(model.connections) == 0


# ====================================================================== #
# Round-trip: populated model
# ====================================================================== #


@pytest.mark.unit
def test_populated_workspace_round_trip(model: WorkspaceModel, registry: ComponentRegistry) -> None:
    """One component + serialized output reloads with identical state."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(10.0, 20.0))
    original_components = dict(model.components)
    payload = json.loads(json.dumps(model.to_dict()))

    fresh = WorkspaceModel(registry=registry)
    fresh.from_dict(payload)

    assert set(fresh.components.keys()) == {cid}
    assert fresh.components[cid] == original_components[cid]


@pytest.mark.unit
def test_workspace_metadata_and_extensions_round_trip(model: WorkspaceModel) -> None:
    """Workspace-level metadata / extensions survive round-trip."""
    payload = model.to_dict()
    payload["metadata"] = {"project_note": "test"}
    payload["extensions"] = {"future_workspace_field": 42}
    model.from_dict(json.loads(json.dumps(payload)))

    second_payload = model.to_dict()
    assert second_payload["metadata"] == {"project_note": "test"}
    assert second_payload["extensions"] == {"future_workspace_field": 42}


# ====================================================================== #
# Atomicity (spec §29.3.1 "must not partially apply state on failure")
# ====================================================================== #


@pytest.mark.unit
def test_from_dict_failure_leaves_model_unchanged(
    model: WorkspaceModel,
) -> None:
    """A parse failure mid-load must not touch the model state."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    pre_components = dict(model.components)

    # Build a payload where the first component is valid but the
    # second is malformed (missing `id`). Atomicity rule says
    # neither lands.
    bad_payload = {
        "components": [
            model.components[cid].to_dict(),
            {"definition_id": "x", "no_id_field": True},  # malformed
        ],
        "connections": [],
        "metadata": {},
        "extensions": {},
    }
    with pytest.raises(KeyError):
        model.from_dict(bad_payload)

    # Model should be untouched — the pre-existing component is
    # still there.
    assert set(model.components.keys()) == set(pre_components.keys())
    assert model.components[cid] == pre_components[cid]


# ====================================================================== #
# `loaded` signal + command stack subscription
# ====================================================================== #


@pytest.mark.unit
def test_loaded_signal_fires_once_on_successful_load(model: WorkspaceModel) -> None:
    """`loaded` emits exactly once at the end of `from_dict`."""
    received: list[None] = []
    model.loaded.connect(lambda: received.append(None))
    model.from_dict({"components": [], "connections": []})
    assert len(received) == 1


@pytest.mark.unit
def test_loaded_signal_does_not_fire_on_parse_failure(model: WorkspaceModel) -> None:
    """`loaded` is silent when the load aborts before the apply phase."""
    received: list[None] = []
    model.loaded.connect(lambda: received.append(None))
    with pytest.raises(KeyError):
        model.from_dict({"components": [{"missing": "id"}], "connections": []})
    assert received == []


@pytest.mark.unit
def test_command_stack_clears_on_load(model: WorkspaceModel) -> None:
    """`WorkspaceCommandStack` listens to `loaded` and clears the QUndoStack.

    Spec/02 §29.3.1: "must clear undo stack and reset dirty state
    to `false` after successful load". This binding happens
    automatically at stack construction; no shell wiring needed.
    """
    from features.SystemModelingModule.commands import AddComponentCommand

    stack = WorkspaceCommandStack(model)
    # Push a command through the stack so history exists.
    stack.push(AddComponentCommand(model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0)))
    assert stack.count() == 1
    assert model.is_dirty is True

    # Load a fresh empty payload.
    model.from_dict({"components": [], "connections": []})

    # Stack cleared by the `loaded` signal binding; dirty cleared
    # by both `reset()` and the stack's cleanChanged binding.
    assert stack.count() == 0
    assert model.is_dirty is False


# ====================================================================== #
# ID counter rebuild
# ====================================================================== #


@pytest.mark.unit
def test_display_id_counters_continue_after_load(
    model: WorkspaceModel, registry: ComponentRegistry
) -> None:
    """After load, new components get display ids beyond the loaded max.

    Spec/02 §8.3 + §8.8: counters reconstruct from loaded
    entities. A loaded resistor with `display_id="resistor_3"`
    must make the next add land at `resistor_4` (not collide
    with 3, not fall back to 1).
    """
    # Pre-populate to drive resistor counter to 3.
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    payload = model.to_dict()
    display_ids = sorted(c["display_id"] for c in payload["components"])
    assert display_ids == ["resistor_1", "resistor_2", "resistor_3"]

    # Fresh model, load, then add — should land at resistor_4.
    fresh = WorkspaceModel(registry=registry)
    fresh.from_dict(payload)
    fresh.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    all_display_ids = sorted(c.display_id for c in fresh.components.values())
    assert all_display_ids == [
        "resistor_1",
        "resistor_2",
        "resistor_3",
        "resistor_4",
    ]


# ====================================================================== #
# modelReset emission on load
# ====================================================================== #


@pytest.mark.unit
def test_model_reset_fires_during_load(model: WorkspaceModel) -> None:
    """`from_dict` emits `modelReset` so subscribers refetch state.

    spec §29.3.1 expects subscribers to react to the load via a
    blanket "everything changed" signal rather than N per-entity
    signals. `reset()` is called inside `from_dict`; `modelReset`
    is its public signal.
    """
    received: list[None] = []
    model.modelReset.connect(lambda: received.append(None))
    model.from_dict({"components": [], "connections": []})
    assert len(received) == 1
