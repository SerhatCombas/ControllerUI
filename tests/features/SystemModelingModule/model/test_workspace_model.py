"""Unit tests for `WorkspaceModel` (S1.3a + S1.3b + S1.3c.1).

Covers (cumulative):

* S1.3a — constructor produces an empty, clean model; `is_dirty`
  initial state is False per ADR-020 §"Initial state"; `components`
  and `connections` views are read-only `MappingProxyType`; internal
  builders mint frozen-dataclass instances without inserting into the
  internal stores.
* S1.3c.1 — the 12 fine-grained signals from ADR-018 are defined on
  the model and connectable; `add_component`, `remove_component`, and
  `move_component` mutate state, emit the correct fine-grained signal,
  and drive transition-only `dirtyChanged` emission. ε=1e-6 no-op
  suppression per ADR-020 is enforced on `move_component`. Missing
  identifiers raise `KeyError`.

Public mutation API for rotation, connections, parameters, and
property setters lands in S1.3c.2 and is not tested here. Batch mode
(S1.3d) and `reset()` (S1.3e) are also out of scope.

References
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §3 (Source of Truth), §4 (Signals),
  §22 (Move/Delete)
"""

from __future__ import annotations

import re
import time
from types import MappingProxyType
from typing import Any

import pytest
from PySide6.QtCore import QObject, QPointF

from features.SystemModelingModule.model.component_instance import (
    ComponentInstance,
    PhysicalAttributes,
    VisualSpec,
)
from features.SystemModelingModule.model.connection import (
    Connection,
    ConnectionRouting,
    PortRef,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel

# ULIDs are 26 base32 characters; the body must match this pattern after the
# `cmp_` / `con_` prefix is stripped. Mirrors the regex in
# `tests/features/SystemModelingModule/model/test_id_generator.py`.
_ULID_BODY_RE = re.compile(r"^[0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{26}$")

# An ISO-8601 timestamp with microsecond precision and an explicit `+00:00`
# UTC offset (Python's `datetime.now(UTC).isoformat(...)` form).
_ISO_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$")


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _build_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return a default `_build_component_instance` kwargs payload.

    Tests pass overrides to vary one field at a time without
    repeating the full argument set. The defaults describe a generic
    resistor at the origin (tuple position, internal builder form).
    """
    base: dict[str, Any] = {
        "definition_id": "electrical.analog.components.resistor",
        "type": "Resistor",
        "display_name": "Resistor",
        "domain": "electrical_analog",
        "category": "component",
        "position": (0.0, 0.0),
        "visual": VisualSpec(svg_id="resistor_default"),
        "physical_attributes": PhysicalAttributes(),
    }
    base.update(overrides)
    return base


def _add_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return a default `add_component` kwargs payload.

    Differs from `_build_kwargs` by using `QPointF` for `position`,
    matching the public mutation API (the internal builder takes a
    tuple; the public method takes `QPointF` per ADR-018 signal
    payload alignment).
    """
    base: dict[str, Any] = {
        "definition_id": "electrical.analog.components.resistor",
        "type": "Resistor",
        "display_name": "Resistor",
        "domain": "electrical_analog",
        "category": "component",
        "position": QPointF(100.0, 200.0),
        "visual": VisualSpec(svg_id="resistor_default"),
        "physical_attributes": PhysicalAttributes(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------- #
# Constructor and views (S1.3a)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_constructor_creates_empty_clean_model() -> None:
    """A fresh `WorkspaceModel` has empty stores and `is_dirty=False`."""
    model = WorkspaceModel()

    assert isinstance(model, QObject)
    assert dict(model.components) == {}
    assert dict(model.connections) == {}
    assert model.is_dirty is False


@pytest.mark.unit
def test_components_view_is_mapping_proxy() -> None:
    """`components` returns a `MappingProxyType` (write attempts raise)."""
    model = WorkspaceModel()

    view = model.components

    assert isinstance(view, MappingProxyType)
    with pytest.raises(TypeError):
        view["cmp_should_fail"] = ...  # type: ignore[index]


@pytest.mark.unit
def test_connections_view_is_mapping_proxy() -> None:
    """`connections` returns a `MappingProxyType` (write attempts raise)."""
    model = WorkspaceModel()

    view = model.connections

    assert isinstance(view, MappingProxyType)
    with pytest.raises(TypeError):
        view["con_should_fail"] = ...  # type: ignore[index]


# ---------------------------------------------------------------------- #
# `_build_component_instance` (S1.3a)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_build_component_instance_returns_fresh_instance() -> None:
    """Builder mints a `ComponentInstance` with generated identity."""
    model = WorkspaceModel()

    comp = model._build_component_instance(
        **_build_kwargs(position=(100.0, 200.0)),
    )

    assert isinstance(comp, ComponentInstance)
    assert comp.id.startswith("cmp_")
    assert _ULID_BODY_RE.match(comp.id.removeprefix("cmp_"))
    assert comp.display_id == "resistor_1"
    assert comp.position == (100.0, 200.0)
    assert _ISO_TIMESTAMP_RE.match(comp.created_at)
    assert comp.modified_at == comp.created_at


@pytest.mark.unit
def test_build_component_instance_does_not_insert() -> None:
    """Building does not mutate `_components`; only the public API does."""
    model = WorkspaceModel()

    comp = model._build_component_instance(**_build_kwargs())

    assert comp.id not in model.components
    assert dict(model.components) == {}


@pytest.mark.unit
def test_consecutive_component_builds_have_unique_ids_and_monotonic_display() -> None:
    """Two builds for the same type slug yield distinct `id` values and
    `resistor_1`, `resistor_2` display IDs in order."""
    model = WorkspaceModel()

    c1 = model._build_component_instance(**_build_kwargs())
    c2 = model._build_component_instance(**_build_kwargs())

    assert c1.id != c2.id
    assert (c1.display_id, c2.display_id) == ("resistor_1", "resistor_2")


@pytest.mark.unit
def test_component_builder_uses_definition_slug_for_display_counter() -> None:
    """Type slug is the last dotted segment of `definition_id`; counters
    are independent across slugs."""
    model = WorkspaceModel()

    resistor = model._build_component_instance(**_build_kwargs())
    capacitor = model._build_component_instance(
        **_build_kwargs(
            definition_id="electrical.analog.components.capacitor",
            type="Capacitor",
            display_name="Capacitor",
        ),
    )

    assert resistor.display_id == "resistor_1"
    assert capacitor.display_id == "capacitor_1"


@pytest.mark.unit
def test_component_builder_copies_mutable_mappings() -> None:
    """Caller-side mutations to `parameters` / `metadata` after build do
    not bleed into the built instance."""
    model = WorkspaceModel()
    params: dict[str, Any] = {"resistance": 1000.0}
    metadata: dict[str, Any] = {"note": "input"}

    comp = model._build_component_instance(
        **_build_kwargs(parameters=params, metadata=metadata),
    )

    params["resistance"] = 9999.0
    metadata["note"] = "tampered"

    assert comp.parameters == {"resistance": 1000.0}
    assert comp.metadata == {"note": "input"}


# ---------------------------------------------------------------------- #
# `_build_connection` (S1.3a)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_build_connection_returns_fresh_instance() -> None:
    """Builder mints a `Connection` with generated identity."""
    model = WorkspaceModel()

    conn = model._build_connection(
        source=PortRef(component_id="cmp_X", port_id="p"),
        target=PortRef(component_id="cmp_Y", port_id="p"),
    )

    assert isinstance(conn, Connection)
    assert conn.id.startswith("con_")
    assert _ULID_BODY_RE.match(conn.id.removeprefix("con_"))
    assert conn.display_id == "conn_1"
    assert conn.source.component_id == "cmp_X"
    assert conn.target.port_id == "p"
    assert isinstance(conn.routing, ConnectionRouting)
    assert conn.routing.style == "orthogonal"


@pytest.mark.unit
def test_build_connection_does_not_insert() -> None:
    """Building does not mutate `_connections`; only the public API does."""
    model = WorkspaceModel()

    conn = model._build_connection(
        source=PortRef(component_id="cmp_X", port_id="p"),
        target=PortRef(component_id="cmp_Y", port_id="p"),
    )

    assert conn.id not in model.connections
    assert dict(model.connections) == {}


@pytest.mark.unit
def test_consecutive_connection_builds_use_global_display_counter() -> None:
    """Connection display IDs share a single global sequence (not per type)."""
    model = WorkspaceModel()

    c1 = model._build_connection(
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_B", port_id="p"),
    )
    c2 = model._build_connection(
        source=PortRef(component_id="cmp_C", port_id="flange_a"),
        target=PortRef(component_id="cmp_D", port_id="flange_b"),
    )

    assert c1.id != c2.id
    assert (c1.display_id, c2.display_id) == ("conn_1", "conn_2")


@pytest.mark.unit
def test_connection_builder_copies_mutable_mappings() -> None:
    """Caller-side mutations to `style` / `metadata` after build do not
    bleed into the built instance."""
    model = WorkspaceModel()
    style: dict[str, Any] = {"color_override": "#ff0000"}
    metadata: dict[str, Any] = {"comment": "trunk"}

    conn = model._build_connection(
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_B", port_id="p"),
        style=style,
        metadata=metadata,
    )

    style["color_override"] = "#000000"
    metadata["comment"] = "tampered"

    assert conn.style == {"color_override": "#ff0000"}
    assert conn.metadata == {"comment": "trunk"}


# ---------------------------------------------------------------------- #
# Signal definitions (S1.3c.1)
# ---------------------------------------------------------------------- #


_EXPECTED_SIGNALS: tuple[str, ...] = (
    "componentAdded",
    "componentRemoved",
    "componentChanged",
    "componentMoved",
    "componentRotated",
    "connectionAdded",
    "connectionRemoved",
    "connectionChanged",
    "selectionChanged",
    "validationChanged",
    "modelReset",
    "dirtyChanged",
)


@pytest.mark.unit
def test_workspace_model_defines_all_12_fine_grained_signals() -> None:
    """ADR-018 §"Signal payload type table" lists 12 fine-grained signals;
    the model exposes each one as a connectable, emittable Qt signal."""
    model = WorkspaceModel()

    for name in _EXPECTED_SIGNALS:
        signal = getattr(model, name, None)
        assert signal is not None, f"missing signal: {name}"
        assert hasattr(signal, "emit"), f"{name} is not an emittable signal"
        assert hasattr(signal, "connect"), f"{name} is not connectable"


# ---------------------------------------------------------------------- #
# `add_component` (S1.3c.1)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_add_component_inserts_and_returns_id() -> None:
    """`add_component` returns the new `cmp_<ULID>` and inserts the instance."""
    model = WorkspaceModel()

    new_id = model.add_component(**_add_kwargs())

    assert isinstance(new_id, str)
    assert new_id.startswith("cmp_")
    assert _ULID_BODY_RE.match(new_id.removeprefix("cmp_"))
    assert new_id in model.components
    assert model.components[new_id].position == (100.0, 200.0)


@pytest.mark.unit
def test_add_component_emits_component_added_signal() -> None:
    """`componentAdded` fires with the new component_id."""
    model = WorkspaceModel()
    received: list[str] = []
    model.componentAdded.connect(received.append)

    new_id = model.add_component(**_add_kwargs())

    assert received == [new_id]


@pytest.mark.unit
def test_add_component_transitions_dirty_on_first_call() -> None:
    """First meaningful edit transitions dirty `False → True` and emits."""
    model = WorkspaceModel()
    dirty_emissions: list[bool] = []
    model.dirtyChanged.connect(dirty_emissions.append)

    assert model.is_dirty is False
    model.add_component(**_add_kwargs())

    assert model.is_dirty is True
    assert dirty_emissions == [True]


@pytest.mark.unit
def test_add_component_does_not_re_emit_dirty_when_already_dirty() -> None:
    """ADR-020 transition-only emission: subsequent edits do not re-emit."""
    model = WorkspaceModel()
    dirty_emissions: list[bool] = []
    model.dirtyChanged.connect(dirty_emissions.append)

    model.add_component(**_add_kwargs())
    model.add_component(**_add_kwargs())
    model.add_component(**_add_kwargs())

    assert dirty_emissions == [True]


# ---------------------------------------------------------------------- #
# `remove_component` (S1.3c.1)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_remove_component_deletes_from_components() -> None:
    """`remove_component` removes the entry from the internal store."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs())
    assert new_id in model.components

    model.remove_component(new_id)

    assert new_id not in model.components


@pytest.mark.unit
def test_remove_component_emits_component_removed_signal() -> None:
    """`componentRemoved` fires with the removed component_id."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs())
    received: list[str] = []
    model.componentRemoved.connect(received.append)

    model.remove_component(new_id)

    assert received == [new_id]


@pytest.mark.unit
def test_remove_component_raises_keyerror_for_unknown_id() -> None:
    """Unknown component_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.remove_component("cmp_nonexistent")

    assert "cmp_nonexistent" in str(exc_info.value)


@pytest.mark.unit
def test_remove_component_does_not_cascade_to_attached_connections() -> None:
    """Raw `remove_component` is low-level; cascade is the compound
    command's responsibility per ADR-005 (S1.7)."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    # Connect a→b directly via the internal builder + dict; the public
    # `add_connection` API is S1.3c.2 and intentionally not used here.
    conn = model._build_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    model._connections[conn.id] = conn

    model.remove_component(a)

    # Connection is dangling on `a` but still present in the store —
    # cascade is the compound command's job, not the raw mutation's.
    assert conn.id in model.connections


# ---------------------------------------------------------------------- #
# `move_component` (S1.3c.1)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_move_component_updates_position() -> None:
    """`move_component` writes the new position into the instance."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(position=QPointF(0.0, 0.0)))

    model.move_component(new_id, QPointF(50.0, 75.0))

    assert model.components[new_id].position == (50.0, 75.0)


@pytest.mark.unit
def test_move_component_emits_signal_with_qpointf_payload() -> None:
    """`componentMoved` payload is `(str, QPointF, QPointF)` per ADR-018."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(position=QPointF(0.0, 0.0)))
    received: list[tuple[str, QPointF, QPointF]] = []
    model.componentMoved.connect(lambda *args: received.append(args))

    model.move_component(new_id, QPointF(50.0, 75.0))

    assert len(received) == 1
    cid, old, new = received[0]
    assert cid == new_id
    assert isinstance(old, QPointF)
    assert isinstance(new, QPointF)
    assert (old.x(), old.y()) == (0.0, 0.0)
    assert (new.x(), new.y()) == (50.0, 75.0)


@pytest.mark.unit
def test_move_component_no_op_for_same_position() -> None:
    """Moving to the current position is a no-op: no signal."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(position=QPointF(100.0, 200.0)))
    received_moves: list[Any] = []
    model.componentMoved.connect(lambda *args: received_moves.append(args))

    model.move_component(new_id, QPointF(100.0, 200.0))

    assert received_moves == []


@pytest.mark.unit
def test_move_component_no_op_for_sub_epsilon_difference() -> None:
    """Sub-ε position drift is suppressed (drag-snap drift case from ADR-020)."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(position=QPointF(100.0, 200.0)))
    received_moves: list[Any] = []
    model.componentMoved.connect(lambda *args: received_moves.append(args))

    model.move_component(new_id, QPointF(100.0 + 5e-7, 200.0 + 5e-7))

    assert received_moves == []
    # Position is unchanged because the call short-circuited.
    assert model.components[new_id].position == (100.0, 200.0)


@pytest.mark.unit
def test_move_component_raises_keyerror_for_unknown_id() -> None:
    """Unknown component_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.move_component("cmp_nonexistent", QPointF(0.0, 0.0))

    assert "cmp_nonexistent" in str(exc_info.value)


@pytest.mark.unit
def test_move_component_updates_modified_at_timestamp() -> None:
    """A real move bumps `modified_at`."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs())
    initial_modified = model.components[new_id].modified_at
    # Sleep ensures the microsecond timestamp will differ.
    time.sleep(0.001)

    model.move_component(new_id, QPointF(999.0, 999.0))

    assert model.components[new_id].modified_at != initial_modified


@pytest.mark.unit
def test_move_component_no_op_does_not_update_modified_at() -> None:
    """A no-op move leaves `modified_at` unchanged (no phantom edits)."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(position=QPointF(50.0, 50.0)))
    initial_modified = model.components[new_id].modified_at
    time.sleep(0.001)

    model.move_component(new_id, QPointF(50.0, 50.0))

    assert model.components[new_id].modified_at == initial_modified


# ---------------------------------------------------------------------- #
# Dirty-bit helper (S1.3c.1)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_dirty_helper_is_idempotent() -> None:
    """`_set_dirty()` only emits on transition; further calls are no-ops."""
    model = WorkspaceModel()
    received: list[bool] = []
    model.dirtyChanged.connect(received.append)

    model._set_dirty()
    model._set_dirty()
    model._set_dirty()

    assert received == [True]
    assert model.is_dirty is True
