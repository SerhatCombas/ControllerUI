"""Unit tests for `WorkspaceModel` event emission (S1.8b).

Verifies that every state-affecting public method on
`WorkspaceModel` emits an INFO log with `extra["event"]`
matching the canonical constants in
`shared.utils.logging_events`, per `specs/10_logging_conventions.md`
§10.1.

Tests use pytest's `caplog` fixture to capture log records and
inspect their `extra` payload. No-op early returns (e.g.,
`move_component` to the same position) must NOT emit an event;
those negative checks live alongside the positive ones to lock
the contract.

References:
----------
* `specs/10_logging_conventions.md` §8, §10.1
* `specs/07_implementation_order.md` §7.x
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)
from shared.utils import logging_events as events

# Logger name used by the model module — the same path the
# model's `logger = logging.getLogger(__name__)` resolves to.
_MODEL_LOGGER = "features.SystemModelingModule.model.workspace_model"


def _record_for_event(records: list[logging.LogRecord], event_name: str) -> logging.LogRecord:
    """Find the (single) log record carrying `extra={"event": event_name}`.

    Raises `AssertionError` when not found exactly once.
    """
    matches = [r for r in records if getattr(r, "event", None) == event_name]
    assert len(matches) == 1, (
        f"expected exactly one log record with event={event_name!r}, "
        f"got {len(matches)}; all events: {[getattr(r, 'event', None) for r in records]}"
    )
    return matches[0]


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


# ---------------------------------------------------------------------- #
# Component lifecycle
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_add_component_from_definition_emits_component_added(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`add_component_from_definition` emits `workspace.component_added`."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    record = _record_for_event(caplog.records, events.WORKSPACE_COMPONENT_ADDED)
    assert record.component_id == cid  # type: ignore[attr-defined]
    assert record.definition_id == RESISTOR_DEFINITION.id  # type: ignore[attr-defined]


@pytest.mark.unit
def test_remove_component_emits_component_removed(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`remove_component` emits `workspace.component_removed`."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.remove_component(cid)

    record = _record_for_event(caplog.records, events.WORKSPACE_COMPONENT_REMOVED)
    assert record.component_id == cid  # type: ignore[attr-defined]


@pytest.mark.unit
def test_restore_component_emits_component_added(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`restore_component` emits the same `workspace.component_added` event."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    instance = model.components[cid]
    model.remove_component(cid)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.restore_component(instance)

    record = _record_for_event(caplog.records, events.WORKSPACE_COMPONENT_ADDED)
    assert record.component_id == cid  # type: ignore[attr-defined]


# ---------------------------------------------------------------------- #
# Move / Rotate
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_move_component_emits_component_moved(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`move_component` emits `workspace.component_moved` with new coords."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.move_component(cid, QPointF(120.0, 80.0))

    record = _record_for_event(caplog.records, events.WORKSPACE_COMPONENT_MOVED)
    assert record.new_x == 120.0  # type: ignore[attr-defined]
    assert record.new_y == 80.0  # type: ignore[attr-defined]


@pytest.mark.unit
def test_move_component_noop_emits_nothing(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Moving to the current position is a no-op → no event log."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.move_component(cid, QPointF(0.0, 0.0))

    matches = [
        r for r in caplog.records if getattr(r, "event", None) == events.WORKSPACE_COMPONENT_MOVED
    ]
    assert matches == []


@pytest.mark.unit
def test_rotate_component_emits_component_rotated(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`rotate_component` emits `workspace.component_rotated` with new angle."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.rotate_component(cid, 90.0)

    record = _record_for_event(caplog.records, events.WORKSPACE_COMPONENT_ROTATED)
    assert record.new_rotation == 90.0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------- #
# Parameter edits
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_parameter_emits_parameter_changed(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`set_parameter` emits `workspace.parameter_changed`."""
    cid = model.add_component_from_definition(
        RESISTOR_DEFINITION.id, QPointF(0.0, 0.0), parameters={"resistance": 1000.0}
    )
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.set_parameter(cid, "resistance", 2200.0)

    record = _record_for_event(caplog.records, events.WORKSPACE_PARAMETER_CHANGED)
    assert record.param_name == "resistance"  # type: ignore[attr-defined]


@pytest.mark.unit
def test_set_parameter_noop_emits_nothing(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Setting a parameter to its existing value is a no-op → no event log."""
    cid = model.add_component_from_definition(
        RESISTOR_DEFINITION.id, QPointF(0.0, 0.0), parameters={"resistance": 1000.0}
    )
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.set_parameter(cid, "resistance", 1000.0)

    matches = [
        r for r in caplog.records if getattr(r, "event", None) == events.WORKSPACE_PARAMETER_CHANGED
    ]
    assert matches == []


@pytest.mark.unit
def test_unset_parameter_emits_parameter_changed(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`unset_parameter` emits `workspace.parameter_changed`."""
    cid = model.add_component_from_definition(
        RESISTOR_DEFINITION.id, QPointF(0.0, 0.0), parameters={"resistance": 1000.0}
    )
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.unset_parameter(cid, "resistance")

    record = _record_for_event(caplog.records, events.WORKSPACE_PARAMETER_CHANGED)
    assert record.param_name == "resistance"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------- #
# componentChanged catch-all (set_custom_label / set_locked / set_tags / set_annotations)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_custom_label_emits_component_changed(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`set_custom_label` emits `workspace.component_changed` with field tag."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.set_custom_label(cid, "R_load")

    record = _record_for_event(caplog.records, events.WORKSPACE_COMPONENT_CHANGED)
    assert record.field == "custom_label"  # type: ignore[attr-defined]


@pytest.mark.unit
def test_set_locked_emits_component_changed(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`set_locked` emits `workspace.component_changed` with the new value."""
    cid = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.set_locked(cid, True)

    record = _record_for_event(caplog.records, events.WORKSPACE_COMPONENT_CHANGED)
    assert record.field == "locked"  # type: ignore[attr-defined]
    assert record.locked is True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------- #
# Connection lifecycle
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_add_connection_emits_connection_added(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`add_connection` emits `workspace.connection_added` with endpoints."""
    cid_a = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(60.0, 0.0))
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        conn_id = model.add_connection(
            source=PortRef(component_id=cid_a, port_id="p"),
            target=PortRef(component_id=cid_b, port_id="n"),
        )

    record = _record_for_event(caplog.records, events.WORKSPACE_CONNECTION_ADDED)
    assert record.connection_id == conn_id  # type: ignore[attr-defined]
    assert record.source_component_id == cid_a  # type: ignore[attr-defined]
    assert record.target_component_id == cid_b  # type: ignore[attr-defined]


@pytest.mark.unit
def test_remove_connection_emits_connection_removed(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`remove_connection` emits `workspace.connection_removed`."""
    cid_a = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(60.0, 0.0))
    conn_id = model.add_connection(
        source=PortRef(component_id=cid_a, port_id="p"),
        target=PortRef(component_id=cid_b, port_id="n"),
    )
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.remove_connection(conn_id)

    record = _record_for_event(caplog.records, events.WORKSPACE_CONNECTION_REMOVED)
    assert record.connection_id == conn_id  # type: ignore[attr-defined]


@pytest.mark.unit
def test_update_connection_emits_connection_modified(
    model: WorkspaceModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`update_connection` emits `workspace.connection_modified`."""
    cid_a = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(60.0, 0.0))
    conn_id = model.add_connection(
        source=PortRef(component_id=cid_a, port_id="p"),
        target=PortRef(component_id=cid_b, port_id="n"),
    )
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_MODEL_LOGGER):
        model.update_connection(conn_id, label="updated")

    record = _record_for_event(caplog.records, events.WORKSPACE_CONNECTION_MODIFIED)
    assert record.connection_id == conn_id  # type: ignore[attr-defined]


# ---------------------------------------------------------------------- #
# Architecture-test compatibility (the event constants are in use)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_all_workspace_events_now_in_use() -> None:
    """Every Phase-1 workspace event constant is referenced from the model.

    Smoke test that S1.8b actually wired all 8 workspace mutation
    paths to event emission. Reads the source file directly and
    counts references to each constant.
    """
    from pathlib import Path

    source = Path("src/features/SystemModelingModule/model/workspace_model.py").read_text(
        encoding="utf-8"
    )

    referenced_events = [
        events.WORKSPACE_COMPONENT_ADDED,
        events.WORKSPACE_COMPONENT_REMOVED,
        events.WORKSPACE_COMPONENT_MOVED,
        events.WORKSPACE_COMPONENT_ROTATED,
        events.WORKSPACE_COMPONENT_CHANGED,
        events.WORKSPACE_PARAMETER_CHANGED,
        events.WORKSPACE_CONNECTION_ADDED,
        events.WORKSPACE_CONNECTION_REMOVED,
        events.WORKSPACE_CONNECTION_MODIFIED,
    ]
    # Source references through `events.<NAME>` attribute access.
    for event_name in referenced_events:
        # Convert "workspace.component_added" → "WORKSPACE_COMPONENT_ADDED"
        constant_name = event_name.replace(".", "_").upper()
        assert constant_name in source, (
            f"event constant {constant_name} ({event_name}) not referenced "
            "in workspace_model.py — S1.8b wiring missed it"
        )
