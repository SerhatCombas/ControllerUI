# ADR-015: Result Panel Unified With Grouped Dropdown

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S6  
**Supersedes:** —  
**Superseded by:** —

## Context

The application produces two kinds of results that the user wants to view:

* **simulation results** — time-series data from `SimulationResultArtifact`
* **stability analysis results** — frequency-domain and algebraic data from `StabilityAnalysisArtifact`

A naive design would have two separate panels: a "Simulation" panel for time-domain plots and a "Stability" panel for Bode/pole-zero plots.

This is awkward because:

* the user wants to see both kinds of plots side by side (e.g., step response + Bode for the same controller)
* the panels duplicate UI infrastructure (slot management, dropdowns, fullscreen)
* switching between panels breaks the visual workflow

## Decision

The application has **one unified Result Panel** with **four configurable plot slots** in a 2×2 grid.

Each slot can render any of the supported plot types:

* time-domain: time response, state variables, input/output signal, force, road profile, step response (when from simulation)
* frequency-domain: Bode, Nyquist
* algebraic: pole-zero, root locus, eigenvalue
* hybrid: step response (may use either simulation or analysis)

A **grouped dropdown** in each slot's header (and mirrored in the Configuration panel, per ADR-017) lets the user choose the plot type. The dropdown groups options by domain:

* Time-domain group
* Frequency-domain group
* Algebraic group
* Unknown group (only shown when project file contains unrecognized plot types)

The slot's plot type determines which artifact reference it uses:

* time-domain → `SimulationResultArtifact` via `result_ref`
* frequency-domain and algebraic → `StabilityAnalysisArtifact` via `analysis_ref`
* step response (special) → either, with priority rule (per `05 §15.2`)

When a slot's required artifact is missing, the slot shows a placeholder with an action button (e.g., "Run Simulation", "Linearize and Analyze") rather than disabling the dropdown.

## Alternatives Considered

### Alternative 1: Two separate panels (Simulation, Stability)

Separate panels for time-domain and frequency-domain.

**Rejected because:**

* User cannot view step response + Bode side by side
* Duplicates infrastructure (dropdowns, fullscreen, channel selection)
* Tabs or panel switching breaks workflow

### Alternative 2: One panel, no grouping

Single panel with a flat plot-type list.

**Rejected because:**

* Many plot types: visual clutter
* Loses the domain context that helps users find the right plot

### Alternative 3: Plot type per artifact type

Auto-select plot types based on which artifact is present.

**Rejected because:**

* Hostile UX: user wants to choose what to see, not be told
* Multiple artifacts may exist; selection is ambiguous

## Consequences

### Positive

* Side-by-side viewing of simulation and stability plots
* Single source of UI infrastructure (one slot widget reused 4×)
* Consistent fullscreen, channel selection, header behavior
* Clear separation of concerns: artifact production vs. plot rendering

### Negative

* Slot rendering must dispatch on plot type and artifact kind
* Step response special case (uses either artifact) needs careful handling

### Risks

* Plot type taxonomy may grow over time
* Mitigation: groups are extensible; new plot types added to existing group or as a new group

## Related ADRs

- ADR-013 StabilityAnalysisArtifact
- ADR-016 channel_selection.kind Schema
- ADR-017 Mirror Sync Plot Dropdowns

## References

- `03_configuration_requirements.md` §8 (Plot Layout Settings), §14.4 (Plot Layout UI)
- `05_simulation_and_results_requirements.md` §13 (Result Panel), §14 (Plot Slots), §15.2 (Step Response)
- `06_data_flow_and_architecture.md` §14 (Result Panel Flow)
- `07_implementation_order.md` §16.15 (S6 verification)
- `08_codex_execution_rules.md` §16.4 (Plot Binding Quick Lookup)
