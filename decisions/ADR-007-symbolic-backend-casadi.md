# ADR-007: Symbolic Backend — CasADi

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S4  
**Supersedes:** —  
**Superseded by:** —

## Context

Phase 2 Stage S4 requires a symbolic + numerical backend for:

* ODE integration
* automatic differentiation (Jacobian computation for linearization)
* potential future MPC (Model Predictive Control) and optimization-based control
* DAE handling with index reduction

The choice constrains:

* runtime performance
* differentiation capabilities
* packaging size and platform compatibility
* learning curve for contributors

## Decision

The project uses **CasADi** as the primary symbolic backend for `shared/engine/`.

CasADi is chosen because it:

* provides excellent automatic differentiation
* has a mature DAE solver (IDAS via SUNDIALS)
* supports the entire workflow from symbolic equation handling through MPC
* is used internally by MATLAB's MPC Toolbox, validating maturity

**SciPy `solve_ivp`** is allowed as an internal fallback when CasADi cannot handle a specific case (e.g., DAE without index reduction, custom event detection). The fallback is logged explicitly (see error code `warning.simulation.fallback_to_scipy` in `11`).

**SymPy** is allowed only for development and debugging — never on the runtime simulation path.

A `SolverAdapter` abstraction (`shared/engine/solvers/solver_adapter.py`) wraps backend selection, allowing the engine to delegate to CasADi by default and SciPy when necessary.

## Alternatives Considered

### Alternative 1: SciPy as primary

Use only `scipy.integrate.solve_ivp` and `scipy.linalg`.

**Rejected because:**

* No automatic differentiation
* No path to MPC
* Inferior DAE handling
* Forces manual Jacobian computation for linearization

### Alternative 2: SymPy as primary

Use SymPy for symbolic and numerical work.

**Rejected because:**

* Pure-Python evaluation is too slow for runtime simulation
* Numerical solver ecosystem is weaker than CasADi or SciPy

### Alternative 3: PyTorch or JAX

Use a deep-learning autodiff framework.

**Rejected because:**

* Overkill for engineering simulation
* GPU dependency not desired
* Large package size
* Optimized for ML, not for stiff DAEs and physical systems

### Alternative 4: Modelica runtime (e.g., OMSimulator)

Use OpenModelica's runtime via an adapter.

**Rejected because:**

* Adds a heavyweight external dependency
* Couples the application to OpenModelica's lifecycle and bug surface
* Forbidden explicitly in `01 §19` (Modelica/Simscape Inspiration Boundary)

## Consequences

### Positive

* Strong autodiff enables MPC and trajectory optimization
* Mature DAE handling
* Single dependency for symbolic and numerical work
* Future-proof for advanced control workflows

### Negative

* C++ build dependency makes installation slower than pure-Python alternatives
* Smaller community and fewer Stack Overflow answers than SciPy
* Steeper learning curve for contributors

### Risks

* Long-term Python 3.13+ compatibility must be monitored
* Mitigation: `SolverAdapter` abstraction allows backend swap; SciPy fallback already covers many cases
* CasADi binary distribution issues on niche platforms
* Mitigation: SciPy fallback ensures the application remains usable even if CasADi fails to install

## Related ADRs

- ADR-001 Phase 1 Engine Isolation
- ADR-009 DAE Reduction Strategy
- ADR-014 Controller Runtime Wrapper in shared/engine

## References

- `04_model_equations_requirements.md` §3.3 (Symbolic Backend Decision)
- `05_simulation_and_results_requirements.md` §3 (Engine Architecture)
- `06_data_flow_and_architecture.md` §5.7
- `07_implementation_order.md` §10 (Stage S4)
