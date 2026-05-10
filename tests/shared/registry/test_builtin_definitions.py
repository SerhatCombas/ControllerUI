"""Smoke tests for the Phase 1 core MVP component definitions (S1.B.1c).

Per `01 §13` MVP list. Verifies that each of the seven core
definitions registers successfully, carries the expected port
domains, and that the `BUILTIN_COMPONENT_DEFINITIONS` tuple loads
into a `ComponentRegistry` without collision.

Covers:

* Each of the 7 definitions has a stable id matching its module
  declaration.
* Ports declare domains consistent with the parent component's
  primary domain (Phase 1: no cross-domain components in the
  built-in set).
* `BUILTIN_COMPONENT_DEFINITIONS` has no duplicate ids.
* `ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)` constructs
  successfully and exposes all seven via `all()`.
* All definitions have `equation_metadata is None` per ADR-001
  (Phase 1 engine isolation).
"""

from __future__ import annotations

import pytest

from shared.registry import ComponentDefinition, ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    CAPACITOR_DEFINITION,
    CONSTANT_VOLTAGE_DEFINITION,
    FIXED_DEFINITION,
    GROUND_ELECTRIC_DEFINITION,
    MASS_DEFINITION,
    RESISTOR_DEFINITION,
    SPRING_DEFINITION,
)

_EXPECTED_DEFINITION_IDS: tuple[tuple[str, ComponentDefinition], ...] = (
    ("electrical.analog.components.ground", GROUND_ELECTRIC_DEFINITION),
    ("electrical.analog.components.resistor", RESISTOR_DEFINITION),
    ("electrical.analog.components.capacitor", CAPACITOR_DEFINITION),
    ("electrical.analog.sources.constant_voltage", CONSTANT_VOLTAGE_DEFINITION),
    ("mechanics.translational.components.fixed", FIXED_DEFINITION),
    ("mechanics.translational.components.mass", MASS_DEFINITION),
    ("mechanics.translational.components.spring", SPRING_DEFINITION),
)


@pytest.mark.unit
@pytest.mark.parametrize(("expected_id", "definition"), _EXPECTED_DEFINITION_IDS)
def test_each_builtin_definition_has_expected_id(
    expected_id: str,
    definition: ComponentDefinition,
) -> None:
    """Every definition's `id` matches its dotted-namespace name."""
    assert definition.id == expected_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "definition",
    [d for _, d in _EXPECTED_DEFINITION_IDS],
)
def test_each_builtin_port_domain_matches_parent_component_domain(
    definition: ComponentDefinition,
) -> None:
    """All ports of every built-in definition share the parent's domain.

    Phase 1 built-in set contains no cross-domain components per
    `02 §18.2`; multi-domain components arrive in Phase 1.5+.
    """
    for port in definition.ports:
        assert port.domain == definition.domain, (
            f"port '{port.id}' of '{definition.id}' has domain "
            f"'{port.domain}', expected '{definition.domain}'"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "definition",
    [d for _, d in _EXPECTED_DEFINITION_IDS],
)
def test_each_builtin_definition_has_no_equation_metadata(
    definition: ComponentDefinition,
) -> None:
    """Per ADR-001 (Phase 1 engine isolation), all definitions have
    `equation_metadata is None`."""
    assert definition.equation_metadata is None


@pytest.mark.unit
def test_builtin_tuple_contains_seven_definitions() -> None:
    """The S1.B.1c MVP set is exactly seven definitions."""
    assert len(BUILTIN_COMPONENT_DEFINITIONS) == 7


@pytest.mark.unit
def test_builtin_tuple_has_no_duplicate_ids() -> None:
    """`BUILTIN_COMPONENT_DEFINITIONS` carries seven unique ids."""
    ids = [d.id for d in BUILTIN_COMPONENT_DEFINITIONS]
    assert len(set(ids)) == len(ids), f"duplicate ids in builtin set: {ids}"


@pytest.mark.unit
def test_builtin_tuple_constructs_into_registry_without_error() -> None:
    """`ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)` builds cleanly."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    assert len(registry.all()) == 7


@pytest.mark.unit
def test_builtin_registry_exposes_each_definition_via_get() -> None:
    """Every built-in definition is retrievable via `registry.get(id)`."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    for expected_id, definition in _EXPECTED_DEFINITION_IDS:
        assert registry.get(expected_id) is definition


@pytest.mark.unit
def test_builtin_registry_filters_by_electrical_domain() -> None:
    """`by_domain("electrical_analog")` returns the four electrical defs."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    electrical = registry.by_domain("electrical_analog")

    assert {d.id for d in electrical} == {
        "electrical.analog.components.ground",
        "electrical.analog.components.resistor",
        "electrical.analog.components.capacitor",
        "electrical.analog.sources.constant_voltage",
    }


@pytest.mark.unit
def test_builtin_registry_filters_by_mechanical_domain() -> None:
    """`by_domain("mechanical_translational")` returns the three mechanical defs."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    mechanical = registry.by_domain("mechanical_translational")

    assert {d.id for d in mechanical} == {
        "mechanics.translational.components.fixed",
        "mechanics.translational.components.mass",
        "mechanics.translational.components.spring",
    }
