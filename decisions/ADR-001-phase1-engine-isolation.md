# ADR-001: Phase 1 Engine Isolation

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S0  
**Supersedes:** —  
**Superseded by:** —

## Context

The project is structured in two product phases:

* **Phase 1**: visual modeling tier — workspace, graph, validation, persistence, configuration UI placeholders
* **Phase 2**: equation extraction, simulation, stability analysis, controller runtime

The numerical simulation backend lives under `shared/engine/`. This package depends on heavy third-party libraries (CasADi, NumPy with full optimization, HDF5 storage) and contains complex logic for solver execution, integration, linearization, and result handling.

If `shared/engine/` is accessible during Phase 1 development, several risks emerge:

* Phase 1 features may accidentally import engine code, creating premature coupling
* AI coding agents may "complete" features by hooking into engine code that does not yet exist or is incomplete
* Phase 1 tests may attempt to use engine functionality, masking interface design issues
* The engine package may evolve based on Phase 1 needs rather than its own architectural drivers
* Refactoring the engine in Phase 2 may break Phase 1 code that should not have been coupled

## Decision

`shared/engine/` is **closed for import** during Phase 1.

This is enforced at the package level: `shared/engine/__init__.py` raises `ImportError` with a clear explanation when imported during Phase 1.

```python
# shared/engine/__init__.py (Phase 1)
raise ImportError(
    "shared.engine is not available in Phase 1. "
    "It will be activated in Stage S4 of Phase 2 implementation. "
    "See 06_data_flow_and_architecture.md §5.7 and "
    "07_implementation_order.md §10."
)
```

The barrier is removed at Stage S4 entry by replacing this `__init__.py` with the normal package exports.

A static architecture test (`tests/architecture/test_engine_isolation.py`) verifies that no Phase 1 code attempts to import `shared.engine` or any submodule.

## Alternatives Considered

### Alternative 1: Stub package with NotImplementedError

Make `shared/engine/` importable but have all functions raise `NotImplementedError`.

**Rejected because:**

* Allows accidental imports to succeed at module-load time
* Tests against the engine API would compile silently, masking interface issues
* Creates the false impression that the package is partially available

### Alternative 2: Conditional import with feature flag

Use a `PHASE_2_ENABLED` flag and skip imports when False.

**Rejected because:**

* Adds runtime branching to imports, slowing startup
* Flag could be flipped by an AI agent or developer "to test something"
* Fails late (at first call) rather than early (at import)

### Alternative 3: Separate Git branch for Phase 2

Develop Phase 2 on a long-lived feature branch.

**Rejected because:**

* Long-lived branches drift and create painful merges
* Architecture invariants should be enforced by code, not workflow

## Consequences

### Positive

* Clean architectural boundary visible to humans and AI agents
* Forces Phase 1 to design proper abstractions for the eventual engine integration
* Allows Phase 2 to evolve the engine without Phase 1 constraints
* Architecture tests catch violations immediately
* Removing the barrier at Stage S4 is a one-line change

### Negative

* Cannot prototype engine integration during Phase 1
* Some "obvious" coupling opportunities are blocked

### Risks

* Phase 1 may design the wrong abstraction without engine feedback
* Mitigation: ADR-014 establishes the controller wrapper pattern; ADRs 007–010 define the engine interfaces ahead of implementation

## Related ADRs

- ADR-007 Symbolic Backend — CasADi
- ADR-009 DAE Reduction Strategy
- ADR-014 Controller Runtime Wrapper in shared/engine

## References

- `06_data_flow_and_architecture.md` §5.7 (shared layer)
- `07_implementation_order.md` §6 (Stage S0), §10 (Stage S4)
- `08_codex_execution_rules.md` §6.1 (Forbidden Actions for Phase 1)
