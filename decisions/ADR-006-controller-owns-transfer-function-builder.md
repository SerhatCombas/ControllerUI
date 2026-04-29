# ADR-006: Controller Owns Transfer-Function and State-Space Builders

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S5  
**Supersedes:** —  
**Superseded by:** —

## Context

In Phase 2, the application needs **transfer-function** and **state-space** representations of the system for control design and stability analysis. These representations are derived **from** the `ODEArtifact` produced by `SystemModelingModule` (per ADR-004).

The question: which feature module owns the transfer-function builder and state-space builder?

Two candidates:

* **`SystemModelingModule`** — already produces `ODEArtifact`
* **`ControllerDesignModule`** — consumes the result for control design

The choice determines whether `ODEArtifact` itself contains `A/B/C/D` matrices and transfer-function representations, or whether those live in a separate downstream artifact.

## Decision

Transfer-function and state-space builders belong to **`ControllerDesignModule`**.

* `features/ControllerDesignModule/builders/transfer_function_builder.py`
* `features/ControllerDesignModule/builders/state_space_builder.py`
* `features/ControllerDesignModule/builders/linearization.py`

These builders consume the `ODEArtifact` from `SystemModelingModule` and produce a downstream `StabilityAnalysisArtifact` (see ADR-013) that contains `A`, `B`, `C`, `D` matrices, eigenvalues, frequency response, and stability margins.

The `ODEArtifact` itself does **not** contain final state-space matrices. It contains:

* `x_dot = f(x, u)` symbolic form
* `y = h(x, u)` symbolic form
* state vector identity (component-scoped, per ADR-002)
* input/output declarations
* linearity flag (whether the system is linear)

Linearization, when needed for design or analysis, is performed by `ControllerDesignModule` against an explicit operating point.

## Alternatives Considered

### Alternative 1: `SystemModelingModule` produces a state-space artifact

Have `ODEArtifact` already contain `A/B/C/D` matrices for linear systems.

**Rejected because:**

* Conflates modeling (ODE form) with analysis (linear approximation)
* Forces nonlinear systems to silently linearize, hiding the choice from the user
* Makes the modeling module responsible for control-design concepts (operating point, linearization tolerance)

### Alternative 2: `shared/engine/` builders

Place builders in the numerical engine layer.

**Rejected because:**

* Builders are symbolic/structural, not numerical
* Engine should consume linearized models, not produce them
* Phase 1 isolation of `shared/engine/` (ADR-001) prevents using these builders during early development

### Alternative 3: Cross-module shared package

Place builders in a `shared/control/` package.

**Rejected because:**

* Only `ControllerDesignModule` consumes them
* Sharing creates a phantom user with no concrete need

## Consequences

### Positive

* Clean separation: modeling produces ODE, control design produces linearized artifacts
* Nonlinear systems are explicit: linearization is a deliberate workflow, not silent
* `ControllerDesignModule` owns its design pipeline end-to-end
* Multiple operating points can produce multiple `StabilityAnalysisArtifact` instances from one `ODEArtifact`

### Negative

* Two-step workflow: simulate from ODE, then linearize for design
* Some duplication of state vector identity between ODE and stability artifacts (managed by `02 §8` identity model)

### Risks

* Confusion about where matrices come from
* Mitigation: ADR-010 (Linearization Ownership) and ADR-013 (StabilityAnalysisArtifact) reinforce this boundary

## Related ADRs

- ADR-004 Equation Builder Ownership
- ADR-010 Linearization Ownership
- ADR-013 StabilityAnalysisArtifact
- ADR-014 Controller Runtime Wrapper in shared/engine

## References

- `04_model_equations_requirements.md` §3.2 (State-Space Ownership Decision), §6 (ODE Artifact)
- `05_simulation_and_results_requirements.md` §16 (StabilityAnalysisArtifact)
- `06_data_flow_and_architecture.md` §4.3 (ControllerDesignModule)
- `07_implementation_order.md` §11 (Stage S5)
