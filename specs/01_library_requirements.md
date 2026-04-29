# 01_library_requirements.md

## 1. Purpose

This document defines the requirements for the component library of the Engineering System Designer application.

The component library is the entry point for creating physical system models. Users browse available engineering components, drag them into the workspace, and use those components as typed, validated building blocks for later graph assembly, equation extraction, simulation, controller design, and result visualization.

The library must support a Simscape / Modelica-inspired workflow while remaining simpler, explicit, and fully controlled by the project architecture.

The library must provide:

- domain-organized component categories
- searchable and browsable component definitions
- SVG-based visual symbols
- metadata-defined ports
- schema-defined parameters
- stable component definition identifiers
- registry-based loading and validation
- drag-and-drop integration with the workspace
- forward-compatible metadata for future equations, probes, variants, and plugins

Phase 1 focuses on visual modeling and schema correctness. It must support component browsing, component drag/drop, component definition loading, parameter defaults, port metadata, visual symbol resolution, and registry validation.

Phase 1 must not implement equation extraction, numerical simulation, controller execution, transfer-function generation, state-space generation, or stability analysis.

---

## 2. Scope

### 2.1 In Scope for Phase 1

- Built-in component library folder structure
- Domain/category/subcategory hierarchy
- `ModelLibraryPanel` browsing UI
- Component search and filtering
- Component definition schema
- Port definition schema
- Parameter definition schema
- SVG visual mapping schema
- Visual variants such as dark/light or selected/normal symbol variants
- Component drag-and-drop payload contract
- Registry loading through `ComponentRegistry`, `DomainRegistry`, `ParameterSchemaRegistry`, and `SvgRegistry`
- Registry validation before feature modules are created
- Default parameter assignment when a component is placed
- Component definition references from `ComponentInstance`
- Preservation of unknown metadata and extension fields
- Basic built-in components for initial electrical and mechanical modeling

### 2.2 Out of Scope for Phase 1

- User-created component plugins
- Full Modelica parser support
- Automatic physics extraction from SVG files
- Automatic port extraction from SVG files
- Equation extraction from component definitions
- Runtime simulation
- Controller execution
- Transfer-function generation
- State-space generation
- Stability analysis
- Advanced dynamic animation of component internals during simulation
- External package manager for component libraries

### 2.3 Future Scope

The design must not block future support for:

- custom user libraries
- imported Modelica-inspired component definitions
- richer equation metadata
- component-level probes
- multi-domain coupling components
- nonlinear components
- component animation metadata
- theme-aware SVG symbols
- library versioning and migration
- plugin-based component packs

---

## 3. Folder Location and Library Layout

The current project structure places the visual model library under the System Modeling feature module:

```text
src/features/SystemModelingModule/panels/ModelLibraryPanel/Models/
  Electrical/
    Analog/
      Components/
      Examples/
      Sensors/
      Sources/
    Digital/
      Components/
      Examples/
      Sensors/
      Sources/
  Mechanics/
    Rotational/
      Components/
      Examples/
      Sensors/
      Sources/
    Translational/
      Components/
      Examples/
      Sensors/
      Sources/
```

This folder may contain SVG files and/or local definition files during early development.

However, the authoritative component definitions must be loaded into shared registries during application bootstrap. The folder layout is a packaged source of built-in assets, not the runtime source of truth.

**Note on path prefix:** The `src/` prefix shown above reflects the current project root layout. The architecture documents (`06_data_flow_and_architecture.md` §2.2, `07_implementation_order.md` §6.5, `08_codex_execution_rules.md` §16.1) use `application/`, `features/`, and `shared/` as logical layer names without the `src/` prefix. Both refer to the same code layout under the project root. AI agents must not invent a separate folder hierarchy for the library; the layout above is the authoritative location relative to the `features/` layer.

### 3.1 Required Separation

The library folder may store assets, but runtime ownership is:

| Concern | Owner |
|---|---|
| Component definitions | `shared/registry/ComponentRegistry` |
| Domain definitions | `shared/registry/DomainRegistry` |
| Parameter schemas | `shared/registry/ParameterSchemaRegistry` |
| SVG mappings | `shared/registry/SvgRegistry` |
| Component instances placed on workspace | `WorkspaceModel` |
| Library browsing UI | `ModelLibraryPanel` |

### 3.2 Path Stability Rule

Built-in asset paths may change during development, but component definition IDs must remain stable once project files can reference them.

A saved project must reference a component by `definition_id`, not by SVG file path or UI tree path.

---

## 4. Architecture Ownership

### 4.1 SystemModelingModule Ownership

`SystemModelingModule` coordinates the component library as part of the visual modeling workflow.

It owns:

- `ModelLibraryPanel` coordination
- drag/drop handoff to `BlockDiagramWorkspace`
- creation of `ComponentInstance` through commands
- workspace validation after placement
- graph assembly inputs derived from placed components

It must not own reusable component definitions directly. Reusable definitions belong to registries.

### 4.2 Shared Registry Ownership

`shared/registry` owns reusable definitions.

Required registries:

- `ComponentRegistry`
- `DomainRegistry`
- `ParameterSchemaRegistry`
- `SvgRegistry`

Registries must be initialized before feature modules are created.

### 4.3 UI Ownership

`ModelLibraryPanel` is a browsing and interaction surface only.

It may display:

- categories
- component names
- descriptions
- icons/SVG previews
- search results
- validation badges
- unavailable/unsupported indicators

It must not become the source of truth for component definitions.

### 4.4 Workspace Ownership

When a user drops a component into the workspace, the created `ComponentInstance` belongs to `WorkspaceModel`.

The library must not store live workspace instances.

---

## 5. Library Design Principles

### 5.1 Model-First

The component library defines model-capable engineering elements, not just visual blocks.

A component definition must describe enough metadata for future graph assembly and equation extraction, even if Phase 1 only renders and connects the component visually.

### 5.2 Metadata Over Inference

Ports, parameters, domains, and future equation behavior must be defined explicitly in metadata.

The system must not infer engineering meaning from SVG shapes, labels, colors, filenames, or UI category paths.

### 5.3 Definitions vs Instances

Component definitions are reusable templates.

Component instances are placed objects in a project workspace.

Definitions provide:

- default display name
- domain
- category
- ports
- parameters
- visual mapping
- future equation metadata

Instances store:

- internal instance ID
- referenced `definition_id`
- position
- rotation
- parameter values and overrides
- custom label
- visual variant override if needed

### 5.4 Forward Compatibility

All schemas must include `metadata` and `extensions` fields.

Unknown fields should be preserved during load/save where safe.

### 5.5 No Fake Physics

The library must not provide fake simulation behavior to make plots, panels, or examples appear functional.

Example circuits or mechanical systems may be visual examples in Phase 1, but they must not pretend to run without the later ODE and simulation artifact pipeline.

---

## 6. Component Definition Schema

Each component must have a stable definition object.

Recommended schema:

```json
{
  "id": "electrical.analog.components.resistor",
  "schema_version": "0.1.0",
  "display_name": "Resistor",
  "short_name": "R",
  "description": "Ideal electrical resistor",
  "domain": "electrical_analog",
  "library_path": ["Electrical", "Analog", "Components"],
  "category": "component",
  "tags": ["electrical", "analog", "passive"],
  "ports": [],
  "parameters": [],
  "visual": {
    "svg_id": "electrical_resistor_default",
    "default_variant": "default",
    "variants": ["default"]
  },
  "equation_metadata": null,
  "probe_metadata": {},
  "metadata": {},
  "extensions": {}
}
```

**Note on schema versions:** This `schema_version` field is the **component definition schema version**, currently `0.1.0`. It is independent from the **project schema version** (currently `0.2.0`) defined in `02_workspace_requirements.md` §29.1 and `06_data_flow_and_architecture.md` §11.1.

Two separate schemas, two independent versions:

| Schema | Version | Where Defined |
|---|---|---|
| Component definition schema | `0.1.0` | `01_library_requirements.md` §6 (this section) |
| Project file schema | `0.2.0` | `02_workspace_requirements.md` §29.1 |

The project file (`project.json`) stores `ComponentInstance` references, not full component definitions. The two schemas evolve independently. AI agents must not unify these two version fields.

### 6.1 Required Fields

| Field | Required | Meaning |
|---|---:|---|
| `id` | yes | Stable component definition ID |
| `schema_version` | yes | Definition schema version |
| `display_name` | yes | User-facing name |
| `domain` | yes | Main physical domain |
| `library_path` | yes | UI tree location |
| `category` | yes | Component, source, sensor, example, etc. |
| `ports` | yes | Metadata-defined ports |
| `parameters` | yes | Schema-defined parameters |
| `visual` | yes | SVG mapping |
| `metadata` | yes | Additional non-breaking metadata |
| `extensions` | yes | Forward-compatible extension data |

### 6.2 Component Definition ID Rules

Definition IDs must be stable and namespace-like.

Examples:

```text
electrical.analog.components.resistor
electrical.analog.components.capacitor
electrical.analog.components.ground
mechanics.translational.components.mass
mechanics.translational.components.spring
mechanics.translational.components.damper
mechanics.rotational.components.inertia
```

Rules:

- Definition IDs must not contain spaces.
- Definition IDs must not depend on the display name.
- Definition IDs must not depend on the SVG filename.
- Renaming a display label must not change the definition ID.
- Moving a component visually in the library tree should require a migration or alias if saved projects already reference it.

#### 6.2.1 Definition ID vs Instance ID — Two Separate Concepts

This is a critical distinction. The `definition_id` defined in this document is **not** the same as the internal instance ID defined in `02_workspace_requirements.md` §8 (ADR-002 Hybrid ULID Identity Model).

| Concept | Format | Example | Defined In | Lifetime |
|---|---|---|---|---|
| Component **definition** ID | namespace-style, dotted | `electrical.analog.components.resistor` | `01` §6.2 | stable across releases (with aliases for renames) |
| Component **instance** ID (internal) | ULID with `cmp_` prefix | `cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0` | `02` §8.2 | unique per placement, never reused |
| Component **instance** display ID | human-readable counter | `resistor_3` | `02` §8.3 | unique within a project, monotonic per type |
| Component **instance** custom label | user-editable | `Input Resistor` | `02` §8.4 | optional, may be empty or duplicated |

When a user drags a component from the library to the workspace:

1. The library produces a drag payload referencing the definition by `definition_id` (a namespace string).
2. The workspace creates a new `ComponentInstance` through `WorkspaceModel.add_component(...)`.
3. `WorkspaceIdGenerator` produces:
   - a fresh ULID-style internal `id` (e.g., `cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0`)
   - a system-generated `display_id` (e.g., `resistor_3`)
   - an empty `custom_label`
4. The instance stores the `definition_id` it references.

The instance and the definition are different objects with different ID schemes. AI agents must not unify them.

A persisted `ComponentInstance` always carries:

- its own internal `id` (ULID, defined in `02` §8.2)
- its own `display_id` (defined in `02` §8.3)
- its own optional `custom_label` (defined in `02` §8.4)
- a reference to its definition through `definition_id` (defined in this document, §6.2)

Connections, undo/redo, selection, and graph assembly use the **instance internal ID**. The library, registry lookup, and migration use the **definition ID**.

(See `02_workspace_requirements.md` §8 for the full instance identity model. See ADR-002 in `06_data_flow_and_architecture.md` §19.)

### 6.3 Category Values

Initial category values:

```text
component
source
sensor
example
```

Future possible values:

```text
subsystem
probe
adapter
annotation
```

Unknown categories should be preserved on load and shown as unsupported if the current app cannot handle them.

---

## 7. Domain Requirements

The library must use domain IDs from `DomainRegistry`.

Initial supported domains:

```text
electrical_analog
electrical_digital
mechanical_translational
mechanical_rotational
```

Phase 1 may fully support only:

```text
electrical_analog
mechanical_translational
```

But the folder structure may already reserve `Digital` and `Rotational` for future expansion.

### 7.1 Domain Definition Schema

Recommended schema:

```json
{
  "id": "electrical_analog",
  "display_name": "Electrical Analog",
  "across_variable": "voltage",
  "through_variable": "current",
  "across_unit": "V",
  "through_unit": "A",
  "connection_color_token": "domain.electrical.analog.connection",
  "metadata": {},
  "extensions": {}
}
```

### 7.2 Bond Graph Preparation

Each domain definition must prepare for across/through semantics.

Examples:

| Domain | Across | Through |
|---|---|---|
| `electrical_analog` | voltage | current |
| `mechanical_translational` | velocity | force |
| `mechanical_rotational` | angular_velocity | torque |

These values support future implicit node equation generation and Bond Graph-style modeling.

---

## 8. Port Definition Schema

Ports must be defined by component metadata, not by SVG geometry.

Recommended schema:

```json
{
  "id": "p",
  "display_name": "Positive",
  "domain": "electrical_analog",
  "kind": "bidirectional",
  "relative_position": { "x": 1.0, "y": 0.5 },
  "required": true,
  "metadata": {},
  "extensions": {}
}
```

### 8.1 Required Port Fields

| Field | Required | Meaning |
|---|---:|---|
| `id` | yes | Stable port ID within the component definition |
| `display_name` | yes | User-facing port name |
| `domain` | yes | Domain compatibility identifier |
| `kind` | yes | Port kind |
| `relative_position` | yes | Visual anchor position relative to symbol bounds |
| `required` | yes | Whether unconnected port may be invalid |
| `metadata` | yes | Future metadata |
| `extensions` | yes | Forward compatibility |

### 8.2 Port ID Rules

Port IDs must be stable within a component definition.

Examples:

```text
p
n
flange_a
flange_b
support
shaft
road_contact
suspension_port
```

Rules:

- Port IDs must not be generated from display names at runtime.
- Port IDs must not be extracted from SVG element IDs.
- Existing port IDs must not be renamed without migration.
- Connections reference ports by `port_id`.

### 8.3 Port Kinds

Initial allowed kind:

```text
bidirectional
```

Future allowed kinds:

```text
signal_input
signal_output
physical_conservative
probe_output
```

### 8.4 Relative Position

`relative_position` uses normalized coordinates relative to the component symbol bounding box.

Recommended convention:

```text
x = 0.0 left edge
x = 1.0 right edge
y = 0.0 top edge
y = 1.0 bottom edge
```

This allows the same port metadata to work with scaled or rotated symbols.

### 8.5 Rotation Behavior

When the component rotates, port visual positions rotate with the component.

The logical `port_id` does not change.

### 8.6 Domain Compatibility

A port belongs to exactly one domain.

Connection validation must reject connections between ports with incompatible domains.

---

## 9. Parameter Definition Schema

Parameters must be schema-driven.

Recommended schema:

```json
{
  "id": "resistance",
  "display_name": "Resistance",
  "symbol": "R",
  "type": "float",
  "unit": "ohm",
  "default": 1000.0,
  "min": 0.0,
  "max": null,
  "step": 1.0,
  "required": true,
  "editable": true,
  "supports_expression": true,
  "description": "Electrical resistance",
  "metadata": {},
  "extensions": {}
}
```

### 9.1 Supported Initial Parameter Types

```text
float
int
bool
string
enum
expression
```

### 9.2 Parameter Rules

- Parameter definitions belong to the registry.
- Component instances store values and optional overrides.
- Units must be explicitly preserved.
- Invalid values must produce validation issues and must not crash the workspace.
- Unknown metadata must be preserved where safe.

### 9.3 Parameter Value Schema on Instance

When a component is placed, default values from the component definition are copied into the instance parameter values.

Recommended instance value shape:

```json
{
  "parameters": {
    "resistance": {
      "value": 1000.0,
      "unit": "ohm",
      "expression": null
    }
  }
}
```

---

## 10. SVG Usage

SVG files are visual symbols only.

Critical rules:

- Do not extract ports from SVG.
- Do not extract physics from SVG.
- Do not infer equations from SVG.
- Do not infer domains from SVG color.
- Do not use SVG filenames as component definition IDs.
- Ports come from component metadata.
- Parameters come from component definitions.
- Physics/equation behavior comes from explicit equation metadata in later phases.

### 10.1 SvgRegistry

`SvgRegistry` maps stable SVG IDs to packaged visual assets.

Recommended schema:

```json
{
  "svg_id": "electrical_resistor_default",
  "asset_path": "Electrical/Analog/Components/resistor.svg",
  "theme": "default",
  "view_box": "0 0 100 60",
  "supports_tint": true,
  "metadata": {},
  "extensions": {}
}
```

### 10.2 Visual Mapping on Component Definition

A component definition references SVG by `svg_id`.

```json
{
  "visual": {
    "svg_id": "mechanics_translational_spring_default",
    "default_variant": "default",
    "variants": ["default", "selected", "dark"]
  }
}
```

### 10.3 Visual Variants

Visual variants are allowed when they do not change physical meaning.

Example:

`Wheel Black` and `Wheel White` may be two visual variants of the same `Wheel` component definition.

They must not become separate physical components unless their ports, parameters, or equation behavior differ.

### 10.4 Attribution and Third-Party SVG Assets

If SVG symbols are adapted from external open-source libraries such as Modelica Standard Library resources, attribution and license files must be preserved according to the source license.

The preferred long-term path is to replace borrowed symbols with project-owned SVG assets after the MVP is functional.

#### 10.4.1 Attribution Metadata

When an SVG asset is adapted from a third-party source, the SvgRegistry entry must include attribution metadata so that license preservation is enforceable through the registry, not relegated to ad-hoc README notes.

Recommended attribution shape inside an SvgRegistry entry:

```json
{
  "svg_id": "electrical_resistor_default",
  "asset_path": "Electrical/Analog/Components/resistor.svg",
  "theme": "default",
  "view_box": "0 0 100 60",
  "supports_tint": true,
  "attribution": {
    "source": "Modelica Standard Library",
    "license": "BSD-3-Clause",
    "url": "https://github.com/modelica/ModelicaStandardLibrary",
    "modified": true,
    "license_file": "assets/licenses/MSL_LICENSE.txt"
  },
  "metadata": {},
  "extensions": {}
}
```

Rules:

- License files referenced by `license_file` must exist under a project-level `assets/licenses/` directory and must be included in any project distribution.
- Project-owned SVGs do not require an `attribution` block.
- If the source license requires source code disclosure or modification notes, those notes must be reachable from the `license_file` path.
- Removing a third-party SVG without removing its registry entry is forbidden; the entry must be deleted or replaced.

The registry validation step (§15.1) must verify that `license_file` paths exist when an `attribution` block is present.

### 10.5 Animation Metadata Reservation

SVG symbols may later support animation metadata such as spring compression, damper travel, wheel rotation, or road contact movement.

Phase 1 must not implement simulation-driven animation, but schemas should reserve metadata fields for it.

Recommended reserved shape:

```json
{
  "animation_metadata": {
    "supports_deformation": false,
    "deformation_handles": [],
    "state_bindings": []
  }
}
```

---

## 11. ModelLibraryPanel UI Requirements

`ModelLibraryPanel` displays available component definitions from `ComponentRegistry`.

### 11.1 Required UI Features

- Tree or grouped list organized by domain/category/subcategory
- Component search field
- SVG preview/icon per component where available
- Component display name
- Optional short description tooltip
- Drag support for placeable components
- Disabled visual state for invalid or unsupported definitions
- Optional filter by domain or category

### 11.2 UI Tree Source

The UI tree must be built from registry metadata, not by blindly scanning folders at runtime.

The folder structure may be used as an asset source during registry loading, but the panel displays validated registry entries.

### 11.3 Search Behavior

Search should match:

- display name
- short name
- definition ID
- tags
- description

Search must not mutate registry state.

### 11.4 Drag Payload

Dragging a component from the library must produce a typed payload.

Recommended payload:

```json
{
  "kind": "component_definition_ref",
  "definition_id": "electrical.analog.components.resistor",
  "requested_visual_variant": "default",
  "source_panel": "ModelLibraryPanel",
  "metadata": {},
  "extensions": {}
}
```

The payload must not contain a fully-created `ComponentInstance`.

The instance is created only when the workspace accepts the drop and executes an add-component command.

### 11.5 Invalid Drag/Drop

If the workspace rejects a drop:

- no component instance is created
- no workspace ID is consumed if avoidable
- the UI shows an invalid drop indicator
- the library remains unchanged

---

## 12. Component Placement Contract

When the workspace receives a valid component definition reference from the library:

```text
User drags component from ModelLibraryPanel
→ BlockDiagramWorkspace receives drop event
→ AddComponentCommand is created
→ WorkspaceModel.add_component(...) is called
→ ComponentRegistry resolves definition_id
→ WorkspaceIdGenerator creates internal ID and display_id
→ default parameters are assigned
→ ComponentInstance is added to WorkspaceModel
→ WorkspaceModel emits componentAdded
→ Workspace scene renders ComponentGraphicsItem
→ Validation is scheduled
→ Dirty state becomes true
```

### 12.1 Add Component Input

Recommended command input:

```json
{
  "definition_id": "mechanics.translational.components.mass",
  "position": { "x": 200.0, "y": 160.0 },
  "rotation": 0,
  "visual_variant": "default"
}
```

### 12.2 Add Component Output

The command creates a `ComponentInstance` with:

- new internal `id`
- generated `display_id`
- empty or default `custom_label`
- stable `definition_id`
- copied default parameter values
- position snapped to grid
- rotation
- visual mapping by `svg_id`
- timestamps if persistence layer supports them

---

## 13. Built-In Component Set

The initial library should include a small but coherent component set.

### 13.0 MVP Component Summary

The following table summarizes the Phase 1 MVP component set with port count, parameter count, and inclusion priority. AI agents must not silently skip or rename components in this set without an alias migration.

The component names below match the actual SVG asset filenames present in `features/SystemModelingModule/panels/ModelLibraryPanel/Models/` and the visible names in the library tree. AI agents must keep these names in sync.

| Domain | Component | Folder | Ports | Parameters | Phase 1 Priority |
|---|---|---|---|---|---|
| Electrical Analog | Capacitor | Components | `p`, `n` | `capacitance` | MVP |
| Electrical Analog | Ground Electric | Components | `p` | (none) | MVP |
| Electrical Analog | Inductor | Components | `p`, `n` | `inductance` | MVP |
| Electrical Analog | Resistor | Components | `p`, `n` | `resistance` | MVP |
| Electrical Analog | Current Sensor | Sensors | `p`, `n` | (none) | MVP |
| Electrical Analog | Voltage Sensor | Sensors | `p`, `n` | (none) | MVP |
| Electrical Analog | Constant Voltage | Sources | `p`, `n` | `voltage` | MVP |
| Electrical Analog | Ramp Voltage | Sources | `p`, `n` | `start_time`, `slope`, `start_value` | MVP |
| Electrical Analog | Signal Voltage | Sources | `p`, `n` | (input-driven) | MVP |
| Electrical Analog | Sine Voltage | Sources | `p`, `n` | `amplitude`, `frequency`, `phase`, `offset` | MVP |
| Electrical Analog | Step Voltage | Sources | `p`, `n` | `initial`, `final`, `start_time` | MVP |
| Mechanical Translational | Damper | Components | `flange_a`, `flange_b` | `damping` | MVP |
| Mechanical Translational | Fixed | Components | `flange` | (none) | MVP |
| Mechanical Translational | Mass | Components | `flange` | `mass` | MVP |
| Mechanical Translational | Spring | Components | `flange_a`, `flange_b` | `stiffness`, `free_length` | MVP |
| Mechanical Translational | Spring Damper | Components | `flange_a`, `flange_b` | `stiffness`, `damping`, `free_length` | MVP |
| Mechanical Translational | Wheel Black | Components | `flange`, `road_contact` | `radius`, `mass` | MVP |
| Mechanical Translational | Wheel White | Components | `flange`, `road_contact` | `radius`, `mass` | MVP |
| Mechanical Translational | Force Source | Sources | `flange` | `force` | MVP |
| Mechanical Translational | Step Force Source | Sources | `flange` | `initial`, `final`, `start_time` | MVP |
| Mechanical Translational | Random Road Source | Sources | `flange` | `amplitude`, `seed` | optional |
| Mechanical Translational | Position Sensor | Sensors | `flange` | (none) | MVP |
| Mechanical Translational | Velocity Sensor | Sensors | `flange` | (none) | MVP |
| Mechanical Translational | Force Sensor | Sensors | `flange_a`, `flange_b` | (none) | MVP |
| Mechanical Rotational | (all) | — | (TBD) | (TBD) | deferred (see §13.7) |
| Electrical Digital | (all) | — | (TBD) | (TBD) | deferred |

Notes on the table:

- Port and parameter names follow conventions in §8.2 and §9.
- `Phase 1 Priority` of `MVP` means the component is required for the initial visual modeling release.
- `Phase 1 Priority` of `optional` means the component may be deferred to a later Phase 1 sub-release if SVG assets or registry validation are not ready.
- `deferred` components have folder placeholders (Digital, Rotational) but their domain definitions and connection rules are not complete in Phase 1.
- `Wheel Black` and `Wheel White` are the **same physical component type** (wheel with road contact); they differ only in visual variant (see §10.2 visual variants). The library tree shows both as separate entries because they have distinct SVG asset filenames; their `definition_id` may share a common prefix with a `variant` discriminator.
- `Spring Damper` is a single component combining spring and damper behavior in one symbol; it is not a syntactic shortcut for connecting separate Spring and Damper instances.
- The exact parameter list per component is finalized when each component definition is written; this table is the high-level contract.

#### 13.0.1 Naming Conventions

Component names in this document, in the library tree UI, in SVG asset filenames, and in component definition `display_name` fields must match exactly.

The current canonical names are:

* `Capacitor`, `Ground Electric`, `Inductor`, `Resistor`
* `Current Sensor`, `Voltage Sensor`
* `Constant Voltage`, `Ramp Voltage`, `Signal Voltage`, `Sine Voltage`, `Step Voltage`
* `Damper`, `Fixed`, `Mass`, `Spring`, `Spring Damper`, `Wheel Black`, `Wheel White`

Renaming any of these requires a definition alias entry (see §15.3).

`definition_id` namespacing remains lowercase with dot separators (see §6.2):

* `electrical.analog.components.capacitor`
* `electrical.analog.components.ground_electric`
* `electrical.analog.sources.step_voltage`
* `mechanics.translational.components.spring_damper`
* `mechanics.translational.components.wheel_black`
* etc.

The mapping between display name and `definition_id` is:

* lowercase the display name
* replace spaces with underscores
* prepend the namespace path (`<domain>.<sub_domain>.<category>.`)

### 13.1 Electrical Analog / Components

Minimum MVP candidates:

- Capacitor
- Ground Electric
- Inductor
- Resistor
- Ideal Switch (optional, deferred to later Phase 1 sub-release)

### 13.2 Electrical Analog / Sources

Minimum MVP candidates:

- Constant Voltage — DC voltage source, parameter: `voltage`
- Ramp Voltage — linear ramp, parameters: `start_time`, `slope`, `start_value`
- Signal Voltage — externally driven (input port for control signal in Phase 2)
- Sine Voltage — sinusoidal, parameters: `amplitude`, `frequency`, `phase`, `offset`
- Step Voltage — step transition, parameters: `initial`, `final`, `start_time`

Note: Current Source is reserved for Phase 1.5 if needed; Phase 1 ships with the five voltage variants above to match the existing SVG library.

### 13.3 Electrical Analog / Sensors

Minimum MVP candidates:

- Current Sensor
- Voltage Sensor

### 13.4 Mechanics / Translational / Components

Minimum MVP candidates:

- Damper
- Fixed
- Mass
- Spring
- Spring Damper
- Wheel Black
- Wheel White

### 13.5 Mechanics / Translational / Sources

Minimum MVP candidates:

- Force Source
- Step Force Source
- Random Road Source (optional)

### 13.6 Mechanics / Translational / Sensors

Minimum MVP candidates:

- Position Sensor
- Velocity Sensor
- Force Sensor

### 13.7 Mechanics / Rotational

Rotational folders may exist in Phase 1, but components may be marked unsupported or experimental until their domain definitions and connection rules are complete.

### 13.8 Examples

Example entries may exist, but examples must be clearly distinguished from normal components.

An example entry may later instantiate multiple components and connections as a template, but Phase 1 may show them as disabled placeholders.

---

## 14. Component Definition Examples

### 14.1 Resistor Definition

```json
{
  "id": "electrical.analog.components.resistor",
  "schema_version": "0.1.0",
  "display_name": "Resistor",
  "short_name": "R",
  "description": "Ideal electrical resistor",
  "domain": "electrical_analog",
  "library_path": ["Electrical", "Analog", "Components"],
  "category": "component",
  "tags": ["electrical", "analog", "passive", "resistance"],
  "ports": [
    {
      "id": "p",
      "display_name": "Positive",
      "domain": "electrical_analog",
      "kind": "bidirectional",
      "relative_position": { "x": 0.0, "y": 0.5 },
      "required": true,
      "metadata": {},
      "extensions": {}
    },
    {
      "id": "n",
      "display_name": "Negative",
      "domain": "electrical_analog",
      "kind": "bidirectional",
      "relative_position": { "x": 1.0, "y": 0.5 },
      "required": true,
      "metadata": {},
      "extensions": {}
    }
  ],
  "parameters": [
    {
      "id": "resistance",
      "display_name": "Resistance",
      "symbol": "R",
      "type": "float",
      "unit": "ohm",
      "default": 1000.0,
      "min": 0.0,
      "max": null,
      "step": 1.0,
      "required": true,
      "editable": true,
      "supports_expression": true,
      "description": "Electrical resistance",
      "metadata": {},
      "extensions": {}
    }
  ],
  "visual": {
    "svg_id": "electrical_resistor_default",
    "default_variant": "default",
    "variants": ["default"]
  },
  "equation_metadata": null,
  "metadata": {},
  "extensions": {}
}
```

### 14.2 Translational Spring Definition

```json
{
  "id": "mechanics.translational.components.spring",
  "schema_version": "0.1.0",
  "display_name": "Spring",
  "short_name": "K",
  "description": "Ideal translational spring",
  "domain": "mechanical_translational",
  "library_path": ["Mechanics", "Translational", "Components"],
  "category": "component",
  "tags": ["mechanical", "translational", "stiffness"],
  "ports": [
    {
      "id": "flange_a",
      "display_name": "Flange A",
      "domain": "mechanical_translational",
      "kind": "bidirectional",
      "relative_position": { "x": 0.0, "y": 0.5 },
      "required": true,
      "metadata": {},
      "extensions": {}
    },
    {
      "id": "flange_b",
      "display_name": "Flange B",
      "domain": "mechanical_translational",
      "kind": "bidirectional",
      "relative_position": { "x": 1.0, "y": 0.5 },
      "required": true,
      "metadata": {},
      "extensions": {}
    }
  ],
  "parameters": [
    {
      "id": "stiffness",
      "display_name": "Stiffness",
      "symbol": "k",
      "type": "float",
      "unit": "N/m",
      "default": 1000.0,
      "min": 0.0,
      "max": null,
      "step": 1.0,
      "required": true,
      "editable": true,
      "supports_expression": true,
      "description": "Spring stiffness",
      "metadata": {},
      "extensions": {}
    }
  ],
  "visual": {
    "svg_id": "mechanics_translational_spring_default",
    "default_variant": "default",
    "variants": ["default"]
  },
  "equation_metadata": null,
  "metadata": {},
  "extensions": {}
}
```

---

## 15. Registry Loading Flow

Registry loading occurs during application bootstrap before feature modules are created.

Required flow:

```text
Application bootstrap
→ Load built-in domain definitions
→ Load built-in component definitions
→ Load built-in parameter schemas
→ Load SVG mappings
→ Validate registries
→ Create SystemModelingModule
→ Create ControllerDesignModule
→ Create SystemDesignerShell
```

### 15.1 Registry Validation

Registry validation must check:

- unique component definition IDs
- unique port IDs within each component definition
- valid domain references
- valid parameter definitions
- valid parameter defaults
- valid SVG references
- allowed category values or unsupported-category warning
- metadata and extensions preservation
- no duplicate SVG IDs
- no missing required fields

### 15.2 Load Failure Behavior

If a non-critical component definition fails validation:

- mark the component unavailable
- show a warning in the library panel if visible
- continue loading other valid definitions

If a critical registry cannot load:

- block application startup or enter safe degraded mode
- show a structured error message
- do not create feature modules with partially unknown registries

### 15.3 Definition Aliases

If a component definition ID is renamed, an alias/migration entry must preserve old project compatibility.

Recommended alias schema:

```json
{
  "old_id": "electrical.analog.resistor",
  "new_id": "electrical.analog.components.resistor",
  "introduced_in": "0.2.0",
  "metadata": {},
  "extensions": {}
}
```

---

## 16. Persistence Relationship

Projects persist component instances, not full duplicated component definitions.

A `ComponentInstance` references the reusable definition through `definition_id`.

Recommended persisted instance shape:

```json
{
  "id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
  "display_id": "resistor_1",
  "custom_label": "Input Resistor",
  "definition_id": "electrical.analog.components.resistor",
  "position": { "x": 100.0, "y": 200.0 },
  "rotation": 0,
  "parameters": {
    "resistance": {
      "value": 1000.0,
      "unit": "ohm",
      "expression": null
    }
  },
  "visual": {
    "svg_id": "electrical_resistor_default",
    "variant": "default"
  },
  "metadata": {},
  "extensions": {}
}
```

### 16.1 Missing Definition on Load

If a project references a missing component definition:

- preserve the raw component instance data
- mark the component as unresolved
- render a fallback placeholder if possible
- block graph validation for that component
- show a clear validation error
- do not silently delete the component

### 16.2 Unknown Fields

Unknown fields in component instances, component definitions, SVG mappings, and parameter definitions should be preserved where safe.

---

## 17. Relationship to Equation Extraction

Phase 1 component definitions may reserve `equation_metadata`, but must not execute it.

Phase 2 will extend component definitions with:

- equation templates
- internal state declarations
- variable declarations
- causality metadata
- output expressions
- nonlinear flags
- time-dependency metadata

### 17.1 Equation Metadata Placeholder

Phase 1 component definitions should set `equation_metadata` to `null` (preferred) or use this minimal placeholder for forward compatibility:

```json
{
  "equation_metadata": {
    "status": "reserved",
    "equation_definition_id": null,
    "linearity_hint": "unknown",
    "metadata": {},
    "extensions": {}
  }
}
```

**Note:** This is a Phase 1 placeholder schema for forward compatibility only. The full Phase 2 equation definition schema is specified in `04_model_equations_requirements.md` §3 through §9, including:

- equation templates and component-level equation declarations
- internal state declarations
- across/through variable mapping (see `04` §8.1)
- node constraint generation (see `04` §8.2)
- causality preparation metadata (see `04` §8.9, ADR-008)
- linearity flag and time-dependency classification (see `04` §6.5, §6.6)

Phase 1 must not populate any of these fields. Setting `equation_metadata` to `null` is the recommended default. If future Phase 2 work needs to attach equation definitions to library components, the schema will evolve under `04`'s ownership, not under `01`.

The full Phase 2 equation pipeline activates in Stage S3 (see `07_implementation_order.md` §9 and ADR-004 Equation Builder Ownership).

### 17.2 Ownership Rule

The component library may define equation metadata, but equation extraction belongs to `SystemModelingModule` equation pipeline.

The library must not generate DAE, ODE, state-space matrices, transfer functions, poles, zeros, or stability data.

---

## 18. Relationship to Probes and Sensors

Sensors are normal components with ports and parameters.

Probes are output observation concepts and may later live in `shared/probes`.

Phase 1 library may include sensor components, but they must not produce live simulation channels until the simulation artifact pipeline exists.

Future sensor/probe metadata may include:

```json
{
  "probe_metadata": {
    "output_quantity": "voltage",
    "output_variable": "across",
    "unit": "V",
    "metadata": {},
    "extensions": {}
  }
}
```

---

## 19. Modelica / Simscape Inspiration Boundary

The project may use Modelica and Simscape as architectural inspiration.

Allowed:

- similar domain hierarchy ideas
- similar component category naming
- simplified physical component concepts
- SVG symbol reuse where license allows
- attribution-preserving adaptation for MVP speed

Forbidden:

- assuming Modelica file syntax is the app schema
- importing the full Modelica complexity into Phase 1
- coupling the app to OpenModelica runtime
- coupling to OMSimulator, OMCSession, or any external Modelica runtime
- extracting physics from SVG symbols
- skipping project-owned component definitions
- copying assets without license attribution

---

## 20. Required Tests

### 20.1 Registry Tests

Tests must verify:

- component definitions load successfully
- invalid definitions are reported
- duplicate component IDs are rejected
- missing SVG IDs are reported
- unknown fields are preserved where allowed
- aliases resolve old IDs to new IDs

### 20.2 Component Schema Tests

Tests must verify:

- required fields exist
- parameter defaults match declared types
- invalid enum values are rejected
- units are preserved
- port IDs are unique within a component
- port domains exist in `DomainRegistry`

### 20.3 SVG Registry Tests

Tests must verify:

- SVG IDs resolve to packaged assets
- missing SVG files are reported
- visual variants do not create new physical definitions
- SVG files are not parsed for ports or physics

### 20.4 Library Panel Tests

Tests must verify:

- the panel displays registry entries
- search matches expected fields
- unsupported definitions show disabled state
- drag payload contains `definition_id`
- drag payload does not contain a full `ComponentInstance`

### 20.5 Placement Integration Tests

Tests must verify:

- dropping a valid component creates a `ComponentInstance`
- default parameters are assigned
- internal ID and display ID are generated
- position snaps to grid
- missing definition prevents placement
- workspace dirty state changes after valid placement

---

## 21. Acceptance Criteria

`01_library_requirements.md` is satisfied for Phase 1 when:

- built-in component definitions are loaded through registries
- the library panel displays validated registry entries
- component SVGs are resolved through `SvgRegistry`
- SVGs are used only as visual symbols
- ports are defined by metadata
- parameters are defined by schema
- drag/drop produces a definition-reference payload
- workspace placement creates instances through `WorkspaceModel`
- invalid definitions are reported without crashing the app
- unknown metadata and extensions are preserved where safe
- no equation, simulation, controller, or stability behavior is implemented in the library layer

---

## 22. Forbidden Rules

The library implementation must not:

- use SVG files as the source of physics
- extract ports from SVG files
- extract equations from SVG files
- use SVG filenames as stable component definition IDs
- create workspace component instances inside `ModelLibraryPanel`
- store live workspace state in the library panel
- duplicate component definitions into every instance unless required for migration
- import `shared.engine` during Phase 1
- implement simulation behavior in component definitions
- implement controller behavior in component definitions
- place `A`, `B`, `C`, or `D` matrices in library metadata
- create transfer functions or stability data from component definitions
- hardcode quarter-car topology into generic library components
- use display labels as stable references
- silently drop unsupported components on project load
- couple the library to OMSimulator, OMCSession, or any external Modelica runtime

### 22.1 ADR Cross-References

The forbidden rules above and the architectural decisions throughout this document are anchored in the following canonical ADRs (full list in `06_data_flow_and_architecture.md` §19):

| Library Concern | ADR | Notes |
|---|---|---|
| `shared.engine` import in Phase 1 | ADR-001 Phase 1 Engine Isolation | enforced by `shared/engine/__init__.py` ImportError guard |
| Stable definition_id and instance ID separation | ADR-002 Hybrid ULID Identity Model | see §6.2.1 |
| Library UI is browsing-only, not source of truth | ADR-003 Workspace UI/Data Separation | see §4.3, §4.4 |
| Library does not generate equations | ADR-004 Equation Builder Ownership | see §17.2 |
| Library does not generate state-space matrices | ADR-006 Controller Owns Transfer-Function and State-Space Builders | see §17.2, §22 |
| Across/through variable metadata in domain definitions | ADR-008 Bond Graph Causality | see §7.2 |
| No `A/B/C/D` in library metadata | ADR-010 Linearization Ownership | see §22 |
| Unit metadata preserved in parameter schema | ADR-011 Dimensional Analysis Policy | see §9 |
| `definition_id` references in `project.json` | ADR-012 Project Package Directory Format | see §16 |
| Library has no stability artifact responsibility | ADR-013 StabilityAnalysisArtifact | see §17.2, §22 |

---

## 23. Implementation Order

Recommended order for implementing the library:

1. Define domain schema and built-in domain definitions.
2. Define SVG registry schema and load packaged SVG assets.
3. Define component definition schema.
4. Define parameter definition schema.
5. Define port definition schema.
6. Implement `ComponentRegistry` loading.
7. Implement registry validation.
8. Implement basic built-in electrical analog components.
9. Implement basic built-in mechanical translational components.
10. Implement `ModelLibraryPanel` registry-based tree rendering.
11. Implement search/filtering.
12. Implement drag payload contract.
13. Integrate drag/drop with `BlockDiagramWorkspace` add-component command.
14. Add persistence compatibility tests for `definition_id` references.
15. Add missing-definition and unsupported-definition behavior.

---

## 24. Open Questions

The following implementation decisions remain open but must not violate this document:

### 24.1 Component Definition Storage Format

Should built-in component definitions initially be JSON files, Python dataclasses, or a hybrid?

Constraint:

- registries must expose the same validated schema regardless of source format
- definitions must remain testable without GUI

### 24.2 SVG Asset Source

Should MVP SVGs be adapted from Modelica resources with attribution, or should minimal project-owned SVGs be drawn immediately?

Constraint:

- SVGs are visual symbols only
- license attribution must be preserved
- replacement path must remain possible

### 24.3 Example Components vs Templates

Should `Examples/` entries appear as disabled examples in Phase 1, or should they instantiate predefined component groups?

Constraint:

- multi-component templates must use workspace commands and stable IDs
- examples must not bypass graph validation

### 24.4 Rotational and Digital Domains

Should `Rotational` and `Digital` entries be hidden, disabled, or shown as experimental in Phase 1?

Constraint:

- unsupported domains must not create invalid workspace objects silently

---

## 25. Final Rule

The component library is a registry-backed source of reusable definitions and visual symbols.

It is not the workspace model, not the equation engine, not the simulation engine, and not the controller layer.

Correct chain:

```text
Component/SVG assets
→ Registries
→ ModelLibraryPanel display
→ Drag payload with definition_id
→ WorkspaceModel creates ComponentInstance
→ SystemGraph assembly
→ Future equation/simulation/controller artifacts
```

No component library feature may bypass this chain.

