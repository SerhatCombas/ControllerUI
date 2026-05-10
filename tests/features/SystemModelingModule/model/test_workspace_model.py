"""Unit tests for `WorkspaceModel` skeleton (S1.3a).

Covers:

* constructor produces an empty, clean model — no signals emitted
* `is_dirty` initial state is False per ADR-020 §"Initial state"
* `components` and `connections` views are read-only `MappingProxyType`
* `_build_component_instance` mints a fresh `ComponentInstance` with
  generated `cmp_<ULID>` id, monotonic display id, and matching
  `created_at` / `modified_at` timestamps; does **not** insert into
  `_components`
* consecutive component builds yield distinct ULIDs and monotonic
  display counters per type slug
* `_build_connection` mints a fresh `Connection` with generated
  `con_<ULID>` id and `conn_<n>` display id; does **not** insert into
  `_connections`
* builders deep-copy mutable mappings (`parameters`, `metadata`, …)
  so caller-side mutations do not bleed into the built instance

Public mutation API, signals, batch mode, and dirty transitions are
not part of S1.3a and are not tested here. They land in S1.3b through S1.3e.

References
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §3 (Source of Truth)
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Any

import pytest
from PySide6.QtCore import QObject

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
    resistor at the origin.
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


# ---------------------------------------------------------------------- #
# Constructor and views
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
# `_build_component_instance`
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
# `_build_connection`
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
