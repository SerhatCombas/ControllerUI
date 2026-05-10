"""Phase 1 core electrical-analog component definitions.

Per `01 §13` (MVP list) and `01 §6` (Component Definition
Schema). Four definitions establish the electrical side of the
validator + assembler exercise surface:

* `GROUND_ELECTRIC_DEFINITION` — single-port reference component.
  `BoundaryKind` per `02 §11.2` is a mechanical concept; the
  electrical reference role is recorded by category, not by a
  `physical_attributes` flag, so the definition carries the
  default `PhysicalAttributes()`.
* `RESISTOR_DEFINITION` — two-port symmetric passive
  (`PhysicalAttributes()` default).
* `CAPACITOR_DEFINITION` — two-port symmetric passive
  (`PhysicalAttributes()` default).
* `CONSTANT_VOLTAGE_DEFINITION` — two-port asymmetric source.
  `physical_attributes` declares `source=True` /
  `source_type="constant"` per `02 §11.2`; the workspace inherits
  these flags at instance creation per `02 §11.3`.

Each `library_path` follows `02 §13`-style tree categorization
(`("Electrical", "Analog", "Components")` for passives,
`("Electrical", "Analog", "Sources")` for sources). Definition
`id`s use the dotted-namespace convention from `01 §6.2`
(`"electrical.analog.components.resistor"`, etc.).

SVG `svg_id` strings are placeholder names; the actual SVG assets
are wired in S1.9 (UI work) and may also be staged via a separate
asset commit. The schema field exists now so that the registry
contract is complete; renderer integration is future work.

References:
----------
* `specs/01_library_requirements.md` §6, §13
* `specs/02_workspace_requirements.md` §11.2 (Physical Attributes),
  §13 (Port System)
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

from shared.registry.component_definition import ComponentDefinition
from shared.registry.library_visual_spec import LibraryVisualSpec
from shared.registry.parameter_definition import ParameterDefinition
from shared.registry.port_definition import PortDefinition
from shared.types.physical_attributes import PhysicalAttributes

# ---------------------------------------------------------------------- #
# Ground Electric — single-port reference
# ---------------------------------------------------------------------- #

GROUND_ELECTRIC_DEFINITION = ComponentDefinition(
    id="electrical.analog.components.ground",
    display_name="Ground Electric",
    short_name="GND",
    description=(
        "Electrical reference node. Each electrical model must contain "
        "at least one Ground Electric component per `02 §20.4`."
    ),
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Components"),
    category="component",
    tags=("electrical", "analog", "reference"),
    ports=(
        PortDefinition(
            id="p",
            display_name="Ground",
            domain="electrical_analog",
            relative_position=(0.5, 0.0),
        ),
    ),
    parameters=(),
    visual=LibraryVisualSpec(svg_id="electrical_ground_default"),
)

# ---------------------------------------------------------------------- #
# Resistor — two-port symmetric passive
# ---------------------------------------------------------------------- #

RESISTOR_DEFINITION = ComponentDefinition(
    id="electrical.analog.components.resistor",
    display_name="Resistor",
    short_name="R",
    description="Ideal electrical resistor (Ohm's law).",
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Components"),
    category="component",
    tags=("electrical", "analog", "passive"),
    ports=(
        PortDefinition(
            id="p",
            display_name="Positive",
            domain="electrical_analog",
            relative_position=(0.0, 0.5),
        ),
        PortDefinition(
            id="n",
            display_name="Negative",
            domain="electrical_analog",
            relative_position=(1.0, 0.5),
        ),
    ),
    parameters=(
        ParameterDefinition(
            id="resistance",
            display_name="Resistance",
            symbol="R",
            type="float",
            unit="ohm",
            default=1000.0,
            min=0.0,
            description="Electrical resistance.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="electrical_resistor_default"),
)

# ---------------------------------------------------------------------- #
# Capacitor — two-port symmetric passive
# ---------------------------------------------------------------------- #

CAPACITOR_DEFINITION = ComponentDefinition(
    id="electrical.analog.components.capacitor",
    display_name="Capacitor",
    short_name="C",
    description="Ideal electrical capacitor.",
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Components"),
    category="component",
    tags=("electrical", "analog", "passive"),
    ports=(
        PortDefinition(
            id="p",
            display_name="Positive",
            domain="electrical_analog",
            relative_position=(0.0, 0.5),
        ),
        PortDefinition(
            id="n",
            display_name="Negative",
            domain="electrical_analog",
            relative_position=(1.0, 0.5),
        ),
    ),
    parameters=(
        ParameterDefinition(
            id="capacitance",
            display_name="Capacitance",
            symbol="C",
            type="float",
            unit="F",
            default=1e-6,
            min=0.0,
            description="Electrical capacitance.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="electrical_capacitor_default"),
)

# ---------------------------------------------------------------------- #
# Constant Voltage — two-port asymmetric source
# ---------------------------------------------------------------------- #

CONSTANT_VOLTAGE_DEFINITION = ComponentDefinition(
    id="electrical.analog.sources.constant_voltage",
    display_name="Constant Voltage",
    short_name="V",
    description="DC voltage source with constant magnitude.",
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Sources"),
    category="source",
    tags=("electrical", "analog", "source", "dc"),
    ports=(
        PortDefinition(
            id="p",
            display_name="Positive",
            domain="electrical_analog",
            relative_position=(0.0, 0.5),
        ),
        PortDefinition(
            id="n",
            display_name="Negative",
            domain="electrical_analog",
            relative_position=(1.0, 0.5),
        ),
    ),
    parameters=(
        ParameterDefinition(
            id="voltage",
            display_name="Voltage",
            symbol="V",
            type="float",
            unit="V",
            default=5.0,
            description="DC output voltage.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="electrical_constant_voltage_default"),
    physical_attributes=PhysicalAttributes(source=True, source_type="constant"),
)


__all__ = [
    "CAPACITOR_DEFINITION",
    "CONSTANT_VOLTAGE_DEFINITION",
    "GROUND_ELECTRIC_DEFINITION",
    "RESISTOR_DEFINITION",
]
