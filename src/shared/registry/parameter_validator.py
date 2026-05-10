"""ParameterValidator: validates an instance value against a definition.

Per `02 §9.4`. Phase 1 active rules:

1. **type check** — value matches `ParameterDefinition.type`
2. **required check** — `None` rejected when `required=True`
3. **min/max check** — numeric bounds for `float` / `int`
4. **enum allowed values** — `enum` value must appear in
   `ParameterDefinition.allowed_values`
5. **unit compatibility** — Phase 1 string-equality only
   (`02 §9.3` "Phase 1 does not need full dimensional analysis")

Phase 1 deferred:

6. **expression parse validity** — `02 §9.4` last bullet;
   schema-only in Phase 1, runtime evaluator lands Phase 2+.
   `ParameterValidator` accepts the `"expression"` type as
   well-formed without parsing the expression string.

The validator returns a list of human-readable error strings
keyed to the parameter `id`; an empty list means the value is
valid. The caller (likely `WorkspaceModel.set_parameter` in
S1.6) decides whether errors block the mutation or surface as
validation issues.

`ParameterValidator` does NOT integrate with `ValidationReport`
directly: it is a pure-function helper used by upper layers
that own report production. This matches the separation between
graph-level validation (`GraphValidator`) and parameter-level
validation.

References:
----------
* `specs/02_workspace_requirements.md` §9.4 (Parameter Validation),
  §9.3 (Units)
* `decisions/ADR-020-dirty-tracking-semantics.md` §"Equality
  semantics" (`set_parameter` schema dispatch lands S1.6)
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .parameter_definition import ParameterDefinition


# Python runtime type each `ParameterDefinition.type` literal maps to.
# `enum` values are strings drawn from `allowed_values`. `expression`
# values are strings (the raw expression source); Phase 1 does not
# parse them.
_TYPE_RUNTIME_CHECK: dict[str, type | tuple[type, ...]] = {
    "float": (int, float),  # int is implicitly convertible to float
    "int": int,
    "bool": bool,
    "string": str,
    "enum": str,
    "expression": str,
}


class ParameterValidator:
    """Validate one parameter value against its definition.

    Stateless in Phase 1; the class exists for future extension
    (plugin-supplied rules, profiling hooks) without forcing
    call-site changes.
    """

    def validate(
        self,
        definition: ParameterDefinition,
        value: Any,
        *,
        unit: str | None = None,
    ) -> list[str]:
        """Return a list of error messages for the given value.

        An empty list means the value satisfies all Phase 1 rules
        from `02 §9.4`. Errors are returned as plain strings; the
        caller is responsible for wrapping them into
        `ValidationIssue` records if needed.

        Args:
            definition: Schema for the parameter being checked.
            value: Candidate value. `None` is treated as "no
                value provided" and rejected when
                `definition.required` is True.
            unit: Optional unit string accompanying the value
                (e.g., `"ohm"`, `"V"`). When supplied and
                `definition.unit` is also set, the two are
                compared by exact string equality (Phase 1; full
                dimensional analysis is Phase 2+ per `02 §9.3`).

        Returns:
            List of error messages. Empty when the value is valid.
        """
        errors: list[str] = []

        # 1. Required check first — if value is None and required,
        #    further checks are uninformative.
        if value is None:
            if definition.required:
                errors.append(f"parameter '{definition.id}' is required but no value was provided")
            return errors

        # 2. Type check.
        runtime_type = _TYPE_RUNTIME_CHECK[definition.type]
        if not isinstance(value, runtime_type):
            errors.append(
                f"parameter '{definition.id}' expects type '{definition.type}', "
                f"got {type(value).__name__}"
            )
            # If the type is wrong, downstream numeric / enum checks
            # would produce noise. Bail out after the type error.
            return errors

        # Boolean is a subclass of int in Python; reject bool when an
        # int / float parameter is expected (silent coercion bug
        # otherwise — `True` would pass `isinstance(True, int)`).
        if definition.type in ("float", "int") and isinstance(value, bool):
            errors.append(
                f"parameter '{definition.id}' expects type '{definition.type}', " f"got bool"
            )
            return errors

        # 3. Min / max check (numeric only).
        if definition.type in ("float", "int"):
            if definition.min is not None and value < definition.min:
                errors.append(
                    f"parameter '{definition.id}' value {value} is below "
                    f"minimum {definition.min}"
                )
            if definition.max is not None and value > definition.max:
                errors.append(
                    f"parameter '{definition.id}' value {value} is above "
                    f"maximum {definition.max}"
                )

        # 4. Enum allowed-values check.
        if definition.type == "enum":
            allowed = definition.allowed_values or ()
            if value not in allowed:
                errors.append(
                    f"parameter '{definition.id}' value '{value}' is not in "
                    f"allowed values {allowed!r}"
                )

        # 5. Unit compatibility (Phase 1: string equality).
        if unit is not None and definition.unit is not None and unit != definition.unit:
            errors.append(
                f"parameter '{definition.id}' unit '{unit}' does not match "
                f"declared unit '{definition.unit}'"
            )

        # 6. Expression parse validity is deferred to Phase 2+
        #    (`02 §9.4`); no check here for `definition.type ==
        #    "expression"` beyond the type check above.

        return errors


__all__ = ["ParameterValidator"]
