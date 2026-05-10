"""Unit tests for `shared.registry.ParameterDefinition` (S1.B.1a).

Covers per `02 §9.1`:

* required-field construction (id, display_name, type, default)
* default values for optional fields
* `enum` parameter with `allowed_values`
* `expression`-type definitions are schema-valid (runtime parsing
  deferred to Phase 2+)
* frozen dataclass guard
"""

from __future__ import annotations

import dataclasses

import pytest

from shared.registry import ParameterDefinition


@pytest.mark.unit
def test_minimal_required_field_construction() -> None:
    """`id`, `display_name`, `type`, `default` are the minimal set."""
    param = ParameterDefinition(
        id="resistance",
        display_name="Resistance",
        type="float",
        default=1000.0,
    )

    assert param.id == "resistance"
    assert param.display_name == "Resistance"
    assert param.type == "float"
    assert param.default == 1000.0


@pytest.mark.unit
def test_optional_fields_have_phase1_defaults() -> None:
    """Optional fields default to spec-aligned values."""
    param = ParameterDefinition(
        id="resistance",
        display_name="Resistance",
        type="float",
        default=1000.0,
    )

    assert param.symbol == ""
    assert param.unit is None
    assert param.min is None
    assert param.max is None
    assert param.step is None
    assert param.required is True
    assert param.editable is True
    assert param.supports_expression is False
    assert param.allowed_values is None
    assert param.description == ""
    assert param.metadata == {}
    assert param.extensions == {}


@pytest.mark.unit
def test_enum_parameter_with_allowed_values() -> None:
    """An `enum` parameter carries its closed set via `allowed_values`."""
    param = ParameterDefinition(
        id="polarity",
        display_name="Polarity",
        type="enum",
        default="positive",
        allowed_values=("positive", "negative"),
    )

    assert param.type == "enum"
    assert param.allowed_values == ("positive", "negative")
    assert param.default == "positive"


@pytest.mark.unit
def test_expression_type_is_schema_valid_in_phase_1() -> None:
    """`type="expression"` is acceptable in Phase 1; runtime parsing
    is deferred to Phase 2+ per `02 §9.4`."""
    param = ParameterDefinition(
        id="initial_voltage",
        display_name="Initial Voltage",
        type="expression",
        default="0",
        supports_expression=True,
    )

    assert param.type == "expression"
    assert param.supports_expression is True


@pytest.mark.unit
def test_frozen_dataclass_cannot_be_mutated() -> None:
    """Frozen + slots guards against direct field assignment."""
    param = ParameterDefinition(
        id="x",
        display_name="X",
        type="float",
        default=0.0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        param.default = 1.0  # type: ignore[misc]
