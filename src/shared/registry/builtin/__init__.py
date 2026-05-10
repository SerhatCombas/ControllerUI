"""shared/registry/builtin: Phase 1 built-in component definitions.

Per ADR-021 and `01 §13` MVP list. With S1.B.2d this module now
ships the full Phase-1 MVP library: all electrical-analog defs
(11), all mechanical-translational components / sources / sensors
(7 + 2 + 3 = 12), for a total of 23 definitions.

Spec-driven deferrals:

* Random Road Source — `01 §13.5` marks optional; deferred to a
  later Phase-1 sub-release.
* Ideal Switch — `01 §13.1` marks deferred.
* Signal Voltage's `signal_input` control port — `01 §13.2`
  marks Phase 2 work.
* Rotational and digital domains — `01 §13.7` / `01 §2.2` mark
  Phase 2+.

Library subtrees (path → count):

* Electrical / Analog / Components — 4 (Ground Electric, Resistor,
  Capacitor, Inductor)
* Electrical / Analog / Sensors — 2 (Current Sensor, Voltage
  Sensor)
* Electrical / Analog / Sources — 5 (Constant Voltage, Ramp
  Voltage, Signal Voltage, Sine Voltage, Step Voltage)
* Mechanical / Translational / Components — 7 (Fixed, Mass,
  Spring, Damper, Spring Damper, Wheel Black, Wheel White)
* Mechanical / Translational / Sources — 2 (Force Source,
  Step Force Source; Random Road Source deferred per
  `01 §13.5`)
* Mechanical / Translational / Sensors — 3 (Position Sensor,
  Velocity Sensor, Force Sensor)

The `BUILTIN_COMPONENT_DEFINITIONS` tuple is the canonical
construction argument for the default `ComponentRegistry`. A
caller passes it directly:

```python
from shared.registry import ComponentRegistry
from shared.registry.builtin import BUILTIN_COMPONENT_DEFINITIONS

registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)
```

There is no global singleton (S1.B.1b instance-pattern decision).
Tests and alternative bootstraps construct their own registries
from explicit definition sets, including subsets of
`BUILTIN_COMPONENT_DEFINITIONS` for focused fixtures.

References:
----------
* `specs/01_library_requirements.md` §13 (MVP component list), §6
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from .electrical import (
    CAPACITOR_DEFINITION,
    CONSTANT_VOLTAGE_DEFINITION,
    CURRENT_SENSOR_DEFINITION,
    GROUND_ELECTRIC_DEFINITION,
    INDUCTOR_DEFINITION,
    RAMP_VOLTAGE_DEFINITION,
    RESISTOR_DEFINITION,
    SIGNAL_VOLTAGE_DEFINITION,
    SINE_VOLTAGE_DEFINITION,
    STEP_VOLTAGE_DEFINITION,
    VOLTAGE_SENSOR_DEFINITION,
)
from .mechanical import (
    DAMPER_DEFINITION,
    FIXED_DEFINITION,
    FORCE_SENSOR_DEFINITION,
    FORCE_SOURCE_DEFINITION,
    MASS_DEFINITION,
    POSITION_SENSOR_DEFINITION,
    SPRING_DAMPER_DEFINITION,
    SPRING_DEFINITION,
    STEP_FORCE_SOURCE_DEFINITION,
    VELOCITY_SENSOR_DEFINITION,
    WHEEL_BLACK_DEFINITION,
    WHEEL_WHITE_DEFINITION,
)

# Canonical tuple of all Phase 1 built-in definitions, in
# library-tree presentation order: each domain block lists
# components first, then sensors, then sources, in the order the
# corresponding `01 §13` subsections present them.
BUILTIN_COMPONENT_DEFINITIONS = (
    # Electrical Analog / Components (4)
    GROUND_ELECTRIC_DEFINITION,
    RESISTOR_DEFINITION,
    CAPACITOR_DEFINITION,
    INDUCTOR_DEFINITION,
    # Electrical Analog / Sensors (2)
    CURRENT_SENSOR_DEFINITION,
    VOLTAGE_SENSOR_DEFINITION,
    # Electrical Analog / Sources (5)
    CONSTANT_VOLTAGE_DEFINITION,
    RAMP_VOLTAGE_DEFINITION,
    SIGNAL_VOLTAGE_DEFINITION,
    SINE_VOLTAGE_DEFINITION,
    STEP_VOLTAGE_DEFINITION,
    # Mechanical Translational / Components (7)
    FIXED_DEFINITION,
    MASS_DEFINITION,
    SPRING_DEFINITION,
    DAMPER_DEFINITION,
    SPRING_DAMPER_DEFINITION,
    WHEEL_BLACK_DEFINITION,
    WHEEL_WHITE_DEFINITION,
    # Mechanical Translational / Sources (2; Random Road Source deferred)
    FORCE_SOURCE_DEFINITION,
    STEP_FORCE_SOURCE_DEFINITION,
    # Mechanical Translational / Sensors (3)
    POSITION_SENSOR_DEFINITION,
    VELOCITY_SENSOR_DEFINITION,
    FORCE_SENSOR_DEFINITION,
)


__all__ = [
    "BUILTIN_COMPONENT_DEFINITIONS",
    "CAPACITOR_DEFINITION",
    "CONSTANT_VOLTAGE_DEFINITION",
    "CURRENT_SENSOR_DEFINITION",
    "DAMPER_DEFINITION",
    "FIXED_DEFINITION",
    "FORCE_SENSOR_DEFINITION",
    "FORCE_SOURCE_DEFINITION",
    "GROUND_ELECTRIC_DEFINITION",
    "INDUCTOR_DEFINITION",
    "MASS_DEFINITION",
    "POSITION_SENSOR_DEFINITION",
    "RAMP_VOLTAGE_DEFINITION",
    "RESISTOR_DEFINITION",
    "SIGNAL_VOLTAGE_DEFINITION",
    "SINE_VOLTAGE_DEFINITION",
    "SPRING_DAMPER_DEFINITION",
    "SPRING_DEFINITION",
    "STEP_FORCE_SOURCE_DEFINITION",
    "STEP_VOLTAGE_DEFINITION",
    "VELOCITY_SENSOR_DEFINITION",
    "VOLTAGE_SENSOR_DEFINITION",
    "WHEEL_BLACK_DEFINITION",
    "WHEEL_WHITE_DEFINITION",
]
