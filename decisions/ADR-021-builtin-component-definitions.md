# ADR-021: Built-in Component Definitions as Python Dataclasses (Phase 1)

**Status:** Accepted  
**Date:** 2026-05-11  
**Deciders:** Serhat Combas  
**Stage:** S1  
**Supersedes:** —  
**Superseded by:** —

## Context

`specs/01_library_requirements.md §24.1` lists this as an **open question**:

> "Should built-in component definitions initially be JSON files, Python
> dataclasses, or a hybrid?"

`§24.1` defines two constraints on whatever answer is chosen:

* Registries must expose the same validated schema regardless of source format.
* Definitions must remain testable without GUI.

`§1.114` further requires that "authoritative component definitions must be loaded into shared registries during application bootstrap", so the choice is about the *source* format the registry consumes, not whether a registry exists.

S1.B implementation cannot proceed without picking a concrete format. The validator, registry, and core MVP component set (Resistor, Capacitor, Ground Electric, Constant Voltage, Fixed, Mass, Spring) all need a single canonical definition shape to share.

This ADR closes `§24.1` for Phase 1 and bounds the choice to a single Python-based format. JSON, YAML, or hybrid formats remain possible in Phase 1.5+ via a future ADR that supersedes this one or extends the registry's source-format contract.

## Decision

All built-in registry definition types are Python `frozen=True` dataclasses under `src/shared/registry/builtin/`. This applies uniformly to:

* `ComponentDefinition`
* `PortDefinition`
* `ParameterDefinition`
* Domain definitions (`electrical_analog`, `mechanical_translational`)
* SVG asset descriptors (`SvgAssetRef`)

No JSON, YAML, or other file-based loader is implemented in Phase 1. Registry bootstrap registers definitions via Python imports during `shared/registry/__init__.py` module load. Definitions live next to the registry that consumes them; user-extensible plugin paths are out of scope.

## Alternatives Considered

### Alternative 1: JSON files in Phase 1

**Rejected because:** adds a parsing layer plus validation duplication (Python schema vs JSON schema). Solves no Phase 1 requirement: there is no user-extensibility goal, no on-disk authoring workflow, no late-binding need. The single canonical schema would have to be expressed twice (Python dataclass for runtime, JSON schema for file validation), creating a drift surface for zero present benefit.

### Alternative 2: Hybrid (Python core + JSON user-extensions)

**Rejected because:** premature for Phase 1. Hybrid is reasonable for Phase 1.5+ when user-extensible plugins are a real requirement. Implementing both paths now means designing the plugin loader, the namespace collision policy, the validation merge order, and the security model — all of which are Phase 1.5+ concerns. A future ADR will revisit at that time.

### Alternative 3: YAML files

**Rejected because:** all of Alternative 1's costs plus an additional dependency (`pyyaml`) and a less strict format. No advantage over JSON for this use.

## Consequences

### Positive

* Schema enforced by Python type system; `mypy --strict` catches errors at import time, not at registry-load time.
* Zero file-parsing dependencies, smaller error surface.
* Trivial to test: fixtures are Python values, no on-disk test artifacts, no test-data path resolution.
* Bootstrap flow stays simple: `register(RESISTOR_DEF)` in `shared/registry/__init__.py`.
* Refactor safety: renaming a field on `ComponentDefinition` propagates through IDE/refactoring tools across all definitions.
* Constraint #1 from `§24.1` ("registries expose the same validated schema regardless of source format") is satisfied — the registry's *API* is source-agnostic; a future JSON loader becomes `ComponentRegistry.load_from_json(path)` as an additional entry point, not a replacement.
* Constraint #2 from `§24.1` ("definitions must remain testable without GUI") is trivially met — no `QApplication` or filesystem needed.

### Negative

* User-extensible plugins (file-based definitions) are deferred to Phase 1.5+; until then, adding a custom component requires vendoring the codebase and writing Python.
* Definition changes require a code commit, not a config-only edit.
* Two-way edit workflow (designer GUI writes definition back to disk) is impossible in Phase 1 — definitions are write-once at code-authoring time.

### Risks

* **Risk:** Schema drift between the Python dataclass and any future JSON loader added in Phase 1.5+.
* **Mitigation:** When the JSON loader lands, each dataclass will gain a `from_dict(data: Mapping[str, Any]) -> Self` constructor as the single canonical conversion path. A round-trip test (`to_dict ∘ from_dict == identity`) enforces equivalence. The JSON loader will be a thin wrapper over `from_dict`, with no parallel validation logic.

* **Risk:** Phase 1 ships with hard-coded definitions; a domain expert who wants to tweak a parameter must wait for a release.
* **Mitigation:** Acceptable for Phase 1 scope (engineering preview, not end-user release). Phase 1.5+ JSON path is the documented mitigation route.

## Related ADRs

- ADR-001 Phase 1 Engine Isolation (registry definitions deliberately exclude `equation_metadata` per `01 §22`; equation extraction belongs to Phase 2 and `shared/engine`)
- ADR-003 Workspace UI/Data Separation (registry is consumed by the data layer, not the UI; this ADR is consistent with that boundary)

## References

- `specs/01_library_requirements.md` §24.1 (the Open Question this ADR closes)
- `specs/01_library_requirements.md` §1.114 (registry-based bootstrap requirement)
- `specs/01_library_requirements.md` §6 (Component Definition Schema)
- `specs/02_workspace_requirements.md` §9 (Parameter Schema)
- `specs/02_workspace_requirements.md` §11.1 (forward-compatibility containers)
- `specs/02_workspace_requirements.md` §13 (Port System)
- `specs/06_data_flow_and_architecture.md` §3 (Module Initialization Order — registry bootstrap)
