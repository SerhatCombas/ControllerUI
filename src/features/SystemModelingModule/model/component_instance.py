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
from typing import Any

# PhysicalAttributes and its closed-set enums (BoundaryKind, MotionKind,
# SourceKind) live in `shared/types/physical_attributes.py` per `06 §5.5`
# so that `ComponentDefinition` (in `shared/registry/`) can declare a
# `physical_attributes` default per `02 §11.3` without crossing the
# architecture boundary into `features/`. They are re-exported here for
# backwards compatibility with existing import sites
# (`from features.SystemModelingModule.model.component_instance import
# PhysicalAttributes, BoundaryKind, ...`).
from shared.types.physical_attributes import (
    BoundaryKind,
    MotionKind,
    PhysicalAttributes,
    SourceKind,
)


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a 2-key dict (S2.E)."""
        return {"svg_id": self.svg_id, "variant": self.variant}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VisualSpec:
        """Inverse of `to_dict`. `svg_id` required, `variant` defaults."""
        svg_id = payload.get("svg_id")
        if not isinstance(svg_id, str) or not svg_id:
            raise KeyError("VisualSpec payload missing required 'svg_id'")
        return cls(svg_id=svg_id, variant=str(payload.get("variant", "default")))


# Known top-level fields recognized by `ComponentInstance.from_dict`;
# anything else is routed into `extensions` to preserve forward-compat
# data per spec/02 §29.4.
_COMPONENT_INSTANCE_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "display_id",
        "definition_id",
        "type",
        "display_name",
        "domain",
        "category",
        "position",
        "visual",
        "physical_attributes",
        "custom_label",
        "rotation",
        "parameters",
        "locked",
        "tags",
        "annotations",
        "metadata",
        "extensions",
        "created_at",
        "modified_at",
    }
)


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a project-file dict (S2.E).

        Tuples (`position`, `tags`) become JSON-friendly lists; nested
        value types (`visual`, `physical_attributes`) recurse via
        their own `to_dict`. Unknown extensions / metadata are deep-
        copied so callers cannot mutate the model through the
        returned payload.
        """
        return {
            "id": self.id,
            "display_id": self.display_id,
            "definition_id": self.definition_id,
            "type": self.type,
            "display_name": self.display_name,
            "domain": self.domain,
            "category": self.category,
            "position": [self.position[0], self.position[1]],
            "visual": self.visual.to_dict(),
            "physical_attributes": self.physical_attributes.to_dict(),
            "custom_label": self.custom_label,
            "rotation": self.rotation,
            "parameters": dict(self.parameters),
            "locked": self.locked,
            "tags": list(self.tags),
            "annotations": dict(self.annotations),
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ComponentInstance:
        """Inverse of `to_dict`. Unknown top-level keys land in `extensions`.

        Required identity fields (`id`, `display_id`, `definition_id`,
        `type`, `domain`, `category`, `position`, `visual`,
        `physical_attributes`) raise `KeyError` on absence; the load
        path treats such an entry as malformed per spec/02 §29.5.
        """
        for required in (
            "id",
            "display_id",
            "definition_id",
            "type",
            "domain",
            "category",
            "position",
            "visual",
            "physical_attributes",
        ):
            if required not in payload:
                raise KeyError(f"ComponentInstance payload missing '{required}'")
        position_raw = payload["position"]
        if not isinstance(position_raw, list | tuple) or len(position_raw) != 2:
            raise ValueError(
                f"ComponentInstance.position must be a 2-element list/tuple; "
                f"got {position_raw!r}"
            )
        visual_payload = payload["visual"]
        if not isinstance(visual_payload, dict):
            raise ValueError("ComponentInstance.visual must be a JSON object")
        phys_payload = payload["physical_attributes"]
        if not isinstance(phys_payload, dict):
            raise ValueError("ComponentInstance.physical_attributes must be a JSON object")
        carry = {k: v for k, v in payload.items() if k not in _COMPONENT_INSTANCE_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            id=str(payload["id"]),
            display_id=str(payload["display_id"]),
            definition_id=str(payload["definition_id"]),
            type=str(payload["type"]),
            display_name=str(payload.get("display_name", "")),
            domain=str(payload["domain"]),
            category=str(payload["category"]),
            position=(float(position_raw[0]), float(position_raw[1])),
            visual=VisualSpec.from_dict(visual_payload),
            physical_attributes=PhysicalAttributes.from_dict(phys_payload),
            custom_label=str(payload.get("custom_label", "")),
            rotation=float(payload.get("rotation", 0.0)),
            parameters=dict(payload.get("parameters", {}) or {}),
            locked=bool(payload.get("locked", False)),
            tags=tuple(str(t) for t in (payload.get("tags") or [])),
            annotations=dict(payload.get("annotations", {}) or {}),
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
            created_at=str(payload.get("created_at", "")),
            modified_at=str(payload.get("modified_at", "")),
        )


__all__ = [
    "BoundaryKind",
    "ComponentInstance",
    "MotionKind",
    "PhysicalAttributes",
    "SourceKind",
    "VisualSpec",
]
