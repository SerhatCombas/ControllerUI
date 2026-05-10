# 08 — Codex / AI-Agent Execution Rules

## 1. Purpose

**Document type:** Execution contract  
**Audience:** AI coding agents, Codex, Claude Code, Cursor agents, human reviewers  
**Scope:** How implementation work must be executed  
**Non-scope:** Feature specification, UI design, physics theory, solver derivation

This document defines mandatory execution rules for AI-assisted development of the Engineering System Designer.

It exists to prevent AI agents from:

- violating architecture ownership boundaries
- implementing stages in the wrong order
- mixing specification layers
- duplicating source-of-truth state
- placing artifacts in the wrong module
- reintroducing rejected legacy schemas
- silently changing public contracts
- creating fake or hardcoded behavior to make tests or plots appear to work

The Engineering System Designer is a model-first, artifact-driven engineering tool inspired by Simscape / Modelica. The user-facing capabilities (component placement, port connection, graph assembly, equation derivation, simulation, stability analysis, unified result visualization) are specified in detail in `02` through `06`. This document does not redefine those capabilities; it constrains the **implementation behavior** of AI agents who build them.

AI agents must implement this system by following the project architecture, stage order, artifact contracts, and forbidden-boundary rules.

This document is **not** a feature specification.

This document is an **execution contract**.

The agent must treat the architecture as a contract, not as a suggestion.

---

## 2. Golden Rule

### 2.1 Strict Ownership Separation

The most important rule of the project is:

> Each module owns exactly its own responsibility. No module may secretly own another module’s artifact, state, or computation.

| Layer / Module | Owns | Must Not Own |
|---|---|---|
| `SystemModelingModule` | workspace, components, ports, graph, DAE, ODE artifact | controller design, A/B/C/D, TF, stability margins |
| `ControllerDesignModule` | linearization, state-space, transfer functions, poles, zeros, stability analysis | workspace graph editing, simulation runtime |
| `shared/engine` | runtime simulation, solver execution, runtime controller execution | design-time controller synthesis, UI state |
| `UI` | rendering, interaction dispatch, visual feedback | source-of-truth model, physics, artifact ownership |
| `shared/registry` | schemas, component definitions, domain definitions | runtime simulation behavior |
| `shared/probes` | output/signal definitions | plot state, solver state |

### 2.2 The UI Is Never the Source of Truth

The UI may render:

- workspace state
- component visuals
- validation messages
- plot outputs
- configuration forms

The UI must not become the canonical storage for:

- component parameters
- connections
- graph topology
- equation state
- simulation result data
- plot slot schema
- controller definitions

If an AI agent reads a value directly from a widget to drive physics, it is violating the architecture.

### 2.3 ODE Is Not State-Space

The ODE artifact contains the nonlinear or symbolic/numeric dynamic model:

```text
x_dot = f(x, u, p, t)
y     = h(x, u, p, t)
```

The ODE artifact must not contain:

- `A`
- `B`
- `C`
- `D`
- transfer functions
- poles
- zeros
- Bode data
- Nyquist data
- stability margins

`A`, `B`, `C`, `D` belong only to the controller/stability layer.

---

## 3. Document Hierarchy and Authority

When documents overlap or appear to conflict, the AI agent must use the following authority order.

### 3.1 Authority Order

| Priority | Document / Source | Authority |
|---|---|---|
| 1 | Explicit user instruction in current task | Highest, unless it violates forbidden architecture rules |
| 2 | `08_codex_execution_rules.md` | Execution behavior and AI-agent constraints |
| 3 | `07_implementation_order.md` | Stage order and acceptance gates |
| 4 | `06_data_flow_and_architecture.md` | Architecture, ownership, artifact flow |
| 5 | `04_model_equations_requirements.md` | Equation, DAE, ODE details |
| 6 | `05_simulation_and_results_requirements.md` | Simulation, result, plot, stability details |
| 7 | `03_configuration_requirements.md` | Parameter/configuration rules |
| 8 | `02_workspace_requirements.md` | Workspace, graph, validation |
| 9 | `01_library_requirements.md` | Component library requirements |
| 10 | `README.md` | Project overview |
| 11 | Existing code | Lowest if it conflicts with the documented architecture |

### 3.2 Conflict Rule

If two documents conflict, the AI agent must not silently choose one.

The agent must:

1. identify the conflict
2. cite both conflicting rules by document/section if known
3. choose the safer architecture-preserving path only if the conflict is minor
4. stop and ask for clarification if the conflict affects ownership, schema, artifacts, or stage order

### 3.3 Existing Code Is Not Automatically Correct

Existing code may be transitional, legacy, or incomplete.

The AI agent must not assume existing code is the final architecture if it conflicts with:

- artifact-driven architecture
- strict ownership separation
- stage order
- current requirement documents

Legacy code may be wrapped, migrated, or isolated, but not used to justify architectural regression.

---

## 4. Mandatory Implementation Order

The AI agent must follow this order unless the user explicitly instructs otherwise and the change does not violate architecture boundaries.

```text
S0 Architecture
→ S1 Workspace
→ S2 Configuration
→ S3 Equation
→ S4 Simulation
→ S5 Stability
→ S6 Plot
→ S7 Controller Runtime
```

Compact flow:

```text
Workspace
→ Configuration
→ Equation
→ Simulation
→ Stability
→ Plot
→ Controller Runtime
```

### 4.1 Stage Table

| Stage | Name | Primary Output |
|---|---|---|
| S0 | Architecture | folder skeleton, contracts, guards, ADR baseline |
| S1 | Workspace | workspace model, graph, validation |
| S2 | Configuration | parameters, units, initial conditions |
| S3 | Equation | DAE artifact, ODE artifact |
| S4 | Simulation | simulation request/result, solver integration |
| S5 | Stability | state-space, TF, stability artifact |
| S6 | Plot | unified plot panel and artifact bindings |
| S7 | Controller Runtime | runtime controller execution in engine |

### 4.2 Stage Jumping Rule

The AI agent must not implement later-stage behavior inside earlier-stage placeholders.

Examples:

- Do not implement real simulation during S1.
- Do not add fake state-space matrices during S3.
- Do not create Bode plots before stability artifacts exist.
- Do not create runtime controller loops inside ControllerDesignModule.

Placeholders are allowed only if they are explicit, isolated, and do not pretend to be production behavior.

---

## 5. Per-Stage Execution Rules

### 5.1 Stage S0 — Architecture Execution Rules

#### Purpose

S0 establishes the project structure, contracts, ownership boundaries, and architectural guards.

#### Do First

Before writing S0 code, the AI agent must:

1. read the project summary
2. identify the intended module boundaries
3. confirm the folder skeleton
4. confirm no runtime engine dependency is needed yet
5. check whether existing files conflict with the desired architecture

#### Allowed Work

The agent may create or update:

- folder skeleton
- module `__init__` files
- basic dataclass schemas
- abstract interfaces
- import guards
- ADR placeholders
- contract tests
- architecture smoke tests

#### Forbidden Work

The agent must not:

- implement solver runtime
- implement controller design algorithms
- implement UI-heavy behavior
- implement fake physics
- import `shared/engine` into modeling modules
- remove import guards that prevent premature stage coupling
- create hidden global state

#### Acceptance Checks

S0 is complete only when:

- module boundaries are visible in the folder structure
- tests can import the main packages
- forbidden imports are guarded or absent
- no later-stage computation is hidden in architecture scaffolding

---

### 5.2 Stage S1 — Workspace Execution Rules

#### Purpose

S1 implements the workspace model, component instances, ports, connections, implicit nodes, and graph validation.

#### Do First

Before S1 implementation, the AI agent must read:

- `01_library_requirements.md`
- `02_workspace_requirements.md`
- relevant ownership sections in `06_data_flow_and_architecture.md`
- S1 sequence in `07_implementation_order.md`

#### Required Concepts

S1 must preserve the ID model:

| Field | Purpose |
|---|---|
| `id` | stable system reference, preferably ULID |
| `display_id` | user-visible readable ID |
| `custom_label` | optional user override |

#### Allowed Work

The agent may implement:

- `ComponentInstance`
- `Port`
- `Connection`
- `ImplicitNode`
- workspace model serialization
- graph construction
- connection validation
- domain compatibility checks
- realtime validation
- debounced workspace validation
- command-based editing

#### Forbidden Work

The agent must not:

- use display labels as stable IDs
- serialize implicit nodes as primary user-authored data
- store workspace truth in UI widgets
- bypass graph validation to make connections work
- hardcode quarter-car topology into generic workspace code
- add equation-building logic into the workspace UI
- add simulation-specific fields into workspace components

#### Validation Levels

S1 must distinguish:

| Validation Level | Purpose |
|---|---|
| realtime | immediate connection feedback |
| debounced | whole-workspace validation |
| future simulation | later-stage solver readiness |

#### Acceptance Checks

S1 is complete only when:

- graph construction is deterministic
- invalid connections are rejected or clearly marked
- domain compatibility is enforced
- component IDs remain stable after label changes
- workspace state can be serialized without UI state

---

### 5.3 Stage S2 — Configuration Execution Rules

#### Purpose

S2 implements parameters, units, initial conditions, configuration validation, and component configuration contracts.

#### Do First

Before S2 implementation, the AI agent must read:

- `03_configuration_requirements.md`
- S2 sections in `07_implementation_order.md`
- relevant schema ownership rules in `06_data_flow_and_architecture.md`

#### Allowed Work

The agent may implement:

- parameter schemas
- default values
- unit metadata
- validation ranges
- initial condition schemas
- configuration panels that write to model state through commands
- migration-safe configuration serialization

#### Forbidden Work

The agent must not:

- store configuration only in UI widgets
- mix configuration state with plot state
- write solver-specific values directly into component configuration unless the schema defines them
- create duplicate parameter stores
- silently coerce invalid units without validation messages
- introduce hidden defaults that are not visible in the schema

#### Initial Condition Rule

Initial conditions belong to configuration/model contracts, not to plot configuration and not to solver internals.

#### Acceptance Checks

S2 is complete only when:

- parameters serialize and deserialize correctly
- unit metadata is preserved
- invalid values generate structured validation errors
- initial conditions are linked by stable component/state identifiers
- UI edits update model state through proper commands or state services

---

### 5.4 Stage S3 — Equation Execution Rules

#### Purpose

S3 transforms the system graph into equations, then DAE, then ODE artifact.

#### Do First

Before S3 implementation, the AI agent must read:

- `04_model_equations_requirements.md`
- relevant graph rules from `02_workspace_requirements.md`
- artifact flow rules from `06_data_flow_and_architecture.md`
- S3 order from `07_implementation_order.md`

#### Required Pipeline

The equation pipeline must follow this conceptual flow:

```text
SystemGraph
→ EquationBuilder
→ DAE
→ classification
→ causality handling
→ algebraic elimination
→ index reduction
→ ODEArtifact
```

#### Allowed Work

The agent may implement:

- equation records
- DAE structures
- ODE artifact schema
- state vector mapping
- input/output mapping
- parameter references
- linearity flag
- equation trace metadata
- graph-to-equation tests

#### Forbidden Work

The agent must not:

- place `A`, `B`, `C`, `D` inside ODE artifacts
- create temporary matrices inside ODE artifacts for convenience
- add transfer functions to ODE artifacts
- hardcode quarter-car equations in the generic equation builder
- use index-only state mapping without stable component/state identity
- skip algebraic constraints by deleting equations
- hide unresolved DAE issues behind fake ODE output

#### State Mapping Rule

State references must be stable and semantic.

Preferred mapping:

```text
(component_id, state_id)
```

Forbidden mapping as sole source of truth:

```text
state_index only
```

Indexes may exist as derived runtime order, but not as the canonical identity.

#### Acceptance Checks

S3 is complete only when:

- DAE generation is traceable
- ODE artifact excludes all state-space/stability fields
- state mapping survives reordering
- equation tests cover at least simple mechanical/electrical examples
- invalid or unsupported systems produce structured errors, not fake equations

---

### 5.5 Stage S4 — Simulation Execution Rules

#### Purpose

S4 executes simulation using ODE artifacts and produces simulation result artifacts.

#### Do First

Before S4 implementation, the AI agent must read:

- `05_simulation_and_results_requirements.md`
- `06_data_flow_and_architecture.md`
- S4 order in `07_implementation_order.md`

#### Runtime Backend Rule

Primary backend:

```text
CasADi
```

Fallback backend:

```text
SciPy
```

The fallback must not become a separate architecture.

#### Allowed Work

The agent may implement:

- `SimulationRequest`
- solver backend interface
- CasADi backend
- SciPy fallback backend
- simulation metadata
- time-series channel writing
- `SimulationResultArtifact`
- HDF5 storage
- result loading by channel reference

#### Forbidden Work

The agent must not:

- store full time-series data in JSON
- fake simulation arrays to make plots work
- make the UI generate simulation results
- mutate ODE artifact during simulation
- back-write solver results into workspace state
- hide solver failures by returning empty successful artifacts
- mix stability frequency response with simulation result data

#### Storage Rule

| Storage | Allowed Content |
|---|---|
| JSON | metadata, references, schema version, artifact IDs |
| HDF5 | full numeric arrays, time-series channels, large result data |

#### Acceptance Checks

S4 is complete only when:

- simulation consumes ODE artifacts
- results are immutable artifacts
- large data is stored outside JSON
- solver errors are structured
- result channels can be referenced by stable IDs

---

### 5.6 Stage S5 — Stability Execution Rules

#### Purpose

S5 performs linearization, state-space generation, transfer function generation, and stability analysis.

#### Do First

Before S5 implementation, the AI agent must read:

- stability sections in `05_simulation_and_results_requirements.md`
- ownership sections in `06_data_flow_and_architecture.md`
- S5 in `07_implementation_order.md`

#### Ownership Rule

Only `ControllerDesignModule` owns:

- linearization
- `A`, `B`, `C`, `D`
- transfer functions
- poles
- zeros
- eigenvalues
- margins
- frequency response
- operating point selection

#### Allowed Work

The agent may implement:

- operating point selection
- zero/initial/last-simulation/auto-equilibrium operating point modes
- linearization
- state-space artifact generation
- transfer function generation
- pole-zero computation
- Bode/Nyquist data generation
- stability margins
- `StabilityAnalysisArtifact`

#### Forbidden Work

The agent must not:

- write `A/B/C/D` back into the ODE artifact
- make simulation engine own transfer functions
- create stability data inside plot code
- make Bode plots compute their own hidden transfer functions
- assume all systems are linear without checking the linearity flag
- ignore nonlinear warnings

#### Operating Point Rule

Supported operating point sources:

| Source | Meaning |
|---|---|
| `zero` | zero state/input reference |
| `initial` | configured initial conditions |
| `last_simulation` | final or selected simulation state |
| `auto_equilibrium` | solve `f(x, u) = 0` |

If `auto_equilibrium` fails, the artifact must report failure. It must not silently fall back without telling the user.

#### Acceptance Checks

S5 is complete only when:

- `StabilityAnalysisArtifact` owns all state-space/stability data
- ODE artifact remains clean
- nonlinear systems are detected or warned
- transfer function data is traceable to I/O selections
- eigenvalue/pole tests exist

---

### 5.7 Stage S6 — Plot Execution Rules

#### Purpose

S6 implements the unified result panel and artifact-bound plot system.

#### Do First

Before S6 implementation, the AI agent must read:

- plot sections in `05_simulation_and_results_requirements.md`
- data-flow rules in `06_data_flow_and_architecture.md`
- S6 in `07_implementation_order.md`

#### Unified Panel Rule

There is only one result panel.

Forbidden:

```text
Separate stability panel
```

Required:

```text
Unified result panel
```

#### Plot Slots

The result panel has four plot slots.

Supported plot types include:

- `time_response`
- `state_variables`
- `bode`
- `nyquist`
- `pole_zero`
- `eigenvalue`

#### Plot Binding Rule

Time-domain plots normally use:

```text
result_ref
```

Frequency/stability plots normally use:

```text
analysis_ref
```

Step response may use both:

```text
result_ref + analysis_ref
```

Priority for step response:

```text
1. result_ref
2. fallback to analysis_ref
```

#### Channel Selection Rule

| `channel_selection.kind` | Used For |
|---|---|
| `channels` | time plots |
| `io_pair` | transfer-function plots |
| `system_wide` | eigenvalue and system-level plots |

#### Forbidden Work

The agent must not:

- revive legacy `signals[]` schema
- duplicate plot state in the UI
- compute stability data inside plot widgets
- compute simulation data inside plot widgets
- use raw array paths instead of artifact/channel references
- create separate stability visualization state
- hide missing artifact references by showing fake data

#### Acceptance Checks

S6 is complete only when:

- plot slots bind to artifacts
- plot state serializes through the plot schema
- time plots resolve result channels
- frequency plots resolve stability analysis references
- step response priority is implemented correctly

---

### 5.8 Stage S7 — Controller Runtime Execution Rules

#### Purpose

S7 implements runtime controller execution in the simulation engine.

#### Do First

Before S7 implementation, the AI agent must read:

- controller sections in `05_simulation_and_results_requirements.md`
- ownership sections in `06_data_flow_and_architecture.md`
- S7 order in `07_implementation_order.md`

#### Design vs Runtime Rule

| Layer | Owns |
|---|---|
| `ControllerDesignModule` | controller synthesis/design |
| `shared/engine/controllers` | runtime controller execution |

Runtime interface:

```text
compute_control(state, error, dt) -> u
```

#### Allowed Work

The agent may implement:

- runtime PID controller execution
- runtime state feedback execution
- controller interface
- control signal logging
- closed-loop simulation integration
- controller runtime tests

#### Forbidden Work

The agent must not:

- implement design algorithms inside runtime engine
- implement runtime loop inside ControllerDesignModule
- make controller runtime depend on UI widgets
- mutate controller design artifacts during simulation
- hide unstable controller behavior by clipping without reporting

#### Acceptance Checks

S7 is complete only when:

- runtime controllers execute through engine interfaces
- design artifacts are read but not mutated
- closed-loop simulation is testable
- controller outputs are logged as result channels

---

## 6. Forbidden Actions

This section is mandatory. If any rule here conflicts with a coding shortcut, the rule wins.

### 6.1 Architecture Forbidden Actions

The AI agent must never:

1. make UI the source of truth
2. merge SystemModelingModule and ControllerDesignModule responsibilities
3. make `shared/engine` own design-time state-space analysis
4. make ControllerDesignModule own runtime simulation loops
5. bypass graph construction with hardcoded topology
6. implement future-stage features inside earlier-stage placeholders
7. introduce hidden global mutable state
8. introduce circular dependencies between feature modules
9. depend on widget state for physics computation
10. treat existing legacy code as higher authority than the architecture documents

### 6.2 Artifact Forbidden Actions

The AI agent must never:

1. put `A/B/C/D` in ODEArtifact
2. put transfer functions in ODEArtifact
3. put poles/zeros/margins in ODEArtifact
4. store full simulation data in JSON
5. mutate immutable artifacts after publication
6. duplicate artifact data in multiple places without a defined reference mechanism
7. use display labels as artifact IDs
8. create fake artifact references
9. silently drop artifact fields during serialization
10. change artifact schemas without tests and migration notes

### 6.3 Plot Forbidden Actions

The AI agent must never:

1. create a separate stability panel
2. revive `signals[]` legacy schema
3. duplicate plot state in UI widgets
4. compute transfer functions inside plot widgets
5. compute solver results inside plot widgets
6. show fake plot data when artifacts are missing
7. bind plots directly to unstable file paths instead of artifact references
8. mix configuration state with plot state
9. use `channels` selection for transfer-function plots
10. use `io_pair` selection for raw time-series plots

### 6.4 Configuration Forbidden Actions

The AI agent must never:

1. store parameters only in UI controls
2. create multiple competing parameter stores
3. silently change units
4. hide defaults outside schemas
5. mix initial conditions with solver internals
6. write solver result values back into initial configuration without explicit user action
7. use labels instead of stable IDs for parameter references
8. ignore invalid ranges to keep simulation running
9. skip validation because a field is “temporary”
10. add undocumented compatibility fields

### 6.5 AI-Agent Shortcut Forbidden Actions

The AI agent must never:

1. add “temporary” matrices inside ODEArtifact
2. store “quick” result arrays in JSON
3. fake simulation data to make plots work
4. directly mutate model state to avoid command/state-service logic
5. skip migration because “the file is new”
6. use readable labels as IDs because they are convenient
7. implement Phase 2 behavior inside Phase 1 placeholders
8. create hardcoded quarter-car exceptions in generic systems
9. suppress failing tests without architectural explanation
10. remove validation to make UI interaction easier
11. catch all exceptions and return success
12. create shadow schemas in UI code
13. duplicate domain rules in multiple modules instead of using registry/domain contracts
14. invent new artifact fields without checking owner and consumer
15. produce code that passes only by relying on execution order side effects

---

## 7. Artifact Contract Rules

### 7.1 WorkspaceModel

#### Owner

`SystemModelingModule`

#### May Contain

- component instances
- port references
- user-authored connections
- component configuration references
- layout metadata
- user labels

#### Must Not Contain

- DAE equations
- ODE equations
- simulation arrays
- state-space matrices
- stability margins
- plot slot runtime data

### 7.2 SystemGraph

#### Owner

`SystemModelingModule`

#### May Contain

- resolved topology
- implicit nodes
- domain grouping
- port-to-node relationships
- graph validation results

#### Must Not Contain

- UI widget references
- solver-specific arrays
- stability data
- plot state

### 7.3 DAEArtifact

#### Owner

`SystemModelingModule`

#### May Contain

- differential equations
- algebraic constraints
- variable metadata
- parameter references
- equation trace records

#### Must Not Contain

- final simulation result arrays
- controller design outputs
- plot configuration

### 7.4 ODEArtifact

#### Owner

`SystemModelingModule`

#### May Contain

- state vector definition
- input mapping
- output mapping
- parameter mapping
- initial condition mapping
- `f(x, u, p, t)` representation
- `h(x, u, p, t)` representation
- linearity flag
- trace metadata

#### Must Not Contain

- `A`
- `B`
- `C`
- `D`
- transfer functions
- poles
- zeros
- eigenvalues
- margins
- Bode data
- Nyquist data

### 7.5 SimulationRequest

#### Owner

`shared/engine`

#### May Contain

- ODE artifact reference
- time span
- solver settings
- selected inputs
- initial condition values
- controller runtime references
- output channel selection

#### Must Not Contain

- UI widget references
- plot slot state
- stability margins
- transfer function objects

### 7.6 SimulationResultArtifact

#### Owner

`shared/engine`

#### May Contain

- metadata
- run ID
- source ODE artifact reference
- solver information
- channel registry
- HDF5 dataset references
- warnings/errors

#### Must Not Contain

- full numeric arrays in JSON
- mutable workspace state
- controller design internals
- plot layout state

### 7.7 StabilityAnalysisArtifact

#### Owner

`ControllerDesignModule`

#### May Contain

- operating point
- linearization metadata
- `A/B/C/D`
- transfer functions
- eigenvalues
- poles
- zeros
- Bode data
- Nyquist data
- stability margins
- warnings

#### Must Not Contain

- workspace UI state
- full time-domain simulation arrays
- editable component configuration
- runtime solver state

### 7.8 PlotSlotConfig

#### Owner

`ControllerDesignModule` (as part of `plot_layout`; see `03_configuration_requirements.md` §8 and `06_data_flow_and_architecture.md` §4.3, §6.2)

#### May Contain

- plot type
- slot ID
- `result_ref`
- `analysis_ref`
- `channel_selection` (with `kind`: `channels` | `io_pair` | `system_wide`)
- axis/display options
- title and labels
- metadata and extensions for forward compatibility

#### Must Not Contain

- full simulation arrays
- transfer function computation logic
- solver state
- duplicated stability data
- component parameter source of truth
- legacy untyped `signals[]` field

### 7.9 ProjectPackage

#### Owner

Project persistence layer

#### Required Structure

```text
project.systemdesign/
  project.json
  results/
  exports/
  recovery/
```

#### Storage Rule

`project.json` stores metadata and references.

Large numeric data belongs in:

```text
results/*.h5
```

---

## 8. ADR Compliance Per Stage

The AI agent must check applicable ADRs before code changes. The full ADR catalog and per-ADR verification rules are in `07_implementation_order.md` §16. This section maps each stage to its applicable ADRs.

The 20 canonical ADRs (per `06_data_flow_and_architecture.md` §19):

| ADR | Title |
|---|---|
| ADR-001 | Phase 1 Engine Isolation |
| ADR-002 | Hybrid ULID Identity Model |
| ADR-003 | Workspace UI/Data Separation |
| ADR-004 | Equation Builder Ownership |
| ADR-005 | Command Stack with QUndoStack |
| ADR-006 | Controller Owns Transfer-Function and State-Space Builders |
| ADR-007 | CasADi Backend |
| ADR-008 | Bond Graph Causality |
| ADR-009 | DAE Reduction Strategy |
| ADR-010 | Linearization Ownership |
| ADR-011 | Dimensional Analysis Policy |
| ADR-012 | Project Package Directory Format |
| ADR-013 | StabilityAnalysisArtifact |
| ADR-014 | Controller Runtime Wrapper in shared/engine |
| ADR-015 | Result Panel Unified With Grouped Dropdown |
| ADR-016 | channel_selection.kind Schema |
| ADR-017 | Mirror Sync Plot Dropdowns |
| ADR-018 | WorkspaceModel Signal Payload Contracts |
| ADR-019 | Batch Mutation Mode and WorkspaceChangeSet |
| ADR-020 | Dirty Tracking Semantics |

If ADR files do not exist yet, the agent must preserve the decisions below as de facto ADRs.

### 8.1 S0 ADR Compliance

S0 must comply with the following ADRs (full verification rules in `07_implementation_order.md` §16):

- ADR-001 Phase 1 Engine Isolation (§16.1)
- ADR-002 Hybrid ULID Identity Model (§16.2)
- ADR-003 Workspace UI/Data Separation (§16.3)
- ADR-004 Equation Builder Ownership (§16.4)
- ADR-005 Command Stack with QUndoStack (§16.5)
- ADR-006 Controller Owns Transfer-Function and State-Space Builders (§16.6)

Critical S0 rules from these ADRs:

- strict module ownership boundaries are visible in the folder skeleton
- `shared.engine` import is blocked by `ImportError` guard during Phase 1
- feature/application layering is enforced by static architecture tests
- artifact-driven architecture is the foundation, not legacy patterns

### 8.2 S1 ADR Compliance

S1 must comply with:

- ADR-002 Hybrid ULID Identity Model (§16.2)
- ADR-003 Workspace UI/Data Separation (§16.3)
- ADR-005 Command Stack with QUndoStack (§16.5)
- ADR-008 Bond Graph Causality (§16.8) — preparation fields only, no causality assignment yet
- ADR-018 WorkspaceModel Signal Payload Contracts (§16.18)
- ADR-019 Batch Mutation Mode and WorkspaceChangeSet (§16.19)
- ADR-020 Dirty Tracking Semantics (§16.20)

Critical S1 rules from these ADRs:

- stable internal IDs use ULID prefixes; display IDs and custom labels are never used as graph references
- `WorkspaceModel` is the source of truth; UI items render only
- all user edits go through `QUndoCommand`-based commands
- domain compatibility is enforced before connection mutation
- Bond Graph metadata fields are reserved in connection style/extensions but not interpreted
- ADR-018: `WorkspaceModel` signals carry exactly the payload types defined in §16.18; subscribers MUST NOT mutate the model from inside a slot
- ADR-019: batch mode (`with model.batch():`) emits `modelChanged` once on outermost exit; the 12 fine-grained signals are suppressed inside a batch (see §16.19)
- ADR-020: `dirtyChanged` emits on transitions only; no-op suppression uses ε=1e-6 tolerance for `QPointF`/`float` (see §16.20)

### 8.3 S2 ADR Compliance

S2 must comply with:

- ADR-002 Hybrid ULID Identity Model (§16.2) — I/O references use internal IDs
- ADR-011 Dimensional Analysis Policy (§16.11) — units preserved in parameter schema
- ADR-012 Project Package Directory Format (§16.12)
- ADR-016 channel_selection.kind Schema (§16.16)
- ADR-017 Mirror Sync Plot Dropdowns (§16.17)

Critical S2 rules from these ADRs:

- project saves as `.systemdesign/` directory bundle with `project.json` and subdirectories (`results/`, `exports/`, `recovery/`)
- legacy single-file JSON projects migrate automatically with unknown field preservation
- plot slot configuration uses `channel_selection.kind` schema (`channels`, `io_pair`, `system_wide`); legacy `signals[]` arrays are forbidden
- configuration plot dropdowns and per-plot header dropdowns share one canonical state
- parameter values preserve units explicitly; canonical internal unit defined per parameter schema

### 8.4 S3 ADR Compliance

S3 must comply with:

- ADR-004 Equation Builder Ownership (§16.4)
- ADR-008 Bond Graph Causality (§16.8) — causality assignment in DAE pipeline
- ADR-009 DAE Reduction Strategy (§16.9)
- ADR-010 Linearization Ownership (§16.10) — ODE artifact stays free of A/B/C/D
- ADR-011 Dimensional Analysis Policy (§16.11) — dimensional metadata in equation extraction

Critical S3 rules from these ADRs:

- equation extraction belongs to `SystemModelingModule`; `ControllerDesignModule` does not generate DAE
- DAE pipeline performs classification, causality preparation, algebraic elimination, and index reduction
- `ODEArtifact` contains `x_dot=f(x,u)` and `y=h(x,u)` only; final `A/B/C/D` are forbidden
- state identity is semantic: `(component_id, state_id)`, never index-only
- nonlinear systems mark the linearity flag; silent linearization is forbidden

### 8.5 S4 ADR Compliance

S4 must comply with:

- ADR-001 Phase 1 Engine Isolation (§16.1) — gate is removed only at S4 entry
- ADR-007 CasADi Backend (§16.7)
- ADR-012 Project Package Directory Format (§16.12) — HDF5 results stored under `results/`

Critical S4 rules from these ADRs:

- CasADi is the primary solver backend; SciPy is internal fallback only
- backend selection is logged and explicit
- `SimulationResultArtifact` is immutable after creation
- full numeric arrays live in HDF5; `project.json` stores only references and channel metadata
- engine has no UI dependency; result callbacks reach UI via queued Qt signals

### 8.6 S5 ADR Compliance

S5 must comply with:

- ADR-006 Controller Owns Transfer-Function and State-Space Builders (§16.6)
- ADR-010 Linearization Ownership (§16.10)
- ADR-013 StabilityAnalysisArtifact (§16.13)

Critical S5 rules from these ADRs:

- linearization workflow belongs to `ControllerDesignModule`; ODE artifact must not be modified to store final matrices
- transfer-function and state-space builders belong to `ControllerDesignModule`
- `StabilityAnalysisArtifact` owns `A/B/C/D`, eigenvalues, poles, zeros, frequency response, and stability margins
- nonlinear systems are linearized only through explicit workflow with structured failure reporting
- operating point sources (`zero`, `component_initial_conditions`, `user_specified`, `last_simulation_initial`, `last_simulation_final`, `auto_equilibrium`) are explicitly supported or disabled with diagnostics

### 8.7 S6 ADR Compliance

S6 must comply with:

- ADR-013 StabilityAnalysisArtifact (§16.13) — consumed by frequency/algebraic plots
- ADR-015 Result Panel Unified With Grouped Dropdown (§16.15)
- ADR-016 channel_selection.kind Schema (§16.16)
- ADR-017 Mirror Sync Plot Dropdowns (§16.17)

Critical S6 rules from these ADRs:

- one unified result panel renders both `SimulationResultArtifact` and `StabilityAnalysisArtifact`
- no separate stability panel exists
- four plot slots; plot type dropdowns are grouped (Time-domain, Frequency-domain, Algebraic, Unknown)
- plot type remains selectable independent of artifact availability
- step response may consume `result_ref` (preferred) or fall back to `analysis_ref`
- plot renderer dispatches by `channel_selection.kind`; legacy untyped signal arrays are forbidden
- mirror sync between Configuration and per-plot header dropdowns is preserved

### 8.8 S7 ADR Compliance

S7 must comply with:

- ADR-006 Controller Owns Transfer-Function and State-Space Builders (§16.6) — design stays in ControllerDesignModule
- ADR-014 Controller Runtime Wrapper in shared/engine (§16.14)

Critical S7 rules from these ADRs:

- runtime controllers live under `shared/engine/controllers/`
- design settings remain in `ControllerDesignModule` and are read but not mutated by runtime
- closed-loop execution occurs in `shared/engine`
- controller runtime errors abort gracefully with structured diagnostics

---

## 9. Schema Change Protocol

Schema changes are high-risk.

The AI agent must not change schemas casually.

### 9.1 Before Changing a Schema

The agent must identify:

1. schema name
2. owning module
3. producer stage
4. consumer stages
5. whether the change is backward compatible
6. whether migration is required
7. which tests must change
8. whether documentation must change

### 9.2 Schema Change Classes

| Class | Description | Requirement |
|---|---|---|
| additive optional | new optional field | tests + docs |
| additive required | new required field | migration + tests + docs |
| rename | field name changes | migration + compatibility strategy |
| removal | field removed | migration + explicit approval |
| semantic change | same field means different thing | explicit approval + tests + docs |

### 9.3 Forbidden Schema Changes

The agent must not:

- add fields to avoid fixing architecture
- add duplicate fields with similar meaning
- add UI-only fields into model schemas
- add state-space fields into ODE schemas
- add raw numeric arrays into JSON schemas
- rename fields without migration notes
- remove fields without checking existing project compatibility

### 9.4 Required Schema Change Report

Every schema change must include:

```text
Schema changed:
Owner:
Change type:
Backward compatible: yes/no
Migration needed: yes/no
Tests updated:
Docs updated:
Risk:
```

---

## 10. Verification Protocol

The AI agent must verify changes before declaring work complete.

### 10.1 Minimum Verification Steps

For every code change:

1. run relevant unit tests if available
2. run import/smoke tests for changed modules
3. check forbidden import boundaries
4. check artifact schemas for forbidden fields
5. check serialization/deserialization if schema changed
6. report skipped tests honestly

### 10.2 Stage-Specific Verification

| Stage | Required Verification |
|---|---|
| S0 | package imports, folder boundaries, guards |
| S1 | graph construction, validation, ID stability |
| S2 | parameter validation, unit metadata, initial conditions |
| S3 | DAE/ODE correctness, no A/B/C/D in ODE |
| S4 | solver execution, result artifact, HDF5 storage |
| S5 | linearization, eigenvalues, TF, margins |
| S6 | plot artifact binding, no duplicated plot state |
| S7 | runtime controller output, closed-loop simulation |

### 10.3 Verification Failure Rule

If verification fails, the agent must not claim success.

The agent must report:

- what failed
- likely cause
- files affected
- whether architecture is still intact
- next recommended fix

---

## 11. Stop Conditions and Escalation Rules

The AI agent must stop and ask for clarification when a decision would affect architecture or irreversible contracts.

### 11.1 Mandatory Stop Conditions

Stop if:

1. ownership is unclear
2. two requirement documents conflict
3. a schema requires a breaking change
4. migration strategy is unclear
5. a stage boundary would be crossed
6. a feature requires fake data to appear functional
7. a solver limitation requires changing the artifact contract
8. UI behavior requires storing model truth in widgets
9. stability logic seems needed inside ODE generation
10. result data storage would exceed JSON metadata scope

### 11.2 Safe Default Rule

If the agent must choose without clarification, it must choose the path that:

1. preserves ownership separation
2. avoids schema changes
3. avoids fake behavior
4. avoids duplicated state
5. keeps later-stage functionality behind explicit interfaces

### 11.3 Escalation Format

When stopping, the agent must report:

```text
Blocked decision:
Affected stage:
Affected module:
Conflict or uncertainty:
Options:
Recommended option:
Reason:
```

---

## 12. Conflict Resolution

### 12.1 Minor Conflict

A minor conflict affects naming, comments, folder placement, or non-contract implementation details.

The agent may choose the option that best preserves current architecture and report the choice.

### 12.2 Major Conflict

A major conflict affects:

- artifact ownership
- schema structure
- stage order
- data persistence
- solver contract
- UI/model separation
- controller design/runtime separation

The agent must stop and ask for clarification.

### 12.3 Code vs Document Conflict

If code conflicts with documents, documents win unless the user explicitly says the code reflects a newer decision.

The agent may create compatibility wrappers, but must not silently continue the legacy direction.

---

## 13. Output and Commit Conventions

### 13.1 Required Agent Response Format

When proposing or applying code changes, the AI agent must report:

```text
Stage:
Module:
Files changed:
Artifact affected:
Schema changed: yes/no
Boundary risk:
Tests added/updated:
Tests run:
Open issues:
```

### 13.2 Commit Message Format

Recommended commit format:

```text
S<stage>: <short imperative summary>

- <change 1>
- <change 2>
- <change 3>

Artifacts:
- <artifact names>

Tests:
- <test names>

Boundary checks:
- <ownership/boundary notes>
```

Example:

```text
S3: Add ODE artifact contract tests

- Add ODEArtifact schema guard
- Add test ensuring A/B/C/D are rejected
- Add semantic state reference checks

Artifacts:
- ODEArtifact

Tests:
- test_ode_artifact_contract.py

Boundary checks:
- No ControllerDesignModule dependency introduced
- No state-space fields added to ODEArtifact
```

### 13.3 File Naming Convention

Requirement documents use numeric prefixes:

```text
01_library_requirements.md
02_workspace_requirements.md
03_configuration_requirements.md
04_model_equations_requirements.md
05_simulation_and_results_requirements.md
06_data_flow_and_architecture.md
07_implementation_order.md
08_codex_execution_rules.md
```

New requirement documents must follow the same style unless explicitly approved.

---

## 14. Stage Completion Reporting

At the end of each stage, the AI agent must produce a completion report.

### 14.1 Required Report Format

```text
Stage completed:
Implemented scope:
Files changed:
Artifacts added/changed:
Schemas added/changed:
Tests added:
Tests run:
Forbidden checks passed:
Known limitations:
Next stage readiness:
```

### 14.2 Forbidden Checks

Each stage completion report must explicitly confirm:

- no UI source-of-truth violation
- no forbidden artifact fields added
- no legacy schema reintroduced
- no full numeric arrays stored in JSON
- no stage jumping hidden in placeholders
- no fake data used to pass UI/plot tests

---

## 15. Failure Modes and Recovery

### 15.1 Failed Tests

If tests fail, the agent must:

1. keep architecture intact
2. identify whether failure is implementation or contract mismatch
3. avoid deleting tests to make the suite pass
4. fix the root cause or ask for clarification

### 15.2 Broken Schema

If a schema change breaks serialization, the agent must:

1. stop further feature work
2. create or update migration logic
3. add regression tests
4. document the change

### 15.3 Broken Artifact Flow

If artifact references break, the agent must not replace references with copied data.

Instead, it must fix:

- artifact ID generation
- artifact registry
- reference resolution
- persistence mapping

### 15.4 Solver Failure

If simulation fails, the agent must return structured failure information.

It must not:

- return fake successful results
- generate empty arrays as success
- suppress solver diagnostics
- mutate the model to make the solver pass

### 15.5 Plot Failure

If a plot cannot resolve its artifact references, the agent must show/report a missing artifact or invalid binding error.

It must not:

- compute hidden data inside the plot widget
- show fake fallback curves
- silently switch plot type

---

## 16. Reference Index

### 16.1 Ownership Quick Lookup

| Question | Correct Owner |
|---|---|
| Who owns workspace graph? | SystemModelingModule |
| Who owns DAE? | SystemModelingModule |
| Who owns ODE artifact? | SystemModelingModule |
| Who owns A/B/C/D? | ControllerDesignModule |
| Who owns transfer functions? | ControllerDesignModule |
| Who owns simulation runtime? | shared/engine |
| Who owns runtime controllers? | shared/engine/controllers |
| Who owns UI rendering? | UI |
| Who owns full result arrays? | HDF5 result storage |
| Who owns plot slot config? | Plot/result configuration layer |

### 16.2 Artifact Quick Lookup

| Artifact | Producer | Consumer |
|---|---|---|
| WorkspaceModel | Workspace | Graph builder, persistence |
| SystemGraph | Workspace/SystemModeling | EquationBuilder |
| DAEArtifact | EquationBuilder | ODE builder |
| ODEArtifact | SystemModelingModule | Simulation, ControllerDesignModule |
| SimulationRequest | Simulation orchestration | shared/engine |
| SimulationResultArtifact | shared/engine | Plot/result panel |
| StabilityAnalysisArtifact | ControllerDesignModule | Plot/result panel |
| PlotSlotConfig | Plot configuration | Result panel |
| ProjectPackage | Persistence layer | App loading/export/recovery |

### 16.3 Storage Quick Lookup

| Data Type | Storage |
|---|---|
| project metadata | JSON |
| schema version | JSON |
| artifact references | JSON |
| component configuration | JSON |
| plot slot config | JSON |
| time-series arrays | HDF5 |
| large numeric simulation data | HDF5 |
| exports | `exports/` |
| recovery snapshots | `recovery/` |

### 16.4 Plot Binding Quick Lookup

| Plot Type | Group | Reference | `channel_selection.kind` |
|---|---|---|---|
| time response | Time-domain | `result_ref` | `channels` |
| state variables | Time-domain | `result_ref` | `channels` |
| input/output signal | Time-domain | `result_ref` | `channels` |
| force | Time-domain | `result_ref` | `channels` |
| road profile | Time-domain | `result_ref` | `channels` |
| Bode | Frequency-domain | `analysis_ref` | `io_pair` |
| Nyquist | Frequency-domain | `analysis_ref` | `io_pair` |
| pole-zero | Algebraic | `analysis_ref` | `system_wide` |
| root locus | Algebraic | `analysis_ref` | `io_pair` |
| eigenvalue | Algebraic | `analysis_ref` | `system_wide` |
| step response | Hybrid | `result_ref` first, fallback `analysis_ref` | `io_pair` |

#### Step Response Special Behavior

Step response is the only plot type allowed to consume both artifact types.

Resolution priority:

1. If `result_ref` is present and points to a valid `SimulationResultArtifact`, use it.
2. Otherwise, if `analysis_ref` is present and points to a valid `StabilityAnalysisArtifact`, use it.
3. If neither is present, the slot must show a placeholder with a clear action button (e.g., "Run Simulation" or "Linearize and Analyze"); fake data must never be substituted.

(See `05_simulation_and_results_requirements.md` §15.2 and §15.12 for full behavior.)

#### Missing Artifact Behavior

For all plot types, if the required artifact reference is missing or stale:

- the plot type dropdown must remain selectable
- the slot must display a structured diagnostic (e.g., "Simulation result missing", "Stability analysis required")
- fake fallback curves are forbidden (see `15.5 Plot Failure`)
- automatic plot-type switching is forbidden (see `15.5 Plot Failure`)

---

## 17. Final Execution Contract

The AI agent must implement the Engineering System Designer as a model-first, artifact-driven system with strict module ownership.

The agent must preserve these five critical decisions at all times:

1. ODE is not state-space.
2. Stability analysis is a separate artifact owned by ControllerDesignModule.
3. There is one unified result panel.
4. JSON stores metadata; HDF5 stores full numeric result data.
5. Controller design and controller runtime are separate layers.

When in doubt:

```text
Do not guess.
Do not bypass architecture.
Do not add hidden state.
Do not move ownership.
Do not fake data.
Do not silently change schemas.
Ask or create an ADR.
```

This document is binding for all AI-assisted implementation work.
