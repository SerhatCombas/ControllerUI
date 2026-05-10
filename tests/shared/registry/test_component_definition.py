"""Unit tests for `shared.registry.ComponentDefinition` (S1.B.1a).

Covers per `01 §6`:

* required-field construction
* optional defaults (schema_version, short_name, description, tags,
  equation_metadata, probe_metadata, metadata, extensions)
* equation_metadata is `None` in Phase 1 per ADR-001
* schema_version defaults to `"0.1.0"`
* ports / parameters as tuples
* frozen dataclass guard
"""

from __future__ import annotations

import dataclasses

import pytest

from shared.registry import (
    ComponentDefinition,
    LibraryVisualSpec,
    ParameterDefinition,
    PortDefinition,
)


def _minimal_resistor_definition() -> ComponentDefinition:
    """Helper: a minimal valid resistor-like `ComponentDefinition`."""
    return ComponentDefinition(
        id="electrical.analog.components.resistor",
        display_name="Resistor",
        domain="electrical_analog",
        library_path=("Electrical", "Analog", "Components"),
        category="component",
        ports=(
            PortDefinition(id="p", display_name="Positive", domain="electrical_analog"),
            PortDefinition(id="n", display_name="Negative", domain="electrical_analog"),
        ),
        parameters=(
            ParameterDefinition(
                id="resistance",
                display_name="Resistance",
                type="float",
                default=1000.0,
                unit="ohm",
                min=0.0,
            ),
        ),
        visual=LibraryVisualSpec(svg_id="electrical_resistor_default"),
    )


@pytest.mark.unit
def test_required_field_construction() -> None:
    """Required-field construction yields a valid definition."""
    definition = _minimal_resistor_definition()

    assert definition.id == "electrical.analog.components.resistor"
    assert definition.display_name == "Resistor"
    assert definition.domain == "electrical_analog"
    assert definition.library_path == ("Electrical", "Analog", "Components")
    assert definition.category == "component"
    assert len(definition.ports) == 2
    assert len(definition.parameters) == 1


@pytest.mark.unit
def test_optional_fields_have_spec_aligned_defaults() -> None:
    """Optional fields default to values consistent with `01 §6`."""
    definition = _minimal_resistor_definition()

    assert definition.schema_version == "0.1.0"
    assert definition.short_name == ""
    assert definition.description == ""
    assert definition.tags == ()
    assert definition.probe_metadata == {}
    assert definition.metadata == {}
    assert definition.extensions == {}


@pytest.mark.unit
def test_equation_metadata_is_none_in_phase_1() -> None:
    """Per ADR-001 (engine isolation), `equation_metadata` is `None`
    in Phase 1; the field exists for forward compatibility."""
    definition = _minimal_resistor_definition()

    assert definition.equation_metadata is None


@pytest.mark.unit
def test_ports_and_parameters_are_tuples() -> None:
    """`ports` and `parameters` are tuples (frozen-correct)."""
    definition = _minimal_resistor_definition()

    assert isinstance(definition.ports, tuple)
    assert isinstance(definition.parameters, tuple)


@pytest.mark.unit
def test_frozen_dataclass_cannot_be_mutated() -> None:
    """Frozen + slots guards against direct field assignment."""
    definition = _minimal_resistor_definition()

    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.display_name = "Renamed Resistor"  # type: ignore[misc]


@pytest.mark.unit
def test_id_is_namespace_style_dotted_string() -> None:
    """`id` follows the dotted-namespace convention per `01 §6.2`."""
    definition = _minimal_resistor_definition()

    # Per spec rules: no spaces, namespace-style.
    assert " " not in definition.id
    assert "." in definition.id
