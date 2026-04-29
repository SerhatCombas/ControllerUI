# ADR-011: Dimensional Analysis Policy

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S2  
**Supersedes:** —  
**Superseded by:** —

## Context

Engineering models involve quantities with units: voltage in volts, mass in kilograms, capacitance in farads, etc. The application must:

* allow users to enter parameter values with units (e.g., `1 kΩ`, `100 µF`, `2.5 kg`)
* validate that user-entered units are compatible with the parameter's expected dimension
* normalize values to a canonical internal unit for computation
* preserve user-typed units in display and persistence
* prevent unit mismatches between connected components

The question: how strictly does the application enforce dimensional analysis, and where does the responsibility live?

## Decision

The project applies a **light dimensional analysis policy**:

* **Parameter schemas** (in component definitions) declare a canonical unit per parameter (e.g., `resistance` in `ohm`, `capacitance` in `farad`)
* **Parameter values** are stored internally in the canonical unit (a single floating-point number)
* **User-entered units** are normalized to the canonical unit at entry; the original entered string is preserved in metadata for display
* **Cross-component dimensional checks** are limited to: same-domain ports must have compatible across/through types (which is enforced by domain compatibility, not dimensional analysis per se)

Phase 1 implements parameter-level unit handling (entry, normalization, display, persistence).

Phase 2+ may add stricter dimensional analysis if equation extraction reveals dimensional inconsistencies.

A library like `pint` is **not** required for Phase 1; simple scale-factor tables suffice (e.g., `kΩ = 1000 ohm`). Phase 2+ may adopt `pint` if more sophisticated unit algebra is needed.

Errors:

* `error.parameter.unit_mismatch` — user enters incompatible unit
* `warning.parameter.unit_normalized` — value normalized; user is informed but not blocked

## Alternatives Considered

### Alternative 1: Strict full dimensional analysis with `pint`

Use `pint` everywhere; every quantity is a `Quantity` with units.

**Rejected because:**

* Heavy runtime cost (Quantity wrapping on every parameter)
* Steeper learning curve for contributors
* Many parameters (e.g., flags, integers) don't have units; wrapping them is awkward
* `pint`'s unit registries can drift across versions

### Alternative 2: No unit handling

Treat all parameter values as dimensionless numbers; rely on the user to use correct units.

**Rejected because:**

* User-hostile: kΩ vs Ω vs MΩ ambiguity is too easy to get wrong
* Loses the educational value of unit display
* Cross-component sanity checks become impossible

### Alternative 3: Unit metadata only, no validation

Store unit strings but don't validate.

**Rejected because:**

* Unit strings drift to inconsistency
* Cross-component checks become brittle

## Consequences

### Positive

* User can enter `1 kΩ` and the system understands
* Internal computation is fast (single floats)
* Display preserves user's preferred unit
* Phase 2+ can upgrade to `pint` without rewriting Phase 1 code

### Negative

* Requires per-parameter scale-factor tables
* Cross-domain dimensional analysis is limited

### Risks

* Scale factor tables may have errors (e.g., `mF` vs `µF`)
* Mitigation: tests cover all canonical-to-display conversions; common units are tabulated explicitly

## Related ADRs

- ADR-002 Hybrid ULID Identity Model

## References

- `01_library_requirements.md` §9 (Parameter Definition Schema)
- `02_workspace_requirements.md` §11 (Component Data Model)
- `07_implementation_order.md` §16.11 (S2 verification)
- `11_error_code_catalog.md` §7.3 (Parameter Errors)
