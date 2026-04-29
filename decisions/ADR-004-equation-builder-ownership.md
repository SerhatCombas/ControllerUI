# ADR-004: Equation Builder Ownership

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S3  
**Supersedes:** —  
**Superseded by:** —

## Context

In Phase 2, the application must extract differential equations from the validated graph of components and connections. This involves:

* generating per-component equation templates
* assembling node equations using across/through variable conservation
* handling cross-domain coupling (transformers, gyrators)
* causality assignment (Bond Graph principles)
* algebraic loop elimination
* DAE index reduction
* producing an `ODEArtifact` with `x_dot = f(x, u)` and `y = h(x, u)`

The question: which feature module owns this work?

Two candidates:

* **`SystemModelingModule`** — owner of `WorkspaceModel` and `SystemGraph`
* **`ControllerDesignModule`** — owner of controller workflow, which consumes equations for design

A third option (`shared/engine/` ownership) was rejected because equations are a **modeling** concept, not a numerical simulation concept.

## Decision

The equation builder belongs to **`SystemModelingModule`**.

The pipeline lives in `features/SystemModelingModule/equations/` (added in Stage S3).

Rationale:

* equations are part of the model definition; controllers consume the resulting `ODEArtifact` but do not author it
* `SystemModelingModule` already owns `WorkspaceModel` and assembles `SystemGraph`, making it the natural place for graph-derived analysis
* keeping equations in System Modeling avoids `ControllerDesignModule` reaching back into modeling internals

The Phase 2 pipeline is:

```
SystemGraph (validated)
  → DAE assembly (in SystemModelingModule)
    → causality preparation (Bond Graph)
      → algebraic elimination
        → index reduction
          → ODEArtifact (in SystemModelingModule)
```

`ControllerDesignModule` consumes the `ODEArtifact` to perform linearization and produce `StabilityAnalysisArtifact` (see ADR-010).

## Alternatives Considered

### Alternative 1: `ControllerDesignModule` owns equation extraction

Place the equation builder near the controller design workflow, since controllers need equations.

**Rejected because:**

* Controllers consume equations; they do not author them
* Forces the controller module to import and understand graph internals
* Couples modeling to a specific control-design workflow
* Multiple consumers (simulation, linearization, future analyses) would all need to touch a controller-owned builder

### Alternative 2: Standalone module `EquationModule`

Create a dedicated feature module just for equations.

**Rejected because:**

* Equations and graph assembly are tightly coupled
* Splitting them creates artificial seams
* Adds a third feature module with no obvious distinct user-facing scope

### Alternative 3: `shared/engine/equations/`

Place equation extraction in the numerical engine.

**Rejected because:**

* Equations are symbolic, not numerical
* Engine should consume equations, not produce them
* Phase 1 isolation of `shared/engine/` (ADR-001) would prevent feature modules from authoring equations

## Consequences

### Positive

* Single owner for graph → equations workflow
* Clear consumer relationship with `ControllerDesignModule`
* Reuse: simulation, stability, future analyses all consume the same `ODEArtifact`
* Spec sections (`04`) align with module ownership

### Negative

* `SystemModelingModule` becomes the larger feature module
* Some controller-specific equation transformations will need to be coordinated with the controller module

### Risks

* Boundary creep: controller-specific transformations might leak into `SystemModelingModule`
* Mitigation: ADR-006 explicitly assigns transfer-function and state-space builders to `ControllerDesignModule`; ADR-010 assigns linearization to `ControllerDesignModule`

## Related ADRs

- ADR-006 Controller Owns Transfer-Function and State-Space Builders
- ADR-008 Bond Graph Causality
- ADR-009 DAE Reduction Strategy
- ADR-010 Linearization Ownership

## References

- `04_model_equations_requirements.md` §3 (Phase Boundary and Ownership)
- `06_data_flow_and_architecture.md` §4.2 (SystemModelingModule)
- `07_implementation_order.md` §9 (Stage S3)
