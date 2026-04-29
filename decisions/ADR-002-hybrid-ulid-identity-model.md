# ADR-002: Hybrid ULID Identity Model

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S1  
**Supersedes:** —  
**Superseded by:** —

## Context

Components and connections need stable identifiers that:

* never change once assigned (used in undo/redo, save/load, cross-references)
* are human-readable when displayed (e.g., for the Component Info Panel and tooltips)
* avoid collisions across copies, clones, and concurrent edits
* can be sorted by creation time for debugging
* survive renaming of display labels

A single identifier scheme cannot satisfy all of these. ULIDs are excellent for stability and sortability but unreadable. Sequential names (`resistor_3`) are readable but conflict on copy/paste and rename. User-typed labels are convenient but unreliable.

The library also has a third ID concept: the **definition_id** (e.g., `electrical.analog.components.resistor`), which identifies a component template, not an instance.

## Decision

Each component instance carries **three identifiers**:

1. **Internal ID** (`id`): ULID with type prefix, e.g., `cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0`. Generated at instance creation, never changed.
2. **Display ID** (`display_id`): human-readable, type+counter, e.g., `resistor_3`. System-generated, unique within the project.
3. **Custom Label** (`custom_label`): user-editable free-form text. Optional.

Connections follow the same pattern with `con_` prefix (`con_01HV...`).

The library's **definition_id** (e.g., `electrical.analog.components.resistor`) is a **fourth, distinct concept** referenced by component instances but not used as a runtime identifier. See `01_library_requirements.md` §6.2.1 for the full distinction.

Stable references throughout the codebase (in `Connection`, undo commands, validation reports, project files, error logs) use the **internal ID**, never the display ID or custom label.

## Alternatives Considered

### Alternative 1: Display ID as primary identifier

Use only `resistor_3`-style names everywhere.

**Rejected because:**

* Breaks on copy/paste (ID collisions)
* Breaks on type rename (e.g., when a definition is renamed via alias)
* Counter regeneration on load is fragile

### Alternative 2: ULID only

Use ULIDs everywhere with no display alternative.

**Rejected because:**

* Unreadable in UI: "Connect cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0 to cmp_01HX..." is hostile
* User cannot meaningfully reference components in conversation or documentation

### Alternative 3: UUID instead of ULID

Use UUIDv4 for internal IDs.

**Rejected because:**

* Not lexicographically sortable by creation time
* Larger character footprint with no offsetting benefit
* ULID provides the same uniqueness with better debuggability

## Consequences

### Positive

* Stable references survive renaming, copy/paste, and migrations
* Display ID is readable in UI and panels
* Custom label is fully user-controlled
* ULID timestamp prefix aids debugging (creation order is visible)
* Distinct definition_id keeps library independent from instances

### Negative

* Three IDs per component is more complex than one
* AI agents and contributors must learn which ID is appropriate in which context
* The `id` field shadows the Python builtin `id()` (acceptable per `09 §7.3` for schema-mandated fields)

### Risks

* AI agents may use the wrong ID in cross-references
* Mitigation: spec sections (`02 §8`, `01 §6.2.1`), ADR cross-references, and architecture tests verify usage patterns

## Related ADRs

- ADR-003 Workspace UI/Data Separation
- ADR-005 Command Stack with QUndoStack
- ADR-012 Project Package Directory Format

## References

- `02_workspace_requirements.md` §8 (full identity model)
- `01_library_requirements.md` §6.2.1 (definition_id vs instance ID)
- `09_coding_standards.md` §7.2.1
