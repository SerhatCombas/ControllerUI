"""ComponentDefinition: stable definition record for one library component.

Per `01 §6`. A `ComponentDefinition` is the canonical schema for
one library entry — what gets dragged from the
`ModelLibraryPanel` to create a `ComponentInstance` on the
workspace. Definitions are loaded into `ComponentRegistry` at
application bootstrap (`01 §1.114`); Phase 1 source format is
Python frozen dataclasses per ADR-021.

Component **definition ID** vs component **instance ID** is a
critical distinction (`01 §6.2.1`):

* Definition ID — namespace-style string (e.g.,
  `"electrical.analog.components.resistor"`), stable across
  releases, never reused. Defined here.
* Instance ID — ULID with `cmp_` prefix (e.g.,
  `"cmp_01HV..."`), generated per placement, never reused. See
  `features/SystemModelingModule/model/component_instance.py`.

Phase 1 `equation_metadata` is always `None`: equation
extraction is Phase 2+ work (ADR-001 Phase-1 engine isolation).
The field is reserved here so registry definitions can carry
equation metadata in later phases without schema migration.

References:
----------
* `specs/01_library_requirements.md` §6 (Component Definition
  Schema), §6.1 (Required Fields), §6.2 (Definition ID Rules),
  §6.2.1 (Definition vs Instance ID), §1.114 (registry-based
  bootstrap)
* `decisions/ADR-001-phase1-engine-isolation.md`
  (`equation_metadata` is None in Phase 1)
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shared.types.domain import DomainId

    from .library_visual_spec import LibraryVisualSpec
    from .parameter_definition import ParameterDefinition
    from .port_definition import PortDefinition


@dataclass(frozen=True, slots=True)
class ComponentDefinition:
    """Stable definition record for one library component.

    Attributes:
        id: Stable namespace-style identifier (e.g.,
            `"electrical.analog.components.resistor"`). Must be
            unique across the registry. Renaming a definition is
            a breaking change and requires a migration alias per
            `01 §6.2`.
        schema_version: Component definition schema version,
            currently `"0.1.0"`. Independent from the project
            file schema version (`02 §29.1`).
        display_name: User-facing component name shown in the
            library panel and info panel.
        domain: Primary physical domain of the component per
            `02 §13.2`. Single-domain components have all ports
            on this domain; multi-domain components (`02 §18.2`)
            may declare per-port domains independently (the
            `domain` field here records the principal domain for
            library categorization).
        library_path: Tuple of category labels naming the path
            in the `ModelLibraryPanel` tree (e.g.,
            `("Electrical", "Analog", "Components")`).
        category: Functional category (`"component"`, `"source"`,
            `"sensor"`, `"example"`, etc.) per `01 §6.3`.
        ports: Tuple of `PortDefinition` records. Each port's id
            must be unique within the component.
        parameters: Tuple of `ParameterDefinition` records. Each
            parameter's id must be unique within the component.
        visual: `LibraryVisualSpec` mapping the definition to its
            SVG asset(s).
        short_name: Short user-facing label (e.g., `"R"`).
            Defaults to empty string.
        description: Free-form documentation shown in tooltips
            and generated docs.
        tags: Free-form tags for search / filter (e.g.,
            `("electrical", "passive")`).
        equation_metadata: Reserved for Phase 2+ equation
            extraction. Phase 1 value is always `None` per
            ADR-001 (engine isolation).
        probe_metadata: Reserved for future probe/observation
            configuration. Defaults to empty mapping.
        metadata: Forward-compatibility container per `02 §11.1`.
        extensions: Forward-compatibility container for
            domain-specific extension fields.

    See Also:
        `01 §6`, `02 §13`, `02 §18.2`, ADR-001, ADR-021.
    """

    id: str
    display_name: str
    domain: DomainId
    library_path: tuple[str, ...]
    category: str
    ports: tuple[PortDefinition, ...]
    parameters: tuple[ParameterDefinition, ...]
    visual: LibraryVisualSpec
    schema_version: str = "0.1.0"
    short_name: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    equation_metadata: None = None
    probe_metadata: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)


__all__ = ["ComponentDefinition"]
