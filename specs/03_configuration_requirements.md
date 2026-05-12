# 03_configuration_requirements.md

## 1. Purpose

This document defines the requirements for the configuration area of the engineering system designer application.

The configuration area contains user-facing controls for:

* controller settings
* I/O selection
* simulation settings
* plot layout selection

Phase 1 stores and validates configuration data but does not execute controllers, simulations, transfer-function generation, or state-space generation.

The configuration must be designed to support Phase 2+ workflows without requiring schema migration wherever possible.

---

## 2. Scope

### 2.1 In Scope for Phase 1

* Controller configuration UI for P, PI, PD, and PID controllers
* List-based controller data model supporting multiple controllers
* I/O selection data model with Bond Graph variable preparation
* Simulation settings data model with initial-conditions schema
* Plot layout selection for four result panels with grouped plot type dropdown
* Mirror synchronization between Configuration plot dropdowns and per-plot header dropdowns
* Stale reference detection for I/O selections and controller-IO linkage
* Persistence of configuration data in `.systemdesign`
* Dirty state updates when configuration changes
* Placeholder integration with `SimulationResultsPanel`
* Reactive UI synchronization with workspace changes

### 2.2 Out of Scope for Phase 1

* Applying PID to a physical model
* Transfer-function generation
* State-space generation
* Numerical simulation
* LQR, pole placement, MPC execution
* Nonlinear controller execution
* Real-time plotting from simulation data
* MIMO controller editor (single-input/single-output sufficient in Phase 1)
* Channel selection editing UI (Phase 2; schema reserved in Phase 1)

---

## 3. Module Ownership

`ControllerDesignModule` owns configuration state in Phase 1.

Owned state:

* controller settings
* I/O selection
* simulation settings
* plot layout

In Phase 2+, the module additionally owns:

* transfer-function construction
* state-space generation
* controller execution workflows
* simulation request orchestration

(see `06_data_flow_and_architecture.md` §4.3)

`SystemModelingModule` owns workspace graph state and component definitions.

The configuration module may reference workspace components and ports through read-only snapshots, but it must not own or mutate the workspace graph.

Configuration data structures defined in this document must support Phase 2+ workflows without schema migration where possible.

---

## 4. Configuration Panel Structure

The configuration area should be organized into logical sections or tabs:

```text
Configuration Panel
├── Controller Settings
├── I/O Selection
├── Simulation Settings
└── Plot Layout
```

The exact UI layout may be adjusted, but the data model must keep these sections separate.

---

## 5. Controller Settings

### 5.1 Design Principle

Controller configuration must be **list-based**, not single-instance.

This ensures support for:

* multiple controllers in a single project
* cascade control (inner loop + outer loop)
* future MIMO systems
* gain scheduling and switching controllers
* future advanced strategies without schema migration

Phase 1 UI may expose only one controller at a time, but the underlying schema must always be a list.

### 5.2 Supported Controller Types in Phase 1

Initial supported controller types:

* `P`
* `PI`
* `PD`
* `PID`

Future controller types (Phase 2+):

* `state_feedback`
* `pole_placement`
* `LQR`
* `MPC`
* nonlinear control methods

### 5.3 Controller Settings Data Model

Recommended schema:

```json
{
  "controller_settings": {
    "controllers": [
      {
        "id": "ctrl_01HV7NE2K8M4Q1W5E7R9T3Y6X9",
        "display_name": "Main PID",
        "enabled": false,
        "controller_type": "PID",
        "parameters": {
          "kp": 1.0,
          "ki": 0.0,
          "kd": 0.0
        },
        "input_ref": "ioin_01HV7NB3R8M5Y6X9Q2P1C7D4E0",
        "output_ref": "ioout_01HV7NC9M2J4K8Q1W5E7R9T3Y6",
        "metadata": {},
        "extensions": {}
      }
    ],
    "metadata": {},
    "extensions": {}
  }
}
```

### 5.4 Controller Parameter Rules

Parameter definitions:

| Parameter | Applies To     | Type  | Default |
| --------- | -------------- | ----- | ------- |
| `kp`      | P, PI, PD, PID | float | 1.0     |
| `ki`      | PI, PID        | float | 0.0     |
| `kd`      | PD, PID        | float | 0.0     |

Rules:

* P uses `kp`
* PI uses `kp`, `ki`
* PD uses `kp`, `kd`
* PID uses `kp`, `ki`, `kd`
* unused parameters should remain stored where possible but may be hidden in the UI
* invalid numeric input must not crash the application

Validation rules follow `02_workspace_requirements.md` §9 (parameter schema).

### 5.5 Controller-IO Linkage

`input_ref` and `output_ref` link a controller to entries in `io_selection`.

Rules:

* both fields are optional in Phase 1 (controller may exist without binding)
* both must be ULIDs of existing entries in `io_selection.inputs` / `io_selection.outputs`
* if a referenced I/O entry is removed, the controller's reference becomes stale
* stale controller-IO references follow the same handling as stale I/O references (§6.7)
* an enabled controller with missing or stale linkage produces a validation warning
* MIMO controllers (Phase 2+) will use list-based `input_refs` / `output_refs`; Phase 1 schema reserves these names

### 5.6 Phase 1 Controller Behavior

Phase 1 controller behavior includes:

* controller list can be edited (add, remove, configure)
* controller parameters are editable
* controller parameters are persisted
* controller settings update dirty state
* changing `controller_type` preserves common parameters where possible (e.g., `kp` survives PID → PI)

Phase 1 controller behavior excludes:

* controller settings do not affect simulation
* controller settings do not change the workspace graph
* controller cannot be applied to a model

---

## 6. I/O Selection

### 6.1 Purpose

I/O selection defines which workspace signals or ports will be used as inputs and outputs for future simulation, transfer-function generation, and controller design.

In Phase 1, I/O selection is stored and validated against the current workspace, but not executed.

### 6.2 I/O Selection Schema

Use list-based reference objects, not string paths.

Recommended schema:

```json
{
  "io_selection": {
    "inputs": [
      {
        "id": "ioin_01HV7NB3R8M5Y6X9Q2P1C7D4E0",
        "display_name": "Input 1",
        "source": {
          "kind": "port_ref",
          "component_id": "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0",
          "port_id": "p",
          "variable": "across"
        },
        "quantity": "voltage",
        "unit": "V",
        "status": "valid",
        "metadata": {},
        "extensions": {}
      }
    ],
    "outputs": [
      {
        "id": "ioout_01HV7NC9M2J4K8Q1W5E7R9T3Y6",
        "display_name": "Output 1",
        "source": {
          "kind": "port_ref",
          "component_id": "cmp_01HV7ND1N9A3B5C7D9E1F2G4H6",
          "port_id": "flange",
          "variable": "across"
        },
        "quantity": "displacement",
        "unit": "m",
        "status": "valid",
        "metadata": {},
        "extensions": {}
      }
    ],
    "metadata": {},
    "extensions": {}
  }
}
```

### 6.3 I/O Reference Rules

I/O references must use internal component IDs (ULIDs), not display IDs.

Rules:

* `component_id` references `ComponentInstance.id`
* `port_id` references the component's port definition ID
* `display_name` is for UI only and is editable by the user
* `status` may be `valid`, `stale`, or `invalid`

### 6.4 Bond Graph Variable Field

The `source.variable` field must be one of:

* `across` (e.g., voltage, velocity, pressure)
* `through` (e.g., current, force, flow)
* `derived` (computed from across/through, e.g., power, energy)

This field is required for compatibility with future Bond Graph modeling and equation extraction (`06 §4.2 Phase 2+`).

Phase 1 stores and validates the field but does not act on it.

### 6.5 Quantity and Unit Values

`quantity` is a domain-specific label. Allowed values come from `DomainRegistry`.

Phase 1 examples:

* `electrical_analog`: `voltage`, `current`, `charge`, `flux`
* `mechanical_translational`: `displacement`, `velocity`, `acceleration`, `force`, `momentum`

Future domains (mechanical_rotational, hydraulic, thermal) will define their own quantity vocabularies in `DomainRegistry`.

`unit` stores the canonical unit string (e.g., `V`, `A`, `m`, `m/s`, `N`).

Unknown quantity or unit values must be preserved on load and reported as warnings.

### 6.6 Multiple Inputs and Outputs

The data model must support multiple inputs and multiple outputs.

Even if the Phase 1 UI starts with one input and one output, the schema must be list-based to support future MIMO systems without migration.

### 6.7 Stale Reference Handling

If a component or port referenced by I/O selection is removed or changed:

* the I/O entry must not crash the app
* the entry must be marked `status: "stale"`
* the user must receive a validation warning
* stale entries must be persisted with their stale status (not silently dropped)
* Phase 2 simulation/controller execution must be blocked until the stale reference is resolved

(Aligns with `06 §4.3.2` cross-module reference handling.)

### 6.8 I/O Source Kinds

Phase 1 source kinds:

* `port_ref`

Future source kinds (Phase 2+):

* `probe_ref`
* `component_state_ref`
* `implicit_node_ref`
* `expression_ref`
* `engine_output_ref`

Phase 1 must preserve unknown source kinds when loading/saving where safe.

### 6.9 Relationship to shared/probes

In Phase 1, I/O selection data structures are defined inside `ControllerDesignModule` with `port_ref` source kind only.

In Phase 2, additional source kinds (`probe_ref`, `state_variable_ref`, `engine_output_ref`) will reference structures defined in `shared/probes`.

The schema fields `state_variable_id`, `output_id`, and `channel_id` mentioned in `06 §5.4` are reserved for Phase 2. They may appear in `metadata` or `extensions` but are unused in Phase 1.

---

## 7. Simulation Settings

### 7.1 Purpose

Simulation settings define how a future simulation should run.

In Phase 1, these settings are editable and persisted but do not start real simulation.

### 7.2 Simulation Settings Data Model

Recommended schema:

```json
{
  "simulation_settings": {
    "start_time": 0.0,
    "stop_time": 10.0,
    "sample_time": 0.01,
    "max_step": null,
    "solver": "auto",
    "use_controller": false,
    "use_last_valid_model": true,
    "initial_conditions": {
      "source": "component_parameters",
      "overrides": []
    },
    "metadata": {},
    "extensions": {}
  }
}
```

### 7.3 Simulation Settings Rules

Rules:

* `start_time` must be numeric
* `stop_time` must be numeric and greater than `start_time`
* `sample_time` must be positive
* `max_step`, if provided, must be positive
* `solver` is stored but not used in Phase 1
* `use_controller` is stored but does not execute controller logic in Phase 1
* `use_last_valid_model` is stored; snapshot semantics defined in Phase 2
* invalid settings should produce validation errors but must not crash the app

Field semantics for Phase 2 hooks:

* `use_controller`: when true, simulation runs in closed-loop mode using `controller_settings`. Phase 2 only.
* `use_last_valid_model`: when true, simulation uses the last validated model snapshot if the current workspace has validation errors. Phase 2 only. Snapshot management is defined in `04_model_equations_requirements.md` §17.

### 7.4 Initial Conditions Policy

Default source: component parameters (each component contributes its own initial state from its parameters).

Schema:

* `source`: `component_parameters` (default) or `explicit_overrides`
* `overrides`: list, reserved for Phase 2; must be empty in Phase 1 unless explicitly populated

Rules:

* Phase 1 stores `initial_conditions` schema but applies no behavior
* unknown `source` values must be preserved on load
* Phase 2 will define override entry structure (component_id, parameter_id, value)

### 7.5 Solver Values

Phase 1 supported values (UI dropdown):

* `auto`
* `fixed_step`
* `variable_step`

Phase 2 will add:

* `rk45`
* `bdf`
* `radau`
* `lsoda`
* custom backend solver IDs

Unknown solver IDs from future projects must be preserved on load but marked unsupported in the UI.

---

## 8. Plot Layout Settings

### 8.1 Purpose

The result area contains four plot slots in a single results panel.

Default plot slots:

1. Time Response
2. Step Response
3. Bode
4. Pole-Zero

The user can change each plot slot through:

* the Configuration / Plot Layout section (four dropdowns, one per slot)
* the per-plot dropdown in the plot panel header

These two interfaces must stay synchronized (see §14.4.1).

### 8.2 Plot Layout Data Model

Recommended schema:

```json
{
  "plot_layout": {
    "slots": [
      {
        "slot_id": "plot_1",
        "plot_type": "time_response",
        "title": "Time Response",
        "channel_selection": {
          "kind": "channels",
          "channels": [],
          "input": null,
          "output": null
        },
        "axis_config": {
          "x_label": null,
          "y_label": null,
          "x_range": null,
          "y_range": null
        },
        "metadata": {},
        "extensions": {}
      },
      {
        "slot_id": "plot_2",
        "plot_type": "step_response",
        "title": "Step Response",
        "channel_selection": {
          "kind": "io_pair",
          "channels": [],
          "input": null,
          "output": null
        },
        "axis_config": {
          "x_label": null,
          "y_label": null,
          "x_range": null,
          "y_range": null
        },
        "metadata": {},
        "extensions": {}
      },
      {
        "slot_id": "plot_3",
        "plot_type": "bode",
        "title": "Bode",
        "channel_selection": {
          "kind": "io_pair",
          "channels": [],
          "input": null,
          "output": null
        },
        "axis_config": {
          "x_label": null,
          "y_label": null,
          "x_range": null,
          "y_range": null
        },
        "metadata": {},
        "extensions": {}
      },
      {
        "slot_id": "plot_4",
        "plot_type": "pole_zero",
        "title": "Pole-Zero",
        "channel_selection": {
          "kind": "system_wide",
          "channels": [],
          "input": null,
          "output": null
        },
        "axis_config": {
          "x_label": null,
          "y_label": null,
          "x_range": null,
          "y_range": null
        },
        "metadata": {},
        "extensions": {}
      }
    ],
    "fullscreen_slot_id": null,
    "metadata": {},
    "extensions": {}
  }
}
```

### 8.3 Slot Field Semantics

* `slot_id`: stable identifier for the slot (`plot_1` through `plot_4` for Phase 1)
* `plot_type`: identifies the plot kind (see §8.4)
* `title`: user-visible label, may be edited
* `channel_selection`: structured selection that depends on plot type kind (see §8.6)
* `axis_config`: optional axis customization, all `null` in Phase 1
* `fullscreen_slot_id`: which slot is currently fullscreen (`null` if none)

### 8.4 Supported Plot Types

Phase 1 plot types (default in the four slots, placeholder rendering):

* `time_response`
* `step_response`
* `bode`
* `pole_zero`

Phase 2 plot types (selectable in dropdown but show "not yet supported" placeholder in Phase 1):

* `root_locus`
* `nyquist`
* `eigenvalue`
* `input_output_signal`
* `state_variables`
* `road_profile`
* `force`

Phase 1 behavior:

* selected plot types are persisted across save/load
* placeholder rendering shows the plot title and type label
* no real data is plotted
* all plot types are selectable from the dropdown regardless of Phase 1 / Phase 2 grouping

Unknown future plot types loaded from project files must fall back to a placeholder with a warning.

### 8.5 Plot Type Dropdown Grouping

Plot types must be visually grouped in dropdowns to reflect their data source and computation kind.

Group structure:

```text
Time-domain
   Time Response
   Step Response
   State Variables
   Input/Output Signal
   Road Profile
   Force
Frequency-domain
   Bode
   Nyquist
Algebraic
   Pole-Zero
   Root Locus
   Eigenvalue
```

Rules:

* group headers are non-selectable section labels
* the same grouping must appear in both the Configuration plot dropdowns and the per-plot header dropdowns
* unknown future plot types loaded from project files must be shown under an `Unknown` group

### 8.6 Plot Type Compatibility (channel_selection.kind)

The canonical `channel_selection` schema is defined in ADR-016
(`decisions/ADR-016-channel-selection-kind-schema.md`). The fields
are flat siblings on the `channel_selection` object — there is no
nested `io_pair` sub-object. When `kind` is `io_pair`, the
`input` / `output` fields carry the I/O entry IDs; for every other
kind they are `null`. The `channels` field is meaningful only for
`kind: "channels"`.

Each plot type belongs to a `channel_selection.kind` group:

| Plot Type             | Selection Kind | Description                          |
| --------------------- | -------------- | ------------------------------------ |
| `time_response`       | `channels`     | one or more time-domain channels     |
| `step_response`       | `io_pair`      | one input/output pair                |
| `state_variables`     | `channels`     | one or more state channels           |
| `input_output_signal` | `channels`     | one or more I/O channels             |
| `road_profile`        | `channels`     | road input channels                  |
| `force`               | `channels`     | force-related channels               |
| `bode`                | `io_pair`      | one input/output pair (LTI)          |
| `nyquist`             | `io_pair`      | one input/output pair (LTI)          |
| `pole_zero`           | `system_wide`  | entire system, no channel selection  |
| `root_locus`          | `system_wide`  | entire system + gain parameter       |
| `eigenvalue`          | `system_wide`  | entire system, no channel selection  |

`channel_selection.kind` values:

* `channels` — list of result channel IDs from the simulation result artifact
* `io_pair` — one input ID + one output ID (used for transfer-function plots)
* `system_wide` — no per-channel selection; the whole linearized system is plotted

Schema for `kind: "channels"`:

```json
{
  "kind": "channels",
  "channels": ["ch_output_y_0"],
  "input": null,
  "output": null
}
```

Schema for `kind: "io_pair"`:

```json
{
  "kind": "io_pair",
  "channels": [],
  "input": "ioin_01HV7NB3R8M5Y6X9Q2P1C7D4E0",
  "output": "ioout_01HV7NC9M2J4K8Q1W5E7R9T3Y6"
}
```

Schema for `kind: "system_wide"`:

```json
{
  "kind": "system_wide",
  "channels": [],
  "input": null,
  "output": null
}
```

### 8.7 Plot Type Change Behavior

When a slot's `plot_type` is changed, `channel_selection` follows these rules:

* If the new plot type uses the **same `kind`** as the previous type, `channel_selection` is **preserved**.
  * Example: `time_response` → `state_variables` keeps the existing channel list.
  * Example: `bode` → `nyquist` keeps the existing `input` / `output` pair.
* If the new plot type uses a **different `kind`**, `channel_selection` is **reset to defaults** for that kind.
  * Example: `time_response` → `bode` resets channels (`kind` changes from `channels` to `io_pair`).
  * Example: `bode` → `pole_zero` resets to empty `system_wide`.
* The previous `channel_selection` is not retained across kind changes.

This rule preserves user effort within a category while preventing invalid selections from leaking into incompatible plot types.

### 8.8 Auto-Fill Rules (Phase 2 Behavior)

Plot slots with empty `channel_selection` may be auto-filled when a simulation result or analysis artifact becomes available.

Phase 2 auto-fill behavior:

* For `kind: "channels"`:
  * if there is exactly one output in the result artifact, it is auto-bound
  * if there are multiple outputs, the first output (by `output_index`) is auto-bound
  * if no outputs exist, the slot remains empty with a placeholder
* For `kind: "io_pair"`:
  * if there is exactly one input and one output in `io_selection`, that pair is auto-bound
  * otherwise, the slot remains empty with a placeholder asking the user to choose
* For `kind: "system_wide"`:
  * no auto-fill needed; the slot uses the entire linearized system

Auto-fill must not overwrite user-set selections. If a slot has a non-empty `channel_selection` (set by the user or loaded from a project file), auto-fill is skipped.

Phase 1 stores the schema but does not auto-fill since no result artifact exists yet.

### 8.9 Plot Fullscreen Behavior

The results panel must support fullscreen plot behavior in Phase 1:

* double-click plot → plot becomes fullscreen
* top-right X → return to 2x2 grid
* plot header (including the plot type dropdown) remains visible
* advanced controls may appear on hover

The fullscreen state is treated as transient view state and does not need to be persisted unless the user explicitly saves it as project view state (`02 §29.6`).

---

## 9. Configuration Signals

`ControllerDesignModule` must emit signals when configuration changes.

Required signals:

* `controllerSettingsChanged()`
* `ioSelectionChanged()`
* `simulationSettingsChanged()`
* `plotLayoutChanged()`
* `configurationValidationChanged(report)`
* `dirtyChanged(is_dirty)` — module-level dirty event routed to application dirty state

Configuration changes must update the project dirty state because configuration is persisted in the project file.

The canonical signal list is mirrored in `06_data_flow_and_architecture.md` §4.3.1. If the lists diverge, `06` is authoritative.

`plotLayoutChanged()` is emitted when:

* a slot's `plot_type` changes
* a slot's `channel_selection` changes
* a slot's `title` or `axis_config` changes
* the `fullscreen_slot_id` changes

This signal must be received by both the Configuration UI and the per-plot header UI to maintain dropdown synchronization (see §14.4.1).

---

## 10. Validation

### 10.1 Validation Categories

Configuration validation must include:

* controller parameter type and range validation
* missing or stale `input_ref` / `output_ref` for enabled controllers
* I/O stale reference validation (component or port removed)
* simulation time validation (`stop_time > start_time`, `sample_time > 0`)
* unsupported `controller_type` warning
* unsupported `solver` warning
* unknown `plot_type` warning with placeholder fallback
* unknown `source.kind` warning with raw data preservation
* `channel_selection.kind` mismatch with `plot_type` (schema-level error)

### 10.2 Validation Severity

Use validation severity levels (aligned with `02 §20.5`):

* `info`
* `warning`
* `error`

Examples:

* stale I/O reference → `warning` in Phase 1, `error` before simulation in Phase 2
* `stop_time <= start_time` → `error`
* unsupported solver ID → `warning`
* unknown plot type → `warning` with placeholder fallback
* enabled controller with missing `input_ref`/`output_ref` → `warning`
* `channel_selection.kind` does not match `plot_type` requirement → `error`

### 10.3 Validation Timing

* **Real-time validation**: parameter type checks during editing (synchronous, lightweight)
* **Debounced incremental validation**: after configuration changes (100–300 ms debounce, aligns with `02 §20.6`)
* **Cross-module validation**: triggered by `SystemModelingModule` signals (`componentRemoved`, `componentChanged`)

Validation must not block the UI thread.

### 10.4 Cross-Module Read-Only Access

Configuration validation must be able to query a read-only snapshot of the workspace model.

Rules:

* `ControllerDesignModule` may read workspace snapshots through a read-only API
* `ControllerDesignModule` must never mutate workspace graph state
* stale component/port references must be reported to project-level validation, not only configuration-local validation

(Aligns with `06 §4.3` "consumer not owner" principle.)

---

## 11. Persistence

### 11.1 Project File Integration

Configuration data is saved as top-level project sections:

```json
{
  "controller_settings": {},
  "io_selection": {},
  "simulation_settings": {},
  "plot_layout": {}
}
```

(Top-level project schema is defined in `06 §11.1`.)

### 11.2 Serialization Rules

* internal IDs (ULIDs) are persisted, not display IDs
* stale entries are persisted with their `status: "stale"` (not silently dropped)
* unknown fields are preserved during load/save where safe
* schema version is inherited from project-level `schema_version`

### 11.3 Unknown Field Preservation

Unknown fields in configuration sections must be preserved during load/save.

This supports forward compatibility with future controller types, solvers, plot types, and source kinds.

### 11.4 Partial Load Safety

* invalid sections may be skipped with a user-visible warning
* missing sections fall back to defaults from `default_config.json` (§13)
* the application must not crash on malformed configuration

### 11.5 Load Behavior

On project load:

* configuration data is loaded through direct APIs (not via setter signals)
* module signals may be suspended during batch load to avoid signal storms
* one consolidated `configurationChanged` signal may be emitted after load completes
* dirty state remains `false` unless migration or recovery requires saving

(Aligns with `06 §7.7` load flow.)

### 11.6 Save Behavior

On save:

* all four configuration sections are serialized
* save must not be blocked by validation errors (warnings or errors are saved alongside)
* validation state may be included in metadata

(Aligns with `06 §7.6` save flow.)

---

## 12. Migration

### 12.1 Schema Versioning

Configuration sections inherit the project-level `schema_version` from `02 §27.3` and `06 §11.3`.

Each section may optionally declare its own version in `metadata` for fine-grained migration.

### 12.2 Forward Compatibility

When loading a newer-version project file in an older application:

* unknown `controller_type` → load with warning, disable controller in UI
* unknown `solver` → load with warning, fall back to `auto` in UI but preserve original value
* unknown `plot_type` → load with warning, fall back to placeholder under `Unknown` group
* unknown `source.kind` → preserve raw data, mark entry as unsupported
* unknown `channel_selection.kind` → preserve raw data, mark slot as unsupported
* unknown fields in metadata or extensions → preserved silently

### 12.3 Backward Compatibility

When loading an older-version project file:

* missing fields are populated from `default_config.json`
* missing sections fall back to defaults entirely
* legacy `signals: []` field (from earlier schema) is migrated to `channel_selection: { kind: "channels", channels: [...], input: null, output: null }`
* no data loss

### 12.4 Migration Failures

If migration fails:

* original file must remain untouched
* user receives an error report
* no partial state is committed

(Aligns with `06 §7.7` migration failure behavior.)

---

## 13. Default Configuration

When a new project is created, configuration sections are initialized with default values defined in:

```text
shared/registry/default_config.json
```

Phase 1 defaults:

* `controller_settings.controllers`: one disabled PID controller (`kp=1.0, ki=0.0, kd=0.0`) with no I/O linkage
* `io_selection.inputs`: empty list
* `io_selection.outputs`: empty list
* `simulation_settings`: `start_time=0.0`, `stop_time=10.0`, `sample_time=0.01`, `solver="auto"`
* `plot_layout.slots`: four slots with the following defaults:
  * `plot_1`: `time_response` (kind: `channels`)
  * `plot_2`: `step_response` (kind: `io_pair`)
  * `plot_3`: `bode` (kind: `io_pair`)
  * `plot_4`: `pole_zero` (kind: `system_wide`)

Defaults must be loadable independently of any project file (used for "New Project" action).

---

## 14. UI Behavior

### 14.1 Controller Settings UI

UI elements:

* list view of all configured controllers
* "Add controller" button → controller_type selector
* per-controller: enable/disable toggle, expand/collapse details
* parameter editing fields relevant to selected `controller_type`:
  * P → Kp only
  * PI → Kp, Ki
  * PD → Kp, Kd
  * PID → Kp, Ki, Kd
* `input_ref` / `output_ref` dropdowns populated from current `io_selection`
* visual indicator for stale `input_ref` / `output_ref`
* "delete controller" button per entry

Phase 1: simple list with edit form for one active controller at a time.
Phase 2: extends to MIMO inputs/outputs as list editors.

Unused parameters may remain stored but hidden from the UI.

### 14.2 I/O Selection UI

The UI must allow the user to select input/output references from the current workspace.

Required behavior:

* show available source/sensor/probe-like components from the current workspace
* show component `display_id` and `custom_label` (internally store ULID `id`)
* mark stale references clearly (red highlight, warning icon)
* allow user to clear stale selections
* prevent invalid selections at UI level (e.g., wrong domain combinations)

Reactive updates:

* the I/O selection UI must subscribe to `SystemModelingModule` signals (`componentAdded`, `componentRemoved`, `componentChanged`)
* the available sources list must refresh reactively on workspace changes
* stale references must be re-validated on `componentRemoved`

### 14.3 Simulation Settings UI

The UI must expose:

* start time
* stop time
* sample time
* max step
* solver (dropdown with Phase 1 values + preserved unknowns)
* use controller (checkbox)
* use last valid model (checkbox)

Phase 2 will add initial-conditions override editor.

### 14.4 Plot Layout UI

The UI must expose:

* four plot slot dropdowns in the **Configuration / Plot Layout** section (one dropdown per slot)
* per-plot dropdown in each plot panel header
* fullscreen toggle by double-click
* close fullscreen with top-right X button

#### 14.4.1 Per-Plot Header Dropdown Visual

Each of the four plot panels must show a header bar with:

* the current plot type as visible title text (e.g., `Time Response`, `Bode`, `Pole-Zero`)
* a small caret icon (downward chevron `▾` or equivalent) immediately next to the title indicating the title is interactive
* an optional close/expand control on the right edge for fullscreen toggle

Interaction:

* clicking on the title text or the caret opens the grouped dropdown menu
* keyboard focus on the header followed by `Enter` or `Space` opens the same menu
* selecting a new plot type from the menu commits the change immediately and triggers `plotLayoutChanged()`
* pressing `Escape` while the menu is open cancels the selection without changing state

The header dropdown is the **same logical control** as the Configuration / Plot Layout dropdown; both surfaces edit the same `plot_layout.slots[i].plot_type` field. See §14.4.2 for synchronization semantics.

#### 14.4.2 Dropdown Synchronization (Mirror)

The Configuration plot dropdowns and the per-plot header dropdowns must show the same state (mirror).

Rules:

* both dropdowns read from and write to the same `plot_layout.slots[i].plot_type` field
* changing one immediately updates the other through the `plotLayoutChanged()` signal
* there is no separate "default" vs "current" state — a single source of truth governs both UIs
* both dropdowns use the same grouping (§8.5)
* dropdown widget instances may be different Qt objects, but they must subscribe to the same model signals; widget-local cached state is forbidden

This ensures the user can change plot types from either entry point without state drift.

#### 14.4.3 Dropdown Grouping

Dropdown items must be visually grouped to reflect plot kind, as defined in §8.5:

* Time-domain group
* Frequency-domain group
* Algebraic group
* Unknown group (only shown when a project file contains unrecognized plot types)

Group headers are non-selectable section labels.

#### 14.4.4 Plot Type Selection State

When the user selects a plot type that requires data not yet available (e.g., `bode` without a `StabilityAnalysisArtifact` in Phase 2):

* the plot type is still selectable in the dropdown
* the plot panel shows a placeholder with a clear message and an action button (e.g., "Linearize and Analyze")
* the dropdown is never silently disabled

This keeps user intent visible and provides a clear path to resolve missing prerequisites.

In Phase 1, all plot types render placeholders since no simulation or analysis runs.

#### 14.4.5 Channel Selection UI (Phase 2)

When `channel_selection` editing UI is added in Phase 2:

* `kind: "channels"` → multi-select dropdown of available result channels
* `kind: "io_pair"` → two dropdowns: input selector + output selector
* `kind: "system_wide"` → no channel control shown

Plot type changes follow §8.7 (preserve within same kind, reset across kinds).

Phase 1 stores `channel_selection` in the schema but does not expose editing UI for channels.

---

## 15. Threading and Execution

Phase 1 configuration operations run on the main thread.

No heavy computation should occur when editing configuration values.

Future Phase 2 simulation execution must not block the UI thread, following the threading rules in `06 §17`.

---

## 16. Test Requirements

### 16.1 Controller Settings Tests

* default controller settings load correctly
* multiple controllers can coexist in a project
* changing `controller_type` preserves common parameters (e.g., `kp` survives PID → PI)
* invalid numeric values are rejected or marked invalid
* `input_ref` / `output_ref` can reference existing I/O entries
* stale `input_ref` / `output_ref` is detected when target I/O is removed

### 16.2 I/O Selection Tests

* valid `port_ref` is accepted
* removed component creates a stale reference (`status: "stale"`)
* stale reference is reported in validation
* internal ULIDs are used, not display IDs
* `variable` field accepts only `across`, `through`, `derived`
* unknown `source.kind` values are preserved during load/save
* unknown `quantity` or `unit` values are preserved with warnings

### 16.3 Simulation Settings Tests

* `stop_time` must be greater than `start_time`
* `sample_time` must be positive
* unsupported solver produces warning but is preserved
* `initial_conditions` schema round-trips through save/load
* unknown `solver` values are preserved on load

### 16.4 Plot Layout Tests

* default four plot slots exist on new project with correct `channel_selection.kind`
* `plot_type` changes persist across save/load
* unknown `plot_type` falls back to placeholder safely
* fullscreen toggle works without persistence requirement
* changing plot type within the same `kind` preserves `channel_selection` (§8.7)
* changing plot type across different `kinds` resets `channel_selection` to defaults (§8.7)
* Configuration plot dropdown and per-plot header dropdown stay synchronized (§14.4.1)
* dropdown groups display correctly: Time-domain, Frequency-domain, Algebraic
* selecting a plot type with unavailable data shows a placeholder, not a disabled state
* `plotLayoutChanged()` is emitted on `plot_type`, `channel_selection`, `title`, and `fullscreen_slot_id` changes
* legacy `signals: []` field migrates to `channel_selection: { kind: "channels", ... }`

### 16.5 Persistence Tests

* configuration save/load round trip without data loss
* unknown fields preserved
* load with missing sections applies defaults
* batch load does not emit excessive change signals
* stale entries persist with stale status
* `channel_selection.kind` is preserved across save/load
* unknown `channel_selection.kind` values are preserved as-is

### 16.6 Cross-Module Tests

* `ControllerDesignModule` reads workspace via read-only snapshot
* `ControllerDesignModule` never writes to workspace
* `componentRemoved` signal triggers stale reference re-validation
* I/O selection UI refreshes on workspace component changes

### 16.7 Migration Tests

* unknown `controller_type` from future schema is preserved with warning
* unknown `plot_type` falls back to placeholder under `Unknown` group
* unknown `channel_selection.kind` is preserved with warning
* missing sections fall back to `default_config.json`

### 16.8 Stress Tests

* 100+ I/O entries handled without UI freeze
* many stale references reported without crash
* configuration validation completes within 100 ms for typical projects

---

## 17. Acceptance Criteria

Configuration implementation is acceptable when:

### Controller

* multiple controllers (P, PI, PD, PID) can be added, edited, and persisted
* `controller_type` change preserves common parameters
* controller can be linked to I/O entries via `input_ref`/`output_ref`
* stale controller-IO linkage is detected and reported

### I/O Selection

* inputs/outputs use ULID references to `ComponentInstance.id`
* removing a referenced component marks I/O entry as stale
* I/O UI refreshes reactively on workspace component changes
* `variable` field (across/through/derived) is required and validated
* `quantity` and `unit` are stored and round-trip correctly

### Simulation

* `start_time`, `stop_time`, `sample_time` are validated on edit
* `stop_time <= start_time` produces error severity
* `initial_conditions` schema is preserved even when `overrides` is empty
* unknown solver values are preserved on load

### Plot Layout

* four default plot slots are created on new project with correct `channel_selection.kind`
* `plot_type` changes persist across save/load
* unknown `plot_type` from future versions falls back to placeholder
* fullscreen toggle works without persistence requirement
* `channel_selection.kind` enforces compatibility between plot type and selection
* plot type changes within the same kind preserve channel selection
* plot type changes across different kinds reset channel selection
* Configuration plot dropdowns and per-plot header dropdowns are synchronized (mirror)
* dropdown grouping (Time-domain / Frequency-domain / Algebraic) is visible in both UIs

### Persistence

* configuration round-trips through save/load without data loss
* unknown fields are preserved
* missing sections fall back to `default_config.json`
* stale entries persist with stale status (not silently dropped)
* save is not blocked by validation errors
* legacy `signals: []` field migrates to `channel_selection`

### Cross-Module

* `ControllerDesignModule` reads workspace via read-only snapshot API
* `ControllerDesignModule` never mutates workspace graph state
* `componentRemoved` signal triggers stale reference re-validation
* configuration validation timing follows debounced incremental strategy

### Performance

* 100+ I/O entries do not cause UI freeze during validation
* configuration validation completes within 100 ms for typical projects

### Phase Boundary

* no simulation, equation, or controller execution is implemented in Phase 1
* `shared/engine` is not imported by `ControllerDesignModule` in Phase 1
* schema is structured to support Phase 2+ workflows without migration where possible
