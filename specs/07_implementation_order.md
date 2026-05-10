# 07_implementation_order.md

## 1. Purpose

This document defines the master implementation order for the Engineering System Designer.

It consolidates the implementation implications of the core requirements documents:

- `02_workspace_requirements.md`
- `03_configuration_requirements.md`
- `04_model_equations_requirements.md`
- `05_simulation_and_results_requirements.md`
- `06_data_flow_and_architecture.md`

The purpose of this document is not to repeat every requirement from those documents. The purpose is to define the correct build order, stage dependencies, acceptance gates, ADR compliance points, and AI-assisted development guardrails.

This document exists because AI-assisted implementation can easily reintroduce rejected architectural choices if the build order is underspecified.

Typical failure modes this document is designed to prevent:

- implementing numerical simulation before the ODE artifact contract is stable
- placing final `A/B/C/D` matrices inside the model equation artifact
- letting `shared/engine` leak into Phase 1 code
- duplicating plot state between configuration dropdowns and plot headers
- bypassing module ownership because a later module needs data early
- implementing plots against ad-hoc arrays instead of artifact contracts
- using UI graphics state as the source of truth
- rebuilding rejected legacy schema fields such as untyped signal lists
- treating controller design and controller runtime as the same ownership layer

The master rule is:

The implementation must proceed through explicit artifact contracts. A downstream stage may only consume an artifact after the upstream stage has produced it and its tests have passed.

---

## 2. Scope

This document covers:

- implementation sequencing
- stage naming
- phase mapping
- dependency ordering
- cross-document references
- ADR compliance points
- test gates
- acceptance criteria
- common AI-agent pitfalls
- forbidden shortcuts
- minimum deliverables per stage

This document does not replace:

- detailed workspace requirements in `02_workspace_requirements.md`
- detailed configuration requirements in `03_configuration_requirements.md`
- detailed equation requirements in `04_model_equations_requirements.md`
- detailed simulation and result requirements in `05_simulation_and_results_requirements.md`
- architectural ownership rules in `06_data_flow_and_architecture.md`
- execution constraints for AI coding agents in `08_codex_execution_rules.md`

---

## 3. Terminology

### 3.1 Product Phase

The term `Phase` is reserved for the product-level phases already used in the requirements documents.

Current product-level meaning:

| Product Phase | Meaning | Primary Documents |
|---|---|---|
| Phase 1 | Visual modeling tier: workspace, graph, validation, persistence, placeholders | `02`, `03`, `06` |
| Phase 2 | Equation extraction, simulation, stability, controller workflows, result visualization | `04`, `05`, `06` |
| Phase 3 | Advanced performance, streaming, nonlinear expansion, large-scale optimization | future extensions |

This document must not redefine Phase 1 or Phase 2 with different meanings.

### 3.2 Implementation Stage

This document uses the term `Stage` to define implementation order.

Stages are smaller than product phases and are dependency-aware.

Example:

- Product Phase 1 contains Stage S1 and Stage S2.
- Product Phase 2 contains Stage S3 through Stage S7.

This avoids conflict with the Phase terminology in `02` through `06`.

### 3.3 Artifact

An artifact is a typed output contract produced by one stage and consumed by a later stage.

Important artifacts:

- `WorkspaceModel`
- `SystemGraph`
- `ODEArtifact`
- `StabilityAnalysisArtifact`
- `SimulationRequest`
- `SimulationResultArtifact`
- `PlotSlotConfig`
- `ProjectPackage`

Artifacts are derived from source-of-truth data unless explicitly stated otherwise.

### 3.4 Source of Truth

The source of truth is the state that owns business meaning.

Examples:

- `WorkspaceModel` owns component and connection state.
- `ControllerDesignModule` owns controller settings, I/O selection, simulation settings, and plot layout.
- Derived equation, stability, and simulation artifacts are not primary project truth.
- UI graphics items are never business truth.

Reference:

- `02_workspace_requirements.md` §3
- `06_data_flow_and_architecture.md` §6

---

## 4. Stage Overview

The implementation order is:

| Stage | Product Phase | Name | Primary Output |
|---|---|---|---|
| S0 | Pre-Phase 1 | Architecture Scaffold and ADR Gate | import-boundary skeleton |
| S1 | Phase 1 | Workspace Foundation | `WorkspaceModel`, commands, graph assembly |
| S2 | Phase 1 | Configuration and Project Package | controller/config/plot placeholders, `.systemdesign/` package |
| S3 | Phase 2 Part A | Equation System | `ODEArtifact` |
| S4 | Phase 2 Part B | Simulation Engine | `SimulationResultArtifact` |
| S5 | Phase 2 Part C | Stability and Control Analysis | `StabilityAnalysisArtifact` |
| S6 | Phase 2 Part D | Plot and Result Rendering | unified result panel consuming artifacts |
| S7 | Phase 2 Part E | Controller Runtime Integration | closed-loop execution through `shared/engine/controllers/` |

A later stage may not be implemented by bypassing a missing earlier artifact.

---

## 5. Non-Negotiable Ownership Rules

### 5.1 Workspace Ownership

`SystemModelingModule` owns:

- workspace model
- graph assembly
- graph validation
- implicit node assembly
- model equation extraction workflow
- DAE generation
- ODE artifact generation

References:

- `02_workspace_requirements.md` §2, §3, §19, §20
- `04_model_equations_requirements.md` implementation sections
- `06_data_flow_and_architecture.md` §4.2

### 5.2 Controller Design Ownership

`ControllerDesignModule` owns:

- controller settings
- I/O selection
- simulation settings
- plot layout preferences
- transfer-function preparation
- state-space preparation
- linearization workflow
- stability analysis
- `StabilityAnalysisArtifact`

References:

- `03_configuration_requirements.md`
- `05_simulation_and_results_requirements.md` §16, §17
- `06_data_flow_and_architecture.md` §4.3, §12.2

### 5.3 Engine Ownership

`shared/engine` owns:

- numerical ODE execution
- solver adapter coordination
- backend execution
- time-domain simulation
- controller runtime adapters under `shared/engine/controllers/`

References:

- `05_simulation_and_results_requirements.md` simulation engine sections
- `06_data_flow_and_architecture.md` §5.7, §12.3

### 5.4 UI Ownership

UI owns rendering and interaction only.

UI must not own:

- graph state
- physics state
- equation state
- simulation state
- controller state

References:

- `02_workspace_requirements.md` §2, §3, §4
- `06_data_flow_and_architecture.md` §9

### 5.5 Artifact Ownership Summary

| Artifact | Owner | Consumer |
|---|---|---|
| `WorkspaceModel` | `SystemModelingModule` | workspace UI, graph assembler |
| `SystemGraph` | `SystemModelingModule` / `shared/graph` | equation builder |
| `ODEArtifact` | `SystemModelingModule` | `ControllerDesignModule`, `shared/engine` via request |
| `StabilityAnalysisArtifact` | `ControllerDesignModule` | result panel |
| `SimulationRequest` | `ControllerDesignModule` | `shared/engine` |
| `SimulationResultArtifact` | `shared/engine` result pipeline | result panel |
| `PlotSlotConfig` | `ControllerDesignModule` | result panel |
| `ProjectPackage` | application/project lifecycle | all modules |

---

## 6. Stage S0 — Architecture Scaffold and ADR Gate

### 6.1 Purpose

Stage S0 establishes the folder structure, import boundaries, ADR references, and test hooks before feature implementation begins.

This stage prevents later implementation from drifting into a monolithic design.

### 6.2 Product Phase

Pre-Phase 1.

### 6.3 Primary Documents

- `06_data_flow_and_architecture.md` §2, §3, §4, §5, §19, §20
- `08_codex_execution_rules.md` once available

### 6.4 Required Inputs

None.

### 6.5 Required Outputs

Folder skeleton:

```text
application/
  main.py
  bootstrap.py
  shell.py
  project_lifecycle.py

features/
  SystemModelingModule/
  ControllerDesignModule/

shared/
  components/
  graph/
  registry/
  probes/
  types/
  utils/
  engine/
    __init__.py
    controllers/
```

### 6.6 Implementation Steps

1. Create package structure from `06` §2.
2. Create bootstrap sequence from `06` §3.
3. Create empty `SystemModelingModule` and `ControllerDesignModule` shells.
4. Create `shared/engine/__init__.py` Phase 1 guard.
5. Add architecture import-boundary test from `06` §5.7.
6. Add placeholder ADR files or ADR index.
7. Add CI target for architecture tests.
8. Add lint rule or test that prevents feature/application imports from `shared.engine` during Phase 1.
9. Add project-level logging bootstrap.
10. Add minimal test layout.

### 6.7 Phase 1 Engine Isolation Rule

During Product Phase 1:

```python
# shared/engine/__init__.py
raise ImportError("shared.engine is not available in Phase 1")
```

No file in `application/` or `features/` may import:

```text
from shared.engine ...
import shared.engine
```

Reference:

- `06_data_flow_and_architecture.md` §5.7

### 6.8 Required ADRs

Minimum ADRs active before implementation:

- ADR-001 Phase 1 engine isolation
- ADR-002 Hybrid ULID identity model
- ADR-003 Workspace UI/data separation
- ADR-004 Equation builder ownership
- ADR-005 Command stack with `QUndoStack`
- ADR-006 Controller owns transfer-function/state-space preparation

If additional ADRs exist, this stage must include an ADR index.

### 6.9 Test Requirements

Minimum tests:

- architecture import-boundary test
- package import smoke test excluding `shared.engine` in Phase 1
- bootstrap order test or static check
- ADR index existence check

### 6.10 Acceptance Criteria

Stage S0 is complete when:

- folder skeleton exists
- Phase 1 engine import isolation test passes
- bootstrap order is documented
- module ownership comments/docstrings exist
- ADR index exists
- CI can run architecture tests

### 6.11 Common AI-Agent Pitfalls

Do not:

- import `shared.engine` while creating placeholders
- put simulation helpers into `ControllerDesignModule`
- put equation helpers into `application/`
- create a single global app state that owns everything
- create UI objects as the canonical data model

---

## 7. Stage S1 — Workspace Foundation

### 7.1 Purpose

Stage S1 implements the visual modeling and graph foundation required for all later stages.

This is the core of Product Phase 1.

### 7.2 Product Phase

Product Phase 1.

### 7.3 Primary Documents

- `02_workspace_requirements.md` entire document
- `06_data_flow_and_architecture.md` §4.2, §5.1, §5.3, §7, §8, §9, §10
- `06_data_flow_and_architecture.md` §20 for Phase 1 boundaries

### 7.4 Required Inputs

- Stage S0 architecture scaffold
- registry skeletons
- domain definitions
- component definition format

### 7.5 Required Outputs

- `WorkspaceModel`
- `ComponentInstance`
- `PortInstance`
- `Connection`
- `SelectionModel`
- `WorkspaceIdGenerator`
- `GraphAssembler`
- `GraphValidator`
- `ImplicitNode`
- command stack
- interactive workspace UI
- graph validation report

### 7.6 Implementation Step Group A — Identity Model

Implement before any persistence, graph assembly, or UI binding.

Required fields:

```json
{
  "id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
  "display_id": "resistor_3",
  "custom_label": "Input Resistor"
}
```

Rules:

- internal IDs use ULID-style prefixes
- `display_id` is user-readable but not authoritative
- `custom_label` is user-editable and optional
- internal IDs are never reused
- deleted display IDs are not reused during normal editing
- duplicate display IDs must not break project load

References:

- `02_workspace_requirements.md` §8
- `06_data_flow_and_architecture.md` §4.2.1

Required tests:

- ULID uniqueness
- display ID monotonicity
- counter reconstruction
- duplicate display ID warning behavior
- paste creates new internal IDs and display IDs

### 7.7 Implementation Step Group B — Component and Parameter Schema

Implement:

- `ComponentDefinition`
- `PortDefinition`
- `ParameterDefinition`
- `ParameterValue`
- `ComponentInstance`

Parameter definitions must support:

- `float`
- `int`
- `bool`
- `string`
- `enum`
- `expression`

Rules:

- definitions belong to registry
- instance stores values and overrides
- units must be explicitly preserved
- invalid parameters produce validation issues but must not crash

References:

- `02_workspace_requirements.md` §9, §11, §13
- `06_data_flow_and_architecture.md` §5.1, §5.2

Required tests:

- default parameter assignment
- type validation
- min/max validation
- enum validation
- unit preservation
- unknown field preservation

### 7.8 Implementation Step Group C — Workspace Model

Implement `WorkspaceModel` as the source of truth.

Must own:

- components
- connections
- positions
- rotations
- parameter values
- labels
- validation status
- dirty state

Must emit model signals:

- `componentAdded`
- `componentRemoved`
- `componentChanged`
- `componentMoved`
- `componentRotated`
- `connectionAdded`
- `connectionRemoved`
- `connectionChanged`
- `selectionChanged`
- `validationChanged`
- `modelReset`
- `dirtyChanged`

References:

- `02_workspace_requirements.md` §3, §4
- `06_data_flow_and_architecture.md` §6.1, §9

Required tests:

- signal emission order
- batch mode suppresses intermediate signals
- model reset causes full rebuild
- dirty state changes only on meaningful edits

### 7.9 Implementation Step Group D — Connection System

Implement:

- connection data model
- port references
- connection validation before mutation
- duplicate connection detection
- self-connection rejection
- same-domain connection rule
- attached connection deletion when component is deleted

References:

- `02_workspace_requirements.md` §14, §15, §22, §37
- `06_data_flow_and_architecture.md` §7.3, §7.4, §7.5

Required tests:

- valid same-domain connection succeeds
- cross-domain connection rejected
- self-connection rejected
- duplicate connection rejected
- missing component reference rejected
- component delete removes attached connections atomically
- connection re-target preserves connection ID
- re-target undo/redo works

### 7.10 Implementation Step Group E — Implicit Node Assembly

Implement union-find / disjoint-set assembly.

Rules:

- every port reference is a vertex
- every connection is an undirected edge
- connected groups become implicit nodes
- implicit nodes are runtime-derived
- implicit node IDs are not stable project references
- mixed-domain nodes are invalid

References:

- `02_workspace_requirements.md` §17, §18
- `06_data_flow_and_architecture.md` §10.1, §10.2

Required tests:

- two connected ports form one node
- chained connections form one node
- disconnected groups form separate nodes
- mixed-domain node invalid
- implicit nodes not serialized as primary project data

### 7.11 Implementation Step Group F — Validation Strategy

Implement validation in layers:

1. real-time connection validation
2. debounced workspace validation
3. future pre-simulation validation placeholders

Validation severity:

- `info`
- `warning`
- `error`

Rules:

- errors block later simulation
- warnings do not necessarily block editing
- validation must not freeze UI
- expensive validation must be deferred or asynchronous later

References:

- `02_workspace_requirements.md` §20
- `06_data_flow_and_architecture.md` §10.3

Required tests:

- invalid connection blocked before mutation
- dangling required ports reported
- missing ground/fixed reference reported
- invalid parameters reported
- stale cross-module I/O placeholder support does not crash
- validation debounce does not emit excessive signals

### 7.12 Implementation Step Group G — Command System

Use `QUndoStack` and `QUndoCommand`.

Required commands:

- `AddComponentCommand`
- `MoveComponentCommand`
- `RotateComponentCommand`
- `DeleteComponentCommand`
- `AddConnectionCommand`
- `DeleteConnectionCommand`
- `ModifyConnectionCommand`
- `ChangeParameterCommand`
- `PasteSelectionCommand`

Rules:

- user edits go through commands
- project load uses direct APIs
- selection-only changes are not undoable
- zoom and pan are not undoable
- move commits on mouse release
- parameter edit commits when editing finishes

References:

- `02_workspace_requirements.md` §25
- `06_data_flow_and_architecture.md` §8

Required tests:

- add undo/redo
- move undo/redo
- rotate undo/redo
- add connection undo/redo
- delete component with attached connections undo/redo
- parameter edit undo/redo
- paste compound command undo/redo

### 7.13 Implementation Step Group H — Workspace UI

Implement:

- `BlockDiagramWorkspaceView`
- `BlockDiagramWorkspaceScene`
- `ComponentGraphicsItem`
- `PortGraphicsItem`
- `ConnectionGraphicsItem`
- `GridBackgroundItem`

Rules:

- UI renders model state
- UI does not store business state
- UI actions produce commands
- zoom/pan are view-only
- snap-to-grid happens on drop/release
- hit testing uses tolerances
- z-order is deterministic

References:

- `02_workspace_requirements.md` §2, §5, §6, §7, §10, §12, §15, §16, §23, §26, §27, §28
- `06_data_flow_and_architecture.md` §7, §9, §17

Required tests:

- scene creates item for added component
- scene removes item for deleted component
- component movement updates connected wires
- rotation updates port visual positions
- selection updates info panel
- invalid connection target is visually indicated

### 7.14 Implementation Step Group I — Selection, Copy/Paste, Locking

Implement:

- single selection
- multi-selection
- rubber-band selection if feasible
- copy/paste/duplicate
- locking behavior

Rules:

- selection state is owned by `SelectionModel`
- deleting selected component deletes attached connections atomically
- copying selected components copies only internal connections
- locked components cannot be moved, rotated, deleted, or parameter-edited
- new connections to locked components are controlled by setting

References:

- `02_workspace_requirements.md` §21, §24, §38

Required tests:

- multi-select state consistency
- copy/paste generates new IDs
- internal connections preserved on paste
- external connections not preserved by default
- locked component move rejected
- locked component parameter edit rejected

### 7.15 Implementation Step Group J — Bond Graph Preparation Fields

Stage S1 must reserve fields needed by later Bond Graph work.

Do not implement full Bond Graph causality yet.

Reserve metadata/extensions for:

- across variable metadata
- through variable metadata
- effort variable metadata
- flow variable metadata
- causality marker
- power direction marker
- transformer/gyrator metadata
- coupling coefficient metadata

References:

- `02_workspace_requirements.md` §39
- `04_model_equations_requirements.md` Bond Graph preparation sections

Required tests:

- unknown metadata survives save/load
- connection style preserves reserved fields
- domain registry can define across/through variable labels
- reserved fields do not affect Phase 1 validation unless explicitly used

### 7.16 Stage S1 Acceptance Criteria

Stage S1 is complete when:

- components can be added, moved, rotated, copied, pasted, and deleted
- connections can be created and re-targeted
- invalid connections are blocked before mutation
- implicit nodes are assembled correctly
- graph validation reports invalid states
- command undo/redo works for all core editing operations
- UI reflects model signals
- data-layer tests run without GUI
- UI smoke tests pass
- architecture tests still prevent `shared.engine` import
- unknown fields in component/connection metadata are preserved
- Stage S1 does not implement equation extraction or simulation

### 7.17 Common AI-Agent Pitfalls

Do not:

- store connection endpoints using display IDs
- serialize implicit nodes as stable model data
- mutate `WorkspaceModel` directly from graphics items
- store business state inside `QGraphicsItem`
- implement equations while creating components
- import solver code for validation
- implement simulation buttons that run fake engine code
- ignore unknown fields during load/save
- implement `id = resistor_1` as internal ID after the ULID decision

---

## 8. Stage S2 — Configuration and Project Package

### 8.1 Purpose

Stage S2 completes Product Phase 1 by implementing controller/configuration placeholders, I/O selection persistence, plot layout persistence, and the directory-based project package format.

This stage is required before equation and simulation work because later stages depend on stable configuration contracts.

### 8.2 Product Phase

Product Phase 1.

### 8.3 Primary Documents

- `03_configuration_requirements.md`
- `02_workspace_requirements.md` §29, §30
- `05_simulation_and_results_requirements.md` plot slot schema sections
- `06_data_flow_and_architecture.md` §4.3, §6.2, §7.6, §7.7, §7.8, §11

### 8.4 Required Inputs

- Stage S1 `WorkspaceModel`
- Stage S1 selection and graph validation
- module skeleton from Stage S0

### 8.5 Required Outputs

- controller settings model
- I/O selection model
- simulation settings model
- plot layout model
- plot slot configuration model
- project serializer
- `.systemdesign/` project package
- migration path from legacy single JSON file
- mirror-sync state model for configuration dropdowns and plot headers

### 8.6 Implementation Step Group A — ControllerDesignModule Phase 1 State

Implement persistent placeholders for:

- controller settings
- I/O selection
- simulation settings
- plot layout preferences

Rules:

- no simulation execution
- no PID execution
- no transfer-function computation
- no state-space computation
- no workspace graph mutation

References:

- `06_data_flow_and_architecture.md` §4.3, §6.2, §20
- `03_configuration_requirements.md`

Required tests:

- controller settings serialize/deserialize
- I/O selection serialize/deserialize
- simulation settings serialize/deserialize
- plot layout serialize/deserialize
- settings changes mark project dirty

### 8.7 Implementation Step Group B — Cross-Module Reference Validation

Controller settings and I/O selections may reference workspace components and ports.

Rules:

- references must use internal IDs
- stale references are detected when components or ports are removed
- stale references produce validation warnings
- future execution must be blocked until stale references are resolved

References:

- `06_data_flow_and_architecture.md` §4.3.2
- `03_configuration_requirements.md`

Required tests:

- deleting referenced component marks I/O reference stale
- stale I/O reference appears in project validation
- stale reference does not crash UI
- stale reference survives load with warning
- resolving reference clears warning

### 8.8 Implementation Step Group C — Plot Slot Configuration

Implement plot slot schema.

Required fields include:

- `plot_type`
- `channel_selection`
- `result_ref`
- `analysis_ref`
- `metadata`
- `extensions`

Rules:

- `channel_selection.kind` is canonical
- legacy untyped signal lists must not be introduced
- unknown fields must be preserved
- plot type dropdown remains selectable even if artifact is missing

References:

- `05_simulation_and_results_requirements.md` §14
- `05_simulation_and_results_requirements.md` §14.4
- `05_simulation_and_results_requirements.md` §15.2
- ADR-016 channel selection kind

Required tests:

- plot slot round trip
- unknown field preservation
- `extensions` preservation
- invalid `channel_selection.kind` warning
- plot type selectable without artifact
- no legacy `signals: []` schema appears

### 8.9 Implementation Step Group D — Mirror Sync

The configuration dropdown and plot header dropdown must mirror the same state.

Rules:

- one canonical plot slot config state
- both UI controls render from same model
- changing one control updates the other
- no duplicate local state per widget

References:

- `03_configuration_requirements.md` §14.4.1
- `05_simulation_and_results_requirements.md` plot configuration sections
- ADR-017 mirror sync

Required tests:

- config dropdown change updates plot header
- plot header change updates config dropdown
- reload project preserves both views
- no diverging state after undo/redo or reset

### 8.10 Implementation Step Group E — Project Package Format

Projects are stored as directory packages.

Structure:

```text
project.systemdesign/
  project.json
  results/
    *.h5
  exports/
  recovery/
```

Rules:

- `project.json` stores model and configuration state
- HDF5 result data belongs in `results/`
- recovery data belongs in `recovery/`
- exported files belong in `exports/`
- legacy single-file `.systemdesign` JSON must be migrated
- unknown fields must be preserved during migration
- project package save must not silently overwrite external modifications

References:

- `02_workspace_requirements.md` §29.1
- `02_workspace_requirements.md` §29.3, §29.4, §29.5, §29.6, §29.7, §29.8
- `05_simulation_and_results_requirements.md` storage decisions
- `06_data_flow_and_architecture.md` §11

Required tests:

- save package
- load package
- migrate legacy single JSON
- preserve unknown fields
- detect external modification
- partial load failure quarantine
- recovery file behavior
- dirty state semantics

### 8.11 Implementation Step Group F — Autosave and Recovery

Implement autosave architecture.

Rules:

- autosave every 600 seconds if dirty
- autosave to recovery file
- autosave does not mark main file saved
- crash recovery is offered on startup
- only latest recovery file per project is required initially

References:

- `02_workspace_requirements.md` §30
- `06_data_flow_and_architecture.md` §7.8

Required tests:

- dirty project triggers recovery save
- non-dirty project does not autosave
- recovery load opens as dirty
- successful main save removes or obsoletes recovery file

### 8.12 Stage S2 Acceptance Criteria

Stage S2 is complete when:

- controller/configuration placeholders persist
- I/O references use internal IDs
- stale references are detected
- plot slot schema supports `channel_selection.kind`
- mirror sync works between dropdowns
- project saves as `.systemdesign/` package
- legacy single JSON migration works
- autosave/recovery works at package level
- Stage S2 still does not implement simulation, equation extraction, transfer functions, or controller execution

### 8.13 Common AI-Agent Pitfalls

Do not:

- store project as one large JSON file after the package decision
- duplicate plot config state between widgets
- use display IDs as I/O references
- add engine imports for simulation settings validation
- create fake result arrays in `project.json`
- store HDF5 data inside JSON
- let stale references crash load
- silently drop unknown fields

---

## 9. Stage S3 — Equation System

### 9.1 Purpose

Stage S3 implements model equation extraction and DAE-to-ODE preparation.

The output of this stage is the `ODEArtifact`.

This is the first major Product Phase 2 implementation stage.

### 9.2 Product Phase

Product Phase 2 Part A.

### 9.3 Primary Documents

- `04_model_equations_requirements.md`
- `06_data_flow_and_architecture.md` §4.2, §6.4, §12.1
- `02_workspace_requirements.md` §18, §19, §20, §39
- ADR-004 equation builder ownership

### 9.4 Required Inputs

- validated `SystemGraph`
- component definitions
- port/domain metadata
- parameter schemas
- implicit nodes
- Bond Graph preparation fields
- configuration I/O placeholders from Stage S2

### 9.5 Required Outputs

- equation definition registry
- symbolic placeholder resolver
- implicit node equations
- component equations
- DAE representation
- DAE classification
- causality assignment preparation
- algebraic elimination
- index reduction
- `ODEArtifact`

### 9.6 Implementation Step Group A — Equation Definition Extension

Extend component definitions with equation metadata.

Required capabilities:

- component-level equation definitions
- internal state declarations
- parameter symbol mapping
- port variable mapping
- domain variable mapping
- optional linearity metadata
- output/probe mapping preparation

Reference:

- `04_model_equations_requirements.md` implementation order
- `04_model_equations_requirements.md` equation definition sections

Required tests:

- component equation definitions validate
- missing symbol mapping detected
- duplicate state IDs detected
- invalid parameter references detected
- unknown extension fields preserved

### 9.7 Implementation Step Group B — Symbol Naming and Placeholder Resolution

Implement deterministic symbol naming.

Rules:

- state variables are referenced by `(component_id, state_id)`
- index-based references are forbidden for persistent mapping
- generated names must be deterministic
- display names are for UI only
- internal IDs are authoritative

References:

- `04_model_equations_requirements.md` state vector and symbol naming sections
- `02_workspace_requirements.md` §8

Required tests:

- deterministic symbol names after save/load
- renamed custom label does not change symbol identity
- component reorder does not change state identity
- duplicate display IDs do not break equation generation

### 9.8 Implementation Step Group C — Implicit Node Equation Generation

Generate node equations from implicit nodes.

Domain rules:

- across variables are equal within a node
- through variables sum to zero within a node

Initial domain mapping:

| Domain | Across | Through |
|---|---|---|
| Electrical | Voltage | Current |
| Mechanical Translational | Velocity | Force |

References:

- `02_workspace_requirements.md` §17, §18, §35, §39
- `04_model_equations_requirements.md` node equation sections
- Bond Graph preparation decisions

Required tests:

- electrical node voltage equality
- electrical KCL-style current sum
- mechanical velocity equality
- mechanical force balance
- mixed-domain node rejected before equation generation

### 9.9 Implementation Step Group D — DAE Representation

Build:

```text
F(x_dot, x, u, t) = 0
```

Rules:

- DAE is owned by SystemModelingModule
- DAE may contain algebraic variables
- DAE is not the final simulation contract
- DAE must preserve traceability to components, ports, and nodes

References:

- `04_model_equations_requirements.md` DAE sections
- `06_data_flow_and_architecture.md` §12.1

Required tests:

- single component DAE generation
- mass-spring DAE generation
- RC circuit DAE generation
- traceability metadata preserved
- invalid graph blocks DAE generation

### 9.10 Implementation Step Group E — DAE Classification and Reduction

Implement pipeline:

1. classification
2. causality preparation
3. algebraic elimination
4. index reduction
5. ODE extraction

Rules:

- if reduction fails, return structured validation error
- do not silently generate incorrect ODE
- nonlinear systems may produce nonlinear ODE
- linearity flag must be accurate enough for later stage decisions

References:

- `04_model_equations_requirements.md` DAE reduction sections
- `05_simulation_and_results_requirements.md` linearization dependency sections

Required tests:

- reducible DAE produces ODE
- irreducible DAE produces error
- algebraic loop reported
- singular system reported
- nonlinear system marks nonlinearity
- linear system marks linearity

### 9.11 Implementation Step Group F — ODEArtifact Contract

Produce:

```text
x_dot = f(x, u)
y     = h(x, u)
```

The artifact contains:

- state vector
- input vector
- output mapping
- parameter snapshot
- linearity flag
- time-dependency flag
- traceability metadata
- validation metadata

The artifact must not contain:

- final `A`
- final `B`
- final `C`
- final `D`
- transfer functions
- stability margins
- Bode data
- root locus data

References:

- `04_model_equations_requirements.md` ODE artifact sections
- `05_simulation_and_results_requirements.md` §16.5
- ADR-010 linearization ownership
- ADR-013 stability analysis artifact

Required tests:

- ODE artifact schema validation
- no `A/B/C/D` fields in ODE artifact
- state identity stable by `(component_id, state_id)`
- output mapping round trip
- linearity flag present
- traceability to graph objects

### 9.12 Stage S3 Acceptance Criteria

Stage S3 is complete when:

- validated `SystemGraph` can produce DAE
- DAE can reduce to ODE for golden examples
- ODE artifact is schema-validated
- ODE artifact contains no final state-space matrices
- invalid systems fail with structured errors
- golden tests for RC and mass-spring systems pass
- Stage S3 does not implement numerical simulation
- Stage S3 does not implement transfer functions or stability analysis

### 9.13 Common AI-Agent Pitfalls

Do not:

- place `A/B/C/D` into ODE artifact
- use list indices as stable state IDs
- generate equations from SVG geometry
- skip algebraic error reporting
- silently linearize nonlinear systems
- import `shared.engine` into equation builder
- let ControllerDesignModule own equation extraction
- use custom labels in symbolic references

---

## 10. Stage S4 — Simulation Engine

### 10.1 Purpose

Stage S4 implements numerical execution of ODE artifacts.

The output is `SimulationResultArtifact`.

### 10.2 Product Phase

Product Phase 2 Part B.

### 10.3 Primary Documents

- `05_simulation_and_results_requirements.md`
- `06_data_flow_and_architecture.md` §5.7, §12.3, §17
- `04_model_equations_requirements.md` ODE artifact contract
- ADR-007 CasADi backend
- ADR-014 controller runtime wrapper in `shared/engine`

### 10.4 Required Inputs

- valid `ODEArtifact`
- simulation settings from Stage S2
- I/O mapping from Stage S2/S3
- parameter snapshot
- solver configuration
- controller runtime interface placeholder

### 10.5 Required Outputs

- `SimulationRequest`
- solver adapter abstraction
- CasADi backend
- SciPy fallback backend
- worker-thread execution model
- `SimulationResultArtifact`
- HDF5 result storage
- channel registry

### 10.6 Implementation Step Group A — Engine Activation

Remove Phase 1 import guard only when Stage S3 ODE artifact is stable.

Rules:

- engine stays independent from UI
- engine does not own workspace
- engine does not own equation extraction
- engine receives execution-ready requests
- engine returns typed results

References:

- `06_data_flow_and_architecture.md` §5.7, §12.3
- `05_simulation_and_results_requirements.md` simulation engine sections

Required tests:

- engine imports only after Phase 2 gate
- feature modules do not depend on concrete backend classes
- request/result API smoke test
- engine has no UI imports

### 10.7 Implementation Step Group B — SimulationRequest

Define request object containing:

- ODE artifact reference or payload
- initial state
- input profile
- simulation time range
- solver settings
- parameter snapshot
- controller runtime config if closed-loop
- output channel selection

Rules:

- request must be immutable during execution
- request must be serializable enough for diagnostics
- request must not contain UI objects
- request must use internal IDs

References:

- `05_simulation_and_results_requirements.md` simulation execution sections
- `06_data_flow_and_architecture.md` §12.3

Required tests:

- request schema validation
- missing initial state reported
- invalid time range rejected
- stale ODE artifact rejected
- UI object cannot be serialized into request

### 10.8 Implementation Step Group C — Solver Adapter

Implement:

- solver interface
- CasADi adapter
- SciPy fallback adapter
- error mapping
- solver diagnostics

Rules:

- CasADi is primary
- SciPy fallback is internal
- fallback behavior must be explicit and logged
- solver errors must return structured diagnostics

References:

- `05_simulation_and_results_requirements.md` backend decision sections
- ADR-007 CasADi backend

Required tests:

- CasADi adapter runs golden ODE
- fallback adapter runs same golden ODE
- solver error maps to structured result
- fallback is logged
- invalid parameters fail predictably

### 10.9 Implementation Step Group D — Worker Thread Execution

Rules:

- model mutations run on main thread
- UI updates run on main thread
- engine computations may run in background thread
- background-to-UI communication uses queued Qt signals
- batch updates are Phase 2
- streaming is Phase 3 unless explicitly enabled later

References:

- `05_simulation_and_results_requirements.md` execution sections
- `06_data_flow_and_architecture.md` §17

Required tests:

- simulation does not block UI smoke test
- cancellation request handled
- failed simulation reports error without crashing
- result callback occurs on main thread boundary

### 10.10 Implementation Step Group E — SimulationResultArtifact

Store results in HDF5.

Rules:

- result data is channel-based
- artifact is immutable after creation
- JSON project stores references, not full data
- HDF5 stores full data
- channel IDs are stable enough for plot binding
- metadata preserves traceability

Example channel IDs:

```text
ch_state_<state_id>
ch_output_<output_id>
ch_input_<input_id>
```

References:

- `05_simulation_and_results_requirements.md` result artifact and storage sections
- Stage S2 package format

Required tests:

- HDF5 write/read round trip
- channel metadata preserved
- result reference stored in project JSON
- result artifact immutable
- missing HDF5 file reported
- result belongs to correct project package

### 10.11 Stage S4 Acceptance Criteria

Stage S4 is complete when:

- valid ODE artifact can be executed numerically
- CasADi backend works for golden systems
- SciPy fallback exists but is not primary public backend
- engine has no UI dependency
- results are stored in HDF5
- project JSON stores result references
- simulation errors are structured
- worker-thread execution does not violate Qt threading rules
- Stage S4 does not implement stability analysis

### 10.12 Common AI-Agent Pitfalls

Do not:

- write simulation arrays directly into `project.json`
- make `ControllerDesignModule` execute the solver directly
- import PySide UI classes into `shared/engine`
- mutate `WorkspaceModel` during simulation
- let solver output become source of truth for model state
- add ad-hoc plot arrays outside `SimulationResultArtifact`
- skip HDF5 because JSON is easier

---

## 11. Stage S5 — Stability and Control Analysis

### 11.1 Purpose

Stage S5 implements linearization, state-space representation, transfer functions, and stability analysis.

The output is `StabilityAnalysisArtifact`.

This stage must happen before full frequency-domain plot support.

### 11.2 Product Phase

Product Phase 2 Part C.

### 11.3 Primary Documents

- `05_simulation_and_results_requirements.md` §16, §17
- `04_model_equations_requirements.md` optional linearity metadata and ODE artifact contract
- `06_data_flow_and_architecture.md` §4.3, §6.4, §12.2
- ADR-006 controller owns transfer-function/state-space builder
- ADR-013 stability analysis artifact

### 11.4 Required Inputs

- valid `ODEArtifact`
- operating point policy
- I/O selection
- controller settings
- linearity metadata
- simulation results optionally for operating point source

### 11.5 Required Outputs

- linearization workflow
- state-space representation
- transfer-function representation
- `StabilityAnalysisArtifact`
- operating point resolution system
- stability validation and disabled-state rules

### 11.6 Implementation Step Group A — Operating Point System

Implement operating point sources:

- `zero`
- `component_initial_conditions`
- `user_specified`
- `last_simulation_initial`
- `last_simulation_final`
- `auto_equilibrium`

Rules:

- selected operating point source must be stored in configuration
- missing simulation result disables last-simulation operating point choices
- invalid user-specified operating point produces validation issue
- auto-equilibrium solves `f(x, u) = 0`

References:

- `05_simulation_and_results_requirements.md` §17
- `03_configuration_requirements.md` operating point configuration if defined

Required tests:

- zero operating point
- component initial conditions
- user-specified validation
- missing last simulation disables source
- auto-equilibrium success
- auto-equilibrium failure diagnostic

### 11.7 Implementation Step Group B — Linearization

Implement linearization around operating point.

Input:

```text
x_dot = f(x, u)
y     = h(x, u)
```

Output:

```text
A, B, C, D
```

Rules:

- linearization belongs to `ControllerDesignModule`
- ODE artifact must not be modified to store final matrices
- nonlinear systems may be linearized only through explicit workflow
- linearization failure must produce structured error
- time-varying systems require explicit handling or disabled state

References:

- `05_simulation_and_results_requirements.md` §16.3
- `05_simulation_and_results_requirements.md` §16.5
- `04_model_equations_requirements.md` linearity metadata
- `06_data_flow_and_architecture.md` §12.2

Required tests:

- linear mass-spring golden A/B/C/D
- RC circuit golden A/B/C/D
- nonlinear system explicit linearization path
- failed linearization reports error
- no matrices written into ODE artifact

### 11.8 Implementation Step Group C — Transfer Function and State-Space Builders

Implement builders owned by `ControllerDesignModule`.

Rules:

- transfer functions derive from state-space representation
- state-space representation derives from ODE artifact and operating point
- I/O selection controls transfer-function output
- stale I/O references block analysis

References:

- `06_data_flow_and_architecture.md` §4.3, §12.2
- ADR-006

Required tests:

- transfer function from known state-space
- selected input/output pair maps correctly
- stale I/O selection blocks transfer function
- MIMO case handled or explicitly limited
- unsupported case reports warning/error

### 11.9 Implementation Step Group D — StabilityAnalysisArtifact Schema

Artifact must contain:

- `A`
- `B`
- `C`
- `D`
- eigenvalues
- poles
- zeros
- transfer functions
- frequency response
- stability margins
- stability assessment
- operating point metadata
- source ODE artifact reference/hash
- source configuration hash
- validation metadata
- metadata
- extensions

Rules:

- owned by `ControllerDesignModule`
- consumed by result panel
- may be persisted as derived artifact reference if design requires
- must not become primary model truth
- invalid/stale artifact must be detected via hashes

References:

- `05_simulation_and_results_requirements.md` §16
- `06_data_flow_and_architecture.md` §6.4
- ADR-013

Required tests:

- schema round trip
- matrix dimensions validate
- eigenvalue golden test
- pole/zero golden test
- margin golden test
- source hash mismatch invalidates artifact
- unknown fields preserved

### 11.10 Implementation Step Group E — Disabled-State Rules

Analysis tools must be disabled or warned when:

- model is invalid
- ODE artifact missing
- selected I/O is stale
- operating point invalid
- linearization failed
- system is nonlinear and no linearization selected
- system is time-varying and unsupported
- analysis artifact is stale

References:

- `05_simulation_and_results_requirements.md` stability and plot disabled-state rules
- `03_configuration_requirements.md`

Required tests:

- disabled state when ODE missing
- disabled state when stale I/O
- warning when nonlinear but linearization possible
- stale artifact warning after workspace edit
- UI does not crash with missing analysis artifact

### 11.11 Stage S5 Acceptance Criteria

Stage S5 is complete when:

- operating point system works
- linearization produces correct A/B/C/D for golden systems
- state-space and transfer-function builders are owned by ControllerDesignModule
- `StabilityAnalysisArtifact` schema validates
- eigenvalue, poles, zeros, frequency response, and margins are produced
- stale artifacts are detected
- disabled-state rules work
- ODE artifact remains free of final `A/B/C/D`

### 11.12 Common AI-Agent Pitfalls

Do not:

- put linearization into `SystemModelingModule` as final state-space ownership
- write A/B/C/D into ODE artifact
- compute Bode directly from simulation result arrays when stability artifact is required
- ignore operating point source
- silently linearize without warning
- assume zero operating point always valid
- use display IDs in transfer-function I/O mapping
- treat stability artifact as primary project model

---

## 12. Stage S6 — Plot and Result Rendering

### 12.1 Purpose

Stage S6 implements the unified result panel and plot rendering against artifact contracts.

Plot system must be implemented after Stage S4 and Stage S5 for full support.

A minimal time-domain-only plot preview may be implemented after Stage S4, but complete Stage S6 requires `StabilityAnalysisArtifact`.

### 12.2 Product Phase

Product Phase 2 Part D.

### 12.3 Primary Documents

- `05_simulation_and_results_requirements.md` §14, §15, §16
- `03_configuration_requirements.md` plot configuration sections
- `06_data_flow_and_architecture.md` §14
- ADR-016 channel selection kind
- ADR-017 mirror sync

### 12.4 Required Inputs

- plot slot config from Stage S2
- `SimulationResultArtifact` from Stage S4
- `StabilityAnalysisArtifact` from Stage S5
- channel metadata
- I/O selection metadata
- result/analysis references

### 12.5 Required Outputs

- unified result panel
- four plot slots
- plot rendering dispatch
- artifact availability handling
- time-domain plots
- frequency-domain plots
- algebraic plots
- step response hybrid behavior
- fullscreen plot interaction if required

### 12.6 Implementation Step Group A — Unified Result Panel

Rules:

- one result panel
- no separate stability panel
- four plot slots by default
- plot types selectable independent of artifact availability
- missing artifact shows empty/disabled/diagnostic state, not hidden UI

Default slots:

1. Time Response
2. Step Response
3. Bode
4. Pole-Zero

References:

- `05_simulation_and_results_requirements.md` §14, §15
- Stage S2 plot config

Required tests:

- four slots render
- missing artifact shows diagnostic
- plot type remains selectable
- panel state persists
- fullscreen enter/exit preserves slot config

### 12.7 Implementation Step Group B — Plot Type Groups

Supported plot groups:

Time-domain:

- `time_response`
- `state_variables`
- `input_output_signal`
- `force`
- `road_profile`

Frequency-domain:

- `bode`
- `nyquist`

Algebraic:

- `pole_zero`
- `root_locus`
- `eigenvalue`

References:

- `05_simulation_and_results_requirements.md` plot type sections

Required tests:

- each supported plot type dispatches to correct renderer
- unsupported plot type produces warning
- group-based artifact requirement validated

### 12.8 Implementation Step Group C — Channel Selection

`channel_selection.kind` is canonical.

Kinds:

- `channels`
- `io_pair`
- `system_wide`

Usage:

| Kind | Intended Use |
|---|---|
| `channels` | time-domain channels |
| `io_pair` | transfer/frequency plots |
| `system_wide` | eigenvalues, poles, global analysis |

Rules:

- do not use untyped legacy signal arrays
- channel IDs must resolve against result metadata
- I/O pairs must resolve against analysis metadata
- system-wide plots do not require channel list

References:

- `05_simulation_and_results_requirements.md` §14.4
- ADR-016

Required tests:

- channel plot resolves channels
- Bode plot uses `io_pair`
- eigenvalue plot uses `system_wide`
- invalid kind produces validation error
- missing channel produces diagnostic

### 12.9 Implementation Step Group D — Artifact Binding Rules

General rule:

- time plots consume `SimulationResultArtifact`
- frequency plots consume `StabilityAnalysisArtifact`
- algebraic stability plots consume `StabilityAnalysisArtifact`

Step response special rule:

- `step_response` is the only plot type allowed to consume both artifact references
- both `result_ref` and `analysis_ref` may be non-null
- renderer must prefer `result_ref` when available
- if `result_ref` is null, fallback to `analysis_ref`

For all other plot types:

- exactly one of `result_ref` or `analysis_ref` must be non-null
- both non-null is validation error
- both null is missing-artifact state

References:

- `05_simulation_and_results_requirements.md` §15.2
- `05_simulation_and_results_requirements.md` step response clarification

Required tests:

- step response prefers result
- step response falls back to analysis
- non-step plot rejects dual refs
- non-step plot rejects missing ref when rendering required
- stale refs produce diagnostic

### 12.10 Implementation Step Group E — Rendering Logic

Plot source mapping:

| Plot Type | Source |
|---|---|
| Time Response | `SimulationResultArtifact` |
| State Variables | `SimulationResultArtifact` |
| Input/Output Signal | `SimulationResultArtifact` |
| Force | `SimulationResultArtifact` |
| Road Profile | `SimulationResultArtifact` |
| Bode | `StabilityAnalysisArtifact` |
| Nyquist | `StabilityAnalysisArtifact` |
| Pole-Zero | `StabilityAnalysisArtifact` |
| Root Locus | `StabilityAnalysisArtifact` |
| Eigenvalue | `StabilityAnalysisArtifact` |
| Step Response | hybrid |

References:

- `05_simulation_and_results_requirements.md` §15, §16
- `06_data_flow_and_architecture.md` §14

Required tests:

- renderer dispatch table complete
- wrong artifact type rejected
- missing channel metadata reported
- stale artifact hash warning
- plot can render after project reload

### 12.11 Stage S6 Acceptance Criteria

Stage S6 is complete when:

- unified result panel works
- four plot slots persist and render
- plot dropdown mirror sync still works
- time-domain plots consume simulation results
- frequency/algebraic plots consume stability artifact
- step response hybrid rule works exactly
- plot slot schema preserves metadata/extensions
- stale or missing artifacts do not crash rendering

### 12.12 Common AI-Agent Pitfalls

Do not:

- create separate Stability Panel
- bind Bode directly to simulation result
- introduce legacy `signals: []` field
- allow non-step plots to consume both result and analysis refs
- duplicate dropdown state
- hide plot type options when artifact is missing
- mutate result artifacts during rendering
- put plot data into workspace model

---

## 13. Stage S7 — Controller Runtime Integration

### 13.1 Purpose

Stage S7 integrates runtime controllers into numerical simulation.

This stage is intentionally after simulation, stability, and plot contracts are stable.

Controller design and controller runtime are separate ownership areas.

### 13.2 Product Phase

Product Phase 2 Part E.

### 13.3 Primary Documents

- `03_configuration_requirements.md`
- `05_simulation_and_results_requirements.md` controller runtime sections
- `06_data_flow_and_architecture.md` §5.7, §12.2, §12.3
- ADR-014 controller wrapper in `shared/engine`

### 13.4 Required Inputs

- controller settings
- `ODEArtifact`
- `SimulationRequest`
- solver adapter
- simulation result artifact
- optional stability analysis for controller design

### 13.5 Required Outputs

- runtime controller interface
- PID runtime adapter
- LQR runtime adapter if supported
- closed-loop simulation request
- closed-loop result channels

### 13.6 Implementation Step Group A — Runtime Controller Interface

Location:

```text
shared/engine/controllers/
```

Required interface:

```python
compute_control(state, error, dt) -> u
```

Rules:

- runtime interface belongs to engine
- controller design settings belong to ControllerDesignModule
- runtime adapter receives resolved numeric parameters
- runtime adapter must not mutate project configuration
- runtime adapter must not depend on UI

References:

- `06_data_flow_and_architecture.md` §5.7
- ADR-014

Required tests:

- runtime controller interface smoke test
- PID adapter deterministic output
- invalid controller parameters rejected
- no UI import in runtime controller package

### 13.7 Implementation Step Group B — Closed-Loop Simulation

Rules:

- closed-loop execution happens in `shared/engine`
- controller settings are resolved before request execution
- controller output appears as input channel
- simulation result includes controller-related channels
- controller runtime errors abort gracefully

References:

- `05_simulation_and_results_requirements.md`
- `06_data_flow_and_architecture.md` §12.3

Required tests:

- closed-loop golden example
- controller output channel written
- controller saturation if supported
- controller runtime error diagnostic
- result artifact stores closed-loop metadata

### 13.8 Implementation Step Group C — Controller Design Workflows

ControllerDesignModule may implement:

- PID tuning
- LQR
- pole placement

Rules:

- design workflows produce configuration and analysis data
- runtime execution remains in engine
- unsupported design workflows must be disabled, not partially faked

References:

- `03_configuration_requirements.md`
- `05_simulation_and_results_requirements.md`
- ADR-006
- ADR-014

Required tests:

- PID settings validation
- LQR disabled if required matrices missing
- pole placement disabled if system unsupported
- designed controller can be converted to runtime adapter config

### 13.9 Stage S7 Acceptance Criteria

Stage S7 is complete when:

- runtime controller interface exists under `shared/engine/controllers/`
- closed-loop simulation works through engine
- controller design remains in ControllerDesignModule
- runtime execution remains in engine
- closed-loop result channels are plotted through Stage S6
- controller errors are structured
- no controller runtime code mutates workspace graph

### 13.10 Common AI-Agent Pitfalls

Do not:

- execute PID directly inside ControllerDesignModule
- put runtime controllers in UI code
- mutate controller settings during simulation
- treat controller output as workspace state
- bypass `SimulationRequest`
- write controller channels outside result artifact
- make LQR run without valid state-space matrices

---

## 14. Cross-Stage Dependency Matrix

### 14.1 Hard Dependencies

| Stage | Depends On | Reason |
|---|---|---|
| S1 | S0 | architecture scaffold and import boundaries |
| S2 | S1 | configuration references workspace objects |
| S3 | S1 | equation builder requires `SystemGraph` |
| S3 | S2 | output and I/O mappings use configuration references |
| S4 | S3 | simulation requires `ODEArtifact` |
| S5 | S3 | linearization requires `ODEArtifact` |
| S5 | S2 | operating point and I/O selection come from config |
| S6 | S2 | plot slots come from config |
| S6 | S4 | time plots require simulation results |
| S6 | S5 | frequency/algebraic plots require stability artifact |
| S7 | S4 | closed-loop execution uses engine |
| S7 | S5 | many controller designs require state-space/stability data |
| S7 | S6 | controller output visualization uses plot system |

### 14.2 Parallelizable Work

| Work | Can Run In Parallel With | Conditions |
|---|---|---|
| UI styling | S1 data-layer tests | no model ownership changes |
| registry loading | S1 UI work | component schema stable |
| configuration panel UI | S1 late work | internal ID references stable |
| HDF5 storage prototype | S3 late work | no integration until ODE artifact stable |
| plot placeholder rendering | S2 | no real artifact binding until S4/S5 |
| ADR writing | all stages | must not contradict accepted docs |

### 14.3 Non-Parallelizable Work

Do not start:

- S4 engine integration before S3 ODE artifact contract is stable
- S5 stability artifact before S3 ODE artifact contract is stable
- full S6 frequency/algebraic rendering before S5 stability artifact exists
- S7 runtime controller execution before S4 simulation request/result contracts exist
- project package integration after result storage; package structure must be in S2

---

## 15. Corrected Compact Execution Order

The correct compact order is:

1. Architecture scaffold and import-boundary tests
2. Workspace identity model
3. Component, port, parameter schema
4. WorkspaceModel and signals
5. GraphAssembler and implicit node assembly
6. Validation system
7. Command system and UI binding
8. Configuration models and I/O references
9. Plot slot config and mirror sync
10. `.systemdesign/` project package persistence
11. Equation definition registry
12. Symbol naming and placeholder resolution
13. Node equation generation
14. DAE generation
15. DAE classification and reduction
16. ODEArtifact
17. SimulationRequest
18. CasADi solver adapter and SciPy fallback
19. SimulationResultArtifact and HDF5 storage
20. Operating point system
21. Linearization
22. State-space and transfer-function builders
23. StabilityAnalysisArtifact
24. Unified result panel time-domain rendering
25. Unified result panel frequency/algebraic rendering
26. Step response hybrid rendering
27. Runtime controller interface under `shared/engine/controllers/`
28. Closed-loop simulation
29. Controller design workflows
30. Final cross-document architecture acceptance

Important correction:

The full plot system is not complete before `StabilityAnalysisArtifact`.

Only time-domain plot rendering can be implemented immediately after `SimulationResultArtifact`.

---

## 16. ADR Compliance Checklist

### 16.1 ADR-001 — Phase 1 Engine Isolation

Relevant stages:

- S0
- S1
- S2

Must verify:

- `shared.engine` import blocked in Phase 1
- architecture test scans `features/` and `application/`
- no fake engine usage in placeholders

### 16.2 ADR-002 — Hybrid ULID Identity Model

Relevant stages:

- S1
- S2
- S3
- S5
- S6

Must verify:

- internal IDs use ULID-style prefixes
- display IDs not used as graph references
- custom labels not used as stable references
- pasted objects receive new IDs
- I/O and plot references use internal IDs

### 16.3 ADR-003 — Workspace UI/Data Separation

Relevant stages:

- S1

Must verify:

- `WorkspaceModel` is source of truth
- UI items do not own graph state
- user actions go through commands
- model signals drive UI updates

### 16.4 ADR-004 — Equation Builder Ownership

Relevant stages:

- S3

Must verify:

- equation extraction belongs to SystemModelingModule
- ControllerDesignModule does not generate DAE
- engine does not generate equations

### 16.5 ADR-005 — Command Stack with QUndoStack

Relevant stages:

- S1

Must verify:

- commands use `QUndoCommand`
- stack clean state aligns with save state
- compound commands are atomic
- zoom/pan/hover are non-undoable

### 16.6 ADR-006 — Controller Owns Transfer-Function and State-Space Builders

Relevant stages:

- S5
- S7

Must verify:

- state-space builder belongs to ControllerDesignModule
- transfer-function builder belongs to ControllerDesignModule
- ODE artifact does not store final state-space matrices

### 16.7 ADR-007 — CasADi Backend

Relevant stages:

- S4

Must verify:

- CasADi is primary backend
- SciPy is fallback/internal
- backend selection is logged and explicit
- engine owns solver adapters

### 16.8 ADR-008 — Bond Graph Causality

Relevant stages:

- S1 (Bond Graph preparation fields reserved)
- S3 (causality assignment in DAE pipeline)

Must verify:

- causality assignment runs as part of DAE pipeline
- causality conflicts produce structured diagnostics
- Bond Graph metadata fields preserved across save/load
- domain registry can declare across/through variable labels

### 16.9 ADR-009 — DAE Reduction Strategy

Relevant stages:

- S3

Must verify:

- DAE pipeline performs classification, causality preparation, algebraic elimination, and index reduction
- reducible DAE produces ODE artifact
- irreducible DAE produces structured error
- algebraic loop and singular system cases reported

### 16.10 ADR-010 — Linearization Ownership

Relevant stages:

- S5

Must verify:

- linearization workflow belongs to `ControllerDesignModule`
- ODE artifact remains free of final `A/B/C/D`
- linearization failure produces structured error
- nonlinear systems are linearized only through explicit workflow

### 16.11 ADR-011 — Dimensional Analysis Policy

Relevant stages:

- S1 (unit preservation in parameter schema)
- S3 (dimensional metadata in equation extraction)

Must verify:

- units preserved explicitly in parameter values
- canonical internal unit defined per parameter schema
- dimensional analysis policy follows the three-phase plan in `04 §16.5`
- unit incompatibilities reported as validation issues

### 16.12 ADR-012 — Project Package Directory Format

Relevant stages:

- S2
- S4

Must verify:

- project is stored as `.systemdesign/` directory bundle
- `project.json` stores model and configuration state
- HDF5 results stored under `results/`
- recovery files stored under `recovery/`
- legacy single JSON file migrates to package format
- unknown fields preserved across migration

### 16.13 ADR-013 — StabilityAnalysisArtifact

Relevant stages:

- S5
- S6

Must verify:

- artifact owned by ControllerDesignModule
- contains matrices, eigenvalues, poles/zeros, frequency response, margins
- consumed by frequency/algebraic plots
- ODE artifact stays clean

### 16.14 ADR-014 — Controller Runtime Wrapper in shared/engine

Relevant stages:

- S7

Must verify:

- runtime controllers live under `shared/engine/controllers/`
- design settings remain in ControllerDesignModule
- closed-loop execution occurs in engine

### 16.15 ADR-015 — Result Panel Unified With Grouped Dropdown

Relevant stages:

- S2 (plot slot config schema)
- S6 (rendering)

Must verify:

- one result panel renders both `SimulationResultArtifact` and `StabilityAnalysisArtifact`
- no separate stability panel exists
- plot type dropdowns are grouped (Time-domain, Frequency-domain, Algebraic, Unknown)
- plot type remains selectable independent of artifact availability

### 16.16 ADR-016 — channel_selection.kind Schema

Relevant stages:

- S2
- S6

Must verify:

- `channels`, `io_pair`, `system_wide` are canonical kinds
- legacy untyped signal arrays are not reintroduced
- plot renderer dispatch respects kind
- unknown extension fields preserved

### 16.17 ADR-017 — Mirror Sync Plot Dropdowns

Relevant stages:

- S2
- S6

Must verify:

- configuration dropdown and plot header dropdown share one canonical state
- no local divergent widget state
- changes propagate in both directions
- save/load preserves a single coherent state

### 16.18 ADR-018 — WorkspaceModel Signal Payload Contracts

Relevant stages:

- S1
- S2 (UI subscriber discipline preserved during persistence work)

Must verify:

- the 12 fine-grained signals carry the payload types specified in ADR-018
- `componentRotated` payload is `(str, float, float)`, not `(str, int, int)`
- subscribers refetch via model query only inside `componentChanged` / `componentAdded` / `connectionChanged` / `connectionAdded` slots
- subscribers do not mutate the model from inside a slot
- signal emission is synchronous (no queued cross-thread emission)
- multi-threaded signal emission is rejected; future work requires ADR amendment

### 16.19 ADR-019 — Batch Mutation Mode and WorkspaceChangeSet

Relevant stages:

- S1
- S2 (project load / `from_dict` uses batch)

Must verify:

- `modelChanged(change_set)` is the 13th signal; mutually exclusive with the 12 fine-grained signals
- `WorkspaceChangeSet` is frozen, slots, and exposes `is_empty()`
- empty batches do not emit `modelChanged`
- `reset_required=True` clears all other diff fields; subscribers check it first
- diff aggregation rules: add+remove → net zero; add+change → added only; exists+change+remove → removed only
- batch validation runs once on outermost exit, not per mutation
- subscriber exceptions during emission do not mask caller exceptions
- Mode B (best-effort commit) is the exception path; transactional rollback delegated to `QUndoStack.beginMacro`/`endMacro`
- selection signals are NOT suppressed during a batch (`selectionChanged` emits independently)

### 16.20 ADR-020 — Dirty Tracking Semantics

Relevant stages:

- S1 (`reset()` clear path)
- S1.7 (`QUndoStack.cleanState` binding)
- S2 (save clear path; save-clean atomicity)

Must verify:

- newly constructed `WorkspaceModel` is clean; no `dirtyChanged` at construction
- `dirtyChanged` emits on transitions only, not on every mutation
- no-op suppression uses ε=1e-6 tolerance for `QPointF` and `float`; exact `==` for other types
- `set_parameter` dispatches equality per parameter schema (S1.6)
- selection / validation / view changes do not mark dirty
- `reset()` clears dirty in S1.3
- save-clean atomicity is enforced when persistence lands in S2
- autosave-recovery path explicitly sets `dirty=True`; normal load leaves model clean

### 16.21 Cross-Cutting ADRs (Result Artifact Immutability and HDF5 Storage)

These items are covered by Stage acceptance criteria and Forbidden Anti-Patterns rather than as separate ADRs. They remain enforced via:

- §10.10 SimulationResultArtifact contract (immutability rule)
- §10.11 Stage S4 Acceptance Criteria (HDF5 storage rule)
- §17.2 Artifact Anti-Patterns (no raw arrays in `project.json`)
- §17.5 AI-Agent Shortcuts (no JSON result storage for large arrays)
- §18.6 Risk R6 (project package regresses to single JSON file)

---

## 17. Forbidden Anti-Patterns

### 17.1 Architecture Anti-Patterns

Forbidden:

- application layer owning graph data
- UI graphics owning business state
- ControllerDesignModule mutating workspace graph
- shared engine importing UI modules
- equation builder importing solver backends
- solver backend importing workspace UI

### 17.2 Artifact Anti-Patterns

Forbidden:

- `A/B/C/D` in ODE artifact
- transfer functions in ODE artifact
- Bode data in simulation result artifact unless explicitly stored as analysis output
- raw time-series data in `project.json`
- implicit nodes persisted as stable primary model data
- display IDs used as stable references

### 17.3 Plot Anti-Patterns

Forbidden:

- separate Stability Panel
- plot slot state duplicated across widgets
- `signals: []` legacy field
- Bode rendered from simulation result artifact
- non-step plot using both `result_ref` and `analysis_ref`
- hiding plot type options when artifact missing

### 17.4 Configuration Anti-Patterns

Forbidden:

- stale references silently removed
- stale references crashing load
- controller settings executing solvers
- configuration UI importing engine backend
- project settings stored only in UI widgets

### 17.5 AI-Agent Shortcuts

Forbidden:

- "temporary" matrices inside ODE artifact
- "quick" JSON result storage for large arrays
- fake simulation data to make plots work
- direct mutation to avoid commands
- skipping migration because file is new
- using labels as IDs because they are readable
- implementing Phase 2 inside Phase 1 placeholders

---

## 18. Risk Register for AI-Assisted Development

### 18.1 Risk R1 — Engine Leaks Into Phase 1

Description:

AI agent may import `shared.engine` to validate settings or create fake simulation placeholders.

Impact:

Breaks Phase 1 boundary and makes architecture untestable.

Early detection:

- static import-boundary test from S0
- CI scan for `shared.engine` imports

Mitigation:

- keep engine import guard active until Stage S4
- use placeholder models only in ControllerDesignModule

### 18.2 Risk R2 — ODE Artifact Polluted With State-Space Matrices

Description:

AI agent may place `A/B/C/D` in ODE artifact for convenience.

Impact:

Breaks ownership between SystemModelingModule and ControllerDesignModule.

Early detection:

- ODE artifact schema test rejects matrix fields
- ADR-010 checklist

Mitigation:

- linearization only in S5
- ODE artifact contract test in S3

### 18.3 Risk R3 — Plot State Duplicated

Description:

AI agent may create separate state in configuration dropdown and plot header dropdown.

Impact:

UI inconsistency and save/load bugs.

Early detection:

- mirror sync tests
- single state model inspection

Mitigation:

- one canonical `PlotSlotConfig`
- UI controls bind to same model

### 18.4 Risk R4 — Legacy Plot Signal Schema Reintroduced

Description:

AI agent may use simple `signals: []` field instead of `channel_selection.kind`.

Impact:

Breaks time/frequency/system-wide plot distinction.

Early detection:

- schema test forbids legacy field
- ADR-016 checklist

Mitigation:

- central `channel_selection` parser
- renderer dispatch requires kind

### 18.5 Risk R5 — Stability Plots Implemented Before Stability Artifact

Description:

AI agent may implement Bode/Pole-Zero using ad-hoc arrays or fake analysis.

Impact:

Creates incompatible plot path and bypasses ControllerDesignModule.

Early detection:

- renderer tests require `StabilityAnalysisArtifact`
- missing artifact diagnostic tests

Mitigation:

- allow only time-domain plot subset after S4
- enable frequency/algebraic plots after S5

### 18.6 Risk R6 — Project Package Regresses to Single JSON File

Description:

AI agent may save everything into one `.systemdesign` JSON file.

Impact:

Breaks HDF5 result storage, recovery structure, and future large project handling.

Early detection:

- project package tests
- file structure acceptance gate

Mitigation:

- serializer only writes package directory
- legacy single JSON supported only as migration input

### 18.7 Risk R7 — UI Becomes Source of Truth

Description:

AI agent may store positions, connections, or parameters in graphics items.

Impact:

Save/load and graph assembly become inconsistent.

Early detection:

- data-layer tests without GUI
- UI smoke tests driven by model signals

Mitigation:

- commands mutate `WorkspaceModel`
- graphics items render only

### 18.8 Risk R8 — Controller Runtime Placed in ControllerDesignModule

Description:

AI agent may implement PID execution in ControllerDesignModule because settings live there.

Impact:

Breaks runtime/design separation.

Early detection:

- controller runtime package tests
- architecture import/dependency review

Mitigation:

- design in ControllerDesignModule
- runtime in `shared/engine/controllers/`

---

## 19. Per-Stage Minimum Test Gates

### 19.1 S0 Test Gate

Must pass:

- architecture import-boundary test
- package import smoke test
- ADR index existence check

### 19.2 S1 Test Gate

Must pass:

- component tests
- connection tests
- node assembly tests
- validation tests
- command undo/redo tests
- selection tests
- locking tests
- UI smoke tests
- performance baseline test for 100 components / 300 connections

References:

- `02_workspace_requirements.md` §36
- `02_workspace_requirements.md` §31

### 19.3 S2 Test Gate

Must pass:

- configuration serialization tests
- stale reference tests
- plot slot schema tests
- mirror sync tests
- project package save/load tests
- migration tests
- autosave/recovery tests

References:

- `03_configuration_requirements.md`
- `02_workspace_requirements.md` §29, §30
- `05_simulation_and_results_requirements.md` plot slot sections

### 19.4 S3 Test Gate

Must pass:

- equation definition registry tests
- symbol resolution tests
- implicit node equation tests
- DAE generation tests
- DAE reduction tests
- ODE artifact schema tests
- golden RC test
- golden mass-spring test
- no `A/B/C/D` in ODE artifact test

References:

- `04_model_equations_requirements.md` test requirements

### 19.5 S4 Test Gate

Must pass:

- simulation request schema tests
- CasADi golden tests
- SciPy fallback tests
- solver error mapping tests
- worker-thread tests
- HDF5 result round-trip tests
- result immutability tests

References:

- `05_simulation_and_results_requirements.md` simulation and result tests

### 19.6 S5 Test Gate

Must pass:

- operating point tests
- auto-equilibrium tests
- linearization golden tests
- transfer-function tests
- stability artifact schema tests
- eigenvalue tests
- poles/zeros tests
- frequency response tests
- margins tests
- stale artifact invalidation tests

References:

- `05_simulation_and_results_requirements.md` §16, §17, §25

### 19.7 S6 Test Gate

Must pass:

- plot slot render tests
- artifact binding tests
- channel selection tests
- step response hybrid tests
- mirror sync regression tests
- missing artifact diagnostic tests
- stale artifact plot warning tests

References:

- `05_simulation_and_results_requirements.md` §14, §15

### 19.8 S7 Test Gate

Must pass:

- runtime controller interface tests
- PID runtime tests
- closed-loop simulation tests
- controller output channel tests
- controller runtime error tests
- no UI import in runtime controller package test

References:

- `05_simulation_and_results_requirements.md`
- `06_data_flow_and_architecture.md` §5.7

---

## 20. Stage Acceptance Summary

### 20.1 S0 Acceptance

Accepted when architecture skeleton and import-boundary enforcement exist.

### 20.2 S1 Acceptance

Accepted when visual workspace and graph foundation operate without equation or engine code.

### 20.3 S2 Acceptance

Accepted when configuration placeholders and project package persistence are stable.

### 20.4 S3 Acceptance

Accepted when ODE artifact is produced from validated graph and schema tests prove it does not contain state-space matrices.

### 20.5 S4 Acceptance

Accepted when numerical simulation produces immutable HDF5-backed result artifacts from ODE artifacts.

### 20.6 S5 Acceptance

Accepted when ControllerDesignModule produces `StabilityAnalysisArtifact` with state-space, transfer, and stability data.

### 20.7 S6 Acceptance

Accepted when one result panel renders time, frequency, algebraic, and hybrid plots through artifact contracts.

### 20.8 S7 Acceptance

Accepted when closed-loop simulation works through runtime controller adapters in `shared/engine/controllers/`.

---

## 21. Global Completion Criteria

The full implementation roadmap is complete when:

- all stage acceptance criteria pass
- all ADR compliance checks pass
- all architecture import-boundary tests pass
- all artifact schema tests pass
- all golden tests pass
- project package save/load/migration works
- ODE artifact contains no final `A/B/C/D`
- StabilityAnalysisArtifact contains final `A/B/C/D`
- HDF5 stores full simulation data
- JSON stores only project/config/result references
- one unified result panel renders all supported plot groups
- controller design and controller runtime remain separated
- AI-agent forbidden shortcuts are covered by tests or static checks

---

## 22. Open Implementation Questions

The following questions may require local implementation decisions but must not violate this document.

### 22.1 Component Registry Format

Question:

Should component definitions initially be Python classes, JSON files, or a hybrid?

Constraint:

The registry must preserve schema-driven parameters and port definitions.

Related documents:

- `02_workspace_requirements.md` §9, §13
- `06_data_flow_and_architecture.md` §5.2

### 22.2 Equation Definition Storage

Question:

Should equation definitions live inside component definition files or separate equation registry files?

Constraint:

EquationBuilder ownership remains in SystemModelingModule.

Related documents:

- `04_model_equations_requirements.md`
- ADR-004

### 22.3 HDF5 Result Index

Question:

Should `project.json` store a result index with hashes, timestamps, and plot-compatible channel summaries?

Constraint:

Full time-series data remains in HDF5.

Related documents:

- `05_simulation_and_results_requirements.md`
- §16.21 cross-cutting HDF5 storage rules

### 22.4 Plot Renderer Backend

Question:

Should plots initially use Matplotlib, PyQtGraph, or another renderer?

Constraint:

Renderer must consume artifacts through `PlotSlotConfig`, not raw module state.

Related documents:

- `05_simulation_and_results_requirements.md` §14, §15

### 22.5 Linearization Backend

Question:

Should linearization use CasADi symbolic differentiation, finite differences, or both?

Constraint:

Linearization output belongs to `StabilityAnalysisArtifact`, not ODE artifact.

Related documents:

- `05_simulation_and_results_requirements.md` §16
- ADR-013

---

## 23. Final Implementation Rule

The implementation must be artifact-driven.

The correct chain is:

```text
WorkspaceModel
→ SystemGraph
→ DAE
→ ODEArtifact
→ SimulationRequest
→ SimulationResultArtifact
→ OperatingPoint
→ Linearization
→ StabilityAnalysisArtifact
→ PlotSlotConfig rendering
→ Runtime controller execution
```

No stage may skip the artifact immediately before it.

No module may write an artifact owned by another module.

No UI component may become the source of truth for model, equation, simulation, stability, or controller state.
