"""Unit tests for `PasteSelectionCommand` (S1.7.5).

Covers the compound multi-entity paste command:

* New ULIDs on first redo (blank-slate semantics): pasted
  components do NOT preserve the captured `cmp_<ULID>`; they
  receive fresh ids from the workspace id-generator.
* User-editable state preserved: position, custom_label,
  rotation, parameters, tags, annotations.
* Connection endpoints remapped via the in-flight old→new
  id-map; half-orphan connections (one endpoint outside the
  source-set) are silently skipped, with the count exposed
  via `skipped_connection_count`.
* Identity-stable across undo→redo cycles: subsequent redos
  use `restore_component` / `restore_connection` so the
  minted ids survive.
* Atomicity: redo and undo emit exactly one `modelChanged`
  each, carrying the cumulative diff.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `specs/07_implementation_order.md` §7.12 ("paste compound
  command undo/redo")
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    PasteSelectionCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    GROUND_ELECTRIC_DEFINITION,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """`WorkspaceCommandStack` bound to the model."""
    return WorkspaceCommandStack(model)


@pytest.fixture
def source_topology(
    model: WorkspaceModel,
) -> tuple[list, list]:
    """A 3-component, 2-connection topology to use as a paste source.

    Two resistors and a ground, with one connection from each
    resistor's `p` port to the ground's `p` port. Returns
    `(captured_components, captured_connections)` snapshots —
    these are then handed to `PasteSelectionCommand` like the
    output of a copy buffer would be.
    """
    r1_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    r2_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(100.0, 0.0))
    g_id = model.add_component_from_definition(GROUND_ELECTRIC_DEFINITION.id, QPointF(50.0, 50.0))
    c1_id = model.add_connection(
        source=PortRef(component_id=r1_id, port_id="n"),
        target=PortRef(component_id=g_id, port_id="p"),
    )
    c2_id = model.add_connection(
        source=PortRef(component_id=r2_id, port_id="n"),
        target=PortRef(component_id=g_id, port_id="p"),
    )
    captured_components = [
        model.components[r1_id],
        model.components[r2_id],
        model.components[g_id],
    ]
    captured_connections = [model.connections[c1_id], model.connections[c2_id]]
    return captured_components, captured_connections


# ---------------------------------------------------------------------- #
# Construction
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_construct_requires_registry_wired_model() -> None:
    """Pre-validation: no-registry model → `RuntimeError`."""
    no_registry_model = WorkspaceModel()

    with pytest.raises(RuntimeError, match=r"registry-wired"):
        PasteSelectionCommand(no_registry_model, [], [])


@pytest.mark.unit
def test_construct_does_not_mutate_model(
    model: WorkspaceModel,
    source_topology: tuple[list, list],
) -> None:
    """Constructing the command does not insert anything."""
    captured_components, captured_connections = source_topology
    pre_components = len(model.components)
    pre_connections = len(model.connections)

    PasteSelectionCommand(model, captured_components, captured_connections)

    assert len(model.components) == pre_components
    assert len(model.connections) == pre_connections


@pytest.mark.unit
def test_construct_filters_half_orphan_connections(
    model: WorkspaceModel,
    source_topology: tuple[list, list],
) -> None:
    """Connections with an endpoint outside the source-set are silently skipped.

    Here we hand the command only one of the two resistors in
    the source-set — both connections become half-orphan (they
    reference a component not in the paste set) and should drop.
    """
    captured_components, captured_connections = source_topology
    # Only paste the first resistor — both connections reference
    # the ground (not pasted) so they should be filtered out.
    command = PasteSelectionCommand(
        model,
        [captured_components[0]],  # only r1
        captured_connections,
    )

    assert command.skipped_connection_count == 2


# ---------------------------------------------------------------------- #
# First redo — blank-slate semantics
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_first_redo_mints_new_component_ulids(
    stack: WorkspaceCommandStack,
    source_topology: tuple[list, list],
) -> None:
    """Pasted components receive fresh `cmp_<ULID>` ids — not the captured ones."""
    captured_components, captured_connections = source_topology
    captured_ids = {c.id for c in captured_components}

    command = PasteSelectionCommand(stack.model, captured_components, captured_connections)
    stack.push(command)

    new_ids = set(command.new_component_ids)
    assert len(new_ids) == len(captured_components)
    assert new_ids.isdisjoint(captured_ids)
    for new_id in new_ids:
        assert new_id.startswith("cmp_")


@pytest.mark.unit
def test_first_redo_preserves_user_editable_component_fields(
    stack: WorkspaceCommandStack,
    model: WorkspaceModel,
) -> None:
    """Pasted components carry position, label, rotation, parameters from the source."""
    src_id = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(75.0, 125.0),
        custom_label="R_paste_source",
        rotation=90.0,
        parameters={"resistance": 4700.0},
    )
    captured = model.components[src_id]

    command = PasteSelectionCommand(stack.model, [captured], [])
    stack.push(command)

    new_id = command.new_component_ids[0]
    pasted = stack.model.components[new_id]
    assert pasted.position == (75.0, 125.0)
    assert pasted.custom_label == "R_paste_source"
    assert pasted.rotation == 90.0
    assert pasted.parameters == {"resistance": 4700.0}
    # ID and timestamps are freshly minted, not copied.
    assert pasted.id != captured.id


@pytest.mark.unit
def test_first_redo_remaps_connection_endpoints(
    stack: WorkspaceCommandStack,
    source_topology: tuple[list, list],
) -> None:
    """Pasted connections reference the new (remapped) component ids, not the old ones."""
    captured_components, captured_connections = source_topology

    command = PasteSelectionCommand(stack.model, captured_components, captured_connections)
    stack.push(command)

    new_component_ids = set(command.new_component_ids)
    for new_conn_id in command.new_connection_ids:
        conn = stack.model.connections[new_conn_id]
        # Both endpoints must reference NEW component ids, not
        # the captured (old) ones.
        assert conn.source.component_id in new_component_ids
        assert conn.target.component_id in new_component_ids


# ---------------------------------------------------------------------- #
# Undo / redo round-trip
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_undo_removes_all_pasted_entities(
    stack: WorkspaceCommandStack,
    source_topology: tuple[list, list],
) -> None:
    """`undo` cleans up every component and connection added by the redo."""
    captured_components, captured_connections = source_topology
    pre_component_count = len(stack.model.components)
    pre_connection_count = len(stack.model.connections)
    command = PasteSelectionCommand(stack.model, captured_components, captured_connections)
    stack.push(command)

    stack.undo()

    assert len(stack.model.components) == pre_component_count
    assert len(stack.model.connections) == pre_connection_count


@pytest.mark.unit
def test_redo_after_undo_restores_same_ulids(
    stack: WorkspaceCommandStack,
    source_topology: tuple[list, list],
) -> None:
    """Subsequent redo replays the previously-minted ids verbatim.

    Identity stability across cycles: undo→redo must not mint
    fresh ids each time, otherwise downstream references would
    break. The captured-state replay path (`restore_component`
    / `restore_connection`) handles this.
    """
    captured_components, captured_connections = source_topology
    command = PasteSelectionCommand(stack.model, captured_components, captured_connections)
    stack.push(command)
    first_redo_ids = command.new_component_ids
    first_redo_conn_ids = command.new_connection_ids

    stack.undo()
    stack.redo()

    assert command.new_component_ids == first_redo_ids
    assert command.new_connection_ids == first_redo_conn_ids
    for cid in first_redo_ids:
        assert cid in stack.model.components
    for conn_id in first_redo_conn_ids:
        assert conn_id in stack.model.connections


# ---------------------------------------------------------------------- #
# Atomicity (single modelChanged per direction)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_redo_emits_single_model_changed_with_full_diff(
    stack: WorkspaceCommandStack,
    source_topology: tuple[list, list],
) -> None:
    """`push` fires exactly one `modelChanged` per direction.

    The batch coalescing ensures UI re-renders the pasted
    entities in one pass rather than firing N+M fine-grained
    componentAdded / connectionAdded signals.
    """
    captured_components, captured_connections = source_topology
    fine_components: list[str] = []
    fine_connections: list[str] = []
    change_sets: list[object] = []
    stack.model.componentAdded.connect(fine_components.append)
    stack.model.connectionAdded.connect(fine_connections.append)
    stack.model.modelChanged.connect(change_sets.append)

    command = PasteSelectionCommand(stack.model, captured_components, captured_connections)
    stack.push(command)

    assert fine_components == []  # suppressed inside batch
    assert fine_connections == []
    assert len(change_sets) == 1
    cs = change_sets[0]
    assert len(cs.added_components) == 3  # type: ignore[attr-defined]
    assert len(cs.added_connections) == 2  # type: ignore[attr-defined]
