"""Unit tests for `shared.registry.ParameterValidator` (S1.B.1a).

Covers per `02 §9.4` Phase 1 active rules:

1. type check — float, int, bool, string, enum, expression
2. required check — `None` rejected when required=True
3. min/max check — numeric bounds enforced
4. enum allowed-values check — value must be in closed set
5. unit compatibility — string-equality only (Phase 1)

Phase 1 deferred:

6. expression parse validity — schema-only; validator accepts
   `type="expression"` without parsing
"""

from __future__ import annotations

import pytest

from shared.registry import ParameterDefinition, ParameterValidator

# ---------------------------------------------------------------------- #
# Type checks
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_float_accepts_int_and_float_values() -> None:
    """`float` parameters accept both float and int (int implicitly
    convertible to float)."""
    param = ParameterDefinition(id="r", display_name="R", type="float", default=1.0)
    validator = ParameterValidator()

    assert validator.validate(param, 1000.0) == []
    assert validator.validate(param, 1000) == []


@pytest.mark.unit
def test_int_rejects_float_value() -> None:
    """`int` parameters reject float values to prevent silent truncation."""
    param = ParameterDefinition(id="n", display_name="N", type="int", default=1)
    validator = ParameterValidator()

    errors = validator.validate(param, 1.5)

    assert len(errors) == 1
    assert "type 'int'" in errors[0]


@pytest.mark.unit
def test_float_and_int_reject_bool_value() -> None:
    """`float` / `int` parameters reject `bool` (subclass of int);
    silent coercion of True/False to 1/0 would be a surprising
    semantic bug."""
    param_int = ParameterDefinition(id="n", display_name="N", type="int", default=1)
    param_float = ParameterDefinition(id="r", display_name="R", type="float", default=1.0)
    validator = ParameterValidator()

    errors_int = validator.validate(param_int, True)
    errors_float = validator.validate(param_float, False)

    assert any("got bool" in msg for msg in errors_int)
    assert any("got bool" in msg for msg in errors_float)


@pytest.mark.unit
def test_string_parameter_accepts_string() -> None:
    """`string` parameters accept str values."""
    param = ParameterDefinition(id="name", display_name="Name", type="string", default="X")
    validator = ParameterValidator()

    assert validator.validate(param, "hello") == []


@pytest.mark.unit
def test_bool_parameter_accepts_bool() -> None:
    """`bool` parameters accept True / False."""
    param = ParameterDefinition(id="on", display_name="On", type="bool", default=False)
    validator = ParameterValidator()

    assert validator.validate(param, True) == []
    assert validator.validate(param, False) == []


# ---------------------------------------------------------------------- #
# Required check
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_none_value_rejected_when_required() -> None:
    """A required parameter rejects `None`."""
    param = ParameterDefinition(id="r", display_name="R", type="float", default=1.0, required=True)
    validator = ParameterValidator()

    errors = validator.validate(param, None)

    assert len(errors) == 1
    assert "required" in errors[0]


@pytest.mark.unit
def test_none_value_accepted_when_not_required() -> None:
    """A non-required parameter accepts `None`."""
    param = ParameterDefinition(id="r", display_name="R", type="float", default=1.0, required=False)
    validator = ParameterValidator()

    assert validator.validate(param, None) == []


# ---------------------------------------------------------------------- #
# Min / max check
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_value_below_min_rejected() -> None:
    """Numeric value below `min` is rejected."""
    param = ParameterDefinition(id="r", display_name="R", type="float", default=1000.0, min=0.0)
    validator = ParameterValidator()

    errors = validator.validate(param, -1.0)

    assert any("below minimum 0.0" in msg for msg in errors)


@pytest.mark.unit
def test_value_above_max_rejected() -> None:
    """Numeric value above `max` is rejected."""
    param = ParameterDefinition(id="r", display_name="R", type="float", default=1000.0, max=10000.0)
    validator = ParameterValidator()

    errors = validator.validate(param, 99999.0)

    assert any("above maximum 10000.0" in msg for msg in errors)


@pytest.mark.unit
def test_value_at_bound_is_accepted() -> None:
    """Boundary value (== min or == max) is accepted (inclusive bounds)."""
    param = ParameterDefinition(
        id="r", display_name="R", type="float", default=1.0, min=0.0, max=10.0
    )
    validator = ParameterValidator()

    assert validator.validate(param, 0.0) == []
    assert validator.validate(param, 10.0) == []


# ---------------------------------------------------------------------- #
# Enum allowed-values check
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_enum_value_in_allowed_set_accepted() -> None:
    """An enum value present in `allowed_values` is accepted."""
    param = ParameterDefinition(
        id="polarity",
        display_name="Polarity",
        type="enum",
        default="positive",
        allowed_values=("positive", "negative"),
    )
    validator = ParameterValidator()

    assert validator.validate(param, "positive") == []
    assert validator.validate(param, "negative") == []


@pytest.mark.unit
def test_enum_value_not_in_allowed_set_rejected() -> None:
    """An enum value missing from `allowed_values` is rejected."""
    param = ParameterDefinition(
        id="polarity",
        display_name="Polarity",
        type="enum",
        default="positive",
        allowed_values=("positive", "negative"),
    )
    validator = ParameterValidator()

    errors = validator.validate(param, "neutral")

    assert any("not in allowed values" in msg for msg in errors)


# ---------------------------------------------------------------------- #
# Unit compatibility (Phase 1: string equality)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_matching_unit_accepted() -> None:
    """When supplied unit equals declared unit (string-equality), no error."""
    param = ParameterDefinition(id="r", display_name="R", type="float", default=1000.0, unit="ohm")
    validator = ParameterValidator()

    assert validator.validate(param, 1000.0, unit="ohm") == []


@pytest.mark.unit
def test_mismatching_unit_rejected() -> None:
    """A mismatching unit string is rejected (Phase 1 string-equality).

    Phase 1 does NOT do dimensional analysis, so 'V/A' is rejected even
    though it is dimensionally equivalent to 'ohm'. Full dimensional
    analysis is Phase 2+ per `02 §9.3`.
    """
    param = ParameterDefinition(id="r", display_name="R", type="float", default=1000.0, unit="ohm")
    validator = ParameterValidator()

    errors = validator.validate(param, 1000.0, unit="V/A")

    assert any("does not match declared unit 'ohm'" in msg for msg in errors)
