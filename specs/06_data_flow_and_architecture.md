# 06_data_flow_and_architecture.md

## 1. Purpose

This document defines the application architecture, module boundaries, ownership rules, lifecycle, and data flow for the engineering system designer application.

The goal is to prevent architectural drift while implementing the visual system designer, graph model, validation layer, persistence layer, and later equation/controller/simulation features.

The architecture diagram `app_two_module_data_flow.svg` represents the **Phase 2 target architecture**.

Phase 1 implements only the visual modeling tier:

* component library
* workspace
* graph model
* implicit node assembly
* validation
* persistence
* controller/configuration placeholders

Phase 1 does **not** implement equation extraction, transfer-function generation, state-space generation, control execution, or numerical simulation.

---

## 2. High-Level Architecture

The application follows a layered architecture:

```text
src/
  application/
  features/
  shared/
```

The `src/` prefix reflects the actual project root layout. The architectural layer names (`application/`, `features/`, `shared/`) are used throughout this document and other specifications without the `src/` prefix when discussing logical responsibilities. Both refer to the same code under `src/`.

### 2.1 Application Layer

Responsible for:

* top-level application entry point
* application bootstrap
* main shell/window composition (`SystemDesignerShell`, a `QMainWindow`)
* layout composition
* module orchestration
* menu/toolbar wiring
* global commands
* project lifecycle actions
* routing between major panels/modules
* status bar / global status area (see `02 §32.2`)

The application layer must not implement component physics, graph assembly, equation extraction, controller design, or simulation logic.

Recommended file structure:

```text
src/application/
  __init__.py
  main.py                    # QApplication entry point
  bootstrap.py               # logging, settings, registries, high-DPI setup
  shell.py                   # SystemDesignerShell (QMainWindow)
  menu.py                    # menu/toolbar/action wiring
  project_lifecycle.py       # new/open/save/save-as/close/autosave coordinator
  status_bar.py              # global status bar (see 02 §32.2)
```

### 2.2 Feature Module Layer

Feature modules own domain workflows.

Initial feature modules:

```text
src/features/SystemModelingModule
src/features/ControllerDesignModule
```

#### 2.2.1 SystemModelingModule Structure

```text
src/features/SystemModelingModule/
  __init__.py
  module.py                       # SystemModelingModule (orchestrator)
  model/                          # data layer (no Qt UI imports)
    __init__.py
    workspace_model.py            # WorkspaceModel (source of truth)
    component_instance.py         # ComponentInstance dataclass
    connection.py                 # Connection dataclass
    selection_model.py            # SelectionModel
    id_generator.py               # WorkspaceIdGenerator (ULID + display ID)
    validation_report.py          # ValidationReport, severity, issue codes
    migrations/
      __init__.py
      registry.py                 # WorkspaceModelMigrations (see 02 §29.3.1)
      v0_1_0_to_v0_2_0.py
  commands/                       # QUndoCommand subclasses (see 02 §25)
    __init__.py
    add_component_command.py
    move_component_command.py
    rotate_component_command.py
    delete_component_command.py
    add_connection_command.py
    delete_connection_command.py
    modify_connection_command.py
    change_parameter_command.py
    paste_selection_command.py
  panels/
    __init__.py
    ModelLibraryPanel/
      __init__.py
      panel.py                    # ModelLibraryPanel (QWidget)
      tree_view.py                # library tree
      search_bar.py
      Models/                     # SVG hierarchy + component definitions
        Electrical/
          Analog/
            Components/           # Capacitor, Ground Electric, Inductor, Resistor
            Examples/
            Sensors/              # Current Sensor, Voltage Sensor
            Sources/              # Constant Voltage, Ramp Voltage, Signal Voltage,
                                  # Sine Voltage, Step Voltage
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
            Components/           # Damper, Fixed, Mass, Spring, Spring Damper,
                                  # Wheel Black, Wheel White
            Examples/
            Sensors/
            Sources/
    ComponentInfoPanel/
      __init__.py
      panel.py                    # bottom info panel (see 02 §28)
    ModelEquationsPanel/
      __init__.py
      panel.py                    # collapsible equation panel (see §13.1)
  workspace/
    __init__.py
    BlockDiagramWorkspace/
      __init__.py
      view.py                     # BlockDiagramWorkspaceView (QGraphicsView)
      scene.py                    # BlockDiagramWorkspaceScene (QGraphicsScene)
      grid_background_item.py
      graphics_items/
        __init__.py
        component_graphics_item.py
        connection_graphics_item.py
        port_graphics_item.py
        selection_outline_item.py
        validation_indicator_item.py  # see 02 §32.3.1
        ghost_connection_item.py
```

The `model/` subfolder is the data-layer source of truth for this module. It must not import Qt UI modules; it may use `QObject`/`Signal` for change notification but must remain testable without instantiating any QWidget.

The `workspace/` subfolder is the UI layer. It listens to model signals and renders graphics items. It must not own model state.

This separation enforces ADR-003 (Workspace UI/Data Separation).

#### 2.2.2 ControllerDesignModule Structure

```text
src/features/ControllerDesignModule/
  __init__.py
  module.py                       # ControllerDesignModule (orchestrator)
  model/                          # configuration data layer
    __init__.py
    controller_settings.py
    io_selection.py
    simulation_settings.py
    plot_layout.py                # PlotLayout, PlotSlotConfig
    stability_analysis_artifact.py  # produced in Phase 2 Stage S5
  builders/                       # Phase 2+: TF and SS builders
    __init__.py
    transfer_function_builder.py  # Phase 2 (Stage S5)
    state_space_builder.py        # Phase 2 (Stage S5)
    linearization.py              # Phase 2 (Stage S5)
  panels/
    __init__.py
    ConfigurationPanel/
      __init__.py
      panel.py                    # tabbed Configuration panel
      controller_tab.py
      io_selection_tab.py
      simulation_settings_tab.py
      plot_layout_tab.py
    ResultsPanel/
      __init__.py
      panel.py                    # 4-slot unified result panel (see 05 §14)
      plot_slot.py                # plot panel with header dropdown (see 03 §14.4.1)
```

### 2.3 Shared Layer

The shared layer contains reusable model, graph, registry, type, utility, probe, and future numerical engine functionality.

```text
src/shared/
  components/                     # Component schema dataclasses
    __init__.py
    component_definition.py
    port_definition.py
    parameter_definition.py
  registry/                       # All registries
    __init__.py
    component_registry.py
    domain_registry.py
    parameter_schema_registry.py
    svg_registry.py
  graph/                          # SystemGraph (Phase 1 + Phase 2)
    __init__.py
    system_graph.py
    graph_assembler.py
    graph_validator.py
    implicit_node.py
    port_ref.py
  types/                          # Common enums and value types
    __init__.py
    domain_id.py
    port_kind.py
    component_category.py
    validation_severity.py
    plot_type.py
    controller_type.py
  probes/                         # Output observation (Phase 1 + Phase 2)
    __init__.py
    probe_definition.py
  utils/                          # Stateless helpers
    __init__.py
    ulid_generator.py
    json_helpers.py
    unit_helpers.py
    logging_helpers.py
    result_helpers.py
  engine/                         # PHASE 2 ONLY — Phase 1: ImportError
    __init__.py                   # raises ImportError in Phase 1
    simulation_request.py         # Phase 2 Stage S4
    simulation_result.py          # Phase 2 Stage S4
    solver_registry.py            # Phase 2 Stage S4
    solvers/
      __init__.py
      solver_adapter.py
      casadi_solver_adapter.py
      scipy_solver_adapter.py
    controllers/                  # Phase 2 Stage S7 — runtime executors
      __init__.py
      controller_runtime_adapter.py
      pid_runtime_adapter.py
      lqr_runtime_adapter.py
    storage/
      __init__.py
      hdf5_result_store.py
```

`shared/engine` is reserved for Phase 2+ numerical simulation and backend execution. It must not be used in Phase 1. The `shared/engine/__init__.py` file in Phase 1 raises `ImportError` (see §5.7).

`shared/registry/` is a separate package, distinct from `shared/utils/`. Registries are stateful runtime-loaded resources; helpers are stateless functions. Conflating the two is forbidden.

The `shared/graph/SystemGraph` is the **derived** graph structure used for validation, equation extraction, and analysis. It is computed from `WorkspaceModel` (which is owned by `SystemModelingModule`). The two are not the same object: `WorkspaceModel` stores user-authored data; `SystemGraph` is a derived structural view.

---

## 3. Module Initialization Order

Modules must be initialized in a strict order to avoid circular dependencies.

Initialization order:

```text
1. Logging and settings
2. Registries
   - ComponentRegistry
   - DomainRegistry
   - ParameterSchemaRegistry
   - SvgRegistry
3. SystemModelingModule
4. ControllerDesignModule
5. SystemDesignerShell
6. Show main window
```

Registry initialization must happen before feature modules because modules depend on component definitions, domain definitions, parameter schemas, and SVG mappings.

---

## 4. Module Ownership

### 4.1 SystemDesignerShell

`SystemDesignerShell` is the top-level application shell.

Responsibilities:

* create and arrange main panels
* host feature modules
* coordinate project open/save/close actions
* provide global status area
* provide menu actions and shortcuts
* coordinate undo/redo actions
* connect high-level signals between modules
* connect workspace selection signals to global UI panels such as status/info panels

Non-responsibilities:

* does not own workspace graph state
* does not own workspace selection state
* does not validate engineering models
* does not derive equations
* does not run simulations
* does not directly mutate component or connection data

`SystemDesignerShell` may route signals, but it must not become the owner of business state.

### 4.2 SystemModelingModule

`SystemModelingModule` owns the workspace and physical system modeling workflow.

Phase 1 responsibilities:

* own `WorkspaceModel` (located in `features/SystemModelingModule/model/workspace_model.py`)
* own `SelectionModel`
* own `WorkspaceIdGenerator`
* own workspace editing command stack (`features/SystemModelingModule/commands/`)
* own schema migration registry (`features/SystemModelingModule/model/migrations/`)
* coordinate `ModelLibraryPanel`
* coordinate `BlockDiagramWorkspace`
* coordinate `ComponentInfoPanel`
* coordinate `ModelEquationsPanel` (placeholder content in Phase 1; full content in Phase 2)
* assemble `SystemGraph` from workspace data
* run graph-level validation
* expose graph/model snapshots to other modules
* emit model-change signals

SystemModelingModule is the source of truth for:

* components
* connections
* component positions
* component rotations
* component parameters
* component labels
* component physical attributes (boundary, motion, directional, source, source_type — see `02 §11.2`)
* implicit node assembly inputs
* workspace validation state

The `model/` subfolder contains pure data classes and `WorkspaceModel`. It must not import Qt UI modules. `WorkspaceModel` may inherit from `QObject` for signal emission, but its API and tests must not require a `QApplication` instance for non-UI operations (e.g., `add_component`, `to_dict`, `from_dict`, validation).

Phase 2+ responsibilities:

* own backend equation extraction workflow (`features/SystemModelingModule/equations/` — added in Stage S3)
* convert validated `SystemGraph` into differential equation representation
* produce model-level equation artifacts for `ModelEquationsPanel`
* expose DAE/ODE model representation to `ControllerDesignModule`
* own last valid model snapshot (see `04_model_equations_requirements.md` §17)

Equation extraction belongs to the System Modeling workflow because equations are part of the model definition, not part of controller execution.

#### 4.2.1 WorkspaceIdGenerator Ownership

`WorkspaceIdGenerator` is owned by `SystemModelingModule` and its state is part of `WorkspaceModel`.

Rules:

* internal ULID generation is stateless and may live in `shared/utils/ulid_generator.py`
* display ID counters are stateful and live in `features/SystemModelingModule/model/id_generator.py`
* display ID counters must be persisted in the project file
* counters must be reconstructable from existing project data if missing

#### 4.2.2 WorkspaceModel Serialization

`WorkspaceModel` exposes two methods for serialization:

* `to_dict() -> dict` — produces the model section of `project.json`
* `from_dict(data: dict) -> WorkspaceModel` — reconstructs a model from `project.json` data

Both methods must follow the schema-versioning contract defined in `02 §29.3.1`. Migration logic lives in `features/SystemModelingModule/model/migrations/registry.py` and is invoked by `from_dict` when the input data has an older `schema_version`.

`to_dict` and `from_dict` must:

* round-trip without data loss when the schema version matches
* preserve unknown fields under `metadata` and `extensions`
* use stable key ordering for human-friendly diffs in version control
* never mutate transient UI state (selection, hover, drag preview)

### 4.3 ControllerDesignModule

`ControllerDesignModule` owns controller, I/O, transfer-function/state-space preparation, and plot/result configuration.

Phase 1 responsibilities:

* store controller settings
* store I/O selection
* store simulation settings
* store plot layout preferences
* provide UI placeholders for controller tuning and result plots
* persist its configuration in the project file
* validate stale I/O references against the current workspace model

Phase 1 non-responsibilities:

* does not run simulation
* does not apply PID to a model
* does not calculate transfer functions
* does not calculate state-space models
* does not modify workspace graph state

Phase 2+ responsibilities:

* consume DAE/ODE representation from `SystemModelingModule`
* build transfer-function representation where applicable
* build state-space and frequency-domain forms where applicable
* produce `StabilityAnalysisArtifact` containing `A`, `B`, `C`, `D` matrices, eigenvalues, poles/zeros, frequency response, and stability margins (see `05_simulation_and_results_requirements.md` §16)
* run controller design workflows
* configure simulation requests
* consume simulation results from `shared/engine`
* update simulation result panels

ControllerDesignModule is a consumer of system models, not the owner of workspace structure.

#### 4.3.1 ControllerDesignModule Signals

The module must emit:

* `controllerSettingsChanged()`
* `ioSelectionChanged()`
* `simulationSettingsChanged()`
* `plotLayoutChanged()`

These signals must trigger dirty state updates because these settings are persisted in the project file.

`plotLayoutChanged()` is emitted when:

* a slot's `plot_type` changes
* a slot's `channel_selection` changes
* a slot's `title` or `axis_config` changes
* the `fullscreen_slot_id` changes

This signal is consumed by both the Configuration UI and the per-plot header UI to maintain dropdown synchronization (see `03_configuration_requirements.md` §14.4.1).

#### 4.3.2 Cross-Module Reference Handling

ControllerDesignModule must subscribe to relevant SystemModelingModule signals.

If a referenced component or port is removed:

* corresponding I/O references must be marked as stale or removed
* the user must receive a validation warning
* project-level validation must include the stale reference
* Phase 2 simulation/controller execution must be blocked until stale references are resolved

Cross-module reference validation is part of the project-level validation report, not only workspace graph validation.

---

## 5. Shared Layer Responsibilities

### 5.1 shared/components

Defines component-related data structures.

Contains:

* `ComponentDefinition`
* `ComponentInstance`
* `PortDefinition`
* `PortInstance`
* `ParameterDefinition`
* `ParameterValue`

Responsibilities:

* describe component schemas
* define parameters and ports
* provide serializable component instance structures
* keep definitions separate from instances

### 5.2 shared/registry

Defines registries for reusable definitions.

Contains:

* `ComponentRegistry`
* `DomainRegistry`
* `ParameterSchemaRegistry`
* `SvgRegistry`
* future: `SolverRegistry`

Responsibilities:

* load component definitions
* provide default parameters
* provide port definitions
* provide SVG mapping
* define domain compatibility rules
* define domain visual styles
* define visual tokens for domain-aware rendering

#### 5.2.1 Registry Loading Flow

Registry loading occurs during application bootstrap before feature modules are created.

Recommended flow:

```text
Application bootstrap
→ Load built-in domain definitions
→ Load built-in component definitions
→ Load built-in parameter schemas
→ Load SVG mappings
→ Validate registries
→ Create feature modules
```

Phase 1 may load definitions from packaged JSON/Python definitions. User-extensible component plugins are out of scope for Phase 1 but should not be architecturally blocked.

### 5.3 shared/graph

Defines graph structures independent from UI.

Contains:

* `WorkspaceModel`
* `SystemGraph`
* `GraphAssembler`
* `GraphValidator`
* `Connection`
* `PortRef`
* `ImplicitNode`
* `ValidationReport`

Responsibilities:

* store workspace model data
* assemble graph from components and connections
* compute implicit nodes
* validate graph-level consistency
* expose graph snapshots for future equation extraction

### 5.4 shared/probes

Defines output observation and signal selection concepts.

Phase 1 responsibilities:

* define probe/output-selection data structures
* store I/O selections where possible
* reserve future engine binding fields such as `state_variable_id`, `output_id`, and `channel_id`

Phase 2+ responsibilities:

* map probes to state variables, outputs, and simulation channels
* support result panel signal selection

### 5.5 shared/types

Defines common type structures and enums.

Contains:

* `DomainId`
* `PortKind`
* `ComponentCategory`
* `ValidationSeverity`
* `PlotType`
* `ControllerType`
* `Point`
* `PortRef`

### 5.6 shared/utils

Contains reusable stateless utilities.

Examples:

* ULID generation
* JSON serialization helpers
* migration helpers
* unit conversion helpers
* logging helpers
* result/error helpers

Stateful display ID generation belongs to `WorkspaceIdGenerator`, which is owned by `SystemModelingModule`.

### 5.7 shared/engine

Future numerical engine and backend execution layer.

Phase 1 enforcement rules:

* `shared/engine/__init__.py` must raise `ImportError("shared.engine is not available in Phase 1")`
* no module in `features/` or `application/` may import from `shared.engine`
* CI must include a static architecture test preventing such imports

Required CI architecture test:

```text
pytest tests/architecture/test_engine_isolation.py
```

The test must scan Python files in `features/` and `application/` for imports matching:

```text
from shared.engine ...
import shared.engine
```

and fail if any are found.

This ensures architectural discipline is enforced, not assumed.

Phase 2+ responsibilities:

* numerical ODE integration
* simulation backend coordination
* solver adapters (CasADi primary, SciPy fallback behind adapter boundary)
* time-domain simulation execution
* possibly nonlinear simulation execution
* runtime controller execution adapters

Recommended Phase 2 structure:

```text
shared/engine/
  __init__.py
  simulation_request.py
  simulation_result.py
  solver_registry.py
  solver_adapter.py
  casadi_solver_adapter.py
  scipy_solver_adapter.py
  controllers/
    pid_runtime_adapter.py
  storage/
    hdf5_result_store.py
```

`shared/engine/controllers/` contains runtime controller execution adapters (e.g., PID runtime, LQR runtime, `compute_control` interface). These are thin numerical executors. Tuning logic (gain selection, pole placement, LQR synthesis) remains in `ControllerDesignModule` (see `05_simulation_and_results_requirements.md` §4.2.1).

Important ownership distinction:

* equation extraction belongs to `SystemModelingModule`
* transfer-function/state-space preparation belongs to `ControllerDesignModule`
* stability analysis (eigenvalues, poles, zeros, frequency response, margins) belongs to `ControllerDesignModule`
* numerical simulation/backends belong to `shared/engine`
* runtime controller execution adapters belong to `shared/engine/controllers/`

---

## 6. Source of Truth Rules

### 6.1 Workspace State

`WorkspaceModel` is the source of truth for all physical diagram state.

UI graphics items are views of this state.

### 6.2 Controller and Simulation Settings

`ControllerDesignModule` owns:

* controller settings
* I/O selection
* simulation settings
* plot layout selection

These settings are persisted in the project file but do not affect physical graph assembly in Phase 1.

### 6.3 Registry Definitions

Registries own reusable definitions.

Definitions are not copied deeply into every instance unless needed for persistence or migration.

Instances store references to definitions through stable IDs.

### 6.4 Derived Artifacts

In Phase 2+, equations, matrices, transfer functions, simulation traces, and analysis results are derived artifacts.

They must not become the primary source of truth.

Phase 2 derived artifacts:

* `ODEArtifact` — produced by `SystemModelingModule` from validated `SystemGraph`
* `SimulationRequest` — immutable hand-off object from configuration to `shared/engine`
* `SimulationResultArtifact` — produced by `shared/engine` after numerical integration; full numerical data stored in HDF5
* `StabilityAnalysisArtifact` — produced by `ControllerDesignModule` from linearized state-space; contains `A`/`B`/`C`/`D`, eigenvalues, poles/zeros, frequency response, and stability margins

The `ODEArtifact` must not contain final `A`/`B`/`C`/`D` matrices. Those belong to the `StabilityAnalysisArtifact` produced by `ControllerDesignModule`. This boundary preserves the ownership separation between model definition and control analysis.

---

## 7. Core Data Flow: Phase 1

### 7.1 Component Placement Flow

```text
User drags component from ModelLibraryPanel
→ BlockDiagramWorkspace receives drop event
→ Create AddComponentCommand
→ Command calls WorkspaceModel.add_component(...)
→ WorkspaceModel creates ComponentInstance
→ WorkspaceModel emits componentAdded
→ Workspace scene creates ComponentGraphicsItem
→ Validation is scheduled
→ Dirty state becomes true
```

### 7.2 Component Move Flow

```text
User drags component on canvas
→ UI updates temporary visual position during drag
→ On mouse release, create MoveComponentCommand
→ Command calls WorkspaceModel.move_component(...)
→ WorkspaceModel updates position
→ WorkspaceModel emits componentMoved
→ Connected ConnectionGraphicsItems update
→ Validation is scheduled
→ Dirty state becomes true
```

### 7.3 Connection Creation Flow

```text
User starts drag from source port
→ Workspace enters DraggingConnection state
→ Ghost connection is rendered
→ Candidate target ports are validated during hover
→ User releases on target port
→ Create AddConnectionCommand
→ Command calls WorkspaceModel.add_connection(source, target)
→ WorkspaceModel validates connection before mutation
→ Connection is added
→ WorkspaceModel emits connectionAdded
→ Scene creates ConnectionGraphicsItem
→ Graph validation is scheduled
→ Dirty state becomes true
```

### 7.4 Connection Re-Target Flow

```text
User drags endpoint of existing connection
→ Workspace enters RetargetingConnection state
→ Ghost connection preview is shown
→ Candidate new target is validated
→ User releases on valid port
→ Create ModifyConnectionCommand
→ Command calls WorkspaceModel.retarget_connection(...)
→ Connection ID remains stable
→ WorkspaceModel emits connectionChanged
→ Scene updates ConnectionGraphicsItem
→ Validation is scheduled
→ Dirty state becomes true
```

### 7.5 Delete Component Flow

```text
User selects component and presses Delete
→ Create DeleteComponentCommand
→ Command asks WorkspaceModel for attached connections
→ WorkspaceModel atomically removes component and attached connections
→ WorkspaceModel emits componentRemoved and connectionRemoved signals
→ Scene removes corresponding graphics items
→ Validation is scheduled
→ Dirty state becomes true
```

### 7.6 Save Flow

```text
User triggers Save
→ Application checks project package last-modified timestamp
→ If external modification detected, prompt user
→ Application asks modules for project state
→ SystemModelingModule serializes workspace model
→ ControllerDesignModule serializes controller/simulation/plot settings
→ Project serializer writes project.json inside the .systemdesign/ package
→ In Phase 2, simulation results are written to .systemdesign/results/*.h5
→ Validation state is included in metadata
→ Save timestamp recorded
→ Dirty state becomes false
→ Recovery file in .systemdesign/recovery/ is removed or marked obsolete after successful save
```

Save must not be blocked by validation errors.

The project package directory format is defined in `02_workspace_requirements.md` §29.1. HDF5 result file storage is defined in `05_simulation_and_results_requirements.md` §12.

### 7.7 Load Flow

```text
User opens .systemdesign/ package (or legacy .systemdesign JSON file)
→ Project loader detects format (package directory or legacy single file)
→ For legacy single-file projects, automatic migration to package format is offered
→ Project loader reads project.json from the package
→ Schema version is checked
→ Migrations are applied if needed
→ WorkspaceModel enters batch mode (signals suspended)
→ Components and connections populated via direct API
→ WorkspaceModel exits batch mode
→ WorkspaceModel emits modelReset()
→ Scene rebuilds from WorkspaceModel
→ Validation runs
→ In Phase 2, result_refs are validated against .systemdesign/results/*.h5 files
→ Missing HDF5 files are marked with status "file_missing" (see 05 §13.3)
→ Undo stack is cleared
→ View state (zoom, pan) applied after scene rebuild
→ Dirty state becomes false unless recovery/migration warnings require user save
```

View state schema is defined in `02_workspace_requirements.md` §29.6.

If migration fails:

* original file must remain untouched
* user receives error report
* no partial model state is committed

### 7.8 Autosave Flow

```text
Autosave timer fires
→ If dirty, application collects project state silently
→ Recovery file written to .systemdesign/recovery/autosave.json
→ Main project.json remains unchanged
→ Dirty state remains true
```

The recovery file lives inside the project package directory under `recovery/`, separate from the main `project.json` (see `02_workspace_requirements.md` §29.1 and §30).

---

## 8. Command vs Direct API Policy

### 8.1 User Actions

All user-triggered editing actions must go through command objects.

Examples:

* add component
* move component
* rotate component
* delete component
* add connection
* delete connection
* retarget connection
* parameter change
* paste selection

Commands are undoable unless explicitly marked otherwise.

### 8.2 PySide6 Command Stack Decision

The command stack should use PySide6's `QUndoStack` and `QUndoCommand` subclasses.

Rules:

* Workspace editing commands live under `features/SystemModelingModule`
* Save state should use `QUndoStack.setClean()` / clean index semantics where practical
* Move commands should commit on mouse release
* Parameter edit commands should merge or commit only when editing is finished
* Compound commands may be represented by parent `QUndoCommand` objects

A custom command stack should only be used if `QUndoStack` becomes insufficient.

### 8.3 Programmatic Actions

Programmatic actions may use direct model APIs.

Examples:

* project loading
* schema migration
* recovery loading
* test setup
* graph rebuild

Programmatic actions should not populate the undo stack unless explicitly required.

After project load or migration, the undo stack should be cleared.

### 8.4 Tests

Data-layer tests may use direct model APIs for setup.

Command tests must explicitly use command objects.

---

## 9. Event and Signal Flow

Full workspace signal details are defined in `02_workspace_requirements.md` §4.1.

### 9.1 Signal Direction

Signals flow from model to UI.

```text
WorkspaceModel → SystemModelingModule → UI panels
```

UI actions do not mutate state directly. They create commands or call module-level actions that create commands.

### 9.2 Signal Granularity

Model signals should be specific enough to avoid full scene rebuilds for small changes.

Examples:

* `componentAdded`
* `componentMoved`
* `componentRotated`
* `componentChanged`
* `componentRemoved`
* `connectionAdded`
* `connectionChanged`
* `connectionRemoved`
* `selectionChanged`
* `validationChanged`
* `dirtyChanged`
* `modelReset`

### 9.3 Full Reset

`modelReset` is used only when rebuilding the scene is simpler or safer.

Examples:

* project load
* major migration
* recovery load
* full reset/new project

---

## 10. Graph Assembly and Validation Flow

### 10.1 Graph Assembly

`GraphAssembler` converts `WorkspaceModel` into `SystemGraph`.

Inputs:

* component instances
* component definitions from registry
* port definitions from registry
* connections

Outputs:

* graph components
* graph connections
* implicit nodes
* validation metadata

### 10.2 Implicit Node Assembly

Implicit nodes are computed from connections using union-find/disjoint-set logic.

Rules:

* each port reference is a graph vertex
* each connection is an undirected edge
* connected port groups become implicit nodes
* all ports in a node must share a compatible domain

### 10.3 Validation

Validation must run in layers:

1. immediate validation during interaction
2. debounced workspace validation after graph edits
3. pre-simulation validation in future phases

Phase 1 validation must include:

* incompatible domains
* self-connections
* duplicate connections
* broken references
* missing required domain references
* invalid parameters
* stale cross-module I/O references

---

## 11. Persistence Architecture

### 11.1 Project File Ownership

A project is stored as a `.systemdesign/` directory bundle containing `project.json` and supporting subdirectories for results, exports, and recovery (see `02_workspace_requirements.md` §29.1).

The `project.json` file inside the package is composed from multiple module snapshots:

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
* `components`: list of `ComponentInstance` objects owned by `SystemModelingModule`
* `connections`: list of `Connection` objects owned by `SystemModelingModule`
* `controller_settings`, `io_selection`, `simulation_settings`, `plot_layout`: configuration sections owned by `ControllerDesignModule` (see `03_configuration_requirements.md`)
* `view`: persisted view state such as zoom, pan, viewport center (see `02 §29.6`)
* `result_refs`: list of references to simulation results stored in `results/` (see `05 §13`); empty array in Phase 1
* `metadata`, `extensions`: forward-compatibility containers for future fields

Subdirectory roles inside the package:

* `results/`: HDF5 simulation result files referenced from `result_refs`
* `exports/`: user-generated exports (PNG plots, CSV data, PDF reports)
* `recovery/`: autosave recovery state, written by the autosave timer

Migration from legacy single-file `.systemdesign` JSON projects is defined in `02 §29.1`.

### 11.2 Reserved Phase 1 Fields

The following fields may be present in Phase 1 even if not fully used:

* `controller_settings`
* `io_selection`
* `simulation_settings`
* `plot_layout`
* `view`
* `result_refs` (empty array in Phase 1)

They are reserved for forward compatibility and basic UI persistence. `result_refs` becomes populated in Phase 2 when simulation results are produced.

### 11.3 Serialization Rules

* Internal IDs are serialized.
* Display IDs are serialized.
* Custom labels are serialized.
* Display ID generator counters are serialized.
* Implicit nodes are not serialized as primary data.
* Unknown fields should be preserved when possible.
* Schema version must always be present.
* `result_refs` entries are lightweight references; full simulation arrays live in HDF5 files under `results/`.
* `StabilityAnalysisArtifact` summary may be persisted in project JSON when small (see `05 §16.6`); large frequency-response arrays may be stored in `results/analysis/` if needed.

---

## 12. Phase 2 Target Data Flow

This section is future-facing and must not be implemented as equation/simulation logic in Phase 1.

The target flow aligns with `app_two_module_data_flow.svg`.

### 12.1 System Modeling Flow

```text
WorkspaceModel
→ GraphAssembler
→ SystemGraph
→ GraphValidator
→ Backend Equation Builder owned by SystemModelingModule
→ ODEArtifact (no final A/B/C/D matrices)
→ ModelEquationsPanel
```

The backend equation builder belongs to the System Modeling workflow because it extracts model equations from the physical system definition.

The `ODEArtifact` schema is defined in `04_model_equations_requirements.md` §6. It must not contain final `A`/`B`/`C`/`D` matrices; those are owned by `ControllerDesignModule`.

### 12.2 Controller Flow

```text
ODEArtifact from SystemModelingModule
→ ControllerDesignModule
→ TransferFunctionBuilder / StateSpaceBuilder owned by ControllerDesignModule
→ StabilityAnalysisArtifact (A, B, C, D, eigenvalues, poles/zeros, frequency response, stability margins)
→ Controller tuning workflows
→ SimulationRequest
→ shared/engine numerical simulation backend
→ SimulationResultArtifact
→ Result Panel
```

Transfer-function and state-space preparation belong to the Controller Design workflow because they are control-analysis representations of the model.

The `StabilityAnalysisArtifact` schema is defined in `05 §16.4`. It is owned by `ControllerDesignModule` and may contain `A`/`B`/`C`/`D` matrices because these are control-analysis representations, not model definitions.

### 12.3 shared/engine Flow

```text
SimulationRequest
→ shared/engine solver adapter (CasADi primary, SciPy fallback)
→ numerical backend
→ time-domain result data
→ HDF5 result storage in .systemdesign/results/
→ SimulationResultArtifact metadata
→ ControllerDesignModule / Result Panel
```

For closed-loop simulation, the controller wrapper inside `shared/engine/controllers/` is invoked at each solver step:

```text
At each solver step:
  state, output, reference, time, dt
  → shared/engine/controllers/<runtime_adapter>.compute_control(...)
  → control input u
  → ODE integrator advances plant
```

`shared/engine` owns numerical execution/backends, not the visual workspace and not Phase 1 equation extraction. The runtime controller wrapper is a thin numerical executor; tuning logic remains in `ControllerDesignModule` (see `05 §4.2.1`).

---

## 13. Model Equations Panel Flow

The Model Equations Panel is a collapsible side panel on the right edge of the application window, attached to the System Modeling area.

### 13.1 Panel Visibility and Pinning

The panel must support three visual states:

* **collapsed** (default in Phase 1): the panel is shown as a vertical tab/handle on the right edge labeled `Model Equations`; its content is hidden
* **expanded**: clicking the tab/handle expands the panel into a side pane showing the Model Equations content
* **pinned**: a pin button inside the expanded panel toggles between auto-collapse-on-blur and persistent-open behavior

Visibility rules:

* the panel must remember its state (collapsed/expanded/pinned) per project, persisted in the project file's `view` field (see `02 §29.6`)
* expanding the panel must not cause the workspace canvas to resize abruptly; transition animation is recommended but not required
* the panel width may be user-resizable within configured min/max bounds
* the collapsed-state tab/handle remains visible at all times in Phase 1 so the user always knows the panel exists

### 13.2 Phase 1 Content

Phase 1 panel content:

* show placeholder message indicating equations will appear in Phase 2
* show workspace summary (component count, connection count, active domains)
* show validation status summary
* show last graph assembly timestamp if available

### 13.3 Phase 2 Content

Phase 2 panel content:

* show human-readable equations
* show state vector
* show input/output vector
* show DAE/ODE representation
* show warnings and validation diagnostics

Detailed Phase 2 panel behavior is defined in `04_model_equations_requirements.md` §20.

### 13.4 Ownership

The Model Equations Panel UI lives in `features/SystemModelingModule/panels/ModelEquationsPanel/` (see §2.2.1).

The panel reads from:

* `WorkspaceModel` for Phase 1 summary content
* `ODEArtifact` for Phase 2 equation content

The panel must not mutate any model state. It is a read-only consumer.

---

## 14. Result Panel Flow

The Result Panel is the unified visual result area for both time-domain simulation results and stability-analysis results. It consumes either `SimulationResultArtifact` or `StabilityAnalysisArtifact` depending on the selected plot type.

Phase 1 behavior:

* show four configurable placeholder plot areas in a 2x2 grid
* persist selected plot types
* allow plot layout configuration via Configuration / Plot Layout dropdowns
* mirror dropdown synchronization between Configuration and per-plot header dropdowns
* support fullscreen toggle by double-click
* no real simulation or analysis data is produced

Default plot slots:

* `plot_1`: Time Response (selection kind: `channels`)
* `plot_2`: Step Response (selection kind: `io_pair`)
* `plot_3`: Bode (selection kind: `io_pair`)
* `plot_4`: Pole-Zero (selection kind: `system_wide`)

Plot type dropdown grouping:

* Time-domain group: Time Response, Step Response, State Variables, Input/Output Signal, Road Profile, Force
* Frequency-domain group: Bode, Nyquist
* Algebraic group: Pole-Zero, Root Locus, Eigenvalue
* Unknown group: shown only when project file contains unrecognized plot types

(See `03_configuration_requirements.md` §8.5 for full grouping rules and §8.6 for `channel_selection.kind` schema.)

Phase 2+ behavior:

* time-domain plots consume `SimulationResultArtifact` from `shared/engine`
* frequency-domain and algebraic plots consume `StabilityAnalysisArtifact` from `ControllerDesignModule`
* `step_response` may consume either artifact (simulation preferred when available)
* missing artifacts show placeholders with clear action buttons (e.g., "Linearize and Analyze")
* plot type dropdowns remain selectable regardless of artifact availability
* full simulation data is loaded lazily from HDF5 files under `.systemdesign/results/`

Stability analysis is owned by `ControllerDesignModule` at the artifact level. The Result Panel is a unified UI surface that renders both artifact types through unified plot slot bindings (see `05 §14` and §16).

---

## 15. Error Handling Architecture

Errors must be handled at the lowest responsible layer and reported upward.

### 15.1 Data Layer Errors

Examples:

* invalid component definition
* missing port reference
* duplicate internal ID
* invalid parameter value

Data-layer errors should return structured result objects or raise controlled exceptions.

### 15.2 UI Layer Errors

Examples:

* invalid drag target
* blocked connection
* unsupported gesture

UI errors should be shown through:

* status bar
* visual highlights
* non-blocking notifications

### 15.3 Fatal Errors

Unexpected exceptions should be logged with diagnostic context.

The application should attempt to keep the project recoverable.

---

## 16. Logging and Diagnostics Flow

The architecture should support diagnostic output for debugging and future AI-assisted development.

Recommended logged events:

* project opened/saved
* schema migration performed
* component added/removed
* connection added/removed/modified
* validation warnings/errors
* graph assembly failures
* autosave/recovery events

Future diagnostic export:

* workspace JSON snapshot
* system graph summary
* validation report
* registry summary
* command stack summary

---

## 17. Threading Model

Rules:

* WorkspaceModel and all direct model mutations run on the main thread
* UI updates run on the main thread
* Qt signal emissions that touch UI must be delivered to the main thread
* expensive validation and future engine computations may run in background threads
* background-to-UI communication must use queued Qt signals

This prevents cross-thread QObject errors in PySide6.

Phase 1 validation should prefer `QTimer`-based debounce before introducing background threads.

Phase 2 simulation execution must run in a worker thread or process so the UI remains responsive (see `05 §9.2` and §20).

---

## 18. Testing Architecture

The data/model layer must be testable without GUI.

Test categories:

* component registry tests
* domain registry tests
* parameter schema tests
* workspace model tests
* graph assembly tests
* implicit node tests
* validation tests
* command/undo-redo tests
* serialization/migration tests
* signal contract tests
* UI smoke tests where practical
* architecture import boundary tests

Phase 2 additional test categories:

* `SystemModelingModule` does not import `shared/engine` solver internals
* `ODEArtifact` does not contain final `A`/`B`/`C`/`D` matrices
* `StabilityAnalysisArtifact` may contain `A`/`B`/`C`/`D` only under `ControllerDesignModule`
* UI does not directly instantiate solver adapters
* Result Panel reads artifacts and channels, not raw engine internals
* Plot slots bind by channel ID, not array indices
* Project package format round-trip preserves all data
* Legacy single-file projects migrate correctly to package format

Tests should be written alongside implementation.

---

## 19. Decision Records

Critical architectural decisions should be mirrored as ADRs in a `/decisions/` or `/docs/adr/` folder.

### 19.1 Phase 1 ADRs

```text
ADR-001-phase1-engine-isolation.md
ADR-002-hybrid-ulid-identity-model.md
ADR-003-workspace-ui-data-separation.md
ADR-004-equation-builder-ownership.md
ADR-005-command-stack-qundostack.md
ADR-006-controller-owns-transfer-function-builder.md
```

### 19.2 Phase 2 ADRs

```text
ADR-007-symbolic-backend-casadi.md
ADR-008-bond-graph-causality.md
ADR-009-dae-reduction-strategy.md
ADR-010-linearization-ownership.md
ADR-011-dimensional-analysis-policy.md
ADR-012-project-package-directory-format.md
ADR-013-stability-analysis-artifact.md
ADR-014-controller-wrapper-shared-engine.md
ADR-015-result-panel-unified-with-grouped-dropdown.md
ADR-016-channel-selection-kind-schema.md
ADR-017-mirror-sync-plot-dropdowns.md
ADR-018-signal-payload-contracts.md
ADR-019-batch-mutation-and-changeset.md
ADR-020-dirty-tracking-semantics.md
```

ADR-018 through ADR-020 are S1-stage ADRs added during the WorkspaceModel design refinement; they are listed here in chronological numbering.

### 19.3 ADR Cross-References

| ADR | Decision | Source Documents |
| --- | --- | --- |
| ADR-001 | `shared/engine` blocked in Phase 1 via ImportError | `06 §5.7` |
| ADR-002 | ID model: `id` (ULID) + `display_id` + `custom_label` | `02 §8` |
| ADR-003 | UI layer separated from data layer | `02 §2`, `06 §4.1` |
| ADR-004 | Equation extraction owned by `SystemModelingModule` | `04 §3.1`, `06 §4.2` |
| ADR-005 | `QUndoStack` for command pattern | `02 §25`, `06 §8.2` |
| ADR-006 | Transfer-function/state-space owned by `ControllerDesignModule` | `04 §3.2`, `06 §4.3` |
| ADR-007 | CasADi as primary symbolic backend | `04 §3.3` |
| ADR-008 | Bond Graph causality assignment rules | `04 §8.9` |
| ADR-009 | DAE reduction strategy | `04 §25` |
| ADR-010 | Linearization owned by `ControllerDesignModule` | `04 §15.5–15.7` |
| ADR-011 | Dimensional analysis Phase 1/2/3 policy | `04 §16.5` |
| ADR-012 | `.systemdesign/` package directory format | `02 §29.1`, `05 §12.5–12.6` |
| ADR-013 | `StabilityAnalysisArtifact` ownership and schema | `05 §16` |
| ADR-014 | Closed-loop controller wrapper in `shared/engine/controllers/` | `05 §4.2.1` |
| ADR-015 | Unified Result Panel with grouped dropdowns | `03 §8.5`, `05 §14`, §16 |
| ADR-016 | `channel_selection.kind` schema (channels / io_pair / system_wide) | `03 §8.6`, `05 §14.4` |
| ADR-017 | Configuration / per-plot dropdown mirror sync | `03 §14.4.1`, `05 §14.5` |
| ADR-018 | WorkspaceModel signal payload contracts (12 fine-grained signals; delta-vs-id-only rule; synchronous emission) | `02 §4.1`, `02 §22`, `02 §23` |
| ADR-019 | Batch mutation mode and `WorkspaceChangeSet` (13th signal `modelChanged`; mutex with fine-grained signals; Mode B exception path) | `02 §4.1`, `02 §20.6`, `02 §22.2` |
| ADR-020 | Dirty tracking semantics (meaningful-edit principle; ε=1e-6 no-op tolerance; transition-only emission; deferred `cleanState` binding) | `02 §29.7`, `02 §32.2` |

ADRs are especially important because AI coding tools may otherwise reintroduce previously rejected architecture choices.

---

## 20. Strict Phase 1 Boundaries

Phase 1 must not implement:

* equation generation
* symbolic math
* DAE reduction
* state-space generation
* transfer function generation
* numerical simulation
* PID execution
* LQR / pole placement / MPC execution
* nonlinear solver integration
* HDF5 result storage
* Stability analysis computations

Phase 1 may implement:

* UI placeholders (including all plot type placeholders)
* configuration persistence (controller, I/O, simulation, plot_layout)
* graph structures required for future equation extraction
* validation metadata needed for future phases
* package format persistence with empty `result_refs`
* `channel_selection.kind` schema in `plot_layout` (UI editing deferred to Phase 2)
* mirror sync between Configuration and per-plot dropdowns

---

## 21. Acceptance Criteria

The architecture is acceptable when:

* module ownership is clear
* workspace state has one source of truth
* UI does not directly own graph state
* user edits go through commands
* project load/save uses direct model APIs and clears undo stack
* graph assembly is independent from UI
* `ControllerDesignModule` does not mutate workspace graph state
* equation extraction is assigned to `SystemModelingModule` for Phase 2+
* transfer-function/state-space preparation is assigned to `ControllerDesignModule` for Phase 2+
* stability analysis (eigenvalues, poles, zeros, frequency response, margins) is assigned to `ControllerDesignModule` for Phase 2+
* runtime controller execution adapters are assigned to `shared/engine/controllers/` for Phase 2+
* numerical simulation/backends are assigned to `shared/engine` for Phase 2+
* `shared/engine` is isolated in Phase 1 with enforced ImportError and CI architecture test
* project files use the `.systemdesign/` package directory format with `schema_version: 0.2.0`
* legacy single-file `.systemdesign` JSON projects can be migrated automatically to the package format
* `result_refs` field is preserved across save/load (empty array in Phase 1)
* `view` field is preserved across save/load (Phase 1 view state)
* Result Panel is a unified UI surface that can render both `SimulationResultArtifact` and `StabilityAnalysisArtifact` through grouped plot type dropdowns
* `channel_selection.kind` schema is preserved across save/load
* mirror synchronization between Configuration plot dropdowns and per-plot header dropdowns is implemented
* tests can exercise graph/model logic without launching the full UI
* CI architecture tests enforce module import boundaries
