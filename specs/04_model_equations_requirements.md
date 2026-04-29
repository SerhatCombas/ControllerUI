# 04_model_equations_requirements.md

## 1. Purpose

This document defines how a validated `SystemGraph` is transformed into a mathematical model representation for the Engineering System Designer application.

The model equation layer must derive a structured Ordinary Differential Equation artifact from the workspace graph.

The system must support:

- component equation definitions
- domain-level across/through semantics
- implicit node equations
- cross-domain coupling metadata
- structured symbolic equation extraction
- DAE construction
- DAE reduction where possible
- ODE artifact generation
- state vector definition
- input and output mapping
- validation diagnostics
- last valid model snapshot handling
- in-memory caching

This document defines model equation extraction only.

It does not define controller design, transfer-function generation, state-space matrix ownership, numerical simulation, plotting, or solver execution.

---

## 2. Scope

### 2.1 In Scope

Phase 2 model equation extraction includes:

- consuming a validated read-only `SystemGraph`
- converting component definitions into concrete symbolic equations
- generating implicit node equations
- applying reference conditions
- constructing a structured DAE representation
- reducing the DAE to an explicit ODE where possible
- producing an ODE artifact
- defining deterministic state, input, and output ordering
- detecting equation-level validation problems
- maintaining a last valid model snapshot
- exposing derived model artifacts through read-only APIs

### 2.2 Out of Scope

The following are out of scope for this document:

- transfer-function generation
- state-space matrix ownership and controller-analysis workflows
- controller execution
- numerical integration
- solver backend implementation
- simulation result generation
- simulation result storage such as HDF5, which belongs to `05_simulation_and_results_requirements.md`
- live plotting
- real-time animation
- controller tuning algorithms
- model export to external solver formats

---

## 3. Phase Boundary and Ownership

Responsibilities are strictly separated.

| Layer | Responsibility |
| --- | --- |
| `SystemModelingModule` | equation extraction and ODE artifact generation |
| `ControllerDesignModule` | transfer-function and state-space preparation and usage |
| `shared/engine` | numerical simulation and solver execution |

### 3.1 Critical Rule

`04_model_equations_requirements.md` stops at the ODE artifact.

It must not own transfer-function generation or final state-space matrices.

### 3.2 State-Space Ownership Decision

The project uses the following decision:

- `SystemModelingModule` produces an ODE artifact.
- `ControllerDesignModule` consumes the ODE artifact.
- `ControllerDesignModule` generates state-space matrices `A`, `B`, `C`, and `D` when needed.
- Linearization belongs to `ControllerDesignModule` as a control-analysis preparation step.

This preserves the architectural boundary defined in the application architecture.

### 3.3 Symbolic Backend Decision

The project uses CasADi as the primary symbolic and automatic differentiation backend for Phase 2+ equation processing.

Reasoning:

- CasADi supports symbolic expressions suitable for control-oriented workflows.
- CasADi provides automatic differentiation for Jacobian-based linearization.
- CasADi is better suited than plain string-based symbolic processing for future nonlinear and optimization workflows.
- CasADi can support future controller workflows such as MPC.

SymPy may be used only as an optional development or debugging helper, not as the primary model equation backend.

A separate architecture decision record should document this choice:

- `ADR-007-symbolic-backend-casadi.md`

---

## 4. Module Ownership

Equation extraction is owned by `SystemModelingModule`.

Expected internal components:

- `EquationBuilder`
- `EquationDefinitionResolver`
- `DomainEquationBuilder`
- `ImplicitNodeEquationBuilder`
- `ReferenceConditionBuilder`
- `DAEAssembler`
- `DAEReducer`
- `ODEArtifactBuilder`
- `ModelSnapshotStore`
- `EquationValidationService`

`SystemModelingModule` must expose only read-only model artifacts to other modules.

`ControllerDesignModule` may request the current ODE artifact, but it must not mutate the workspace graph, equation system, or model snapshot cache.

---

## 5. Input: SystemGraph

Equation extraction consumes a validated `SystemGraph` produced by the workspace pipeline.

Input pipeline:

`WorkspaceModel -> GraphAssembler -> GraphValidator -> SystemGraph -> EquationBuilder`

### 5.1 Required SystemGraph State

`EquationBuilder` consumes a frozen, read-only snapshot of `SystemGraph`.

Preconditions:

- all component instances have valid component definitions
- all component definitions contain valid port definitions
- all required parameters have values
- all parameter values pass type validation
- all connections reference existing components and ports
- all implicit nodes are domain-consistent
- no implicit node contains mixed physical domains
- required domain references exist where needed
- graph validation contains no `error` severity issues
- stale I/O references have already been reported by project-level validation

If these preconditions are not met, equation extraction must be skipped.

When extraction is skipped, the last valid model snapshot must remain unchanged.

### 5.2 Snapshot Immutability

`EquationBuilder` must never mutate `SystemGraph`.

The graph must be provided through one of the following mechanisms:

- read-only adapter
- immutable dataclass structure
- deep-copy snapshot
- frozen graph object

### 5.3 SystemGraph Read API

The graph snapshot must expose enough information for equation extraction.

Recommended read API:

- `get_components() -> list[ComponentInstance]`
- `get_component(component_id) -> ComponentInstance | None`
- `get_component_definition(definition_id) -> ComponentDefinition | None`
- `get_connections() -> list[Connection]`
- `get_implicit_nodes() -> list[ImplicitNode]`
- `get_ports_for_node(node_id) -> list[PortRef]`
- `get_domain_metadata(domain_id) -> DomainDefinition`
- `get_validation_report() -> ValidationReport`
- `get_structural_hash() -> str`

### 5.4 Extraction Readiness

Equation extraction is allowed only when:

- workspace graph validation has no blocking errors
- component registry validation has no blocking errors
- domain registry validation has no blocking errors
- parameter schema validation has no blocking errors

Warnings may allow equation extraction to continue if the affected feature is non-critical.

Examples:

- unsupported future metadata field: warning, extraction may continue
- stale output selection: warning, output excluded from mapping
- missing ground/reference in a connected electrical subgraph: error, extraction blocked
- missing component definition: error, extraction blocked

---

## 6. Core Output: ODE Artifact

This module produces an ODE artifact, not a state-space artifact.

### 6.1 ODE Artifact Purpose

The ODE artifact is the hand-off format from `SystemModelingModule` to `ControllerDesignModule`.

It represents the mathematical model derived from the workspace graph.

### 6.2 ODE Artifact Schema

Recommended schema:

```json
{
  "id": "ode_01HV7NE2K8M4Q1W5E7R9T3Y6X9",
  "schema_version": "0.1.0",
  "source_workspace_hash": "sha256:...",
  "linearity": "linear",
  "time_dependency": "time_invariant",
  "dae_form": {
    "residual_equations": []
  },
  "ode_form": {
    "kind": "explicit",
    "state_derivatives": []
  },
  "state_vector": [],
  "input_vector": [],
  "output_vector": [],
  "input_mapping": [],
  "output_mapping": [],
  "parameters": [],
  "validation_report": {},
  "metadata": {},
  "extensions": {}
}
```

### 6.3 ODE Artifact Rules

The ODE artifact must:

- be read-only after creation
- include a source workspace hash
- include a registry version or registry hash
- include deterministic state ordering
- include deterministic input ordering
- include deterministic output ordering
- preserve traceability from symbols back to components, ports, nodes, and I/O entries
- include validation diagnostics
- exclude final state-space matrices

### 6.4 What the ODE Artifact Does Not Contain

The ODE artifact must not contain final controller-owned artifacts:

- `A` matrix
- `B` matrix
- `C` matrix
- `D` matrix
- transfer functions
- controller gains
- simulation traces
- solver results

### 6.5 Optional Linearity Metadata

For systems detected as linear, the ODE artifact may include optional linearity metadata.

Allowed metadata:

- `linearity_proof`: description of the test or symbolic check that confirmed linearity
- `detected_linear_form`: one of `x_dot = A*x + B*u`, `x_dot = A*x + B*u + b`, or `unknown`
- symbolic Jacobian expressions in metadata, but not materialized final matrices
- recommended operating point metadata, such as zero state for naturally linear systems

This metadata is advisory.

`ControllerDesignModule` may use it to skip redundant checks, but it remains responsible for materializing final `A`, `B`, `C`, and `D` matrices.

The ODE artifact must not store controller-owned final matrices.

### 6.6 Time Dependency Classification

Allowed `time_dependency` values:

- `time_invariant`: `f` and `h` do not explicitly depend on time `t`
- `time_variant`: `f` or `h` explicitly depend on time `t`, for example through a time-varying source
- `unknown`: time dependency could not be safely determined

This classification is independent of linearity.

Combined classifications:

- `linear` + `time_invariant`: LTI model candidate
- `linear` + `time_variant`: LTV model candidate
- `nonlinear` + `time_invariant`: nonlinear time-invariant model
- `nonlinear` + `time_variant`: most general case

`ControllerDesignModule` must check both `linearity` and `time_dependency` before enabling transfer-function, Bode, root-locus, or LQR workflows.

---

## 7. Equation Builder

### 7.1 Responsibility

`EquationBuilder` transforms `SystemGraph` into a structured symbolic equation system.

It must combine:

- component constitutive equations
- component internal state equations
- implicit node equations
- reference conditions
- boundary and input equations
- output mapping expressions

### 7.2 Equation Builder Input

Inputs:

- read-only `SystemGraph`
- `ComponentRegistry`
- `DomainRegistry`
- `ParameterSchemaRegistry`
- controller I/O selection snapshot
- symbolic backend adapter

### 7.3 Equation Builder Output

Output:

- `SymbolicSystem`

Recommended structure:

```json
{
  "id": "sym_01HV7NE2K8M4Q1W5E7R9T3Y6X9",
  "all_equations": [],
  "differential_equations": [],
  "algebraic_constraints": [],
  "node_constraints": [],
  "reference_conditions": [],
  "state_variables": [],
  "algebraic_variables": [],
  "input_variables": [],
  "output_variables": [],
  "parameters": [],
  "validation_report": {},
  "metadata": {},
  "extensions": {}
}
```

### 7.4 StructuredEquation Schema

Each equation must be represented as a structured object, not a raw string.

Recommended schema:

```json
{
  "id": "eq_01HV7NE2K8M4Q1W5E7R9T3Y6X9",
  "kind": "differential",
  "lhs": "der(x_cmp_01HV_position)",
  "rhs": "v_cmp_01HV_velocity",
  "expression": "der(x_cmp_01HV_position) - v_cmp_01HV_velocity = 0",
  "variables_used": [
    "x_cmp_01HV_position",
    "v_cmp_01HV_velocity"
  ],
  "parameters_used": [],
  "source": {
    "kind": "component_equation",
    "component_id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
    "equation_template_id": "position_derivative"
  },
  "domain": "mechanical_translational",
  "unit_check": {
    "status": "valid",
    "lhs_unit": "m/s",
    "rhs_unit": "m/s"
  },
  "metadata": {},
  "extensions": {}
}
```

### 7.5 Equation Kinds

Allowed `kind` values:

- `constitutive`
- `differential`
- `algebraic`
- `node_across_constraint`
- `node_through_constraint`
- `reference_condition`
- `boundary_condition`
- `input_binding`
- `output_expression`

### 7.6 Equation Source Kinds

Allowed `source.kind` values:

- `component_equation`
- `component_internal_state`
- `implicit_node_across`
- `implicit_node_through`
- `reference_condition`
- `boundary_condition`
- `io_input_mapping`
- `io_output_mapping`

### 7.7 Symbol Names

Concrete symbol names must be deterministic and machine-safe.

Recommended naming:

- component state: `x_<component_id>_<state_id>`
- component derivative: `dx_<component_id>_<state_id>`
- port across: `e_<component_id>_<port_id>`
- port through: `f_<component_id>_<port_id>`
- node across: `e_<node_id>`
- parameter: `p_<component_id>_<parameter_id>`
- input: `u_<input_index>`
- output: `y_<output_index>`

Human-readable labels may be stored separately in metadata.

---

## 8. Domain Semantics

### 8.1 Across and Through Variables

Each physical domain defines two conjugate variables.

| Domain | Across / Effort | Through / Flow | Power Expression |
| --- | --- | --- | --- |
| `electrical_analog` | voltage `V` | current `A` | voltage times current |
| `mechanical_translational` | velocity `m/s` | force `N` | force times velocity |
| `mechanical_rotational` | angular velocity `rad/s` | torque `N*m` | torque times angular velocity |
| `hydraulic` | pressure `Pa` | volume flow `m^3/s` | pressure times flow |
| `thermal` | temperature `K` | entropy flow `W/K` | temperature times entropy flow |

In Bond Graph terminology:

- across corresponds to effort
- through corresponds to flow

### 8.2 Node Constraints

For every implicit node:

- all across variables in that node are equal
- all through variables in that node sum to zero

These constraints generalize Kirchhoff-style conservation laws across physical domains.

### 8.3 Reference Conditions

Each connected subgraph in a conservative physical domain requires a reference component.

| Domain | Reference Component |
| --- | --- |
| `electrical_analog` | `Ground Electric` |
| `mechanical_translational` | `Fixed` |
| `mechanical_rotational` | `Fixed Rotation` |

Reference components fix the relevant across variable to zero.

Without a reference, the system has a constant offset ambiguity and may become algebraically singular.

### 8.4 Cross-Domain Components

Cross-domain components must not create mixed-domain implicit nodes.

Instead, they expose separate ports for each domain and define coupling equations internally.

Examples:

- electric motor
- actuator
- sensor transducer
- gear pair
- ideal transformer
- gyrator

### 8.5 Cross-Domain Coupling Types

Supported coupling metadata types:

- `TF` for transformer
- `GY` for gyrator
- `MTF` for modulated transformer
- `MGY` for modulated gyrator

### 8.6 Transformer Coupling

A transformer maps effort and flow between two ports using a modulus.

Conceptual form:

- secondary effort depends on primary effort and modulus
- primary flow depends on secondary flow and modulus

Examples:

- ideal electrical transformer
- mechanical lever
- gear pair

### 8.7 Gyrator Coupling

A gyrator maps effort to flow and flow to effort using a modulus.

Examples:

- DC motor coupling electrical and rotational domains
- electromechanical transducer

### 8.8 Coupling Metadata Schema

Recommended metadata for cross-domain components:

```json
{
  "coupling": {
    "kind": "GY",
    "ports": ["electrical", "mechanical"],
    "modulus": {
      "parameter_id": "motor_constant",
      "unit": "N*m/A"
    },
    "metadata": {},
    "extensions": {}
  }
}
```

### 8.9 Causality Preparation

Bond Graph causality indicates which variable a component computes and which variable it receives.

Phase 1 stores causality metadata fields where needed.

Phase 2 may assign causality during equation extraction.

Causality assignment is used to:

- identify state variables
- reduce DAE index
- detect algebraic loops
- choose computable equation direction
- identify over-constrained or under-constrained systems

A separate ADR should define detailed causality rules:

- `ADR-008-bond-graph-causality.md`

---

## 9. Component Equation Definitions

### 9.1 Purpose

Component definitions must include equation templates.

Equation templates define the physics of a component independently from any specific instance.

Component instances provide concrete parameters, IDs, labels, and graph placement.

### 9.2 EquationDefinition Schema

Recommended schema:

```json
{
  "id": "ohms_law",
  "kind": "constitutive",
  "expression": "{port.p.across} - {port.n.across} = {parameter.R} * {port.p.through}",
  "variables_introduced": [],
  "parameters_used": ["R"],
  "ports_used": ["p", "n"],
  "domain": "electrical_analog",
  "unit_rule": {
    "lhs": "V",
    "rhs": "V"
  },
  "metadata": {},
  "extensions": {}
}
```

### 9.3 Variable Reference Syntax

Equation templates use placeholder references.

Allowed placeholders:

- `{port.<port_id>.across}`
- `{port.<port_id>.through}`
- `{parameter.<parameter_id>}`
- `{state.<state_id>}`
- `{state.<state_id>.derivative}`
- `{input.<input_id>}`
- `{time}`

Examples:

- `{port.p.across}`
- `{port.n.through}`
- `{parameter.R}`
- `{state.position}`
- `{state.velocity.derivative}`

### 9.4 Placeholder Resolution

`EquationBuilder` resolves placeholders into concrete symbols.

Example:

- template: `{port.p.across}`
- component: `cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0`
- resolved symbol: `e_cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0_p`

### 9.5 Internal State Schema

Components may define internal states.

Recommended schema:

```json
{
  "id": "position",
  "display_name": "Position",
  "symbol": "x",
  "kind": "position",
  "unit": "m",
  "initial_value_parameter": "x0",
  "metadata": {},
  "extensions": {}
}
```

Allowed `kind` values:

- `position`
- `velocity`
- `across_integral`
- `through_integral`
- `energy_storage`
- `custom`

### 9.6 Standard Electrical Components

#### Resistor

Component equations:

- voltage difference equals resistance times current
- port currents balance to zero

Required parameters:

- `R`

Required ports:

- `p`
- `n`

#### Capacitor

Component equations:

- current equals capacitance times voltage derivative
- port currents balance to zero

Required parameters:

- `C`
- optional `v0`

Internal state:

- capacitor voltage or charge

#### Inductor

Component equations:

- voltage equals inductance times current derivative
- port currents balance to zero

Required parameters:

- `L`
- optional `i0`

Internal state:

- inductor current or flux

#### Voltage Source

Component equations:

- port voltage difference equals source value

Required parameters:

- source value or input binding

#### Current Source

Component equations:

- through variable equals source value

Required parameters:

- source value or input binding

#### Ground Electric

Reference condition:

- electrical potential equals zero

### 9.7 Standard Mechanical Translational Components

#### Mass

Component equations:

- position derivative equals velocity
- velocity derivative equals net force divided by mass

Required parameters:

- `m`
- optional `x0`
- optional `v0`

Internal states:

- position
- velocity

#### Spring

Component equations:

- force equals stiffness times relative displacement
- port forces balance to zero

Required parameters:

- `k`
- optional `L0`

#### Damper

Component equations:

- force equals damping coefficient times relative velocity
- port forces balance to zero

Required parameters:

- `c`

#### Fixed

Reference condition:

- position equals zero
- velocity equals zero

### 9.8 Standard Source Components

Source components may introduce inputs into the ODE artifact.

Examples:

- step force
- voltage input
- road displacement input
- signal source

A source component must declare whether its value is:

- constant parameter
- time function
- external input
- expression

### 9.9 Equation Definition Validation

Component equation definitions must be validated during registry loading.

Validation checks:

- all referenced ports exist
- all referenced parameters exist
- all referenced states exist
- equation kind is supported
- units are compatible where declared
- placeholders are syntactically valid
- cross-domain coupling metadata is consistent with port domains

Registry validation failure must block application startup for built-in components.

---

## 10. Implicit Node Equations

### 10.1 Node Construction

Implicit nodes are derived from connections by `GraphAssembler`.

`EquationBuilder` consumes these nodes and produces node equations.

### 10.2 Equation Generation

For each implicit node containing `N` ports:

- generate `N - 1` across equations
- generate `1` through equation

Total generated equations per node:

- `N` equations

### 10.3 Across Equations

Across equations express that all port across variables are equal to the node across variable.

Conceptual form:

- port 1 across equals node across
- port 2 across equals node across
- port 3 across equals node across

### 10.4 Through Equation

Through equation expresses conservation of through variables.

Conceptual form:

- sum of all port through variables in the node equals zero

### 10.5 Node-Level Variables

Each implicit node introduces one node-level across variable.

Naming convention:

- generic: `e_<node_id>`
- electrical display label: `v_<node_id>`
- mechanical display label: `v_<node_id>` or domain-specific label

Through variables remain port-specific.

### 10.6 Reference Resolution

If a node is connected to a reference component, the node across variable is fixed to zero.

Examples:

- electrical ground fixes voltage to zero
- mechanical fixed component fixes position and velocity to zero where applicable

### 10.7 Floating Subgraphs

A connected conservative domain subgraph without reference produces a validation error.

Examples:

- electrical circuit with no ground
- mechanical translational chain with no fixed or absolute reference when absolute displacement is required

---

## 11. DAE Representation

### 11.1 Purpose

The initial equation system is represented as a DAE because component equations and node equations naturally contain both differential and algebraic constraints.

General residual form:

`F(x_dot, x, z, u, t, p) = 0`

Where:

- `x` = state variables
- `x_dot` = state derivatives
- `z` = algebraic variables
- `u` = inputs
- `t` = time
- `p` = parameters

### 11.2 DAE Artifact Schema

Recommended schema:

```json
{
  "kind": "dae_residual",
  "residual_equations": [],
  "state_variables": [],
  "state_derivatives": [],
  "algebraic_variables": [],
  "input_variables": [],
  "parameters": [],
  "time_symbol": "t",
  "metadata": {},
  "extensions": {}
}
```

### 11.3 Variable Classification

Variables must be classified as:

- state variable
- state derivative
- algebraic variable
- input variable
- output variable
- parameter
- time variable

### 11.4 DAE Validation

The DAE representation must be checked for:

- missing variables
- duplicate variables
- inconsistent equation dimensions
- underdetermined system
- overdetermined system
- singular reference conditions
- unresolved placeholders
- unsupported nonlinear expressions

---

## 12. DAE Reduction

### 12.1 Goal

DAE reduction attempts to convert the DAE residual form into an explicit ODE form.

Target form:

`x_dot = f(x, u, t, p)`

### 12.2 Primary Algorithm

Phase 2 uses Bond Graph causality assignment as the primary reduction strategy.

Causality assignment determines which variables are computed by which components and helps identify differential states and algebraic dependencies.

### 12.3 Fallback Algorithms

Fallback strategies may include:

- symbolic substitution
- graph-based dependency ordering
- Tarjan strongly connected component decomposition
- block lower triangular decomposition
- Pantelides-style index reduction for high-index DAE systems

### 12.4 Reduction Steps

Reduction process:

1. classify variables
2. assign causality where possible
3. build dependency graph
4. detect algebraic loops
5. solve algebraic constraints symbolically where possible
6. substitute algebraic variables into differential equations
7. isolate state derivatives
8. produce explicit ODE form if successful
9. produce implicit residual form if explicit reduction fails

### 12.5 Reduction Output Schema

Recommended schema:

```json
{
  "kind": "ode_reduction_result",
  "status": "explicit_ode",
  "state_derivatives": [],
  "remaining_algebraic_variables": [],
  "remaining_algebraic_constraints": [],
  "linearity": "linear",
  "diagnostics": [],
  "metadata": {},
  "extensions": {}
}
```

Allowed `status` values:

- `explicit_ode`
- `semi_explicit_dae`
- `implicit_dae`
- `failed`

### 12.6 Reduction Failure

If reduction fails:

- the failure must be reported with diagnostics
- the last valid model snapshot must not be overwritten
- `ControllerDesignModule` must receive an unavailable model status
- simulation must be blocked unless a compatible implicit solver is introduced in a later phase

### 12.7 Algebraic Loop Detection

An algebraic loop exists when algebraic variables depend on themselves without a state, delay, or external input breaking the dependency.

Detected loops must include trace information:

- involved equations
- involved variables
- involved components
- involved implicit nodes

### 12.8 High-Index DAE Handling

High-index DAE systems must not crash the application.

Minimum behavior:

- mark system as high-index or unreduced
- report diagnostic warning or error
- preserve partial equation system for inspection
- block controller and simulation workflows until resolved

---

## 13. State Vector Selection

### 13.1 State Variable Source

State variables come from component internal state declarations.

Examples:

- mass position
- mass velocity
- capacitor voltage
- capacitor charge
- inductor current
- inductor flux

### 13.2 Deterministic Ordering

State variables are ordered by:

1. component internal ID in lexicographic ULID order
2. state ID in alphabetical order within the component

This guarantees deterministic ordering across rebuilds and machines.

### 13.3 State Vector Stability Across Edits

State vector indices are not stable across structural edits.

Therefore, result data and mappings must not rely only on integer indices.

They must reference states using:

- `component_id`
- `state_id`
- canonical symbol name

### 13.4 State Variable Schema

Recommended schema:

```json
{
  "index": 0,
  "component_id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
  "component_display_id": "mass_1",
  "state_id": "position",
  "canonical_name": "mass_1.position",
  "symbol": "x_cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0_position",
  "quantity": "displacement",
  "unit": "m",
  "initial_value": {
    "source": "component_parameter",
    "parameter_id": "x0",
    "value": 0.0
  },
  "metadata": {},
  "extensions": {}
}
```

### 13.5 Initial Values

Initial values are derived from simulation settings and component parameters.

Default source:

- `component_parameters`

Future source:

- explicit override entries from simulation settings
- operating point solver result
- imported state snapshot

### 13.6 Missing Initial Values

If a state has no explicit initial value:

- use the default from its component definition if available
- otherwise use zero only if the component definition allows it
- otherwise emit a validation warning or error depending on component requirements

---

## 14. Input and Output Mapping

### 14.1 Input Vector

Inputs are derived from `io_selection.inputs`.

Only valid, non-stale input entries are included.

Input ordering follows the order stored in `io_selection.inputs`.

### 14.2 Input Mapping Rules

For each input entry:

- `source.component_id` identifies the component
- `source.port_id` identifies the port
- `source.variable` identifies across, through, or derived variable
- `quantity` defines the physical meaning
- `unit` defines the canonical unit

The mapped symbol becomes an input variable `u_i`.

### 14.3 Output Vector

Outputs are derived from `io_selection.outputs`.

Only valid, non-stale output entries are included.

Output ordering follows the order stored in `io_selection.outputs`.

### 14.4 Output Mapping Rules

For each output entry, the system must derive an output expression.

For explicit ODE systems:

`y = h(x, u, t, p)`

For linear systems, `ControllerDesignModule` may later convert `h` into `C` and `D` matrices.

### 14.5 Stale Reference Handling

If an I/O entry has `status = stale`:

- it is excluded from the input or output vector
- a warning is emitted
- raw entry data is preserved in project configuration
- controller and simulation workflows may be blocked if the missing entry is required

### 14.6 Input Mapping Schema

Recommended schema:

```json
{
  "input_index": 0,
  "io_selection_id": "ioin_01HV7NB3R8M5Y6X9Q2P1C7D4E0",
  "symbol": "u_0",
  "source_symbol": "e_cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0_p",
  "component_id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
  "port_id": "p",
  "variable": "across",
  "quantity": "voltage",
  "unit": "V",
  "metadata": {},
  "extensions": {}
}
```

### 14.7 Output Mapping Schema

Recommended schema:

```json
{
  "output_index": 0,
  "io_selection_id": "ioout_01HV7NC9M2J4K8Q1W5E7R9T3Y6",
  "symbol": "y_0",
  "expression": "x_cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0_position",
  "component_id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
  "port_id": "flange",
  "variable": "across",
  "quantity": "displacement",
  "unit": "m",
  "metadata": {},
  "extensions": {}
}
```

### 14.8 Input Sources: Component-Provided vs I/O Selection

The input vector `u` may receive entries from two sources.

#### Source Components With External Input Declaration

A source component may declare `value_kind = external_input` in its component definition.

Examples:

- input voltage source
- input force source
- controlled current source
- controlled torque source

Such a component automatically registers an input variable in the ODE artifact.

The user does not need to manually add the same source to `io_selection.inputs` for the source to exist mathematically.

#### Explicit I/O Selection Inputs

The user may also mark a port as an input through `io_selection.inputs` as defined in `03_configuration_requirements.md`.

Explicit I/O selection inputs may:

- expose a source component input with a user-defined name
- override display metadata for an automatically registered source input
- add an external boundary input for supported source kinds

#### Conflict Rule

If the same port is declared as input by both a source component and `io_selection.inputs`, the explicit I/O selection entry takes precedence for naming, ordering, and metadata.

The mathematical input symbol must not be duplicated.

#### Input Origin Metadata

Each input mapping must record its origin.

Allowed `origin` values:

- `source_component`
- `io_selection`
- `merged_source_component_and_io_selection`

Recommended metadata extension:

```json
{
  "origin": "merged_source_component_and_io_selection",
  "source_component_id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
  "io_selection_id": "ioin_01HV7NB3R8M5Y6X9Q2P1C7D4E0"
}
```

---

## 15. Linearity and Nonlinearity

### 15.1 Linearity Classification

The equation system must be classified as one of:

- `linear`
- `affine`
- `nonlinear`
- `unknown`

### 15.2 Linear ODE Form

A linear system can be represented conceptually as:

`x_dot = A*x + B*u`

However, this module does not own final `A` and `B` matrix generation.

It may expose the symbolic function `f(x, u, t, p)` and linearity metadata.

### 15.3 Nonlinear ODE Form

A nonlinear system is represented as:

`x_dot = f(x, u, t, p)`

Output form:

`y = h(x, u, t, p)`

### 15.4 Transfer Function Restriction

Nonlinear systems cannot directly produce transfer functions.

A transfer function may only be produced after linearization by `ControllerDesignModule`.

### 15.5 Linearization Boundary

Linearization is requested and owned by `ControllerDesignModule`.

`ControllerDesignModule` may request linearization around an operating point.

The symbolic ODE artifact must provide enough information for this process:

- state vector
- input vector
- output vector
- function `f`
- function `h`
- parameters
- units
- operating point metadata

### 15.6 Linearization Workflow

Conceptual workflow:

1. `ControllerDesignModule` receives an ODE artifact.
2. `ControllerDesignModule` selects or computes an operating point.
3. `ControllerDesignModule` computes Jacobians using CasADi.
4. `ControllerDesignModule` produces `A`, `B`, `C`, and `D`.
5. `ControllerDesignModule` uses those matrices for transfer functions and controller design.

### 15.7 Operating Point Sources

Possible operating point sources:

- user-provided state and input values
- equilibrium solve result
- previous simulation snapshot
- default component initial conditions

Operating point solving is not part of this document.

---

## 16. Validation and Diagnostics

### 16.1 Validation Levels

Validation severity levels:

- `info`
- `warning`
- `error`

### 16.2 Blocking Errors

The following must block successful ODE artifact generation:

- missing component definition
- missing required parameter
- invalid parameter type
- unresolved equation placeholder
- mixed-domain implicit node
- missing required domain reference
- overdetermined equation system
- underdetermined equation system
- unresolved high-index DAE
- failed DAE reduction when explicit ODE is required

### 16.3 Warnings

The following may allow extraction to continue:

- unsupported metadata preserved but unused
- stale optional output entry excluded
- unknown future equation extension preserved but unused
- unit metadata incomplete where not required
- nonlinear system detected when linear analysis was expected

### 16.4 Diagnostic Schema

Recommended schema:

```json
{
  "id": "diag_01HV7NE2K8M4Q1W5E7R9T3Y6X9",
  "severity": "error",
  "code": "missing_reference_component",
  "message": "Electrical subgraph has no Ground Electric reference component.",
  "source": {
    "kind": "implicit_node",
    "node_id": "node_3",
    "component_ids": ["cmp_01HV..."],
    "connection_ids": ["con_01HV..."]
  },
  "metadata": {},
  "extensions": {}
}
```

### 16.5 Dimensional Analysis

Phase 1 behavior:

- unit metadata is stored in component parameters and I/O entries
- no dimensional consistency validation runs during Phase 1
- unknown units are preserved during load and save

Phase 2 behavior:

- `EquationBuilder` performs dimensional consistency checks during equation extraction
- left-hand side and right-hand side dimensions must match
- parameter units must match equation requirements
- input and output mappings must preserve canonical units
- domain effort and flow variables must produce valid power dimensions

Phase 2 minimum checks:

- validate declared units for built-in components
- report unit mismatches as errors
- report missing optional unit metadata as warnings
- preserve unknown future unit metadata where safe

Phase 3 may add full symbolic unit conversion, such as converting `kΩ` to `Ω` before equation construction.

### 16.6 Traceability Requirement

Every diagnostic must be traceable to at least one of:

- component ID
- connection ID
- port reference
- implicit node ID
- equation ID
- I/O selection ID
- parameter ID

---

## 17. Last Valid Model Snapshot

### 17.1 Ownership

The last valid model snapshot is owned by `SystemModelingModule`.

It is maintained by `ModelSnapshotStore`.

### 17.2 Update Policy

A snapshot is captured when:

- equation extraction completes without errors
- DAE reduction status is `explicit_ode`
- ODE artifact validation succeeds
- state, input, and output mappings are internally consistent

A successful new snapshot replaces the previous snapshot.

Only the most recent valid snapshot is kept in memory.

### 17.3 Failed Extraction Policy

If extraction fails:

- do not overwrite the previous snapshot
- preserve diagnostics from the failed attempt
- report that the current workspace has no valid current ODE artifact
- allow access to the previous snapshot only if fallback is enabled

### 17.4 Persistence

The last valid model snapshot is not persisted to the project file.

Reason:

- it is a derived artifact
- it may become stale across sessions
- it must be rebuilt from the workspace graph on project load

### 17.5 Snapshot Access API

Recommended API:

- `get_current_ode_artifact() -> ODEArtifact | None`
- `get_last_valid_model_snapshot() -> ModelSnapshot | None`
- `get_last_extraction_diagnostics() -> ValidationReport`

These APIs must return read-only objects.

### 17.6 Snapshot Schema

Recommended schema:

```json
{
  "id": "snapshot_01HV7NE2K8M4Q1W5E7R9T3Y6X9",
  "captured_at": "2026-04-28T12:00:00Z",
  "captured_from_workspace_hash": "sha256:...",
  "component_registry_hash": "sha256:...",
  "ode_artifact": {},
  "validation_report": {},
  "metadata": {},
  "extensions": {}
}
```

### 17.7 Workspace Divergence

If the current workspace hash differs from the snapshot hash:

- UI must mark the snapshot as stale relative to current workspace
- fallback may still use the snapshot if explicitly enabled
- the user must be informed that results are based on the last valid model, not the current invalid workspace

### 17.8 Workspace Hash Computation

The workspace hash is a SHA-256 hash of a canonical JSON representation.

Included fields:

- all component instances
- component `id`
- component `definition_id`
- component parameter values
- component internal state initial value parameters
- all connections
- connection source component and port references
- connection target component and port references
- valid I/O selection entries used by equation extraction
- domain registry version or hash
- component registry version or hash
- equation definition registry version or hash

Excluded fields:

- view state such as zoom, pan, and viewport center
- selection state
- hover state
- timestamps such as `created_at` and `modified_at`
- validation reports
- derived artifacts
- equation snapshots
- simulation results

Two workspaces with identical equation-relevant structure but different timestamps must produce the same hash.

The canonical JSON representation must sort object keys and deterministic lists where ordering is not semantically meaningful.

---

## 18. Persistence and Caching Rules

### 18.1 Project Persistence

The following must not be persisted in `.systemdesign` files:

- equations
- symbolic expressions
- DAE artifacts
- ODE artifacts
- model snapshots
- state-space matrices
- transfer functions
- simulation traces

Reason:

- these are derived artifacts
- they must be rebuilt from the project source of truth

### 18.2 In-Memory Caching

`EquationBuilder` may cache extraction results during a session.

Cache key should include:

- workspace structural hash
- component registry hash
- domain registry hash
- parameter values hash
- I/O selection hash
- symbolic backend version

### 18.3 Cache Invalidation

Cache must be invalidated when any of the following changes:

- component added
- component removed
- component definition changed
- component parameter changed
- component state definition changed
- connection added
- connection removed
- connection retargeted
- implicit node structure changed
- I/O selection changed
- domain registry changed
- component registry changed
- symbolic backend version changed

### 18.4 Cache Lifetime

Cache is session-scoped only.

Project load always starts with an empty equation cache.

### 18.5 Extraction Triggering

Equation extraction should not run automatically after every small edit.

Phase 2 extraction triggers:

- user clicks `Generate Equations`
- user opens `ModelEquationsPanel` and requests refresh
- `ControllerDesignModule` requests a model artifact
- simulation request needs a current model artifact

This is different from lightweight workspace validation, which may run debounced after graph edits.

---

## 19. Symbolic Backend Adapter

### 19.1 Primary Backend

CasADi is the primary symbolic backend for Phase 2+.

### 19.2 Adapter Requirement

The application must not directly scatter CasADi calls throughout feature modules.

All symbolic backend operations must go through a backend adapter.

Recommended class:

- `CasadiSymbolicAdapter`

Recommended interface:

- `create_symbol(name, shape)`
- `create_parameter(name, value, unit)`
- `parse_expression(template, context)`
- `build_residual(equations)`
- `compute_jacobian(expression, variables)`
- `substitute(expression, substitutions)`
- `simplify(expression)`
- `detect_linearity(expression, variables)`

### 19.3 Backend Isolation

Equation data structures must remain backend-neutral where possible.

Structured schemas should store:

- symbol names
- equation IDs
- source metadata
- units
- traceability metadata

Backend-native expression objects may exist only in runtime memory.

They must not be serialized into project files.

### 19.4 Backend Error Handling

Backend errors must be wrapped in project diagnostics.

Examples:

- expression parse failure
- unsupported symbolic operation
- Jacobian failure
- simplification timeout
- incompatible dimensions

Raw backend exceptions must not reach UI code.

---

## 20. UI Integration: ModelEquationsPanel

### 20.1 Phase 1 Behavior

In Phase 1, the panel is a placeholder.

It may show:

- component count
- connection count
- active domains
- validation status
- message that equation extraction is not available in Phase 1

### 20.2 Phase 2 Behavior

In Phase 2, the panel must show:

- extraction status
- equation list
- grouped equations by source
- state vector
- input vector
- output vector
- DAE reduction status
- ODE artifact summary
- diagnostics
- last valid snapshot status

### 20.3 Equation Display Requirements

Equation display must support:

- user-readable labels
- internal symbol names on demand
- source component links
- source node links
- diagnostic highlighting
- filtering by component, domain, equation kind, and severity

### 20.4 Invalid Current Model Display

When the current workspace cannot produce a valid ODE artifact, the `ModelEquationsPanel` must show an explicit invalid-model state.

Required UI elements:

- top banner: `Current model invalid — equation extraction blocked`
- list of blocking diagnostics
- severity badges for each diagnostic
- source links to affected components, ports, connections, or implicit nodes
- refresh action to reattempt extraction

If a last valid snapshot exists:

- show badge: `Showing last valid model from <timestamp>`
- displayed equations must be marked as snapshot-based
- downstream workflows must indicate whether they use the snapshot or the current model
- the snapshot hash and current workspace hash comparison must be available in diagnostics metadata

If no last valid snapshot exists:

- show message: `No valid model available yet — fix the issues above`
- block downstream controller, transfer-function, and simulation workflows

User actions:

- click diagnostic: select or focus the offending workspace element
- click refresh: retry equation extraction
- click generate with warnings: allowed only if there are no blocking errors

The UI must never silently show old equations as if they belong to the current invalid workspace.

---

## 21. Performance Targets

Initial Phase 2 targets:

- 100 components: equation extraction under 2 seconds
- 250 components: equation extraction under 5 seconds
- 1000 components: equation extraction under 30 seconds as a stretch target

### 21.1 Performance Rules

Implementation should:

- avoid full symbolic expansion unless required
- prefer sparse graph operations
- use deterministic graph traversal
- cache repeated component equation templates
- avoid exponential symbolic simplification
- allow cancellation for long extraction jobs

### 21.2 UI Responsiveness

Long equation extraction must not freeze the UI.

If extraction may take longer than 500 ms, it should run as a background task with progress reporting.

---

## 22. Test Requirements

### 22.1 Equation Definition Tests

Tests must verify:

- equation templates reference valid ports
- equation templates reference valid parameters
- invalid placeholders are detected
- component equation metadata loads correctly
- unknown future metadata is preserved where allowed

### 22.2 Equation Builder Tests

Tests must verify:

- single resistor equations are generated correctly
- RC circuit produces correct first-order ODE structure
- mass-spring-damper system produces correct second-order ODE structure
- ground-less electrical circuit produces a reference error
- fixed-less mechanical system produces a reference warning or error depending on model requirements
- multi-domain motor component produces coupling equations

### 22.3 Implicit Node Tests

Tests must verify:

- node with two ports creates correct across and through equations
- node with N ports creates N equations
- mixed-domain node is rejected before equation extraction
- reference node is fixed to zero

### 22.4 DAE Reduction Tests

Tests must verify:

- simple algebraic substitution reduces correctly
- algebraic loop is detected
- high-index DAE is reported safely
- failed reduction does not crash
- failed reduction does not overwrite last valid snapshot

### 22.5 State Vector Tests

Tests must verify:

- state ordering is deterministic
- state names are stable across rebuilds
- adding a component changes ordering only according to ULID order
- removing a component removes its states
- state mapping uses component ID and state ID, not only index

### 22.6 I/O Mapping Tests

Tests must verify:

- valid input selection produces input vector entry
- valid output selection produces output vector entry
- stale input is excluded with warning
- stale output is excluded with warning
- multiple inputs preserve configured order
- multiple outputs preserve configured order

### 22.7 Snapshot Tests

Tests must verify:

- successful extraction creates a snapshot
- failed extraction preserves previous snapshot
- snapshot contains workspace hash
- snapshot is not saved to project file
- snapshot is marked stale when workspace changes

### 22.8 Cache Tests

Tests must verify:

- unchanged workspace reuses cache
- parameter change invalidates cache
- connection change invalidates cache
- registry change invalidates cache
- project load starts with empty cache

### 22.9 Property-Based Tests

Future property-based tests should verify:

- extraction is idempotent for unchanged graphs
- random valid graphs do not crash extraction
- duplicate unsupported structures produce diagnostics instead of exceptions
- graph traversal order does not change equation ordering

---

## 23. Implementation Order

Recommended implementation order:

1. extend component definitions with `EquationDefinition`
2. extend component definitions with internal state declarations
3. extend port/domain metadata with Bond Graph preparation fields
4. implement equation definition registry validation
5. implement symbol naming and placeholder resolution
6. implement implicit node equation generation
7. implement Bond Graph causality assignment
8. implement `StructuredEquation` and `SymbolicSystem`
9. implement CasADi symbolic adapter
10. implement DAE assembly
11. implement DAE reduction using causality information
12. implement basic explicit ODE extraction for simple linear systems
13. implement ODE artifact schema
14. implement state vector ordering
15. implement I/O mapping
16. implement last valid snapshot store
17. implement ModelEquationsPanel Phase 2 display
18. implement controller hand-off to `ControllerDesignModule`

Causality assignment must be implemented before DAE reduction because the reduction strategy depends on which variables are treated as computed outputs of each component.

---

## 24. Acceptance Criteria

The model equation system is acceptable when:

- `EquationBuilder` consumes only read-only `SystemGraph` snapshots
- component equations are schema-driven
- implicit node equations are generated deterministically
- cross-domain coupling metadata is represented without mixed-domain nodes
- DAE form is produced for supported systems
- simple DAEs are reduced to explicit ODE form
- ODE artifact is produced without owning final state-space matrices
- state vector ordering is deterministic
- input and output mapping is traceable to I/O selection
- stale I/O entries are handled safely
- validation diagnostics are structured and traceable
- last valid snapshot is updated only after successful extraction
- failed extraction does not overwrite last valid snapshot
- derived artifacts are not persisted
- CasADi is isolated behind a symbolic backend adapter
- tests cover equation definitions, node equations, DAE reduction, state ordering, I/O mapping, snapshots, and caching

---

## 25. Open Decisions and Future ADRs

The following decisions should be documented separately:

- `ADR-007-symbolic-backend-casadi.md`
- `ADR-008-bond-graph-causality.md`
- `ADR-009-dae-reduction-strategy.md`
- `ADR-010-linearization-ownership.md`
- `ADR-011-dimensional-analysis-policy.md`

Current accepted decisions:

- 04 stops at ODE artifact.
- `ControllerDesignModule` owns state-space matrix generation.
- CasADi is the primary symbolic backend.
- Equations, symbolic expressions, ODE artifacts, and snapshots are not persisted.
- Last valid model snapshot is session-scoped and owned by `SystemModelingModule`.
