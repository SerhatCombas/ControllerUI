# 02_workspace_requirements.md

## 1. Purpose

The `BlockDiagramWorkspace` is the central interactive modeling canvas of the System Designer application. Users build engineering system diagrams by dragging components from the library, placing them on a grid-based workspace, and connecting compatible ports.

Phase 1 focuses on a stable visual system designer. It must support placement, selection, movement, connection, validation, undo/redo, and persistence. It must not implement symbolic equations, simulation, or controller execution yet.

The workspace is designed so that future phases can derive implicit nodes, equations, state-space models, transfer functions, and simulation-ready models from the same graph structure.

---

## 2. Strict Architecture Separation

The workspace must be split into two layers:

### 2.1 UI Layer

Responsible only for visual rendering and user interaction.

Recommended PySide6 classes:

* `BlockDiagramWorkspaceView` based on `QGraphicsView`
* `BlockDiagramWorkspaceScene` based on `QGraphicsScene`
* `ComponentGraphicsItem`
* `PortGraphicsItem`
* `ConnectionGraphicsItem`
* `GridBackgroundItem`
* Optional later: `SelectionBoxItem`, `MiniMapView`, `RubberBandSelectionItem`

The UI layer must not be the source of truth for model structure.

### 2.2 Data Layer

Responsible for the actual model state.

Core objects:

* `WorkspaceModel`
* `ComponentInstance`
* `PortInstance`
* `Connection`
* `ImplicitNode`
* `SystemGraph`
* `GraphAssembler`
* `GraphValidator`

The data layer must be testable without a running GUI.

---

## 3. Ownership and Source of Truth

`WorkspaceModel` is the source of truth for:

* components
* component positions
* component rotations
* connections
* parameter values
* labels
* selection-independent model state
* validation status

The UI must render the current `WorkspaceModel`. UI items must not store independent business state that can diverge from the model.

Allowed UI-only state:

* hover state
* temporary drag preview
* temporary connection preview
* current zoom level
* current pan offset
* rubber-band selection rectangle
* active interaction mode

---

## 4. Event / Signal Synchronization

The application must use Qt signals/slots for synchronization between the data layer and UI layer.

### 4.1 Required Workspace Signals

`WorkspaceModel` should emit signals such as:

* `componentAdded(component_id)`
* `componentRemoved(component_id)`
* `componentChanged(component_id)`
* `componentMoved(component_id, old_pos, new_pos)`
* `componentRotated(component_id, old_rotation, new_rotation)`
* `connectionAdded(connection_id)`
* `connectionRemoved(connection_id)`
* `connectionChanged(connection_id)`
* `selectionChanged(selection_snapshot)`
* `validationChanged(validation_report)`
* `modelReset()`
* `dirtyChanged(is_dirty)`

### 4.2 UI Reaction Rules

The scene must subscribe to these signals and update visual items accordingly.

Examples:

* When `componentAdded` fires, create a `ComponentGraphicsItem`.
* When `componentMoved` fires, update the corresponding item position.
* When `connectionAdded` fires, create a `ConnectionGraphicsItem`.
* When `validationChanged` fires, update warning/error highlights.
* When `modelReset` fires, rebuild the scene from the model.

### 4.3 No Direct Mutation Rule

UI items must not directly mutate graph state. User actions must be converted into commands, and commands must update `WorkspaceModel`.

---

## 5. Coordinate System and Grid

### 5.1 Coordinate Types

The system must distinguish between:

* Scene coordinates: QGraphicsScene logical coordinates.
* View coordinates: screen pixels after zoom/pan.
* Model coordinates: persisted logical workspace coordinates.

Model coordinates must be stored independently from screen pixels.

Recommended approach:

* Store positions in logical scene units.
* Use one grid cell as the basic layout unit.
* Persist component positions in model coordinates.

### 5.2 Grid

The workspace must display a visible grid.

Recommended defaults:

* Minor grid size: `20` logical units
* Major grid every: `5` minor grid cells
* Snap grid size: `20` logical units

### 5.3 Snap Behavior

Components dropped or moved by the user must snap to the nearest grid point by default.

Snap behavior:

* Drag from library → snap on drop
* Move component → snap on release
* Optional later: hold modifier key to disable snap

### 5.4 Zoom and Pan

The workspace must support:

* Mouse wheel zoom
* Trackpad zoom where available
* Middle mouse or space-drag pan
* Optional later: fit-to-view

Zoom and pan are view-only operations and must not affect undo/redo history.

---

## 6. Z-Ordering Rules

Visual stacking order must be deterministic.

Recommended z-order:

1. Grid background
2. Connections
3. Components
4. Ports
5. Selection outlines
6. Temporary connection preview
7. Tooltips / overlays

Rules:

* Ports must always remain visually accessible above components.
* Connections must normally render behind components.
* A selected connection may render above normal connections but below ports.
* A selected component may receive an outline instead of being moved above all other components.
* Temporary interaction previews must render above normal items.

---

## 7. Hit Testing and Interaction Tolerances

Hit testing must not require pixel-perfect clicking.

Recommended default tolerances:

* Port hover radius: 8–12 px in view coordinates
* Port connection snap radius: 12–16 px in view coordinates
* Connection selection tolerance: 6–10 px in view coordinates
* Component selection: bounding shape, not only SVG visible pixels

Tolerances must remain usable under zoom.

---

## 8. ID Generation Policy

Component and connection identifiers must use a hybrid ID strategy.

This is mandatory because the system needs both:

* stable machine-safe references for persistence, undo/redo, graph assembly, and future merge scenarios
* readable user-facing identifiers for UI, diagnostics, validation messages, and logs

### 8.1 Required ID Fields

Each component must have three separate identity fields:

```json
{
  "id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
  "display_id": "resistor_3",
  "custom_label": "Input Resistor"
}
```

Meaning:

* `id`: internal stable machine identifier
* `display_id`: system-generated human-readable identifier
* `custom_label`: optional user-editable label

### 8.2 Internal ID Format

Internal IDs must use ULID-style identifiers with a type prefix.

Examples:

```text
cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0
con_01HV7NA2K8M4X7GQ1DR9V5M2F6
```

Required prefixes:

* `cmp_` for components
* `con_` for connections
* `cmd_` may be used for command/debug IDs if needed

Reasons for ULID:

* practically collision-safe
* lexicographically sortable by creation time
* more readable and compact than UUID v4
* useful for debugging, save-file inspection, and future sync/merge workflows

Internal IDs must never be reused after deletion.

### 8.3 Display ID Policy

`display_id` is generated by the system for user readability.

Examples:

```text
resistor_1
resistor_2
mass_1
spring_4
conn_12
```

Rules:

* `display_id` is not the primary reference key.
* `display_id` should be monotonic per component type.
* Deleted display IDs should not be reused during normal editing.
* Paste/duplicate operations generate a new display ID using the next counter.
* `display_id` is normally not user-editable.
* If a project is partially recovered and counters are missing, counters must be reconstructed from existing display IDs.

Example:

* Create `resistor_1`
* Create `resistor_2`
* Delete `resistor_2`
* Create another resistor → `resistor_3`, not `resistor_2`

### 8.4 Custom Label Policy

`custom_label` is user-editable and purely descriptive.

Examples:

```text
Input Resistor
Suspension Spring
Wheel Mass
Battery Source
```

Rules:

* `custom_label` may be empty.
* `custom_label` may be duplicated.
* `custom_label` must not be used as a graph reference.
* UI should prefer showing `custom_label` when available, with `display_id` visible as secondary information.

### 8.5 ID Usage Rules

Use internal `id` for:

* connection references
* selection state
* undo/redo commands
* save/load cross-references
* API method parameters
* graph assembly
* serialization
* debug logs

Use `display_id` for:

* component info panel display
* validation messages shown to users
* status bar messages
* search/filter UI
* human-readable diagnostics

Use `custom_label` for:

* user-facing labels
* exports/printing
* diagram annotations
* preferred title in the info panel when present

### 8.6 Connection IDs

Connections must use the same hybrid pattern.

Example:

```json
{
  "id": "con_01HV7NA2K8M4X7GQ1DR9V5M2F6",
  "display_id": "conn_12"
}
```

Connection references must always use internal IDs and internal component IDs.

### 8.7 Implicit Node IDs

Implicit nodes are runtime-derived and not persisted as primary project data.

Therefore, implicit nodes may use simple runtime IDs:

```text
node_1
node_2
node_3
```

These IDs are valid only for the current assembled graph instance and must not be stored as stable project references.

### 8.8 Display ID Collision Handling

`display_id` should be unique during normal operation, but the system must not rely on this for correctness.

If duplicate display IDs appear because of corrupted files, partial recovery, migration, or manual JSON edits:

* internal IDs remain authoritative
* the project should still load where safe
* UI may show a warning
* UI may display suffixes such as `resistor_3 (2)` for disambiguation

---

## 9. Parameter Schema

Component parameters must be schema-driven. Parameter definitions belong to the component registry, while parameter values belong to component instances.

### 9.1 Parameter Definition

Each parameter definition should include:

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

Supported initial parameter types:

* `float`
* `int`
* `bool`
* `string`
* `enum`
* `expression`

### 9.2 Parameter Values

A component instance stores only values and optional overrides:

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

### 9.3 Units

The system must preserve units explicitly. The canonical internal unit must be defined by the parameter schema.

Examples:

* `1 kΩ` should be normalized or stored safely as `1000 ohm`.
* `1 mm` vs `0.001 m` must not be ambiguous.

Phase 1 does not need full dimensional analysis, but the schema must be designed so dimensional analysis can be added later.

### 9.4 Parameter Validation

Parameter validation rules must come from `ParameterDefinition` and must include:

* type check
* required check
* min/max check
* enum allowed values
* unit compatibility
* expression parse validity if expressions are enabled

Invalid parameters produce validation warnings/errors but must not crash the workspace.

---

## 10. Component Placement

### 10.1 Drag and Drop From Library

User behavior:

* User drags a component from `ModelLibraryPanel`.
* Workspace shows a drag preview.
* On valid drop, the component is created at the drop location.
* Position is snapped to the grid.
* A unique component ID is generated.
* Default parameters are assigned from the component definition.

Example IDs:

* `resistor_1`
* `resistor_2`
* `capacitor_1`
* `mass_1`

### 10.2 Invalid Drop

Invalid drop areas must reject the component. The cursor or preview should indicate the invalid drop state.

### 10.3 Component Overlap

Overlapping components should be allowed in Phase 1 to avoid overly restrictive editing behavior.

However:

* The system may optionally show a visual warning.
* Overlap must not invalidate the graph.
* Future auto-layout tools may resolve overlaps.

---

## 11. Component Data Model

Each `ComponentInstance` must include at minimum:

```json
{
  "id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
  "display_id": "resistor_1",
  "definition_id": "electrical.analog.components.resistor",
  "type": "Resistor",
  "display_name": "Resistor",
  "custom_label": "R1",
  "domain": "electrical_analog",
  "category": "component",
  "position": { "x": 100.0, "y": 200.0 },
  "rotation": 0,
  "parameters": {},
  "visual": {
    "svg_id": "resistor_default",
    "variant": "default"
  },
  "physical_attributes": {
    "boundary": "free",
    "motion": null,
    "directional": false,
    "source": false,
    "source_type": null
  },
  "locked": false,
  "tags": [],
  "annotations": {},
  "metadata": {},
  "extensions": {},
  "created_at": "ISO-8601 timestamp",
  "modified_at": "ISO-8601 timestamp"
}
```

### 11.1 Required Extensibility Rule

Unknown fields must be preserved during load/save when possible.

### 11.2 Physical Attributes

The `physical_attributes` object stores derived or declared properties used by the Component Info Panel and by future analysis layers.

#### `boundary` — Mechanical Boundary Condition

Mechanical components may have a boundary condition that constrains their motion.

Allowed values:

* `"free"` — component is unconstrained (default for masses, sprung objects)
* `"fixed"` — component is anchored to ground or a fixed reference (e.g., `Fixed` reference, walls)
* `"constrained"` — component is partially constrained (Phase 2+ feature)
* `null` — boundary is not applicable (electrical components, sensors)

#### `motion` — Motion Type

For mechanical components, indicates the type of motion supported.

Allowed values:

* `"translational"` — linear motion (e.g., Mass, Spring, Damper)
* `"rotational"` — angular motion (Phase 1.5+)
* `null` — motion is not applicable (electrical components, fixed references)

#### `directional` — Direction-Dependent Behavior

Indicates whether the component's behavior depends on connection direction.

Allowed values:

* `true` — component is direction-sensitive (e.g., diodes, one-way valves, force sources with sign convention)
* `false` — component is symmetric (e.g., resistor, capacitor, spring)

#### `source` — Source Component Flag

Indicates whether the component injects energy or signal into the system (rather than dissipating, storing, or transforming it).

Allowed values:

* `true` — component is a source (e.g., Voltage Source, Force Source, Step Voltage)
* `false` — component is passive or consumes energy (e.g., Resistor, Mass, Damper)

#### `source_type` — Source Subtype

If `source` is `true`, this field describes the source's signal pattern.

Allowed values:

* `"constant"` — DC value, no time variation (e.g., Constant Voltage)
* `"step"` — step transition at a defined time (e.g., Step Voltage, Step Force)
* `"ramp"` — linear ramp (e.g., Ramp Voltage)
* `"sine"` — sinusoidal source (e.g., Sine Voltage)
* `"signal"` — externally driven signal source (e.g., Signal Voltage, controlled by external input)
* `"random"` — stochastic source (e.g., Random Road Source)
* `null` — `source` is `false`

### 11.3 Physical Attributes Origin

The values for `physical_attributes` come from two sources:

* **Definition-level defaults**: declared in the `ComponentDefinition` (see `01_library_requirements.md` §6) and applied at instance creation
* **User-level overrides**: future Phase 1.5+ feature; in Phase 1, the user does not edit these directly

Phase 1 must:

* persist `physical_attributes` across save/load
* preserve unknown fields inside `physical_attributes` (forward compatibility)
* display values in the Component Info Panel (see §28)

Phase 1 must not:

* derive these values from SVG geometry
* compute these values from the graph topology
* allow the user to type arbitrary values; values are constrained to the enumerations above

---

## 12. SVG Usage

SVG files are visual symbols only.

Critical rules:

* Do not extract ports from SVG.
* Do not extract physics from SVG.
* Do not infer equations from SVG.
* Ports come from component metadata.
* Parameters come from component definitions.
* Physics/equation behavior will be defined by metadata and backend components in later phases.

SVG may be:

* rotated
* scaled
* theme-swapped
* rendered as normal or selected state

Example:

* `Wheel Black` and `Wheel White` are the same physical component type.
* They differ only by visual variant.

---

## 13. Port System

Ports must be defined by component metadata.

Each `PortDefinition` should include:

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

### 13.1 Port Kinds

For Phase 1, ports are primarily bidirectional physical ports.

Allowed initial kind:

* `bidirectional`

Future possible kinds:

* `signal_input`
* `signal_output`
* `physical_conservative`
* `probe_output`

### 13.2 Domain Rule

A port belongs to exactly one domain.

Initial supported domains:

* `electrical_analog`
* `mechanical_translational`

---

## 14. Connection System

### 14.1 User Behavior

The user draws connections from one port to another port.

The user cannot manually create explicit standalone nodes.

### 14.2 Connection Data Model

A connection must include:

```json
{
  "id": "conn_1",
  "source": {
    "component_id": "resistor_1",
    "port_id": "p"
  },
  "target": {
    "component_id": "capacitor_1",
    "port_id": "p"
  },
  "routing": {
    "style": "orthogonal",
    "waypoints": []
  },
  "label": "",
  "style": {},
  "metadata": {},
  "extensions": {}
}
```

### 14.3 Connection Validation Before Creation

A connection must be validated before it is created.

Invalid cases:

* Different port domains
* Connecting a port to itself
* Duplicate connection between the same two ports
* Connection to a missing component or missing port
* Connection involving a locked component if locking disables editing

Invalid connection attempts must be blocked.

### 14.4 Error Message Example

If the user attempts to connect an electrical port to a mechanical port:

`Incompatible domains: Electrical cannot connect to Mechanical.`

---

## 15. In-Progress Connection Interaction

When the user starts dragging from a port:

* A temporary ghost connection must be shown.
* Valid target ports should be highlighted green.
* Invalid target ports should be highlighted red.
* The source port should be highlighted.

Interaction rules:

* Release on valid target port → create connection.
* Release on empty workspace → cancel connection.
* Press `Esc` → cancel connection.
* Release on invalid target → cancel and show status message.

---

## 16. Connection Routing

### 16.1 Initial Routing Strategy

Use orthogonal / Manhattan routing as the preferred default for engineering diagrams.

Phase 1 acceptable fallback:

* Straight line routing may be used temporarily only if the architecture allows replacing it later with orthogonal routing.

Recommended routing styles:

* `straight`
* `orthogonal`
* future: `bezier`

### 16.2 Waypoints

Connections should support optional routing waypoints even if manual editing is not implemented immediately.

This allows future support for:

* manual wire shaping
* avoiding components
* routing persistence
* improved diagram readability

### 16.3 Component Movement

When a connected component moves:

* The connection graphics must update immediately.
* The underlying connection data does not change unless manual waypoints are edited.

---

## 17. Junction and Implicit Node Behavior

### 17.1 Internal Node Concept

Nodes are implicit and not directly created by the user.

An implicit node is a connected set of ports that share the same physical potential / across variable.

Examples:

Electrical:

* resistor_1.p
* capacitor_1.p
* voltage_source_1.p

Mechanical translational:

* spring_1.flange_a
* mass_1.flange
* damper_1.flange_a

### 17.2 Multiple Ports Per Node

Multiple ports may belong to the same implicit node.

This is required for Modelica/Simscape-like physical modeling.

### 17.3 Visual Junctions

Because the user cannot create explicit nodes, visual junction dots may be generated automatically when a connection graph branches.

Rules:

* Junction graphics are visual only.
* Junctions must not be stored as user-created nodes.
* Implicit nodes are reconstructed from connections.
* Junction appearance must be derived from connection topology.

---

## 18. Implicit Node Assembly

The graph layer must compute implicit nodes from connections.

Recommended approach:

* Treat each port reference as a vertex.
* Treat each connection as an undirected edge.
* Use union-find / disjoint set to group connected ports.
* Each connected group becomes one implicit node.

### 18.1 Node Domain Rule

All ports in an implicit node must belong to the same domain.

Mixed-domain nodes are invalid.

### 18.2 Cross-Domain Components

Mixed-domain nodes are forbidden, but multi-domain components are allowed.

Examples of future cross-domain components:

* electric motor
* actuator
* sensor transducer
* transformer
* gyrator

Such components must expose separate ports for each domain and define coupling internally through component equations, not through mixed-domain node merging.

---

## 19. Graph Assembly

`GraphAssembler` must convert workspace state into a `SystemGraph`.

The graph must include:

* component instances
* port references
* connections
* implicit nodes
* validation metadata

Graph assembly must be independent from UI.

---

## 20. Validation Strategy

Validation happens in layers.

### 20.1 Real-Time Validation

Run immediately during interaction:

* incompatible domain check
* duplicate connection check
* self-connection check
* missing target port check

These block invalid actions before mutation.

### 20.2 Incremental Workspace Validation

Run after graph-affecting changes:

* missing required reference component
* broken connections
* dangling required ports
* duplicate IDs
* invalid parameter values

### 20.3 Pre-Simulation Validation

Future Phase 2/3 validation:

* equation solvability
* algebraic loops
* singular systems
* missing input/output mapping
* unsupported nonlinearities for selected analysis tools

### 20.4 Initial Domain Reference Rules

Electrical Analog:

* At least one `Ground Electric` component must exist for a valid electrical model.

Mechanical Translational:

* At least one `Fixed` reference component must exist for a valid mechanical model.

### 20.5 Validation Result Severity

Validation results must have severity:

* `info`
* `warning`
* `error`

Errors block simulation in later phases.
Warnings do not necessarily block editing.

### 20.6 Validation Timing and Debouncing

Validation must not freeze the UI.

Recommended strategy:

* Real-time connection validation is synchronous and lightweight.
* Incremental workspace validation is scheduled/debounced after model changes.
* Expensive validation should run asynchronously or be deferred.
* `validationChanged` should preferably emit a structured report with stable issue IDs, and may support diffs later.

Initial debounce target:

* 100–300 ms after the last graph-changing edit.

### 20.7 Cycle and Algebraic Loop Preparation

Full algebraic-loop and solvability checks belong to Phase 2/3.

However, Phase 1 should keep enough graph metadata to allow future cycle/algebraic-loop diagnostics without changing the workspace data model.

---

## 21. Selection System

### 21.1 Single Selection

Clicking a component or connection selects it.

### 21.2 Multi-Selection

The system must support multi-selection in Phase 1 or be architected so it can be added without refactoring.

Recommended behavior:

* Shift-click: add/remove item from selection
* Drag empty area: rubber-band selection
* Cmd/Ctrl+A: select all

Multi-selection enables:

* group move
* bulk delete
* copy/paste
* future grouping/subsystems

### 21.3 Selection Model

Selection state should be managed by a dedicated `SelectionModel`, not scattered across graphics items.

Selection changes must update:

* item highlights
* component info panel
* status area

### 21.4 Selection and Connected Wires

Selecting a component does not automatically select its connected connections.

However:

* Moving a selected component must visually update connected connections.
* Deleting a selected component must atomically delete attached connections.
* Copying selected components should copy only connections between selected components.
* Context menu behavior must be based on the exact selection set.

---

## 22. Move, Delete, and Atomic Operations

### 22.1 Move

Moving a component updates its position in `WorkspaceModel`.

Move command should commit on mouse release, not every mouse move.

### 22.2 Delete Component

Deleting a component must also delete all connections attached to its ports.

This must be an atomic operation.

No half-deleted state is allowed.

### 22.3 Delete Connection

Deleting a connection updates:

* workspace model
* implicit nodes after graph rebuild
* scene rendering
* validation report

---

## 23. Rotation

Rotation behavior:

* `R` rotates selected component by +90°.
* `Shift + R` rotates selected component by -90°.
* Rotation can also be edited numerically in the component information panel.

Rotation must update:

* component orientation
* port visual positions
* connected connection rendering

---

## 24. Copy / Paste / Duplicate

Phase 1 should include or prepare for copy/paste.

Recommended shortcuts:

* Cmd/Ctrl+C: copy selected components and connections between them
* Cmd/Ctrl+V: paste with new IDs and offset
* Cmd/Ctrl+D: duplicate selected items

Rules:

* Pasted components must receive new unique IDs.
* Connections between copied components should be preserved.
* Connections to non-copied external components should not be preserved unless explicitly supported later.

---

## 25. Undo / Redo

Undo/redo must be implemented with the Command Pattern.

Required commands:

* `AddComponentCommand`
* `MoveComponentCommand`
* `RotateComponentCommand`
* `DeleteComponentCommand`
* `AddConnectionCommand`
* `DeleteConnectionCommand`
* `ChangeParameterCommand`
* `PasteSelectionCommand`

### 25.1 Compound Commands

Operations that affect multiple model objects must be represented as compound commands.

Examples:

* Delete component + attached connections
* Paste multiple components + internal connections
* Move multiple selected components

### 25.2 Non-Undoable Operations

The following must not be undoable:

* zoom
* pan
* hover
* selection-only changes
* temporary connection preview

### 25.3 Parameter Edit Granularity

Parameter changes should commit as one undo step when editing is finished, not on every keystroke.

Recommended commit triggers:

* focus lost
* Enter pressed
* slider released
* explicit apply

### 25.4 Undo Stack Limits

The undo stack must have a configurable maximum depth.

Recommended initial value:

* 100 commands

Large compound commands may count as one undo step but must be memory-aware.

---

## 26. Keyboard Shortcuts

Minimum Phase 1 shortcuts:

* Delete / Backspace: delete selected items
* R: rotate +90°
* Shift+R: rotate -90°
* Esc: cancel current interaction
* Cmd/Ctrl+Z: undo
* Cmd/Ctrl+Shift+Z or Cmd/Ctrl+Y: redo
* Cmd/Ctrl+C: copy
* Cmd/Ctrl+V: paste
* Cmd/Ctrl+D: duplicate
* Cmd/Ctrl+A: select all
* Space + drag or middle mouse: pan

Future shortcuts:

* F: fit selection / fit all
* G: toggle grid
* L: auto-layout
* H: show/hide library

---

## 27. Context Menu

Right-click context menus should be supported.

Component context menu:

* Delete
* Duplicate
* Rotate clockwise
* Rotate counter-clockwise
* Edit label
* Lock / Unlock
* Reset parameters

Connection context menu:

* Delete
* Edit label
* Reset routing

Workspace context menu:

* Paste
* Select all
* Fit all
* Toggle grid

---

## 28. Component Info Panel Integration

The bottom component information panel shows properties of the current selection.

For a single component:

* `Selected` — display name (e.g., `Capacitor`)
* `Component ID` — display ID (e.g., `capacitor_1`); the internal ULID may be shown on hover or in a debug mode
* `Custom Label` — user-editable label, if set
* `Domain` — domain ID (e.g., `Electrical`)
* `Category` — category from the registry (e.g., `Components`, `Sensors`, `Sources`)
* `Position` — `x`, `y` in scene coordinates
* `Rotation` — degrees
* `Ports` — port count (e.g., `2`)
* `Boundary` — from `physical_attributes.boundary` (e.g., `Free`, `Fixed`)
* `Motion` — from `physical_attributes.motion` (e.g., `Translational`, `-`)
* `Directional` — from `physical_attributes.directional` (`Yes`/`No`)
* `Source` — from `physical_attributes.source` (`Yes`/`No`)
* `Source Type` — from `physical_attributes.source_type` (e.g., `Step`, `Sine`, `-`)
* `Parameters` — list of parameter values with units
* `Status` — validation status of the selected component (see §32.3.2)

For a connection:

* `Connection ID` — display ID
* `Source` — `component_display_id.port_id`
* `Target` — `component_display_id.port_id`
* `Domain`
* `Routing Style`
* `Status` — validation status

For multi-selection:

* number of selected components
* number of selected connections
* shared editable properties where applicable
* aggregated validation summary (e.g., `2 components, 1 with warnings`)

The Component Info Panel must:

* update on `selectionChanged` and on `componentChanged` / `connectionChanged` events
* remain readable even when no item is selected (showing project-level summary)
* not be hideable in Phase 1 (see UI panel visibility rules in `06 §4.1`)

---

## 29. Persistence

### 29.1 Project Package Format

Projects are stored as a directory-based package with `.systemdesign/` extension.

Structure:

```text
project.systemdesign/
├── project.json           # core model file
├── results/               # simulation results
│   └── *.h5
├── exports/               # user-exported plots, CSVs, etc.
└── recovery/              # autosave recovery files
    └── autosave.json
```

#### project.json (Core Model File)

The `project.json` file inside the package contains the core project state:

```json
{
  "schema_version": "0.2.0",
  "application_version": "0.2.0",
  "components": [],
  "connections": [],
  "controller_settings": {},
  "io_selection": {},
  "simulation_settings": {},
  "plot_layout": {},
  "view": {},
  "result_refs": [],
  "metadata": {},
  "extensions": {}
}
```

Field semantics:

* `schema_version`: project schema version, currently `0.2.0` for the package format
* `application_version`: application version that wrote the file
* `components`: list of `ComponentInstance` objects (see §11)
* `connections`: list of `Connection` objects (see §14.2)
* `controller_settings`, `io_selection`, `simulation_settings`, `plot_layout`: configuration sections owned by `ControllerDesignModule` (see `03_configuration_requirements.md`)
* `view`: persisted view state such as zoom, pan, viewport center (see §29.6)
* `result_refs`: list of references to simulation results stored in `results/` (see `05_simulation_and_results_requirements.md` §13)
* `metadata`, `extensions`: forward-compatibility containers for future fields

#### Subdirectory Roles

* `results/`: HDF5 simulation result files referenced from `result_refs`
* `exports/`: user-generated exports (PNG plots, CSV data, PDF reports)
* `recovery/`: autosave recovery state, written by the autosave timer

#### Migration From Legacy Single-File Format

Phase 1 single-file `.systemdesign` JSON projects must be migrated to the package format on load.

Migration steps:

* The application detects whether the path is a directory bundle or a legacy JSON file.
* For a legacy file:
  * Original JSON content becomes `project.json` inside a new `project.systemdesign/` directory.
  * If older versions stored simulation results inline, they are extracted into `results/*.h5`.
  * Recovery data, if present, is moved into `recovery/`.
  * The user is warned once that the legacy file has been converted.
  * Unknown fields are preserved during migration.
* The original legacy file must remain untouched until the new package is successfully written.
* If conversion fails, the user is notified and no destructive change is committed.

(Aligns with `05_simulation_and_results_requirements.md` §12.5 and §12.6.)

### 29.2 Nodes Are Not Persisted

Implicit nodes must not be saved as primary project data.

They are reconstructed from connections on load.

### 29.3 Schema Versioning

Every saved file must contain `schema_version`.

Future migrations must follow this pattern:

* detect schema version
* migrate to current version
* preserve unknown fields where possible
* report partial migration warnings

#### 29.3.1 to_dict / from_dict Contract

`WorkspaceModel.to_dict()` and `WorkspaceModel.from_dict(data)` must implement schema-version-aware serialization to support backward compatibility as the schema evolves.

`to_dict()` rules:

* must always emit the **current** `schema_version` (currently `0.2.0`)
* must always emit the current `application_version`
* must preserve unknown fields read during the most recent `from_dict()` call (round-trip preservation)
* must emit a deterministic, human-diff-friendly JSON structure (stable key order, no random IDs in unrelated fields)
* must not emit transient UI state (selection, hover, drag preview)

`from_dict(data)` rules:

* must read `data["schema_version"]` first
* if `schema_version` is older than current, run the migration chain (e.g., `0.1.0 → 0.2.0 → current`)
* if `schema_version` is unknown or newer than current, raise a structured error with a clear message
* must preserve unknown fields under `metadata` and `extensions` for round-trip safety
* must clear undo stack and reset dirty state to `false` after successful load
* must not partially apply state on failure; either the model fully loads or it remains unchanged

Recommended migration registry pattern:

```python
class WorkspaceModelMigrations:
    """Registry of schema migrations for project files."""
    
    MIGRATIONS = {
        ("0.1.0", "0.2.0"): migrate_0_1_0_to_0_2_0,
        # Future entries added here as schema evolves.
    }
    
    @classmethod
    def migrate(cls, data: dict, target_version: str) -> dict:
        current = data["schema_version"]
        while current != target_version:
            next_step = cls._find_next_step(current, target_version)
            if next_step is None:
                raise SchemaMigrationError(
                    f"No migration path from {current} to {target_version}"
                )
            data = cls.MIGRATIONS[(current, next_step)](data)
            current = next_step
        return data
```

This pattern ensures:

* every schema version transition is testable in isolation
* multi-step migrations (e.g., `0.1.0 → 0.2.0 → 0.3.0`) compose automatically
* migration failures are diagnosable
* the migration registry is the single source of truth for backward compatibility

Migration tests are required (see §36.9).

### 29.4 Unknown Field Preservation

Unknown fields in components, connections, metadata, and extensions should be preserved during load/save when possible.

### 29.5 Partial Load Failure

If part of a file is invalid:

* The application should load all valid content where safe.
* Invalid items should be skipped or quarantined.
* The user must receive a clear warning report.
* The app must not crash.

### 29.6 View State Persistence

Project-level view state may be saved, but it must be separate from model state.

Allowed per-project view fields:

* last viewport center
* zoom level
* grid visibility
* selected plot layout

Selection state should not be persisted by default.

User preferences such as panel visibility, theme, and editor layout should be stored as user settings, not inside the project file, unless explicitly project-specific.

### 29.7 Dirty State Semantics

Dirty state must track meaningful project changes.

Dirty operations:

* add/delete/move/rotate component
* add/delete/modify connection
* parameter changes
* label changes
* simulation/configuration changes saved in project

Non-dirty operations:

* zoom
* pan
* hover
* temporary previews
* selection changes

After successful save, dirty becomes false.
If undo returns the document to the saved state, dirty should become false.
Recovered autosave files should open as dirty until explicitly saved.

### 29.8 File Concurrency

The application should detect if the project package was modified externally after it was opened.

Minimum behavior:

* store last known modification timestamp of `project.json`
* warn before overwriting externally modified files
* never silently overwrite external changes

---

## 30. Autosave and Recovery

The workspace should support autosave.

Recommended behavior:

* Autosave every 600 seconds if project is dirty.
* Autosave to a recovery file inside `project.systemdesign/recovery/`, separate from the main `project.json`.
* On startup after crash, offer recovery from the recovery directory.

Phase 1 may implement the persistence architecture first and autosave shortly after.

Autosave policy:

* Use a separate recovery file under `recovery/`.
* Keep only the latest recovery file per project initially.
* Avoid autosaving on every small edit.
* Do not mark the main `project.json` as saved after autosave.

---

## 31. Performance Targets

Initial target scale:

* 100 components
* 300 connections
* responsive editing at approximately 60 FPS on normal diagrams

Stretch target:

* 1000 components
* 3000 connections with viewport culling and optimized redraws

### 31.1 Rebuild Strategy

Avoid full graph rebuild on every mouse move.

Recommended:

* During drag: update graphics only.
* On drag commit: update model once.
* After model change: rebuild affected graph structures or schedule validation.

### 31.2 Viewport Optimization

Future support:

* viewport culling
* simplified connection rendering at low zoom
* level-of-detail rendering for large diagrams

---

## 32. Error Handling and Status Reporting

Errors must not be silent.

User-visible error locations:

* status bar / status area
* component info panel
* visual highlights on invalid items
* optional non-blocking toast messages

Modal dialogs should be avoided for routine validation errors.

### 32.1 Error Severity

Use severity levels:

* info
* warning
* error
* fatal

Fatal errors are unexpected and should be logged.

### 32.2 Status Bar

The application shell must include a status bar at the bottom of the main window.

Status bar responsibilities:

* show the current project file name and dirty indicator (e.g., `quarter_car.systemdesign *`)
* show the current interaction mode (e.g., `Idle`, `Connecting…`, `Dragging component`)
* show the most recent action or message (e.g., `Component "resistor_1" added`, `Connection blocked: incompatible domains`)
* show validation summary (e.g., `2 warnings, 1 error`)
* show backend/connection status when relevant (e.g., `Engine: ready`, `Engine: simulating…` in Phase 2)

Status bar rules:

* status bar is always visible in Phase 1; it must not be hideable
* most recent message must persist for at least 4 seconds before being replaced by passive content
* error and fatal messages must remain until the user dismisses them or another error replaces them
* status bar messages must not block UI interaction
* status bar text must be selectable for copy/paste

### 32.3 Validation Indicators

Validation results must be visible in three coordinated locations:

#### 32.3.1 Visual Highlights on the Workspace

Components and connections with active validation issues must be visually marked.

Recommended visual conventions:

| Severity | Workspace Marking |
|---|---|
| `info` | small blue dot near the component, no border change |
| `warning` | yellow/amber outline around the component or connection |
| `error` | red outline around the component or connection |
| `fatal` | red outline plus a small badge indicating the error code |

Highlights must:

* update immediately when the underlying validation state changes
* not interfere with normal selection visuals (use additive layering)
* respect z-ordering rules from §6 (highlights go in the selection layer)

#### 32.3.2 Component Info Panel Status Field

The Component Info Panel (see §28) must include a `Status` field showing the most relevant validation result for the selected component or connection.

Examples:

* `OK`
* `Warning: connection has no electrical ground reference`
* `Error: port "p" is not connected`
* `Selected component is locked`

If no item is selected, the panel may show overall workspace validation summary (e.g., `Workspace: 0 errors, 1 warning`).

#### 32.3.3 Status Bar Validation Summary

The status bar must show a counted summary of active validation issues across the workspace.

Examples:

* `Workspace OK`
* `1 warning`
* `2 warnings, 1 error`
* `Validation in progress…` (during debounced revalidation)

Clicking the validation summary should open a structured validation panel listing all current issues with navigation links to the relevant components/connections. The validation panel itself is optional in Phase 1 but must be architecturally allowed.

### 32.4 Validation Indicator Lifecycle

Validation indicators must be driven by `WorkspaceModel.validationChanged` signals (see §4.1).

Lifecycle:

* on `validationChanged`, all three indicator surfaces (workspace highlights, info panel, status bar) must update within the same Qt event loop iteration when possible
* indicators must not flicker during debounced revalidation; intermediate states should not be shown
* when an item with active validation issues is deleted, its highlights must be cleared atomically with the deletion

---

## 33. Logging and Diagnostics

The system should log important workspace events:

* component creation/deletion
* connection creation/deletion
* validation errors
* load/save failures
* schema migration warnings
* unexpected exceptions

A future diagnostic mode should allow exporting:

* workspace model JSON
* assembled graph summary
* validation report
* selection state

---

## 34. Accessibility and Localization

### 34.1 Accessibility

The workspace should not rely only on color.

Domain distinction should use:

* color
* port shape or icon
* tooltip text
* labels where useful

Keyboard navigation should be considered for core actions.

### 34.2 Localization

User-facing strings must not be hardcoded inside business logic.

Validation messages should be routed through a message catalog or translation-ready layer.

Example message key:

`error.connection.incompatible_domains`

---

## 35. Domain Extensibility

The system currently supports:

* Electrical Analog
* Mechanical Translational

The architecture must allow future domains without rewriting workspace logic.

Future possible domains:

* Mechanical Rotational
* Hydraulic / fluid
* Thermal
* Signal / control

Domain definitions should be registry-driven, including:

* domain ID
* display name
* color
* port visual style
* compatibility rules

### 35.1 Cross-Domain Coupling

Cross-domain coupling must not happen by connecting different domain ports into one node.

Instead, cross-domain components must define multiple domain-specific ports and internal coupling behavior.

Examples:

* Motor: electrical ports + mechanical rotational shaft port
* Actuator: electrical control + mechanical translational output
* Sensor: physical input + signal output

---

## 36. Test Requirements

The workspace must be testable at the data layer without GUI.

Required test categories:

### 36.1 Component Tests

* create component from registry definition
* assign default parameters
* generate unique IDs
* rotate component
* update position

### 36.2 Connection Tests

* valid same-domain connection succeeds
* different-domain connection is rejected
* self-connection is rejected
* duplicate connection is rejected
* deleting component removes attached connections

### 36.3 Node Assembly Tests

* two connected ports create one implicit node
* chained connections create one implicit node
* disconnected groups create separate nodes
* mixed-domain node is invalid

### 36.4 Serialization Tests

* save/load round trip with package format
* unknown field preservation
* schema version present
* missing component reference handled safely
* legacy single-file project migrates to package format
* `result_refs` round-trip without loss
* missing HDF5 result files in `results/` are handled gracefully (status reported, not crash)

### 36.5 Undo/Redo Tests

* add component undo/redo
* move component undo/redo
* add connection undo/redo
* delete component with attached connections undo/redo
* parameter change undo/redo

### 36.6 UI Smoke Tests

Where possible:

* scene creates graphics item for added component
* scene removes graphics item for deleted component
* selection update reflects model selection

### 36.7 Performance and Stress Tests

* load 100 components and 300 connections within acceptable time
* load 1000 components as stretch/performance benchmark
* move selected component with attached connections without visible freezing

### 36.8 Property-Based / Fuzz Tests

Future tests should generate random valid and invalid graphs and verify:

* save/load round trip
* no dangling references after delete
* implicit node assembly consistency
* validation never crashes

### 36.9 Migration Tests

Every schema migration must include tests from previous schema versions to the current version.

Specific migration tests required for Phase 2:

* legacy single-file `.systemdesign` JSON loads and converts to package format
* original legacy file remains untouched on conversion failure
* unknown fields preserved across migration
* `result_refs` populated correctly when legacy file references inline results

### 36.10 Signal Contract Tests

Signal order should be deterministic where it matters.

Example:

* `componentAdded` must occur before selection updates that reference the new component.
* `modelReset` should cause a full scene rebuild and avoid duplicate item creation.

---

## 37. Connection Re-Targeting

Existing connections should support endpoint re-targeting.

User behavior:

* User drags one endpoint of an existing connection.
* A temporary preview follows the cursor.
* Valid and invalid target ports are highlighted.
* Releasing on a valid port changes the endpoint.
* Releasing on invalid area cancels the operation.

Data behavior:

* The connection ID should remain stable.
* The operation should mutate the endpoint, not delete and recreate the connection.
* The operation must be undoable via `ModifyConnectionCommand`.
* Validation rules are the same as new connection creation.

---

## 38. Locking Behavior

Locked components are protected from accidental editing.

Rules:

* Locked components cannot be moved.
* Locked components cannot be rotated.
* Locked components cannot be deleted unless explicitly unlocked first.
* Locked component parameters are read-only.
* Existing connections may remain attached.
* Creating new connections to locked components should be allowed only if `allow_connections_when_locked` is true in settings; default should be false.

Locked items should show a lock indicator.

---

## 39. Connection Visual Properties and Bond Graph Preparation

Connections must support visual and future semantic extensions.

Connection style may include:

```json
{
  "line_width": null,
  "color_override": null,
  "dash_pattern": null,
  "arrow_style": null,
  "causality_marker": null
}
```

Default visual style should come from the domain registry.

For future Bond Graph support, the data model should reserve extension fields for:

* effort variable metadata
* flow variable metadata
* causality marker
* power direction marker
* transformer/gyrator metadata
* coupling coefficient metadata

Phase 1 does not interpret these values, but must not block storing them in `metadata` or `extensions`.

---

## 40. Subsystem and Grouping Strategy

Hierarchical subsystems and grouping are out of scope for Phase 1.

However, the data model must avoid decisions that make future hierarchy impossible.

Future subsystem requirements may include:

* group selection into subsystem
* nested workspace graphs
* exposed subsystem ports
* collapse/expand subsystem view
* local component IDs inside subsystem scope

Phase 1 must not implement subsystem behavior unless explicitly requested.

---

## 41. Phase 1 Out of Scope

The following are explicitly out of scope for Phase 1:

* symbolic equation generation
* DAE reduction
* numerical simulation
* transfer function generation
* state-space generation
* PID execution
* LQR / pole placement / MPC execution
* nonlinear solver integration

The workspace must be designed so these can be added later through `shared/engine` without refactoring the UI architecture.

---

## 42. Acceptance Criteria

Phase 1 workspace is acceptable when:

* components can be dragged from library to workspace
* components snap to grid
* components can be selected, moved, rotated, copied, pasted, and deleted
* compatible ports can be connected
* incompatible connections are blocked before creation
* implicit nodes can be assembled from connections
* graph validation reports missing references and invalid states
* component info panel updates from selection
* undo/redo works for core editing actions
* project can be saved and loaded as a `.systemdesign/` package directory
* legacy single-file `.systemdesign` JSON projects can be migrated automatically to the package format
* `project.json` round-trips through save/load without data loss
* `result_refs` field is preserved across save/load (empty array in Phase 1)
* unknown fields in components, connections, metadata, and extensions are preserved
* schema version is always present and validated on load
* data layer tests pass without GUI
* UI remains responsive during normal editing
