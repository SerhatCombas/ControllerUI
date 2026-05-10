"""shared/registry: component / parameter / port definition schema.

Per `06 §5.2`. Phase 1 surface (S1.B.1a):

* `ComponentDefinition` — library entry schema (`01 §6`)
* `PortDefinition` — port metadata schema (`02 §13`)
* `ParameterDefinition` — parameter schema (`02 §9`)
* `ParameterType` — parameter type Literal
* `LibraryVisualSpec` — definition-time SVG variant catalog
* `ParameterValidator` — value validator (`02 §9.4`)

Forthcoming (S1.B.1b+):

* `ComponentRegistry` — registry instance and bootstrap
* `DomainRegistry` — domain compatibility rules

Per ADR-021, all definitions are Python `frozen=True` dataclasses;
no JSON / YAML loader in Phase 1.
"""

from .component_definition import ComponentDefinition
from .library_visual_spec import LibraryVisualSpec
from .parameter_definition import ParameterDefinition, ParameterType
from .parameter_validator import ParameterValidator
from .port_definition import PortDefinition

__all__ = [
    "ComponentDefinition",
    "LibraryVisualSpec",
    "ParameterDefinition",
    "ParameterType",
    "ParameterValidator",
    "PortDefinition",
]
