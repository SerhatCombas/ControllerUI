"""Unit tests for `WorkspaceModel.restore_connection` and
`WorkspaceModel.connections_for_component` (S1.7.3).

Both methods are introduced in S1.7.3 to support
`DeleteComponentCommand`'s cascade-and-undo loop, but their
contracts stand independent of any specific command — they live
on the model and may serve future validators, project export, or
other commands.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §8, §14
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

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
def two_components_with_connection(
    model: WorkspaceModel,
) -> tuple[str, str, str]:
    """A resistor + ground connected by one connection.

    Returns `(resistor_id, ground_id, conn_id)`.
    """
    resistor_id = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    ground_id = model.add_component_from_definition(
        GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0)
    )
    conn_id = model.add_connection(
        source=PortRef(component_id=resistor_id, port_id="p"),
        target=PortRef(component_id=ground_id, port_id="p"),
    )
    return resistor_id, ground_id, conn_id


# ---------------------------------------------------------------------- #
# connections_for_component
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_connections_for_component_returns_empty_for_isolated_component(
    model: WorkspaceModel,
) -> None:
    """A component with no connections yields an empty tuple."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert model.connections_for_component(cid) == ()


@pytest.mark.unit
def test_connections_for_component_finds_source_endpoint(
    model: WorkspaceModel,
    two_components_with_connection: tuple[str, str, str],
) -> None:
    """A component referenced on the source endpoint is found."""
    resistor_id, _, conn_id = two_components_with_connection

    result = model.connections_for_component(resistor_id)

    assert len(result) == 1
    assert result[0].id == conn_id


@pytest.mark.unit
def test_connections_for_component_finds_target_endpoint(
    model: WorkspaceModel,
    two_components_with_connection: tuple[str, str, str],
) -> None:
    """A component referenced on the target endpoint is also found."""
    _, ground_id, conn_id = two_components_with_connection

    result = model.connections_for_component(ground_id)

    assert len(result) == 1
    assert result[0].id == conn_id


@pytest.mark.unit
def test_connections_for_component_unknown_id_returns_empty(
    model: WorkspaceModel,
) -> None:
    """Unknown component_id yields an empty tuple (no exception)."""
    assert model.connections_for_component("cmp_nonexistent") == ()


# ---------------------------------------------------------------------- #
# restore_connection
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_restore_connection_reinserts_with_original_id(
    model: WorkspaceModel,
    two_components_with_connection: tuple[str, str, str],
) -> None:
    """Round-trip add → remove → restore yields the same connection."""
    _, _, conn_id = two_components_with_connection
    captured = model.connections[conn_id]
    model.remove_connection(conn_id)
    assert conn_id not in model.connections

    model.restore_connection(captured)

    assert conn_id in model.connections
    assert model.connections[conn_id] == captured


@pytest.mark.unit
def test_restore_connection_raises_on_id_collision(
    model: WorkspaceModel,
    two_components_with_connection: tuple[str, str, str],
) -> None:
    """Re-inserting on top of an existing id raises `ValueError`."""
    _, _, conn_id = two_components_with_connection
    captured = model.connections[conn_id]

    with pytest.raises(ValueError, match=r"id collision"):
        model.restore_connection(captured)


@pytest.mark.unit
def test_restore_connection_emits_connection_added(
    model: WorkspaceModel,
    two_components_with_connection: tuple[str, str, str],
) -> None:
    """`restore_connection` fires the same `connectionAdded` signal as
    a fresh `add_connection`."""
    _, _, conn_id = two_components_with_connection
    captured = model.connections[conn_id]
    model.remove_connection(conn_id)
    received: list[str] = []
    model.connectionAdded.connect(received.append)

    model.restore_connection(captured)

    assert received == [conn_id]


@pytest.mark.unit
def test_restore_connection_drives_dirty_transition(
    model: WorkspaceModel,
    two_components_with_connection: tuple[str, str, str],
) -> None:
    """`restore_connection` follows ADR-020 transition-only dirty tracking."""
    _, _, conn_id = two_components_with_connection
    captured = model.connections[conn_id]
    model.remove_connection(conn_id)
    model._clear_dirty()
    dirty_emits: list[bool] = []
    model.dirtyChanged.connect(dirty_emits.append)

    model.restore_connection(captured)

    assert dirty_emits == [True]
    assert model.is_dirty is True
