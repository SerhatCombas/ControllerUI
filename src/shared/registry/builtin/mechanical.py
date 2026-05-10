"""Phase 1 core mechanical-translational component definitions.

Per `01 §13` (MVP list) and `01 §6` (Component Definition
Schema). Three definitions establish the mechanical side of the
validator + assembler exercise surface:

* `FIXED_DEFINITION` — single-port reference (analog of Ground
  Electric in the mechanical domain). At instance creation,
  `physical_attributes.boundary="fixed"` per `02 §11.2`.
* `MASS_DEFINITION` — single-port translational mass with a
  parameter for the mass quantity.
* `SPRING_DEFINITION` — two-port symmetric spring.

Each `library_path` follows `02 §13`-style tree categorization
under `("Mechanical", "Translational", "Components")`. Definition
`id`s use the `mechanics.translational.components.*` namespace
per `01 §6.2` (note: namespace uses `mechanics`, distinct from
the `mechanical_translational` domain identifier per `02 §13.2`).

References:
----------
* `specs/01_library_requirements.md` §6, §13
* `specs/02_workspace_requirements.md` §11.2 (Physical Attributes),
  §13 (Port System), §20.4 (Initial Domain Reference Rules)
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

from shared.registry.component_definition import ComponentDefinition
from shared.registry.library_visual_spec import LibraryVisualSpec
from shared.registry.parameter_definition import ParameterDefinition
from shared.registry.port_definition import PortDefinition

# ---------------------------------------------------------------------- #
# Fixed — single-port mechanical reference
# ---------------------------------------------------------------------- #

FIXED_DEFINITION = ComponentDefinition(
    id="mechanics.translational.components.fixed",
    display_name="Fixed",
    short_name="Fix",
    description=(
        "Fixed mechanical reference (anchor / wall). Each mechanical "
        "translational model must contain at least one Fixed component "
        "per `02 §20.4`."
    ),
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Components"),
    category="component",
    tags=("mechanical", "translational", "reference"),
    ports=(
        PortDefinition(
            id="flange",
            display_name="Flange",
            domain="mechanical_translational",
            relative_position=(0.5, 1.0),
        ),
    ),
    parameters=(),
    visual=LibraryVisualSpec(svg_id="mechanical_fixed_default"),
)

# ---------------------------------------------------------------------- #
# Mass — single-port translational mass
# ---------------------------------------------------------------------- #

MASS_DEFINITION = ComponentDefinition(
    id="mechanics.translational.components.mass",
    display_name="Mass",
    short_name="m",
    description="Translational mass with one flange.",
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Components"),
    category="component",
    tags=("mechanical", "translational", "inertia"),
    ports=(
        PortDefinition(
            id="flange",
            display_name="Flange",
            domain="mechanical_translational",
            relative_position=(0.5, 1.0),
        ),
    ),
    parameters=(
        ParameterDefinition(
            id="mass",
            display_name="Mass",
            symbol="m",
            type="float",
            unit="kg",
            default=1.0,
            min=0.0,
            description="Mass quantity.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_mass_default"),
)

# ---------------------------------------------------------------------- #
# Spring — two-port symmetric translational spring
# ---------------------------------------------------------------------- #

SPRING_DEFINITION = ComponentDefinition(
    id="mechanics.translational.components.spring",
    display_name="Spring",
    short_name="k",
    description="Linear translational spring (Hooke's law).",
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Components"),
    category="component",
    tags=("mechanical", "translational", "elastic"),
    ports=(
        PortDefinition(
            id="flange_a",
            display_name="Flange A",
            domain="mechanical_translational",
            relative_position=(0.0, 0.5),
        ),
        PortDefinition(
            id="flange_b",
            display_name="Flange B",
            domain="mechanical_translational",
            relative_position=(1.0, 0.5),
        ),
    ),
    parameters=(
        ParameterDefinition(
            id="stiffness",
            display_name="Stiffness",
            symbol="k",
            type="float",
            unit="N/m",
            default=100.0,
            min=0.0,
            description="Spring stiffness (force per unit displacement).",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_spring_default"),
)


__all__ = [
    "FIXED_DEFINITION",
    "MASS_DEFINITION",
    "SPRING_DEFINITION",
]
