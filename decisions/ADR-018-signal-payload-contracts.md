# ADR-018: WorkspaceModel Signal Payload Contracts

**Status:** Accepted  
**Date:** 2026-05-10  
**Deciders:** Serhat Combas  
**Stage:** S1  
**Supersedes:** —  
**Superseded by:** —

## Context

`02 §4.1` lists 12 signals that `WorkspaceModel` must emit, but specifies them at a name-and-shape level only (e.g., `componentMoved(component_id, old_pos, new_pos)`). The payload **types** and the **rule** for choosing payload structure are not stated:

* What Python type carries `component_id`? (Implied: `str`, but not formal.)
* Is `old_pos` a `QPointF`, a `tuple[float, float]`, a `Vec2` dataclass?
* When a subscriber receives `componentChanged(component_id)`, how does it discover *what* changed?
* Is a subscriber permitted to query `model.get_component(component_id)` from inside the slot, or must the payload be fully self-contained?

Without a formal contract:

* Subscribers may guess at shapes and break when implementations change
* Two equally-defensible payload designs (delta-bearing vs id-only) get chosen ad-hoc per signal
* Race-condition reasoning is impossible because synchronous-emission semantics are not codified
* Future schema migrations cannot detect contract drift

This ADR sets the formal contract before `WorkspaceModel` is implemented in S1.3.

## Decision

### Signal payload type table

The 12 signals listed in `02 §4.1` carry exactly the following payloads. No additional fields, no overloads. Renames are forbidden (use `componentChanged`/`connectionChanged` as catch-all instead of adding new signals).

| Signal | Payload | Self-contained? |
|---|---|---|
| `componentAdded(component_id)` | `str` | No — refetch |
| `componentRemoved(component_id)` | `str` | No (model no longer has it; subscriber removes from view) |
| `componentChanged(component_id)` | `str` | No — refetch |
| `componentMoved(component_id, old_pos, new_pos)` | `(str, QPointF, QPointF)` | Yes |
| `componentRotated(component_id, old_rotation, new_rotation)` | `(str, float, float)` | Yes |
| `connectionAdded(connection_id)` | `str` | No — refetch |
| `connectionRemoved(connection_id)` | `str` | No |
| `connectionChanged(connection_id)` | `str` | No — refetch |
| `selectionChanged(snapshot)` | `SelectionSnapshot` (frozen dataclass) | Yes |
| `validationChanged(report)` | `ValidationReport` (frozen dataclass) | Yes |
| `modelReset()` | `()` | Yes (semantics: discard + rebuild from model) |
| `dirtyChanged(is_dirty)` | `bool` | Yes |

Component IDs follow the ULID-prefixed format (`cmp_…`, `con_…`) per ADR-002. Coordinates use `QPointF` to match `QGraphicsScene` coordinate semantics so subscribers do not perform conversions. Rotation is a `float` measured in degrees. The 90° quantization rule from `02 §22`/`§23` is enforced at the mutation API layer (`rotate_component` validates input), **not** in the signal payload — keeping the payload `float` means the signal contract stays stable if `02` later admits free or non-orthogonal rotation. Subscribers must treat the value as an arbitrary degree measurement, not as a member of a closed `{0, 90, 180, 270}` set.

### Payload design principle

The asymmetry between `componentMoved(id, old, new)` (delta-bearing) and `componentChanged(id)` (id-only) is intentional and follows a single rule:

> **Payload contains state delta (old + new) when the field set is small, fixed, and undo/redo benefits from race-free observation. Payload contains only `id` when the field set is wide or dynamic; subscribers refetch via model query.**

Concretely:

* `componentMoved` → 2 floats per coordinate, fixed shape; carrying the delta avoids races and lets command-merging (per ADR-005) inspect old/new without touching the model.
* `componentRotated` → 1 float (degrees); same rationale. Width is `float` rather than `int` so future free-rotation does not break the signal contract.
* `componentChanged` → catch-all for parameter, label, tag, lock, annotation, and metadata edits. The mutable field set is wide and varies per component definition. Adding dedicated signals (`parameterChanged`, `labelChanged`, `tagsChanged`, …) would inflate `02 §4.1` without payoff. Subscribers refetch the full instance.

When future signals are added, this rule decides their shape: small + fixed → delta; wide + dynamic → id-only.

### Synchronous emission semantics

`WorkspaceModel` emits signals **after** its internal state is updated, on the same thread, using Qt's default `Qt.AutoConnection` (which becomes `Qt.DirectConnection` for same-thread sender/receiver pairs).

Consequence:

> **Phase 1: signal emission is synchronous. A subscriber that refetches via `model.get_component(component_id)` from inside its slot reads the post-mutation state corresponding to *this exact signal*.**

This rules out:

* Emitting a signal *before* state is updated (subscriber would refetch stale state)
* Queueing emissions across multiple mutations on the same thread (subscriber would refetch a state that combines several user actions)
* Cross-thread queued emission with id-only payloads (subscriber refetch would race with subsequent mutations)

#### Multi-threaded mutation: deferred

Multi-threaded mutation is **explicitly out of scope** for Phase 1. When a future phase introduces it, the synchronous refetch guarantee above will break: a subscriber receiving `componentChanged(id)` may refetch a state that has already been further mutated on another thread.

Supporting cross-thread mutation will require an **ADR amendment** that addresses race-free refetch. Two known strategies:

* **Snapshot payloads:** add the post-mutation snapshot to the payload, removing the need to refetch.
* **Queued connections with quiescence guarantees:** subscribers run on the emitting thread's queue; the model commits to no further mutations between emit and slot execution.

Neither is implemented; both are documented here so the future change is recognized as an ADR-level decision rather than a silent implementation detail.

### Subscriber contract

Subscribers MUST:

* Treat payload arguments as authoritative for the signal's purpose (e.g., `old_pos`/`new_pos` are exact pre/post values; do not reconcile against a refetch).
* Refetch via `model.get_component(component_id)` only inside `componentChanged` / `componentAdded` / `connectionChanged` / `connectionAdded` slots, and only on the emitting thread.

Subscribers MUST NOT:

* Cache `componentChanged` payloads expecting them to carry diff information — none is provided.
* Mutate the model from inside a slot. UI mutations go through commands (ADR-005); model-internal cross-mutations risk reentrancy and are explicitly out of scope for the synchronous-emission guarantee.

## Alternatives Considered

### Alternative 1: Uniform delta payloads on every signal

Always carry old/new state on every signal, including `componentChanged`.

**Rejected because:**

* The mutable field set on a component is wide and varies per definition (parameters, label, tags, annotations, metadata, lock). Carrying old/new for all of them either bloats every signal or requires per-field signal explosion.
* Diff payload would need per-component-type schemas, coupling the signal contract to the component registry.

### Alternative 2: Uniform id-only payloads on every signal

Replace `componentMoved(id, old, new)` with `componentMoved(id)` and force refetch.

**Rejected because:**

* Loses race-free old/new observation that command-merging (ADR-005) needs.
* `componentMoved` is high-frequency (drag); model-query cost adds up.
* Animations and undo previews need both old and new without an extra hop.

### Alternative 3: Payload as opaque dict

Use `dict[str, Any]` for all payloads.

**Rejected because:**

* Type-unsafe; fights mypy strict mode.
* Subscriber must validate dict shape every time.
* Defeats the point of formal Qt signal types.

### Alternative 4: `int` rotation payload

Restrict `componentRotated` to `(str, int, int)` matching the current `02 §22`/`§23` quantization.

**Rejected because:**

* Couples the signal contract to the current quantization rule. A future spec change admitting 45° or free rotation would force a backwards-incompatible signal change.
* The quantization rule belongs in the mutation API (input validation), not the observation API (signal payload). DRY: enforcing it twice introduces drift risk.

## Consequences

### Positive

* Type-checked subscribers; mypy strict catches signature drift.
* Race-free reasoning under Phase 1's synchronous-emission guarantee.
* A single rule (delta vs id-only) makes future signal additions self-evident.
* No per-component-type signal explosion.
* `componentMoved`/`componentRotated` deltas feed ADR-005 command merging directly.
* Float rotation payload is forward-compatible with future free-rotation features.

### Negative

* The asymmetry between delta-bearing and id-only signals must be explained on first reading; this ADR is the explanation.
* Subscribers of `componentChanged` must hold a reference to the model; cannot be wired purely from the signal payload.

### Risks

* A future contributor may add a new signal with a delta payload for a wide field, violating the principle.
* *Mitigation:* this ADR's design principle is the test; PR review enforces it. A future architecture test could lint signal shapes against the field-set criterion.
* Multi-threaded mutation in a later phase would invalidate the synchronous refetch guarantee.
* *Mitigation:* the ADR explicitly defers cross-thread to amendment; introducing it triggers a new ADR with snapshot or queued-connection design.

## Related ADRs

- ADR-002 Hybrid ULID Identity Model (component/connection ID format)
- ADR-003 Workspace UI/Data Separation (signal/slot is the cross-layer interface)
- ADR-005 Command Stack with QUndoStack (consumes `componentMoved`/`componentRotated` deltas for merging)
- ADR-019 Batch Mutation Mode and WorkspaceChangeSet (introduces `modelChanged` as 13th signal; complementary contract)
- ADR-020 Dirty Tracking Semantics (`dirtyChanged` payload semantics)

## References

- `02_workspace_requirements.md` §3 (Source of Truth), §4.1 (Required Workspace Signals), §4.2 (UI Reaction Rules), §4.3 (No Direct Mutation Rule), §22 (Move/Delete), §23 (Rotation)
- `06_data_flow_and_architecture.md` §4.2 (SystemModelingModule responsibilities)
- `09_coding_standards.md` §7.2.2 (Signal naming), §10 (PySide6 conventions)
