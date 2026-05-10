"""shared/registry: component / parameter / port definition schema.

Per `06 §5.2`. Phase 1 surface:

* `ComponentDefinition` — library entry schema (`01 §6`)
* `PortDefinition` — port metadata schema (`02 §13`)
* `ParameterDefinition` — parameter schema (`02 §9`)
* `ParameterType` — parameter type Literal
* `LibraryVisualSpec` — definition-time SVG variant catalog
* `ParameterValidator` — value validator (`02 §9.4`)
* `ComponentRegistry` — in-memory store of definitions (S1.B.1b)
* `DomainRegistry` — supported domains + compatibility rules (S1.B.1b)

Forthcoming (S1.B.1c+):

* `BUILTIN_DEFINITIONS` — seven core MVP definitions
* `default_component_registry()` — factory wiring the above

Per ADR-021, all definitions are Python `frozen=True` dataclasses;
no JSON / YAML loader in Phase 1. Registries follow the instance
pattern (no global singletons); each consumer owns or receives a
registry by construction.
"""

from .component_definition import ComponentDefinition
from .component_registry import ComponentRegistry
from .domain_registry import DomainRegistry
from .library_visual_spec import LibraryVisualSpec
from .parameter_definition import ParameterDefinition, ParameterType
from .parameter_validator import ParameterValidator
from .port_definition import PortDefinition

__all__ = [
    "ComponentDefinition",
    "ComponentRegistry",
    "DomainRegistry",
    "LibraryVisualSpec",
    "ParameterDefinition",
    "ParameterType",
    "ParameterValidator",
    "PortDefinition",
]
