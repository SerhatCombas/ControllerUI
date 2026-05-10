"""LibraryVisualSpec: SVG variant catalog for a component definition.

Defines which SVG asset(s) a component definition can render with.
This is the **definition-time** variant catalog, distinct from the
**instance-time** `VisualSpec` in
`features/SystemModelingModule/model/component_instance.py`, which
records the variant a placed `ComponentInstance` currently uses.

Per `01 §6` `visual` field:

* `svg_id` — canonical SVG asset identifier
* `default_variant` — variant chosen when a component is dropped
  from the library
* `variants` — full set of supported variants (default plus
  theme- / state-swappable variants per `02 §12`)

Phase 1 typically ships `variants=("default",)` and
`default_variant="default"`; multi-variant SVGs are reserved for
Phase 1.5+ when theme / dark-mode work lands.

References:
----------
* `specs/01_library_requirements.md` §6 (Component Definition Schema)
* `specs/02_workspace_requirements.md` §12 (SVG Usage)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LibraryVisualSpec:
    """Definition-time SVG variant catalog.

    Attributes:
        svg_id: Canonical identifier of the SVG asset registered
            in the SVG registry (e.g.,
            `"electrical_resistor_default"`).
        default_variant: Variant chosen when a component is
            placed onto the workspace.
        variants: Tuple of all supported variant identifiers.
            Must include `default_variant`.

    See Also:
        `01 §6`, `02 §12`.
    """

    svg_id: str
    default_variant: str = "default"
    variants: tuple[str, ...] = ("default",)


__all__ = ["LibraryVisualSpec"]
