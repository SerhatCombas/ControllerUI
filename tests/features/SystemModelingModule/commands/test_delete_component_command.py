"""Unit tests for `DeleteComponentCommand` (S1.7.3).

Covers the component-deletion-with-cascade command introduced in
S1.7.3. The command captures the full target `ComponentInstance`
plus all `Connection` records referencing it, then in `redo()`
removes both atomically inside a `model.batch()`; `undo()` re-
inserts them inside another batch, preserving all `cmp_<ULID>` /
`con_<ULID>` ids per ADR-002.

Specifically:

* `__init__` pre-validates the component exists.
* The cascade set is captured at construction time (so undo can
  replay even after subsequent unrelated mutations).
* `redo()` removes both layers; `undo()` restores them; subsequent
  `redo()` re-deletes — all id-stable.
* The atomic batch emits exactly one `modelChanged` per direction
  carrying the full cascade in its diff lists.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `specs/02_workspace_requirements.md` §8, §14, §25
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.commands import (
    DeleteComponentCommand,
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
    """Registry-wired model for the delete-with-cascade tests."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """`WorkspaceCommandStack` bound to the model."""
    return WorkspaceCommandStack(model)


@pytest.fixture
def isolated_resistor(model: WorkspaceModel) -> str:
    """A resistor with no connections attached."""
    return model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))


@pytest.fixture
def wired_topology(model: WorkspaceModel) -> tuple[str, str, str, str]:
    """A small topology: resistor with two connections to two grounds.

    Returns `(resistor_id, ground_a_id, ground_b_id, conn_ids)` —
    the resistor sits at the center; both its ports `p` / `n`
    connect to two ground references. Deleting the resistor must
    cascade-remove both connections.
    """
    resistor_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    ground_a_id = model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(-100.0, 0.0)
    )
    ground_b_id = model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0)
    )
    conn_a_id = model.add_connection(
        source=PortRef(component_id=resistor_id, port_id="p"),
        target=PortRef(component_id=ground_a_id, port_id="p"),
    )
    conn_b_id = model.add_connection(
        source=PortRef(component_id=resistor_id, port_id="n"),
        target=PortRef(component_id=ground_b_id, port_id="p"),
    )
    return resistor_id, ground_a_id, ground_b_id, f"{conn_a_id}|{conn_b_id}"


# ---------------------------------------------------------------------- #
# Construction + capture
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_construct_raises_keyerror_for_unknown_component(
    model: WorkspaceModel,
) -> None:
    """Pre-validation: missing component → `KeyError`."""
    with pytest.raises(KeyError):
        DeleteComponentCommand(model, "cmp_nonexistent")


@pytest.mark.unit
def test_construct_captures_zero_connections_when_isolated(
    model: WorkspaceModel,
    isolated_resistor: str,
) -> None:
    """An isolated component has an empty cascade set."""
    command = DeleteComponentCommand(model, isolated_resistor)

    assert command.cascaded_connections == ()


@pytest.mark.unit
def test_construct_captures_all_referencing_connections(
    model: WorkspaceModel,
    wired_topology: tuple[str, str, str, str],
) -> None:
    """All connections touching either endpoint are captured."""
    resistor_id, _, _, conn_ids_packed = wired_topology
    conn_a_id, conn_b_id = conn_ids_packed.split("|")

    command = DeleteComponentCommand(model, resistor_id)

    captured_ids = {c.id for c in command.cascaded_connections}
    assert captured_ids == {conn_a_id, conn_b_id}


@pytest.mark.unit
def test_construct_does_not_mutate_model(
    model: WorkspaceModel,
    wired_topology: tuple[str, str, str, str],
) -> None:
    """Constructing the command does not delete anything."""
    resistor_id, _, _, _ = wired_topology

    DeleteComponentCommand(model, resistor_id)

    assert resistor_id in model.components
    assert len(model.connections) == 2


# ---------------------------------------------------------------------- #
# Redo / undo / redo cycle
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_push_removes_component_and_all_cascaded_connections(
    stack: WorkspaceCommandStack,
    wired_topology: tuple[str, str, str, str],
) -> None:
    """`stack.push` cascade-removes both layers atomically."""
    resistor_id, _, _, _ = wired_topology

    stack.push(DeleteComponentCommand(stack.model, resistor_id))

    assert resistor_id not in stack.model.components
    assert len(stack.model.connections) == 0


@pytest.mark.unit
def test_undo_restores_component_with_same_id(
    stack: WorkspaceCommandStack,
    wired_topology: tuple[str, str, str, str],
) -> None:
    """`stack.undo` reinserts the component with its original id."""
    resistor_id, _, _, _ = wired_topology
    pre_instance = stack.model.components[resistor_id]
    stack.push(DeleteComponentCommand(stack.model, resistor_id))

    stack.undo()

    assert resistor_id in stack.model.components
    assert stack.model.components[resistor_id] == pre_instance


@pytest.mark.unit
def test_undo_restores_all_cascaded_connections_with_original_ids(
    stack: WorkspaceCommandStack,
    wired_topology: tuple[str, str, str, str],
) -> None:
    """`stack.undo` reinserts each cascaded connection verbatim.

    Identity stability for connections matters because validation
    reports, future graph caches, and project files index by
    `con_<ULID>`. Restoring with the same id keeps those
    references live across delete/undo cycles.
    """
    resistor_id, _, _, conn_ids_packed = wired_topology
    expected_conn_ids = set(conn_ids_packed.split("|"))
    pre_connections = {cid: stack.model.connections[cid] for cid in expected_conn_ids}
    stack.push(DeleteComponentCommand(stack.model, resistor_id))

    stack.undo()

    assert set(stack.model.connections) == expected_conn_ids
    for cid, pre in pre_connections.items():
        assert stack.model.connections[cid] == pre


@pytest.mark.unit
def test_redo_after_undo_re_deletes_cascade(
    stack: WorkspaceCommandStack,
    wired_topology: tuple[str, str, str, str],
) -> None:
    """Redo cycles the cascade back to deleted state."""
    resistor_id, _, _, _ = wired_topology
    stack.push(DeleteComponentCommand(stack.model, resistor_id))
    stack.undo()

    stack.redo()

    assert resistor_id not in stack.model.components
    assert len(stack.model.connections) == 0


# ---------------------------------------------------------------------- #
# Batch coalescing (ADR-019 atomicity)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_redo_emits_single_model_changed_with_cascade(
    stack: WorkspaceCommandStack,
    wired_topology: tuple[str, str, str, str],
) -> None:
    """`redo` fires exactly one `modelChanged` carrying the full cascade.

    Per ADR-019, the per-mutation `componentRemoved` /
    `connectionRemoved` signals are suppressed inside the batch
    and subscribers see one coalesced `modelChanged(change_set)`
    instead.
    """
    resistor_id, _, _, conn_ids_packed = wired_topology
    expected_conn_ids = set(conn_ids_packed.split("|"))
    fine_grained_component: list[str] = []
    fine_grained_connection: list[str] = []
    change_sets: list[object] = []
    stack.model.componentRemoved.connect(fine_grained_component.append)
    stack.model.connectionRemoved.connect(fine_grained_connection.append)
    stack.model.modelChanged.connect(change_sets.append)

    stack.push(DeleteComponentCommand(stack.model, resistor_id))

    assert fine_grained_component == []
    assert fine_grained_connection == []
    assert len(change_sets) == 1
    cs = change_sets[0]
    assert cs.removed_components == (resistor_id,)  # type: ignore[attr-defined]
    assert set(cs.removed_connections) == expected_conn_ids  # type: ignore[attr-defined]


@pytest.mark.unit
def test_undo_emits_single_model_changed_with_restored_items(
    stack: WorkspaceCommandStack,
    wired_topology: tuple[str, str, str, str],
) -> None:
    """`undo` likewise emits one `modelChanged` with `added_*` lists."""
    resistor_id, _, _, conn_ids_packed = wired_topology
    expected_conn_ids = set(conn_ids_packed.split("|"))
    stack.push(DeleteComponentCommand(stack.model, resistor_id))
    change_sets: list[object] = []
    stack.model.modelChanged.connect(change_sets.append)

    stack.undo()

    assert len(change_sets) == 1
    cs = change_sets[0]
    assert cs.added_components == (resistor_id,)  # type: ignore[attr-defined]
    assert set(cs.added_connections) == expected_conn_ids  # type: ignore[attr-defined]
