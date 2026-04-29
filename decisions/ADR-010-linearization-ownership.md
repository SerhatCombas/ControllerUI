# ADR-010: Linearization Ownership

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S5  
**Supersedes:** —  
**Superseded by:** —

## Context

For control design and stability analysis, the application needs **linearized state-space matrices** `A`, `B`, `C`, `D` derived from the system's `ODEArtifact`.

Linearization involves:

* selecting an **operating point** (equilibrium state, user-specified state, or auto-computed)
* computing Jacobians of `f(x, u)` and `h(x, u)` at the operating point
* validating that the operating point is meaningful (e.g., not at a singularity)
* warning when the system is nonlinear and linearization introduces approximation error

The question: which feature module owns linearization?

A related question: do the resulting matrices live in `ODEArtifact` or a separate artifact?

## Decision

Linearization belongs to **`ControllerDesignModule`**, not `SystemModelingModule`.

Linearization code lives in `features/ControllerDesignModule/builders/linearization.py`.

The `ODEArtifact` produced by `SystemModelingModule` does **not** contain `A/B/C/D` matrices. The matrices are produced by linearization and stored in a separate `StabilityAnalysisArtifact` (see ADR-013) owned by `ControllerDesignModule`.

Operating point sources (per `05 §16.4`):

* `zero` — all states zero
* `component_initial_conditions` — from component `initial_conditions` parameter
* `user_specified` — explicit values
* `last_simulation_initial` — initial state of the last simulation
* `last_simulation_final` — final state of the last simulation
* `auto_equilibrium` — solved via root-finding from `ODEArtifact.f`

For nonlinear systems, linearization is performed only through an **explicit user workflow** (a "Linearize and Analyze" action). The system is **never silently linearized** without user awareness; the resulting `StabilityAnalysisArtifact` carries `nonlinear_warning` metadata.

## Alternatives Considered

### Alternative 1: Linearization in `SystemModelingModule`

Have `SystemModelingModule` produce linearized matrices alongside the ODE.

**Rejected because:**

* Conflates modeling with control-design analysis
* Forces every model to commit to a single operating point
* Hides the linearization choice from the user
* Couples `ODEArtifact` to control-design lifecycle

### Alternative 2: Linearization in `shared/engine/`

Place linearization in the numerical engine.

**Rejected because:**

* Linearization is a control-design step, not a runtime numerical operation
* Engine should consume linearized models, not produce them
* Cross-module: who decides the operating point?

### Alternative 3: Embed `A/B/C/D` in `ODEArtifact`

Add matrix fields to `ODEArtifact` for linear systems.

**Rejected because:**

* Mixes modeling and analysis
* Nonlinear systems would have to silently linearize or set fields to None
* Multiple operating points (multiple analyses) cannot share one ODE

## Consequences

### Positive

* Clean ownership: modeling produces ODE, control design produces linearized analysis
* Multiple `StabilityAnalysisArtifact` instances per `ODEArtifact` (different operating points)
* Nonlinear systems handled honestly: the user must opt in to linearization
* Operating point choice is explicit and traceable

### Negative

* Two-step workflow (simulate, then linearize) instead of one-step
* Some duplication: state vector identity exists in both ODE and stability artifacts (acceptable, both reference the same `(component_id, state_id)` tuples)

### Risks

* User confusion about why "linearize" is a separate step
* Mitigation: UI provides clear "Linearize and Analyze" action; documentation explains the rationale

## Related ADRs

- ADR-004 Equation Builder Ownership
- ADR-006 Controller Owns Transfer-Function and State-Space Builders
- ADR-013 StabilityAnalysisArtifact

## References

- `04_model_equations_requirements.md` §3.2 (State-Space Ownership Decision)
- `05_simulation_and_results_requirements.md` §16 (StabilityAnalysisArtifact), §16.4 (operating points)
- `07_implementation_order.md` §11 (Stage S5), §16.10 (S5 verification)
