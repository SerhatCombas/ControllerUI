"""Unit tests for `shared.registry.ComponentRegistry` (S1.B.1b).

Covers:

* construction from an iterable of definitions, insertion order
  preserved
* duplicate id at construction raises `ValueError` (fail-fast)
* `get(id)` returns the definition; `KeyError` on miss
* `has(id)` is a safe boolean check
* `all()` returns the tuple in registration order
* `by_domain(d)` filters by primary domain
* `by_library_path(prefix)` filters by library-path prefix; empty
  prefix returns all
* `port_definition(def_id, port_id)` returns the matching port;
  `KeyError` on miss (either component or port)
"""

from __future__ import annotations

import pytest

from shared.registry import (
    ComponentDefinition,
    ComponentRegistry,
    LibraryVisualSpec,
    ParameterDefinition,
    PortDefinition,
)

# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #


def _make_resistor() -> ComponentDefinition:
    return ComponentDefinition(
        id="electrical.analog.components.resistor",
        display_name="Resistor",
        domain="electrical_analog",
        library_path=("Electrical", "Analog", "Components"),
        category="component",
        ports=(
            PortDefinition(id="p", display_name="P", domain="electrical_analog"),
            PortDefinition(id="n", display_name="N", domain="electrical_analog"),
        ),
        parameters=(
            ParameterDefinition(
                id="resistance",
                display_name="Resistance",
                type="float",
                default=1000.0,
            ),
        ),
        visual=LibraryVisualSpec(svg_id="resistor"),
    )


def _make_capacitor() -> ComponentDefinition:
    return ComponentDefinition(
        id="electrical.analog.components.capacitor",
        display_name="Capacitor",
        domain="electrical_analog",
        library_path=("Electrical", "Analog", "Components"),
        category="component",
        ports=(
            PortDefinition(id="p", display_name="P", domain="electrical_analog"),
            PortDefinition(id="n", display_name="N", domain="electrical_analog"),
        ),
        parameters=(),
        visual=LibraryVisualSpec(svg_id="capacitor"),
    )


def _make_mass() -> ComponentDefinition:
    return ComponentDefinition(
        id="mechanics.translational.components.mass",
        display_name="Mass",
        domain="mechanical_translational",
        library_path=("Mechanical", "Translational", "Components"),
        category="component",
        ports=(
            PortDefinition(
                id="flange",
                display_name="Flange",
                domain="mechanical_translational",
            ),
        ),
        parameters=(),
        visual=LibraryVisualSpec(svg_id="mass"),
    )


# ---------------------------------------------------------------------- #
# Construction
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_construction_preserves_insertion_order() -> None:
    """`all()` returns definitions in the order they were registered."""
    r1 = _make_resistor()
    r2 = _make_capacitor()
    registry = ComponentRegistry([r1, r2])

    assert registry.all() == (r1, r2)


@pytest.mark.unit
def test_duplicate_id_at_construction_raises_valueerror() -> None:
    """Two definitions with the same id fail fast at registry build."""
    r1 = _make_resistor()
    r2 = _make_resistor()  # same id

    with pytest.raises(ValueError, match="duplicate component definition id"):
        ComponentRegistry([r1, r2])


# ---------------------------------------------------------------------- #
# Lookup
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_get_returns_definition_by_id() -> None:
    """`get(id)` returns the registered definition."""
    resistor = _make_resistor()
    registry = ComponentRegistry([resistor])

    assert registry.get("electrical.analog.components.resistor") is resistor


@pytest.mark.unit
def test_get_raises_keyerror_for_unknown_id() -> None:
    """`get(id)` raises `KeyError` on miss."""
    registry = ComponentRegistry([_make_resistor()])

    with pytest.raises(KeyError) as exc_info:
        registry.get("nonexistent.id")

    assert "nonexistent.id" in str(exc_info.value)


@pytest.mark.unit
def test_has_returns_boolean() -> None:
    """`has(id)` is a safe presence check."""
    registry = ComponentRegistry([_make_resistor()])

    assert registry.has("electrical.analog.components.resistor") is True
    assert registry.has("nonexistent.id") is False


# ---------------------------------------------------------------------- #
# Filtered views
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_by_domain_filters_by_primary_domain() -> None:
    """`by_domain(d)` returns only definitions with that primary domain."""
    resistor = _make_resistor()
    capacitor = _make_capacitor()
    mass = _make_mass()
    registry = ComponentRegistry([resistor, capacitor, mass])

    electrical = registry.by_domain("electrical_analog")
    mechanical = registry.by_domain("mechanical_translational")

    assert electrical == (resistor, capacitor)
    assert mechanical == (mass,)


@pytest.mark.unit
def test_by_library_path_with_empty_prefix_returns_all() -> None:
    """`by_library_path(())` is equivalent to `all()`."""
    resistor = _make_resistor()
    mass = _make_mass()
    registry = ComponentRegistry([resistor, mass])

    assert registry.by_library_path() == (resistor, mass)
    assert registry.by_library_path(()) == (resistor, mass)


@pytest.mark.unit
def test_by_library_path_filters_by_prefix() -> None:
    """A specific prefix narrows the result to that subtree."""
    resistor = _make_resistor()
    capacitor = _make_capacitor()
    mass = _make_mass()
    registry = ComponentRegistry([resistor, capacitor, mass])

    electrical_subtree = registry.by_library_path(("Electrical",))
    mechanical_subtree = registry.by_library_path(("Mechanical",))

    assert electrical_subtree == (resistor, capacitor)
    assert mechanical_subtree == (mass,)


@pytest.mark.unit
def test_by_library_path_no_match_returns_empty() -> None:
    """A prefix with no matches returns the empty tuple."""
    registry = ComponentRegistry([_make_resistor()])

    assert registry.by_library_path(("Hydraulic",)) == ()


# ---------------------------------------------------------------------- #
# Port-level lookup
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_port_definition_returns_matching_port() -> None:
    """`port_definition(def_id, port_id)` finds the port on the component."""
    registry = ComponentRegistry([_make_resistor()])

    port = registry.port_definition("electrical.analog.components.resistor", "p")

    assert port.id == "p"
    assert port.domain == "electrical_analog"


@pytest.mark.unit
def test_port_definition_raises_keyerror_for_unknown_component() -> None:
    """An unknown `definition_id` propagates the inner `KeyError`."""
    registry = ComponentRegistry([_make_resistor()])

    with pytest.raises(KeyError) as exc_info:
        registry.port_definition("nonexistent.id", "p")

    assert "nonexistent.id" in str(exc_info.value)


@pytest.mark.unit
def test_port_definition_raises_keyerror_for_unknown_port() -> None:
    """Known component + unknown port raises `KeyError` with a clear message."""
    registry = ComponentRegistry([_make_resistor()])

    with pytest.raises(KeyError) as exc_info:
        registry.port_definition("electrical.analog.components.resistor", "nonexistent_port")

    msg = str(exc_info.value)
    assert "nonexistent_port" in msg
    assert "resistor" in msg
