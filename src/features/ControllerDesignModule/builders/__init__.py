"""Transfer-function, state-space, and linearization builders.

**Phase 2 only** — this package is populated in Stage S5. Phase 1
keeps the package as an empty placeholder to fix the architectural
ownership of these builders inside ControllerDesignModule.

Phase 2 contents (planned, populated during Stage S5):

* TransferFunctionBuilder — produces transfer functions from ODE artifact
* StateSpaceBuilder — produces A/B/C/D matrices via linearization
* Linearization — Jacobian computation at operating points

These builders consume `ODEArtifact` (produced by SystemModelingModule)
and produce `StabilityAnalysisArtifact` (owned by ControllerDesignModule).

References
----------
* ADR-006: Controller Owns Transfer-Function and State-Space Builders
* ADR-010: Linearization Ownership
* ADR-013: StabilityAnalysisArtifact
* `specs/04_model_equations_requirements.md` §3.2
* `specs/07_implementation_order.md` §11 (Stage S5)
"""

__all__: list[str] = []
