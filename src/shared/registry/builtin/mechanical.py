"""Phase 1 mechanical-translational component definitions.

Per `01 §13` (MVP list) and `01 §6` (Component Definition
Schema). Seven definitions cover the full Phase-1 mechanical-
translational component block (`01 §13.4`); sources and sensors
follow in S1.B.2c / S1.B.2d.

Library entries by subtree:

Components (`01 §13.4`):

* `FIXED_DEFINITION` — single-port reference (analog of Ground
  Electric in the mechanical domain).
  `physical_attributes=PhysicalAttributes(boundary="fixed",
  motion="translational")` per `02 §11.2` / `02 §11.3`; the
  workspace inherits these flags at instance creation.
* `MASS_DEFINITION` — single-port translational mass with a
  parameter for the mass quantity.
  `physical_attributes.motion="translational"`.
* `SPRING_DEFINITION` — two-port symmetric spring.
  `physical_attributes.motion="translational"`. Per `01 §13.0`
  the Phase-1 spring carries two parameters: `stiffness` and
  `free_length` (the rest-length offset around which Hooke's
  law is evaluated). The `free_length` parameter is added in
  S1.B.2b to match the spec; prior to this stage the definition
  carried only `stiffness`.
* `DAMPER_DEFINITION` — two-port symmetric translational damper
  (linear dashpot). Parameter `damping`.
  `physical_attributes.motion="translational"`.
* `SPRING_DAMPER_DEFINITION` — combined spring + damper element
  per `01 §13.0` ("not a syntactic shortcut for separate Spring
  and Damper instances"). Parameters `stiffness` / `damping` /
  `free_length`. `physical_attributes.motion="translational"`.
* `WHEEL_BLACK_DEFINITION` / `WHEEL_WHITE_DEFINITION` — two-port
  wheel-with-road-contact elements. Per `01 §13.0` these share
  the same physical type but ship as distinct definitions
  because they correspond to distinct SVG asset filenames in
  the library tree; both declare `physical_attributes.motion=
  "translational"`. Ports `flange` (mechanical axle attachment)
  and `road_contact` (translational contact with the ground).

Sources (`01 §13.5`):

* `FORCE_SOURCE_DEFINITION` — single-port translational force
  source. `physical_attributes` declares `source=True` /
  `source_type="constant"` (DC force, analogous to Constant
  Voltage on the electrical side). Parameter `force`.
* `STEP_FORCE_SOURCE_DEFINITION` — single-port step-transition
  force source. `physical_attributes` declares `source=True` /
  `source_type="step"`. Parameters `initial` / `final` /
  `start_time`. Random Road Source is marked optional per
  `01 §13.5` and is deferred to a later Phase-1 sub-release.

Sensors (`01 §13.6`):

* `POSITION_SENSOR_DEFINITION` — single-port translational
  position observer. No parameters; `physical_attributes`
  default (passive observer).
* `VELOCITY_SENSOR_DEFINITION` — single-port translational
  velocity observer. No parameters.
* `FORCE_SENSOR_DEFINITION` — two-port translational force
  observer (flange_a / flange_b). No parameters.

Each `library_path` follows `02 §13`-style tree categorization
under `("Mechanical", "Translational", "Components")`. Definition
`id`s use the `mechanics.translational.components.*` namespace
per `01 §6.2` and `01 §13.0.1` (note: the namespace prefix uses
`mechanics`, distinct from the `mechanical_translational` domain
identifier per `02 §13.2`).

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
from shared.types.physical_attributes import PhysicalAttributes

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
    physical_attributes=PhysicalAttributes(boundary="fixed", motion="translational"),
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
    physical_attributes=PhysicalAttributes(motion="translational"),
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
        ParameterDefinition(
            id="free_length",
            display_name="Free Length",
            symbol="L0",
            type="float",
            unit="m",
            default=0.0,
            min=0.0,
            description=(
                "Rest length offset; Hooke's law evaluates force as "
                "`k*(L - free_length)` around this reference."
            ),
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_spring_default"),
    physical_attributes=PhysicalAttributes(motion="translational"),
)

# ---------------------------------------------------------------------- #
# Damper — two-port symmetric translational dashpot
# ---------------------------------------------------------------------- #

DAMPER_DEFINITION = ComponentDefinition(
    id="mechanics.translational.components.damper",
    display_name="Damper",
    short_name="c",
    description="Linear translational damper (viscous dashpot).",
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Components"),
    category="component",
    tags=("mechanical", "translational", "dissipative"),
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
            id="damping",
            display_name="Damping",
            symbol="c",
            type="float",
            unit="N*s/m",
            default=1.0,
            min=0.0,
            description="Linear damping coefficient (force per unit velocity).",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_damper_default"),
    physical_attributes=PhysicalAttributes(motion="translational"),
)

# ---------------------------------------------------------------------- #
# Spring Damper — combined two-port translational spring + dashpot
# ---------------------------------------------------------------------- #

SPRING_DAMPER_DEFINITION = ComponentDefinition(
    id="mechanics.translational.components.spring_damper",
    display_name="Spring Damper",
    short_name="kc",
    description=(
        "Combined translational spring + damper element. Per `01 §13.0` "
        "this is a single component, not a syntactic shortcut for connecting "
        "separate Spring and Damper instances."
    ),
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Components"),
    category="component",
    tags=("mechanical", "translational", "elastic", "dissipative"),
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
        ParameterDefinition(
            id="damping",
            display_name="Damping",
            symbol="c",
            type="float",
            unit="N*s/m",
            default=1.0,
            min=0.0,
            description="Linear damping coefficient (force per unit velocity).",
        ),
        ParameterDefinition(
            id="free_length",
            display_name="Free Length",
            symbol="L0",
            type="float",
            unit="m",
            default=0.0,
            min=0.0,
            description="Rest length offset for the embedded spring element.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_spring_damper_default"),
    physical_attributes=PhysicalAttributes(motion="translational"),
)

# ---------------------------------------------------------------------- #
# Wheel (Black / White) — two-port wheel + road-contact element
# ---------------------------------------------------------------------- #
#
# Wheel Black and Wheel White share the same physical type per
# `01 §13.0`; they exist as distinct definitions because the library
# tree presents them under distinct SVG assets. Their port shape,
# parameter set, and physical_attributes are intentionally identical.

WHEEL_BLACK_DEFINITION = ComponentDefinition(
    id="mechanics.translational.components.wheel_black",
    display_name="Wheel Black",
    short_name="W",
    description=(
        "Wheel with road contact (black visual variant). Same physical "
        "type as Wheel White; the two ship as distinct definitions because "
        "they correspond to distinct SVG asset filenames per `01 §13.0`."
    ),
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Components"),
    category="component",
    tags=("mechanical", "translational", "wheel"),
    ports=(
        PortDefinition(
            id="flange",
            display_name="Axle Flange",
            domain="mechanical_translational",
            relative_position=(0.5, 0.0),
        ),
        PortDefinition(
            id="road_contact",
            display_name="Road Contact",
            domain="mechanical_translational",
            relative_position=(0.5, 1.0),
        ),
    ),
    parameters=(
        ParameterDefinition(
            id="radius",
            display_name="Radius",
            symbol="r",
            type="float",
            unit="m",
            default=0.3,
            min=0.0,
            description="Wheel radius.",
        ),
        ParameterDefinition(
            id="mass",
            display_name="Mass",
            symbol="m",
            type="float",
            unit="kg",
            default=10.0,
            min=0.0,
            description="Wheel mass.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_wheel_black_default"),
    physical_attributes=PhysicalAttributes(motion="translational"),
)

WHEEL_WHITE_DEFINITION = ComponentDefinition(
    id="mechanics.translational.components.wheel_white",
    display_name="Wheel White",
    short_name="W",
    description=(
        "Wheel with road contact (white visual variant). Same physical "
        "type as Wheel Black; see that definition's docstring."
    ),
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Components"),
    category="component",
    tags=("mechanical", "translational", "wheel"),
    ports=(
        PortDefinition(
            id="flange",
            display_name="Axle Flange",
            domain="mechanical_translational",
            relative_position=(0.5, 0.0),
        ),
        PortDefinition(
            id="road_contact",
            display_name="Road Contact",
            domain="mechanical_translational",
            relative_position=(0.5, 1.0),
        ),
    ),
    parameters=(
        ParameterDefinition(
            id="radius",
            display_name="Radius",
            symbol="r",
            type="float",
            unit="m",
            default=0.3,
            min=0.0,
            description="Wheel radius.",
        ),
        ParameterDefinition(
            id="mass",
            display_name="Mass",
            symbol="m",
            type="float",
            unit="kg",
            default=10.0,
            min=0.0,
            description="Wheel mass.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_wheel_white_default"),
    physical_attributes=PhysicalAttributes(motion="translational"),
)


# ---------------------------------------------------------------------- #
# Force Source — single-port DC translational force source
# ---------------------------------------------------------------------- #

FORCE_SOURCE_DEFINITION = ComponentDefinition(
    id="mechanics.translational.sources.force_source",
    display_name="Force Source",
    short_name="F",
    description="Constant translational force source.",
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Sources"),
    category="source",
    tags=("mechanical", "translational", "source"),
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
            id="force",
            display_name="Force",
            symbol="F",
            type="float",
            unit="N",
            default=1.0,
            description="Applied force magnitude.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_force_source_default"),
    physical_attributes=PhysicalAttributes(
        motion="translational",
        source=True,
        source_type="constant",
    ),
)

# ---------------------------------------------------------------------- #
# Step Force Source — single-port step-transition force source
# ---------------------------------------------------------------------- #

STEP_FORCE_SOURCE_DEFINITION = ComponentDefinition(
    id="mechanics.translational.sources.step_force_source",
    display_name="Step Force Source",
    short_name="F",
    description="Step-transition translational force source.",
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Sources"),
    category="source",
    tags=("mechanical", "translational", "source", "step"),
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
            id="initial",
            display_name="Initial Value",
            symbol="F0",
            type="float",
            unit="N",
            default=0.0,
            description="Output force before `start_time`.",
        ),
        ParameterDefinition(
            id="final",
            display_name="Final Value",
            symbol="F1",
            type="float",
            unit="N",
            default=1.0,
            description="Output force at or after `start_time`.",
        ),
        ParameterDefinition(
            id="start_time",
            display_name="Start Time",
            symbol="t0",
            type="float",
            unit="s",
            default=0.0,
            min=0.0,
            description="Time at which the step transition occurs.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="mechanical_step_force_source_default"),
    physical_attributes=PhysicalAttributes(
        motion="translational",
        source=True,
        source_type="step",
    ),
)


# ---------------------------------------------------------------------- #
# Position Sensor — single-port translational position observer
# ---------------------------------------------------------------------- #
#
# Mechanical sensors carry `motion="translational"` because the
# motion type is load-bearing for downstream boundary / DOF
# reasoning even on passive observers. Unlike sources they keep
# `source=False`.

POSITION_SENSOR_DEFINITION = ComponentDefinition(
    id="mechanics.translational.sensors.position_sensor",
    display_name="Position Sensor",
    short_name="x",
    description="Ideal translational position observer (no loading).",
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Sensors"),
    category="sensor",
    tags=("mechanical", "translational", "sensor"),
    ports=(
        PortDefinition(
            id="flange",
            display_name="Flange",
            domain="mechanical_translational",
            relative_position=(0.5, 1.0),
        ),
    ),
    parameters=(),
    visual=LibraryVisualSpec(svg_id="mechanical_position_sensor_default"),
    physical_attributes=PhysicalAttributes(motion="translational"),
)

# ---------------------------------------------------------------------- #
# Velocity Sensor — single-port translational velocity observer
# ---------------------------------------------------------------------- #

VELOCITY_SENSOR_DEFINITION = ComponentDefinition(
    id="mechanics.translational.sensors.velocity_sensor",
    display_name="Velocity Sensor",
    short_name="v",
    description="Ideal translational velocity observer (no loading).",
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Sensors"),
    category="sensor",
    tags=("mechanical", "translational", "sensor"),
    ports=(
        PortDefinition(
            id="flange",
            display_name="Flange",
            domain="mechanical_translational",
            relative_position=(0.5, 1.0),
        ),
    ),
    parameters=(),
    visual=LibraryVisualSpec(svg_id="mechanical_velocity_sensor_default"),
    physical_attributes=PhysicalAttributes(motion="translational"),
)

# ---------------------------------------------------------------------- #
# Force Sensor — two-port translational force observer
# ---------------------------------------------------------------------- #

FORCE_SENSOR_DEFINITION = ComponentDefinition(
    id="mechanics.translational.sensors.force_sensor",
    display_name="Force Sensor",
    short_name="F",
    description=(
        "Ideal translational force observer. Two-port because force is "
        "measured between two mechanical points (analogous to a voltage "
        "sensor on the electrical side)."
    ),
    domain="mechanical_translational",
    library_path=("Mechanical", "Translational", "Sensors"),
    category="sensor",
    tags=("mechanical", "translational", "sensor"),
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
    parameters=(),
    visual=LibraryVisualSpec(svg_id="mechanical_force_sensor_default"),
    physical_attributes=PhysicalAttributes(motion="translational"),
)


__all__ = [
    "DAMPER_DEFINITION",
    "FIXED_DEFINITION",
    "FORCE_SENSOR_DEFINITION",
    "FORCE_SOURCE_DEFINITION",
    "MASS_DEFINITION",
    "POSITION_SENSOR_DEFINITION",
    "SPRING_DAMPER_DEFINITION",
    "SPRING_DEFINITION",
    "STEP_FORCE_SOURCE_DEFINITION",
    "VELOCITY_SENSOR_DEFINITION",
    "WHEEL_BLACK_DEFINITION",
    "WHEEL_WHITE_DEFINITION",
]
