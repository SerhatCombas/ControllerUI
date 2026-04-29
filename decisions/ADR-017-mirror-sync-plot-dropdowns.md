# ADR-017: Mirror Sync Plot Dropdowns

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S2  
**Supersedes:** —  
**Superseded by:** —

## Context

The user can change the plot type of a slot from two places:

* **Configuration panel** → Plot Layout tab → per-slot dropdown
* **Result panel** → per-plot header dropdown (caret next to title)

These two surfaces edit the same underlying `plot_layout.slots[i].plot_type` field. Without coordination:

* changing one dropdown leaves the other showing stale state
* the user wonders which one is "true"
* widget-local cached state can drift

## Decision

The two dropdown surfaces are **mirrored**: they always show the same value because they read from and write to the **same model field**.

Implementation rules:

* both dropdowns subscribe to the `plotLayoutChanged` signal of the underlying `PlotLayout` model
* changing one dropdown triggers a model mutation, which emits the signal, which updates both dropdowns
* there is **no separate "default" vs "current" state**; one source of truth governs both UIs
* both dropdowns use the same group structure (per ADR-015)
* widget instances may be different Qt objects, but they must subscribe to the same model signals; widget-local cached state is **forbidden**

The flow:

```
User changes Configuration dropdown for slot 0
  → ChangePlotTypeCommand executes
    → PlotLayout.set_plot_type(slot_index=0, plot_type="bode")
      → plotLayoutChanged signal emitted
        → Configuration dropdown for slot 0 updates (no-op, already correct)
        → Result panel header dropdown for slot 0 updates
```

The reverse flow (changing the header dropdown) is symmetric.

The same principle applies to channel selection (per ADR-016): if a future UI exposes channel selection from both surfaces, they must mirror via the same model field.

## Alternatives Considered

### Alternative 1: Separate state per dropdown

Each dropdown maintains its own state.

**Rejected because:**

* Two sources of truth for the same logical value
* Drift is inevitable
* Reconciliation logic is complex and error-prone

### Alternative 2: Configuration as primary, Result as read-only

Make Configuration the editor and Result a passive display.

**Rejected because:**

* Hostile UX: user wants to change plot type from where they're looking
* Per-plot header dropdowns are a natural affordance

### Alternative 3: Polling

Have one dropdown poll the other.

**Rejected because:**

* Wasted CPU
* Latency between change and update
* Qt's signal system is the right tool

## Consequences

### Positive

* No drift
* No cached widget state to reconcile
* New dropdown surfaces (e.g., a future toolbar button) automatically participate
* Tests can verify by changing one dropdown and asserting the other updates

### Negative

* Slot widgets must subscribe to and disconnect from model signals correctly (lifecycle)
* Slightly more boilerplate than a "primary + secondary" design

### Risks

* Signal disconnection bugs (widget destroyed but signal still connected)
* Mitigation: per `09 §10.3`, long-lived objects explicitly disconnect signals; tests verify cleanup

## Related ADRs

- ADR-015 Result Panel Unified With Grouped Dropdown
- ADR-016 channel_selection.kind Schema

## References

- `03_configuration_requirements.md` §14.4.1 (Per-Plot Header Dropdown Visual), §14.4.2 (Dropdown Synchronization)
- `05_simulation_and_results_requirements.md` §14.5 (Header and Advanced Controls)
- `06_data_flow_and_architecture.md` §14 (Result Panel Flow)
- `07_implementation_order.md` §16.17 (S2 verification)
