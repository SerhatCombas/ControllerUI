"""Smoke tests for the Phase 1 built-in component definitions.

Per `01 §13` MVP list. Verifies that each definition registers
successfully, carries the expected port domains, and that the
`BUILTIN_COMPONENT_DEFINITIONS` tuple loads into a
`ComponentRegistry` without collision.

History of growth (the tuple expands as S1.B.2 stages land):

* S1.B.1c — seven core MVP definitions (electrical: ground,
  resistor, capacitor, constant_voltage; mechanical: fixed, mass,
  spring).
* S1.B.2a — full electrical Phase 1 set (+inductor, +current_sensor,
  +voltage_sensor, +ramp_voltage, +signal_voltage, +sine_voltage,
  +step_voltage), bringing the tuple to 14.
* S1.B.2b — full mechanical-translational components block
  (+damper, +spring_damper, +wheel_black, +wheel_white) plus the
  Spring schema bump (+free_length parameter), bringing the
  tuple to 18.
* S1.B.2c-d — mechanical sources and sensors (force_source,
  step_force_source, position/velocity/force sensors).

Covers:

* Each definition has a stable id matching its module declaration.
* Ports declare domains consistent with the parent component's
  primary domain (Phase 1: no cross-domain components in the
  built-in set).
* `BUILTIN_COMPONENT_DEFINITIONS` has no duplicate ids.
* `ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)` constructs
  successfully and exposes every definition via `all()`.
* All definitions have `equation_metadata is None` per ADR-001
  (Phase 1 engine isolation).
* Source-category definitions carry `physical_attributes.source=True`
  with the appropriate `source_type` per `02 §11.2`.
* Sensor-category definitions carry the default `PhysicalAttributes()`
  (sensors are passive observers; they neither inject energy nor
  participate in `boundary` / `motion` semantics).
"""

from __future__ import annotations

import pytest

from shared.registry import ComponentDefinition, ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    CAPACITOR_DEFINITION,
    CONSTANT_VOLTAGE_DEFINITION,
    CURRENT_SENSOR_DEFINITION,
    DAMPER_DEFINITION,
    FIXED_DEFINITION,
    GROUND_ELECTRIC_DEFINITION,
    INDUCTOR_DEFINITION,
    MASS_DEFINITION,
    RAMP_VOLTAGE_DEFINITION,
    RESISTOR_DEFINITION,
    SIGNAL_VOLTAGE_DEFINITION,
    SINE_VOLTAGE_DEFINITION,
    SPRING_DAMPER_DEFINITION,
    SPRING_DEFINITION,
    STEP_VOLTAGE_DEFINITION,
    VOLTAGE_SENSOR_DEFINITION,
    WHEEL_BLACK_DEFINITION,
    WHEEL_WHITE_DEFINITION,
)

_EXPECTED_DEFINITION_IDS: tuple[tuple[str, ComponentDefinition], ...] = (
    # Electrical Analog / Components (4)
    ("electrical.analog.components.ground", GROUND_ELECTRIC_DEFINITION),
    ("electrical.analog.components.resistor", RESISTOR_DEFINITION),
    ("electrical.analog.components.capacitor", CAPACITOR_DEFINITION),
    ("electrical.analog.components.inductor", INDUCTOR_DEFINITION),
    # Electrical Analog / Sensors (2)
    ("electrical.analog.sensors.current_sensor", CURRENT_SENSOR_DEFINITION),
    ("electrical.analog.sensors.voltage_sensor", VOLTAGE_SENSOR_DEFINITION),
    # Electrical Analog / Sources (5)
    ("electrical.analog.sources.constant_voltage", CONSTANT_VOLTAGE_DEFINITION),
    ("electrical.analog.sources.ramp_voltage", RAMP_VOLTAGE_DEFINITION),
    ("electrical.analog.sources.signal_voltage", SIGNAL_VOLTAGE_DEFINITION),
    ("electrical.analog.sources.sine_voltage", SINE_VOLTAGE_DEFINITION),
    ("electrical.analog.sources.step_voltage", STEP_VOLTAGE_DEFINITION),
    # Mechanical Translational / Components (7; sources / sensors in S1.B.2c-d)
    ("mechanics.translational.components.fixed", FIXED_DEFINITION),
    ("mechanics.translational.components.mass", MASS_DEFINITION),
    ("mechanics.translational.components.spring", SPRING_DEFINITION),
    ("mechanics.translational.components.damper", DAMPER_DEFINITION),
    (
        "mechanics.translational.components.spring_damper",
        SPRING_DAMPER_DEFINITION,
    ),
    ("mechanics.translational.components.wheel_black", WHEEL_BLACK_DEFINITION),
    ("mechanics.translational.components.wheel_white", WHEEL_WHITE_DEFINITION),
)

# Source definitions and their expected source_type, derived from the
# Phase 1 source taxonomy in `02 §11.2`. Verifies the
# `physical_attributes` is wired correctly on each new source
# (S1.B.2a expands this from one entry — constant_voltage — to five).
_EXPECTED_SOURCE_TYPES: tuple[tuple[ComponentDefinition, str], ...] = (
    (CONSTANT_VOLTAGE_DEFINITION, "constant"),
    (RAMP_VOLTAGE_DEFINITION, "ramp"),
    (SIGNAL_VOLTAGE_DEFINITION, "signal"),
    (SINE_VOLTAGE_DEFINITION, "sine"),
    (STEP_VOLTAGE_DEFINITION, "step"),
)

_SENSOR_DEFINITIONS: tuple[ComponentDefinition, ...] = (
    CURRENT_SENSOR_DEFINITION,
    VOLTAGE_SENSOR_DEFINITION,
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
def test_builtin_tuple_size_matches_expected_definition_list() -> None:
    """Tuple length matches the curated `_EXPECTED_DEFINITION_IDS`.

    Decoupled from a hard-coded magic number so that adding a
    definition only requires updating `_EXPECTED_DEFINITION_IDS`
    in one place. Mismatches surface as a clear failure naming the
    drift direction.
    """
    assert len(BUILTIN_COMPONENT_DEFINITIONS) == len(_EXPECTED_DEFINITION_IDS)


@pytest.mark.unit
def test_builtin_tuple_has_no_duplicate_ids() -> None:
    """`BUILTIN_COMPONENT_DEFINITIONS` carries unique ids only."""
    ids = [d.id for d in BUILTIN_COMPONENT_DEFINITIONS]
    assert len(set(ids)) == len(ids), f"duplicate ids in builtin set: {ids}"


@pytest.mark.unit
def test_builtin_tuple_constructs_into_registry_without_error() -> None:
    """`ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)` builds cleanly."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    assert len(registry.all()) == len(_EXPECTED_DEFINITION_IDS)


@pytest.mark.unit
def test_builtin_registry_exposes_each_definition_via_get() -> None:
    """Every built-in definition is retrievable via `registry.get(id)`."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    for expected_id, definition in _EXPECTED_DEFINITION_IDS:
        assert registry.get(expected_id) is definition


@pytest.mark.unit
def test_builtin_registry_filters_by_electrical_domain() -> None:
    """`by_domain("electrical_analog")` returns the full Phase-1 electrical set.

    After S1.B.2a the Phase-1 electrical-analog block is 11 entries:
    4 components, 2 sensors, 5 sources.
    """
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    electrical = registry.by_domain("electrical_analog")

    assert {d.id for d in electrical} == {
        "electrical.analog.components.ground",
        "electrical.analog.components.resistor",
        "electrical.analog.components.capacitor",
        "electrical.analog.components.inductor",
        "electrical.analog.sensors.current_sensor",
        "electrical.analog.sensors.voltage_sensor",
        "electrical.analog.sources.constant_voltage",
        "electrical.analog.sources.ramp_voltage",
        "electrical.analog.sources.signal_voltage",
        "electrical.analog.sources.sine_voltage",
        "electrical.analog.sources.step_voltage",
    }


@pytest.mark.unit
def test_builtin_registry_filters_by_mechanical_domain() -> None:
    """`by_domain("mechanical_translational")` returns the full Phase-1
    mechanical components block (S1.B.2b).

    Mechanical sources and sensors land in S1.B.2c-d; this
    assertion will grow at those stages.
    """
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    mechanical = registry.by_domain("mechanical_translational")

    assert {d.id for d in mechanical} == {
        "mechanics.translational.components.fixed",
        "mechanics.translational.components.mass",
        "mechanics.translational.components.spring",
        "mechanics.translational.components.damper",
        "mechanics.translational.components.spring_damper",
        "mechanics.translational.components.wheel_black",
        "mechanics.translational.components.wheel_white",
    }


# ---------------------------------------------------------------------- #
# S1.B.2b: Spring schema bump + Wheel Black/White identical-shape checks
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_spring_definition_declares_stiffness_and_free_length() -> None:
    """Spring carries both `stiffness` and `free_length` per `01 §13.0`.

    S1.B.2b added `free_length` so the built-in matches the spec
    MVP table. The assertion locks the parameter id set rather than
    the ordering so future re-ordering is safe.
    """
    param_ids = {p.id for p in SPRING_DEFINITION.parameters}

    assert param_ids == {"stiffness", "free_length"}


@pytest.mark.unit
def test_wheel_black_and_wheel_white_share_physical_shape() -> None:
    """Per `01 §13.0` the two wheel definitions are the same physical
    component type; only their SVG visual differs. This pin asserts
    that the port-id set, parameter-id set, and `physical_attributes`
    stay aligned so a future schema drift on one and not the other is
    caught at test time.
    """
    black_ports = {p.id for p in WHEEL_BLACK_DEFINITION.ports}
    white_ports = {p.id for p in WHEEL_WHITE_DEFINITION.ports}
    black_params = {p.id for p in WHEEL_BLACK_DEFINITION.parameters}
    white_params = {p.id for p in WHEEL_WHITE_DEFINITION.parameters}

    assert black_ports == white_ports == {"flange", "road_contact"}
    assert black_params == white_params == {"radius", "mass"}
    assert WHEEL_BLACK_DEFINITION.physical_attributes == WHEEL_WHITE_DEFINITION.physical_attributes
    # Distinct visual assets per `01 §13.0`.
    assert WHEEL_BLACK_DEFINITION.visual.svg_id != WHEEL_WHITE_DEFINITION.visual.svg_id


# ---------------------------------------------------------------------- #
# Category-specific physical_attributes checks (S1.B.2a)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize(("definition", "expected_source_type"), _EXPECTED_SOURCE_TYPES)
def test_each_source_definition_declares_source_physical_attributes(
    definition: ComponentDefinition,
    expected_source_type: str,
) -> None:
    """Every Phase-1 voltage source declares `source=True` with the
    correct `source_type` per `02 §11.2`.

    Confirms the inheritance contract: the workspace
    (`add_component_from_definition`, S1.B.1d) will surface these
    flags on the new instance per `02 §11.3`.
    """
    assert definition.category == "source"
    assert definition.physical_attributes.source is True
    assert definition.physical_attributes.source_type == expected_source_type


@pytest.mark.unit
@pytest.mark.parametrize("definition", _SENSOR_DEFINITIONS)
def test_each_sensor_definition_uses_default_physical_attributes(
    definition: ComponentDefinition,
) -> None:
    """Sensors carry the default `PhysicalAttributes()` — they are
    passive observers and do not inject energy, set a mechanical
    boundary, or declare motion. Their sensor role is recorded by
    `category` only.
    """
    assert definition.category == "sensor"
    assert definition.physical_attributes.source is False
    assert definition.physical_attributes.source_type is None
    assert definition.physical_attributes.boundary is None
    assert definition.physical_attributes.motion is None
    assert definition.physical_attributes.directional is False
