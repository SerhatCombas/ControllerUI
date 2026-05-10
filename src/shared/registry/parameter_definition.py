"""ParameterDefinition: schema-driven parameter declaration.

Per `02 §9.1`. A `ParameterDefinition` declares a single tunable
parameter on a component: its type, default value, units,
constraints, and metadata. `ComponentInstance.parameters` (in
`features/SystemModelingModule/model/component_instance.py`)
stores per-instance values keyed by the `ParameterDefinition.id`.

Phase 1 parameter types (`ParameterType` Literal):

* `float`, `int`, `bool`, `string`, `enum` — fully validated
* `expression` — schema-reserved; runtime evaluation deferred to
  Phase 2+ (`02 §9.4` last bullet)

Phase 1 validation rules (`02 §9.4`):

* type check, required check, min/max check, enum allowed-values
  → all active (see `ParameterValidator`)
* unit compatibility → Phase 1 string-equality only (`02 §9.3`
  "Phase 1 does not need full dimensional analysis")
* expression parse validity → Phase 1 schema-only (no evaluator)

Frozen + slots: hashable, immutable; safe to share across
component definitions.

References:
----------
* `specs/02_workspace_requirements.md` §9 (Parameter Schema),
  §9.1 (Parameter Definition), §9.3 (Units), §9.4 (Parameter
  Validation)
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# Phase 1 parameter types per `02 §9.1`. `expression` is reserved
# (`02 §9.4` last bullet): schema accepts the type, runtime
# evaluation is Phase 2+.
ParameterType = Literal["float", "int", "bool", "string", "enum", "expression"]


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    """Schema declaration for one tunable component parameter.

    Attributes:
        id: Parameter identifier used as the key in
            `ComponentInstance.parameters` (e.g., `"resistance"`).
        display_name: User-facing label (e.g., `"Resistance"`).
        symbol: Mathematical / engineering symbol for the
            parameter (e.g., `"R"`).
        type: Parameter type per `02 §9.1`.
        unit: Canonical internal unit string (e.g., `"ohm"`,
            `"F"`, `"N/m"`). `None` for unit-less parameters
            (e.g., gain ratios, counts).
        default: Default value of the appropriate Python type for
            `type`. Used when an instance does not override it.
        min: Inclusive lower bound for `float` / `int`, or `None`
            if unbounded. Ignored for other types.
        max: Inclusive upper bound for `float` / `int`, or `None`
            if unbounded. Ignored for other types.
        step: Recommended UI step size for sliders / spinboxes.
            `None` if not applicable.
        required: When `True`, an instance must carry a value
            (not just inherit `default`). Phase 1 treats all
            parameters as effectively required at simulation time;
            the field is preserved for future fine-grained
            validation.
        editable: When `False`, the parameter is read-only in the
            UI. Reserved for `02 §11.3` definition-inherited
            fields and locked components per `02 §38`.
        supports_expression: When `True`, the parameter accepts
            an `expression` source per `02 §9.2`. Phase 1 schema
            preserves the flag but runtime evaluation is deferred
            to Phase 2+.
        allowed_values: For `type="enum"`, the closed set of
            allowed value strings. `None` for non-enum types.
        description: Free-form documentation for tooltips and
            generated docs.
        metadata: Forward-compatibility container for non-breaking
            metadata fields per `02 §11.1`.
        extensions: Forward-compatibility container for
            domain-specific extension fields.

    See Also:
        `02 §9.1`, `02 §9.4` (validation rules), `ParameterValidator`.
    """

    id: str
    display_name: str
    type: ParameterType
    default: Any
    symbol: str = ""
    unit: str | None = None
    min: Any | None = None
    max: Any | None = None
    step: Any | None = None
    required: bool = True
    editable: bool = True
    supports_expression: bool = False
    allowed_values: tuple[str, ...] | None = None
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ParameterDefinition",
    "ParameterType",
]
