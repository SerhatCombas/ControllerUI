# ADR-009: DAE Reduction Strategy

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S3  
**Supersedes:** —  
**Superseded by:** —

## Context

Physical system models naturally produce **Differential-Algebraic Equations (DAEs)**:

* differential equations from energy storage elements (capacitors, inductors, masses, springs)
* algebraic constraints from conservation laws at nodes (Kirchhoff, Newton)
* algebraic constraints from non-storage elements (resistors, dampers)

A solver-friendly form is the **Ordinary Differential Equation (ODE)** form:

```
x_dot = f(x, u)
y     = h(x, u)
```

Converting DAE to ODE requires:

* identifying minimal state vector
* eliminating dependent variables
* index reduction when algebraic constraints contain hidden differential constraints (high-index DAE)

The question: which strategy does the equation pipeline use?

## Decision

The equation pipeline performs **DAE → ODE reduction** using:

1. **Causality assignment** (Bond Graph SCAP, per ADR-008) to determine equation ordering
2. **Algebraic loop elimination** by symbolic substitution where possible
3. **Index reduction** using **Pantelides' algorithm** for index-1 → index-0 reduction
4. **State vector minimization** by removing redundant storage elements (dependent capacitors, dependent springs)

The output is an `ODEArtifact` containing `x_dot = f(x, u)` and `y = h(x, u)` with:

* state identity tied to `(component_id, state_id)` per ADR-002
* linearity flag indicating whether `f` and `h` are linear
* metadata describing reductions performed (which storage elements were dependent, which constraints were eliminated)

If reduction fails:

* index too high → `error.equation.dae_index_too_high`
* algebraic loop unresolvable → `error.equation.algebraic_loop`
* singular system → `error.equation.singular_system`

These errors are surfaced with diagnostic context for user troubleshooting.

The reduction is a **deterministic compile step** — same input graph produces the same `ODEArtifact`.

## Alternatives Considered

### Alternative 1: Solve DAE directly without reduction

Use CasADi's IDAS DAE solver and skip reduction.

**Rejected because:**

* High-index DAEs cannot be solved without reduction
* Reduction enables better solver performance for low-index systems
* Linearization requires ODE form
* Stability analysis (state-space) requires ODE form

### Alternative 2: Manual reduction by user

Have the user identify state variables.

**Rejected because:**

* Hostile to schematic-thinking users
* Error-prone for non-trivial systems

### Alternative 3: Numerical reduction without causality

Use generic DAE-to-ODE conversion algorithms without Bond Graph causality.

**Rejected because:**

* Less robust than causality-guided reduction
* Loses diagnostic value (cannot pinpoint why reduction fails)
* Conflicts with ADR-008

## Consequences

### Positive

* Robust handling of standard mechanical and electrical systems
* Compatible with Pantelides' algorithm for high-index reduction
* Diagnostic errors guide users toward fixes
* Linearization and stability analysis become possible

### Negative

* Implementation complexity
* Some topologies may produce reductions that surprise users
* Pantelides' algorithm may produce non-minimal state representations in some cases

### Risks

* Edge cases with mixed-causality components
* Mitigation: tests cover canonical topologies (RLC, mass-spring-damper, quarter-car, suspension models)
* Reduction failures must be reported clearly
* Mitigation: structured errors in `11 §8.1`

## Related ADRs

- ADR-004 Equation Builder Ownership
- ADR-008 Bond Graph Causality
- ADR-010 Linearization Ownership

## References

- `04_model_equations_requirements.md` §6 (ODE Artifact), §10 (DAE Reduction)
- `07_implementation_order.md` §16.9 (S3 verification)
- Pantelides, C. C. (1988). "The consistent initialization of differential-algebraic systems"
