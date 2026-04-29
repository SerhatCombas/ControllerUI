# Architecture

## Layer 1: Application Layer

- `SystemDesignerShell`

Owns the top-level application composition, layout, navigation, and module orchestration.

## Layer 2: Feature Module Layer

- `SystemModelingModule`
- `ControllerDesignModule`

Each feature module owns its domain workflow and coordinates the views/panels below it.

## Layer 3: View / Panel Layer

- `ModelLibraryPanel`
- `BlockDiagramWorkspace`
- `ControllerTuningPanel`
- `SimulationResultsPanel`

These are the user-facing work surfaces and panels used by the feature modules.

## Shared Engine Layer

- `shared/engine`
- `shared/components`
- `shared/graph`
- `shared/probes`
- `shared/types`
- `shared/utils`
- `shared/registry`

Both feature modules depend on this shared layer. The system modeling module builds a workspace graph from dropped components. The shared engine converts that graph into equations and simulation-ready models. The controller module consumes those models for transfer-function/state-space construction, controller tuning, simulation, and result analysis.

## Data Flow

1. User selects components from `ModelLibraryPanel`.
2. User places and configures components in `BlockDiagramWorkspace`.
3. The workspace graph is assembled through `shared/graph`.
4. `shared/engine` builds the symbolic/numeric model.
5. `ControllerDesignModule` consumes the model for controller design.
6. `SimulationResultsPanel` and `ModelEquationsPanel` present results and equations.
