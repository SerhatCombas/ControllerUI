# ADR-008: Bond Graph Causality

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S3  
**Supersedes:** —  
**Superseded by:** —

## Context

Equation extraction from a multi-domain physical system requires assigning **causality** to each component port — that is, deciding which variable (across or through) is the input and which is the output for that port in the assembled equations.

Bond Graph theory provides a principled way to assign causality:

* effort sources impose effort (across variable: voltage, force, torque)
* flow sources impose flow (through variable: current, velocity, angular velocity)
* energy storage elements (inductors, capacitors, masses, springs) prefer integral causality
* dissipative elements (resistors, dampers) accept either causality
* junctions enforce conservation laws

Without explicit causality, the equation extractor faces:

* algebraic loops that cannot be resolved
* multiple equation orderings that yield different solver behavior
* ambiguity when handling dependent storage elements (e.g., two capacitors in parallel)
* difficulty supporting cross-domain coupling (transformers, gyrators)

## Decision

The application uses **Bond Graph causality assignment** during DAE extraction in Stage S3.

* domain definitions (`01 §7.2`) declare across and through variables for each domain
* component definitions declare causality preferences (preferred / acceptable / forbidden) for each port
* the equation pipeline performs **Sequential Causality Assignment Procedure (SCAP)** during DAE assembly
* causality conflicts produce a structured error (`error.equation.causality_conflict` per `11 §8.1`)

Phase 1 reserves causality metadata fields in component definitions and connection style/extensions but does **not** interpret them. Causality assignment is a Stage S3 (Phase 2A) responsibility.

The Bond Graph approach is internal to the equation pipeline. The user is **not** required to think in Bond Graph terms; the UI continues to show standard schematic symbols and connection lines.

## Alternatives Considered

### Alternative 1: No causality, brute-force solving

Let the symbolic backend (CasADi) figure out the equations directly.

**Rejected because:**

* Algebraic loops require explicit decisions
* Some valid topologies become unsolvable
* DAE index reduction needs causality information

### Alternative 2: Modelica-style flat equations

Use undirected equations and let the compiler sort it out.

**Rejected because:**

* Requires a Modelica-like compiler infrastructure (rejected per `01 §19`)
* Loses the educational and diagnostic value of explicit causality

### Alternative 3: User-specified causality

Require the user to assign causality manually.

**Rejected because:**

* Hostile to engineering users who think in schematic terms
* Causality is a derived concept, not a design intent

## Consequences

### Positive

* Principled algebraic loop resolution
* Supports multi-domain coupling (transformers, gyrators) cleanly
* DAE index reduction benefits from causality information
* Diagnostic output ("port X cannot be in derivative causality") becomes actionable

### Negative

* Implementation complexity in Stage S3
* Some unconventional topologies may produce causality conflicts that surprise users
* Causality concepts must be hidden from the UI (Phase 1) but visible in error messages (Phase 2)

### Risks

* SCAP implementation may have edge cases with dependent storage elements
* Mitigation: Phase 1 reserves causality fields; Phase 2 implements SCAP with extensive tests; conflicts raise structured errors

## Related ADRs

- ADR-004 Equation Builder Ownership
- ADR-009 DAE Reduction Strategy

## References

- `01_library_requirements.md` §7.2 (Bond Graph Preparation in domain definitions)
- `02_workspace_requirements.md` §39 (Bond Graph Preparation in connections)
- `04_model_equations_requirements.md` §8 (Causality and Domain Coupling)
- `07_implementation_order.md` §16.8 (S3 verification)
