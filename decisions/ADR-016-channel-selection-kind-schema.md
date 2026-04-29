# ADR-016: channel_selection.kind Schema

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S2  
**Supersedes:** —  
**Superseded by:** —

## Context

Each plot slot needs to know **what data to plot**. Different plot types have different selection semantics:

* time response: select a list of channels (states, inputs, outputs)
* Bode plot: select an input/output pair (one input → one output)
* pole-zero: applies to the entire system, no per-channel selection
* root locus: select an I/O pair plus a gain parameter

A naive design would have a single `signals: list[str]` field that means different things in different contexts. This is the legacy approach used in early prototypes.

The legacy approach is fragile:

* the renderer must guess what `signals` means for the current plot type
* changing plot type requires rewriting `signals` semantics
* extending to new selection kinds (e.g., system-wide) requires special cases everywhere
* type information is lost in serialization

## Decision

Plot slot configuration uses a **typed `channel_selection`** schema with an explicit `kind` discriminator:

```python
@dataclass
class ChannelSelection:
    kind: Literal["channels", "io_pair", "system_wide"]
    channels: list[str] | None = None        # when kind="channels"
    input: str | None = None                 # when kind="io_pair"
    output: str | None = None                # when kind="io_pair"
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)
```

The three kinds:

* **`channels`** — select a list of result channels (used by time-domain plots)
* **`io_pair`** — select one input and one output (used by Bode, Nyquist, root locus, step response)
* **`system_wide`** — no selection, applies to the entire system (used by pole-zero, eigenvalue)

The plot renderer dispatches on `kind`. Adding a new selection kind adds a new variant; existing kinds remain stable.

The legacy `signals: list[str]` field is **forbidden** in new code. Migration `0.1.0 → 0.2.0` translates legacy fields to the new schema.

Plot type → selection kind mapping is fixed in `08 §16.4`:

| Plot Type | kind |
|---|---|
| time response | channels |
| state variables | channels |
| input/output signal | channels |
| force | channels |
| road profile | channels |
| Bode | io_pair |
| Nyquist | io_pair |
| pole-zero | system_wide |
| root locus | io_pair |
| eigenvalue | system_wide |
| step response | io_pair |

When the user changes plot type within the same `kind`, the existing `channel_selection` is preserved. When the user changes plot type to a different `kind`, `channel_selection` resets.

## Alternatives Considered

### Alternative 1: Untyped `signals` list

Use a single `signals: list[str]` with semantics depending on plot type.

**Rejected because:**

* Type-unsafe; renderer must guess
* Hard to extend
* Migration nightmares
* Used in early prototypes; **forbidden** going forward

### Alternative 2: Per-plot-type selection schemas

Define a separate selection class per plot type.

**Rejected because:**

* Plot types within the same `kind` share selection logic; duplication
* Adding a new plot type requires a new selection class
* Renderer dispatch becomes a per-plot-type explosion

### Alternative 3: Free-form selection dict

Use a generic `dict[str, Any]` for selection.

**Rejected because:**

* No schema enforcement
* Renderer must validate dict shape every time

## Consequences

### Positive

* Type-safe selection across all plot types
* Renderer dispatches cleanly on `kind`
* Migration from legacy is well-defined
* New selection kinds add cleanly without breaking existing ones
* `extensions` field provides forward compatibility

### Negative

* Slightly more verbose than a flat list for simple cases
* Migration from legacy `signals` is required

### Risks

* Selection kind for a new plot type may not fit existing kinds
* Mitigation: new kinds can be added; the schema is extensible

## Related ADRs

- ADR-013 StabilityAnalysisArtifact
- ADR-015 Result Panel Unified With Grouped Dropdown
- ADR-017 Mirror Sync Plot Dropdowns

## References

- `03_configuration_requirements.md` §8 (Plot Layout Settings), §8.6 (Plot Type Compatibility)
- `05_simulation_and_results_requirements.md` §14.4 (Plot Slot Binding)
- `08_codex_execution_rules.md` §16.4 (Plot Binding Quick Lookup)
- `07_implementation_order.md` §16.16 (S2 verification)
