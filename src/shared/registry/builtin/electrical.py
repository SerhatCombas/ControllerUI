"""Phase 1 electrical-analog component definitions.

Per `01 §13` (MVP list) and `01 §6` (Component Definition
Schema). Eleven definitions establish the full electrical Phase 1
MVP set across three library subtrees:

Components (`01 §13.1`, 4 entries):

* `GROUND_ELECTRIC_DEFINITION` — single-port reference component.
  `BoundaryKind` per `02 §11.2` is a mechanical concept; the
  electrical reference role is recorded by category, not by a
  `physical_attributes` flag, so the definition carries the
  default `PhysicalAttributes()`.
* `RESISTOR_DEFINITION` — two-port symmetric passive
  (`PhysicalAttributes()` default).
* `CAPACITOR_DEFINITION` — two-port symmetric passive
  (`PhysicalAttributes()` default).
* `INDUCTOR_DEFINITION` — two-port symmetric passive
  (`PhysicalAttributes()` default).

Sensors (`01 §13.3`, 2 entries):

* `CURRENT_SENSOR_DEFINITION` — two-port passive observer; no
  parameters, no `physical_attributes` flags (sensors do not
  inject energy).
* `VOLTAGE_SENSOR_DEFINITION` — two-port passive observer; same
  shape as the current sensor.

Sources (`01 §13.2`, 5 entries):

* `CONSTANT_VOLTAGE_DEFINITION` — DC source, `source_type="constant"`.
* `RAMP_VOLTAGE_DEFINITION` — linear ramp, `source_type="ramp"`,
  parameters `start_time` / `slope` / `start_value`.
* `SIGNAL_VOLTAGE_DEFINITION` — externally-driven source,
  `source_type="signal"`. Phase 1 carries only the electrical
  `p` / `n` ports; the Phase 2 work adds the `signal_input`
  control port (deferred per `01 §13.2`).
* `SINE_VOLTAGE_DEFINITION` — sinusoidal source,
  `source_type="sine"`, parameters `amplitude` / `frequency` /
  `phase` / `offset`.
* `STEP_VOLTAGE_DEFINITION` — step transition, `source_type="step"`,
  parameters `initial` / `final` / `start_time`.

Each `library_path` follows `02 §13`-style tree categorization
(`("Electrical", "Analog", "Components" | "Sensors" | "Sources")`).
Definition `id`s use the dotted-namespace convention from `01 §6.2`
and `01 §13.0.1` (`"electrical.analog.components.resistor"`,
`"electrical.analog.sensors.current_sensor"`,
`"electrical.analog.sources.sine_voltage"`, etc.).

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

# ---------------------------------------------------------------------- #
# Inductor — two-port symmetric passive
# ---------------------------------------------------------------------- #

INDUCTOR_DEFINITION = ComponentDefinition(
    id="electrical.analog.components.inductor",
    display_name="Inductor",
    short_name="L",
    description="Ideal electrical inductor.",
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
            id="inductance",
            display_name="Inductance",
            symbol="L",
            type="float",
            unit="H",
            default=1e-3,
            min=0.0,
            description="Electrical inductance.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="electrical_inductor_default"),
)

# ---------------------------------------------------------------------- #
# Current Sensor — two-port passive observer
# ---------------------------------------------------------------------- #

CURRENT_SENSOR_DEFINITION = ComponentDefinition(
    id="electrical.analog.sensors.current_sensor",
    display_name="Current Sensor",
    short_name="A",
    description="Ideal current measurement element (no loading).",
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Sensors"),
    category="sensor",
    tags=("electrical", "analog", "sensor"),
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
    parameters=(),
    visual=LibraryVisualSpec(svg_id="electrical_current_sensor_default"),
)

# ---------------------------------------------------------------------- #
# Voltage Sensor — two-port passive observer
# ---------------------------------------------------------------------- #

VOLTAGE_SENSOR_DEFINITION = ComponentDefinition(
    id="electrical.analog.sensors.voltage_sensor",
    display_name="Voltage Sensor",
    short_name="V",
    description="Ideal voltage measurement element (no loading).",
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Sensors"),
    category="sensor",
    tags=("electrical", "analog", "sensor"),
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
    parameters=(),
    visual=LibraryVisualSpec(svg_id="electrical_voltage_sensor_default"),
)

# ---------------------------------------------------------------------- #
# Ramp Voltage — linear-ramp source
# ---------------------------------------------------------------------- #

RAMP_VOLTAGE_DEFINITION = ComponentDefinition(
    id="electrical.analog.sources.ramp_voltage",
    display_name="Ramp Voltage",
    short_name="V",
    description="Linear-ramp voltage source.",
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Sources"),
    category="source",
    tags=("electrical", "analog", "source", "ramp"),
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
            id="start_time",
            display_name="Start Time",
            symbol="t0",
            type="float",
            unit="s",
            default=0.0,
            min=0.0,
            description="Time at which the ramp begins.",
        ),
        ParameterDefinition(
            id="slope",
            display_name="Slope",
            symbol="dV/dt",
            type="float",
            unit="V/s",
            default=1.0,
            description="Voltage rate of change after `start_time`.",
        ),
        ParameterDefinition(
            id="start_value",
            display_name="Start Value",
            symbol="V0",
            type="float",
            unit="V",
            default=0.0,
            description="Output value before `start_time`.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="electrical_ramp_voltage_default"),
    physical_attributes=PhysicalAttributes(source=True, source_type="ramp"),
)

# ---------------------------------------------------------------------- #
# Signal Voltage — externally-driven source (Phase 1: no input port yet)
# ---------------------------------------------------------------------- #

SIGNAL_VOLTAGE_DEFINITION = ComponentDefinition(
    id="electrical.analog.sources.signal_voltage",
    display_name="Signal Voltage",
    short_name="V",
    description=(
        "Externally-driven voltage source. Phase 1 ships with the electrical "
        "`p`/`n` ports only; the control `signal_input` port is added in "
        "Phase 2 per `01 §13.2`."
    ),
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Sources"),
    category="source",
    tags=("electrical", "analog", "source", "signal"),
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
    parameters=(),
    visual=LibraryVisualSpec(svg_id="electrical_signal_voltage_default"),
    physical_attributes=PhysicalAttributes(source=True, source_type="signal"),
)

# ---------------------------------------------------------------------- #
# Sine Voltage — sinusoidal source
# ---------------------------------------------------------------------- #

SINE_VOLTAGE_DEFINITION = ComponentDefinition(
    id="electrical.analog.sources.sine_voltage",
    display_name="Sine Voltage",
    short_name="V",
    description="Sinusoidal voltage source.",
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Sources"),
    category="source",
    tags=("electrical", "analog", "source", "sine"),
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
            id="amplitude",
            display_name="Amplitude",
            symbol="A",
            type="float",
            unit="V",
            default=1.0,
            min=0.0,
            description="Peak amplitude of the sinusoid.",
        ),
        ParameterDefinition(
            id="frequency",
            display_name="Frequency",
            symbol="f",
            type="float",
            unit="Hz",
            default=1.0,
            min=0.0,
            description="Frequency of the sinusoid.",
        ),
        ParameterDefinition(
            id="phase",
            display_name="Phase",
            symbol="phi",
            type="float",
            unit="rad",
            default=0.0,
            description="Phase offset of the sinusoid.",
        ),
        ParameterDefinition(
            id="offset",
            display_name="Offset",
            symbol="V0",
            type="float",
            unit="V",
            default=0.0,
            description="DC offset added to the sinusoid.",
        ),
    ),
    visual=LibraryVisualSpec(svg_id="electrical_sine_voltage_default"),
    physical_attributes=PhysicalAttributes(source=True, source_type="sine"),
)

# ---------------------------------------------------------------------- #
# Step Voltage — step-transition source
# ---------------------------------------------------------------------- #

STEP_VOLTAGE_DEFINITION = ComponentDefinition(
    id="electrical.analog.sources.step_voltage",
    display_name="Step Voltage",
    short_name="V",
    description="Step-transition voltage source.",
    domain="electrical_analog",
    library_path=("Electrical", "Analog", "Sources"),
    category="source",
    tags=("electrical", "analog", "source", "step"),
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
            id="initial",
            display_name="Initial Value",
            symbol="V0",
            type="float",
            unit="V",
            default=0.0,
            description="Output value before `start_time`.",
        ),
        ParameterDefinition(
            id="final",
            display_name="Final Value",
            symbol="V1",
            type="float",
            unit="V",
            default=1.0,
            description="Output value at or after `start_time`.",
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
    visual=LibraryVisualSpec(svg_id="electrical_step_voltage_default"),
    physical_attributes=PhysicalAttributes(source=True, source_type="step"),
)


__all__ = [
    "CAPACITOR_DEFINITION",
    "CONSTANT_VOLTAGE_DEFINITION",
    "CURRENT_SENSOR_DEFINITION",
    "GROUND_ELECTRIC_DEFINITION",
    "INDUCTOR_DEFINITION",
    "RAMP_VOLTAGE_DEFINITION",
    "RESISTOR_DEFINITION",
    "SIGNAL_VOLTAGE_DEFINITION",
    "SINE_VOLTAGE_DEFINITION",
    "STEP_VOLTAGE_DEFINITION",
    "VOLTAGE_SENSOR_DEFINITION",
]
