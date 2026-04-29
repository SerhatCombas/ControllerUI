# ADR-014: Controller Runtime Wrapper in shared/engine

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S7  
**Supersedes:** —  
**Superseded by:** —

## Context

In Phase 2 Stage S7, the application supports **closed-loop simulation**: a controller (PID, LQR, MPC) is integrated into the simulation loop, computing control input `u` at each solver step.

This requires:

* fast, allocation-free execution at each solver step (potentially thousands of steps per second)
* access to the current state, error, time, dt
* numerical computation, not symbolic
* clear separation from the **design** workflow (tuning, gain selection)

The question: where does the controller's runtime executor live?

`ControllerDesignModule` owns controller **design** (tuning, selection, parameter editing). But running the controller inside the solver loop is not a design concern — it's a numerical execution concern.

## Decision

Controller runtime executors live in **`shared/engine/controllers/`**:

```
shared/engine/controllers/
  __init__.py
  controller_runtime_adapter.py     # abstract base class
  pid_runtime_adapter.py
  lqr_runtime_adapter.py
  mpc_runtime_adapter.py            # Phase 3
```

A `ControllerRuntimeAdapter` exposes:

```python
class ControllerRuntimeAdapter:
    def __init__(self, settings: ControllerSettings) -> None: ...
    def reset(self, initial_state: np.ndarray) -> None: ...
    def compute_control(
        self,
        state: np.ndarray,
        error: float,
        dt: float,
        time: float,
    ) -> float: ...
```

The closed-loop simulation flow:

```
each solver step:
    state, time = solver.current_state()
    error = reference - measured_output(state)
    u = runtime_adapter.compute_control(state, error, dt, time)
    state_dot = ode_artifact.f(state, u)
    solver.advance(state_dot, dt)
```

`ControllerDesignModule` produces a `ControllerSettings` object (from the user's design choices). The runtime adapter consumes those settings; it does not modify them.

In Phase 1, the `controllers/` subpackage exists in the folder skeleton but is not active (per ADR-001, the entire `shared/engine/` package raises `ImportError`).

## Alternatives Considered

### Alternative 1: Runtime adapters in `ControllerDesignModule`

Place runtime executors next to the design code.

**Rejected because:**

* Mixes design (UI-coupled, slow path) with runtime (numerical, hot path)
* Forces the engine to import from a feature module
* Cross-module dependencies become complex

### Alternative 2: Runtime adapters in `shared/utils/controllers/`

Place them in shared utilities.

**Rejected because:**

* Shared utils is for stateless helpers (per `06 §2.3`)
* Controller adapters have state (integrator, previous error) and lifecycle
* Engine is the natural home for numerical execution

### Alternative 3: Runtime adapters as part of `SolverAdapter`

Embed controller logic in the solver.

**Rejected because:**

* Couples controller type to solver type
* Different controllers have different state and step semantics
* Loses separation of concerns

## Consequences

### Positive

* Hot path is in the engine, separate from UI
* Controller settings are the contract between design and runtime
* New controller types add adapters without touching design
* Phase 1 isolation (ADR-001) protects the runtime from premature use

### Negative

* Controller types are duplicated in concept across modules: design class in `ControllerDesignModule`, runtime adapter in `shared/engine/controllers/`
* Coordination needed when adding a new controller type

### Risks

* Settings drift: design and runtime may interpret settings differently
* Mitigation: `ControllerSettings` is a `@dataclass(frozen=True)` with clear field semantics; adapter constructor validates settings

## Related ADRs

- ADR-001 Phase 1 Engine Isolation
- ADR-006 Controller Owns Transfer-Function and State-Space Builders
- ADR-007 Symbolic Backend — CasADi

## References

- `03_configuration_requirements.md` §6 (Controller Settings)
- `05_simulation_and_results_requirements.md` §10 (Closed-loop simulation)
- `06_data_flow_and_architecture.md` §5.7 (`shared/engine/controllers/`)
- `07_implementation_order.md` §13 (Stage S7), §16.14 (S7 verification)
