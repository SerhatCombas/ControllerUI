"""ComponentInstance: data layer dataclass for a placed component.

Holds the authoritative state of a single placed component on the workspace
canvas. Identity follows the hybrid ULID model (ADR-002, `02 §8`); the schema
follows `02 §11`.

This module is part of the data layer. It must not import any Qt UI classes
(`QWidget`, `QGraphicsItem`, etc.). The module is testable without a running
`QApplication`.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `specs/02_workspace_requirements.md` §8 (ID Generation Policy)
* `specs/02_workspace_requirements.md` §11 (Component Data Model)
* `specs/02_workspace_requirements.md` §12 (SVG Usage)
* `specs/09_coding_standards.md` §5.6 (Pydantic and Dataclasses)
* `specs/09_coding_standards.md` §7.2.1 (Component IDs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# Type aliases for the constrained physical-attribute enums. The closed-set
# values come from `02 §11.2`; using `Literal` lets mypy enforce them at the
# type-check layer without runtime overhead.
BoundaryKind = Literal["free", "fixed", "constrained"]
MotionKind = Literal["translational", "rotational"]
SourceKind = Literal["constant", "step", "ramp", "sine", "signal", "random"]


@dataclass(frozen=True)
class VisualSpec:
    """SVG variant selector for rendering a component instance.

    SVG is purely visual per `02 §12`: physics, ports, and parameters are
    *not* derived from SVG. This dataclass only resolves which symbol and
    variant to draw.

    Attributes:
        svg_id: Identifier of the SVG asset registered in `SvgRegistry`
            (e.g., `"resistor_default"`).
        variant: Visual variant selector for theming or state (e.g.,
            `"default"`, `"selected"`). Defaults to `"default"`.
    """

    svg_id: str
    variant: str = "default"


@dataclass(frozen=True)
class PhysicalAttributes:
    """Declared physical-attribute flags for a component instance.

    Values in Phase 1 originate from definition-level defaults (see
    `02 §11.3`). The user does not edit these directly in Phase 1.

    Attributes:
        boundary: Mechanical boundary condition; `None` when not
            applicable (e.g., electrical components).
        motion: Type of motion supported; `None` when not applicable.
        directional: True when behavior is direction-sensitive
            (e.g., diodes, force sources). Defaults to False.
        source: True when the component injects energy or signal into
            the system. Defaults to False.
        source_type: Source-signal subtype when `source` is True;
            `None` otherwise. Defaults to None.
    """

    boundary: BoundaryKind | None = None
    motion: MotionKind | None = None
    directional: bool = False
    source: bool = False
    source_type: SourceKind | None = None


@dataclass(frozen=True)
class ComponentInstance:
    """Placed component on the modeling workspace.

    Carries the three identity fields (`id`, `display_id`, `custom_label`)
    described in ADR-002, plus the placement, parameter, and presentation
    state defined in `02 §11`.

    The dataclass is frozen so that mutations go through the command stack
    (ADR-005): an "edit" produces a new `ComponentInstance` with the same
    `id` rather than mutating in place. Nested mutable containers
    (`parameters`, `metadata`, etc.) are technically still mutable for
    pragmatic reasons; convention is to copy on edit.

    Attributes:
        id: Internal stable ULID with the `cmp_` prefix. Generated at
            instance creation and never changed (ADR-002, `02 §8.2`).
        display_id: System-generated human-readable identifier
            (e.g., `"resistor_3"`). Monotonic per type. Not the
            primary reference key (`02 §8.3`, §8.5).
        definition_id: Dotted-namespace identifier of the source
            `ComponentDefinition` template
            (e.g., `"electrical.analog.components.resistor"`).
            Distinct from the runtime `id` (ADR-002).
        type: Definition type label (e.g., `"Resistor"`). Cached from
            the definition for offline display.
        display_name: Human-readable definition name shown in the UI
            (e.g., `"Resistor"`).
        domain: Physical domain identifier resolved through
            `DomainRegistry` (e.g., `"electrical_analog"`).
        category: Library category from the definition
            (e.g., `"component"`, `"sensor"`, `"source"`).
        position: Scene-coordinate `(x, y)` of the component anchor.
        visual: SVG variant selector for rendering.
        physical_attributes: Declared physical-attribute flags.
        custom_label: Optional user-editable free-form label
            (`02 §8.4`). Defaults to empty string.
        rotation: Rotation in degrees as `float`. Phase 1 quantization
            rule restricts the value to `{0.0, 90.0, 180.0, 270.0}` per
            `02 §22`/`§23` and ADR-018. The signal payload type is `float`
            (ADR-018 §"Alternative 4: `int` rotation payload" — rejected
            because it would couple the signal contract to the current
            quantization rule). Defaults to 0.0.
        parameters: Mapping of definition-declared parameter IDs to
            user-set values. Empty mapping means "use definition
            defaults at runtime."
        locked: True when editing is disabled for this instance.
            Defaults to False.
        tags: Tuple of free-form user tags. Tuple (not list) for
            frozen-correctness.
        annotations: Reserved for definition- or user-supplied
            annotations.
        metadata: Reserved for non-load-bearing supplementary data.
            Unknown fields preserved across save/load (`02 §11.1`).
        extensions: Reserved for forward-compatible extension fields
            (e.g., future Bond Graph metadata, `02 §39`).
        created_at: ISO-8601 timestamp of creation. Empty string is
            permitted only at construction time before the
            `WorkspaceModel` factory stamps it.
        modified_at: ISO-8601 timestamp of the most recent
            modification. Same construction-time exception as
            `created_at`.

    See Also:
        `02 §8`, `02 §11`, ADR-002, ADR-003.
    """

    id: str
    display_id: str
    definition_id: str
    type: str
    display_name: str
    domain: str
    category: str
    position: tuple[float, float]
    visual: VisualSpec
    physical_attributes: PhysicalAttributes
    custom_label: str = ""
    rotation: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)
    locked: bool = False
    tags: tuple[str, ...] = ()
    annotations: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    modified_at: str = ""


__all__ = [
    "BoundaryKind",
    "ComponentInstance",
    "MotionKind",
    "PhysicalAttributes",
    "SourceKind",
    "VisualSpec",
]
