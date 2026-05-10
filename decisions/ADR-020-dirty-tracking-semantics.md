# ADR-020: Dirty Tracking Semantics

**Status:** Accepted  
**Date:** 2026-05-10  
**Deciders:** Serhat Combas  
**Stage:** S1  
**Supersedes:** —  
**Superseded by:** —

## Context

`02 §29.7` lists which operations should and should not mark the project dirty:

* **Dirty:** add/delete/move/rotate component, add/delete/modify connection, parameter changes, label changes, simulation/configuration changes
* **Non-dirty:** zoom, pan, hover, temporary previews, selection changes

It also states three clear paths for clearing dirty:

* Successful save → `dirty = False`
* Undo back to the saved state → `dirty = False`
* Recovered autosave files open as dirty until explicitly saved

But several lower-level questions are not specified:

* Does an "edit" that produces no actual change (e.g., `move_component(c, p)` where `c` is already at `p`) mark the model dirty?
* When does `dirtyChanged(is_dirty)` emit — on every mutation, or only on transitions?
* What is the dirty bit's initial state on a freshly-constructed `WorkspaceModel`?
* How does the dirty bit interact with the S1.7 `QUndoStack.cleanState` mechanism?
* What clears dirty in S1, before persistence is implemented?

Without formal answers, implementations can drift: dirty-on-every-mutation creates spam; dirty-on-no-op creates phantom dirty; dirty-clear-on-undo without `cleanState` is impossible.

This ADR codifies the answers consistent with `02 §29.7` and the staged build plan.

## Decision

### Meaningful-edit principle

Dirty tracks **structural and semantic mutations of model state**. It does not track:

* Selection changes (selection is UI affordance, not project state)
* Validation runs (validation is derived state)
* View state (zoom, pan, hover, temporary previews)
* No-op mutations (see below)

This aligns with `02 §29.7` but tightens the boundary: validation result *changes* per `validationChanged` are observable but do **not** mark dirty. Validation is a function of model state; if model state did not change, no dirty bit flips.

### Initial state

A newly constructed `WorkspaceModel` is **clean** (`is_dirty == False`). The first meaningful edit transitions to dirty and emits `dirtyChanged(True)`. Construction itself does **not** emit `dirtyChanged` — subscribers that need the initial state read it via `model.is_dirty` after wiring slots.

The autosave-recovery path (`02 §30`, S2 work) is the documented exception: after `from_dict()` loads a recovery file, the load path explicitly sets `is_dirty = True` and emits `dirtyChanged(True)` so subscribers update their indicators. Normal `from_dict()` of a saved file leaves the model clean.

### No-op suppression

Mutation methods detect same-value calls and suppress the dirty transition (and the corresponding fine-grained signal):

```python
def move_component(self, component_id: str, new_pos: QPointF) -> None:
    current = self._components[component_id].position
    if _approx_equal_qpointf(current, new_pos):
        return  # no-op: no signal, no dirty change
    ...
```

Applies to: `move_component`, `rotate_component`, `set_parameter`, `set_custom_label`, `set_locked`, `set_tags`, `set_annotations`. Add/remove operations are intrinsically non-no-op (they change the component set), so no suppression is needed there.

#### Equality semantics

The naïve approach — Python `==` everywhere — fails on floating-point. Drag-snap calculations like `grid_size * round(pos.x() / grid_size)` produce positions that are numerically distinct from the current position by a few ULPs but functionally identical. Exact `==` would dirty the project on what the user perceives as a no-op.

Equality rules per type:

| Type | Rule |
|---|---|
| `QPointF` (positions) | Squared-distance tolerance: `(new.x() - cur.x())**2 + (new.y() - cur.y())**2 < ε**2` with **ε = 1e-6** scene units (one micron) |
| `float` (rotation, numeric parameters) | Absolute-difference tolerance: `abs(new - cur) < ε` with the same ε = 1e-6 |
| `int`, `bool`, `str`, `enum` | Exact `==` |
| Frozen dataclass parameter values | Field-by-field comparison; nested floats follow the float rule above |
| `dict[str, Any]` (annotations, tags) | Exact `==` (caller is responsible for canonicalization) |

ε = 1e-6 was chosen because:

* one micron in scene units is well below any user-perceivable difference
* it is well above any plausible accumulation error from grid-snap rounding in 64-bit float arithmetic
* it is small enough that two intentionally-distinct positions (smallest grid step ≥ 1.0 per `02 §5.2`) are never collapsed

For `set_parameter`, the equality check is dispatched per parameter schema (defined in `01_library_requirements.md` and instantiated per component definition via `ParameterDefinition`, `02 §9.1`). Float parameters use the float rule above; `int`/`bool`/`str`/`enum` parameters use exact `==`; composite parameter values follow field-by-field rules. The dispatch lives in the parameter validation pipeline (S1.6); the S1.3 implementation may stub `set_parameter`'s no-op suppression with exact `==` until the dispatch lands and revisit it then.

### `dirtyChanged` emits on transitions only

`dirtyChanged(is_dirty: bool)` emits when the dirty bit transitions:

* `False → True` on the first meaningful edit after a clean state
* `True → False` on `reset()`, on save (S2), on undo back to a saved state (S1.7)

It does **not** emit on every dirty mutation while already dirty. This avoids spam in the status bar and matches the Qt convention that signals carry actual state changes.

The synchronous-emission rule from ADR-018 applies: `dirtyChanged` emits after the dirty bit is updated, on the same thread.

### Dirty clear paths in Phase 1

The clear paths land across multiple stages. ADR-020 records what S1 owns and what is deferred:

| Path | Stage | Status in S1 |
|---|---|---|
| `model.reset()` clears dirty | S1.3 | **In scope** — implemented in `WorkspaceModel.reset()` |
| Successful save clears dirty | S2 | Deferred — `to_dict`/persistence is S2 work |
| Undo to saved state clears dirty | S1.7 | Deferred — requires `QUndoStack.cleanState` integration |
| Autosave-recovered file opens dirty | S2 | Deferred |

In S1.3 proper, only `reset()` clears dirty. The other paths are wired in their respective stages and reference this ADR for semantics.

### Save-clean atomicity (S2 deferral)

When persistence is implemented in S2, the save → `setClean()` transition must be **atomic with the snapshot that was actually written**:

* Either save is synchronous on the UI thread and `setClean()` runs immediately after a successful write (no other mutations can interleave).
* Or save captures a snapshot (`to_dict()` result) on the UI thread and `setClean()` runs only if no mutations occurred between snapshot capture and write completion.

A naïve async save that calls `setClean()` after I/O completes is **incorrect**: the model may have been mutated during the write, and clearing dirty would falsely advertise the on-disk file as matching the in-memory state.

The exact mechanism is the responsibility of the S2 persistence ADR. ADR-020 records the constraint here so it is not lost in the handoff.

### `QUndoStack.cleanState` integration (S1.7)

When the command stack is introduced (ADR-005, S1.7), the dirty bit binds to `QUndoStack.cleanState`:

* On save (S2), `undo_stack.setClean()` is called.
* `dirtyChanged` is driven by `QUndoStack.cleanChanged(is_clean)` — `is_dirty = not is_clean`.
* Undoing past the saved state keeps the model dirty; redoing back to it re-clears.

This means: in S1.7+, the dirty bit is a **function of `QUndoStack.cleanState`**, not a separately-maintained flag. The S1.3 implementation maintains an internal `_dirty: bool` flag; the S1.7 wiring replaces that flag with a property bridged to `cleanState`.

This deferral is intentional: a dirty flag without an undo stack is meaningful (`reset()` is the only clear path), and an undo stack without `cleanState` binding is also meaningful (commands track history without dirty integration). They compose at S1.7.

### Status bar dirty indicator

Per `02 §32.2`, the status bar shows the current project file name and dirty indicator (e.g., `quarter_car.systemdesign *`). The `*` symbol is driven by `dirtyChanged`:

* On `dirtyChanged(True)` → append `*` to filename
* On `dirtyChanged(False)` → remove `*`

The status bar is a subscriber, not a source of truth. Its rendering is governed by the transitions emitted by `dirtyChanged`. Because `dirtyChanged` emits on transitions only, the status bar does not rerender on every drag tick.

## Alternatives Considered

### Alternative 1: Emit `dirtyChanged` on every mutation while dirty

`dirtyChanged(True)` re-emitted for each mutation after the first.

**Rejected because:**

* Status bar would re-render on every drag tick.
* Subscribers cannot distinguish "newly dirty" from "still dirty" without external tracking.
* Spammy; loses the signal-on-state-change Qt convention.

### Alternative 2: No no-op suppression — every mutation marks dirty

Treat any call to a mutation method as a meaningful edit, even when values are unchanged.

**Rejected because:**

* `move_component(c, current_pos)` would dirty the project. Easy to trigger from drag-snap when the snap target equals the current position.
* Phantom dirty pollutes saved-state semantics: undoing to a save point would not re-clear dirty if redundant moves had been applied.

### Alternative 3: Exact `==` for floats (caller pre-rounds)

Rely on callers to pre-round positions to grid before invoking `move_component`; suppression uses exact equality.

**Rejected because:**

* Easy to forget at a UI command site; phantom dirty resurfaces silently.
* Drag-snap calculations like `grid_size * round(pos.x() / grid_size)` can still produce sub-ULP drift even with caller-side rounding.
* The cost of the tolerance check is negligible; the cost of debugging phantom dirty is not.

### Alternative 4: Dirty as a public mutable flag

Allow callers to set `model.dirty = True/False` directly.

**Rejected because:**

* Bypasses the meaningful-edit principle.
* Hides the source of dirty changes from logs and audits.
* Conflicts with `QUndoStack.cleanState` integration in S1.7.

The clear paths are explicit methods (`reset()`, persistence in S2, undo-to-clean in S1.7). No public flag.

### Alternative 5: Dirty stays after `reset()`

Treat `reset()` as a major mutation that should mark the project dirty.

**Rejected because:**

* `reset()` is "discard everything"; the natural follow-up is "save as new" or "close without saving". Either way, the dirty bit is meaningless after reset.
* `02 §29.7` lists save as a clear path; `reset()` is a stronger discard-state operation and clears for the same reason.
* User-facing semantics: after `reset()`, the workspace is empty and untouched relative to "no project loaded"; that is a clean state.

## Consequences

### Positive

* Clear contract: dirty tracks model state, nothing else.
* No-op suppression with ε-tolerance eliminates phantom dirty under drag-snap drift.
* Transition-only emission prevents status-bar spam.
* `QUndoStack.cleanState` integration deferred cleanly to S1.7; S1.3 has a small flag that will be replaced.
* Initial-state and recovery-load semantics are explicit; subscribers are not surprised by missing emissions at construction time.

### Negative

* ε-tolerance comparison adds a bit of code for each mutation method — small but non-zero overhead.
* The dirty implementation in S1.3 is a bridge that gets replaced in S1.7; some throwaway code.
* Tolerance ε is a magic constant; tuning it would be a backwards-incompatible change.

### Risks

* A future contributor adds a mutation method without no-op suppression, reintroducing phantom dirty.
* *Mitigation:* this ADR's rule is the test; PR review enforces it. A unit test per mutation method covering the same-value path is recommended.
* `QUndoStack.cleanState` semantics may not match the dirty-bit semantics for compound commands (e.g., paste of N components with an interior failure).
* *Mitigation:* S1.7 work re-evaluates the binding when `QUndoStack` lands; ADR-020 may be amended at that time.
* ε = 1e-6 may be too tight or too loose for a future coordinate system change.
* *Mitigation:* ε is documented as load-bearing here; any change is an ADR amendment.

## Related ADRs

- ADR-003 Workspace UI/Data Separation (`WorkspaceModel` is the source of truth)
- ADR-005 Command Stack with QUndoStack (S1.7 `cleanState` binding)
- ADR-012 Project Package Directory Format (S2 save → `setClean()`)
- ADR-018 WorkspaceModel Signal Payload Contracts (`dirtyChanged(is_dirty: bool)`)
- ADR-019 Batch Mutation Mode and WorkspaceChangeSet (`dirty_changed` aggregate flag)

## References

- `02_workspace_requirements.md` §5.2 (Grid units), §29.7 (Dirty State Semantics), §30 (Autosave and Recovery), §32.2 (Status Bar dirty indicator)
- `06_data_flow_and_architecture.md` §4.2 (SystemModelingModule responsibilities)
- `07_implementation_order.md` §7.8 (S1 WorkspaceModel), §7.13 (S1 Command System), §8.10 (S2 Persistence)
