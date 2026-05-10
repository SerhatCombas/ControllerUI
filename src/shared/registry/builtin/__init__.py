"""shared/registry/builtin: Phase 1 built-in component definitions.

Per ADR-021 and `01 §13` MVP list. The current set covers the
full Phase 1 electrical-analog library (11 definitions) plus the
full Phase 1 mechanical-translational components block (7
definitions); mechanical sources and sensors land in S1.B.2c
and S1.B.2d respectively.

Library subtrees (path → count):

* Electrical / Analog / Components — 4 (Ground Electric, Resistor,
  Capacitor, Inductor)
* Electrical / Analog / Sensors — 2 (Current Sensor, Voltage
  Sensor)
* Electrical / Analog / Sources — 5 (Constant Voltage, Ramp
  Voltage, Signal Voltage, Sine Voltage, Step Voltage)
* Mechanical / Translational / Components — 7 (Fixed, Mass,
  Spring, Damper, Spring Damper, Wheel Black, Wheel White)

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
    MASS_DEFINITION,
    SPRING_DAMPER_DEFINITION,
    SPRING_DEFINITION,
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
)


__all__ = [
    "BUILTIN_COMPONENT_DEFINITIONS",
    "CAPACITOR_DEFINITION",
    "CONSTANT_VOLTAGE_DEFINITION",
    "CURRENT_SENSOR_DEFINITION",
    "DAMPER_DEFINITION",
    "FIXED_DEFINITION",
    "GROUND_ELECTRIC_DEFINITION",
    "INDUCTOR_DEFINITION",
    "MASS_DEFINITION",
    "RAMP_VOLTAGE_DEFINITION",
    "RESISTOR_DEFINITION",
    "SIGNAL_VOLTAGE_DEFINITION",
    "SINE_VOLTAGE_DEFINITION",
    "SPRING_DAMPER_DEFINITION",
    "SPRING_DEFINITION",
    "STEP_VOLTAGE_DEFINITION",
    "VOLTAGE_SENSOR_DEFINITION",
    "WHEEL_BLACK_DEFINITION",
    "WHEEL_WHITE_DEFINITION",
]
