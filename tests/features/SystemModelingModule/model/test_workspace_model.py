"""Unit tests for `WorkspaceModel` (S1.3a + S1.3b + S1.3c.1 + S1.3c.2a + S1.3c.2b + S1.3e).

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
  suppression on `move_component`. Missing identifiers raise
  `KeyError`.
* S1.3c.2a — `ComponentInstance.rotation` is `float` per ADR-018;
  `_canonical_rotation` validates and snaps sub-ε drift; both
  `add_component` and `rotate_component` store the canonical value;
  `componentRotated` signal payload is canonical. Validation order in
  rotate_component is argument-first / existence-second.
* S1.3c.2b — five component property setters (`set_parameter`,
  `set_custom_label`, `set_locked`, `set_tags`, `set_annotations`)
  and three connection mutations (`add_connection`,
  `remove_connection`, `update_connection`). `set_custom_label`
  applies whitespace strip canonicalization. `update_connection` is a
  combo updater with all-None no-op suppression and a single
  `connectionChanged` emission. `add_connection` is a low-level raw
  mutation with no duplicate detection (validator chain documented
  in the docstring).
* S1.3e (dirty-bit helpers only here) — `_clear_dirty()` is the
  symmetric counterpart to `_set_dirty()` per ADR-020 transition-only
  rule. A 2x2 parametrized grid (helper x initial dirty state) plus
  individual idempotency / transition tests fully exercise the
  non-batch path.

Batch mode (S1.3d) and `reset()` semantics (S1.3d/e) — including
batch-aware `_set_dirty` / `_clear_dirty` interaction and `reset()`
ID-generator blank-slate behavior — live in
`test_workspace_model_batch.py`.

References
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §3 (Source of Truth), §4 (Signals),
  §11.4 (Field Mutability Matrix), §14 (Connection System), §22
  (Move/Delete), §23 (Rotation), §38 (Locking)
"""

from __future__ import annotations

import math
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
# `add_component` rotation validation and canonicalization (S1.3c.2a)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("angle", [0.0, 90.0, 180.0, 270.0])
def test_add_component_accepts_phase1_quantized_rotations(angle: float) -> None:
    """All four Phase-1 quantization angles are accepted without error."""
    model = WorkspaceModel()

    new_id = model.add_component(**_add_kwargs(rotation=angle))

    assert model.components[new_id].rotation == angle


@pytest.mark.unit
def test_add_component_raises_valueerror_for_invalid_rotation() -> None:
    """An off-quantum rotation value raises `ValueError` before mutation."""
    model = WorkspaceModel()

    with pytest.raises(ValueError, match="rotation must be one of"):
        model.add_component(**_add_kwargs(rotation=45.0))

    # Validation happens before insert; the model stays empty.
    assert dict(model.components) == {}
    assert model.is_dirty is False


@pytest.mark.unit
def test_add_component_snaps_sub_epsilon_drifted_rotation_to_canonical() -> None:
    """Drifted input within ε is snapped to the exact canonical angle.

    `math.degrees(3 * math.pi / 2)` is `270.0` plus sub-ULP drift in
    practice; storage must carry the exact canonical `270.0`.
    """
    model = WorkspaceModel()

    drifted_270 = math.degrees(3 * math.pi / 2)
    new_id = model.add_component(**_add_kwargs(rotation=drifted_270))

    assert model.components[new_id].rotation == 270.0


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
    conn_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )

    model.remove_component(a)

    # Connection is dangling on `a` but still present in the store —
    # cascade is the compound command's job, not the raw mutation's.
    assert conn_id in model.connections


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
# `rotate_component` (S1.3c.2a)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_rotate_component_updates_rotation() -> None:
    """`rotate_component` writes the new rotation into the instance."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=0.0))

    model.rotate_component(new_id, 90.0)

    assert model.components[new_id].rotation == 90.0


@pytest.mark.unit
def test_rotate_component_emits_signal_with_float_payload() -> None:
    """`componentRotated` payload is `(str, float, float)` per ADR-018."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=0.0))
    received: list[tuple[str, float, float]] = []
    model.componentRotated.connect(lambda *args: received.append(args))

    model.rotate_component(new_id, 180.0)

    assert len(received) == 1
    cid, old, new = received[0]
    assert cid == new_id
    assert isinstance(old, float)
    assert isinstance(new, float)
    assert (old, new) == (0.0, 180.0)


@pytest.mark.unit
@pytest.mark.parametrize("angle", [0.0, 90.0, 180.0, 270.0])
def test_rotate_component_accepts_phase1_quantized_angles(angle: float) -> None:
    """All four Phase-1 quantization angles are accepted without error."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=0.0))

    # Set up a non-zero starting angle so each parameterized run is a
    # real rotation (no no-op short-circuit from 0.0 → 0.0).
    if angle == 0.0:
        model.rotate_component(new_id, 90.0)

    model.rotate_component(new_id, angle)

    assert model.components[new_id].rotation == angle


@pytest.mark.unit
def test_rotate_component_raises_valueerror_for_invalid_rotation() -> None:
    """An off-quantum rotation value raises `ValueError` before mutation."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=0.0))

    with pytest.raises(ValueError, match="rotation must be one of"):
        model.rotate_component(new_id, 45.0)

    # Validation happens before mutation; rotation stays unchanged.
    assert model.components[new_id].rotation == 0.0


@pytest.mark.unit
def test_rotate_component_snaps_sub_epsilon_drift_to_canonical_angle() -> None:
    """Sub-ε drifted input is snapped to the canonical exact angle."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=0.0))

    drifted_90 = math.degrees(math.pi / 2)
    model.rotate_component(new_id, drifted_90)

    assert model.components[new_id].rotation == 90.0


@pytest.mark.unit
def test_rotate_component_emits_canonical_angle_in_signal() -> None:
    """Signal payload `new_rotation` is canonical, not caller's drifted input."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=0.0))
    received: list[tuple[str, float, float]] = []
    model.componentRotated.connect(lambda *args: received.append(args))

    drifted_180 = math.degrees(math.pi)
    model.rotate_component(new_id, drifted_180)

    assert len(received) == 1
    _cid, _old, new = received[0]
    assert new == 180.0


@pytest.mark.unit
def test_rotate_component_no_op_for_same_rotation() -> None:
    """Rotating to the current angle is a no-op: no signal, no mutation."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=90.0))
    received: list[Any] = []
    model.componentRotated.connect(lambda *args: received.append(args))

    model.rotate_component(new_id, 90.0)

    assert received == []


@pytest.mark.unit
def test_rotate_component_no_op_when_both_input_and_current_are_drifted() -> None:
    """Canonical storage guarantees double-drifted no-op detection."""
    model = WorkspaceModel()
    drifted_90 = math.degrees(math.pi / 2)
    new_id = model.add_component(**_add_kwargs(rotation=drifted_90))
    assert model.components[new_id].rotation == 90.0
    received: list[Any] = []
    model.componentRotated.connect(lambda *args: received.append(args))

    model.rotate_component(new_id, drifted_90)

    assert received == []
    assert model.components[new_id].rotation == 90.0


@pytest.mark.unit
def test_rotate_component_raises_keyerror_for_unknown_id() -> None:
    """Unknown component_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.rotate_component("cmp_nonexistent", 90.0)

    assert "cmp_nonexistent" in str(exc_info.value)


@pytest.mark.unit
def test_rotate_component_updates_modified_at_timestamp() -> None:
    """A real rotation bumps `modified_at`."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=0.0))
    initial_modified = model.components[new_id].modified_at
    time.sleep(0.001)

    model.rotate_component(new_id, 90.0)

    assert model.components[new_id].modified_at != initial_modified


@pytest.mark.unit
def test_rotate_component_no_op_does_not_update_modified_at() -> None:
    """A no-op rotation leaves `modified_at` unchanged."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(rotation=180.0))
    initial_modified = model.components[new_id].modified_at
    time.sleep(0.001)

    model.rotate_component(new_id, 180.0)

    assert model.components[new_id].modified_at == initial_modified


# ---------------------------------------------------------------------- #
# `set_parameter` (S1.3c.2b)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_parameter_updates_existing_parameter_value() -> None:
    """Existing parameter is overwritten with the new value."""
    model = WorkspaceModel()
    new_id = model.add_component(
        **_add_kwargs(parameters={"resistance": 1000.0}),
    )

    model.set_parameter(new_id, "resistance", 2200.0)

    assert model.components[new_id].parameters == {"resistance": 2200.0}


@pytest.mark.unit
def test_set_parameter_upserts_unknown_parameter_in_phase1() -> None:
    """Phase-1 stub: setting an unknown parameter adds it (TODO S1.6)."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(parameters={}))

    model.set_parameter(new_id, "tolerance", 0.05)

    assert model.components[new_id].parameters == {"tolerance": 0.05}


@pytest.mark.unit
def test_set_parameter_emits_component_changed_signal() -> None:
    """`componentChanged` is the catch-all signal for parameter edits."""
    model = WorkspaceModel()
    new_id = model.add_component(
        **_add_kwargs(parameters={"resistance": 1000.0}),
    )
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(new_id, "resistance", 2200.0)

    assert received == [new_id]


@pytest.mark.unit
def test_set_parameter_no_op_for_same_value() -> None:
    """Setting an existing parameter to the same value is a no-op."""
    model = WorkspaceModel()
    new_id = model.add_component(
        **_add_kwargs(parameters={"resistance": 1000.0}),
    )
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(new_id, "resistance", 1000.0)

    assert received == []


@pytest.mark.unit
def test_set_parameter_raises_keyerror_for_unknown_component_id() -> None:
    """Unknown component_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.set_parameter("cmp_nonexistent", "resistance", 1000.0)

    assert "cmp_nonexistent" in str(exc_info.value)


# ---------------------------------------------------------------------- #
# `set_custom_label` (S1.3c.2b)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_custom_label_updates_label() -> None:
    """`set_custom_label` writes the new label into the instance."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(custom_label=""))

    model.set_custom_label(new_id, "Input Resistor")

    assert model.components[new_id].custom_label == "Input Resistor"


@pytest.mark.unit
def test_set_custom_label_emits_component_changed_signal() -> None:
    """`componentChanged` is the catch-all signal for label edits."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs())
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_custom_label(new_id, "R1")

    assert received == [new_id]


@pytest.mark.unit
def test_set_custom_label_strips_whitespace_before_storage() -> None:
    """Leading/trailing whitespace is normalized away before storage."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs())

    model.set_custom_label(new_id, "  Input Resistor  ")

    assert model.components[new_id].custom_label == "Input Resistor"


@pytest.mark.unit
def test_set_custom_label_whitespace_only_clears_label() -> None:
    """A whitespace-only string canonicalizes to empty (clears the label)."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(custom_label="R1"))

    model.set_custom_label(new_id, "   ")

    assert model.components[new_id].custom_label == ""


@pytest.mark.unit
def test_set_custom_label_no_op_for_whitespace_variation() -> None:
    """Setting current="foo" to "foo " (trailing space) is a no-op
    after canonicalization. No phantom signal."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(custom_label="foo"))
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_custom_label(new_id, "foo ")

    assert received == []
    assert model.components[new_id].custom_label == "foo"


@pytest.mark.unit
def test_set_custom_label_raises_keyerror_for_unknown_id() -> None:
    """Unknown component_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.set_custom_label("cmp_nonexistent", "X")

    assert "cmp_nonexistent" in str(exc_info.value)


# ---------------------------------------------------------------------- #
# `set_locked` (S1.3c.2b)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_locked_updates_flag_and_emits_signal() -> None:
    """`set_locked` flips the flag and emits `componentChanged`."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(locked=False))
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_locked(new_id, True)

    assert model.components[new_id].locked is True
    assert received == [new_id]


@pytest.mark.unit
def test_set_locked_no_op_for_same_value() -> None:
    """Setting locked to its current value is a no-op."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(locked=True))
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_locked(new_id, True)

    assert received == []


@pytest.mark.unit
def test_set_locked_raises_keyerror_for_unknown_id() -> None:
    """Unknown component_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.set_locked("cmp_nonexistent", True)

    assert "cmp_nonexistent" in str(exc_info.value)


# ---------------------------------------------------------------------- #
# `set_tags` (S1.3c.2b)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_tags_updates_tuple_and_emits_signal() -> None:
    """`set_tags` replaces the tags tuple wholesale and emits."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(tags=("input",)))
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_tags(new_id, ("output", "critical"))

    assert model.components[new_id].tags == ("output", "critical")
    assert received == [new_id]


@pytest.mark.unit
def test_set_tags_no_op_for_same_tuple() -> None:
    """Setting tags to the current tuple is a no-op."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(tags=("a", "b")))
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_tags(new_id, ("a", "b"))

    assert received == []


@pytest.mark.unit
def test_set_tags_raises_keyerror_for_unknown_id() -> None:
    """Unknown component_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.set_tags("cmp_nonexistent", ("x",))

    assert "cmp_nonexistent" in str(exc_info.value)


# ---------------------------------------------------------------------- #
# `set_annotations` (S1.3c.2b)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_annotations_replaces_dict_wholesale_and_emits() -> None:
    """`set_annotations` replaces the dict wholesale and emits."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(annotations={"old": "value"}))
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_annotations(new_id, {"new": "data"})

    assert model.components[new_id].annotations == {"new": "data"}
    assert received == [new_id]


@pytest.mark.unit
def test_set_annotations_replaces_not_merges() -> None:
    """Wholesale replace: keys not in the new dict are dropped."""
    model = WorkspaceModel()
    new_id = model.add_component(
        **_add_kwargs(annotations={"a": 1, "b": 2}),
    )

    model.set_annotations(new_id, {"c": 3})

    # `a` and `b` are gone — replace, not merge.
    assert model.components[new_id].annotations == {"c": 3}


@pytest.mark.unit
def test_set_annotations_no_op_for_identical_dict() -> None:
    """Setting annotations to a structurally identical dict is a no-op."""
    model = WorkspaceModel()
    new_id = model.add_component(**_add_kwargs(annotations={"k": "v"}))
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_annotations(new_id, {"k": "v"})

    assert received == []


@pytest.mark.unit
def test_set_annotations_raises_keyerror_for_unknown_id() -> None:
    """Unknown component_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.set_annotations("cmp_nonexistent", {"x": 1})

    assert "cmp_nonexistent" in str(exc_info.value)


# ---------------------------------------------------------------------- #
# `add_connection` (S1.3c.2b)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_add_connection_inserts_and_returns_id() -> None:
    """`add_connection` returns `con_<ULID>` and inserts the entry."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())

    new_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )

    assert isinstance(new_id, str)
    assert new_id.startswith("con_")
    assert _ULID_BODY_RE.match(new_id.removeprefix("con_"))
    assert new_id in model.connections


@pytest.mark.unit
def test_add_connection_emits_connection_added_signal() -> None:
    """`connectionAdded` fires with the new connection_id."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    received: list[str] = []
    model.connectionAdded.connect(received.append)

    new_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )

    assert received == [new_id]


@pytest.mark.unit
def test_add_connection_does_no_duplicate_check_at_raw_layer() -> None:
    """Per docstring: raw mutation. Duplicate detection is the command
    layer's job (validator chain, ADR-005 / 02 §14.3)."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())

    id_1 = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    id_2 = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )

    # Two distinct connections with different ULIDs; no duplicate check.
    assert id_1 != id_2
    assert id_1 in model.connections
    assert id_2 in model.connections


@pytest.mark.unit
def test_add_connection_transitions_dirty_on_first_call() -> None:
    """First connection edit transitions dirty `False → True` and emits."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    # Adding components already made the model dirty; reset transition
    # state by counting only emissions from here on.
    dirty_emissions: list[bool] = []
    model.dirtyChanged.connect(dirty_emissions.append)

    model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )

    # Already dirty from add_component above; ADR-020 transition-only
    # rule means no further emission.
    assert dirty_emissions == []


# ---------------------------------------------------------------------- #
# `remove_connection` (S1.3c.2b)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_remove_connection_deletes_from_connections() -> None:
    """`remove_connection` removes the entry from the internal store."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    conn_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    assert conn_id in model.connections

    model.remove_connection(conn_id)

    assert conn_id not in model.connections


@pytest.mark.unit
def test_remove_connection_emits_connection_removed_signal() -> None:
    """`connectionRemoved` fires with the removed connection_id."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    conn_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    received: list[str] = []
    model.connectionRemoved.connect(received.append)

    model.remove_connection(conn_id)

    assert received == [conn_id]


@pytest.mark.unit
def test_remove_connection_raises_keyerror_for_unknown_id() -> None:
    """Unknown connection_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.remove_connection("con_nonexistent")

    assert "con_nonexistent" in str(exc_info.value)


# ---------------------------------------------------------------------- #
# `update_connection` (S1.3c.2b)
# ---------------------------------------------------------------------- #


def _make_connection(model: WorkspaceModel) -> str:
    """Helper: add two components plus a connection, return connection_id."""
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    return model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )


@pytest.mark.unit
def test_update_connection_changes_label() -> None:
    """Setting a new label updates the label and emits."""
    model = WorkspaceModel()
    conn_id = _make_connection(model)
    received: list[str] = []
    model.connectionChanged.connect(received.append)

    model.update_connection(conn_id, label="Power Trunk")

    assert model.connections[conn_id].label == "Power Trunk"
    assert received == [conn_id]


@pytest.mark.unit
def test_update_connection_changes_routing() -> None:
    """Setting a new routing updates routing and emits."""
    model = WorkspaceModel()
    conn_id = _make_connection(model)
    received: list[str] = []
    model.connectionChanged.connect(received.append)

    new_routing = ConnectionRouting(style="straight", waypoints=())
    model.update_connection(conn_id, routing=new_routing)

    assert model.connections[conn_id].routing == new_routing
    assert received == [conn_id]


@pytest.mark.unit
def test_update_connection_changes_style() -> None:
    """Setting a new style updates the style dict and emits."""
    model = WorkspaceModel()
    conn_id = _make_connection(model)
    received: list[str] = []
    model.connectionChanged.connect(received.append)

    model.update_connection(conn_id, style={"color_override": "#ff0000"})

    assert model.connections[conn_id].style == {"color_override": "#ff0000"}
    assert received == [conn_id]


@pytest.mark.unit
def test_update_connection_multi_field_emits_single_signal() -> None:
    """A combo update of label + routing emits exactly one
    `connectionChanged`."""
    model = WorkspaceModel()
    conn_id = _make_connection(model)
    received: list[str] = []
    model.connectionChanged.connect(received.append)

    model.update_connection(
        conn_id,
        label="Combined",
        routing=ConnectionRouting(style="straight", waypoints=()),
    )

    assert len(received) == 1
    assert model.connections[conn_id].label == "Combined"
    assert model.connections[conn_id].routing.style == "straight"


@pytest.mark.unit
def test_update_connection_all_none_is_a_no_op() -> None:
    """All-None call performs no mutation and emits no signal."""
    model = WorkspaceModel()
    conn_id = _make_connection(model)
    received: list[str] = []
    model.connectionChanged.connect(received.append)

    model.update_connection(conn_id)

    assert received == []


@pytest.mark.unit
def test_update_connection_raises_keyerror_for_unknown_id() -> None:
    """Unknown connection_id raises a plain `KeyError` carrying the id."""
    model = WorkspaceModel()

    with pytest.raises(KeyError) as exc_info:
        model.update_connection("con_nonexistent", label="X")

    assert "con_nonexistent" in str(exc_info.value)


# ---------------------------------------------------------------------- #
# Dirty-bit helpers (S1.3c.1 + S1.3e)
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


@pytest.mark.unit
def test_clear_dirty_no_op_on_clean_model() -> None:
    """`_clear_dirty()` on an already-clean model is a no-op (no emit)."""
    model = WorkspaceModel()
    received: list[bool] = []
    model.dirtyChanged.connect(received.append)

    model._clear_dirty()

    assert received == []
    assert model.is_dirty is False


@pytest.mark.unit
def test_clear_dirty_emits_transition_when_dirty() -> None:
    """`_clear_dirty()` transitions dirty `True → False` and emits once."""
    model = WorkspaceModel()
    model._set_dirty()  # bring the model to dirty
    received: list[bool] = []
    model.dirtyChanged.connect(received.append)

    model._clear_dirty()

    assert received == [False]
    assert model.is_dirty is False


@pytest.mark.unit
def test_clear_dirty_helper_is_idempotent() -> None:
    """Subsequent `_clear_dirty()` calls after a transition are no-ops."""
    model = WorkspaceModel()
    model._set_dirty()
    received: list[bool] = []
    model.dirtyChanged.connect(received.append)

    model._clear_dirty()
    model._clear_dirty()
    model._clear_dirty()

    assert received == [False]
    assert model.is_dirty is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("helper_name", "initial_dirty", "expected_emissions", "expected_final_dirty"),
    [
        ("_set_dirty", False, [True], True),  # transition: clean → dirty
        ("_set_dirty", True, [], True),  # idempotent: already dirty
        ("_clear_dirty", True, [False], False),  # transition: dirty → clean
        ("_clear_dirty", False, [], False),  # idempotent: already clean
    ],
)
def test_dirty_bit_helpers_symmetric_transition_emit(
    helper_name: str,
    initial_dirty: bool,
    expected_emissions: list[bool],
    expected_final_dirty: bool,
) -> None:
    """`_set_dirty` and `_clear_dirty` are symmetric per ADR-020:
    transition emits exactly once; same-state call is a no-op.

    The four parametrized cases form a 2x2 grid (helper x initial
    state) that fully exercises ADR-020 transition-only emission
    in the non-batch path.
    """
    model = WorkspaceModel()
    model._dirty = initial_dirty
    received: list[bool] = []
    model.dirtyChanged.connect(received.append)

    getattr(model, helper_name)()

    assert received == expected_emissions
    assert model.is_dirty is expected_final_dirty
