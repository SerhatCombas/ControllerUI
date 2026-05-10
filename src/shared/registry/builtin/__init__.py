"""shared/registry/builtin: Phase 1 core MVP component definitions.

Per ADR-021 and `01 §13` MVP list. The S1.B.1c definition set is
the minimum required to exercise the connection validator (S1.4)
and the graph assembler (S1.5) across both Phase 1 domains:

* Single-port — `ground_electric`, `fixed`, `mass`
* Two-port symmetric — `resistor`, `capacitor`, `spring`
* Two-port asymmetric source — `constant_voltage`

The remaining ~15 Phase 1 components from `01 §13` (additional
voltage sources, sensors, force sources, etc.) are deferred to
S1.B.2 and are added before UI smoke tests in S1.9 land.

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
    GROUND_ELECTRIC_DEFINITION,
    RESISTOR_DEFINITION,
)
from .mechanical import (
    FIXED_DEFINITION,
    MASS_DEFINITION,
    SPRING_DEFINITION,
)

# Canonical tuple of all Phase 1 core MVP definitions, in
# library-tree presentation order (electrical first, then
# mechanical, components-then-sources within each domain).
BUILTIN_COMPONENT_DEFINITIONS = (
    GROUND_ELECTRIC_DEFINITION,
    RESISTOR_DEFINITION,
    CAPACITOR_DEFINITION,
    CONSTANT_VOLTAGE_DEFINITION,
    FIXED_DEFINITION,
    MASS_DEFINITION,
    SPRING_DEFINITION,
)


__all__ = [
    "BUILTIN_COMPONENT_DEFINITIONS",
    "CAPACITOR_DEFINITION",
    "CONSTANT_VOLTAGE_DEFINITION",
    "FIXED_DEFINITION",
    "GROUND_ELECTRIC_DEFINITION",
    "MASS_DEFINITION",
    "RESISTOR_DEFINITION",
    "SPRING_DEFINITION",
]
