"""PhysicalAttributes: declared physical-attribute flags.

Per `02 §11.2` and `§11.3`. `PhysicalAttributes` describes
component-level physical traits (boundary condition, motion type,
directional behavior, source flag) that the workspace and future
analysis layers consume. Values come from definition-level defaults
(`02 §11.3`) and are applied at instance creation.

Located in `shared/types/` so that:

* `ComponentDefinition` (in `shared/registry/`) can declare a
  `physical_attributes` default per `02 §11.3`.
* `ComponentInstance` (in `features/SystemModelingModule/model/`)
  can carry the same value type at instance creation.
* The architecture boundary holds: `shared/` never imports
  `features/`, while features import freely from shared.

`features/SystemModelingModule/model/component_instance.py`
re-exports the type for backwards compatibility with existing
import sites (same pattern used for `PortRef`).

References:
----------
* `specs/02_workspace_requirements.md` §11.2 (Physical Attributes),
  §11.3 (Physical Attributes Origin)
* `specs/06_data_flow_and_architecture.md` §5.5 (shared/types)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# Mechanical boundary condition closed set per `02 §11.2`.
BoundaryKind = Literal["free", "fixed", "constrained"]

# Mechanical motion type closed set per `02 §11.2`.
MotionKind = Literal["translational", "rotational"]

# Source subtype closed set per `02 §11.2`.
SourceKind = Literal["constant", "step", "ramp", "sine", "signal", "random"]


@dataclass(frozen=True)
class PhysicalAttributes:
    """Declared physical-attribute flags for a component.

    Values in Phase 1 originate from definition-level defaults
    (see `02 §11.3`). User-level overrides land in Phase 1.5+.

    Attributes:
        boundary: Mechanical boundary condition; `None` when not
            applicable (e.g., electrical components).
        motion: Type of motion supported; `None` when not applicable.
        directional: True when behavior is direction-sensitive
            (e.g., diodes, force sources). Defaults to False.
        source: True when the component injects energy or signal
            into the system. Defaults to False.
        source_type: Source-signal subtype when `source` is True;
            `None` otherwise. Defaults to None.

    See Also:
        `02 §11.2`, `02 §11.3`.
    """

    boundary: BoundaryKind | None = None
    motion: MotionKind | None = None
    directional: bool = False
    source: bool = False
    source_type: SourceKind | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a 5-key dict for project-file persistence (S2.E)."""
        return {
            "boundary": self.boundary,
            "motion": self.motion,
            "directional": self.directional,
            "source": self.source,
            "source_type": self.source_type,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PhysicalAttributes:
        """Inverse of `to_dict`. Missing fields fall back to defaults.

        Enum-typed fields (`boundary`, `motion`, `source_type`) are
        preserved verbatim — unknown future values pass through for
        forward compatibility (spec §29.4) and the validator surfaces
        them in a later stage.
        """
        return cls(
            boundary=payload.get("boundary"),
            motion=payload.get("motion"),
            directional=bool(payload.get("directional", False)),
            source=bool(payload.get("source", False)),
            source_type=payload.get("source_type"),
        )


__all__ = [
    "BoundaryKind",
    "MotionKind",
    "PhysicalAttributes",
    "SourceKind",
]
